# Contributing

Bug reports, odd photos that Burstwise judges wrongly, and new translations are the most useful
things you can send.

## Setup

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Checks before a pull request

```
ruff check . && ruff format --check .
pytest                      # fast tests, no models
pytest -m models            # real models, downloads about 100 MB once
playwright install chromium && pytest -m browser
```

Tests that read sidecars with ExifTool run when `exiftool` is on your PATH.

## A photo judged wrongly

Open an issue with the numbers, not the photo. `burstwise cull FOLDER --report report.json -v`
prints every measurement and the rule that fired. If a threshold is wrong for a kind of
photo, say which kind and what value worked. Thresholds live in `src/burstwise/config.py`
and each one has a comment that says what it means.

## Translations

Strings live in `src/burstwise/web/locales/*.json`. Keep every key and every `{placeholder}`.
`tests/test_locales.py` fails when one is missing. To add a language, copy `en.json`, add the
code to `LANGS` in `src/burstwise/web/app.js`, and add a `README.<code>.md`.

## Style

Python 3.10 and up, ruff with the settings in `pyproject.toml`, no new runtime dependency
without a reason in the pull request. The web app is plain ES modules with no build step and
no `innerHTML`. Build elements with the `h()` helper so that file names can never become markup.

## Scope

Burstwise reads photos and writes small sidecar files next to them. It never edits or deletes an
original. A change that breaks that rule will not be merged.
