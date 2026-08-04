import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.embeddings import Embedder, get_embedder
from app.llm import LLMClient, build_chat_messages, get_llm_client
from app.models import Conversation, Message, Project, UsageEvent, User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
)
from app.services import get_owned_conversation, get_owned_project, get_user_usage
from app.tools import MAX_TOOL_TURNS, TOOLS, execute_tool

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
            .order_by(Conversation.pinned.desc(), Conversation.created_at.desc())
        )
    )


@router.patch(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=ConversationOut,
)
def update_conversation(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(conversation, field, value)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    db.delete(conversation)
    db.commit()


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
    embedder: Embedder = Depends(get_embedder),
) -> MessageOut:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    project = get_owned_project(db, user, project_id)

    history = list(conversation.messages)
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Tool loop: call the model, run any requested tools, feed results back,
    # and repeat until it replies with plain text or we hit MAX_TOOL_TURNS.
    # Identity grounding: models hallucinate their own vendor/version when the
    # system prompt doesn't state it, so append the configured model id.
    identity_hint = (
        f"\n\nPlatform note: you are served as the model '{project.model}' through "
        "this platform's configured LLM provider. If asked which model or vendor "
        "you are, answer truthfully with your configured model id; if you are "
        "unsure of your exact version, say so instead of guessing."
    )
    system = (project.system_prompt or "") + identity_hint
    messages = build_chat_messages(system, history, payload.message)
    for _ in range(MAX_TOOL_TURNS):
        try:
            response = llm.complete(project.model, messages, tools=TOOLS)
        except Exception as exc:
            logger.exception("LLM call failed for model %s", project.model)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"The model service is unavailable for '{project.model}', please try another model",
            ) from exc

        _record_usage(db, user, project, conversation, project.model, response)
        _enforce_usage_limit(db, user)

        tool_calls = response.tool_calls
        if not tool_calls:
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response.content or "",
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)
            return MessageOut.model_validate(assistant_message)

        calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
            }
            for tc in tool_calls
        ]
        _persist_assistant_turn(db, conversation.id, response.content or "", calls)
        messages.append({"role": "assistant", "content": response.content or None, "tool_calls": calls})

        for tc in tool_calls:
            arguments = tc.function.arguments or "{}"
            try:
                args = json.loads(arguments)
                if not isinstance(args, dict):
                    raise ValueError("tool arguments must be a JSON object")
                result = execute_tool(tc.function.name, args, db, project_id, embedder)
            except Exception as exc:
                result = f"Error: {exc}"
            _persist_tool_result(db, conversation.id, tc.id, tc.function.name, result, arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="The model did not finish responding after several tool rounds",
    )


def _persist_assistant_turn(db: Session, conversation_id: uuid.UUID, content: str, calls: list[dict]) -> None:
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tool_arguments=json.dumps(calls),
        )
    )
    db.commit()


def _persist_tool_result(
    db: Session, conversation_id: uuid.UUID, call_id: str, name: str, result: str, arguments_json: str
) -> None:
    db.add(
        Message(
            conversation_id=conversation_id,
            role="tool",
            content=str(result),
            tool_call_id=call_id,
            tool_name=name,
            tool_arguments=arguments_json,
        )
    )
    db.commit()


def _record_usage(
    db: Session, user: User, project: Project, conversation: Conversation, model: str, response: Any
) -> None:
    """Best-effort: one usage_events row per model response (metering must never break chat)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    try:
        db.add(
            UsageEvent(
                user_id=user.id,
                project_id=project.id,
                conversation_id=conversation.id,
                model=model,
                prompt_tokens=int(usage.prompt_tokens or 0),
                completion_tokens=int(usage.completion_tokens or 0),
                total_tokens=int(usage.total_tokens or 0),
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _enforce_usage_limit(db: Session, user: User) -> None:
    limit = settings.usage_daily_token_limit
    if limit <= 0:
        return
    stats = get_user_usage(db, user.id, settings.usage_window_hours)
    if stats["total_tokens"] >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily token usage limit reached, please try again later",
        )
