# backend/app/models/customer.py
"""
Customer Model - Stores customer information
"""

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class Customer(BaseModel):
    """Customer database model"""
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: Optional[str] = Field(default=None, alias="_id")
    
    # Basic information
    name: str
    email: EmailStr
    phone: str
    company: Optional[str] = None
    address: Optional[str] = None
    
    # Organization
    tags: List[str] = []
    notes: Optional[str] = None
    
    # Statistics (computed)
    total_appointments: int = 0
    total_calls: int = 0
    total_interactions: int = 0
    
    # Status
    status: str = "active"  # active, inactive, lead, converted
    
    # Owner
    user_id: str  # Business owner who owns this customer
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contact_at: Optional[datetime] = None