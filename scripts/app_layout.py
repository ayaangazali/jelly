"""The /app layout check (#146): every page at 1920, 1280, 836 and 390 px wide, headless, against `graduate up --demo`'s
fixture state. Fails on console errors, page-level horizontal overflow (scrollWidth > clientWidth) and any wrapped
control: a button, nav item, tag, badge, chip, KPI label or table header taller than one line.
Run: python scripts/app_layout.py [base-url]. Without a URL it serves the demo on a free port. Needs playwright."""

import os
import socket
import sys
import threading
import time

from playwright.sync_api import sync_playwright

WIDTHS = [(1920, 1080), (1280, 720), (836, 900), (390, 844)]
PAGES = ["/app", "/app/race", "/app/tasks", "/app/agents", "/app/providers", "/app/providers/river", "/app/providers/memorable", "/app/providers/gbrain", "/app/providers/frontier", "/app/logs", "/app/overview"]
CONTROLS = ".btn, nav.side a, .tag, .state, .flag, th, .sp b, .kpi span, .kpi b, .race-bar a, .lane .st"
WRAPPED = """(sel) => [...document.querySelectorAll(sel)].filter((el) => {
  if (!el.checkVisibility()) return false;
  const cs = getComputedStyle(el), line = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3;
  const r = document.createRange(); r.selectNodeContents(el);
  const lines = new Set([...r.getClientRects()].map((q) => Math.round(q.top))).size;
  return lines > 1 && el.getBoundingClientRect().height > line * 1.6;
}).map((el) => `${el.tagName.toLowerCase()}.${el.className}: ${el.textContent.trim().slice(0, 30)}`)"""


def serve():
    from graduate import cli

    os.chdir(cli._demo_dir())
    os.environ["GRADUATE_SAMPLE"] = "1"
    import uvicorn

    from graduate.router.app import app

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"port": port, "log_level": "warning"},
        daemon=True,
    ).start()
    time.sleep(2)
    return f"http://127.0.0.1:{port}"


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else serve()
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in WIDTHS:
            for path in PAGES:
                page = browser.new_page(viewport={"width": w, "height": h})
                errors = []
                page.on(
                    "console", lambda m: m.type == "error" and errors.append(m.text)
                )
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(base + path)
                page.wait_for_timeout(2500)
                sideways = page.evaluate(
                    "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                )
                wrapped = page.evaluate(WRAPPED, CONTROLS)
                problems = (
                    errors
                    + [f"page scrolls sideways by {sideways}px"] * (sideways > 0)
                    + [f"wrapped: {x}" for x in wrapped]
                )
                print(
                    f"{'FAIL' if problems else 'ok  '} {path:14} {w}px",
                    *problems,
                    sep="\n     " if problems else "",
                )
                failures += problems
                page.close()
        browser.close()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
