"""Local review app: a FastAPI backend and a static single page front end."""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import media
from .config import Settings
from .export import copy_keepers, edit_for, write_xmp
from .library import Library, analyze_folder, regroup
from .models import cache_dir
from .pick import group_sharpness
from .xmp import undo_latest

WEB_DIR = Path(__file__).parent / "web"
THUMB_SIDE = 480
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
VALID_STATES = {"pick", "review", "alt", "reject"}


class Session:
    """One folder under review: the library, the user's decisions and the analysis job."""

    def __init__(self, folder: Path, settings: Settings, use_gpu: bool):
        self.folder = folder
        self.settings = settings
        self.use_gpu = use_gpu
        self.library: Library | None = None
        self.lock = threading.Lock()
        self.job = {"state": "idle", "done": 0, "total": 0, "name": "", "error": None}
        self.decision_file = folder / ".burstwise" / "decisions.json"
        self.decisions: dict[str, dict] = {}
        self.thumbs = cache_dir() / "thumbs"
        self.thumbs.mkdir(parents=True, exist_ok=True)

    def load_decisions(self) -> None:
        if self.decision_file.exists():
            self.decisions = json.loads(self.decision_file.read_text())

    def save_decisions(self) -> None:
        self.decision_file.parent.mkdir(parents=True, exist_ok=True)
        self.decision_file.write_text(json.dumps(self.decisions))

    def start(self) -> bool:
        with self.lock:
            if self.job["state"] == "running":
                return False
            self.job = {"state": "running", "done": 0, "total": 0, "name": "", "error": None}
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _progress(self, done: int, total: int, name: str) -> None:
        self.job.update(done=done, total=total, name=name)

    def _run(self) -> None:
        try:
            self.library = analyze_folder(
                self.folder, self.settings, use_gpu=self.use_gpu, progress=self._progress
            )
            self.load_decisions()
            self.job["state"] = "done"
        except Exception as exc:  # noqa: BLE001 - report any failure to the page
            self.job.update(state="error", error=f"{type(exc).__name__}: {exc}")

    def photo(self, photo_id: str):
        if self.library:
            for photo in self.library.photos:
                if photo.id == photo_id:
                    return photo
        raise HTTPException(404, "unknown photo")

    def thumb(self, photo_id: str, side: int) -> Path:
        target = self.thumbs / f"{photo_id}_{side}.jpg"
        if not target.exists():
            img, _ = media.load_preview(Path(self.photo(photo_id).path), side)
            partial = target.with_name(target.name + ".part")
            img.save(partial, format="JPEG", quality=85)
            partial.replace(target)
        return target


def state_payload(session: Session) -> dict:
    library = session.library
    payload: dict = {
        "folder": str(session.folder),
        "job": session.job,
        "settings": session.settings.to_dict(),
        "demo": False,
    }
    if library is None:
        return payload
    group_of = library.group_of()
    sharp: dict[str, float] = {}
    for members in library.groups:
        sharp.update(group_sharpness([library.photos[i] for i in members]))
    photos = []
    for photo in library.photos:
        verdict = library.verdicts[photo.id]
        photos.append(
            {
                "id": photo.id,
                "name": photo.name,
                "width": photo.width,
                "height": photo.height,
                "taken": photo.taken,
                "group": group_of[photo.id],
                "state": verdict.state,
                "rank": verdict.rank,
                "reasons": verdict.reasons,
                "problems": verdict.problems,
                "sharp": round(sharp[photo.id], 1),
                "highlights": round(photo.clip_hi, 4),
                "shadows": round(photo.clip_lo, 4),
                "faces": [
                    {"box": f["box"], "blink": round((f["blink_l"] + f["blink_r"]) / 2, 3)}
                    for f in photo.faces
                ],
            }
        )
    payload.update(
        photos=photos,
        groups=[[library.photos[i].id for i in m] for m in library.groups],
        counts=library.counts(),
        device=library.device,
        seconds=round(library.seconds, 2),
        decisions=session.decisions,
        failed=[{"file": f, "error": e} for f, e in library.failed],
    )
    return payload


def create_app(session: Session) -> FastAPI:
    app = FastAPI(title="Burstwise", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        """Refuse other host names, which blocks DNS rebinding, and cross-site writes."""
        host = urlparse("//" + request.headers.get("host", "")).hostname
        if host not in LOOPBACK:
            return JSONResponse({"detail": "unexpected host name"}, status_code=403)
        if request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
        return await call_next(request)

    @app.get("/api/state")
    def get_state():
        return state_payload(session)

    @app.post("/api/analyze")
    def analyze():
        return {"started": session.start()}

    @app.post("/api/settings")
    async def settings(request: Request):
        if session.library is None:
            raise HTTPException(409, "analysis has not finished")
        body = await _json_object(request)
        merged = Settings.from_dict({**session.settings.to_dict(), **body})
        try:
            merged.validate()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        session.settings = merged
        regroup(session.library, merged)
        return state_payload(session)

    @app.put("/api/decision/{photo_id}")
    async def decide(photo_id: str, request: Request):
        session.photo(photo_id)
        body = await _json_object(request)
        clean = {}
        if body.get("state") in VALID_STATES:
            clean["state"] = body["state"]
        if isinstance(body.get("rating"), int) and -1 <= body["rating"] <= 5:
            clean["rating"] = body["rating"]
        if isinstance(body.get("label"), str) and body["label"] in {
            "Red", "Yellow", "Green", "Blue", "Purple",
        }:  # fmt: skip
            clean["label"] = body["label"]
        if clean:
            session.decisions[photo_id] = clean
        else:
            session.decisions.pop(photo_id, None)
        session.save_decisions()
        return {"decisions": session.decisions}

    @app.get("/api/thumb/{photo_id}")
    def thumb(photo_id: str, size: int = THUMB_SIDE):
        side = min(max(size, 120), media.PREVIEW_SIDE)
        return FileResponse(
            session.thumb(photo_id, side), headers={"Cache-Control": "max-age=3600"}
        )

    @app.post("/api/xmp")
    async def xmp(request: Request):
        library = _ready(session)
        body = await _json_object(request)
        naming = body.get("naming", "both")
        if naming not in {"adobe", "darktable", "both"}:
            raise HTTPException(400, "naming must be adobe, darktable or both")
        tally = write_xmp(
            library,
            naming,
            overwrite=bool(body.get("overwrite")),
            dry_run=bool(body.get("dry_run")),
            decisions=session.decisions,
        )
        return {"tally": tally}

    @app.get("/api/xmp-preview/{photo_id}")
    def xmp_preview(photo_id: str):
        library = _ready(session)
        photo = session.photo(photo_id)
        edit = edit_for(
            library.verdicts[photo_id], library.settings, session.decisions.get(photo_id)
        )
        return {"name": photo.name, "edit": None if edit is None else edit.__dict__}

    @app.post("/api/undo")
    def undo():
        return {"restored": undo_latest(session.folder)}

    @app.post("/api/export")
    async def export(request: Request):
        library = _ready(session)
        body = await _json_object(request)
        dest = Path(str(body.get("dest", ""))).expanduser()
        if not body.get("dest"):
            raise HTTPException(400, "dest is required")
        kept = copy_keepers(library, dest, decisions=session.decisions)
        return {"copied": len(kept), "dest": str(dest)}

    @app.get("/api/locales")
    def locales():
        return sorted(p.stem for p in (WEB_DIR / "locales").glob("*.json"))

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


async def _json_object(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(400, "body is not valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "expected a JSON object")
    return body


def _ready(session: Session) -> Library:
    if session.library is None:
        raise HTTPException(409, "analysis has not finished")
    return session.library


def serve(folder: Path, settings: Settings, use_gpu: bool, port: int, open_browser: bool) -> None:
    import uvicorn

    session = Session(folder, settings, use_gpu)
    session.start()
    url = f"http://127.0.0.1:{port}"
    print(f"Burstwise review app for {folder}\n  {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(session), host="127.0.0.1", port=port, log_level="warning")
