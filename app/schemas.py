import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.config import settings


# ---------- Auth ----------


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Projects ----------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = Field(default=None, max_length=255)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = Field(default=None, max_length=255)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str | None
    model: str
    created_at: datetime
    updated_at: datetime


def resolve_model(model: str | None, user: Any = None) -> str:
    """Precedence: request model -> user's default_model preference -> global default."""
    if model:
        return model
    prefs = getattr(user, "preferences", None) or {}
    return prefs.get("default_model") or settings.default_model


# ---------- Preferences / Usage ----------


class PreferencesUpdate(BaseModel):
    default_model: str | None = Field(default=None, max_length=255)
    context_window: int | None = Field(default=None, ge=1, le=512)


class UsageOut(BaseModel):
    requests: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    window_hours: int


# ---------- Conversations / Messages / Chat ----------


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    pinned: bool | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    # Populated only for tool exchanges (Step 6, Part B)
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments: str | None = None
    # Streamed reasoning persisted so the thinking block survives reload
    reasoning: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str | None
    pinned: bool = False
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class AttachmentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_b64: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    attachments: list[AttachmentIn] | None = None


# ---------- Files ----------


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_filename: str
    storage_path: str
    mime_type: str | None
    size_bytes: int
    chunk_count: int
    created_at: datetime
