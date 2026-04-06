# backend/app/api/v1/api_keys.py
"""
API Key Management Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.api.deps import get_current_user
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreateResponse,
    APIKeyListResponse
)
from app.services.api_key import api_key_service

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=APIKeyListResponse)
async def get_api_keys(
    current_user: dict = Depends(get_current_user)
):
    """Get all API keys for the current user"""
    try:
        user_id = str(current_user["_id"])
        api_keys = await api_key_service.get_api_keys(user_id)
        
        return {
            "api_keys": api_keys,
            "total": len(api_keys)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new API key"""
    try:
        user_id = str(current_user["_id"])
        
        result = await api_key_service.create_api_key(
            user_id=user_id,
            name=key_data.name,
            permissions=key_data.permissions,
            scopes=key_data.scopes,
            rate_limit=key_data.rate_limit,
            expires_in_days=key_data.expires_in_days
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create API key")
            )
        
        return result["api_key"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Revoke an API key"""
    try:
        user_id = str(current_user["_id"])
        
        result = await api_key_service.revoke_api_key(key_id, user_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "API key not found")
            )
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )