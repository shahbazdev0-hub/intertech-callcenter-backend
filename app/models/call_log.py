# models/call_log.py
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from .base import PyObjectId
from bson import ObjectId


class CallLog(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "call_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "transcript": "Full conversation transcript...",
                "summary": "Customer inquired about pricing",
                "outcome": "successful",
                "sentiment": "positive",
                "keywords": ["pricing", "features", "demo"]
            }
        }
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    call_id: str
    user_id: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None  # successful, failed, no-answer, voicemail
    sentiment: Optional[str] = None  # positive, neutral, negative
    keywords: Optional[List[str]] = []
    ai_insights: Optional[Dict] = {}
    recording_duration: Optional[int] = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)