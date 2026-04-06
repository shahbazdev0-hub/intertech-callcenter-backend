# backend/app/models/sms.py

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class SMSMessage(BaseModel):
    """SMS Message Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    to_number: str
    from_number: str
    message: str
    status: str = "pending"  # pending, sent, delivered, failed
    direction: str = "outbound"  # outbound, inbound
    
    # Twilio data
    twilio_sid: Optional[str] = None
    twilio_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Metadata
    campaign_id: Optional[str] = None
    automation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class SMSTemplate(BaseModel):
    """SMS Template Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    content: str
    variables: list = []
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}