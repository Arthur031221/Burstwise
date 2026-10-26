"""A broken install must stop the run with a reason, not report an empty folder."""

import threading
from types import SimpleNamespace

import pytest

from burstwise import cli, models
from burstwise.cache import Cache
from burstwise.config import Settings
from burstwise.library import NothingAnalysed, analyze_folder

from .helpers import texture, write_jpeg


class BrokenAnalyzer:
    device = "cpu"
    landmarks = SimpleNamespace(close=lambda: None)

    def analyze(self, path):
        raise OSError("libEGL.so.1: cannot open shared object file")


@pytest.fixture
def shots(tmp_path):
    for n in range(3):
        write_jpeg(tmp_path / f"IMG_{n}.jpg", texture(n))
    return tmp_path


def test_every_photo_failing_raises_with_the_first_error(shots, tmp_path):
    cache = Cache(tmp_path / "c.db")
    with pytest.raises(NothingAnalysed, match=r"none of the 3 photos.*libEGL"):
        analyze_folder(shots, Settings(), analyzer=BrokenAnalyzer(), cache=cache)
    cache.close()


def test_cull_prints_the_reason_and_exits_with_one(shots, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise models.ModelLoadError("the face model could not start: install libegl1")

    monkeypatch.setattr(cli, "analyze_folder", boom)
    assert cli.main(["cull", str(shots), "--cpu"]) == 1
    assert "burstwise: the face model could not start" in capsys.readouterr().err


def test_missing_graphics_library_names_the_package(monkeypatch):
    from mediapipe.tasks.python import vision

    def fail(_options):
        raise OSError("libEGL.so.1: cannot open shared object file: No such file or directory")

    monkeypatch.setattr(vision.FaceLandmarker, "create_from_options", staticmethod(fail))
    faces = models.FaceLandmarks.__new__(models.FaceLandmarks)
    faces._local = threading.local()
    faces._all = []
    faces._lock = threading.Lock()
    faces._path = "unused.task"
    with pytest.raises(models.ModelLoadError, match="sudo apt install libegl1 libgles2"):
        faces.warm()


def test_failure_while_importing_mediapipe_gets_the_same_hint(monkeypatch):
    import builtins

    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name.startswith("mediapipe"):
            raise ImportError("libEGL.so.1: cannot open shared object file")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    faces = models.FaceLandmarks.__new__(models.FaceLandmarks)
    faces._local = threading.local()
    faces._all = []
    faces._lock = threading.Lock()
    faces._path = "unused.task"
    with pytest.raises(models.ModelLoadError, match="libegl1"):
        faces.warm()
