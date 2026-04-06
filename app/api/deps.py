# backend/app/api/deps.py
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.auth import get_current_user_from_token
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.services.api_key import api_key_service  # ✅ NEW

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get current authenticated user"""
    try:
        user = await get_current_user_from_token(credentials.credentials, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Get current active user"""
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_admin_user(current_user: dict = Depends(get_current_active_user)):
    """Get current admin user"""
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# ✅ ADDED - Alias for admin.py which expects this function name
async def get_current_admin_user(current_user: dict = Depends(get_current_active_user)):
    """Get current admin user - alias for get_admin_user"""
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# ✅ NEW - API Key Authentication for Public API
async def get_api_key_user(
    x_api_key: str = Header(..., description="API Key for authentication")
) -> dict:
    """
    Dependency to authenticate requests using API key
    Returns the user associated with the API key
    """
    # Validate API key
    api_key = await api_key_service.validate_api_key(x_api_key)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    
    # Check rate limit
    if not await api_key_service.check_rate_limit(api_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    # Get the user associated with this API key
    db = await get_database()
    user = await db.users.find_one({"_id": ObjectId(api_key["user_id"])})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Attach API key info to user for permission checking
    user["_api_key"] = api_key
    
    return user