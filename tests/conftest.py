from __future__ import annotations

from pathlib import Path

import pytest

from burstwise.config import Settings
from burstwise.library import Library, regroup

from .helpers import make_photo, texture, unit, write_jpeg


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def library(tmp_path: Path, settings: Settings) -> Library:
    """Four photos in two groups with known verdicts, files on disk."""
    specs = [
        {"sharp_tile": 120.0, "embedding": unit(0)},
        {"sharp_tile": 40.0, "embedding": unit(5)},
        {"sharp_tile": 90.0, "embedding": unit(90), "taken": 1_700_001_000.0},
        {"sharp_tile": 95.0, "embedding": unit(92), "taken": 1_700_001_001.0},
    ]
    photos = []
    for spec in specs:
        photo = make_photo(**spec)
        path = tmp_path / photo.name
        write_jpeg(path, texture(photo.mtime_ns))
        photo.path = str(path)
        photos.append(photo)
    return regroup(Library(folder=tmp_path, settings=settings, photos=photos))
