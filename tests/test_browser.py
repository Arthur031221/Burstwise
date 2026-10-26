"""Drives the real review app in Chromium. Run with: pytest -m browser"""

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from PIL import ImageFilter

from burstwise.config import Settings
from burstwise.server import Session, create_app

from .helpers import texture, write_jpeg

pytestmark = [pytest.mark.browser, pytest.mark.models]
sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os

    root = tmp_path_factory.mktemp("browser")
    os.environ["BURSTWISE_HOME"] = str(root / "home")
    shots = root / "shots"
    shots.mkdir()
    sharp = texture(1, (640, 480))
    write_jpeg(shots / "A1.jpg", sharp.filter(ImageFilter.GaussianBlur(4)), "2024:06:01 10:00:00")
    write_jpeg(shots / "A2.jpg", sharp, "2024:06:01 10:00:01")
    write_jpeg(shots / "B1.jpg", texture(7, (640, 480)), "2024:06:01 11:00:00")
    session = Session(shots, Settings(), use_gpu=False)
    session.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(session), port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", shots
    server.should_exit = True


@pytest.fixture
def page(app):
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.goto(app[0])
        page.wait_for_selector(".card", timeout=60000)
        yield page
        browser.close()


def test_grid_shows_every_photo_and_no_errors(page):
    assert page.locator(".card").count() == 3
    assert page.locator('.card[data-state="reject"]').count() == 1
    assert page.errors == []


def test_keyboard_decision_is_saved_to_disk(page, app):
    page.locator('.card[data-state="reject"]').click()
    page.keyboard.press("p")
    page.wait_for_timeout(500)
    saved = json.loads((Path(app[1]) / ".burstwise" / "decisions.json").read_text())
    assert [d["state"] for d in saved.values()] == ["pick"]


def test_language_switch_changes_the_text_and_is_remembered(page):
    before = page.locator("#btn-xmp").inner_text()
    page.select_option("#lang", "ja")
    page.wait_for_function("document.documentElement.lang === 'ja'")
    assert page.locator("#btn-xmp").inner_text() != before
    page.reload()
    page.wait_for_selector(".card")
    assert page.evaluate("document.documentElement.lang") == "ja"


def test_theme_toggle(page):
    first = page.evaluate("document.documentElement.dataset.theme")
    page.click("#btn-theme")
    assert page.evaluate("document.documentElement.dataset.theme") != first


def test_phone_layout_does_not_scroll_sideways(page):
    page.set_viewport_size({"width": 390, "height": 800})
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
