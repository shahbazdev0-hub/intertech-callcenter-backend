# backend/app/models/email_log.py - NEW FILE

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class EmailLog(BaseModel):
    """Email Log Model - Complete history of all emails"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    
    # Email details
    to_email: EmailStr
    from_email: EmailStr
    subject: str
    content: str  # HTML content
    text_content: Optional[str] = None  # Plain text version
    
    # Recipient info
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    
    # Status tracking
    status: str  # pending, sent, delivered, opened, clicked, failed
    smtp_message_id: Optional[str] = None
    error_message: Optional[str] = None
    
    # Context
    campaign_id: Optional[str] = None  # If part of a campaign
    automation_id: Optional[str] = None  # If triggered by automation
    call_id: Optional[str] = None  # If sent after a call
    appointment_id: Optional[str] = None  # If appointment confirmation
    
    # Engagement tracking
    opened_at: Optional[datetime] = None
    opened_count: int = 0
    clicked_at: Optional[datetime] = None
    clicked_count: int = 0
    clicked_links: List[str] = []
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }