import json
import logging
import uuid
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.embeddings import Embedder, get_embedder
from app.llm import LLMClient, build_chat_messages, get_llm_client
from app.models import Conversation, Message, UsageEvent, User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
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
) -> StreamingResponse:
    """Stream the reply as Server-Sent Events (text/event-stream).

    Events (JSON in each `data:` line): `thinking` (live reasoning delta),
    `content` (answer delta, only on the final non-tool turn), `tool` (live
    tool-call progress), `done` (message_id/content/model/provider/usage) and
    `error` (in-band failure — the stream container itself stays HTTP 200 so
    errors after the first byte can still be reported).
    """
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    project = get_owned_project(db, user, project_id)
    _enforce_usage_limit(db, user)

    # Capture plain primitives up front: the SSE generator below runs in a
    # worker thread, and touching ORM attributes (which expire on commit)
    # from that thread raises DetachedInstanceError.
    cid = conversation.id
    pid = project.id
    uid = user.id
    model = project.model

    history = list(conversation.messages)
    user_message = Message(conversation_id=cid, role="user", content=payload.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Identity grounding: models hallucinate their own vendor/version when the
    # system prompt doesn't state it, so append the configured model id.
    identity_hint = (
        f"\n\nPlatform note: you are served as the model '{model}' through "
        "this platform's configured LLM provider. If asked which model or vendor "
        "you are, answer truthfully with your configured model id; if you are "
        "unsure of your exact version, say so instead of guessing."
    )
    system = (project.system_prompt or "") + identity_hint
    messages = build_chat_messages(system, history, payload.message)

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def generate() -> Iterator[str]:
        for _ in range(MAX_TOOL_TURNS):
            try:
                result: dict | None = None
                content_parts: list[str] = []
                reasoning_parts: list[str] = []
                for ev in llm.stream(model, messages, tools=TOOLS):
                    if ev["type"] == "provider":
                        yield sse(
                            {
                                "event": "provider",
                                "provider": ev["provider"],
                                "model": ev["model"],
                            }
                        )
                    elif ev["type"] == "thinking":
                        reasoning_parts.append(ev["text"])
                        yield sse({"event": "thinking", "delta": ev["text"]})
                    elif ev["type"] == "content":
                        content_parts.append(ev["text"])
                    elif ev["type"] == "tool":
                        yield sse(
                            {
                                "event": "tool",
                                "id": ev["id"],
                                "name": ev["name"],
                                "arguments": ev["arguments"],
                            }
                        )
                    elif ev["type"] == "result":
                        result = ev
            except Exception as exc:
                logger.exception("LLM call failed for model %s", model)
                yield sse(
                    {
                        "event": "error",
                        "error": f"The model service is unavailable for '{model}', please try another model",
                    }
                )
                return
            if result is None:
                continue

            _record_usage(db, uid, pid, cid, result["model"], result.get("usage"))
            try:
                _enforce_usage_limit(db, user)
            except HTTPException as exc:
                yield sse({"event": "error", "error": exc.detail})
                return

            tool_calls = result.get("tool_calls")
            if not tool_calls:
                final_content = "".join(content_parts)
                reasoning = "".join(reasoning_parts) or None
                for part in content_parts:
                    yield sse({"event": "content", "delta": part})
                assistant_message_id = uuid.uuid4()
                db.add(
                    Message(
                        id=assistant_message_id,
                        conversation_id=cid,
                        role="assistant",
                        content=final_content,
                        reasoning=reasoning,
                    )
                )
                db.commit()
                usage = result.get("usage")
                yield sse(
                    {
                        "event": "done",
                        "message_id": str(assistant_message_id),
                        "content": final_content,
                        "reasoning": reasoning,
                        "model": result["model"],
                        "provider": result["provider"],
                        "usage": (
                            {
                                "prompt_tokens": usage.prompt_tokens,
                                "completion_tokens": usage.completion_tokens,
                                "total_tokens": usage.total_tokens,
                            }
                            if usage is not None
                            else None
                        ),
                    }
                )
                return

            _persist_assistant_turn(
                db, cid, "".join(content_parts), tool_calls, "".join(reasoning_parts) or None
            )
            messages.append(
                {"role": "assistant", "content": "".join(content_parts) or None, "tool_calls": tool_calls}
            )

            for tc in tool_calls:
                arguments = tc["function"].get("arguments") or "{}"
                try:
                    args = json.loads(arguments)
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                    result_text = execute_tool(
                        tc["function"]["name"], args, db, project_id, embedder
                    )
                except Exception as exc:
                    result_text = f"Error: {exc}"
                _persist_tool_result(
                    db, cid, tc["id"], tc["function"]["name"], result_text, arguments
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": str(result_text)}
                )

        yield sse(
            {
                "event": "error",
                "error": "The model did not finish responding after several tool rounds",
            }
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


def _persist_assistant_turn(
    db: Session,
    conversation_id: uuid.UUID,
    content: str,
    calls: list[dict],
    reasoning: str | None = None,
) -> None:
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tool_arguments=json.dumps(calls),
            reasoning=reasoning,
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
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    model: str,
    usage: Any,
) -> None:
    """Best-effort: one usage_events row per model response (metering must never break chat)."""
    if usage is None:
        return
    try:
        db.add(
            UsageEvent(
                user_id=user_id,
                project_id=project_id,
                conversation_id=conversation_id,
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
