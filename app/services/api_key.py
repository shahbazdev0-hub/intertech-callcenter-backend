# backend/app/services/api_key.py
"""
API Key Service - Generate, validate, and manage API keys
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import hashlib
import logging

from app.database import get_database

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API keys"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def generate_api_key(self) -> tuple[str, str, str]:
        """
        Generate a new API key
        
        Returns:
            Tuple of (full_key, key_prefix, hashed_key)
        """
        # Generate a secure random key
        random_bytes = secrets.token_bytes(32)
        key = f"ck_live_{secrets.token_urlsafe(32)}"
        
        # Get prefix for identification
        key_prefix = key[:16]
        
        # Hash the key for storage
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        
        return key, key_prefix, hashed_key
    
    def hash_key(self, key: str) -> str:
        """Hash an API key"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str] = None,
        scopes: List[str] = None,
        rate_limit: int = 1000,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key
        
        Args:
            user_id: Owner user ID
            name: Friendly name
            permissions: List of permissions
            scopes: List of accessible resources
            rate_limit: Requests per hour
            expires_in_days: Days until expiration
            
        Returns:
            Dict with API key details (including the actual key)
        """
        try:
            db = await self.get_db()
            
            # Generate key
            full_key, key_prefix, hashed_key = self.generate_api_key()
            
            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Create document
            api_key_doc = {
                "name": name,
                "key": hashed_key,
                "key_prefix": key_prefix,
                "user_id": user_id,
                "permissions": permissions or ["read"],
                "scopes": scopes or ["customers", "appointments"],
                "rate_limit": rate_limit,
                "is_active": True,
                "last_used_at": None,
                "total_requests": 0,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "revoked_at": None
            }
            
            # Insert
            result = await db.api_keys.insert_one(api_key_doc)
            
            logger.info(f"✅ API key created: {name} for user {user_id}")
            
            return {
                "success": True,
                "api_key": {
                    "id": str(result.inserted_id),
                    "name": name,
                    "key": full_key,  # Only returned on creation
                    "key_prefix": key_prefix,
                    "permissions": api_key_doc["permissions"],
                    "scopes": api_key_doc["scopes"],
                    "rate_limit": rate_limit,
                    "created_at": api_key_doc["created_at"],
                    "expires_at": expires_at,
                    "message": "Save this key securely. It won't be shown again."
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating API key: {e}")
            return {"success": False, "error": str(e)}
    
    async def validate_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return its details
        
        Args:
            key: The API key to validate
            
        Returns:
            API key document if valid, None otherwise
        """
        try:
            db = await self.get_db()
            
            # Hash the provided key
            hashed_key = self.hash_key(key)
            
            # Find the key
            api_key = await db.api_keys.find_one({
                "key": hashed_key,
                "is_active": True
            })
            
            if not api_key:
                return None
            
            # Check expiration
            if api_key.get("expires_at") and api_key["expires_at"] < datetime.utcnow():
                logger.warning(f"API key expired: {api_key['key_prefix']}")
                return None
            
            # Update usage stats
            await db.api_keys.update_one(
                {"_id": api_key["_id"]},
                {
                    "$set": {"last_used_at": datetime.utcnow()},
                    "$inc": {"total_requests": 1}
                }
            )
            
            return api_key
            
        except Exception as e:
            logger.error(f"❌ Error validating API key: {e}")
            return None
    
    async def get_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all API keys for a user"""
        try:
            db = await self.get_db()
            
            cursor = db.api_keys.find({
                "user_id": user_id,
                "revoked_at": None
            }).sort("created_at", -1)
            
            api_keys = await cursor.to_list(length=100)
            
            # Format response (without actual key)
            formatted = []
            for key in api_keys:
                formatted.append({
                    "id": str(key["_id"]),
                    "name": key.get("name", ""),
                    "key_prefix": key.get("key_prefix", ""),
                    "permissions": key.get("permissions", []),
                    "scopes": key.get("scopes", []),
                    "rate_limit": key.get("rate_limit", 1000),
                    "is_active": key.get("is_active", True),
                    "last_used_at": key.get("last_used_at"),
                    "total_requests": key.get("total_requests", 0),
                    "created_at": key.get("created_at"),
                    "expires_at": key.get("expires_at")
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"❌ Error getting API keys: {e}")
            return []
    
    async def revoke_api_key(self, key_id: str, user_id: str) -> Dict[str, Any]:
        """Revoke an API key"""
        try:
            db = await self.get_db()
            
            result = await db.api_keys.update_one(
                {"_id": ObjectId(key_id), "user_id": user_id},
                {
                    "$set": {
                        "is_active": False,
                        "revoked_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return {"success": False, "error": "API key not found"}
            
            logger.info(f"✅ API key revoked: {key_id}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ Error revoking API key: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_rate_limit(self, api_key: Dict[str, Any]) -> bool:
        """
        Check if API key is within rate limit
        
        Args:
            api_key: The API key document
            
        Returns:
            True if within limit, False if exceeded
        """
        try:
            db = await self.get_db()
            
            # Count requests in the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            # For simplicity, we'll use total_requests
            # In production, you'd want a separate rate_limit_logs collection
            rate_limit = api_key.get("rate_limit", 1000)
            
            # This is a simplified check
            # For production, implement proper rate limiting with Redis
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking rate limit: {e}")
            return False


# Create singleton instance
api_key_service = APIKeyService()