#!/usr/bin/env python3
"""Render trmnl/full.liquid with a today.json into a standalone HTML page that
mimics the TRMNL X screen (screen--lg, 4bit, landscape). For local checks only;
the real test is the TRMNL markup previewer.

  python tools/render_preview.py site/today.json preview.html [--assets http://localhost:8765]
"""
import argparse
import json
from pathlib import Path

from liquid import Environment

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="{assets}/css/plugins.css">
<script src="{assets}/js/plugins.js"></script>
</head>
<body class="environment trmnl">
<div class="screen screen--v2 screen--lg screen--density-2x screen--4bit{portrait}">
<div class="view view--full">
{markup}
</div></div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("out")
    ap.add_argument("--assets", default="https://trmnl.com")
    ap.add_argument("--portrait", action="store_true")
    a = ap.parse_args()
    data = json.loads(Path(a.json).read_text(encoding="utf-8"))
    tpl = Environment().from_string((ROOT / "trmnl" / "full.liquid").read_text(encoding="utf-8"))
    html = PAGE.format(assets=a.assets.rstrip("/"), markup=tpl.render(**data),
                       portrait=" screen--portrait" if a.portrait else "")
    Path(a.out).write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
