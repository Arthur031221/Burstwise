"""SQLite cache of per-photo analysis so a second pass is instant."""

from __future__ import annotations

import json
import sqlite3
import threading

from .analyze import ANALYSIS_VERSION, Photo
from .models import cache_dir


class Cache:
    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(
            str(path or cache_dir() / "analysis.db"), check_same_thread=False
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS photos "
            "(id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL)"
        )

    def get(self, photo_id: str) -> Photo | None:
        with self._lock:
            row = self._db.execute(
                "SELECT data FROM photos WHERE id = ? AND version = ?",
                (photo_id, ANALYSIS_VERSION),
            ).fetchone()
        return Photo.from_dict(json.loads(row[0])) if row else None

    def put(self, photo: Photo) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO photos (id, version, data) VALUES (?, ?, ?)",
                (photo.id, ANALYSIS_VERSION, json.dumps(photo.to_dict())),
            )
            self._db.commit()

    def close(self) -> None:
        self._db.close()
