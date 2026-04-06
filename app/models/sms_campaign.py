# # backend/app/models/sms_campaign.py - NEW FILE

# from datetime import datetime
# from typing import Optional, List, Dict, Any
# from pydantic import BaseModel, Field
# from bson import ObjectId


# class SMSCampaignRecipient(BaseModel):
#     """Individual recipient in a campaign"""
#     phone_number: str
#     name: Optional[str] = None
#     status: str = "pending"  # pending, sent, delivered, failed
#     twilio_sid: Optional[str] = None
#     error_message: Optional[str] = None
#     sent_at: Optional[datetime] = None
#     delivered_at: Optional[datetime] = None


# class SMSCampaign(BaseModel):
#     """Bulk SMS Campaign Model"""
#     id: Optional[str] = Field(None, alias="_id")
#     user_id: str
    
#     # Campaign details
#     campaign_id: str  # User-friendly campaign ID
#     campaign_name: Optional[str] = None
#     message: str
#     from_number: str
    
#     # Recipients
#     recipients: List[SMSCampaignRecipient] = []
#     total_recipients: int = 0
    
#     # Status tracking
#     status: str = "pending"  # pending, in_progress, completed, failed, cancelled
#     sent_count: int = 0
#     delivered_count: int = 0
#     failed_count: int = 0
    
#     # Upload source
#     upload_source: str = "manual"  # manual, csv, excel, document
#     uploaded_file_name: Optional[str] = None
    
#     # Batch processing
#     batch_size: int = 25
#     current_batch: int = 0
#     total_batches: int = 0
    
#     # Campaign settings
#     enable_replies: bool = True
#     track_responses: bool = True
    
#     # Timestamps
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     started_at: Optional[datetime] = None
#     completed_at: Optional[datetime] = None
#     updated_at: datetime = Field(default_factory=datetime.utcnow)
    
#     # Error tracking
#     errors: List[Dict[str, Any]] = []
    
#     class Config:
#         populate_by_name = True
#         json_encoders = {
#             ObjectId: str,
#             datetime: lambda v: v.isoformat()
#         }


# backend/app/models/sms_campaign.py - UPDATED WITH CUSTOM AI SCRIPT

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class SMSCampaignRecipient(BaseModel):
    """Individual recipient in a campaign"""
    phone_number: str
    name: Optional[str] = None
    status: str = "pending"  # pending, sent, delivered, failed
    twilio_sid: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class SMSCampaign(BaseModel):
    """Bulk SMS Campaign Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    
    # Campaign details
    campaign_id: str  # User-friendly campaign ID
    campaign_name: Optional[str] = None
    message: str
    from_number: str
    
    # 🆕 CUSTOM AI SCRIPT
    custom_ai_script: Optional[str] = None  # Custom system prompt for AI responses
    
    # Recipients
    recipients: List[SMSCampaignRecipient] = []
    total_recipients: int = 0
    
    # Status tracking
    status: str = "pending"  # pending, in_progress, completed, failed, cancelled
    sent_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    
    # Upload source
    upload_source: str = "manual"  # manual, csv, excel, document
    uploaded_file_name: Optional[str] = None
    
    # Batch processing
    batch_size: int = 25
    current_batch: int = 0
    total_batches: int = 0
    
    # Campaign settings
    enable_replies: bool = True
    track_responses: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Error tracking
    errors: List[Dict[str, Any]] = []
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }