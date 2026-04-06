# backend/app/schemas/email.py - MILESTONE 3 COMPLETE

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class EmailCampaignCreate(BaseModel):
    """Schema for creating an email campaign"""
    name: str = Field(..., min_length=1, max_length=200, description="Campaign name")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject")
    content: str = Field(..., description="Email content (HTML)")
    recipients: List[EmailStr] = Field(..., min_items=1, description="List of recipient emails")
    send_immediately: bool = Field(False, description="Send campaign immediately")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled send time")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Welcome Campaign",
                "subject": "Welcome to CallCenter Pro!",
                "content": "<h1>Welcome!</h1><p>Thank you for joining us.</p>",
                "recipients": ["user1@example.com", "user2@example.com"],
                "send_immediately": False,
                "scheduled_at": "2024-12-31T23:59:59"
            }
        }


class EmailCampaignUpdate(BaseModel):
    """Schema for updating an email campaign"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    recipients: Optional[List[EmailStr]] = None
    scheduled_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Campaign Name",
                "subject": "New Subject",
                "content": "<h1>Updated Content</h1>"
            }
        }


class EmailCampaignResponse(BaseModel):
    """Schema for email campaign response"""
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    subject: str
    content: str
    recipients: List[str]
    status: str
    send_immediately: bool
    scheduled_at: Optional[datetime] = None
    recipient_count: int
    sent_count: int
    delivered_count: int
    opened_count: int
    clicked_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class EmailTemplateCreate(BaseModel):
    """Schema for creating an email template"""
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject")
    content: str = Field(..., description="Email content (HTML)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Welcome Email Template",
                "subject": "Welcome to {{company_name}}!",
                "content": "<h1>Welcome {{user_name}}!</h1><p>We're glad to have you.</p>"
            }
        }


class EmailTemplateResponse(BaseModel):
    """Schema for email template response"""
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    subject: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class SendEmailRequest(BaseModel):
    """Schema for sending a single email"""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject")
    content: str = Field(..., description="Email content (HTML)")

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "customer@example.com",
                "subject": "Thank you for your call",
                "content": "<h1>Thank You!</h1><p>We appreciate your business.</p>"
            }
        }