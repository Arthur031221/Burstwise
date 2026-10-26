"""Find photos and read a fast preview, a capture time and the image size."""

from __future__ import annotations

import calendar
import io
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import exifread
import numpy as np
import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()
logging.getLogger("exifread").setLevel(logging.ERROR)

JPEG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
HEIF_EXT = {".heic", ".heif"}
RAW_EXT = {
    ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng", ".orf",
    ".raf", ".rw2", ".pef", ".srw", ".3fr", ".erf", ".kdc", ".mrw", ".x3f", ".iiq",
}  # fmt: skip
PHOTO_EXT = JPEG_EXT | HEIF_EXT | RAW_EXT
PREVIEW_SIDE = 1600
MIN_RAW_PREVIEW_SIDE = 1000


def find_photos(folder: Path, recursive: bool = True) -> list[Path]:
    """List supported photos. When a RAW and a JPEG share a stem, only the RAW is kept."""
    pattern = "**/*" if recursive else "*"
    files = [
        p
        for p in sorted(folder.glob(pattern))
        if p.is_file() and p.suffix.lower() in PHOTO_EXT and ".burstwise" not in p.parts
    ]
    raw_stems = {(p.parent, p.stem.lower()) for p in files if p.suffix.lower() in RAW_EXT}
    return [
        p
        for p in files
        if p.suffix.lower() in RAW_EXT or (p.parent, p.stem.lower()) not in raw_stems
    ]


def _fit(img: Image.Image, side: int) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if max(img.size) > side:
        img.thumbnail((side, side), Image.Resampling.LANCZOS)
    return img


def _raw_preview(path: Path, side: int) -> tuple[Image.Image, tuple[int, int]]:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        full = (raw.sizes.width, raw.sizes.height)
        try:
            thumb = raw.extract_thumb()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            thumb = None
        if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
            img = Image.open(io.BytesIO(thumb.data))
            if max(img.size) >= MIN_RAW_PREVIEW_SIDE:
                img.draft("RGB", (side, side))
                return img, full
        if thumb is not None and thumb.format == rawpy.ThumbFormat.BITMAP:
            img = Image.fromarray(thumb.data)
            if max(img.size) >= MIN_RAW_PREVIEW_SIDE:
                return img, full
        rgb = raw.postprocess(half_size=True, use_camera_wb=True, output_bps=8)
        return Image.fromarray(rgb), full


def load_preview(path: Path, side: int = PREVIEW_SIDE) -> tuple[Image.Image, tuple[int, int]]:
    """Return an RGB preview of at most `side` pixels and the full image size."""
    ext = path.suffix.lower()
    if ext in RAW_EXT:
        img, size = _raw_preview(path, side)
        # A rotated RAW reports the sensor size, so size follows the oriented preview.
        oriented = _fit(img, side)
        if oriented.size[0] < oriented.size[1] and size[0] > size[1]:
            size = (size[1], size[0])
        return oriented, size
    img = Image.open(path)
    size = img.size
    if img.getexif().get(0x0112, 1) in (5, 6, 7, 8):
        size = (size[1], size[0])
    if img.format == "JPEG":
        img.draft("RGB", (side, side))
    return _fit(img, side), size


_EXIF_FMT = "%Y:%m:%d %H:%M:%S"


def _parse_time(stamp: str, subsec: str | None) -> float | None:
    stamp = stamp.strip()
    if not re.match(r"\d{4}:\d\d:\d\d \d\d:\d\d:\d\d", stamp):
        return None
    try:
        when = datetime.strptime(stamp[:19], _EXIF_FMT)
    except ValueError:
        return None
    base = float(calendar.timegm(when.timetuple()))
    if subsec and subsec.strip().isdigit():
        base += int(subsec.strip()) / 10 ** len(subsec.strip())
    return base


def capture_time(path: Path) -> tuple[float, bool]:
    """Capture time in seconds and whether it came from EXIF (else the file time)."""
    try:
        with open(path, "rb") as fh:
            tags = exifread.process_file(fh, details=False, stop_tag="EXIF SubSecTimeOriginal")
        stamp = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        subsec = tags.get("EXIF SubSecTimeOriginal")
        if stamp is not None:
            parsed = _parse_time(str(stamp), str(subsec) if subsec is not None else None)
            if parsed is not None:
                return parsed, True
    except Exception:  # noqa: BLE001 - a damaged EXIF block must not stop the scan
        pass
    # EXIF has no zone, so the file time is read as wall clock time too and the two compare.
    return float(calendar.timegm(time.localtime(path.stat().st_mtime))), False


def to_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img, dtype=np.uint8)
