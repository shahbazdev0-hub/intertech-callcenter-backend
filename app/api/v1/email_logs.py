

# backend/app/api/v1/email_logs.py - CORRECTED VERSION (NO EMOJIS)

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.schemas.email_log import (
    EmailLogResponse,
    EmailLogFilters,
    EmailReplyRequest
)
from app.api.deps import get_current_user
from app.database import get_database
from app.services.email_automation import email_automation_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict)
async def get_email_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
    has_opened: Optional[bool] = None,
    has_clicked: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get email logs for the current user with filtering and pagination
    
    - **status**: Filter by status (pending, sent, delivered, opened, clicked, failed)
    - **from_date**: Filter from date (ISO format)
    - **to_date**: Filter to date (ISO format)
    - **search**: Search in subject, recipient email, or content
    - **has_opened**: Filter by opened status
    - **has_clicked**: Filter by clicked status
    """
    try:
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        if status:
            query["status"] = status
        
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
                {"subject": {"$regex": search, "$options": "i"}},
                {"to_email": {"$regex": search, "$options": "i"}},
                {"recipient_name": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}}
            ]
        
        # Opened filter
        if has_opened is not None:
            if has_opened:
                query["opened_count"] = {"$gt": 0}
            else:
                query["opened_count"] = 0
        
        # Clicked filter
        if has_clicked is not None:
            if has_clicked:
                query["clicked_count"] = {"$gt": 0}
            else:
                query["clicked_count"] = 0
        
        # Get total count
        total = await db.email_logs.count_documents(query)
        
        # Get email logs
        cursor = db.email_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
        email_logs = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string and remove full content for list view
        for log in email_logs:
            log["_id"] = str(log["_id"])
            log["id"] = str(log["_id"])
            # Truncate content for list view
            if "content" in log and len(log["content"]) > 200:
                log["content_preview"] = log["content"][:200] + "..."
                del log["content"]  # Remove full content from list view
        
        logger.info(f"Found {total} email logs for user {user_id}")
        
        return {
            "email_logs": email_logs,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching email logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{email_id}", response_model=dict)
async def get_email_log_detail(
    email_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get detailed information about a specific email log"""
    try:
        user_id = str(current_user["_id"])
        
        # Get the email log
        email_log = await db.email_logs.find_one({
            "_id": ObjectId(email_id),
            "user_id": user_id
        })
        
        if not email_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email log not found"
            )
        
        # Convert ObjectId to string
        email_log["_id"] = str(email_log["_id"])
        email_log["id"] = str(email_log["_id"])
        
        return email_log
        
    except Exception as e:
        logger.error(f"Error fetching email log detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reply", response_model=dict)
async def reply_to_email(
    reply_data: EmailReplyRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Reply to an email from email logs
    
    This endpoint allows users to reply to emails they have previously sent.
    The reply will be sent to the original recipient and logged in the system.
    """
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"Processing email reply from user {user_id}")
        
        # Get the original email log to validate it exists and belongs to the user
        original_email = await db.email_logs.find_one({
            "_id": ObjectId(reply_data.original_email_id),
            "user_id": user_id
        })
        
        if not original_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original email not found or you don't have permission to reply"
            )
        
        # Prepare reply subject (add "Re: " if not already present)
        original_subject = original_email.get("subject", "")
        reply_subject = reply_data.subject if reply_data.subject else f"Re: {original_subject}"
        
        if reply_data.subject and not reply_data.subject.startswith("Re: "):
            reply_subject = f"Re: {reply_subject}"
        
        # Get recipient information from original email
        recipient_email = original_email.get("to_email")
        recipient_name = original_email.get("recipient_name")
        recipient_phone = original_email.get("recipient_phone")
        
        logger.info(f"Reply to: {recipient_email}")
        logger.info(f"Subject: {reply_subject}")
        
        # Send the reply email using email automation service
        result = await email_automation_service.send_email(
            to_email=recipient_email,
            subject=reply_subject,
            html_content=reply_data.content,
            text_content=reply_data.content,
            user_id=user_id,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            automation_id=original_email.get("automation_id"),
            call_id=original_email.get("call_id"),
            appointment_id=original_email.get("appointment_id")
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send reply")
            )
        
        # Update original email to mark that it has been replied to
        await db.email_logs.update_one(
            {"_id": ObjectId(reply_data.original_email_id)},
            {
                "$set": {
                    "has_reply": True,
                    "last_replied_at": datetime.utcnow()
                },
                "$inc": {
                    "reply_count": 1
                }
            }
        )
        
        logger.info(f"Email reply sent successfully")
        
        return {
            "success": True,
            "message": "Email reply sent successfully",
            "email_log_id": result.get("email_log_id"),
            "sent_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email reply: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats/summary", response_model=dict)
async def get_email_stats_summary(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get email statistics summary"""
    try:
        user_id = str(current_user["_id"])
        
        # Total counts by status
        total_sent = await db.email_logs.count_documents({
            "user_id": user_id,
            "status": {"$in": ["sent", "delivered", "opened", "clicked"]}
        })
        
        total_delivered = await db.email_logs.count_documents({
            "user_id": user_id,
            "status": {"$in": ["delivered", "opened", "clicked"]}
        })
        
        total_opened = await db.email_logs.count_documents({
            "user_id": user_id,
            "opened_count": {"$gt": 0}
        })
        
        total_clicked = await db.email_logs.count_documents({
            "user_id": user_id,
            "clicked_count": {"$gt": 0}
        })
        
        total_failed = await db.email_logs.count_documents({
            "user_id": user_id,
            "status": "failed"
        })
        
        total_pending = await db.email_logs.count_documents({
            "user_id": user_id,
            "status": "pending"
        })
        
        # Calculate success rate
        success_rate = 0
        if total_sent > 0:
            success_rate = round((total_delivered / total_sent) * 100, 2)
        
        # Calculate open rate
        open_rate = 0
        if total_delivered > 0:
            open_rate = round((total_opened / total_delivered) * 100, 2)
        
        # Calculate click rate
        click_rate = 0
        if total_opened > 0:
            click_rate = round((total_clicked / total_opened) * 100, 2)
        
        # Get today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sent = await db.email_logs.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": today_start}
        })
        
        return {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_opened": total_opened,
            "total_clicked": total_clicked,
            "total_failed": total_failed,
            "total_pending": total_pending,
            "success_rate": success_rate,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "today_sent": today_sent
        }
        
    except Exception as e:
        logger.error(f"Error fetching email stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )