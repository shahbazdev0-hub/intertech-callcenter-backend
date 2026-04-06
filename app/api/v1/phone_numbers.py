# backend/app/api/v1/phone_numbers.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional, List
from app.api.deps import get_current_active_user
from app.services.twilio_provisioning import twilio_provisioning_service
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AvailableNumber(BaseModel):
    phone_number: str
    friendly_name: str
    locality: Optional[str] = ""
    region: Optional[str] = ""
    country_code: str


class PurchaseRequest(BaseModel):
    phone_number: str
    country_code: str = "CA"


class PurchaseResponse(BaseModel):
    success: bool
    phone_number: str
    message: str


@router.get("/available", response_model=List[AvailableNumber])
async def search_available_numbers(
    country: str = Query("CA", description="Country code (e.g., CA, US)"),
    area_code: Optional[str] = Query(None, description="Area code filter"),
    current_user: dict = Depends(get_current_active_user),
):
    """Search available Twilio phone numbers. Requires active subscription."""
    plan = current_user.get("subscription_plan", "free")
    if plan == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to search phone numbers",
        )

    if current_user.get("twilio_phone_number"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a phone number provisioned",
        )

    try:
        numbers = await asyncio.to_thread(
            twilio_provisioning_service.search_available_numbers,
            country_code=country,
            area_code=area_code or None,
            limit=20,
        )
        return numbers
    except Exception as e:
        logger.error(f"Error searching phone numbers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search available phone numbers",
        )


@router.post("/purchase", response_model=PurchaseResponse)
async def purchase_phone_number(
    data: PurchaseRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """Purchase a specific phone number. Creates subaccount + buys + configures webhooks."""
    user_id = str(current_user["_id"])
    plan = current_user.get("subscription_plan", "free")

    if plan == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    if current_user.get("twilio_phone_number"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a phone number provisioned",
        )

    try:
        result = await twilio_provisioning_service.provision_user_with_selected_number(
            user_id=user_id,
            phone_number=data.phone_number,
            country_code=data.country_code,
        )
        return PurchaseResponse(
            success=True,
            phone_number=result["twilio_phone_number"],
            message="Phone number provisioned successfully",
        )
    except Exception as e:
        logger.error(f"Error purchasing phone number for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purchase phone number: {str(e)}",
        )
