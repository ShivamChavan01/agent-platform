"""Object storage boundary (Supabase Storage in prod, local dir fallback in dev)."""

from pathlib import Path
from typing import Protocol

from app.config import settings


class StorageBackend(Protocol):
    def upload(self, path: str, data: bytes, content_type: str | None = None) -> None: ...


class SupabaseStorage:
    def __init__(
        self,
        url: str | None = None,
        service_role_key: str | None = None,
        bucket: str | None = None,
    ) -> None:
        self._url = url or settings.supabase_url
        self._key = service_role_key or settings.supabase_service_role_key
        self._bucket = bucket or settings.supabase_storage_bucket
        self._client = None

    def _get_client(self):
        if self._client is None:
            from supabase import create_client

            self._client = create_client(self._url, self._key)
        return self._client

    def upload(self, path: str, data: bytes, content_type: str | None = None) -> None:
        options = {"content-type": content_type} if content_type else None
        self._get_client().storage.from_(self._bucket).upload(
            path, data, file_options=options
        )


class LocalStorage:
    """Filesystem fallback so dev/tests don't need Supabase. Path: storage/<path>."""

    def __init__(self, base_dir: str = "storage") -> None:
        self._base = Path(base_dir)

    def upload(self, path: str, data: bytes, content_type: str | None = None) -> None:
        dest = self._base / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def get_storage() -> StorageBackend:
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseStorage()
    return LocalStorage()