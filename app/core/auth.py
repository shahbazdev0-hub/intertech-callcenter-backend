# backend/app/core/auth.py
from fastapi import HTTPException, status
from app.core.security import verify_token
from app.models.user import UserInDB
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.security import verify_password
import logging

logger = logging.getLogger(__name__)

async def authenticate_user(username: str, password: str) -> UserInDB:
    """Authenticate user with username or email"""
    try:
        from app.database import get_collection
        users_collection = await get_collection("users")
        
        # Find user by username OR email (for backward compatibility)
        user_doc = await users_collection.find_one({
            "$or": [
                {"username": username},
                {"email": username}
            ]
        })
        if not user_doc:
            logger.warning(f"User not found: {username}")
            return None
        
        # Verify password
        if not verify_password(password, user_doc["hashed_password"]):
            logger.warning(f"Invalid password for user: {username}")
            return None
        
        # Add default username if missing (for old users)
        if "username" not in user_doc or user_doc["username"] is None:
            user_doc["username"] = user_doc["email"].split("@")[0]
        
        return UserInDB(**user_doc)
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None

async def get_user_by_email(email: str) -> UserInDB:
    """Get user by email"""
    try:
        from app.database import get_collection
        users_collection = await get_collection("users")
        
        user_doc = await users_collection.find_one({"email": email})
        if not user_doc:
            return None
        
        return UserInDB(**user_doc)
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None

async def get_user_by_id(user_id: str) -> UserInDB:
    """Get user by ID"""
    try:
        from app.database import get_collection
        users_collection = await get_collection("users")
        
        if not ObjectId.is_valid(user_id):
            return None
        
        user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            return None
        
        return UserInDB(**user_doc)
    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        return None

async def get_current_user_from_token(token: str, db: AsyncIOMotorDatabase = None) -> dict:
    """Get current user from JWT token"""
    try:
        # Verify and decode token
        payload = verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # ✅ FIXED: Check database parameter properly
        if db is None:
            from app.database import get_collection
            users_collection = await get_collection("users")
        else:
            users_collection = db.users
        
        if not ObjectId.is_valid(user_id):
            return None
        
        user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            return None
        
        # Convert ObjectId to string for JSON serialization
        user_doc["_id"] = str(user_doc["_id"])
        
        return user_doc
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None