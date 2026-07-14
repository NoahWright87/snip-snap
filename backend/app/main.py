import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.ffmpeg_setup import ensure_ffmpeg_ready, get_status as get_ffmpeg_status
from app.lifecycle import record_heartbeat, request_shutdown, watch_inactivity
from app.open_file import open_file
from app.routes import dialogs, export, folders, segments, videos
from app.schemas import FfmpegStatus, OpenFileRequest

if getattr(sys, "frozen", False):
    # Running as a PyInstaller-packaged executable: the built frontend is
    # bundled alongside the interpreter in the extracted temp dir, not on
    # disk relative to this source file.
    FRONTEND_DIST = Path(sys._MEIPASS) / "frontend_dist"  # type: ignore[attr-defined]
else:
    FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_ffmpeg_ready()  # non-blocking: downloads in the background if needed
    watcher = asyncio.create_task(watch_inactivity())
    try:
        yield
    finally:
        watcher.cancel()


app = FastAPI(title="snip-snap", lifespan=lifespan)

app.include_router(videos.router)
app.include_router(segments.router)
app.include_router(export.router)
app.include_router(dialogs.router)
app.include_router(folders.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/heartbeat")
def heartbeat():
    record_heartbeat()
    return {"ok": True}


@app.post("/api/shutdown")
def shutdown():
    request_shutdown()
    return JSONResponse({"ok": True})


@app.get("/api/ffmpeg/status", response_model=FfmpegStatus)
def ffmpeg_status():
    return get_ffmpeg_status()


@app.post("/api/open-file")
def open_file_endpoint(payload: OpenFileRequest):
    if not Path(payload.path).exists():
        raise HTTPException(404, "file not found")
    try:
        open_file(payload.path)
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        raise HTTPException(500, f"couldn't open file: {exc}")
    return {"ok": True}


if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets"
    )

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
