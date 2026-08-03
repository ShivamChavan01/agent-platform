import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.llm import LLMClient, build_chat_messages, get_llm_client
from app.models import Conversation, Message, Project, User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
)
from app.services import get_owned_conversation, get_owned_project

router = APIRouter()


@router.post(
    "/projects/{project_id}/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    project_id: uuid.UUID,
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    get_owned_project(db, user, project_id)
    conversation = Conversation(project_id=project_id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    get_owned_project(db, user, project_id)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
        )
    )


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=ConversationDetailOut,
)
def get_conversation(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    messages = list(conversation.messages)
    return ConversationDetailOut(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=messages,
    )


@router.post("/projects/{project_id}/conversations/{conversation_id}/chat")
def chat(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> MessageOut:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    project = get_owned_project(db, user, project_id)

    history = list(conversation.messages)
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    messages = build_chat_messages(project.system_prompt or "", history, payload.message)
    try:
        reply_text = llm.complete(project.model, messages)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model service is unavailable, please try again later",
        )

    assistant_message = Message(
        conversation_id=conversation.id, role="assistant", content=reply_text
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return MessageOut.model_validate(assistant_message)
