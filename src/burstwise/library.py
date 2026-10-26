"""Analyse a folder into a Library: sorted photos, groups and a verdict for each."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import media
from .analyze import Analyzer, Photo, photo_id
from .cache import Cache
from .config import Settings
from .group import group_photos, sort_photos
from .pick import Verdict, judge_group


class NothingAnalysed(RuntimeError):
    """Every photo in the folder failed, so there is nothing to show."""


Progress = Callable[[int, int, str], None]


@dataclass
class Library:
    folder: Path
    settings: Settings
    photos: list[Photo]
    groups: list[list[int]] = field(default_factory=list)
    verdicts: dict[str, Verdict] = field(default_factory=dict)
    failed: list[tuple[str, str]] = field(default_factory=list)
    device: str = "cpu"
    seconds: float = 0.0
    cached: int = 0

    def group_of(self) -> dict[str, int]:
        return {self.photos[i].id: g for g, members in enumerate(self.groups) for i in members}

    def counts(self) -> dict[str, int]:
        tally = {"pick": 0, "review": 0, "alt": 0, "reject": 0}
        for verdict in self.verdicts.values():
            tally[verdict.state] += 1
        return tally


def regroup(library: Library, settings: Settings | None = None) -> Library:
    """Recompute groups and verdicts from cached measurements with new settings."""
    if settings is not None:
        library.settings = settings
    library.photos = sort_photos(library.photos)
    library.groups = group_photos(library.photos, library.settings) if library.photos else []
    library.verdicts = {}
    for members in library.groups:
        library.verdicts.update(judge_group([library.photos[i] for i in members], library.settings))
    return library


def analyze_folder(
    folder: Path,
    settings: Settings,
    use_gpu: bool = True,
    workers: int | None = None,
    recursive: bool = True,
    progress: Progress | None = None,
    cache: Cache | None = None,
    analyzer: Analyzer | None = None,
) -> Library:
    started = time.perf_counter()
    paths = media.find_photos(folder, recursive)
    own_cache = cache is None
    cache = cache or Cache()
    photos: list[Photo] = []
    todo: list[Path] = []
    for path in paths:
        stat = path.stat()
        hit = cache.get(photo_id(path, stat.st_size, stat.st_mtime_ns))
        if hit:
            photos.append(hit)
        else:
            todo.append(path)
    cached = len(photos)
    failed: list[tuple[str, str]] = []
    done = cached
    total = len(paths)
    if progress and cached:
        progress(done, total, "")
    device = "cpu"
    if todo:
        try:
            analyzer = analyzer or Analyzer(use_gpu=use_gpu)
        except BaseException:
            if own_cache:
                cache.close()
            raise
        device = analyzer.device
        count = workers or min(8, os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=count) as pool:
            jobs = {pool.submit(analyzer.analyze, path): path for path in todo}
            for job in as_completed(jobs):
                path = jobs[job]
                try:
                    photo = job.result()
                except Exception as exc:  # noqa: BLE001 - one unreadable file must not stop a run
                    failed.append((str(path), f"{type(exc).__name__}: {exc}"))
                else:
                    cache.put(photo)
                    photos.append(photo)
                done += 1
                if progress:
                    progress(done, total, path.name)
        analyzer.landmarks.close()
    if own_cache:
        cache.close()
    if failed and not photos:
        path, error = failed[0]
        raise NothingAnalysed(
            f"none of the {len(paths)} photos could be analysed. First error: {path}: {error}"
        )
    library = Library(
        folder=folder,
        settings=settings,
        photos=photos,
        failed=failed,
        device=device,
        cached=cached,
    )
    regroup(library)
    library.seconds = time.perf_counter() - started
    return library
