# # backend/app/schemas/__init__.py - UPDATED
# """
# Pydantic Schemas Package
# """

# from .user import UserCreate, UserUpdate, UserResponse
# from .auth import Token, TokenData, UserLogin, PasswordReset, PasswordResetConfirm, EmailVerification
# from .demo import DemoBookingCreate, DemoBookingResponse
# from .appointment import (  # ✅ NEW
#     AppointmentCreate,
#     AppointmentUpdate,
#     AppointmentResponse,
#     AvailabilityRequest,
#     AvailabilityResponse
# )

# __all__ = [
#     "UserCreate",
#     "UserUpdate", 
#     "UserResponse",
#     "Token",
#     "TokenData",
#     "UserLogin",
#     "PasswordReset",
#     "PasswordResetConfirm",
#     "EmailVerification",
#     "DemoBookingCreate",
#     "DemoBookingResponse",
#     # ✅ NEW
#     "AppointmentCreate",
#     "AppointmentUpdate",
#     "AppointmentResponse",
#     "AvailabilityRequest",
#     "AvailabilityResponse",
# ]

# backend/app/schemas/__init__.py - UPDATED
"""
Pydantic Schemas Package
"""

from .user import UserCreate, UserUpdate, UserResponse
from .auth import Token, TokenData, UserLogin, PasswordReset, PasswordResetConfirm, EmailVerification
from .demo import DemoBookingCreate, DemoBookingResponse
from .appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AvailabilityRequest,
    AvailabilityResponse
)
from .customer import (  # ✅ NEW
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatsResponse,
    AddNoteRequest,
    AddTagsRequest
)

__all__ = [
    "UserCreate",
    "UserUpdate", 
    "UserResponse",
    "Token",
    "TokenData",
    "UserLogin",
    "PasswordReset",
    "PasswordResetConfirm",
    "EmailVerification",
    "DemoBookingCreate",
    "DemoBookingResponse",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    "AvailabilityRequest",
    "AvailabilityResponse",
    # ✅ NEW
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerListResponse",
    "CustomerStatsResponse",
    "AddNoteRequest",
    "AddTagsRequest",
]