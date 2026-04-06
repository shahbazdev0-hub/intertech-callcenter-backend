# # backend/app/models/demo_booking.py
# from pydantic import BaseModel, Field, EmailStr
# from typing import Optional
# from datetime import datetime
# from bson import ObjectId

# class DemoBooking(BaseModel):
#     id: Optional[str] = Field(default_factory=str, alias="_id")
#     full_name: str
#     email: EmailStr
#     company: str
#     phone: str
#     message: Optional[str] = None
#     preferred_date: Optional[str] = None
#     preferred_time: Optional[str] = None
#     status: str = "pending"  # pending, confirmed, completed, cancelled
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     updated_at: datetime = Field(default_factory=datetime.utcnow)

#     class Config:
#         populate_by_name = True
#         json_encoders = {ObjectId: str}
# demo_booking.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from bson import ObjectId

class DemoBooking(BaseModel):
    id: Optional[str] = Field(default_factory=str, alias="_id")
    name: str
    business_name: str
    email: EmailStr
    phone: str
    business_description: str
    status: str = "pending"  # pending, confirmed, completed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}