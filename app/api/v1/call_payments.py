# app/api/v1/call_payments.py
"""
Admin API for viewing payment details collected via AI voice calls.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import logging

from app.api.deps import get_current_user, get_database

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize(doc: dict) -> dict:
    """Convert MongoDB ObjectId fields to strings."""
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", summary="List payment details collected via calls")
async def list_call_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    call_id: Optional[str] = Query(None, description="Filter by call_id"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Return all payment details collected for this user's calls, newest first.
    Each record contains: cardholder_name, card_last4, expiry_date, call_sid, collected_at.
    The full card_number and cvc are included for admin review.
    """
    user_id = str(current_user["_id"])

    query: dict = {"user_id": user_id}
    if call_id:
        query["call_id"] = call_id

    cursor = (
        db.call_payment_details
        .find(query)
        .sort("collected_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    total = await db.call_payment_details.count_documents(query)

    return {
        "success": True,
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize(d) for d in docs],
    }


@router.get("/{payment_id}", summary="Get a single payment detail record")
async def get_call_payment(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """Return a single payment-detail record by its ID."""
    user_id = str(current_user["_id"])

    try:
        oid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment_id format")

    doc = await db.call_payment_details.find_one({"_id": oid, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment record not found")

    return {"success": True, "item": _serialize(doc)}


@router.delete("/{payment_id}", summary="Delete a payment detail record")
async def delete_call_payment(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete a payment-detail record."""
    user_id = str(current_user["_id"])

    try:
        oid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment_id format")

    result = await db.call_payment_details.delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payment record not found")

    return {"success": True, "message": "Payment record deleted"}
