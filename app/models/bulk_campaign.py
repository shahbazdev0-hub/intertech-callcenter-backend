#  backend/app/models/bulk_campaign.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

class BulkCampaign(BaseModel):
    """Bulk SMS/Call Campaign Model"""
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    campaign_id: str
    campaign_name: Optional[str] = None
    campaign_type: str = "call"
    custom_ai_script: Optional[str] = None
    
    # Campaign settings
    total_recipients: int = 0
    completed_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    appointments_booked: int = 0
    
    # Status tracking
    status: str = "draft"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        # ✅ FIXED: Changed from schema_extra to json_schema_extra for Pydantic v2
        json_schema_extra = {
            "example": {
                "campaign_id": "bulk-campaign-001",
                "campaign_name": "Summer Promotion 2024",
                "custom_ai_script": "You are a friendly sales rep..."
            }
        }


class CampaignRecipient(BaseModel):
    """Individual recipient in a bulk campaign"""
    id: Optional[str] = Field(default=None, alias="_id")
    campaign_id: str
    user_id: str
    
    # Recipient info
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    
    # Call status
    call_status: str = "pending"
    call_attempts: int = 0
    last_call_attempt: Optional[datetime] = None
    
    # Call outcome
    call_sid: Optional[str] = None
    call_duration: Optional[int] = None
    appointment_booked: bool = False
    appointment_id: Optional[str] = None
    keywords_matched: List[str] = []
    conversation_summary: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "name": "John Doe",
                "email": "john@example.com"
            }
        }


class CampaignCallLog(BaseModel):
    """Detailed log for each call attempt"""
    id: Optional[str] = Field(default=None, alias="_id")
    campaign_id: str
    recipient_id: str
    user_id: str
    
    # Call details
    call_sid: str
    phone_number: str
    call_status: str
    call_direction: str = "outbound-api"
    
    # Call outcome
    outcome: Optional[str] = None
    duration: Optional[int] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    
    # AI behavior tracking
    custom_script_used: bool = False
    appointment_flow_triggered: bool = False
    campaign_keywords_matched: List[str] = []
    openai_fallback_used: bool = False
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "phone_number": "+1234567890",
                "call_status": "completed"
            }
        }
