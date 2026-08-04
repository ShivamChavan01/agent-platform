from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers import auth, conversations, files, projects


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
