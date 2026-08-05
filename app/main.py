from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers import auth, conversations, files, projects

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Preload the embedding model so the first upload/chat request of a fresh
    # container is fast (lazy first load costs ~2.5 min). Disabled in tests.
    if settings.preload_embedder:
        from app.embeddings import get_embedder

        get_embedder().embed_query("preload")
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
