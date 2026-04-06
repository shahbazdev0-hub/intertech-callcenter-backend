# backend/app/api/v1/reminders.py - NEW FILE
"""
Reminders API - Manage reminders and scheduled actions
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import logging

from app.api.deps import get_current_user
from app.database import get_database
from app.services.sms import sms_service
from app.services.email import email_service
from app.services.outbound_call import outbound_call_service
from app.tasks.reminder_tasks import send_sms_reminder, send_email_reminder, send_call_reminder

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# PYDANTIC SCHEMAS
# ============================================

class ReminderCreate(BaseModel):
    """Schema for creating a reminder"""
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    reminder_message: str
    reminder_type: str  # sms, email, call
    scheduled_time: datetime
    appointment_id: Optional[str] = None


class ReminderUpdate(BaseModel):
    """Schema for updating a reminder"""
    reminder_message: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    status: Optional[str] = None


# ============================================
# REMINDER ENDPOINTS
# ============================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder_data: ReminderCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new reminder
    
    Supports SMS, Email, and Call reminders
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Validate reminder type
        valid_types = ["sms", "email", "call"]
        if reminder_data.reminder_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reminder type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Validate contact info based on type
        if reminder_data.reminder_type == "sms" and not reminder_data.customer_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number required for SMS reminders"
            )
        
        if reminder_data.reminder_type == "email" and not reminder_data.customer_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address required for email reminders"
            )
        
        if reminder_data.reminder_type == "call" and not reminder_data.customer_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number required for call reminders"
            )
        
        # Create reminder record
        reminder_doc = {
            "user_id": user_id,
            "customer_name": reminder_data.customer_name,
            "customer_phone": reminder_data.customer_phone,
            "customer_email": reminder_data.customer_email,
            "reminder_message": reminder_data.reminder_message,
            "reminder_type": reminder_data.reminder_type,
            "scheduled_time": reminder_data.scheduled_time,
            "appointment_id": reminder_data.appointment_id,
            "status": "scheduled",
            "sent": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.reminders.insert_one(reminder_doc)
        reminder_id = str(result.inserted_id)
        
        logger.info(f"✅ Reminder created: {reminder_id}")
        
        # Calculate delay in seconds
        delay = int((reminder_data.scheduled_time - datetime.utcnow()).total_seconds())
        
        if delay > 0:
            # Schedule reminder task
            if reminder_data.reminder_type == "sms":
                send_sms_reminder.apply_async(
                    args=[
                        reminder_data.customer_phone,
                        reminder_data.customer_name,
                        reminder_data.reminder_message,
                        user_id,
                        reminder_data.appointment_id
                    ],
                    countdown=delay
                )
            elif reminder_data.reminder_type == "email":
                send_email_reminder.apply_async(
                    args=[
                        reminder_data.customer_email,
                        reminder_data.customer_name,
                        "Reminder",
                        reminder_data.reminder_message,
                        reminder_data.appointment_id
                    ],
                    countdown=delay
                )
            elif reminder_data.reminder_type == "call":
                send_call_reminder.apply_async(
                    args=[
                        reminder_data.customer_phone,
                        reminder_data.customer_name,
                        reminder_data.reminder_message,
                        user_id,
                        None,  # agent_id
                        reminder_data.appointment_id
                    ],
                    countdown=delay
                )
            
            logger.info(f"✅ Reminder scheduled for {reminder_data.scheduled_time}")
        
        return {
            "success": True,
            "reminder_id": reminder_id,
            "message": "Reminder created and scheduled",
            "scheduled_time": reminder_data.scheduled_time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/")
async def list_reminders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    reminder_type: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    """
    List reminders with filters
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Build query
        query = {"user_id": user_id}
        
        if reminder_type:
            query["reminder_type"] = reminder_type
        
        if status_filter:
            query["status"] = status_filter
        
        # Get total count
        total = await db.reminders.count_documents(query)
        
        # Get reminders
        cursor = db.reminders.find(query).sort("scheduled_time", -1).skip(skip).limit(limit)
        reminders = await cursor.to_list(length=limit)
        
        # Format response
        formatted_reminders = []
        for reminder in reminders:
            formatted_reminders.append({
                "id": str(reminder["_id"]),
                "customer_name": reminder.get("customer_name"),
                "customer_phone": reminder.get("customer_phone"),
                "customer_email": reminder.get("customer_email"),
                "reminder_message": reminder.get("reminder_message"),
                "reminder_type": reminder.get("reminder_type"),
                "scheduled_time": reminder.get("scheduled_time").isoformat() if reminder.get("scheduled_time") else None,
                "status": reminder.get("status"),
                "sent": reminder.get("sent", False),
                "sent_at": reminder.get("sent_at").isoformat() if reminder.get("sent_at") else None,
                "created_at": reminder.get("created_at").isoformat() if reminder.get("created_at") else None
            })
        
        return {
            "success": True,
            "reminders": formatted_reminders,
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing reminders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{reminder_id}")
async def get_reminder(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single reminder"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        if not ObjectId.is_valid(reminder_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reminder ID"
            )
        
        reminder = await db.reminders.find_one({
            "_id": ObjectId(reminder_id),
            "user_id": user_id
        })
        
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found"
            )
        
        return {
            "id": str(reminder["_id"]),
            "customer_name": reminder.get("customer_name"),
            "customer_phone": reminder.get("customer_phone"),
            "customer_email": reminder.get("customer_email"),
            "reminder_message": reminder.get("reminder_message"),
            "reminder_type": reminder.get("reminder_type"),
            "scheduled_time": reminder.get("scheduled_time").isoformat() if reminder.get("scheduled_time") else None,
            "status": reminder.get("status"),
            "sent": reminder.get("sent", False),
            "sent_at": reminder.get("sent_at").isoformat() if reminder.get("sent_at") else None,
            "appointment_id": reminder.get("appointment_id")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{reminder_id}")
async def update_reminder(
    reminder_id: str,
    reminder_data: ReminderUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a reminder"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        if not ObjectId.is_valid(reminder_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reminder ID"
            )
        
        # Build update data
        update_data = reminder_data.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.reminders.update_one(
            {"_id": ObjectId(reminder_id), "user_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found"
            )
        
        logger.info(f"✅ Reminder updated: {reminder_id}")
        
        return {
            "success": True,
            "message": "Reminder updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a reminder"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        if not ObjectId.is_valid(reminder_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reminder ID"
            )
        
        result = await db.reminders.delete_one({
            "_id": ObjectId(reminder_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reminder not found"
            )
        
        logger.info(f"✅ Reminder deleted: {reminder_id}")
        
        return {
            "success": True,
            "message": "Reminder deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats/summary")
async def get_reminder_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get reminder statistics"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Total reminders
        total = await db.reminders.count_documents({"user_id": user_id})
        
        # By status
        scheduled = await db.reminders.count_documents({
            "user_id": user_id,
            "status": "scheduled"
        })
        
        sent = await db.reminders.count_documents({
            "user_id": user_id,
            "sent": True
        })
        
        # By type
        sms_count = await db.reminders.count_documents({
            "user_id": user_id,
            "reminder_type": "sms"
        })
        
        email_count = await db.reminders.count_documents({
            "user_id": user_id,
            "reminder_type": "email"
        })
        
        call_count = await db.reminders.count_documents({
            "user_id": user_id,
            "reminder_type": "call"
        })
        
        return {
            "total": total,
            "scheduled": scheduled,
            "sent": sent,
            "by_type": {
                "sms": sms_count,
                "email": email_count,
                "call": call_count
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting reminder stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )