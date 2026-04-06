


# backend/app/api/v1/users.py - FIXED to handle dict current_user
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, EmailStr
from bson import ObjectId
import base64
from app.schemas.user import (
    UserUpdate, UserResponse, NotificationPreferences, 
    PasswordChangeRequest, EmailChangeRequest,
    PasswordChangeResponse, EmailChangeResponse, NotificationUpdateResponse
)
from app.api.deps import get_current_active_user
from app.database import get_collection
from app.utils.helpers import format_user_response
from app.core.security import verify_password, get_password_hash
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get current user information"""
    return format_user_response(current_user)

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Update current user information"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access instead of attribute access
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        update_data = {k: v for k, v in user_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided for update"
            )
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await users_collection.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user"
            )
        
        # Get updated user
        updated_user = await users_collection.find_one({"_id": user_id})
        return format_user_response(updated_user)
        
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
        )

# ✅ NEW - Profile picture upload endpoint
@router.put("/me/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user)
):
    """Upload user profile picture — stored as base64 in MongoDB"""
    try:
        users_collection = await get_collection("users")

        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read and validate size (5MB max)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image must be less than 5MB")

        # Store as base64 data URI in MongoDB
        b64 = base64.b64encode(content).decode("utf-8")
        data_uri = f"data:{file.content_type};base64,{b64}"

        await users_collection.update_one(
            {"_id": user_id},
            {"$set": {"profile_picture": data_uri, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Profile picture uploaded for user {current_user.get('email')}")

        # Return updated user
        updated_user = await users_collection.find_one({"_id": user_id})
        return format_user_response(updated_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")


# ✅ NEW - Password change endpoint
@router.put("/me/password", response_model=PasswordChangeResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Change user password"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access and handle ObjectId conversion
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        user_email = current_user.get("email", "unknown")
        
        # Get current user from database
        user_doc = await users_collection.find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not verify_password(password_data.current_password, user_doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password
        if len(password_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Additional password validation
        import re
        if not re.search(r"[A-Z]", password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one uppercase letter"
            )
        if not re.search(r"[a-z]", password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one lowercase letter"
            )
        if not re.search(r"[0-9]", password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one number"
            )
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one special character"
            )
        
        # Hash new password
        new_hashed_password = get_password_hash(password_data.new_password)
        
        # Update password in database
        result = await users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "hashed_password": new_hashed_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update password"
            )
        
        logger.info(f"Password changed successfully for user: {user_email}")
        return PasswordChangeResponse(message="Password changed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        user_email = current_user.get("email", "unknown")  # ✅ FIXED: Use dict access
        logger.error(f"Error changing password for user {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )

# ✅ NEW - Email change endpoint
@router.put("/me/email", response_model=EmailChangeResponse)
async def change_email(
    email_data: EmailChangeRequest,
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Change user email"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access and handle ObjectId conversion
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        user_email = current_user.get("email", "unknown")
        
        # Get current user from database
        user_doc = await users_collection.find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not verify_password(email_data.current_password, user_doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Check if new email already exists
        existing_email = await users_collection.find_one({"email": email_data.new_email})
        if existing_email and str(existing_email["_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use"
            )
        
        # Update email in database
        result = await users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "email": email_data.new_email,
                    "is_verified": False,  # User needs to verify new email
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update email"
            )
        
        logger.info(f"Email changed from {user_email} to {email_data.new_email}")
        return EmailChangeResponse(
            message="Email updated successfully",
            new_email=email_data.new_email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        user_email = current_user.get("email", "unknown")  # ✅ FIXED: Use dict access
        logger.error(f"Error changing email for user {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change email"
        )

# ✅ NEW - Get notification preferences
@router.get("/me/notifications")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get user notification preferences"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access and handle ObjectId conversion
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        user_doc = await users_collection.find_one({"_id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Return notification preferences with defaults if not set
        notifications = user_doc.get("notification_preferences", {
            "email_campaigns": True,
            "sms_alerts": False,
            "call_summaries": True,
            "weekly_reports": True,
            "security_alerts": True
        })
        
        return notifications
        
    except HTTPException:
        raise
    except Exception as e:
        user_email = current_user.get("email", "unknown")  # ✅ FIXED: Use dict access
        logger.error(f"Error getting notification preferences for user {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification preferences"
        )

# ✅ NEW - Update notification preferences
@router.put("/me/notifications", response_model=NotificationUpdateResponse)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Update user notification preferences"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access and handle ObjectId conversion
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        user_email = current_user.get("email", "unknown")
        
        # Convert preferences to dict
        preferences_dict = preferences.dict()
        
        # Update notification preferences in database
        result = await users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "notification_preferences": preferences_dict,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            # Even if no modification, return success (preferences might be the same)
            logger.info(f"No changes in notification preferences for user: {user_email}")
        else:
            logger.info(f"Notification preferences updated for user: {user_email}")
        
        return NotificationUpdateResponse(
            message="Notification preferences updated successfully",
            preferences=preferences_dict
        )
        
    except Exception as e:
        user_email = current_user.get("email", "unknown")  # ✅ FIXED: Use dict access
        logger.error(f"Error updating notification preferences for user {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )

# ✅ EXISTING - Delete user account
@router.delete("/me")
async def delete_current_user(
    current_user: dict = Depends(get_current_active_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Delete current user account"""
    try:
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access and handle ObjectId conversion
        user_id = current_user.get("_id") or current_user.get("id")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        user_email = current_user.get("email", "unknown")
        
        result = await users_collection.delete_one({"_id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete user account"
            )
        
        logger.info(f"User account deleted: {user_email}")
        return {"message": "Account deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        user_email = current_user.get("email", "unknown")  # ✅ FIXED: Use dict access
        logger.error(f"Error deleting user account {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )