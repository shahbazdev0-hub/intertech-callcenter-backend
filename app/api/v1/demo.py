
# demo.py
from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.demo import DemoBookingCreate, DemoBookingResponse
from app.models.demo_booking import DemoBooking
from app.models.user import UserInDB
from app.api.deps import get_current_admin_user
from app.database import get_collection
from app.utils.helpers import validate_phone_number
from bson import ObjectId
from datetime import datetime
from typing import List

router = APIRouter()

@router.post("/book", response_model=dict)
async def book_demo(demo_data: DemoBookingCreate):
    """Book a demo session"""
    try:
        # Validate phone number
        if not validate_phone_number(demo_data.phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format"
            )
        
        demos_collection = await get_collection("demo_bookings")
        
        # Check for duplicate booking
        existing_demo = await demos_collection.find_one({
            "email": demo_data.email,
            "status": {"$in": ["pending", "confirmed"]}
        })
        
        if existing_demo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a pending demo booking"
            )
        
        # Create demo booking
        demo_doc = {
            "_id": str(ObjectId()),
            "name": demo_data.name,
            "business_name": demo_data.business_name,
            "email": demo_data.email,
            "phone": demo_data.phone,
            "business_description": demo_data.business_description,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await demos_collection.insert_one(demo_doc)
        
        if result.inserted_id:
            return {
                "message": "Demo booked successfully! We'll contact you soon to schedule.",
                "booking_id": demo_doc["_id"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to book demo"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book demo: {str(e)}"
        )

@router.get("/bookings", response_model=List[DemoBookingResponse])
async def get_demo_bookings(
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Get all demo bookings (admin only)"""
    demos_collection = await get_collection("demo_bookings")
    
    cursor = demos_collection.find({}).sort("created_at", -1)
    demos = await cursor.to_list(length=100)
    
    return [DemoBookingResponse(**demo) for demo in demos]

@router.get("/bookings/{booking_id}", response_model=DemoBookingResponse)
async def get_demo_booking(
    booking_id: str,
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Get a specific demo booking (admin only)"""
    demos_collection = await get_collection("demo_bookings")
    
    demo = await demos_collection.find_one({"_id": booking_id})
    
    if not demo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return DemoBookingResponse(**demo)

@router.put("/bookings/{booking_id}/status")
async def update_demo_status(
    booking_id: str,
    new_status: str,
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Update demo booking status (admin only)"""
    if new_status not in ["pending", "confirmed", "completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )
    
    demos_collection = await get_collection("demo_bookings")
    
    result = await demos_collection.update_one(
        {"_id": booking_id},
        {
            "$set": {
                "status": new_status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return {"message": f"Booking status updated to {new_status}"}

@router.delete("/bookings/{booking_id}")
async def delete_demo_booking(
    booking_id: str,
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Delete a demo booking (admin only)"""
    demos_collection = await get_collection("demo_bookings")
    
    result = await demos_collection.delete_one({"_id": booking_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return {"message": "Booking deleted successfully"}