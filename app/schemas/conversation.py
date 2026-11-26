from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import AgentChatRequest


class ConversationCreated(BaseModel):
    conversation_id: UUID


class ConversationSummary(ConversationCreated):
    created_at: str


class Message(BaseModel):
    role: str
    content: str


class MessagesResponse(ConversationCreated):
    messages: list[Message]


class ConversationReplyRequest(AgentChatRequest):
    pass


class ConversationReplyResponse(ConversationCreated):
    answer: str
    model: str
    tools_used: list[str]
    context_messages: int


class MemoryCreate(BaseModel):
    fact: str = Field(
        min_length=3,
        max_length=300,
    )


class MemoryItem(MemoryCreate):
    memory_id: UUID