import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.lifecycle import record_heartbeat, request_shutdown, watch_inactivity
from app.routes import export, segments, videos

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
    watcher = asyncio.create_task(watch_inactivity())
    try:
        yield
    finally:
        watcher.cancel()


app = FastAPI(title="snip-snap", lifespan=lifespan)

app.include_router(videos.router)
app.include_router(segments.router)
app.include_router(export.router)


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
