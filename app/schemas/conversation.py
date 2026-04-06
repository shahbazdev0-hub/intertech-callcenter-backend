# conversation.py
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class MessageSchema(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = None
    audio_url: Optional[str] = None


class ConversationCreate(BaseModel):
    call_id: str
    agent_id: Optional[str] = None
    context: Optional[Dict] = {}


class ConversationUpdate(BaseModel):
    is_active: Optional[bool] = None
    ended_at: Optional[datetime] = None


class ConversationResponse(BaseModel):
    id: str = Field(..., alias="_id")
    call_id: str
    user_id: str
    agent_id: Optional[str] = None
    messages: List[MessageSchema]
    context: Dict
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class AddMessageRequest(BaseModel):
    role: str
    content: str
    audio_url: Optional[str] = None