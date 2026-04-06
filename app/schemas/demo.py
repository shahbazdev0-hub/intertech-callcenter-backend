# # backend/app/schemas/demo.py
# from pydantic import BaseModel, EmailStr, Field
# from typing import Optional
# from datetime import datetime

# class DemoBookingCreate(BaseModel):
#     full_name: str = Field(..., min_length=2, max_length=100)
#     email: EmailStr
#     company: str = Field(..., min_length=2, max_length=100)
#     phone: str = Field(..., min_length=10, max_length=20)
#     message: Optional[str] = Field(None, max_length=500)
#     preferred_date: Optional[str] = None
#     preferred_time: Optional[str] = None

# class DemoBookingResponse(BaseModel):
#     id: str
#     full_name: str
#     email: EmailStr
#     company: str
#     phone: str
#     message: Optional[str] = None
#     preferred_date: Optional[str] = None
#     preferred_time: Optional[str] = None
#     status: str
#     created_at: datetime
#     updated_at: datetime

# schemas/demo.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class DemoBookingCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    business_name: str = Field(..., min_length=2, max_length=100, alias="businessName")
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    business_description: str = Field(..., min_length=10, max_length=1000, alias="businessDescription")
    
    class Config:
        populate_by_name = True

class DemoBookingResponse(BaseModel):
    id: str
    name: str
    business_name: str
    email: EmailStr
    phone: str
    business_description: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True