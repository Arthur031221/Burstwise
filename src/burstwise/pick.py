"""Rate every photo of a group against its peers and pick the best frame.

Reasons and problems are codes with numbers, so the CLI prints English and the web
interface renders its own language.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import checks
from .analyze import Photo
from .config import Settings


@dataclass
class Verdict:
    state: str  # pick, review, alt or reject
    rank: int
    problems: list[dict] = field(default_factory=list)
    reasons: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def group_sharpness(photos: list[Photo]) -> dict[str, float]:
    """One comparable sharpness per photo.

    Face sharpness is used only when every frame of the group has a face, because a face
    patch and a whole-frame tile score are on different scales and must not be compared.
    """
    use_face = all(p.sharp_face > 0 for p in photos)
    return {p.id: p.sharp_face if use_face else p.sharp_tile for p in photos}


def closed_faces(photo: Photo, settings: Settings) -> int:
    return sum(1 for f in photo.faces if checks.blink(f) >= settings.blink_closed)


def _problems(
    photo: Photo, sharp: float, best_sharp: float, group_size: int, settings: Settings
) -> list[dict]:
    problems = []
    closed = closed_faces(photo, settings)
    if closed:
        problems.append({"code": "closed_eyes", "closed": closed, "faces": len(photo.faces)})
    share = sharp / best_sharp if best_sharp > 0 else 1.0
    relative_soft = group_size > 1 and share < settings.soft_ratio
    if relative_soft or sharp < settings.soft_floor:
        problems.append({"code": "soft", "percent": round(100 * min(share, 1.0))})
    if photo.clip_hi >= settings.clip_highlight:
        problems.append({"code": "highlights", "percent": round(100 * photo.clip_hi)})
    if photo.clip_lo >= settings.clip_shadow:
        problems.append({"code": "shadows", "percent": round(100 * photo.clip_lo)})
    return problems


def _flagged(problems: list[dict]) -> bool:
    return any(p["code"] in {"soft", "highlights", "shadows"} for p in problems)


def _clipped(problems: list[dict]) -> bool:
    return any(p["code"] in {"highlights", "shadows"} for p in problems)


def _winner_reasons(
    winner: Photo,
    others: list[Photo],
    problems: dict[str, list[dict]],
    sharp: dict[str, float],
    settings: Settings,
) -> list[dict]:
    if not others:
        return [{"code": "only_frame"}]
    reasons = []
    winner_closed = closed_faces(winner, settings)
    peers_closed = sum(1 for o in others if closed_faces(o, settings) > winner_closed)
    if peers_closed and winner.faces:
        code = "fewest_closed" if winner_closed else "eyes_open"
        reasons.append({"code": code, "peers": peers_closed, "of": len(others)})
    runner_up = max(sharp[o.id] for o in others)
    if runner_up > 0 and sharp[winner.id] >= 1.1 * runner_up:
        gain = round(100 * (sharp[winner.id] / runner_up - 1))
        reasons.append({"code": "sharpest", "percent": gain})
    winner_clips = _clipped(problems[winner.id])
    peers_clip = sum(1 for o in others if _clipped(problems[o.id]) and not winner_clips)
    if peers_clip:
        reasons.append({"code": "least_clipping", "peers": peers_clip, "of": len(others)})
    return reasons or [{"code": "tie"}]


def judge_group(photos: list[Photo], settings: Settings) -> dict[str, Verdict]:
    """Verdicts for the photos of one group, keyed by photo id."""
    sharp = group_sharpness(photos)
    best_sharp = max(sharp.values())
    problems = {p.id: _problems(p, sharp[p.id], best_sharp, len(photos), settings) for p in photos}

    def rank_key(p: Photo):
        flagged = sum(1 for q in problems[p.id] if q["code"] != "closed_eyes")
        return (closed_faces(p, settings), flagged, -sharp[p.id], p.taken)

    ordered = sorted(photos, key=rank_key)
    winner = ordered[0]
    verdicts = {}
    for rank, photo in enumerate(ordered, start=1):
        issues = problems[photo.id]
        if photo is winner:
            state = "review" if issues else "pick"
            reasons = _winner_reasons(winner, ordered[1:], problems, sharp, settings)
        else:
            state = "reject" if issues else "alt"
            reasons = []
        verdicts[photo.id] = Verdict(state=state, rank=rank, problems=issues, reasons=reasons)
    return verdicts


def reason_text(item: dict) -> str:
    """English wording of a reason or problem code, used by the CLI, reports and XMP."""
    code = item["code"]
    templates = {
        "only_frame": "only frame of its moment",
        "eyes_open": "eyes open on every face, {peers} of {of} other frames have a blink",
        "fewest_closed": "fewest closed eyes, {peers} of {of} other frames have more",
        "sharpest": "subject {percent}% sharper than the next frame",
        "least_clipping": "no clipping, {peers} of {of} other frames clip",
        "tie": "sharpest by a small margin, no other check separates the frames",
        "closed_eyes": "{closed} of {faces} faces have closed eyes",
        "soft": "soft, {percent}% of the sharpest frame",
        "highlights": "{percent}% of pixels clipped to white",
        "shadows": "{percent}% of pixels crushed to black",
    }
    return templates[code].format(**item)
