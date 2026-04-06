# backend/app/schemas/customer.py
"""
Customer Pydantic Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class CustomerCreate(BaseModel):
    """Schema for creating a customer"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    company: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    tags: List[str] = []
    notes: Optional[str] = None
    role: Optional[str] = None  # None = normal customer, "sales_manager", "viewer"
    password: Optional[str] = None  # Required when role is set
    allowed_services: List[str] = []


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    company: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    allowed_services: Optional[List[str]] = None


class CustomerResponse(BaseModel):
    """Schema for customer response"""
    id: str
    name: str
    email: EmailStr
    phone: str
    company: Optional[str] = None
    address: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None
    total_appointments: int = 0
    total_calls: int = 0
    total_interactions: int = 0
    status: str = "active"
    user_id: str
    role: Optional[str] = None
    allowed_services: List[str] = []
    created_at: datetime
    updated_at: datetime
    last_contact_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """Schema for paginated customer list"""
    customers: List[CustomerResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CustomerStatsResponse(BaseModel):
    """Schema for customer statistics"""
    total_customers: int = 0
    new_this_month: int = 0
    active_customers: int = 0
    total_appointments: int = 0
    upcoming_appointments: int = 0
    completed_appointments: int = 0
    total_interactions: int = 0
    avg_interactions: float = 0


class AddNoteRequest(BaseModel):
    """Schema for adding a note"""
    note: str = Field(..., min_length=1, max_length=1000)


class AddTagsRequest(BaseModel):
    """Schema for adding tags"""
    tags: List[str]


class TimelineItem(BaseModel):
    """Schema for timeline item"""
    id: str
    type: str  # call, appointment, note, sms, email
    title: str
    description: Optional[str] = None
    timestamp: datetime
    metadata: Optional[dict] = None