import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate, resolve_model

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_owned_project(db: Session, user: User, project_id: uuid.UUID) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        model=resolve_model(payload.model),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    return list(db.scalars(select(Project).where(Project.user_id == user.id).order_by(Project.created_at)))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    return _get_owned_project(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = _get_owned_project(db, user, project_id)
    updates = payload.model_dump(exclude_unset=True)
    if "model" in updates:
        updates["model"] = resolve_model(updates["model"])
    for field, value in updates.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    project = _get_owned_project(db, user, project_id)
    db.delete(project)
    db.commit()
