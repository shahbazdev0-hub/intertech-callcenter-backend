# backend/app/schemas/email_campaign.py - Bulk Email Campaign Schemas

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re


class EmailRecipientInput(BaseModel):
    """Single email recipient input"""
    email: str = Field(..., description="Recipient email address")
    name: Optional[str] = Field(None, description="Recipient name (optional)")

    @validator('email')
    def validate_email(cls, v):
        """Validate email format"""
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email address format')
        return v


class EmailCampaignCreateRequest(BaseModel):
    """Schema for creating bulk email campaign"""
    campaign_id: str = Field(..., min_length=1, max_length=100, description="Unique campaign identifier")
    campaign_name: Optional[str] = Field(None, max_length=200, description="Campaign name")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject line")
    message: str = Field(..., min_length=1, max_length=50000, description="Email body content (HTML supported)")

    # Recipients - either manual list or will be added via CSV upload
    recipients: List[EmailRecipientInput] = Field(default=[], description="List of recipients")

    # Settings
    batch_size: int = Field(25, ge=1, le=100, description="Batch size for sending")

    @validator('subject')
    def validate_subject(cls, v):
        if not v.strip():
            raise ValueError('Subject cannot be empty')
        return v.strip()

    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()

    @validator('campaign_id')
    def validate_campaign_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Campaign ID can only contain letters, numbers, hyphens, and underscores')
        return v


class EmailCampaignResponse(BaseModel):
    """Schema for campaign response"""
    id: str = Field(..., alias="_id")
    user_id: str
    campaign_id: str
    campaign_name: Optional[str]
    subject: str
    message: str
    total_recipients: int
    sent_count: int
    failed_count: int
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        populate_by_name = True


class EmailCampaignDetailResponse(EmailCampaignResponse):
    """Detailed campaign response with recipients"""
    recipients: List[dict]
    batch_size: int
    current_batch: int
    total_batches: int
    errors: List[dict]


class EmailCampaignStartRequest(BaseModel):
    """Schema for starting a campaign"""
    campaign_id: str = Field(..., description="Campaign ID to start")


class EmailCampaignStatusResponse(BaseModel):
    """Real-time campaign status"""
    campaign_id: str
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    current_batch: int
    total_batches: int
    progress_percentage: float
