"""Turn verdicts into XMP sidecars, a keepers folder and a JSON report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import Settings
from .library import Library
from .pick import Verdict, group_sharpness, reason_text
from .xmp import (
    Edit,
    UndoLog,
    clear_ours,
    is_protected,
    read_existing,
    sidecar_paths,
    write_sidecar,
)

FLAG_STATES = {"pick", "review", "alt", "reject"}


def effective_state(verdict: Verdict, decision: dict | None) -> str:
    return (decision or {}).get("state") or verdict.state


def edit_for(verdict: Verdict, settings: Settings, decision: dict | None = None) -> Edit | None:
    """The XMP change for a photo, or None when it should be left unrated."""
    decision = decision or {}
    state = effective_state(verdict, decision)
    rating = decision.get("rating")
    label = decision.get("label")
    if state == "pick":
        rating = settings.pick_stars if rating is None else rating
        label = label or settings.pick_label
    elif state == "reject":
        rating = -1 if rating is None else rating
        if rating == -1:
            label = label or settings.reject_label
    elif state == "review":
        label = label or settings.review_label
    elif rating is None and not label:
        return None
    texts = [reason_text(r) for r in verdict.reasons] + [reason_text(p) for p in verdict.problems]
    return Edit(rating=rating, label=label, verdict=state, reason="; ".join(texts) or None)


def write_xmp(
    library: Library,
    naming: str = "both",
    overwrite: bool = False,
    dry_run: bool = False,
    decisions: dict[str, dict] | None = None,
) -> dict[str, int]:
    """Write sidecars for every photo. Originals are never opened for writing."""
    undo = UndoLog(library.folder)
    tally = {"created": 0, "updated": 0, "skipped": 0, "unrated": 0}
    claimed: set[Path] = set()
    for photo in library.photos:
        verdict = library.verdicts[photo.id]
        edit = edit_for(verdict, library.settings, (decisions or {}).get(photo.id))
        sidecars = sidecar_paths(Path(photo.path), naming)
        if edit is None:
            tally["unrated"] += 1
            if not dry_run:
                for sidecar in sidecars:
                    if read_existing(sidecar)[2]:
                        undo.remember(sidecar)
                        clear_ours(sidecar)
            continue
        protected = not overwrite and any(is_protected(s) for s in sidecars)
        for sidecar in sidecars:
            if protected or sidecar in claimed:
                tally["skipped"] += 1
                continue
            claimed.add(sidecar)
            if dry_run:
                tally["created" if not sidecar.exists() else "updated"] += 1
                continue
            undo.remember(sidecar)
            tally[write_sidecar(sidecar, edit, overwrite)] += 1
    return tally


def copy_keepers(
    library: Library,
    dest: Path,
    decisions: dict[str, dict] | None = None,
) -> list[Path]:
    """Copy the picked photos, with their sidecars, into `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for photo in library.photos:
        state = effective_state(library.verdicts[photo.id], (decisions or {}).get(photo.id))
        if state != "pick":
            continue
        source = Path(photo.path)
        target = _free_name(dest, source.name)
        pairs = zip(sidecar_paths(source, "both"), sidecar_paths(target, "both"), strict=True)
        for old, new in pairs:
            if old.exists():
                shutil.copy2(old, new)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _free_name(dest: Path, name: str) -> Path:
    """`dest/name`, or `dest/name_2` style when two source folders hold the same file name."""
    target = dest / name
    stem, suffix = Path(name).stem, Path(name).suffix
    count = 2
    while target.exists() or any(s.exists() for s in sidecar_paths(target, "both")):
        target = dest / f"{stem}_{count}{suffix}"
        count += 1
    return target


def report(library: Library, decisions: dict[str, dict] | None = None) -> dict:
    group_of = library.group_of()
    sharp: dict[str, float] = {}
    for members in library.groups:
        sharp.update(group_sharpness([library.photos[i] for i in members]))
    photos = []
    for photo in library.photos:
        verdict = library.verdicts[photo.id]
        photos.append(
            {
                "file": Path(photo.path).relative_to(library.folder).as_posix(),
                "group": group_of[photo.id],
                "state": effective_state(verdict, (decisions or {}).get(photo.id)),
                "rank": verdict.rank,
                "faces": len(photo.faces),
                "reasons": [reason_text(r) for r in verdict.reasons],
                "problems": [reason_text(p) for p in verdict.problems],
                "sharpness": round(sharp[photo.id], 1),
                "highlights": round(photo.clip_hi, 4),
                "shadows": round(photo.clip_lo, 4),
            }
        )
    return {
        "folder": str(library.folder),
        "settings": library.settings.to_dict(),
        "device": library.device,
        "seconds": round(library.seconds, 2),
        "photos": len(library.photos),
        "groups": len(library.groups),
        "counts": library.counts(),
        "failed": [{"file": f, "error": e} for f, e in library.failed],
        "items": photos,
    }


def write_report(library: Library, path: Path, decisions: dict[str, dict] | None = None) -> None:
    path.write_text(json.dumps(report(library, decisions), indent=1, ensure_ascii=False))
