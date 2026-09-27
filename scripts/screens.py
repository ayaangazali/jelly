"""make screens (#55): the dashboard against the fixtures, headless, at projector sizes.

Serves the repo root on a free port, opens ui/index.html?state=<fixture>&bench=fixtures/bench.example.json in Chromium (Playwright) and saves
docs/screens/<fixture>-<view>-<size>.png. Fails on console errors, failed requests, horizontal overflow, a view
cut off at the bottom, text under innerHeight/45 (16px at 720p, the r2 roadmap's floor), on the presenter showcase
a wrong 5-of-5 count or owned numbers for a type that isn't graduated, on any view a missing sample-data label,
and on presenter Under the hood a ticker without the latest trace event.
Offline; needs `pip install playwright && playwright install chromium`.
"""

import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screens"
FIXTURES = ["state.example", "state.graduated"]
SIZES = [(1920, 1080), (1280, 720)]
# (name, hash, query, what must sit fully on screen)
VIEWS = [("show", "#/show", "", ".show"), ("show-present", "#/show", "&present", "#app"),
         ("compare", "#/compare", "", ".cmp"), ("compare-present", "#/compare", "&present", "#app"),
         ("overview-present", "#/", "&present", "#app"), ("system-present", "#/system", "&present", "#app")]

# [overflow-x (page or a box its content spills out of), cut off at the bottom, smallest text px and its text]; SVG text is measured on screen, not in user units.
MEASURE = """(fold) => {
  const d = document.documentElement, texts = [];
  const w = document.createTreeWalker(document.getElementById("app"), NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const el = n.parentElement;
    if (!n.textContent.trim() || !el.checkVisibility()) continue;
    const px = parseFloat(getComputedStyle(el).fontSize) * (el.closest("svg") ? el.getScreenCTM().a : 1);
    texts.push([Math.round(px * 10) / 10, n.textContent.trim().slice(0, 40)]);
  }
  texts.sort((a, b) => a[0] - b[0]);
  const spill = [...document.querySelectorAll("#app *")].some((el) =>
    !el.closest("svg") && el.scrollWidth > el.clientWidth + 1 && el.clientWidth && getComputedStyle(el).overflowX === "visible");
  return [d.scrollWidth > innerWidth || spill, document.querySelector(fold).getBoundingClientRect().bottom > innerHeight, texts[0]];
}"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/ui/index.html"
    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for fx in FIXTURES:
            state = json.loads((ROOT / "fixtures" / f"{fx}.json").read_text())
            for w, h in SIZES:
                for view, hash_, flag, fold in VIEWS:
                    if "compare" in view and fx != FIXTURES[0]:
                        continue  # the bench file, not /state, feeds compare
                    name = f"{fx.removeprefix('state.')}-{view}-{w}x{h}"
                    page = browser.new_page(viewport={"width": w, "height": h})
                    errors = []
                    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.on("requestfailed", lambda r: errors.append(f"failed {r.url}"))
                    page.on("response", lambda r: r.status >= 400 and errors.append(f"{r.status} {r.url}"))
                    page.goto(f"{base}?state=/fixtures/{fx}.json&bench=/fixtures/bench.example.json{flag}{hash_}")
                    page.wait_for_selector("#app > :not(.lede)")  # rendered past "Loading…"
                    page.evaluate("document.fonts.ready")
                    page.wait_for_timeout(600)  # let the stamp animation settle
                    over_x, over_y, (px, text) = page.evaluate(MEASURE, fold)
                    page.screenshot(path=OUT / f"{name}.png")
                    problems = errors + ["horizontal overflow"] * over_x + [f"{fold} cut off at the bottom"] * over_y
                    problems += [f"text {px}px < {h / 45}px: {text!r}"] * (px < h / 45)
                    if view == "show-present":
                        k = page.get_attribute("[data-qa=state]", "class").split()[-1]
                        t = next(t for t in state["registry"]["task_types"].values() if t["state"] == k)
                        want = str(min(t["verified_runs"], state["config"]["n"]))
                        problems += [f"verified {page.inner_text('[data-qa=verified]')} != {want}"] * (page.inner_text("[data-qa=verified]") != want)
                        problems += ["owned numbers for a type that isn't graduated"] * (k != "GRADUATED" and page.query_selector("[data-qa=out-change]") is not None)
                    problems += ["fixture numbers without the sample-data label"] * (not page.evaluate("document.documentElement.classList.contains('sample')"))
                    if view == "system-present":
                        who = state["trace"][-1]["who"]
                        problems += [f"ticker lacks the latest call {who!r}"] * (who not in page.inner_text("[data-qa=ticker]"))
                    print(f"{'FAIL' if problems else 'ok  '} {name:38} smallest text {px}px", *problems, sep="\n     " if problems else "")
                    failures += problems
                    page.close()
        browser.close()
    server.shutdown()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
