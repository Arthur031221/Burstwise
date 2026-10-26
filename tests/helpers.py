from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
from PIL import Image

from burstwise.analyze import Photo

_ids = itertools.count(1)


def make_photo(**over) -> Photo:
    """A Photo with plausible measurements, so rules can be tested without any model."""
    n = next(_ids)
    base = {
        "id": f"p{n:03d}",
        "path": f"/photos/IMG_{n:04d}.JPG",
        "name": f"IMG_{n:04d}.JPG",
        "size_bytes": 1000,
        "mtime_ns": n,
        "width": 6000,
        "height": 4000,
        "taken": 1_700_000_000.0 + n,
        "taken_from_exif": True,
        "sharp_face": 0.0,
        "sharp_tile": 100.0,
        "clip_hi": 0.0,
        "clip_lo": 0.0,
        "faces": [],
        "embedding": [1.0, 0.0],
    }
    base.update(over)
    return Photo(**base)


def face(blink: float = 0.0) -> dict:
    return {"box": [0.4, 0.3, 0.2, 0.3], "blink_l": blink, "blink_r": blink}


def unit(angle: float) -> list[float]:
    """A unit vector at `angle` degrees: cosine similarity between two is cos of the gap."""
    rad = np.radians(angle)
    return [float(np.cos(rad)), float(np.sin(rad))]


def texture(seed: int, size: tuple[int, int] = (320, 240)) -> Image.Image:
    """A detailed synthetic picture with edges at many scales."""
    rng = np.random.default_rng(seed)
    w, h = size
    canvas = np.full((h, w, 3), 120, dtype=np.float32)
    for _ in range(40):
        x0, y0 = int(rng.integers(0, w - 20)), int(rng.integers(0, h - 20))
        x1, y1 = x0 + int(rng.integers(10, 120)), y0 + int(rng.integers(10, 90))
        canvas[y0:y1, x0:x1] = rng.integers(20, 235, 3)
    canvas += rng.normal(0, 6, canvas.shape)
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def write_jpeg(path: Path, img: Image.Image, stamp: str | None = None) -> Path:
    exif = Image.Exif()
    if stamp:
        exif.get_ifd(0x8769)[0x9003] = stamp
    img.save(path, format="JPEG", quality=92, exif=exif)
    return path
