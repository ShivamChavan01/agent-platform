import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import urllib.request

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import auth, conversations, files, projects

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

_KEEP_ALIVE_INTERVAL_S = 600
# Ping only during waking hours (IST, no DST) — nobody tests at night, so the
# instance is allowed to sleep then. Saves ~1/3 of the 750 free instance
# hours/month; the first visitor after the window eats one cold start.
_KEEP_ALIVE_IST_START = 7   # 07:00 IST
_KEEP_ALIVE_IST_END = 23    # 23:00 IST


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def _ist_hour() -> int:
    utc_hour = time.gmtime().tm_hour
    return (utc_hour + 5) % 24 if time.gmtime().tm_min < 30 else (utc_hour + 6) % 24


async def _keep_alive_loop() -> None:
    """Ping our own /health periodically so the Render free instance never
    idles long enough to spin down. Only runs when RENDER_EXTERNAL_URL is
    set (i.e. on Render) — local dev and tests never start it."""
    import logging

    log = logging.getLogger("uvicorn.error")
    url = os.environ["RENDER_EXTERNAL_URL"].rstrip("/") + "/health"
    log.info(
        "keep-alive enabled: pinging %s every %ss between %02d:00-%02d:00 IST",
        url, _KEEP_ALIVE_INTERVAL_S, _KEEP_ALIVE_IST_START, _KEEP_ALIVE_IST_END,
    )
    while True:
        hour = _ist_hour()
        if not (_KEEP_ALIVE_IST_START <= hour < _KEEP_ALIVE_IST_END):
            await asyncio.sleep(_KEEP_ALIVE_INTERVAL_S)
            continue
        await asyncio.sleep(_KEEP_ALIVE_INTERVAL_S)
        try:
            await asyncio.to_thread(urllib.request.urlopen, url, None, 30)
        except Exception as exc:
            log.warning("keep-alive ping failed: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("RENDER_EXTERNAL_URL"):
        task = asyncio.create_task(_keep_alive_loop())
        yield
        task.cancel()
    else:
        yield


app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(422, "Invalid request body")


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(conversations.router)
app.include_router(files.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    """Serve the built React app (SPA) for any route the API doesn't own.

    Registered after the API routers, so it only catches unmatched GETs.
    Real files under frontend/dist (e.g. /assets/*.js) are served as-is;
    everything else falls back to index.html so client-side routes like
    /login and /app/projects/* survive a refresh. With no build present
    (a bare API container) it returns a JSON 404.
    """
    if not _FRONTEND_INDEX.is_file():
        return _error_response(404, "Not found")
    base = _FRONTEND_DIST.resolve()
    target = (base / (full_path or "index.html")).resolve()
    if not str(target).startswith(str(base)):
        return _error_response(404, "Not found")
    if target.is_file():
        return FileResponse(target)
    return FileResponse(_FRONTEND_INDEX)
