# # backend/app/services/auth.py orginal file 
# from datetime import datetime, timedelta
# from app.database import get_collection
# from app.models.user import UserInDB
# from app.schemas.user import UserCreate
# from app.core.security import get_password_hash, create_verification_token
# from app.services.email import email_service
# from bson import ObjectId
# from typing import Optional
# import logging

# logger = logging.getLogger(__name__)

# class AuthService:
#     def __init__(self):
#         pass

#     async def create_user(self, user_data: UserCreate) -> Optional[UserInDB]:
#         """Create a new user"""
#         try:
#             users_collection = await get_collection("users")
            
#             # Check if user already exists
#             existing_user = await users_collection.find_one({"email": user_data.email})
#             if existing_user:
#                 logger.warning(f"User already exists: {user_data.email}")
#                 return None

#             # Validate password length before hashing
#             if len(user_data.password.encode('utf-8')) > 200:  # Reasonable limit
#                 logger.error("Password too long")
#                 raise ValueError("Password is too long")

#             # Create verification token
#             verification_token = create_verification_token(user_data.email)

#             # Hash password with length check
#             try:
#                 hashed_password = get_password_hash(user_data.password)
#             except Exception as e:
#                 logger.error(f"Password hashing failed: {str(e)}")
#                 raise ValueError("Password hashing failed")

#             # Create user document
#             user_doc = {
#                 "email": user_data.email,
#                 "full_name": user_data.full_name,
#                 "company": user_data.company,
#                 "phone": user_data.phone,
#                 "hashed_password": hashed_password,
#                 "is_active": True,
#                 "is_verified": False,
#                 "is_admin": False,
#                 "subscription_plan": "free",
#                 "verification_token": verification_token,
#                 "created_at": datetime.utcnow(),
#                 "updated_at": datetime.utcnow()
#             }

#             # Insert user
#             result = await users_collection.insert_one(user_doc)
#             if result.inserted_id:
#                 # Send verification email (async, don't wait for it)
#                 try:
#                     await email_service.send_verification_email(
#                         user_data.email, verification_token
#                     )
#                 except Exception as e:
#                     logger.warning(f"Failed to send verification email: {str(e)}")
#                     # Don't fail user creation if email fails
                
#                 # Return user with correct ID
#                 user_doc["_id"] = str(result.inserted_id)
#                 user_doc["id"] = str(result.inserted_id)
#                 return UserInDB(**user_doc)
            
#             return None

#         except ValueError as e:
#             # Re-raise value errors (these are expected errors)
#             logger.error(f"Validation error creating user: {str(e)}")
#             raise e
#         except Exception as e:
#             logger.error(f"Unexpected error creating user: {str(e)}")
#             return None

#     async def verify_user_email(self, token: str) -> bool:
#         """Verify user email with token"""
#         try:
#             from app.core.security import decode_token
            
#             payload = decode_token(token)
#             if not payload or payload.get("type") != "verification":
#                 return False

#             email = payload.get("sub")
#             if not email:
#                 return False

#             users_collection = await get_collection("users")
#             result = await users_collection.update_one(
#                 {"email": email, "verification_token": token},
#                 {
#                     "$set": {
#                         "is_verified": True,
#                         "updated_at": datetime.utcnow()
#                     },
#                     "$unset": {"verification_token": ""}
#                 }
#             )

#             return result.modified_count > 0

#         except Exception as e:
#             logger.error(f"Error verifying email: {str(e)}")
#             return False

# # Create the auth_service instance at the end of the file
# auth_service = AuthService()   


# backend/app/services/auth.py orginal file 
from datetime import datetime, timedelta
from app.database import get_collection
from app.models.user import UserInDB
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, create_verification_token
from app.services.email import email_service
from bson import ObjectId
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        pass

    async def create_user(self, user_data: UserCreate) -> Optional[UserInDB]:
        """Create a new user"""
        try:
            users_collection = await get_collection("users")
            
            # Check if user already exists
            existing_user = await users_collection.find_one({"email": user_data.email})
            if existing_user:
                logger.warning(f"User already exists: {user_data.email}")
                return None
            
            # Check for duplicate username
            existing_username = await users_collection.find_one({"username": user_data.username})
            if existing_username:
                logger.warning(f"Username already exists: {user_data.username}")
                return None

            # Validate password length before hashing
            if len(user_data.password.encode('utf-8')) > 200:  # Reasonable limit
                logger.error("Password too long")
                raise ValueError("Password is too long")

            # Create verification token
            verification_token = create_verification_token(user_data.email)

            # Hash password with length check
            try:
                hashed_password = get_password_hash(user_data.password)
            except Exception as e:
                logger.error(f"Password hashing failed: {str(e)}")
                raise ValueError("Password hashing failed")

            # Create user document
            user_doc = {
                "email": user_data.email,
                "username": user_data.username,
                "full_name": user_data.full_name,
                "company": user_data.company,
                "phone": user_data.phone,
                "hashed_password": hashed_password,
                "is_active": True,
                "is_verified": False,
                "is_admin": False,
                "subscription_plan": "free",
                "verification_token": verification_token,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert user
            result = await users_collection.insert_one(user_doc)
            if result.inserted_id:
                # Send verification email (async, don't wait for it)
                try:
                    await email_service.send_verification_email(
                        user_data.email, verification_token
                    )
                except Exception as e:
                    logger.warning(f"Failed to send verification email: {str(e)}")
                    # Don't fail user creation if email fails
                
                # Return user with correct ID
                user_doc["_id"] = str(result.inserted_id)
                user_doc["id"] = str(result.inserted_id)
                return UserInDB(**user_doc)
            
            return None

        except ValueError as e:
            # Re-raise value errors (these are expected errors)
            logger.error(f"Validation error creating user: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error creating user: {str(e)}")
            return None

    async def verify_user_email(self, token: str) -> bool:
        """Verify user email with token"""
        try:
            from app.core.security import decode_token
            
            payload = decode_token(token)
            if not payload or payload.get("type") != "verification":
                return False

            email = payload.get("sub")
            if not email:
                return False

            users_collection = await get_collection("users")
            result = await users_collection.update_one(
                {"email": email, "verification_token": token},
                {
                    "$set": {
                        "is_verified": True,
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {"verification_token": ""}
                }
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error verifying email: {str(e)}")
            return False

# Create the auth_service instance at the end of the file
auth_service = AuthService()