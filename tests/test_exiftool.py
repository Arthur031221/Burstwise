"""Read the sidecars back with ExifTool, an independent XMP reader."""

import json
import shutil
import subprocess

import pytest

from burstwise.export import write_xmp
from burstwise.xmp import Edit, write_sidecar

from .test_xmp import LIGHTROOM

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def exif(path, *tags):
    out = subprocess.run(
        ["exiftool", "-j", "-G1", "-n", *tags, str(path)], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)[0]


def test_rating_label_and_verdict_are_read_back(library):
    write_xmp(library, "adobe")
    pick = next(p for p in library.photos if library.verdicts[p.id].state == "pick")
    got = exif(library.folder / pick.name.replace(".JPG", ".xmp"))
    assert got["XMP-xmp:Rating"] == 4
    assert got["XMP-xmp:Label"] == "Green"
    assert got["XMP-burstwise:Verdict"] == "pick"


def test_rejected_photo_reads_as_minus_one(library):
    write_xmp(library, "adobe")
    reject = next(p for p in library.photos if library.verdicts[p.id].state == "reject")
    got = exif(library.folder / reject.name.replace(".JPG", ".xmp"))
    assert got["XMP-xmp:Rating"] == -1 and got["XMP-xmp:Label"] == "Red"


def test_existing_develop_settings_survive(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(LIGHTROOM.format(rating="0"), encoding="utf-8")
    write_sidecar(side, Edit(rating=4, label="Green"))
    got = exif(side)
    assert got["XMP-crs:Exposure2012"] == "+0.35"
    assert got["XMP-xmp:Rating"] == 4


def test_exiftool_reports_no_warnings_for_a_new_sidecar(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    write_sidecar(side, Edit(rating=4, label="Green", verdict="pick", reason="sharpest"))
    assert "ExifTool:Warning" not in exif(side, "-a", "-u")
