"""Download, verify and open the two models Burstwise uses."""

from __future__ import annotations

import contextlib
import hashlib
import os
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

DINO_REV = "8b1f705a3a7f6f062f6bdd21986c1583d3ef105d"


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    sha256: str
    size_mb: int


DINO = ModelFile(
    "dinov2-small.onnx",
    f"https://huggingface.co/onnx-community/dinov2-small/resolve/{DINO_REV}/onnx/model.onnx",
    "f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a",
    89,
)
FACE = ModelFile(
    "face_landmarker.task",
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    4,
)


def cache_dir() -> Path:
    base = os.environ.get("BURSTWISE_HOME") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "burstwise"
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure(model: ModelFile) -> Path:
    """Return the local path of a model, downloading and checking it on first use."""
    target = cache_dir() / "models" / model.name
    if target.exists() and _sha256(target) == model.sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {model.name} ({model.size_mb} MB) ...", file=sys.stderr)
    part = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(model.url, headers={"User-Agent": "burstwise"})
    with urllib.request.urlopen(request, timeout=60) as resp, open(part, "wb") as out:
        while block := resp.read(1 << 20):
            out.write(block)
    if _sha256(part) != model.sha256:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {model.name}; the download was not kept.")
    part.replace(target)
    return target


@contextlib.contextmanager
def _quiet_stderr():
    """MediaPipe writes C++ startup warnings to file descriptor 2; hide them while it loads."""
    try:
        saved = os.dup(2)
        null = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        yield
        return
    try:
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


class Embedder:
    """DINOv2-small CLS embeddings through ONNX Runtime, on CUDA when it is installed."""

    SIDE = 224
    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, use_gpu: bool = True):
        import onnxruntime as ort

        available = ort.get_available_providers()
        providers = ["CPUExecutionProvider"]
        if use_gpu and "CUDAExecutionProvider" in available:
            providers.insert(0, "CUDAExecutionProvider")
        options = ort.SessionOptions()
        options.log_severity_level = 3
        model_path = str(ensure(DINO))
        try:
            self.session = ort.InferenceSession(
                model_path, sess_options=options, providers=providers
            )
        except Exception:  # noqa: BLE001 - CUDA libraries missing: carry on with the CPU
            if providers[0] == "CPUExecutionProvider":
                raise
            self.session = ort.InferenceSession(
                model_path, sess_options=options, providers=["CPUExecutionProvider"]
            )
        self.provider = self.session.get_providers()[0]
        self._input = self.session.get_inputs()[0].name

    @property
    def device(self) -> str:
        return "cuda" if self.provider == "CUDAExecutionProvider" else "cpu"

    def prepare(self, small_rgb: np.ndarray) -> np.ndarray:
        """Turn a SIDE x SIDE RGB uint8 image into a normalised CHW float tensor."""
        x = small_rgb.astype(np.float32) / 255.0
        return ((x - self.MEAN) / self.STD).transpose(2, 0, 1)

    def embed(self, batch: np.ndarray) -> np.ndarray:
        """Unit-length CLS vectors for a batch of prepared tensors."""
        out = self.session.run(None, {self._input: batch.astype(np.float32)})[0]
        cls = out[:, 0, :]
        return cls / np.linalg.norm(cls, axis=1, keepdims=True)


class ModelLoadError(RuntimeError):
    """A model could not start. The message says what to install or try."""


def _load_hint(exc: BaseException) -> str:
    text = str(exc)
    if "libEGL" in text or "libGLES" in text or "libGL." in text:
        return (
            "the system graphics libraries that MediaPipe needs are missing. "
            "On Debian or Ubuntu run: sudo apt install libegl1 libgles2"
        )
    return text


class FaceLandmarks:
    """MediaPipe face landmarker with eye blink blendshapes, one instance per thread."""

    def __init__(self):
        self._local = threading.local()
        self._all: list = []
        self._lock = threading.Lock()
        self._path = str(ensure(FACE))

    def _get(self):
        landmarker = getattr(self._local, "landmarker", None)
        if landmarker is None:
            with self._lock, _quiet_stderr():
                try:
                    from mediapipe.tasks import python as mp_python
                    from mediapipe.tasks.python import vision

                    options = vision.FaceLandmarkerOptions(
                        base_options=mp_python.BaseOptions(model_asset_path=self._path),
                        running_mode=vision.RunningMode.IMAGE,
                        output_face_blendshapes=True,
                        num_faces=12,
                        min_face_detection_confidence=0.4,
                        min_face_presence_confidence=0.4,
                    )
                    landmarker = vision.FaceLandmarker.create_from_options(options)
                except (OSError, ImportError) as exc:
                    raise ModelLoadError(
                        f"the face model could not start: {_load_hint(exc)}"
                    ) from exc
                self._all.append(landmarker)
            self._local.landmarker = landmarker
        return landmarker

    def warm(self) -> None:
        """Start the face model on this thread now, so a broken install fails once, early."""
        self._get()

    def close(self) -> None:
        with self._lock:
            for landmarker in self._all:
                landmarker.close()
            self._all.clear()
        self._local = threading.local()

    def detect(self, rgb: np.ndarray) -> list[dict]:
        """Faces as normalised boxes with the two eye blink scores."""
        import mediapipe as mp

        result = self._get().detect(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        )
        faces = []
        for points, shapes in zip(result.face_landmarks, result.face_blendshapes, strict=False):
            xs = [p.x for p in points]
            ys = [p.y for p in points]
            scores = {s.category_name: s.score for s in shapes}
            x0, x1 = max(0.0, min(xs)), min(1.0, max(xs))
            y0, y1 = max(0.0, min(ys)), min(1.0, max(ys))
            faces.append(
                {
                    "box": [x0, y0, x1 - x0, y1 - y0],
                    "blink_l": float(scores.get("eyeBlinkLeft", 0.0)),
                    "blink_r": float(scores.get("eyeBlinkRight", 0.0)),
                }
            )
        return faces
