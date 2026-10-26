"""Rebuild the sample photo set from four openly licensed Wikimedia Commons videos.

The frames are real, but they come from video, so the capture times are generated: each
scene starts ten minutes after the last and frames follow the sampling rate. Needs ffmpeg.

    python examples/make_sample.py examples/sample
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

# name, Commons file, start second, length in seconds, frames per second
SCENES = [
    ("singer", "Song sung during marriage ceremony in Arebashe.webm", 4, 8, 6),
    ("finch", "Carduelis sinica bathing and flying x40 slowmotion.webm", 0, 7, 6),
    ("cat", "Cat Play 03.webm", 0, 9, 5),
    ("grad", "Graduation Ceremony (1008568).webm", 5, 12, 3),
]
START = datetime(2024, 6, 1, 10, 0, 0)
SCENE_GAP = timedelta(minutes=10)
AGENT = {"User-Agent": "Burstwise-sample/0.1 (https://github.com/Arthur031221/Burstwise)"}


def download(title: str, target: Path) -> None:
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(title)
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as r:
        target.write_bytes(r.read())


def extract(video: Path, start: int, length: int, fps: int, out: Path, name: str) -> list[Path]:
    pattern = out / f"{name}_%03d.jpg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(length), "-i", str(video)]
        + ["-vf", f"fps={fps},scale=1280:-2", "-q:v", "3", "-start_number", "1", str(pattern)],
        check=True,
    )
    return sorted(out.glob(f"{name}_*.jpg"))


def stamp(frames: list[Path], begin: datetime, fps: int) -> None:
    for i, frame in enumerate(frames):
        when = begin + timedelta(seconds=i / fps)
        img = Image.open(frame)
        exif = Image.Exif()
        exif[0x0110] = "Burstwise sample"
        sub = exif.get_ifd(0x8769)
        sub[0x9003] = when.strftime("%Y:%m:%d %H:%M:%S")
        sub[0x9291] = f"{when.microsecond // 1000:03d}"
        img.save(frame, quality=92, exif=exif)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for index, (name, title, start, length, fps) in enumerate(SCENES):
            video = Path(tmp) / f"{name}.vid"
            download(title, video)
            frames = extract(video, start, length, fps, out, name)
            stamp(frames, START + index * SCENE_GAP, fps)
            print(f"{name}: {len(frames)} frames")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "examples/sample"))
