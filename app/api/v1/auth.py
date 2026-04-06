from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
import traceback
from app.schemas.auth import Token, UserLogin, PasswordReset, PasswordResetConfirm, EmailVerification
from app.schemas.user import UserCreate, UserResponse
from app.core.auth import authenticate_user, get_user_by_email
from app.core.security import create_access_token, create_reset_token, decode_token, get_password_hash
from app.services.auth import auth_service
from app.services.email import email_service
from app.database import get_collection
from app.config import settings
from app.utils.helpers import format_user_response
from app.api.deps import get_current_active_user, get_current_user
from app.models.user import UserInDB

router = APIRouter()
security = HTTPBearer()

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate):
    """Register a new user and automatically log them in"""
    try:
        print(f"Registration attempt for: {user_data.email}")
        print(f"Password length: {len(user_data.password)} characters")

        # Check password length before processing
        if len(user_data.password) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is too long. Maximum 100 characters allowed."
            )

        if user_data.company and len(user_data.company) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name cannot exceed 100 characters"
            )

        user = await auth_service.create_user(user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        print(f"User created successfully: {user.email}")

        # Auto-login the user by creating access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        )

        # Update last login timestamp
        users_collection = await get_collection("users")
        await users_collection.update_one(
            {"_id": user.id},
            {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )

        # Re-fetch raw document so integration_config is included
        raw_user = await users_collection.find_one({"_id": user.id})
        raw_user["_id"] = str(raw_user["_id"])

        print(f"Auto-login token created for: {user.email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": format_user_response(raw_user)
        }

    except HTTPException:
        raise
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Registration error: {str(e)}")
        print(f"Registration traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate):
    """Register a new user (alias for register)"""
    return await register(user_data)

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Login user and return access token"""
    try:
        print(f"Login attempt for: {user_credentials.username}")

        user = await authenticate_user(user_credentials.username, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is deactivated"
            )

        # Update last login
        users_collection = await get_collection("users")
        await users_collection.update_one(
            {"_id": user.id},
            {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )

        # Re-fetch raw document so integration_config is included
        raw_user = await users_collection.find_one({"_id": user.id})
        raw_user["_id"] = str(raw_user["_id"])

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        )

        print(f"Login successful for: {user.email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": format_user_response(raw_user)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        print(f"Login traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """Get current user info"""
    try:
        if isinstance(current_user, dict):
            user_email = current_user.get("email", "unknown")
            print(f"Getting user info for: {user_email}")
            return format_user_response(current_user)
        else:
            print(f"Getting user info for: {current_user.email}")
            return format_user_response(current_user.dict() if hasattr(current_user, 'dict') else current_user)
    except Exception as e:
        print(f"Error getting current user: {str(e)}")
        return {
            "id": current_user.get("_id", ""),
            "email": current_user.get("email", ""),
            "first_name": current_user.get("first_name", ""),
            "last_name": current_user.get("last_name", ""),
            "phone": current_user.get("phone", ""),
            "company_name": current_user.get("company_name", ""),
            "is_active": current_user.get("is_active", True),
            "is_verified": current_user.get("is_verified", False),
            "subscription_plan": current_user.get("subscription_plan", "free"),
            "twilio_phone_number": current_user.get("twilio_phone_number"),
            "created_at": current_user.get("created_at", ""),
            "last_login": current_user.get("last_login", "")
        }

@router.post("/logout")
async def logout():
    """Logout user"""
    return {"message": "Logged out successfully"}

@router.post("/refresh")
async def refresh_token():
    """Refresh access token"""
    # TODO: Implement refresh token logic
    return {"message": "Token refresh endpoint - TODO: Implement"}

@router.post("/verify-email")
async def verify_email(verification_data: EmailVerification):
    """Verify user email"""
    success = await auth_service.verify_user_email(verification_data.token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    return {"message": "Email verified successfully"}

@router.post("/forgot-password")
async def forgot_password(reset_data: PasswordReset):
    """Request password reset"""
    user = await get_user_by_email(reset_data.email)
    if not user:
        return {"message": "If the email exists, a reset link has been sent"}

    reset_token = create_reset_token(user.email)
    reset_expires = datetime.utcnow() + timedelta(hours=1)

    users_collection = await get_collection("users")
    await users_collection.update_one(
        {"_id": user.id},
        {
            "$set": {
                "reset_token": reset_token,
                "reset_token_expires": reset_expires,
                "updated_at": datetime.utcnow()
            }
        }
    )

    await email_service.send_password_reset_email(user.email, reset_token)

    return {"message": "If the email exists, a reset link has been sent"}

@router.post("/reset-password")
async def reset_password(reset_data: PasswordResetConfirm):
    """Reset password with token"""
    payload = decode_token(reset_data.token)
    if not payload or payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token"
        )

    users_collection = await get_collection("users")
    user_doc = await users_collection.find_one({
        "email": email,
        "reset_token": reset_data.token,
        "reset_token_expires": {"$gt": datetime.utcnow()}
    })

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    new_hashed_password = get_password_hash(reset_data.new_password)
    await users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "hashed_password": new_hashed_password,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "reset_token": "",
                "reset_token_expires": ""
            }
        }
    )

    return {"message": "Password reset successfully"}