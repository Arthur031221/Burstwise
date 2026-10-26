"""Drives the real review app in Chromium. Run with: pytest -m browser"""

import json
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from PIL import ImageFilter

from burstwise.config import Settings
from burstwise.server import Session, create_app

from .helpers import texture, write_jpeg

pytestmark = [pytest.mark.browser, pytest.mark.models]
sync_api = pytest.importorskip("playwright.sync_api")


def serve(root: Path, shots: Path):
    import os

    os.environ["BURSTWISE_HOME"] = str(root / "home")
    session = Session(shots, Settings(), use_gpu=False)
    session.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(session), port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("browser")
    shots = root / "shots"
    shots.mkdir()
    sharp = texture(1, (640, 480))
    write_jpeg(shots / "A1.jpg", sharp.filter(ImageFilter.GaussianBlur(4)), "2024:06:01 10:00:00")
    write_jpeg(shots / "A2.jpg", sharp, "2024:06:01 10:00:01")
    write_jpeg(shots / "B1.jpg", texture(7, (640, 480)), "2024:06:01 11:00:00")
    server, url = serve(root, shots)
    yield url, shots
    server.should_exit = True


@pytest.fixture(scope="module")
def long_app(tmp_path_factory):
    """One burst of 14 frames, S00 the sharpest and each later one a little softer."""
    root = tmp_path_factory.mktemp("long")
    shots = root / "shots"
    shots.mkdir()
    base = texture(3, (640, 480))
    for i in range(14):
        img = base.filter(ImageFilter.GaussianBlur(i * 0.5)) if i else base
        write_jpeg(shots / f"S{i:02d}.jpg", img, f"2024:06:01 10:00:{i:02d}")
    server, url = serve(root, shots)
    yield url, shots
    server.should_exit = True


@contextmanager
def open_page(url, **size):
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=size or {"width": 1280, "height": 800})
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.goto(url)
        page.wait_for_selector(".card", timeout=60000)
        try:
            yield page
        finally:
            browser.close()


@pytest.fixture
def page(app):
    with open_page(app[0]) as page:
        yield page


@pytest.fixture
def long_page(long_app):
    with open_page(long_app[0]) as page:
        # The server is shared by the tests of this module, so start each one without decisions.
        page.evaluate(
            """async () => {
                const { photos } = await (await fetch('api/state')).json();
                await Promise.all(photos.map((p) => fetch(`api/decision/${p.id}`, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' })));
            }"""
        )
        page.reload()
        page.wait_for_selector(".card")
        yield page


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


def test_pick_advances_to_the_next_photo_and_keeps_the_grid(page, app):
    cards = page.locator(".card")
    first = cards.nth(0)
    first_id = first.get_attribute("data-id")
    first.click()
    title = page.locator(".v-head h2").inner_text()
    page.keyboard.press("x")
    page.wait_for_function("(t) => document.querySelector('.v-head h2').innerText !== t", arg=title)
    assert page.locator(".card").count() == 3
    assert page.locator(f'.card[data-id="{first_id}"]').get_attribute("data-state") == "reject"
    assert page.errors == []


def test_down_arrow_jumps_to_the_next_group_and_closing_keeps_your_place(page):
    page.locator(".card").nth(0).click()
    page.keyboard.press("ArrowDown")
    name = page.locator(".v-head h2").inner_text().split("\n")[0]
    assert name.startswith("B1")
    page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement.dataset.id") is not None


def _swipe(page, dx, dy=0):
    page.evaluate(
        """([dx, dy]) => {
            const stage = document.querySelector('.v-stage');
            const fire = (type, x, y) => stage.dispatchEvent(new PointerEvent(type,
                { pointerType: 'touch', clientX: x, clientY: y, bubbles: true }));
            fire('pointerdown', 200, 300);
            fire('pointerup', 200 + dx, 300 + dy);
        }""",
        [dx, dy],
    )


def test_swipe_moves_between_photos_but_a_vertical_drag_does_not(page):
    page.locator(".card").nth(0).click()
    first = page.locator(".v-head h2").inner_text()
    _swipe(page, -120)
    page.wait_for_function("(t) => document.querySelector('.v-head h2').innerText !== t", arg=first)
    second = page.locator(".v-head h2").inner_text()
    _swipe(page, 10, 150)
    assert page.locator(".v-head h2").inner_text() == second
    _swipe(page, 120)
    page.wait_for_function("(t) => document.querySelector('.v-head h2').innerText === t", arg=first)


def test_rating_button_shows_the_current_stars_and_a_second_press_clears_them(page, app):
    page.locator(".card").nth(0).click()
    stars = page.locator(".v-act .stars button")
    stars.nth(2).click()
    assert stars.nth(2).get_attribute("aria-pressed") == "true"
    page.keyboard.press("3")
    assert stars.nth(2).get_attribute("aria-pressed") == "false"
    assert page.errors == []


def test_phone_viewer_keeps_the_actions_on_screen(page):
    page.set_viewport_size({"width": 360, "height": 640})
    page.locator(".card").nth(0).click()
    page.keyboard.press("c")
    box = page.evaluate(
        "(() => { const a = document.querySelector('.v-act').getBoundingClientRect();"
        " return [a.bottom, innerHeight, document.documentElement.scrollWidth, innerWidth]; })()"
    )
    assert box[0] <= box[1] and box[2] <= box[3]
    assert page.locator(".v-head [data-close]").is_visible()


def test_a_long_group_shows_its_best_frame_large_and_folds_the_rest(long_page):
    assert long_page.locator(".group").count() == 1
    hero = long_page.locator(".card.hero")
    assert hero.count() == 1 and hero.get_attribute("data-id")
    assert "S00" in hero.get_attribute("aria-label")
    assert long_page.locator(".card").count() == 9
    box = hero.bounding_box()
    other = long_page.locator(".card:not(.hero)").first.bounding_box()
    assert box["width"] > 1.8 * other["width"]
    more = long_page.locator(".group .more")
    more.click()
    assert long_page.locator(".card").count() == 14
    assert long_page.locator(".group .more").get_attribute("aria-expanded") == "true"
    long_page.locator(".group .more").click()
    assert long_page.locator(".card").count() == 9
    assert long_page.errors == []


def test_closing_the_viewer_on_a_folded_frame_unfolds_the_group(long_page):
    long_page.locator(".card.hero").click()
    long_page.keyboard.press("ArrowLeft")
    assert long_page.locator(".v-head h2").inner_text().startswith("S13")
    long_page.keyboard.press("Escape")
    assert long_page.locator(".card").count() == 14
    assert long_page.evaluate("document.activeElement.getAttribute('aria-label')").startswith("S13")


def test_a_rejected_best_frame_hands_the_hero_to_the_next_one(long_page):
    long_page.locator(".card.hero").focus()
    long_page.keyboard.press("x")
    long_page.wait_for_function(
        "document.querySelector('.card.hero').getAttribute('aria-label').startsWith('S01')"
    )
    assert long_page.locator(".card").count() >= 9


def test_grid_keys_move_between_cards_and_act_on_the_focused_one(long_page, long_app):
    long_page.locator(".card.hero").focus()
    long_page.keyboard.press("ArrowRight")
    name = long_page.evaluate("document.activeElement.getAttribute('aria-label')")
    assert not name.startswith("S00")
    long_page.keyboard.press("3")
    long_page.wait_for_selector(".card:focus .own")
    assert "3" in long_page.locator(".card:focus .own").inner_text()
    long_page.keyboard.press("ArrowDown")
    assert long_page.evaluate("document.activeElement.getAttribute('aria-label')") != name
    long_page.keyboard.press("ArrowUp")
    assert long_page.evaluate("document.activeElement.getAttribute('aria-label')") == name
    assert long_page.errors == []


def test_phone_long_group_has_a_full_width_hero_and_no_sideways_scroll(long_app):
    with open_page(long_app[0], width=390, height=800) as page:
        hero = page.locator(".card.hero").bounding_box()
        assert hero["width"] > 300 and hero["height"] < 300
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
