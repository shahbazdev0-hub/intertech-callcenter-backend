# backend/app/schemas/appointment.py - NEW FILE
"""
Appointment Pydantic Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class AppointmentCreate(BaseModel):
    """Schema for creating appointment"""
    customer_name: str = Field(..., min_length=2, max_length=100)
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = Field(None, max_length=20)
    appointment_date: datetime
    appointment_time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    service_type: Optional[str] = None
    cost: Optional[float] = None
    duration_minutes: Optional[int] = 60
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """Schema for updating appointment"""
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    appointment_date: Optional[datetime] = None
    appointment_time: Optional[str] = None
    service_type: Optional[str] = None
    cost: Optional[float] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Schema for appointment response"""
    id: str
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    appointment_date: datetime
    appointment_time: str
    service_type: Optional[str] = None
    notes: Optional[str] = None
    status: str
    google_calendar_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class AvailabilityRequest(BaseModel):
    """Schema for checking availability"""
    date: datetime
    duration_minutes: int = 60


class AvailabilityResponse(BaseModel):
    """Schema for availability response"""
    date: str
    available_slots: list[str]  # ["09:00", "10:00", "14:00"]