# # backend/app/models/__init__.py - UPDATED
# """
# Database Models Package
# """

# from .user import User, UserInDB, UserResponse
# from .subscription import Subscription, SubscriptionPlan
# from .demo_booking import DemoBooking
# from .appointment import Appointment  # ✅ NEW

# __all__ = [
#     "User",
#     "UserInDB", 
#     "UserResponse",
#     "Subscription",
#     "SubscriptionPlan",
#     "DemoBooking",
#     "Appointment",  # ✅ NEW
# ]


# backend/app/models/__init__.py - UPDATED
"""
Database Models Package
"""

from .user import User, UserInDB, UserResponse
from .subscription import Subscription, SubscriptionPlan
from .demo_booking import DemoBooking
from .appointment import Appointment
from .customer import Customer  # ✅ NEW

__all__ = [
    "User",
    "UserInDB", 
    "UserResponse",
    "Subscription",
    "SubscriptionPlan",
    "DemoBooking",
    "Appointment",
    "Customer",  # ✅ NEW
]