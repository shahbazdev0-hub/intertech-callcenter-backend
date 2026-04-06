# backend/app/schemas/sms_log.py - NEW FILE

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SMSLogResponse(BaseModel):
    """Schema for SMS log response"""
    id: str = Field(..., alias="_id")
    user_id: str
    to_number: str
    from_number: str
    message: str
    direction: str
    status: str
    twilio_sid: Optional[str] = None
    twilio_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    call_id: Optional[str] = None
    campaign_id: Optional[str] = None
    automation_id: Optional[str] = None
    is_reply: bool = False
    reply_to_sms_id: Optional[str] = None
    has_replies: bool = False
    reply_count: int = 0
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class SMSReplyRequest(BaseModel):
    """Schema for replying to an SMS"""
    to_number: str
    message: str = Field(..., max_length=160)
    original_sms_id: str  # ID of the SMS being replied to


class SMSLogFilters(BaseModel):
    """Schema for filtering SMS logs"""
    status: Optional[str] = None
    direction: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    search: Optional[str] = None  # Search in message or phone number