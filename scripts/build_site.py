"""Build the GitHub Pages site: the review app as a static demo plus the benchmark page.

python scripts/build_site.py examples/sample site [--results bench/results.json]
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import tempfile
from pathlib import Path

from burstwise import media
from burstwise.cache import Cache
from burstwise.config import Settings
from burstwise.library import analyze_folder
from burstwise.server import Session, state_payload

WEB = Path(__file__).resolve().parents[1] / "src" / "burstwise" / "web"
DEMO_SIDE = 800
DEMO_FLAG = "<script>window.BURSTWISE_DEMO = true;</script>\n"


def build_demo(sample: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WEB, out, dirs_exist_ok=True)
    index = (out / "index.html").read_text()
    (out / "index.html").write_text(
        index.replace('<script type="module"', DEMO_FLAG + '<script type="module"')
    )
    cache = Cache(Path(tempfile.mkdtemp()) / "demo.db")
    library = analyze_folder(sample, Settings(), cache=cache)
    cache.close()
    if library.failed:
        shown = "; ".join(f"{Path(f).name}: {e}" for f, e in library.failed[:3])
        raise SystemExit(f"build_site: {len(library.failed)} sample photos failed: {shown}")
    session = Session(sample, Settings(), use_gpu=False)
    session.library = library
    state = state_payload(session)
    ids = {p["id"]: Path(p["name"]).stem for p in state["photos"]}
    for photo in state["photos"]:
        photo["id"] = ids[photo["id"]]
    state["groups"] = [[ids[i] for i in group] for group in state["groups"]]
    state.update(demo=True, folder="sample", decisions={}, job={"state": "done"})
    (out / "state.json").write_text(json.dumps(state, separators=(",", ":")))
    thumbs = out / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for photo in library.photos:
        img, _ = media.load_preview(Path(photo.path), DEMO_SIDE)
        img.save(thumbs / f"{Path(photo.name).stem}.jpg", quality=72, optimize=True)
    return state


def build_benchmark(results: Path, out: Path) -> None:
    data = json.loads(results.read_text())
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in data["table"]
    )
    head = "".join(f"<th>{html.escape(h)}</th>" for h in data["columns"])
    method = "".join(f"<li>{html.escape(line)}</li>" for line in data["method"])
    notes = "".join(f"<li>{html.escape(line)}</li>" for line in data["notes"])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Burstwise benchmark</title>
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>
body{{font:16px/1.55 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px 16px;
background:#f6f3ec;color:#1c1a14}}
@media(prefers-color-scheme:dark){{
body{{background:#0e1015;color:#e8eaf0}}
th{{background:#161922}}
td,th{{border-color:#262b38}}}}
table{{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}}
td,th{{border:1px solid #ded9cc;padding:6px 10px;text-align:left;white-space:nowrap}}
th{{background:#ece7da}}
a{{color:#c77800}}
h1{{font-size:26px}}
</style></head><body>
<p><a href="./">&larr; Live demo</a> &middot; <a href="https://github.com/Arthur031221/Burstwise">GitHub</a></p>
<h1>Benchmark</h1>
<p>{html.escape(data["headline"])}</p>
<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>
<h2>Method</h2><ul>{method}</ul>
<h2>What this does not show</h2><ul>{notes}</ul>
<p><small>Measured {html.escape(data["date"])} on {html.escape(data["machine"])}.
Reproduce with <code>python bench/run.py</code>.</small></p>
</body></html>
"""
    (out / "benchmark.html").write_text(page)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    build_demo(args.sample, args.out)
    if args.results:
        build_benchmark(args.results, args.out)
    print(f"site written to {args.out}")


if __name__ == "__main__":
    main()
