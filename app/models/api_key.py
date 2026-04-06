# backend/app/models/api_key.py
"""
API Key Model - Stores API keys for external integrations
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class APIKey(BaseModel):
    """API Key database model"""
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: Optional[str] = Field(default=None, alias="_id")
    
    # Key information
    name: str  # Friendly name for the key
    key: str  # The actual API key (hashed)
    key_prefix: str  # First 8 chars for identification (e.g., "ck_live_")
    
    # Owner
    user_id: str  # User who created this key
    
    # Permissions
    permissions: List[str] = ["read"]  # read, write, delete
    
    # Scopes - what resources can be accessed
    scopes: List[str] = ["customers", "appointments"]
    
    # Rate limiting
    rate_limit: int = 1000  # Requests per hour
    
    # Status
    is_active: bool = True
    
    # Usage tracking
    last_used_at: Optional[datetime] = None
    total_requests: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # None = never expires
    revoked_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }