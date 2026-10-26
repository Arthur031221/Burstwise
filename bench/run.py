"""Measure Burstwise throughput on public photos and write bench/results.json.

    python bench/run.py prepare DIR      download the CC0 test photos into DIR (about 400 MB)
    python bench/run.py measure DIR [SAMPLE]   time the sample, large JPEG and RAW sets
    python bench/run.py render           rebuild docs/benchmark.md from results.json

Every file used is CC0: four large JPEGs from Wikimedia Commons and three RAW files from
raw.pixls.us. Copies of one file are distinct files to Burstwise (different path), so they are
analysed separately, but the grouping result on copies is not meaningful. Only speed is measured.
"""

from __future__ import annotations

import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burstwise import media  # noqa: E402
from burstwise.analyze import Analyzer  # noqa: E402
from burstwise.cache import Cache  # noqa: E402
from burstwise.config import Settings  # noqa: E402
from burstwise.library import analyze_folder  # noqa: E402

AGENT = {"User-Agent": "Burstwise-bench/0.1 (https://github.com/Arthur031221/Burstwise)"}
COMMONS = [
    "Lake Mountain Landscape.jpg",
    "Mountain and Landscape.jpg",
    "Siracusan Street at Night.jpg",
    "Street lamps at the National Assembly of Quebec.jpg",
]
RAWS = [
    "Sony/ILCE-7M3/_DSC0009.ARW",
    "Sony/ILCE-7M3/_DSC0010.ARW",
    "Canon/EOS 5D Mark IV/B13A0732.CR2",
]
COPIES_LARGE, COPIES_RAW = 15, 8
RUNS = 3


def fetch(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=180) as resp:
        target.write_bytes(resp.read())


def prepare(base: Path) -> None:
    source = base / "source"
    source.mkdir(parents=True, exist_ok=True)
    for title in COMMONS:
        fetch(
            "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(title),
            source / title.replace(" ", "_"),
        )
    for name in RAWS:
        fetch("https://raw.pixls.us/data/" + urllib.parse.quote(name), source / Path(name).name)
    for folder, files, copies in (
        ("large", [p for p in source.glob("*.jpg")], COPIES_LARGE),
        ("raw", [p for p in source.iterdir() if p.suffix.lower() in media.RAW_EXT], COPIES_RAW),
    ):
        out = base / folder
        out.mkdir(exist_ok=True)
        for file in files:
            for i in range(copies):
                shutil.copy2(file, out / f"{file.stem}_{i:02d}{file.suffix}")
    print("prepared", base)


def timed(folder: Path, use_gpu: bool, warm_cache: Cache | None = None) -> tuple[float, int, str]:
    cache = warm_cache or Cache(Path(tempfile.mkdtemp()) / "bench.db")
    started = time.perf_counter()
    library = analyze_folder(folder, Settings(), use_gpu=use_gpu, cache=cache)
    seconds = time.perf_counter() - started
    if warm_cache is None:
        cache.close()
    return seconds, len(library.photos), library.device


def stage_ms(folder: Path) -> dict[str, float]:
    """Median milliseconds per photo for each stage, one thread, after a warm-up photo."""
    import cv2

    from burstwise import checks

    analyzer = Analyzer(use_gpu=True)
    files = media.find_photos(folder)[:12]
    analyzer.analyze(files[0])
    rows: dict[str, list[float]] = {"decode": [], "faces": [], "sharpness": [], "embedding": []}
    for path in files:
        t0 = time.perf_counter()
        img, _ = media.load_preview(path)
        rgb = media.to_array(img)
        t1 = time.perf_counter()
        faces = analyzer.landmarks.detect(rgb)
        t2 = time.perf_counter()
        gray = checks.gray_of(rgb)
        checks.face_sharpness(gray, [f["box"] for f in faces])
        checks.tile_sharpness(gray)
        checks.exposure(gray)
        t3 = time.perf_counter()
        small = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        analyzer.embedder.embed(analyzer.embedder.prepare(small)[None])
        t4 = time.perf_counter()
        for key, a, b in (
            ("decode", t0, t1),
            ("faces", t1, t2),
            ("sharpness", t2, t3),
            ("embedding", t3, t4),
        ):
            rows[key].append(1000 * (b - a))
    analyzer.landmarks.close()
    return {k: round(statistics.median(v), 1) for k, v in rows.items()}


def machine() -> str:
    cpu = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        platform.processor(),
    )
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        gpu = "no NVIDIA GPU"
    import os

    return f"{cpu} ({os.cpu_count()} threads), {gpu}, Python {platform.python_version()}"


def measure(base: Path, sample: Path) -> None:
    sets = [
        ("Sample frames", "1280 x 720 JPEG", sample),
        ("Large JPEG", "5100 to 7700 px wide, 2.9 to 6.6 MB", base / "large"),
        ("RAW", "ARW 24 MP, CR2 7 MP", base / "raw"),
    ]
    table = []
    best_rate = 0.0
    for name, kind, folder in sets:
        count = len(media.find_photos(folder))
        row = [name, kind, count]
        for use_gpu in (True, False):
            timed(folder, use_gpu)  # warm the files and the model
            runs = [timed(folder, use_gpu)[0] for _ in range(RUNS)]
            median = statistics.median(runs)
            row.append(f"{median:.1f} s ({count / median:.0f}/s)")
            if use_gpu and name == "Sample frames":
                best_rate = count / median
        cache = Cache(Path(tempfile.mkdtemp()) / "warm.db")
        timed(folder, False, cache)
        row.append(f"{timed(folder, False, cache)[0]:.2f} s")
        cache.close()
        table.append(row)
        print(row, flush=True)
    stages = stage_ms(base / "large")
    print("stages", stages)
    data = {
        "headline": (
            f"On the sample set Burstwise reads, groups, checks and ranks "
            f"{table[0][2]} photos in {table[0][3].split(' s')[0]} seconds with the GPU "
            f"(median of {RUNS} runs, {best_rate:.0f} photos per second)."
        ),
        "columns": [
            "Set",
            "Files",
            "Count",
            "GPU, cold",
            "CPU only, cold",
            "Second run, cached",
        ],
        "table": table,
        "stages_ms_per_photo_large": stages,
        "method": [
            f"Each cell is the median of {RUNS} runs of analyze_folder with an empty cache, "
            "after one untimed run to warm the file cache and the model.",
            "Time covers file discovery, loading both models, preview decode, face landmarks and "
            "blink scores, sharpness, exposure, the DINOv2 embedding, grouping and ranking.",
            "RAW files are read through their embedded preview. Every file in this set had one "
            "of at least 1000 px. A RAW file without one is decoded at half size, which is slower.",
            "The sample set is 166 frames from four Creative Commons videos, see "
            "examples/CREDITS.md. The large JPEG and RAW sets are CC0 files copied "
            "several times, so speed is meaningful and grouping on them is not.",
            "Photo workers: the default of min(8, CPU threads). The run had OMP_NUM_THREADS=2, "
            "so native math libraries used two threads each. Unset it for a fair CPU-only figure.",
        ],
        "notes": [
            "No accuracy figure is claimed. The checks are heuristics with documented thresholds.",
            "Blink scores come from MediaPipe blendshapes and can call a laugh or a squint closed.",
            "Speed depends on disk and CPU more than on the GPU: the embedding is a small "
            "share of the time on large files, see the stage breakdown in results.json.",
            "The large JPEG and RAW sets contain no faces, so the face stage is nearly free "
            "there. Photos with faces cost more.",
            "One machine. Numbers on other hardware will differ.",
        ],
        "date": date.today().isoformat(),
        "machine": machine(),
    }
    (ROOT / "bench" / "results.json").write_text(json.dumps(data, indent=1))
    print("wrote bench/results.json")
    render()


def render() -> None:
    """Write docs/benchmark.md from bench/results.json so the two cannot drift apart."""
    data = json.loads((ROOT / "bench" / "results.json").read_text())
    lines = ["# Benchmark", "", data["headline"], ""]
    lines += ["| " + " | ".join(data["columns"]) + " |", "|" + " --- |" * len(data["columns"])]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in data["table"]]
    stages = ", ".join(f"{k} {v} ms" for k, v in data["stages_ms_per_photo_large"].items())
    lines += ["", f"Machine: {data['machine']}. Measured on {data['date']}.", ""]
    lines += ["Per photo on the large JPEG set, one thread, median: " + stages + ".", ""]
    lines += ["## Method", ""] + [f"- {m}" for m in data["method"]]
    lines += ["", "## What this does not say", ""] + [f"- {n}" for n in data["notes"]]
    lines += [
        "",
        "## Run it yourself",
        "",
        "```",
        "python bench/run.py prepare DIR",
        "python bench/run.py measure DIR SAMPLE_DIR",
        "python bench/run.py render",
        "```",
        "",
    ]
    (ROOT / "docs" / "benchmark.md").write_text("\n".join(lines))
    print("wrote docs/benchmark.md")


def main() -> None:
    if sys.argv[1:2] == ["render"]:
        return render()
    if len(sys.argv) < 3 or sys.argv[1] not in {"prepare", "measure"}:
        sys.exit(__doc__)
    base = Path(sys.argv[2])
    if sys.argv[1] == "prepare":
        prepare(base)
    else:
        measure(base, Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "examples" / "sample")


if __name__ == "__main__":
    main()
