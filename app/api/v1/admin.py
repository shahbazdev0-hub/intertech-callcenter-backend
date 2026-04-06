# backend/app/api/v1/admin.py - FIXED
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId
from app.models.user import UserInDB
from app.schemas.user import UserResponse
from app.api.deps import get_current_admin_user
from app.database import get_collection
from app.utils.helpers import format_user_response, generate_mock_stats
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for update request bodies
class UserStatusUpdate(BaseModel):
    is_active: bool

class UserVerificationUpdate(BaseModel):
    is_verified: bool

class UserAdminUpdate(BaseModel):
    is_admin: bool

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_admin_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get all users (admin only)"""
    try:
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} requesting users list")
        users_collection = await get_collection("users")
        
        # Build query test commit
        query = {}
        if search:
            query = {
                "$or": [
                    {"email": {"$regex": search, "$options": "i"}},
                    {"full_name": {"$regex": search, "$options": "i"}},
                    {"company": {"$regex": search, "$options": "i"}}
                ]
            }
        
        # Get users with pagination
        cursor = users_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        users = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(users)} users")
        return [format_user_response(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_admin_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get specific user by ID (admin only)"""
    try:
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} requesting user {user_id}")
        users_collection = await get_collection("users")
        
        # Convert user_id to ObjectId if it's a valid ObjectId, otherwise use as string
        query_id = user_id
        if ObjectId.is_valid(user_id):
            query_id = ObjectId(user_id)
            logger.info(f"Using ObjectId for query: {query_id}")
        else:
            logger.info(f"Using string ID for query: {query_id}")
        
        user = await users_collection.find_one({"_id": query_id})
        
        if not user:
            logger.error(f"User not found with ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return format_user_response(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user: {str(e)}"
        )

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_update: UserStatusUpdate,
    current_user: dict = Depends(get_current_admin_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Update user active status (admin only)"""
    try:
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} updating user {user_id} status to {status_update.is_active}")
        
        users_collection = await get_collection("users")
        
        # ✅ FIXED: Use dict access for user ID
        current_user_id_str = str(current_user["_id"])
        
        # Prevent admin from deactivating themselves
        if user_id == current_user_id_str and not status_update.is_active:
            logger.warning(f"Admin {current_user['email']} tried to deactivate themselves")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        
        # Convert user_id to ObjectId if it's a valid ObjectId, otherwise use as string
        query_id = user_id
        if ObjectId.is_valid(user_id):
            query_id = ObjectId(user_id)
            logger.info(f"Using ObjectId for query: {query_id}")
        else:
            logger.info(f"Using string ID for query: {query_id}")
        
        # First check if user exists
        existing_user = await users_collection.find_one({"_id": query_id})
        if not existing_user:
            logger.error(f"User not found with ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"Found user: {existing_user.get('email', 'Unknown email')}")
        
        # Update the user
        result = await users_collection.update_one(
            {"_id": query_id},
            {
                "$set": {
                    "is_active": status_update.is_active,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Update result - matched: {result.matched_count}, modified: {result.modified_count}")
        
        if result.matched_count == 0:
            logger.error(f"No documents matched for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if result.modified_count == 0:
            logger.warning(f"No documents were modified for user {user_id} - status may already be {status_update.is_active}")
        
        action = "activated" if status_update.is_active else "deactivated"
        message = f"User {action} successfully"
        
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} {action} user {user_id}")
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id} status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user status: {str(e)}"
        )

@router.put("/users/{user_id}/verify")
async def update_user_verification(
    user_id: str,
    verification_update: UserVerificationUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """Update user verification status (admin only)"""
    try:
        logger.info(f"Admin {current_user['email']} updating user {user_id} verification to {verification_update.is_verified}")
        users_collection = await get_collection("users")

        query_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        existing_user = await users_collection.find_one({"_id": query_id})
        if not existing_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        result = await users_collection.update_one(
            {"_id": query_id},
            {"$set": {"is_verified": verification_update.is_verified, "updated_at": datetime.utcnow()}}
        )

        action = "verified" if verification_update.is_verified else "unverified"
        logger.info(f"Admin {current_user['email']} {action} user {user_id}")
        return {"message": f"User {action} successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id} verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user verification: {str(e)}"
        )

@router.put("/users/{user_id}/admin")
async def update_user_admin(
    user_id: str,
    admin_update: UserAdminUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """Grant or revoke admin access (admin only)"""
    try:
        logger.info(f"Admin {current_user['email']} updating user {user_id} admin to {admin_update.is_admin}")
        users_collection = await get_collection("users")

        current_user_id_str = str(current_user["_id"])
        if user_id == current_user_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify your own admin status"
            )

        query_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        existing_user = await users_collection.find_one({"_id": query_id})
        if not existing_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        result = await users_collection.update_one(
            {"_id": query_id},
            {"$set": {"is_admin": admin_update.is_admin, "updated_at": datetime.utcnow()}}
        )

        action = "granted" if admin_update.is_admin else "revoked"
        logger.info(f"Admin {current_user['email']} {action} admin access for user {user_id}")
        return {"message": f"Admin access {action} successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id} admin status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update admin status: {str(e)}"
        )

@router.get("/stats")
async def get_admin_stats(
    current_user: dict = Depends(get_current_admin_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get admin dashboard statistics"""
    try:
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} requesting dashboard stats")
        
        users_collection = await get_collection("users")
        demo_bookings_collection = await get_collection("demo_bookings")
        
        # Get user statistics
        total_users = await users_collection.count_documents({})
        active_users = await users_collection.count_documents({"is_active": True})
        verified_users = await users_collection.count_documents({"is_verified": True})
        admin_users = await users_collection.count_documents({"is_admin": True})
        
        # Get subscription breakdown
        free_users = await users_collection.count_documents({"subscription_plan": "free"})
        professional_users = await users_collection.count_documents({"subscription_plan": "professional"})
        enterprise_users = await users_collection.count_documents({"subscription_plan": "enterprise"})
        
        # Get demo bookings count
        total_demo_bookings = await demo_bookings_collection.count_documents({})
        
        # Calculate date ranges
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        new_users_this_week = await users_collection.count_documents({
            "created_at": {"$gte": week_ago}
        })
        new_users_this_month = await users_collection.count_documents({
            "created_at": {"$gte": month_ago}
        })
        
        # Calculate growth rates
        week_growth = round((new_users_this_week / total_users * 100), 1) if total_users > 0 else 0
        month_growth = round((new_users_this_month / total_users * 100), 1) if total_users > 0 else 0
        
        stats_data = {
            "user_stats": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "verified_users": verified_users,
                "admin_users": admin_users,
                "new_users_this_week": new_users_this_week,
                "new_users_this_month": new_users_this_month,
                "week_growth_rate": week_growth,
                "month_growth_rate": month_growth
            },
            "subscription_stats": {
                "free_users": free_users,
                "professional_users": professional_users,
                "enterprise_users": enterprise_users,
                "paid_users": professional_users + enterprise_users,
                "conversion_rate": round(((professional_users + enterprise_users) / total_users * 100), 1) if total_users > 0 else 0
            },
            "other_stats": {
                "total_demo_bookings": total_demo_bookings,
                "verification_rate": round((verified_users / total_users * 100), 1) if total_users > 0 else 0
            },
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "real_time"
        }
        
        logger.info(f"Generated stats for {total_users} users")
        return stats_data
        
    except Exception as e:
        logger.error(f"Error fetching admin stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )

@router.get("/subscription-stats")
async def get_subscription_stats(
    current_user: dict = Depends(get_current_admin_user)  # ✅ FIXED: dict instead of UserInDB
):
    """Get subscription statistics (admin only)"""
    try:
        # ✅ FIXED: Use dict access instead of attribute access
        logger.info(f"Admin {current_user['email']} requesting subscription stats")
        users_collection = await get_collection("users")
        
        total_users = await users_collection.count_documents({})
        free_users = await users_collection.count_documents({"subscription_plan": "free"})
        professional_users = await users_collection.count_documents({"subscription_plan": "professional"})
        enterprise_users = await users_collection.count_documents({"subscription_plan": "enterprise"})
        
        paid_users = professional_users + enterprise_users
        conversion_rate = round((paid_users / total_users * 100), 1) if total_users > 0 else 0
        
        monthly_revenue = (professional_users * 149) + (enterprise_users * 299)
        
        return {
            "total_users": total_users,
            "free_users": free_users,
            "professional_users": professional_users,
            "enterprise_users": enterprise_users,
            "paid_users": paid_users,
            "conversion_rate": conversion_rate,
            "monthly_revenue": monthly_revenue
        }
        
    except Exception as e:
        logger.error(f"Error fetching subscription stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription statistics: {str(e)}"
        )