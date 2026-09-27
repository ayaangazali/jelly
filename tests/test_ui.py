"""The dashboard's sidecar assets (#55): what the projector would show as unstyled or blank if a path broke."""

import re

from conftest import ROOT


def test_router_serves_every_local_ui_asset(router):
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "projector.css").read_text(encoding="utf-8")
    paths = re.findall(r'(?:href|src)="(/ui/[^"]+)"', html) + ["/ui/" + u for u in re.findall(r'url\("([^"]+)"\)', css)]
    assert {"/ui/projector.css", "/ui/present.js", "/ui/fonts/archivo.woff2"} <= set(paths)
    assert router("GET", "/").status_code == 200
    for path in paths:
        assert router("GET", path).status_code == 200, path
