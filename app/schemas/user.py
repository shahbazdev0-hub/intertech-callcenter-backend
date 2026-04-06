# backend/app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    """Base user model with common fields"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, max_length=100)

class UserUpdate(BaseModel):
    """Schema for updating user information"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    
    # ✅ NEW - Allow updating notification preferences through user update
    notification_preferences: Optional[Dict[str, Any]] = None

class UserResponse(BaseModel):
    """Schema for user API responses"""
    id: str
    email: EmailStr
    username: str
    full_name: str
    company: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    subscription_plan: str
    role: str = "user"
    allowed_services: list = []
    twilio_phone_number: Optional[str] = None
    has_twilio_configured: bool = False

    notification_preferences: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "email_campaigns": True,
            "sms_alerts": False,
            "call_summaries": True,
            "weekly_reports": True,
            "security_alerts": True
        }
    )

    created_at: datetime
    last_login: Optional[datetime] = None

class UserInDBResponse(UserResponse):
    """Extended user response for internal use"""
    hashed_password: str

# ✅ NEW - Specific schemas for settings page functionality
class NotificationPreferences(BaseModel):
    """Schema for notification preferences"""
    email_campaigns: bool = True
    sms_alerts: bool = False
    call_summaries: bool = True
    weekly_reports: bool = True
    security_alerts: bool = True

class PasswordChangeRequest(BaseModel):
    """Schema for password change requests"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)

class EmailChangeRequest(BaseModel):
    """Schema for email change requests"""
    new_email: EmailStr
    current_password: str = Field(..., min_length=1)

class NotificationUpdateRequest(BaseModel):
    """Schema for updating notification preferences"""
    email_campaigns: Optional[bool] = None
    sms_alerts: Optional[bool] = None
    call_summaries: Optional[bool] = None
    weekly_reports: Optional[bool] = None
    security_alerts: Optional[bool] = None

    def dict_with_values_only(self) -> Dict[str, bool]:
        """Return only non-None values as dict"""
        return {k: v for k, v in self.dict().items() if v is not None}

# ✅ NEW - Response schemas for settings operations
class PasswordChangeResponse(BaseModel):
    """Response schema for password change"""
    message: str
    success: bool = True

class EmailChangeResponse(BaseModel):
    """Response schema for email change"""
    message: str
    new_email: EmailStr
    success: bool = True

class NotificationUpdateResponse(BaseModel):
    """Response schema for notification preference updates"""
    message: str
    preferences: Dict[str, Any]
    success: bool = True

# ✅ NEW - User profile update schema (more comprehensive)
class UserProfileUpdate(BaseModel):
    """Schema for comprehensive user profile updates"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    notification_preferences: Optional[NotificationPreferences] = None

    def dict_with_values_only(self) -> Dict[str, Any]:
        """Return only non-None values as dict"""
        result = {}
        for key, value in self.dict().items():
            if value is not None:
                if key == "notification_preferences" and isinstance(value, dict):
                    result[key] = value
                elif key != "notification_preferences":
                    result[key] = value
        return result