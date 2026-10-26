"""Command line: cull a folder, open the review app, undo, download models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, media
from .config import Settings
from .export import copy_keepers, write_report, write_xmp
from .library import Library, analyze_folder
from .models import DINO, FACE, ensure
from .pick import reason_text
from .xmp import undo_latest


def _settings(args: argparse.Namespace) -> Settings:
    return Settings(similarity=args.similarity, scene_gap=args.scene_gap)


def _add_analysis_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("folder", type=Path, help="folder of photos")
    parser.add_argument(
        "--similarity",
        type=float,
        default=Settings.similarity,
        help="cosine similarity needed to share a group (default %(default)s)",
    )
    parser.add_argument(
        "--scene-gap",
        type=float,
        default=Settings.scene_gap,
        help="seconds apart that always split groups (default %(default)s)",
    )
    parser.add_argument("--cpu", action="store_true", help="do not use the GPU")
    parser.add_argument("--no-recursive", action="store_true", help="skip subfolders")
    parser.add_argument("--workers", type=int, default=None, help="decoder threads")


def _progress(done: int, total: int, name: str) -> None:
    if sys.stderr.isatty():
        print(f"\r  {done}/{total} {name[:40]:<40}", end="", file=sys.stderr, flush=True)
        if done == total:
            print(file=sys.stderr)


def _folder(args: argparse.Namespace) -> Path:
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"burstwise: {folder} is not a folder")
    if not media.find_photos(folder, recursive=not args.no_recursive):
        sys.exit(f"burstwise: no supported photos in {folder}")
    return folder


def _run(args: argparse.Namespace) -> Library:
    folder = _folder(args)
    return analyze_folder(
        folder,
        _settings(args),
        use_gpu=not args.cpu,
        workers=args.workers,
        recursive=not args.no_recursive,
        progress=_progress,
    )


def _summary(library: Library) -> str:
    c = library.counts()
    lines = [
        f"{len(library.photos)} photos in {len(library.groups)} groups, "
        f"{library.seconds:.1f}s on {library.device} ({library.cached} from cache)",
        f"  pick {c['pick']}   review {c['review']}   alt {c['alt']}   reject {c['reject']}",
    ]
    for path, error in library.failed:
        lines.append(f"  skipped {path}: {error}")
    return "\n".join(lines)


def cmd_cull(args: argparse.Namespace) -> int:
    library = _run(args)
    print(_summary(library))
    if args.verbose:
        group_of = library.group_of()
        for photo in library.photos:
            verdict = library.verdicts[photo.id]
            notes = [reason_text(x) for x in verdict.reasons + verdict.problems]
            print(f"  g{group_of[photo.id]:<4} {verdict.state:<7} {photo.name}  {'; '.join(notes)}")
    if args.write_xmp:
        tally = write_xmp(library, args.xmp_naming, overwrite=args.overwrite, dry_run=args.dry_run)
        verb = "would write" if args.dry_run else "wrote"
        print(f"{verb} sidecars: " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    if args.report:
        write_report(library, args.report)
        print(f"report: {args.report}")
    if args.copy_keepers:
        kept = copy_keepers(library, args.copy_keepers)
        print(f"{len(kept)} keepers copied to {args.copy_keepers}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    folder = _folder(args)
    serve(
        folder, _settings(args), use_gpu=not args.cpu, port=args.port, open_browser=not args.no_open
    )
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    count = undo_latest(args.folder.expanduser().resolve())
    print(f"restored {count} sidecars" if count else "nothing to undo")
    return 0


def cmd_models(_: argparse.Namespace) -> int:
    for model in (DINO, FACE):
        print(ensure(model))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="burstwise", description="Cull a photo folder: groups, checks, best frame, XMP."
    )
    parser.add_argument("--version", action="version", version=f"burstwise {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    cull = sub.add_parser("cull", help="analyse a folder and optionally write XMP sidecars")
    _add_analysis_options(cull)
    cull.add_argument("--write-xmp", action="store_true", help="write ratings and labels")
    cull.add_argument(
        "--xmp-naming",
        choices=["adobe", "darktable", "both"],
        default="both",
        help="IMG.xmp, IMG.ext.xmp or both (default %(default)s)",
    )
    cull.add_argument(
        "--overwrite",
        action="store_true",
        help="replace ratings and labels that are already set in a sidecar",
    )
    cull.add_argument("--dry-run", action="store_true", help="count sidecars without writing")
    cull.add_argument("--report", type=Path, help="write a JSON report")
    cull.add_argument("--copy-keepers", type=Path, metavar="DIR", help="copy picked photos to DIR")
    cull.add_argument("-v", "--verbose", action="store_true", help="print every photo")
    cull.set_defaults(func=cmd_cull)

    serve = sub.add_parser("serve", help="open the review app in your browser")
    _add_analysis_options(serve)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-open", action="store_true", help="do not open a browser tab")
    serve.set_defaults(func=cmd_serve)

    undo = sub.add_parser("undo", help="restore the sidecars changed by the last --write-xmp")
    undo.add_argument("folder", type=Path)
    undo.set_defaults(func=cmd_undo)

    models = sub.add_parser("models", help="download the models and print their paths")
    models.set_defaults(func=cmd_models)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
