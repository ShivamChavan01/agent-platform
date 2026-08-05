import base64
import json
import logging
import re
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
from app.rag import extract_text
from app.schemas import (
    AttachmentIn,
    ChatRequest,
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
)
from app.services import get_owned_conversation, get_owned_project, get_user_usage
from app.tools import MAX_TOOL_TURNS, TOOLS, execute_tool

router = APIRouter()

MAX_ATTACHMENT_TEXT = 40_000


def _attachment_text(att: AttachmentIn) -> str:
    """Extract readable text from a message-scoped attachment.

    PDFs and DOCX are parsed like uploads (see app.rag.extract_text);
    plain-text/code files are decoded as UTF-8. Raw binary is never injected
    into the model context — on any failure the caller gets an honest note
    the model can report instead of garbage bytes.
    """
    try:
        raw = base64.b64decode(att.content_b64)
    except Exception as exc:
        return f"(could not read {att.filename}: invalid base64 — {exc})"
    try:
        text = extract_text(att.filename, raw)
    except HTTPException as exc:
        return f"(could not read {att.filename}: {exc.detail})"
    except Exception as exc:
        return f"(could not read {att.filename}: {exc})"
    if len(text) > MAX_ATTACHMENT_TEXT:
        text = text[:MAX_ATTACHMENT_TEXT]
        text += f"\n[File text truncated — showing the first {MAX_ATTACHMENT_TEXT} characters]"
    return text


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
    artifact_guidance = (
        "\n\nOutput style: write prose in clean markdown (use **bold**, ## headings, "
        "- lists, and tables where they help). Whenever you produce code — a script, "
        "a component, a config, or especially a self-contained UI/HTML file — put it "
        "in a fenced code block with a language tag (```html, ```python, ```js, etc.). "
        "For single-file apps or UI previews, provide a complete, runnable HTML file "
        "in one fenced ```html block. These blocks are rendered in a side panel with "
        "a live preview, so keep each file self-contained. Plain text only — no emojis, "
        "no decorative symbols, anywhere in your responses."
    )
    system = (project.system_prompt or "") + identity_hint + artifact_guidance

    # Inject message-scoped attachments as context (not stored, not embedded)
    user_content = payload.message
    if payload.attachments:
        parts = []
        for att in payload.attachments:
            parts.append(f"--- File: {att.filename} ---\n{_attachment_text(att)}\n--- End: {att.filename} ---")
        file_context = "\n\n".join(parts)
        user_content = f"{file_context}\n\n{user_content}"

    messages = build_chat_messages(system, history, user_content)

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
                final_content = strip_emoji("".join(content_parts))
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
                db, cid, strip_emoji("".join(content_parts)), tool_calls, "".join(reasoning_parts) or None
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


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF"
    "\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000FE0E\U000020E3\U000000A9\U000000AE"
    "\U00002122\U00003030\U0000303D]"
)


def strip_emoji(text: str) -> str:
    """Remove emoji and decorative symbols so assistant replies stay plain text."""
    return _EMOJI_RE.sub("", text)


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
