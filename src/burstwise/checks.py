"""Per-photo measurements. Each one is a plain number with a stated rule."""

from __future__ import annotations

import cv2
import numpy as np

FACE_PATCH = 160
TILE = 80


def gray_of(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _laplacian_var(gray: np.ndarray) -> float:
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.0)
    return float(cv2.Laplacian(smooth, cv2.CV_32F, ksize=3).var())


def face_sharpness(gray: np.ndarray, boxes: list[list[float]]) -> float:
    """Laplacian variance inside each face box at a fixed patch size, weighted by box area."""
    height, width = gray.shape
    total, weight = 0.0, 0.0
    for x, y, w, h in boxes:
        x0, y0 = int(x * width), int(y * height)
        x1, y1 = int((x + w) * width), int((y + h) * height)
        if x1 - x0 < 24 or y1 - y0 < 24:
            continue
        crop = gray[y0:y1, x0:x1]
        patch = cv2.resize(crop, (FACE_PATCH, FACE_PATCH), interpolation=cv2.INTER_AREA)
        area = w * h
        total += _laplacian_var(patch) * area
        weight += area
    return total / weight if weight else 0.0


def tile_sharpness(gray: np.ndarray) -> float:
    """90th percentile of per-tile Laplacian variance: how sharp the sharpest part is."""
    height, width = gray.shape
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.0)
    lap = cv2.Laplacian(smooth, cv2.CV_32F, ksize=3)
    values = [
        float(lap[y : y + TILE, x : x + TILE].var())
        for y in range(0, height - TILE + 1, TILE)
        for x in range(0, width - TILE + 1, TILE)
    ]
    return float(np.percentile(values, 90)) if values else _laplacian_var(gray)


def exposure(gray: np.ndarray) -> tuple[float, float]:
    """Share of pixels at 250 or above and at 5 or below."""
    count = gray.size
    return float((gray >= 250).sum() / count), float((gray <= 5).sum() / count)


def blink(face: dict) -> float:
    return (face["blink_l"] + face["blink_r"]) / 2
