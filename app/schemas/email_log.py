# # backend/app/schemas/email_log.py - NEW FILE

# from pydantic import BaseModel, Field, EmailStr
# from typing import Optional, List
# from datetime import datetime


# class EmailLogResponse(BaseModel):
#     """Schema for email log response"""
#     id: str = Field(..., alias="_id")
#     user_id: str
#     to_email: EmailStr
#     from_email: EmailStr
#     subject: str
#     content: str
#     text_content: Optional[str] = None
#     recipient_name: Optional[str] = None
#     recipient_phone: Optional[str] = None
#     status: str
#     smtp_message_id: Optional[str] = None
#     error_message: Optional[str] = None
#     campaign_id: Optional[str] = None
#     automation_id: Optional[str] = None
#     call_id: Optional[str] = None
#     appointment_id: Optional[str] = None
#     opened_at: Optional[datetime] = None
#     opened_count: int = 0
#     clicked_at: Optional[datetime] = None
#     clicked_count: int = 0
#     clicked_links: List[str] = []
#     created_at: datetime
#     sent_at: Optional[datetime] = None
#     delivered_at: Optional[datetime] = None

#     class Config:
#         populate_by_name = True


# class EmailLogFilters(BaseModel):
#     """Schema for filtering email logs"""
#     status: Optional[str] = None
#     from_date: Optional[datetime] = None
#     to_date: Optional[datetime] = None
#     search: Optional[str] = None  # Search in subject, recipient, or content
#     has_opened: Optional[bool] = None
#     has_clicked: Optional[bool] = None

# backend/app/schemas/email_log.py - âœ… UPDATED WITH REPLY SCHEMA

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class EmailLogResponse(BaseModel):
    """Schema for email log response"""
    id: str = Field(..., alias="_id")
    user_id: str
    to_email: EmailStr
    from_email: EmailStr
    subject: str
    content: str
    text_content: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    status: str
    smtp_message_id: Optional[str] = None
    error_message: Optional[str] = None
    campaign_id: Optional[str] = None
    automation_id: Optional[str] = None
    call_id: Optional[str] = None
    appointment_id: Optional[str] = None
    opened_at: Optional[datetime] = None
    opened_count: int = 0
    clicked_at: Optional[datetime] = None
    clicked_count: int = 0
    clicked_links: List[str] = []
    has_reply: bool = False  # NEW
    reply_count: int = 0  # NEW
    last_replied_at: Optional[datetime] = None  # NEW
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class EmailLogFilters(BaseModel):
    """Schema for filtering email logs"""
    status: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    search: Optional[str] = None  # Search in subject, recipient, or content
    has_opened: Optional[bool] = None
    has_clicked: Optional[bool] = None


# âœ… NEW - EMAIL REPLY REQUEST SCHEMA
class EmailReplyRequest(BaseModel):
    """Schema for email reply request"""
    original_email_id: str = Field(..., description="ID of the original email to reply to")
    subject: Optional[str] = Field(None, description="Reply subject (will auto-add 'Re:' if not present)")
    content: str = Field(..., description="HTML content of the reply email")
    
    class Config:
        schema_extra = {
            "example": {
                "original_email_id": "507f1f77bcf86cd799439011",
                "subject": "Thank you for your appointment",
                "content": "<p>Dear Customer,</p><p>Thank you for scheduling an appointment with us...</p>"
            }
        }