import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from river_client import rl

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"```(?:python)?\n(.*?)```", re.S)


class ExitCodeEnv(rl.Env):
    def __init__(self, root):
        self.root = Path(root)

    async def reset(self, row):
        repo = self.root / row
        task = json.loads((repo / "tasks" / f"{row}.json").read_text())
        mod, test = f"calc/mod_{row}.py", f"tests/test_mod_{row}.py"
        files = "".join(f"\n{p}:\n```python\n{(repo / p).read_text()}```\n" for p in (mod, test))
        return [{"role": "user", "content": f"{task['prompt']}\n{files}\nReply with the whole fixed {mod} in one ```python block."}]

    async def reward(self, traj, row):
        code = FENCE.search(traj.final_text)
        if not code:
            return 0.0
        verify = json.loads((self.root / row / "tasks" / f"{row}.json").read_text())["verify"]
        with tempfile.TemporaryDirectory() as d:
            work = shutil.copytree(self.root / row, Path(d) / "repo", ignore=shutil.ignore_patterns(".venv", "__pycache__"))
            (work / f"calc/mod_{row}.py").write_text(code.group(1))
            done = subprocess.run(verify, shell=True, cwd=work, capture_output=True, timeout=60,
                                  env={**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"})
        return float(done.returncode == 0)


def plant(row, root):
    subprocess.run([ROOT / "scripts/reset-demo.sh", row], check=True)
    try:
        shutil.copytree(ROOT / "demo-repo", Path(root) / row, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
    finally:
        subprocess.run([ROOT / "scripts/reset-demo.sh", "clean"], check=True)


def train(env, rows, steps, group, lr):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from graduate.registrar.train import BASE_MODEL, THREADS

    torch.set_num_threads(THREADS)
    torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = get_peft_model(
        AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.float32),
        LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, task_type="CAUSAL_LM", target_modules=["q_proj", "v_proj"]),
    )
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    end = tok.convert_tokens_to_ids("<|im_end|>")
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for step in range(1, steps + 1):
        t0 = time.monotonic()
        row = rows[(step - 1) % len(rows)]
        messages = asyncio.run(env.reset(row))
        prompt = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)["input_ids"]
        model.eval()
        with torch.no_grad():
            out = model.generate(prompt, do_sample=True, temperature=1.0, max_new_tokens=160, num_return_sequences=group)
        comps = []
        for seq in out[:, prompt.shape[1]:].tolist():
            comps.append(seq[: seq.index(end) + 1] if end in seq else seq)
        rewards = [asyncio.run(env.reward(SimpleNamespace(final_text=tok.decode(c)), row)) for c in comps]
        mean = sum(rewards) / group
        model.train()
        loss = torch.zeros(())
        for c, r in zip(comps, rewards):
            if r == mean:
                continue
            ids = torch.cat([prompt[0], torch.tensor(c)]).unsqueeze(0)
            logits = model(input_ids=ids).logits[0, prompt.shape[1] - 1 : -1]
            logp = torch.log_softmax(logits, -1).gather(1, torch.tensor(c).unsqueeze(1)).mean()
            loss = loss - (r - mean) * logp / group
        if loss.requires_grad:
            loss.backward()
            opt.step()
            opt.zero_grad()
        print(json.dumps({"started": started, "step": step, "task": row, "rewards": rewards, "mean_reward": mean,
                          "updated": loss.requires_grad, "secs": round(time.monotonic() - t0, 1)}), flush=True)


def main():
    p = argparse.ArgumentParser(prog="python -m graduate.rl_env")
    p.add_argument("--steps", type=int, default=2)
    p.add_argument("--group", type=int, default=4)
    p.add_argument("--tasks", default="01")
    p.add_argument("--lr", type=float, default=1e-4)
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        rows = a.tasks.split(",")
        for r in rows:
            plant(r, d)
        train(ExitCodeEnv(d), rows, a.steps, a.group, a.lr)


if __name__ == "__main__":
    main()
