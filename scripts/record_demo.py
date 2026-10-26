"""Record assets/demo.gif from the real review app running on a real folder of photos.

    python scripts/record_demo.py examples/sample assets/demo.gif

Needs Playwright with Chromium, and ffmpeg. The analysis you see in the first seconds is the
real run, so the recording starts from an empty cache.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import Page, sync_playwright

from burstwise.config import Settings
from burstwise.models import DINO, FACE, ensure
from burstwise.server import Session, create_app

SIZE = {"width": 1100, "height": 660}


def pause(seconds: float) -> None:
    time.sleep(seconds)


def script(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_selector(".card", timeout=120000)
    pause(1.6)
    page.locator('.card[data-state="reject"]').first.click()
    pause(1.6)
    page.keyboard.press("f")
    pause(1.4)
    page.keyboard.press("c")
    pause(2.0)
    page.keyboard.press("c")
    page.keyboard.press("ArrowRight")
    pause(1.0)
    page.keyboard.press("p")
    pause(1.0)
    page.keyboard.press("Escape")
    pause(0.8)
    page.click("#btn-xmp")
    pause(2.0)
    page.keyboard.press("Escape")
    pause(0.6)
    page.select_option("#lang", "ja")
    pause(1.6)
    page.click("#btn-theme")
    pause(1.2)


def record(folder: Path, out: Path) -> None:
    work = Path(tempfile.mkdtemp(prefix="bw-demo-"))
    os.environ["BURSTWISE_HOME"] = str(work / "home")
    photos = work / "photos"
    shutil.copytree(folder, photos)
    for model in (DINO, FACE):  # download before recording, not during it
        ensure(model)
    session = Session(photos, Settings(), use_gpu=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(session), port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        pause(0.05)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=SIZE, record_video_dir=str(work / "video"), record_video_size=SIZE
        )
        page = context.new_page()
        session.start()
        script(page, f"http://127.0.0.1:{port}/")
        context.close()
        browser.close()
    server.should_exit = True
    video = next((work / "video").glob("*.webm"))
    filters = (
        "fps=12,scale=880:-1:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", filters, str(out)], check=True
    )
    print(f"{out}: {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    record(Path(sys.argv[1]), Path(sys.argv[2]))
