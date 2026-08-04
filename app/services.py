import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Conversation, Project, UsageEvent, User


def get_owned_project(db: Session, user: User, project_id: uuid.UUID) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_owned_conversation(
    db: Session, user: User, project_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .join(Project, Conversation.project_id == Project.id)
        .where(
            Conversation.id == conversation_id,
            Conversation.project_id == project_id,
            Project.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


def get_user_usage(db: Session, user_id: uuid.UUID, window_hours: int) -> dict:
    """Aggregate usage_events for a user over a rolling window (tokens only)."""
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    requests, prompt_tokens, completion_tokens, total_tokens = db.execute(
        select(
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UsageEvent.total_tokens), 0),
        ).where(UsageEvent.user_id == user_id, UsageEvent.created_at >= since)
    ).one()
    return {
        "requests": int(requests),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
    }
