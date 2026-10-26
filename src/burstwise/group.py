"""Group photos of the same moment: split by time gaps, then cluster by embedding."""

from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from .analyze import Photo, embedding_matrix
from .config import Settings

MAX_SCENE = 2500


def sort_photos(photos: list[Photo]) -> list[Photo]:
    return sorted(photos, key=lambda p: (p.taken, p.name))


def split_scenes(photos: list[Photo], scene_gap: float) -> list[list[int]]:
    """Index runs of photos with no time gap above `scene_gap`, capped in size."""
    scenes: list[list[int]] = []
    for i, photo in enumerate(photos):
        gap_found = scenes and photo.taken - photos[i - 1].taken > scene_gap
        if not scenes or gap_found or len(scenes[-1]) >= MAX_SCENE:
            scenes.append([])
        scenes[-1].append(i)
    return scenes


def _cluster(vectors: np.ndarray, similarity: float) -> np.ndarray:
    if len(vectors) == 1:
        return np.array([1])
    distance = np.clip(1.0 - vectors @ vectors.T, 0.0, 2.0)
    np.fill_diagonal(distance, 0.0)
    tree = linkage(squareform(distance, checks=False), method="average")
    return fcluster(tree, t=1.0 - similarity, criterion="distance")


def group_photos(photos: list[Photo], settings: Settings) -> list[list[int]]:
    """Groups as lists of indexes into `photos`, which must be sorted by time."""
    vectors = embedding_matrix(photos)
    groups: list[list[int]] = []
    for scene in split_scenes(photos, settings.scene_gap):
        labels = _cluster(vectors[scene], settings.similarity)
        by_label: dict[int, list[int]] = {}
        for index, label in zip(scene, labels, strict=True):
            by_label.setdefault(int(label), []).append(index)
        groups.extend(by_label.values())
    return sorted(groups, key=lambda g: g[0])
