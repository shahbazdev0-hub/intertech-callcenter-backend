# backend/app/models/email_campaign.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class EmailCampaign(BaseModel):
    """Email Campaign Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    subject: str
    content: str
    template_id: Optional[str] = None
    
    # Recipients
    recipients: List[EmailStr] = []
    recipient_count: int = 0
    
    # Status
    status: str = "draft"  # draft, scheduled, sending, sent, cancelled
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    send_immediately: bool = False
    
    # Stats
    sent_count: int = 0
    delivered_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0
    failed_count: int = 0
    
    # Settings
    send_rate_limit: int = 10  # emails per second
    batch_size: int = 50
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class EmailTemplate(BaseModel):
    """Email Template Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    subject: str
    html_content: str
    text_content: Optional[str] = None
    variables: List[str] = []
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}