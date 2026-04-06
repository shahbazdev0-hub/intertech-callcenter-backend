# backend/app/schemas/sms.py - MILESTONE 3 COMPLETE

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SMSSendRequest(BaseModel):
    """Schema for sending a single SMS"""
    to_number: str = Field(..., description="Recipient phone number")
    message: str = Field(..., max_length=160, description="SMS message content")
    from_number: Optional[str] = Field(None, description="Sender phone number (optional)")


class SMSBulkRequest(BaseModel):
    """Schema for sending bulk SMS"""
    to_numbers: List[str] = Field(..., description="List of recipient phone numbers")
    message: str = Field(..., max_length=160, description="SMS message content")
    from_number: Optional[str] = Field(None, description="Sender phone number (optional)")
    batch_size: int = Field(25, ge=1, le=100, description="Number of SMS to send per batch")


class SMSResponse(BaseModel):
    """Schema for SMS response"""
    id: str = Field(..., alias="_id")
    user_id: str
    to_number: str
    from_number: str
    message: str
    status: str
    direction: str
    twilio_sid: Optional[str] = None
    twilio_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "to_number": "+1234567890",
                "from_number": "+0987654321",
                "message": "Hello from CallCenter Pro!",
                "status": "sent",
                "direction": "outbound",
                "twilio_sid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "twilio_status": "delivered",
                "created_at": "2024-01-01T00:00:00",
                "sent_at": "2024-01-01T00:00:01"
            }
        }


class SMSStatsResponse(BaseModel):
    """Schema for SMS statistics"""
    total_sent: int = Field(0, description="Total SMS sent")
    total_failed: int = Field(0, description="Total SMS failed")
    total_pending: int = Field(0, description="Total SMS pending")
    today_sent: int = Field(0, description="SMS sent today")
    this_week_sent: int = Field(0, description="SMS sent this week")
    this_month_sent: int = Field(0, description="SMS sent this month")

    class Config:
        json_schema_extra = {
            "example": {
                "total_sent": 1500,
                "total_failed": 25,
                "total_pending": 10,
                "today_sent": 50,
                "this_week_sent": 300,
                "this_month_sent": 1200
            }
        }