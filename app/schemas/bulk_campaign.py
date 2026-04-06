# backend/app/schemas/bulk_campaign.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re

class RecipientInput(BaseModel):
    """Schema for manually adding recipients"""
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', v)
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        # Add + prefix if not present
        if not v.startswith('+'):
            return f'+{cleaned}'
        return v


class BulkCampaignCreate(BaseModel):
    """Schema for creating bulk campaign"""
    campaign_id: str = Field(..., min_length=3, max_length=100)
    campaign_name: Optional[str] = Field(None, max_length=200)
    custom_ai_script: Optional[str] = Field(None, max_length=2000)
    campaign_type: str = Field(default="call")
    
    @validator('campaign_id')
    def validate_campaign_id(cls, v):
        # Only allow alphanumeric, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Campaign ID can only contain letters, numbers, hyphens, and underscores')
        return v


class BulkCampaignUpdate(BaseModel):
    """Schema for updating campaign"""
    campaign_name: Optional[str] = None
    custom_ai_script: Optional[str] = None
    status: Optional[str] = None


class CSVUploadResponse(BaseModel):
    """Response after CSV upload"""
    success: bool
    total_uploaded: int
    valid_numbers: int
    invalid_numbers: int
    duplicate_numbers: int
    errors: List[str] = []


class ManualRecipientsAdd(BaseModel):
    """Schema for adding recipients manually"""
    recipients: List[RecipientInput] = Field(..., min_items=1, max_items=10)


class CampaignStartRequest(BaseModel):
    """Request to start campaign"""
    campaign_id: str
    max_concurrent_calls: Optional[int] = Field(default=1, ge=1, le=5)


class CampaignStatusResponse(BaseModel):
    """Campaign progress response"""
    campaign_id: str
    campaign_name: Optional[str]
    status: str
    total_recipients: int
    completed_calls: int
    successful_calls: int
    failed_calls: int
    appointments_booked: int
    progress_percentage: float
    current_recipient: Optional[str] = None
    estimated_completion: Optional[datetime] = None


class RecipientDetailResponse(BaseModel):
    """Detailed recipient call information"""
    phone_number: str
    name: Optional[str]
    call_status: str
    call_duration: Optional[int]
    appointment_booked: bool
    keywords_matched: List[str]
    conversation_summary: Optional[str]
    last_call_attempt: Optional[datetime]