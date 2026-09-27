"""Trainer (#22): LoRA SFT on a task type's chat records, then registry TRAINING -> GRADUATED.

    python -m graduate.registrar.train <task_type> [--steps N] [--use-checkpoint PATH]

Reads `data/<task_type>.chat.jsonl` (contracts §6a, built by graduate.registrar.dataset), writes the loss curve to
`data/<task_type>.loss.jsonl` and the checkpoint to `data/checkpoints/<task_type>-v<n>/`. The consent endpoint (#25)
launches it as a detached process with the task type already TRAINING; by hand it makes that move itself.

Two backends, one shape: `train(chats, name, log) -> model` and `complete(model, messages, tools) -> (message, usage)`.
LocalBackend fine-tunes a small open model on this machine's CPU (torch + peft, the [train] extra). RiverBackend
runs the same loop on River (river-client) and is chosen when RIVER_API_KEY is set; the router (#37) picks the
backend from the registry's model path, so a real key swaps River in without touching the router.
"""

import argparse
import json
import os
import re
import resource
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graduate import ledger, registry, trace
from graduate.registrar import dataset

DATA = Path("data")
BASE_MODEL = os.environ.get("GRADUATE_LOCAL_MODEL", "Qwen/Qwen2.5-Coder-0.5B-Instruct")
THREADS = int(
    os.environ.get("GRADUATE_TORCH_THREADS", "6")
)  # the box is shared: leave cores for the router
KEEP_TOOLS = ("bash", "edit", "glob", "grep", "read", "write")
SYSTEM = "You are a coding agent. Use the tools to read, edit and test code in the repository until the task is done."
STALE = timedelta(hours=1)
CORPUS = "/home/ubuntu/jelly-corpus"  # scripts/corpus.sh copies ledger.jsonl, stage-ledger.jsonl, sessions/ here
MAX_LEN = int(
    os.environ.get("GRADUATE_MAX_LEN", "3072")
)  # tokens per session; caps training memory


def compact(messages, tools):
    """The prompt the small model sees, in training and in serving alike.

    OpenCode's system prompt and ten tool schemas are ~25k tokens; on a CPU that is minutes of prefill per call.
    Keep its <env> block (working directory) under a one-line system prompt, the six tools the task uses with the
    first line of their descriptions, and messages in the plain shape a HF chat template takes.
    """
    out = []
    for m in dataset.relative(messages):
        c = m.get("content") or ""
        if not isinstance(c, str):
            c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
        if m["role"] == "system":
            env = re.search(r"<env>.*?</env>", c, re.S)
            c = SYSTEM + ("\n" + env.group(0) if env else "")
        msg = {"role": m["role"], "content": c}
        if m.get("tool_calls"):
            msg["tool_calls"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["function"]["name"],
                        "arguments": _args(t["function"]["arguments"]),
                    },
                }
                for t in m["tool_calls"]
            ]
        out.append(msg)
    specs = [
        t.get("function", t) for t in tools or []
    ]  # OpenAI tools or §6a's flattened ToolSpec
    short = [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": (s.get("description") or "").split("\n")[0][:200],
                "parameters": s.get("parameters", {}),
            },
        }
        for s in specs
        if s["name"] in KEEP_TOOLS
    ]
    return out, short


def _args(a):
    try:
        return json.loads(a) if isinstance(a, str) else a
    except ValueError:
        return {}


def parse(text):
    """Qwen output -> OpenAI assistant message: <tool_call>{json}</tool_call> blocks become tool_calls, <think> goes."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    calls = []
    for i, body in enumerate(
        re.findall(r"</?tool_call>\s*(.*?)\s*</tool_call>", text, re.S)
    ):
        try:
            call = json.loads(body)
            calls.append(
                {
                    "id": f"call_{time.time_ns()}_{i}",
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments", {})),
                    },
                }
            )
        except (ValueError, KeyError, TypeError):
            continue  # a malformed call is dropped; the verify command catches what that breaks
    content = re.sub(r"</?tool_call>.*?(</tool_call>|$)", "", text, flags=re.S).strip()
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = calls
    return msg


class LocalBackend:
    """LoRA on a small open model, trained and served on this machine's CPU."""

    _loaded = {}
    _lock = threading.Lock()  # one generation at a time: the cores are the bottleneck

    def _torch(self):
        import torch

        torch.set_num_threads(THREADS)
        return torch

    def _examples(self, tok, chats):
        """(input_ids, labels) per chat: loss only on assistant turns, like River's TrainOnWhat.ALL_ASSISTANT."""
        render = lambda ms, tools, gen=False: tok.apply_chat_template(
            ms, tools=tools, tokenize=False, add_generation_prompt=gen
        )
        ids = lambda text: tok(text, add_special_tokens=False)["input_ids"]
        out = []
        for chat in chats:
            ms, tools = compact(chat["messages"], chat["tools"])
            full = ids(render(ms, tools))
            labels = [-100] * len(full)
            for i, m in enumerate(ms):
                if m["role"] == "assistant":
                    start, end = (
                        len(ids(render(ms[:i], tools, True))),
                        len(ids(render(ms[: i + 1], tools))),
                    )
                    labels[start:end] = full[start:end]
            if any(
                l != -100 for l in labels[1:MAX_LEN]
            ):  # a session cut before its first answer teaches nothing
                out.append((full[:MAX_LEN], labels[:MAX_LEN]))
        return out

    def train(self, chats, name, log, steps):
        torch = self._torch()
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(BASE_MODEL)
        examples = self._examples(tok, chats)
        model = get_peft_model(
            AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.float32),
            LoraConfig(
                r=16,
                lora_alpha=32,
                lora_dropout=0.0,
                task_type="CAUSAL_LM",
                target_modules=[
                    "q_proj",
                    "k_proj",
                    "v_proj",
                    "o_proj",
                    "gate_proj",
                    "up_proj",
                    "down_proj",
                ],
                # The small model's <tool_call> rows sit next to <|im_start|>'s; LoRA alone moves the answer toward
                # "some special token" and <|im_start|> wins. Train these two rows (tied with lm_head) as well.
                trainable_token_indices=tok.convert_tokens_to_ids(
                    ["<tool_call>", "</tool_call>"]
                ),
            ),
        )
        trace.emit(
            "Registrar → local trainer",
            f'get_peft_model("{BASE_MODEL}", LoraConfig(r=16))',
            f"LoRA created · {len(examples)} sessions · {steps} steps",
            22,
            ["registrar", "rivertrain"],
            ["train"],
        )
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=2e-4)
        inner = model.get_base_model()
        inner.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        model.train()
        t0 = time.monotonic()
        for step in range(1, steps + 1):
            ids, labels = examples[(step - 1) % len(examples)]
            # Logits only where there is a label: the full 1500 x 152k-vocab logits alone would cost ~2 GB with grads.
            hidden = inner.model(input_ids=torch.tensor([ids])).last_hidden_state[0]
            at = torch.tensor([i for i in range(len(ids) - 1) if labels[i + 1] != -100])
            loss = torch.nn.functional.cross_entropy(
                inner.lm_head(hidden[at]), torch.tensor(labels)[at + 1]
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            opt.zero_grad()
            row = {
                "step": step,
                "loss": round(loss.item(), 4),
                "secs": round(time.monotonic() - t0, 1),
                "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                // 1024,
            }
            log(row)
            if step % 5 == 0 or step == steps:
                trace.emit(
                    "Registrar → local trainer",
                    f"train step {step}/{steps}",
                    f"loss {row['loss']}",
                    22,
                    ["registrar", "rivertrain"],
                    ["train"],
                )
        path = DATA / "checkpoints" / name
        model.save_pretrained(path)
        tok.save_pretrained(path)
        return str(path.resolve())

    def _load(self, path):
        if path not in self._loaded:
            torch = self._torch()
            from peft import AutoPeftModelForCausalLM
            from transformers import AutoTokenizer

            model = (
                AutoPeftModelForCausalLM.from_pretrained(path, dtype=torch.float32)
                .merge_and_unload()
                .eval()
            )
            self._loaded[path] = (AutoTokenizer.from_pretrained(path), model)
        return self._loaded[path]

    def complete(self, model_path, messages, tools):
        with self._lock:
            tok, model = self._load(model_path)
            ms, short = compact(messages, tools)
            enc = tok.apply_chat_template(
                ms,
                tools=short,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            )
            n = enc["input_ids"].shape[1]
            # LoRA leaves the special-token rows untrained, so after fine-tuning <tool_call> and <|im_start|> score
            # alike. An assistant turn never contains any added token but these four: forbid the rest.
            keep = ("<tool_call>", "</tool_call>", "<|im_end|>", "<|endoftext|>")
            banned = [i for t, i in tok.get_added_vocab().items() if t not in keep]
            with self._torch().no_grad():
                out = model.generate(
                    **enc,
                    max_new_tokens=384,
                    do_sample=False,
                    suppress_tokens=banned,
                )
        # <tool_call> is a special token in Qwen's vocab: skip_special_tokens would drop the markers parse() needs.
        text = tok.decode(out[0, n:]).split("<|im_end|>")[0].split("<|endoftext|>")[0]
        return parse(text), {"prompt_tokens": n, "completion_tokens": out.shape[1] - n}


class RiverBackend:
    """The same two calls on River (river-client 0.12, contracts §6b). Needs RIVER_API_KEY; untested without one."""

    BASE = dataset.BASE_MODEL

    def _client(self):
        if not os.environ.get("RIVER_API_KEY"):  # before the import: the reason, not a missing-extra error
            raise RuntimeError("no River key: set RIVER_API_KEY or use a local checkpoint")
        import river_client

        return river_client.Client(api_key=os.environ["RIVER_API_KEY"])

    def train(self, chats, name, log, steps):
        from river_client import LoraConfig

        rend = dataset.renderer()
        wires = [dataset.wire(rend, c)[0] for c in chats]
        with self._client().session() as session:
            model = session.create_model(self.BASE, lora=LoraConfig(rank=32))
            for step in range(1, steps + 1):
                fwd, _ = model.train_step(
                    data=[wires[(step - 1) % len(wires)]],
                    lr=2e-4,
                    loss_fn="cross_entropy",
                )
                log({"step": step, "loss": fwd.metrics.get("loss")})
            return model.save_weights(name, mode="inference").path

    def complete(self, model_path, messages, tools):
        r = self._client().chat_complete_from_checkpoint(
            messages,
            checkpoint_path=model_path,
            base_model=self.BASE,
            tools=tools,
            temperature=0,
            chat_template_kwargs={"enable_thinking": False},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"River {r.status_code}: {r.response_json[:200]}")
        body = json.loads(r.response_json)
        msg = body["choices"][0]["message"]
        # River's renderer may already return OpenAI tool_calls; otherwise parse Qwen's text format.
        return (
            msg if msg.get("tool_calls") else parse(msg.get("content") or "")
        ), body.get("usage", {})


def backend(model=None):
    """The checkpoint decides (river:// or a local directory); a new run takes GRADUATE_OWNED_BACKEND (graduate init
    writes it), else River if a key exists, else local. `none` fails every call, so the frontier serves everything."""
    name = os.environ.get("GRADUATE_OWNED_BACKEND")
    if name == "none":
        raise RuntimeError("GRADUATE_OWNED_BACKEND=none")
    if model:
        name = "river" if model.startswith("river://") else "local"
    river = name == "river" or (not name and os.environ.get("RIVER_API_KEY"))
    return RiverBackend() if river else LocalBackend()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reset_stale():
    """A TRAINING task type whose run started over an hour ago lost its trainer (killed, rebooted): back to READY."""
    reg = registry.load()
    cutoff = (datetime.now(timezone.utc) - STALE).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, tt in reg["task_types"].items():
        started = next(
            (
                e["ts"]
                for e in reg["events"]
                if e["task_type"] == name and e["kind"] == "training"
            ),
            "",
        )
        if tt["state"] == "TRAINING" and started < cutoff:
            registry.transition(name, "READY")
            registry.add_event(
                "error",
                name,
                f"Training of {name} stopped without finishing. Back to READY.",
            )


def from_corpus(task_type, corpus):
    """Rebuild data/<task_type>.chat.jsonl from the durable corpus copy (docs/corpus.md): its ledger, the staged
    rows it holds back for the live demo, and its session logs."""
    root = Path(corpus)
    rows = "".join((root / f).read_text(encoding="utf-8") for f in ("ledger.jsonl", "stage-ledger.jsonl") if (root / f).exists())
    if not rows:
        sys.exit(f"{root}/ledger.jsonl not found: run the corpus first (docs/corpus.md)")
    DATA.mkdir(exist_ok=True)
    (DATA / "corpus-ledger.jsonl").write_text(rows, encoding="utf-8")
    ledger.LEDGER_PATH, dataset.SESSIONS_DIR = str(DATA / "corpus-ledger.jsonl"), root / "sessions"
    s = dataset.build(task_type)
    print(f"{task_type}: {s['records']} records from {root} ({s['skipped']} skipped)")


def run(task_type, steps=None, use_checkpoint=None):
    reset_stale()
    tt = registry.load()["task_types"].get(task_type)
    if tt is None:
        sys.exit(f"no task type {task_type!r} in {registry.REGISTRY_PATH}")
    if (
        tt["state"] != "TRAINING"
    ):  # by hand; the consent endpoint has already made this move
        registry.transition(task_type, "TRAINING")  # raises without consent
        registry.add_event("training", task_type, f"Training started for {task_type}.")
    signal.signal(
        signal.SIGTERM, lambda *_: sys.exit("killed")
    )  # a kill still runs the READY fallback below
    t0 = time.monotonic()
    try:
        if use_checkpoint:
            if not (
                Path(use_checkpoint) / "adapter_config.json"
            ).exists() and not use_checkpoint.startswith("river://"):
                raise FileNotFoundError(f"{use_checkpoint} has no adapter_config.json")
            meta = Path(use_checkpoint) / "graduate.json"  # written beside the adapter when it was trained
            model, runs = (
                str(Path(use_checkpoint).resolve())
                if "://" not in use_checkpoint
                else use_checkpoint,
                json.loads(meta.read_text())["trained_on_runs"] if meta.exists() else tt["trained_on_runs"],
            )
        else:
            chats = [
                json.loads(l)
                for l in (DATA / f"{task_type}.chat.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if l.strip()
            ]
            if not chats:
                raise ValueError(f"data/{task_type}.chat.jsonl is empty")
            version = 1 + len(list((DATA / "checkpoints").glob(f"{task_type}-v*")))
            loss_log = (DATA / f"{task_type}.loss.jsonl").open("w", encoding="utf-8")

            def log(row):
                loss_log.write(json.dumps(row) + "\n")
                loss_log.flush()
                print(json.dumps(row), flush=True)

            model = backend().train(chats, f"{task_type}-v{version}", log, steps or max(15, 3 * len(chats)))
            runs = len(chats)
            if Path(model).is_dir():  # so --use-checkpoint can say what it was trained on
                (Path(model) / "graduate.json").write_text(json.dumps({"task_type": task_type, "trained_on_runs": runs}))
        secs = round(time.monotonic() - t0, 1)
        trace.emit(
            "Registrar → disk",
            f"save checkpoint {model}",
            f"saved · {secs} s",
            22,
            ["rivertrain", "river"],
            ["serve"],
        )
        registry.transition(
            task_type,
            "GRADUATED",
            model=model,
            serving="checkpoint",
            deployment=None,
            trained_on_runs=runs,
            graduated_at=_now(),
            verified_since_graduation=0,
            failures_since_graduation=0,
        )
        registry.add_event(
            "graduated",
            task_type,
            f"{task_type} graduated: {Path(model).name}, trained on {runs} runs in {secs} s.",
        )
        print(f"GRADUATED {task_type}: {model} ({secs} s)")
        return model
    except BaseException as e:
        if (
            registry.load()["task_types"][task_type]["state"] == "TRAINING"
        ):  # else someone graduated it meanwhile
            registry.transition(task_type, "READY")
        registry.add_event(
            "error",
            task_type,
            f"Training {task_type} failed: {e!r:.200}. The frontier keeps serving it.",
        )
        raise


def main():
    p = argparse.ArgumentParser(prog="graduate train")
    p.add_argument("task_type")
    p.add_argument("--steps", type=int)
    p.add_argument(
        "--use-checkpoint",
        metavar="PATH",
        help="graduate from an existing checkpoint, no training",
    )
    p.add_argument("--corpus", nargs="?", const=CORPUS, metavar="DIR", help=f"train on the durable corpus (default {CORPUS})")
    a = p.parse_args()
    if a.corpus:
        from_corpus(a.task_type, a.corpus)
    run(a.task_type, a.steps, a.use_checkpoint)


if __name__ == "__main__":
    main()
