import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).parents[1] / "src" / "burstwise" / "web"
LOCALES = sorted((WEB / "locales").glob("*.json"))
EN = json.loads((WEB / "locales" / "en.json").read_text())
CODES = ["de", "en", "es", "fr", "ja", "ko", "pt-BR", "zh-CN", "zh-TW"]


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_the_nine_languages_are_present():
    assert [p.stem for p in LOCALES] == CODES


@pytest.mark.parametrize("path", LOCALES, ids=lambda p: p.stem)
def test_locale_has_every_key_and_matching_placeholders(path):
    data = json.loads(path.read_text())
    assert set(data) == set(EN)
    for key, text in data.items():
        assert text.strip(), key
        assert placeholders(text) == placeholders(EN[key]), (path.stem, key)


def test_every_key_the_page_uses_exists():
    source = (WEB / "app.js").read_text() + (WEB / "index.html").read_text()
    used = set(re.findall(r"""\bt\(\s*["']([\w.]+)["']""", source))
    used |= set(re.findall(r"""data-i18n(?:-title|-placeholder)?="([\w.]+)""", source))
    assert used and not used - set(EN), sorted(used - set(EN))


def test_reason_codes_all_have_text():
    from burstwise.pick import reason_text

    for code in ("only_frame", "eyes_open", "fewest_closed", "sharpest", "tie", "least_clipping"):
        assert f"reason.{code}" in EN
    assert reason_text({"code": "tie"})
