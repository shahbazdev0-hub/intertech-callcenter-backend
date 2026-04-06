# backend/app/schemas/api_key.py
"""
API Key Pydantic Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class APIKeyCreate(BaseModel):
    """Schema for creating an API key"""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = ["read"]
    scopes: List[str] = ["customers", "appointments"]
    rate_limit: int = Field(default=1000, ge=100, le=10000)
    expires_in_days: Optional[int] = None  # None = never expires


class APIKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)"""
    id: str
    name: str
    key_prefix: str
    permissions: List[str]
    scopes: List[str]
    rate_limit: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    total_requests: int = 0
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Schema for newly created API key (includes the actual key - only shown once)"""
    id: str
    name: str
    key: str  # The actual key - only returned on creation
    key_prefix: str
    permissions: List[str]
    scopes: List[str]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    message: str = "Save this key securely. It won't be shown again."


class APIKeyListResponse(BaseModel):
    """Schema for list of API keys"""
    api_keys: List[APIKeyResponse]
    total: int