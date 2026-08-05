from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Conversation, Project, ProjectFile, User
from app.schemas import (
    PreferencesUpdate,
    TokenOut,
    UsageOut,
    UserLogin,
    UserOut,
    UserRegister,
    UserUpdate,
)
from app.security import create_access_token, hash_password, verify_password
from app.services import get_usage_windows, get_user_usage
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenOut:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(user)

    token = create_access_token(str(user.id))
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    token = create_access_token(str(user.id))
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(
    user: User = Depends(get_current_user),
) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/preferences")
def get_preferences(
    user: User = Depends(get_current_user),
) -> dict:
    return user.preferences or {}


@router.patch("/me/preferences", response_model=dict)
def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user.preferences = {**(user.preferences or {}), **payload.model_dump(exclude_unset=True)}
    db.commit()
    db.refresh(user)
    return user.preferences


@router.delete("/me/conversations")
def clear_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    conversations = db.scalars(
        select(Conversation)
        .join(Project, Conversation.project_id == Project.id)
        .where(Project.user_id == user.id)
    ).all()
    count = len(conversations)
    for conversation in conversations:
        db.delete(conversation)
    db.commit()
    return {"deleted": count}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> None:
    paths = list(
        db.scalars(select(ProjectFile.storage_path).where(ProjectFile.user_id == user.id))
    )
    db.delete(user)
    db.commit()
    for path in paths:
        try:
            storage.delete(path)
        except Exception:
            pass


@router.get("/me/usage", response_model=UsageOut)
def get_usage(
    window_hours: int = Query(default=settings.usage_window_hours, ge=1, le=720),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageOut:
    stats = get_user_usage(db, user.id, window_hours)
    windows = get_usage_windows(db, user.id)
    return UsageOut(**stats, window_hours=window_hours, **windows)