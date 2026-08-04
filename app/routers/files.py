import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.embeddings import Embedder, get_embedder
from app.models import FileChunk, Project, ProjectFile, User
from app.rag import MAX_UPLOAD_BYTES, chunk_text, embed_chunks, extract_text
from app.schemas import FileOut
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/projects", tags=["files"])


def _get_owned_project(db: Session, user: User, project_id: uuid.UUID) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _read_upload(file: UploadFile) -> bytes:
    data = bytearray()
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds the 10MB size limit",
            )
    return bytes(data)


@router.post("/{project_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
def upload_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    storage: StorageBackend = Depends(get_storage),
) -> ProjectFile:
    _get_owned_project(db, user, project_id)  # 404 if not owned

    data = _read_upload(file)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    try:
        content = extract_text(file.filename or "", data)
    except HTTPException:
        raise
    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text found in the file",
        )

    filename = file.filename or "file.bin"
    db_file = ProjectFile(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=user.id,
        original_filename=filename,
        mime_type=file.content_type,
        size_bytes=len(data),
        storage_path="",
        chunk_count=0,
    )
    db_file.storage_path = f"{project_id}/{db_file.id}/{filename}"
    db.add(db_file)
    db.flush()

    try:
        storage.upload(db_file.storage_path, data, file.content_type)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="File storage unavailable"
        )

    try:
        chunks = chunk_text(content)
        vectors = embed_chunks(embedder, chunks)
        for index, (text, vector) in enumerate(zip(chunks, vectors)):
            db.add(
                FileChunk(
                    file_id=db_file.id,
                    project_id=project_id,
                    chunk_index=index,
                    content=text,
                    embedding=vector,
                )
            )
        db_file.chunk_count = len(chunks)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Embedding generation failed"
        ) from exc

    db.refresh(db_file)
    return db_file


@router.get("/{project_id}/files", response_model=list[FileOut])
def list_files(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectFile]:
    _get_owned_project(db, user, project_id)
    return list(
        db.scalars(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at)
        )
    )