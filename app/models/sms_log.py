# backend/app/models/sms_log.py - NEW FILE

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class SMSLog(BaseModel):
    """SMS Log Model - Complete history of all SMS messages"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    
    # Message details
    to_number: str
    from_number: str
    message: str
    direction: str  # outbound, inbound
    
    # Status tracking
    status: str  # pending, sent, delivered, failed, received
    twilio_sid: Optional[str] = None
    twilio_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Context
    call_id: Optional[str] = None  # If sent during a call
    campaign_id: Optional[str] = None  # If part of a campaign
    automation_id: Optional[str] = None  # If triggered by automation
    
    # Reply tracking
    is_reply: bool = False
    reply_to_sms_id: Optional[str] = None
    has_replies: bool = False
    reply_count: int = 0
    
    # Customer info
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    
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