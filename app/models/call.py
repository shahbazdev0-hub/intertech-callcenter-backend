# # backend/app/models/call.py - orginal file 

# from datetime import datetime
# from typing import Optional
# from pydantic import BaseModel, Field, ConfigDict
# from .base import PyObjectId
# from bson import ObjectId


# class Call(BaseModel):
#     model_config = ConfigDict(
#         populate_by_name=True,
#         arbitrary_types_allowed=True,
#         json_encoders={ObjectId: str},
#         json_schema_extra={
#             "example": {
#                 "user_id": "507f1f77bcf86cd799439011",
#                 "direction": "outbound",
#                 "from_number": "+1234567890",
#                 "to_number": "+0987654321",
#                 "phone_number": "+0987654321",
#                 "status": "completed",
#                 "duration": 120,
#                 "call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#                 "twilio_call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#                 "recording_url": "https://api.twilio.com/recordings/RExxxx",
#                 "recording_sid": "RExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#                 "recording_duration": 120
#             }
#         }
#     )

#     id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
#     user_id: str
#     direction: str  # inbound or outbound
#     from_number: str
#     to_number: str
#     phone_number: Optional[str] = None  # ✅ Customer's phone number
#     status: str  # initiated, ringing, in-progress, completed, failed, busy, no-answer
#     duration: Optional[int] = 0  # in seconds
#     outcome: Optional[str] = None  # success, failed, no-answer, busy
    
#     # ✅ Twilio identifiers
#     call_sid: Optional[str] = None  # Legacy field
#     twilio_call_sid: Optional[str] = None  # ✅ Primary Twilio call SID
    
#     # ✅ NEW: Recording fields
#     recording_url: Optional[str] = None  # ✅ Public URL to access recording
#     recording_sid: Optional[str] = None  # ✅ Twilio recording SID
#     recording_duration: Optional[int] = 0  # ✅ Recording duration in seconds
    
#     # ✅ Agent information
#     agent_id: Optional[PyObjectId] = None
    
#     # ✅ Timestamps
#     started_at: Optional[datetime] = None
#     ended_at: Optional[datetime] = None
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     updated_at: datetime = Field(default_factory=datetime.utcnow)

# backend/app/models/call.py - ✅ Updated with local recording storage fields

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from .base import PyObjectId
from bson import ObjectId


class Call(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "direction": "outbound",
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "phone_number": "+0987654321",
                "status": "completed",
                "duration": 120,
                "call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "twilio_call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "recording_url": "https://api.twilio.com/recordings/RExxxx",
                "recording_sid": "RExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "recording_duration": 120,
                "local_recording_path": "recordings/RExxxx.mp3",
                "local_recording_filename": "RExxxx.mp3",
                "recording_downloaded": True
            }
        }
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    direction: str  # inbound or outbound
    from_number: str
    to_number: str
    phone_number: Optional[str] = None  # ✅ Customer's phone number
    status: str  # initiated, ringing, in-progress, completed, failed, busy, no-answer
    duration: Optional[int] = 0  # in seconds
    outcome: Optional[str] = None  # success, failed, no-answer, busy
    
    # ✅ Twilio identifiers
    call_sid: Optional[str] = None  # Legacy field
    twilio_call_sid: Optional[str] = None  # ✅ Primary Twilio call SID
    
    # ✅ Recording fields
    recording_url: Optional[str] = None  # ✅ Public URL to access recording
    recording_sid: Optional[str] = None  # ✅ Twilio recording SID
    recording_duration: Optional[int] = 0  # ✅ Recording duration in seconds
    
    # ✅ Local recording storage
    local_recording_path: Optional[str] = None  # Path to local MP3 file
    local_recording_filename: Optional[str] = None  # Filename
    recording_downloaded: Optional[bool] = False  # Download status
    
    # ✅ Agent information
    agent_id: Optional[PyObjectId] = None
    
    # ✅ Timestamps
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)