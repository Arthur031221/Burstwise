"""Thresholds in one place. Every value is a documented, adjustable rule."""

from __future__ import annotations

from dataclasses import asdict, dataclass

LABELS = {"Red", "Yellow", "Green", "Blue", "Purple"}


@dataclass
class Settings:
    # Photos closer than this in cosine similarity of DINOv2 embeddings share a group.
    similarity: float = 0.80
    # Photos taken further apart than this many seconds are never grouped.
    scene_gap: float = 120.0
    # Mean of the two eyeBlink blendshape scores at or above this counts as closed.
    blink_closed: float = 0.50
    # A frame is soft when its subject sharpness is below this share of the group best.
    soft_ratio: float = 0.55
    # Subject sharpness below this is soft even without a sharper neighbour.
    soft_floor: float = 12.0
    # Share of preview pixels at 250 or above (highlights) or at 5 or below (shadows).
    clip_highlight: float = 0.08
    clip_shadow: float = 0.30
    pick_stars: int = 4
    pick_label: str = "Green"
    reject_label: str = "Red"
    review_label: str = "Yellow"

    def validate(self) -> None:
        """Raise ValueError for a value the rules cannot work with."""
        unit = ("similarity", "blink_closed", "soft_ratio", "clip_highlight", "clip_shadow")
        for name in unit:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a number from 0 to 1")
        for name in ("scene_gap", "soft_floor"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
                raise ValueError(f"{name} must be a number of 0 or more")
        if isinstance(self.pick_stars, bool) or self.pick_stars not in range(6):
            raise ValueError("pick_stars must be a whole number from 0 to 5")
        for name in ("pick_label", "reject_label", "review_label"):
            if getattr(self, name) not in LABELS:
                raise ValueError(f"{name} must be one of {', '.join(sorted(LABELS))}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
