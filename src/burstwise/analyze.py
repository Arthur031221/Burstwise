"""Analyse one photo: preview, faces, sharpness, exposure and an embedding."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import checks, media
from .models import Embedder, FaceLandmarks

ANALYSIS_VERSION = 3


@dataclass
class Photo:
    id: str
    path: str
    name: str
    size_bytes: int
    mtime_ns: int
    width: int
    height: int
    taken: float
    taken_from_exif: bool
    sharp_face: float
    sharp_tile: float
    clip_hi: float
    clip_lo: float
    faces: list[dict] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Photo:
        return cls(**data)


def photo_id(path: Path, size: int, mtime_ns: int) -> str:
    return hashlib.sha1(f"{path}|{size}|{mtime_ns}".encode()).hexdigest()[:12]


class Analyzer:
    """Holds the models. analyze() is safe to call from several threads."""

    def __init__(self, use_gpu: bool = True):
        self.embedder = Embedder(use_gpu=use_gpu)
        self.landmarks = FaceLandmarks()
        self.landmarks.warm()

    @property
    def device(self) -> str:
        return self.embedder.device

    def analyze(self, path: Path) -> Photo:
        stat = path.stat()
        img, (full_w, full_h) = media.load_preview(path)
        rgb = media.to_array(img)
        faces = self.landmarks.detect(rgb)
        gray = checks.gray_of(rgb)
        sharp_face = checks.face_sharpness(gray, [f["box"] for f in faces])
        sharp_tile = checks.tile_sharpness(gray)
        clip_hi, clip_lo = checks.exposure(gray)
        small = cv2.resize(rgb, (self.embedder.SIDE,) * 2, interpolation=cv2.INTER_AREA)
        vector = self.embedder.embed(self.embedder.prepare(small)[None])[0]
        taken, from_exif = media.capture_time(path)
        return Photo(
            id=photo_id(path, stat.st_size, stat.st_mtime_ns),
            path=str(path),
            name=path.name,
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            width=full_w,
            height=full_h,
            taken=taken,
            taken_from_exif=from_exif,
            sharp_face=sharp_face,
            sharp_tile=sharp_tile,
            clip_hi=clip_hi,
            clip_lo=clip_lo,
            faces=faces,
            embedding=[round(float(v), 6) for v in vector],
        )


def embedding_matrix(photos: list[Photo]) -> np.ndarray:
    return np.asarray([p.embedding for p in photos], dtype=np.float32)
