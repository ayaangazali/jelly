"""make record (#31): a 1920x1080 mp4 of scripts/demo.sh driving the presenter dashboard, for a backup video.

    python scripts/record.py [demo.sh flags]     default: --offline --auto-approve --use-checkpoint <rehearsal ckpt>

Starts demo.sh on a free port, opens /?present#/system in headless Chromium (Playwright's screencast), cuts to the
showcase when the task type graduates and with the final state at the end, then ffmpeg -> docs/recordings/<label>.mp4 (over 20 MB goes to
~/jelly-corpus/recordings/). An --offline run is labelled on screen "offline rehearsal, stub model" in every frame.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from graduate.router.state import build_state

ROOT = Path(__file__).resolve().parents[1]
ARGS = sys.argv[1:] or ["--offline", "--auto-approve", "--use-checkpoint", "river://offline-rehearsal/fix-failing-test-v1"]
LABEL = "offline rehearsal, stub model" if "--offline" in ARGS else "live run"
BANNER = """addEventListener("DOMContentLoaded", () => { const b = document.createElement("div"); b.textContent = %s;
  b.style.cssText = "position:fixed;right:2vw;bottom:2vh;z-index:99;padding:.4em .9em;border:2px solid #F0B955;border-radius:6px;"
    + "color:#F0B955;background:#0B0F17;font:700 2.6vh Archivo,sans-serif;letter-spacing:.04em;text-transform:uppercase";
  document.body.append(b); });""" % json.dumps(LABEL)


def main():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://localhost:{port}"
    demo = subprocess.Popen(["scripts/demo.sh", *ARGS], cwd=ROOT, env={**os.environ, "PORT": str(port)})
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    videos = Path(tempfile.mkdtemp())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=videos,
                                  record_video_size={"width": 1920, "height": 1080})
        ctx.add_init_script(BANNER)
        page = ctx.new_page()
        page.goto(base + "/?present#/system")
        graduated = False
        while demo.poll() is None:  # the runs on Under the hood, the graduation moment on the showcase
            time.sleep(1)
            try:
                state = json.loads(urllib.request.urlopen(base + "/state", timeout=2).read())
            except OSError:
                continue
            if not graduated and any(t["state"] == "GRADUATED" for t in state["registry"]["task_types"].values()):
                graduated = True
                page.evaluate("location.hash = '#/show'")
                time.sleep(6)
                page.evaluate("location.hash = '#/system'")
        # demo.sh stops its router on exit, so the page may have missed the last rows: hand it the final state
        os.chdir(ROOT)
        page.evaluate("s => { S = s; location.hash = '#/show'; render(); }", build_state())
        time.sleep(8)
        ctx.close()
        browser.close()
    out = ROOT / "docs/recordings" / (LABEL.split(",")[0].replace(" ", "-") + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(next(videos.glob("*.webm"))), "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    if out.stat().st_size > 20e6:
        out = Path(shutil.move(out, Path.home() / "jelly-corpus/recordings" / out.name))
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                capture_output=True, text=True).stdout)
    print(f"recorded {out}: {secs:.0f}s, {out.stat().st_size / 1e6:.1f} MB, demo.sh exit {demo.returncode}")
    sys.exit(demo.returncode)


if __name__ == "__main__":
    main()
