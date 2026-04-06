# # backend/app/schemas/sms_campaign.py - NEW FILE

# from pydantic import BaseModel, Field, validator
# from typing import Optional, List
# from datetime import datetime
# import re


# class RecipientInput(BaseModel):
#     """Single recipient input"""
#     phone_number: str = Field(..., description="Phone number with country code")
#     name: Optional[str] = Field(None, description="Recipient name (optional)")
    
#     @validator('phone_number')
#     def validate_phone(cls, v):
#         """Validate phone number format"""
#         # Remove all non-digit characters except +
#         cleaned = re.sub(r'[^\d+]', '', v)
        
#         # Must start with + and have 10-15 digits
#         if not re.match(r'^\+\d{10,15}$', cleaned):
#             raise ValueError('Phone number must be in format +1234567890 (10-15 digits with country code)')
        
#         return cleaned


# class SMSCampaignCreateRequest(BaseModel):
#     """Schema for creating bulk SMS campaign"""
#     campaign_id: str = Field(..., min_length=1, max_length=100, description="Unique campaign identifier")
#     campaign_name: Optional[str] = Field(None, max_length=200, description="Campaign name")
#     message: str = Field(..., min_length=1, max_length=1600, description="SMS message content")
#     from_number: Optional[str] = Field(None, description="Sender phone number (optional)")
    
#     # Recipients - either manual list or will be added via CSV upload
#     recipients: List[RecipientInput] = Field(default=[], description="List of recipients")
    
#     # Settings
#     batch_size: int = Field(25, ge=1, le=100, description="Batch size for sending")
#     enable_replies: bool = Field(True, description="Enable AI replies to incoming messages")
#     track_responses: bool = Field(True, description="Track customer responses")
    
#     @validator('message')
#     def validate_message(cls, v):
#         """Validate message content"""
#         if not v.strip():
#             raise ValueError('Message cannot be empty')
        
#         # Warn if message is very long (will be sent as multiple SMS)
#         if len(v) > 160:
#             # This is fine, but user should know it counts as multiple SMS
#             pass
        
#         return v.strip()
    
#     @validator('campaign_id')
#     def validate_campaign_id(cls, v):
#         """Validate campaign ID format"""
#         # Only allow alphanumeric, hyphens, and underscores
#         if not re.match(r'^[a-zA-Z0-9_-]+$', v):
#             raise ValueError('Campaign ID can only contain letters, numbers, hyphens, and underscores')
        
#         return v


# class SMSCampaignCSVUploadRequest(BaseModel):
#     """Schema for CSV upload to existing campaign"""
#     campaign_id: str = Field(..., description="Campaign ID to add recipients to")


# class SMSCampaignResponse(BaseModel):
#     """Schema for campaign response"""
#     id: str = Field(..., alias="_id")
#     user_id: str
#     campaign_id: str
#     campaign_name: Optional[str]
#     message: str
#     from_number: str
#     total_recipients: int
#     sent_count: int
#     delivered_count: int
#     failed_count: int
#     status: str
#     created_at: datetime
#     started_at: Optional[datetime]
#     completed_at: Optional[datetime]
    
#     class Config:
#         populate_by_name = True


# class SMSCampaignDetailResponse(SMSCampaignResponse):
#     """Detailed campaign response with recipients"""
#     recipients: List[dict]
#     batch_size: int
#     current_batch: int
#     total_batches: int
#     errors: List[dict]


# class SMSCampaignStartRequest(BaseModel):
#     """Schema for starting a campaign"""
#     campaign_id: str = Field(..., description="Campaign ID to start")


# class SMSCampaignStatusResponse(BaseModel):
#     """Real-time campaign status"""
#     campaign_id: str
#     status: str
#     total_recipients: int
#     sent_count: int
#     delivered_count: int
#     failed_count: int
#     current_batch: int
#     total_batches: int
#     progress_percentage: float
#     estimated_time_remaining: Optional[int] = None  # seconds

# backend/app/schemas/sms_campaign.py - UPDATED WITH CUSTOM AI SCRIPT VALIDATION

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re


class RecipientInput(BaseModel):
    """Single recipient input"""
    phone_number: str = Field(..., description="Phone number with country code")
    name: Optional[str] = Field(None, description="Recipient name (optional)")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Validate phone number format"""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', v)
        
        # Must start with + and have 10-15 digits
        if not re.match(r'^\+\d{10,15}$', cleaned):
            raise ValueError('Phone number must be in format +1234567890 (10-15 digits with country code)')
        
        return cleaned


class SMSCampaignCreateRequest(BaseModel):
    """Schema for creating bulk SMS campaign"""
    campaign_id: str = Field(..., min_length=1, max_length=100, description="Unique campaign identifier")
    campaign_name: Optional[str] = Field(None, max_length=200, description="Campaign name")
    message: str = Field(..., min_length=1, max_length=1600, description="SMS message content")
    from_number: Optional[str] = Field(None, description="Sender phone number (optional)")
    
    # 🆕 CUSTOM AI SCRIPT
    custom_ai_script: Optional[str] = Field(
        None, 
        max_length=2000, 
        description="Custom AI system prompt for handling customer replies"
    )
    
    # Recipients - either manual list or will be added via CSV upload
    recipients: List[RecipientInput] = Field(default=[], description="List of recipients")
    
    # Settings
    batch_size: int = Field(25, ge=1, le=100, description="Batch size for sending")
    enable_replies: bool = Field(True, description="Enable AI replies to incoming messages")
    track_responses: bool = Field(True, description="Track customer responses")
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message content"""
        if not v.strip():
            raise ValueError('Message cannot be empty')
        
        # Warn if message is very long (will be sent as multiple SMS)
        if len(v) > 160:
            # This is fine, but user should know it counts as multiple SMS
            pass
        
        return v.strip()
    
    @validator('campaign_id')
    def validate_campaign_id(cls, v):
        """Validate campaign ID format"""
        # Only allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Campaign ID can only contain letters, numbers, hyphens, and underscores')
        
        return v
    
    @validator('custom_ai_script')
    def validate_custom_ai_script(cls, v):
        """Validate custom AI script"""
        if v is None:
            return v
        
        # Strip whitespace
        v = v.strip()
        
        # If empty after stripping, return None
        if not v:
            return None
        
        # Check for minimum length
        if len(v) < 10:
            raise ValueError('Custom AI script must be at least 10 characters if provided')
        
        # Check for malicious content patterns
        dangerous_patterns = [
            r'ignore\s+all\s+previous',
            r'disregard\s+instructions',
            r'system\s*:\s*you\s+are\s+now',
            r'<script>',
            r'javascript:',
            r'eval\s*\(',
        ]
        
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, v_lower):
                raise ValueError('Custom AI script contains potentially unsafe content')
        
        return v


class SMSCampaignCSVUploadRequest(BaseModel):
    """Schema for CSV upload to existing campaign"""
    campaign_id: str = Field(..., description="Campaign ID to add recipients to")


class SMSCampaignResponse(BaseModel):
    """Schema for campaign response"""
    id: str = Field(..., alias="_id")
    user_id: str
    campaign_id: str
    campaign_name: Optional[str]
    message: str
    from_number: str
    custom_ai_script: Optional[str] = None  # 🆕 Include in response
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        populate_by_name = True


class SMSCampaignDetailResponse(SMSCampaignResponse):
    """Detailed campaign response with recipients"""
    recipients: List[dict]
    batch_size: int
    current_batch: int
    total_batches: int
    errors: List[dict]


class SMSCampaignStartRequest(BaseModel):
    """Schema for starting a campaign"""
    campaign_id: str = Field(..., description="Campaign ID to start")


class SMSCampaignStatusResponse(BaseModel):
    """Real-time campaign status"""
    campaign_id: str
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    current_batch: int
    total_batches: int
    progress_percentage: float
    estimated_time_remaining: Optional[int] = None  # seconds