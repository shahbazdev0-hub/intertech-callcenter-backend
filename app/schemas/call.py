# backend/app/schemas/call.py - ✅ COMPLETE & FIXED

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class CallCreate(BaseModel):
    """Schema for creating a new call - matches frontend"""
    phone_number: str = Field(..., description="Customer phone number to call")
    agent_id: Optional[str] = Field(None, description="Voice agent ID (optional)")
    direction: str = Field(default="outbound", description="Call direction")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if not v or len(v.strip()) < 10:
            raise ValueError('Phone number must be at least 10 characters')
        return v.strip()
    
    @validator('direction')
    def validate_direction(cls, v):
        """Validate direction"""
        if v not in ['inbound', 'outbound']:
            raise ValueError('Direction must be either "inbound" or "outbound"')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "+14155551234",
                "agent_id": "507f1f77bcf86cd799439011",
                "direction": "outbound"
            }
        }


class CallUpdate(BaseModel):
    """Schema for updating a call"""
    status: Optional[str] = None
    duration: Optional[int] = None
    ended_at: Optional[datetime] = None
    recording_url: Optional[str] = None
    recording_sid: Optional[str] = None
    recording_duration: Optional[int] = None
    outcome: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "duration": 120,
                "outcome": "successful"
            }
        }


class CallResponse(BaseModel):
    """Schema for call API responses"""
    id: str = Field(..., alias="_id")
    user_id: str
    phone_number: str
    agent_id: Optional[str] = None
    direction: str
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    status: str
    duration: Optional[int] = 0
    outcome: Optional[str] = None
    twilio_call_sid: Optional[str] = None
    call_sid: Optional[str] = None
    recording_url: Optional[str] = None
    recording_sid: Optional[str] = None
    recording_duration: Optional[int] = 0
    local_recording_path: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "phone_number": "+14155551234",
                "direction": "outbound",
                "from_number": "+14388177856",
                "to_number": "+14155551234",
                "status": "completed",
                "duration": 120,
                "twilio_call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "recording_url": "https://api.twilio.com/recordings/RExxxx",
                "created_at": "2024-01-01T12:00:00"
            }
        }


class CallStatsResponse(BaseModel):
    """Schema for call statistics"""
    total_calls: int
    completed_calls: int
    failed_calls: int
    average_duration: float
    total_duration: int
    success_rate: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "total_calls": 150,
                "completed_calls": 120,
                "failed_calls": 30,
                "average_duration": 180,
                "total_duration": 21600,
                "success_rate": 80.0
            }
        }