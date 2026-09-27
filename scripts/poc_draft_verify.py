import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

OUT = Path("data/poc")
SYSTEM = "You are a precise Python assistant. Reply with exactly one ```python code block containing only the requested function, with no explanation."
FRONTIER = os.environ.get("POC_FRONTIER_MODEL", "gpt-4.1-mini")
PRICE = {"input": 0.40, "cached_input": 0.10, "output": 1.60}
MIN_RECALL = float(os.environ.get("POC_MIN_RECALL", "0.55"))

TASKS = [
    ("train", "is_palindrome", "Write `is_palindrome(s: str) -> bool` that ignores case and every non-alphanumeric character.",
     "assert is_palindrome('A man, a plan, a canal: Panama')\nassert not is_palindrome('race a car')\nassert is_palindrome('')"),
    ("train", "fizzbuzz", "Write `fizzbuzz(n: int) -> list[str]` returning the FizzBuzz strings for 1..n.",
     "assert fizzbuzz(5) == ['1', '2', 'Fizz', '4', 'Buzz']\nassert fizzbuzz(15)[-1] == 'FizzBuzz'\nassert fizzbuzz(0) == []"),
    ("train", "word_count", "Write `word_count(text: str) -> dict[str, int]` counting lowercase words split on whitespace.",
     "assert word_count('a A b') == {'a': 2, 'b': 1}\nassert word_count('') == {}"),
    ("train", "flatten", "Write `flatten(items: list) -> list` that flattens arbitrarily nested lists.",
     "assert flatten([1, [2, [3, [4]]], 5]) == [1, 2, 3, 4, 5]\nassert flatten([]) == []"),
    ("train", "chunk", "Write `chunk(items: list, n: int) -> list[list]` splitting items into consecutive lists of size n (the last may be shorter).",
     "assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\nassert chunk([], 3) == []"),
    ("train", "roman_to_int", "Write `roman_to_int(s: str) -> int` converting a Roman numeral to an integer.",
     "assert roman_to_int('MCMXCIV') == 1994\nassert roman_to_int('IX') == 9\nassert roman_to_int('LVIII') == 58"),
    ("train", "is_anagram", "Write `is_anagram(a: str, b: str) -> bool`, case-insensitive, ignoring spaces.",
     "assert is_anagram('Dormitory', 'dirty room')\nassert not is_anagram('abc', 'abd')"),
    ("train", "running_sum", "Write `running_sum(nums: list[int]) -> list[int]` returning the cumulative sums.",
     "assert running_sum([1, 2, 3, 4]) == [1, 3, 6, 10]\nassert running_sum([]) == []"),
    ("train", "dedupe", "Write `dedupe(items: list) -> list` removing duplicates while keeping first-seen order.",
     "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\nassert dedupe([]) == []"),
    ("train", "c_to_f", "Write `c_to_f(c: float) -> float` converting Celsius to Fahrenheit, rounded to 1 decimal.",
     "assert c_to_f(100) == 212.0\nassert c_to_f(-40) == -40.0\nassert c_to_f(36.6) == 97.9"),
    ("heldout", "vowel_count", "Write `vowel_count(s: str) -> int` counting a, e, i, o, u in either case.",
     "assert vowel_count('Hello World') == 3\nassert vowel_count('') == 0\nassert vowel_count('AEIOU') == 5"),
    ("heldout", "second_largest", "Write `second_largest(nums: list[int]) -> int | None` returning the second largest distinct value, or None.",
     "assert second_largest([4, 1, 4, 3]) == 3\nassert second_largest([7]) is None\nassert second_largest([]) is None"),
    ("heldout", "capitalize_words", "Write `capitalize_words(s: str) -> str` capitalizing the first letter of each space-separated word and lowercasing the rest.",
     "assert capitalize_words('hello WORLD') == 'Hello World'\nassert capitalize_words('') == ''"),
    ("heldout", "merge_sorted", "Write `merge_sorted(a: list[int], b: list[int]) -> list[int]` merging two sorted lists into one sorted list.",
     "assert merge_sorted([1, 3, 5], [2, 4]) == [1, 2, 3, 4, 5]\nassert merge_sorted([], [1]) == [1]"),
    ("heldout", "digit_sum", "Write `digit_sum(n: int) -> int` returning the sum of the decimal digits of abs(n).",
     "assert digit_sum(1234) == 10\nassert digit_sum(-56) == 11\nassert digit_sum(0) == 0"),
]


def dotenv(key):
    if os.environ.get(key):
        return os.environ[key]
    env = Path(".env")
    for line in env.read_text().splitlines() if env.exists() else []:
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip("'\"")
    return ""


def code_of(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text or "", re.S)
    return m.group(1) if m else (text or "")


def verify(code, tests):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "solution.py").write_text(code)
        Path(d, "test_solution.py").write_text("from solution import *\n\n\ndef test_it():\n" + "".join(f"    {l}\n" for l in tests.splitlines()))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_solution.py"], cwd=d, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout.strip().splitlines() or [""])[-1]


def messages(prompt, answer=None):
    m = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    return m + ([{"role": "assistant", "content": answer}] if answer is not None else [])


def load(name):
    p = OUT / name
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def save(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text("".join(json.dumps(r) + "\n" for r in rows))


def cost(usage):
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    fresh = usage.get("prompt_tokens", 0) - cached
    return round((fresh * PRICE["input"] + cached * PRICE["cached_input"] + usage.get("completion_tokens", 0) * PRICE["output"]) / 1e6, 6)


def stage_frontier():
    key = dotenv("OPENAI_API_KEY")
    done = {r["name"]: r for r in load("frontier.jsonl")}
    rows = []
    for split, name, prompt, tests in TASKS:
        if name in done and done[name]["exit_code"] == 0:
            rows.append(done[name])
            continue
        r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=120, headers={"Authorization": f"Bearer {key}"},
                       json={"model": FRONTIER, "messages": messages(prompt), "max_completion_tokens": 600})
        body = r.json()
        if r.status_code != 200:
            sys.exit(f"frontier {r.status_code} on {name}: {json.dumps(body)[:300]}")
        answer = body["choices"][0]["message"]["content"]
        exit_code, summary = verify(code_of(answer), tests)
        usage = body.get("usage", {})
        rows.append({"split": split, "name": name, "prompt": prompt, "tests": tests, "answer": answer, "model": body.get("model"),
                     "usage": usage, "cost_usd": cost(usage), "exit_code": exit_code, "verify": summary})
        print(f"{split:8} {name:18} exit {exit_code} · {usage.get('completion_tokens')} out tokens · ${cost(usage)}")
        save("frontier.jsonl", rows + [done[n] for _, n, _, _ in TASKS if n in done and n not in {x["name"] for x in rows}])
        time.sleep(float(os.environ.get("POC_FRONTIER_GAP", "7")))
    save("frontier.jsonl", rows)
    print(f"frontier: {sum(r['exit_code'] == 0 for r in rows)}/{len(rows)} verified, ${round(sum(r['cost_usd'] for r in rows), 6)} total")


def memorable(*args):
    home = Path(os.environ.get("MEMORABLE_HOME", OUT / "memorable")).resolve()
    cfg = home / ".memorable" / "config.json"
    if not cfg.exists():
        cfg.parent.mkdir(parents=True, exist_ok=True)
        own = json.loads((Path.home() / ".memorable" / "config.json").read_text())
        cfg.write_text(json.dumps({k: own[k] for k in ("api_url", "api_key")} | {"consent": "read-write", "record_repos": False}))
        cfg.chmod(0o600)
    return subprocess.run(["memorable", *args], capture_output=True, text=True, timeout=120, env=os.environ | {"MEMORABLE_HOME": str(home)})


def stage_memorable():
    rows = load("frontier.jsonl")
    traces = OUT / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    ingested = []
    for r in rows:
        if r["split"] != "train" or r["exit_code"] != 0:
            continue
        sid = f"sess-poc-{r['name']}"
        path = traces / f"{sid}.json"
        path.write_text(json.dumps({"session_id": sid, "harness": "opencode", "task_description": r["prompt"][:200], "tool_calls": [
            {"name": "write", "input": {"file_path": "solution.py"}, "result": {"ok": True}},
            {"name": "bash", "input": {"command": "pytest -q test_solution.py"}, "result": {"exit_code": 0}}]}))
        out = memorable("ingest", str(path.resolve()))
        slug = re.search(r"procedures/[A-Za-z0-9_-]+", out.stdout + out.stderr)
        ingested.append({"name": r["name"], "session_id": sid, "slug": slug.group(0) if slug else None, "ingest": (out.stdout + out.stderr).strip()[:200]})
        print(f"ingest {r['name']:18} -> {ingested[-1]['slug'] or ingested[-1]['ingest']}")
    listed = memorable("list", "--json")
    recalls = []
    for r in rows:
        out = memorable("recall", r["prompt"])
        hits = [(float(s), slug) for s, slug in re.findall(r"^\s*([0-9.]+)\s+(procedures/\S+)", out.stdout, re.M)]
        recalls.append({"name": r["name"], "split": r["split"], "hits": hits[:5], "top": hits[0][0] if hits else 0.0})
        print(f"recall {r['split']:8} {r['name']:18} top {recalls[-1]['top']:.3f} ({len(hits)} hits)")
    by_slug = {i["slug"]: i["name"] for i in ingested if i["slug"]}
    selected = sorted({by_slug[s] for rc in recalls for score, s in rc["hits"] if score >= MIN_RECALL and s in by_slug})
    save("memorable.jsonl", [{"ingested": ingested, "list_status": listed.returncode, "list": listed.stdout[:4000], "recalls": recalls,
                              "min_recall": MIN_RECALL, "selected": selected}])
    print(f"memorable: {len(ingested)} ingested, {len(selected)} traces selected at recall >= {MIN_RECALL}: {selected}")


def river():
    import river_client

    return river_client.Client(api_key=dotenv("RIVER_API_KEY"))


def base_model(client):
    wanted = os.environ.get("RIVER_BASE_MODEL")
    caps = client.get_capabilities()
    names = [c if isinstance(c, str) else getattr(c, "name", str(c)) for c in (caps if isinstance(caps, list) else getattr(caps, "models", caps))]
    if wanted:
        return wanted, names
    nine = [n for n in names if re.search(r"qwen", n, re.I) and re.search(r"(^|[^0-9])9B", n)]
    if not nine:
        sys.exit(f"no ~9B Qwen among River's models {names}; set RIVER_BASE_MODEL")
    return nine[0], names


def stage_train():
    from river_client import LoraConfig
    from river_client.renderers import TrainOnWhat, get_renderer

    mem = load("memorable.jsonl")[0]
    rows = {r["name"]: r for r in load("frontier.jsonl")}
    chosen = [rows[n] for n in mem["selected"]]
    client = river()
    base, names = base_model(client)
    rend = get_renderer(base, thinking=False)
    data = [rend.build_training_example(messages(r["prompt"], r["answer"]), train_on=TrainOnWhat.LAST_ASSISTANT).to_dict() for r in chosen]
    steps = int(os.environ.get("POC_STEPS", str(2 * len(data))))
    log, t0 = [], time.time()
    with client.session() as session:
        model = session.create_model(base, lora=LoraConfig(rank=16))
        for step in range(1, steps + 1):
            fwd, _ = model.train_step(data=[data[(step - 1) % len(data)]], lr=float(os.environ.get("POC_LR", "5e-5")), loss_fn="cross_entropy")
            log.append({"step": step, "loss": fwd.metrics.get("loss"), "secs": round(time.time() - t0, 1)})
            print(log[-1])
        ckpt = model.save_weights(f"poc-draft-{int(t0)}", mode="inference")
    save("train.jsonl", [{"base_model": base, "river_models": names, "examples": [r["name"] for r in chosen], "steps": steps,
                          "checkpoint": ckpt.path, "log": log, "secs": round(time.time() - t0, 1)}])
    print(f"trained {base} LoRA r=16 on {len(chosen)} traces, {steps} steps -> {ckpt.path}")


def draft(client, base, prompt, checkpoint=None):
    m = messages(prompt)
    kw = {"max_tokens": 800, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
    r = (client.chat_complete_from_checkpoint(m, checkpoint_path=checkpoint, base_model=base, **kw) if checkpoint
         else client.chat_complete(m, base_model=base, **kw))
    if r.status_code >= 400:
        return "", {}, f"River {r.status_code}: {r.response_json[:200]}"
    body = json.loads(r.response_json)
    return body["choices"][0]["message"].get("content") or "", body.get("usage", {}), None


def stage_eval():
    tr = load("train.jsonl")[0]
    client = river()
    rows, results = load("frontier.jsonl"), []
    for r in rows:
        for arm, ckpt in (("base", None), ("lora", tr["checkpoint"])):
            text, usage, err = draft(client, tr["base_model"], r["prompt"], ckpt)
            exit_code, summary = verify(code_of(text), r["tests"]) if not err else (1, err)
            results.append({"name": r["name"], "split": r["split"], "arm": arm, "accepted": exit_code == 0, "verify": summary, "draft": text,
                            "draft_out_tokens": usage.get("completion_tokens"), "frontier_out_tokens": r["usage"].get("completion_tokens"),
                            "frontier_cost_usd": r["cost_usd"]})
            print(f"{r['split']:8} {r['name']:18} {arm:4} {'ACCEPT' if exit_code == 0 else 'reject'} · {usage.get('completion_tokens')} tok · {summary[:60]}")
    save("eval.jsonl", results)
    for split in ("train", "heldout"):
        for arm in ("base", "lora"):
            rs = [x for x in results if x["split"] == split and x["arm"] == arm]
            acc = [x for x in rs if x["accepted"]]
            print(f"{split:8} {arm:4} accepted {len(acc)}/{len(rs)} · frontier output tokens avoided {sum(x['frontier_out_tokens'] or 0 for x in acc)}"
                  f" · frontier $ avoided {round(sum(x['frontier_cost_usd'] for x in acc), 6)}")


def stage_local():
    from graduate.registrar.train import BASE_MODEL, LocalBackend

    mem = load("memorable.jsonl")[0]
    rows = load("frontier.jsonl")
    by = {r["name"]: r for r in rows}
    chats = [{"messages": messages(by[n]["prompt"], by[n]["answer"]), "tools": []} for n in mem["selected"]]
    lb, logs, arms = LocalBackend(), [], {}
    for arm, steps in (("base", 0), ("lora", int(os.environ.get("POC_STEPS", str(3 * len(chats)))))):
        t0 = time.time()
        arms[arm] = lb.train(chats, f"poc-local-{arm}", logs.append, steps)
        print(f"local {arm}: {steps} steps in {round(time.time() - t0, 1)} s -> {arms[arm]}")
    results = []
    for r in rows:
        for arm, path in arms.items():
            msg, usage = lb.complete(str(path), messages(r["prompt"]), [])
            exit_code, summary = verify(code_of(msg.get("content")), r["tests"])
            results.append({"name": r["name"], "split": r["split"], "arm": arm, "accepted": exit_code == 0, "verify": summary,
                            "draft_out_tokens": usage.get("completion_tokens"), "frontier_out_tokens": r["usage"].get("completion_tokens"),
                            "frontier_cost_usd": r["cost_usd"]})
            print(f"{r['split']:8} {r['name']:18} {arm:4} {'ACCEPT' if exit_code == 0 else 'reject'} · {summary[:70]}")
    save("eval-local.jsonl", [{"base_model": BASE_MODEL, "loss": logs}] + results)
    for split in ("train", "heldout"):
        for arm in arms:
            rs = [x for x in results if x["split"] == split and x["arm"] == arm]
            acc = [x for x in rs if x["accepted"]]
            print(f"{split:8} {arm:4} accepted {len(acc)}/{len(rs)} · frontier output tokens avoided {sum(x['frontier_out_tokens'] or 0 for x in acc)}"
                  f" · frontier $ avoided {round(sum(x['frontier_cost_usd'] for x in acc), 6)}")


if __name__ == "__main__":
    stages = {"frontier": stage_frontier, "memorable": stage_memorable, "train": stage_train, "eval": stage_eval, "local": stage_local}
    for s in (list(stages) if sys.argv[1:] == ["all"] else sys.argv[1:]):
        stages[s]()
