"""The submission video (#146): the /app showcase on a running router, headless Chromium at 1920x1080, ~114 s.

    python scripts/record_app.py [base-url] [out.mp4] [seconds-scale]
    default: http://127.0.0.1:4151 docs/recordings/showcase-real.mp4 1

Tour: Live (the main screen) 50 s, Race 34 s (a real pair, replayed at 4x after the first pass for 20 s), Task types 12 s, Agents 12 s, back to Live.
Playwright's screencast -> ffmpeg (H.264, yuv420p). Nothing is labelled here: the page's own source tag says whether it
shows a recorded real run or demo data. Needs playwright and ffmpeg.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4151"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/recordings/showcase-real.mp4")
SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0


def main():
    tmp = Path(tempfile.mkdtemp())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(tmp),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        wait = lambda s: page.wait_for_timeout(int(s * 1000 * SCALE))
        page.goto(f"{BASE}/app")
        page.wait_for_selector("#live-root")
        wait(50)
        page.click('nav.side a[data-nav="race"]')
        page.wait_for_selector("#view h1")
        wait(14)
        if page.query_selector('button[data-race="4"]'):  # only once your model has a run to race
            page.click('button[data-race="4"]')
        wait(20)
        page.click('nav.side a[data-nav="tasks"]')
        wait(12)
        page.click('nav.side a[data-nav="agents"]')
        wait(12)
        page.click('nav.side a[data-nav="live"]')
        wait(8)
        video = page.video.path()
        ctx.close()
        browser.close()
    if errors:
        sys.exit(f"page errors while recording: {errors}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "23",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
            str(OUT),
        ],
        check=True,
    )
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{OUT} {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
