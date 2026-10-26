"""End to end with the real models on generated pictures. Run with: pytest -m models"""

import os
from pathlib import Path

import pytest
from PIL import ImageFilter

from burstwise import cli
from burstwise.config import Settings
from burstwise.library import analyze_folder
from burstwise.xmp import read_existing

from .helpers import texture, write_jpeg

pytestmark = pytest.mark.models


@pytest.fixture(scope="session", autouse=True)
def model_home(tmp_path_factory):
    """One cache directory for the whole run, so the models download once."""
    home = tmp_path_factory.mktemp("home")
    previous = os.environ.get("BURSTWISE_HOME")
    os.environ["BURSTWISE_HOME"] = str(home)
    yield home
    if previous is None:
        del os.environ["BURSTWISE_HOME"]
    else:
        os.environ["BURSTWISE_HOME"] = previous


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    shots = tmp_path / "shots"
    shots.mkdir()
    sharp = texture(1, (640, 480))
    write_jpeg(shots / "A1.jpg", sharp.filter(ImageFilter.GaussianBlur(4)), "2024:06:01 10:00:00")
    write_jpeg(shots / "A2.jpg", sharp, "2024:06:01 10:00:01")
    write_jpeg(shots / "B1.jpg", texture(7, (640, 480)), "2024:06:01 11:00:00")
    return shots


def test_blurred_burst_frame_loses_and_lone_frame_is_kept(folder):
    library = analyze_folder(folder, Settings(), use_gpu=False)
    by_name = {p.name: library.verdicts[p.id] for p in library.photos}
    assert len(library.groups) == 2
    assert by_name["A2.jpg"].state == "pick"
    assert by_name["A1.jpg"].state == "reject"
    assert by_name["B1.jpg"].state in {"pick", "review"}


def test_second_run_comes_from_the_cache(folder):
    analyze_folder(folder, Settings(), use_gpu=False)
    again = analyze_folder(folder, Settings(), use_gpu=False)
    assert again.cached == 3


def test_cull_writes_sidecars_and_undo_removes_them(folder, capsys):
    assert cli.main(["cull", str(folder), "--cpu", "--write-xmp", "--xmp-naming", "adobe"]) == 0
    assert read_existing(folder / "A2.xmp")[:2] == (4, "Green")
    assert read_existing(folder / "A1.xmp")[0] == -1
    assert cli.main(["undo", str(folder)]) == 0
    assert not list(folder.glob("*.xmp"))
    assert "restored 3" in capsys.readouterr().out
