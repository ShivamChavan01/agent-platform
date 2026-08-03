import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Project, User


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
