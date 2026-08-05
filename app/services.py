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


def get_user_usage_window(
    db: Session, user_id: uuid.UUID, window_hours: int, cap_tokens: int
) -> dict:
    """Usage + cap math for one rolling window.

    `seconds_until_reset` is the time until the oldest event in the current
    window ages out (a rolling window "resets" continuously as tokens expire);
    an empty window reports the full window duration.
    """
    stats = get_user_usage(db, user_id, window_hours)
    now = datetime.now(timezone.utc)
    window_seconds = window_hours * 3600
    since = now - timedelta(hours=window_hours)
    oldest = db.scalar(
        select(func.min(UsageEvent.created_at)).where(
            UsageEvent.user_id == user_id, UsageEvent.created_at >= since
        )
    )
    if oldest is None:
        seconds_until_reset = window_seconds
    else:
        seconds_until_reset = max(
            0, int((oldest + timedelta(hours=window_hours) - now).total_seconds())
        )
    percent = (stats["total_tokens"] / cap_tokens * 100) if cap_tokens > 0 else 0.0
    return {
        "used_tokens": stats["total_tokens"],
        "requests": stats["requests"],
        "cap_tokens": cap_tokens,
        "percent": percent,
        "seconds_until_reset": seconds_until_reset,
    }


def get_usage_windows(db: Session, user_id: uuid.UUID) -> dict:
    """Session (5h) and weekly (7d) usage windows for the composer bars."""
    from app.config import settings

    return {
        "session": get_user_usage_window(
            db, user_id, settings.session_token_window_hours, settings.session_token_limit
        ),
        "weekly": get_user_usage_window(
            db, user_id, settings.weekly_token_window_hours, settings.weekly_token_limit
        ),
    }
