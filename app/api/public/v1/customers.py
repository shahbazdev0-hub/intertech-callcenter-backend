# backend/app/api/public/v1/customers.py
"""
Public Customer API Endpoints - For external CRM integration
Uses API Key authentication instead of JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List

from app.api.deps import get_api_key_user
from app.schemas.customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatsResponse
)
from app.services.customer import customer_service

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def check_permission(user: dict, required_permission: str):
    """Check if API key has required permission"""
    api_key = user.get("_api_key", {})
    permissions = api_key.get("permissions", [])
    
    if required_permission not in permissions and "admin" not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have '{required_permission}' permission"
        )


def check_scope(user: dict, required_scope: str):
    """Check if API key has access to required scope"""
    api_key = user.get("_api_key", {})
    scopes = api_key.get("scopes", [])
    
    if required_scope not in scopes and "all" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have access to '{required_scope}' scope"
        )


@router.get("/customers", response_model=CustomerListResponse)
async def get_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    current_user: dict = Depends(get_api_key_user)
):
    """
    Get paginated list of customers
    
    Requires: read permission, customers scope
    """
    check_permission(current_user, "read")
    check_scope(current_user, "customers")
    
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.get_customers(
            user_id=user_id,
            page=page,
            limit=limit,
            search=search
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Public API - Error getting customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/customers/stats", response_model=CustomerStatsResponse)
async def get_customer_stats(
    current_user: dict = Depends(get_api_key_user)
):
    """
    Get customer statistics
    
    Requires: read permission, customers scope
    """
    check_permission(current_user, "read")
    check_scope(current_user, "customers")
    
    try:
        user_id = str(current_user["_id"])
        stats = await customer_service.get_stats(user_id)
        return stats
        
    except Exception as e:
        logger.error(f"❌ Public API - Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_api_key_user)
):
    """
    Get a single customer by ID
    
    Requires: read permission, customers scope
    """
    check_permission(current_user, "read")
    check_scope(current_user, "customers")
    
    try:
        user_id = str(current_user["_id"])
        
        customer = await customer_service.get_customer(customer_id, user_id)
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        return customer
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Public API - Error getting customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/customers", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: dict = Depends(get_api_key_user)
):
    """
    Create a new customer
    
    Requires: write permission, customers scope
    """
    check_permission(current_user, "write")
    check_scope(current_user, "customers")
    
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.create_customer(
            user_id=user_id,
            name=customer_data.name,
            email=customer_data.email,
            phone=customer_data.phone,
            company=customer_data.company,
            address=customer_data.address,
            tags=customer_data.tags,
            notes=customer_data.notes
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create customer")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Public API - Error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/appointments")
async def get_appointments(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_api_key_user)
):
    """
    Get paginated list of appointments
    
    Requires: read permission, appointments scope
    """
    check_permission(current_user, "read")
    check_scope(current_user, "appointments")
    
    try:
        from app.services.appointment import appointment_service
        
        user_id = str(current_user["_id"])
        
        result = await appointment_service.get_appointments(
            user_id=user_id,
            skip=(page - 1) * limit,
            limit=limit,
            status_filter=status_filter
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Public API - Error getting appointments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )