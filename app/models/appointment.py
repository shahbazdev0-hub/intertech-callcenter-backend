# # backend/app/models/appointment.py -without ai follow up calender integration
# """
# Appointment Model - Stores appointment bookings
# """

# from pydantic import BaseModel, Field, EmailStr
# from typing import Optional
# from datetime import datetime
# from bson import ObjectId


# class Appointment(BaseModel):
#     """Appointment database model"""
    
#     id: Optional[str] = Field(default_factory=str, alias="_id")
    
#     # Customer information
#     customer_name: str
#     customer_email: EmailStr
#     customer_phone: str
    
#     # Appointment details
#     appointment_date: datetime
#     appointment_time: str  # "14:00", "09:30", etc.
#     service_type: Optional[str] = None
#     notes: Optional[str] = None
    
#     # Booking metadata
#     call_id: Optional[str] = None  # Link to call that created it
#     user_id: Optional[str] = None  # Business owner
#     agent_id: Optional[str] = None  # Voice agent that booked it
#     workflow_id: Optional[str] = None  # Workflow used
    
#     # Google Calendar integration
#     google_calendar_event_id: Optional[str] = None
    
#     # Status
#     status: str = "scheduled"  # scheduled, confirmed, cancelled, completed, no_show
    
#     # Timestamps
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     updated_at: datetime = Field(default_factory=datetime.utcnow)
#     confirmed_at: Optional[datetime] = None
    
#     class Config:
#         populate_by_name = True
#         json_encoders = {ObjectId: str} 



# backend/app/models/appointment.py - UPDATED FILE with ai follow up calender integration
"""
Appointment Model - Stores appointment bookings
✅ ENHANCED: Added follow-up, event_type, and action_type fields
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from bson import ObjectId


class Appointment(BaseModel):
    """Appointment database model"""
    
    id: Optional[str] = Field(default_factory=str, alias="_id")
    
    # Customer information
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    
    # Appointment details
    appointment_date: datetime
    appointment_time: str  # "14:00", "09:30", etc.
    service_type: Optional[str] = None
    notes: Optional[str] = None
    
    # ✅ NEW: Follow-up and event tracking
    event_type: Optional[str] = "appointment"  # appointment, follow_up_call, reminder, callback
    action_type: Optional[str] = None  # call, sms, email
    original_user_request: Optional[str] = None  # "Call me in 2 hours"
    is_automated_action: bool = False  # True if created by AI for follow-up
    parent_appointment_id: Optional[str] = None  # Link to original appointment if this is a follow-up
    
    # ✅ NEW: Reminder settings
    reminder_sent: bool = False
    reminder_sent_at: Optional[datetime] = None
    
    # ✅ NEW: Action completion tracking
    action_completed: bool = False
    action_completed_at: Optional[datetime] = None
    action_result: Optional[str] = None  # Result of automated action (success, failed, no_answer)
    
    # Booking metadata
    call_id: Optional[str] = None  # Link to call that created it
    user_id: Optional[str] = None  # Business owner
    agent_id: Optional[str] = None  # Voice agent that booked it
    workflow_id: Optional[str] = None  # Workflow used
    
    # Google Calendar integration
    google_calendar_event_id: Optional[str] = None
    google_calendar_link: Optional[str] = None
    
    # Status
    status: str = "scheduled"  # scheduled, confirmed, cancelled, completed, no_show, pending_action
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}