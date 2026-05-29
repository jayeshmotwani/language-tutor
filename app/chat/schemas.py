from datetime import datetime

from pydantic import BaseModel


class ChatSessionCreate(BaseModel):
    language: str


class ChatSessionSummary(BaseModel):
    id: str
    language: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetail(BaseModel):
    id: str
    language: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]

    model_config = {"from_attributes": True}
