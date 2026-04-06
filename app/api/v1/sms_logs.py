

# backend/app/api/v1/sms_logs.py - FIXED REPLY FUNCTION

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import os

from app.schemas.sms_log import (
    SMSLogResponse,
    SMSReplyRequest,
    SMSLogFilters
)
from app.api.deps import get_current_user
from app.database import get_database
from app.services.sms import sms_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict)
async def get_sms_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    direction: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get SMS logs for the current user with filtering and pagination
    """
    try:
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        if status:
            query["status"] = status
        
        if direction:
            query["direction"] = direction
        
        # Date range filter
        if from_date or to_date:
            query["created_at"] = {}
            if from_date:
                query["created_at"]["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            if to_date:
                query["created_at"]["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Search filter
        if search:
            query["$or"] = [
                {"message": {"$regex": search, "$options": "i"}},
                {"to_number": {"$regex": search, "$options": "i"}},
                {"from_number": {"$regex": search, "$options": "i"}},
                {"customer_name": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await db.sms_logs.count_documents(query)
        
        # Get SMS logs
        cursor = db.sms_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
        sms_logs = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for log in sms_logs:
            log["_id"] = str(log["_id"])
            log["id"] = str(log["_id"])
        
        logger.info(f"Found {total} SMS logs for user {user_id}")
        
        return {
            "sms_logs": sms_logs,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching SMS logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{sms_id}", response_model=dict)
async def get_sms_log_detail(
    sms_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get detailed information about a specific SMS log including replies"""
    try:
        user_id = str(current_user["_id"])
        
        # Get the SMS log
        sms_log = await db.sms_logs.find_one({
            "_id": ObjectId(sms_id),
            "user_id": user_id
        })
        
        if not sms_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMS log not found"
            )
        
        # Convert ObjectId to string
        sms_log["_id"] = str(sms_log["_id"])
        sms_log["id"] = str(sms_log["_id"])
        
        # Get replies to this SMS
        replies_cursor = db.sms_logs.find({
            "reply_to_sms_id": sms_id,
            "user_id": user_id
        }).sort("created_at", 1)
        
        replies = await replies_cursor.to_list(length=100)
        
        for reply in replies:
            reply["_id"] = str(reply["_id"])
            reply["id"] = str(reply["_id"])
        
        sms_log["replies"] = replies
        
        return sms_log
        
    except Exception as e:
        logger.error(f"Error fetching SMS log detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reply", response_model=dict, status_code=status.HTTP_201_CREATED)
async def reply_to_sms(
    reply_request: SMSReplyRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Reply to an SMS message"""
    try:
        user_id = str(current_user["_id"])
        
        # Verify the original SMS exists
        original_sms = await db.sms_logs.find_one({
            "_id": ObjectId(reply_request.original_sms_id),
            "user_id": user_id
        })
        
        if not original_sms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original SMS not found"
            )
        
        # Resolve Twilio phone number with fallback chain
        from app.utils.credential_resolver import resolve_twilio_credentials
        _, _, twilio_phone_number = resolve_twilio_credentials(current_user)

        if not twilio_phone_number:
            logger.error("No Twilio phone number configured for user")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SMS service not configured. Please set up Twilio integration or purchase a phone number."
            )
        
        logger.info(f"📤 Sending SMS reply:")
        logger.info(f"   From: {twilio_phone_number} (Your Twilio number)")
        logger.info(f"   To: {reply_request.to_number} (Customer number)")
        logger.info(f"   Message: {reply_request.message[:50]}...")
        
        # ✅ FIX: Send the reply SMS with explicit from_number
        result = await sms_service.send_sms(
            to_number=reply_request.to_number,
            message=reply_request.message,
            from_number=twilio_phone_number,  # ✅ CRITICAL FIX: Explicitly pass Twilio number
            user_id=user_id
        )
        
        if not result.get("success"):
            logger.error(f"❌ Failed to send SMS: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to send SMS reply")
            )
        
        # Create SMS log entry for the reply
        reply_log = {
            "user_id": user_id,
            "to_number": reply_request.to_number,
            "from_number": twilio_phone_number,  # ✅ Use Twilio number
            "message": reply_request.message,
            "direction": "outbound",
            "status": "sent",
            "twilio_sid": result.get("twilio_sid"),
            "is_reply": True,
            "reply_to_sms_id": reply_request.original_sms_id,
            "customer_name": original_sms.get("customer_name"),
            "customer_email": original_sms.get("customer_email"),
            "created_at": datetime.utcnow(),
            "sent_at": datetime.utcnow()
        }
        
        reply_result = await db.sms_logs.insert_one(reply_log)
        reply_log["_id"] = str(reply_result.inserted_id)
        
        # Update original SMS to mark it has replies
        await db.sms_logs.update_one(
            {"_id": ObjectId(reply_request.original_sms_id)},
            {
                "$set": {"has_replies": True},
                "$inc": {"reply_count": 1}
            }
        )
        
        logger.info(f"✅ Reply sent successfully to {reply_request.to_number}")
        logger.info(f"   Twilio SID: {result.get('twilio_sid')}")
        
        return {
            "success": True,
            "message": "Reply sent successfully",
            "sms_log": reply_log
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error sending reply: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats/summary", response_model=dict)
async def get_sms_stats_summary(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get SMS statistics summary"""
    try:
        user_id = str(current_user["_id"])
        
        # Total counts by status
        total_sent = await db.sms_logs.count_documents({
            "user_id": user_id,
            "status": "sent"
        })
        
        total_delivered = await db.sms_logs.count_documents({
            "user_id": user_id,
            "status": "delivered"
        })
        
        total_failed = await db.sms_logs.count_documents({
            "user_id": user_id,
            "status": "failed"
        })
        
        total_pending = await db.sms_logs.count_documents({
            "user_id": user_id,
            "status": "pending"
        })
        
        # Today's sent
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sent = await db.sms_logs.count_documents({
            "user_id": user_id,
            "direction": "outbound",
            "created_at": {"$gte": today_start}
        })
        
        # This week's sent
        week_start = today_start - timedelta(days=today_start.weekday())
        week_sent = await db.sms_logs.count_documents({
            "user_id": user_id,
            "direction": "outbound",
            "created_at": {"$gte": week_start}
        })
        
        # This month's sent
        month_start = today_start.replace(day=1)
        month_sent = await db.sms_logs.count_documents({
            "user_id": user_id,
            "direction": "outbound",
            "created_at": {"$gte": month_start}
        })
        
        return {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_failed": total_failed,
            "total_pending": total_pending,
            "today_sent": today_sent,
            "this_week_sent": week_sent,
            "this_month_sent": month_sent
        }
        
    except Exception as e:
        logger.error(f"Error fetching SMS stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )