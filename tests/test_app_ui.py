"""GET /app serves the product frontend; its assets load through the /ui mount and every API it calls exists."""

import re

from conftest import ROOT


def test_app_page_and_its_assets_are_served(router, workdir):
    page = router("GET", "/app")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assets = re.findall(r'(?:href|src)="(/ui/app/[^"]+)"', page.text)
    assert sorted(assets) == ["/ui/app/app.css", "/ui/app/app.js"]
    for a in assets:
        assert router("GET", a).status_code == 200, a


def test_every_api_the_app_reads_answers_json(router, workdir):
    js = (ROOT / "ui/app/app.js").read_text(encoding="utf-8")
    for url in ["/state", "/api/swarm", "/api/sample", "/bench/latest/results.json"]:
        assert f'"{url}"' in js, url
        assert isinstance(router("GET", url).json(), dict), url
    assert router("GET", "/api/consent/nope").json()["error"].startswith("No task type")
