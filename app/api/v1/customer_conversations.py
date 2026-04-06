"""
Customer Conversations API
Groups SMS + Email messages by customer into unified conversation threads.
Supports AI auto-categorization and manual status override.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import logging

from app.api.deps import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_STATUSES = ["interested", "not_interested", "job_booked", "closed", "new"]


def _safe_date(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


# ============================================
# GET ALL CONVERSATIONS (grouped by customer)
# ============================================

@router.get("/")
async def list_conversations(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Return one entry per unique customer (phone or email),
    with last message preview, unread count, and conversation status.
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        # ── Fetch recent SMS logs ──────────────────────────────────────
        sms_cursor = db.sms_logs.find(
            {"user_id": user_id},
            {"from_number": 1, "to_number": 1, "message": 1, "direction": 1,
             "created_at": 1, "customer_name": 1, "customer_email": 1}
        ).sort("created_at", -1).limit(2000)
        sms_docs = await sms_cursor.to_list(length=2000)

        # ── Fetch recent Email logs ────────────────────────────────────
        email_cursor = db.email_logs.find(
            {"user_id": user_id},
            {"to_email": 1, "from_email": 1, "subject": 1, "text_content": 1,
             "content": 1, "created_at": 1, "recipient_name": 1, "recipient_phone": 1,
             "direction": 1}
        ).sort("created_at", -1).limit(2000)
        email_docs = await email_cursor.to_list(length=2000)

        # ── Fetch saved conversation statuses ─────────────────────────
        conv_states = {}
        async for cs in db.conversation_statuses.find({"user_id": user_id}):
            conv_states[cs["customer_key"]] = cs

        # ── Group by customer key ──────────────────────────────────────
        customers = {}  # key → { name, phone, email, messages[], last_at, ... }

        for sms in sms_docs:
            # Determine the "other party" phone number
            if sms.get("direction") == "inbound":
                phone = sms.get("from_number", "")
            else:
                phone = sms.get("to_number", "")

            if not phone:
                continue

            key = f"phone:{phone}"
            if key not in customers:
                customers[key] = {
                    "customer_key": key,
                    "phone": phone,
                    "email": sms.get("customer_email", ""),
                    "name": sms.get("customer_name", "") or phone,
                    "last_message": "",
                    "last_message_at": None,
                    "sms_count": 0,
                    "email_count": 0,
                    "channels": [],
                }
            c = customers[key]
            c["sms_count"] += 1
            if "sms" not in c["channels"]:
                c["channels"].append("sms")
            msg_at = sms.get("created_at")
            if not c["last_message_at"] or (msg_at and msg_at > c["last_message_at"]):
                c["last_message_at"] = msg_at
                c["last_message"] = sms.get("message", "")[:120]
                if sms.get("customer_name"):
                    c["name"] = sms["customer_name"]
                if sms.get("customer_email"):
                    c["email"] = sms["customer_email"]

        for em in email_docs:
            email_addr = em.get("to_email", "")
            if not email_addr:
                continue

            # Check if this customer already exists by phone
            matched_key = None
            for k, v in customers.items():
                if v.get("email") == email_addr:
                    matched_key = k
                    break

            key = matched_key or f"email:{email_addr}"
            if key not in customers:
                customers[key] = {
                    "customer_key": key,
                    "phone": em.get("recipient_phone", ""),
                    "email": email_addr,
                    "name": em.get("recipient_name", "") or email_addr,
                    "last_message": "",
                    "last_message_at": None,
                    "sms_count": 0,
                    "email_count": 0,
                    "channels": [],
                }
            c = customers[key]
            c["email_count"] += 1
            if "email" not in c["channels"]:
                c["channels"].append("email")
            msg_at = em.get("created_at")
            if not c["last_message_at"] or (msg_at and msg_at > c["last_message_at"]):
                c["last_message_at"] = msg_at
                preview = em.get("text_content") or em.get("subject", "")
                c["last_message"] = preview[:120]
                if em.get("recipient_name"):
                    c["name"] = em["recipient_name"]
                c["email"] = email_addr

        # ── Merge saved statuses + AI-suggested status ─────────────────
        result = []
        for key, c in customers.items():
            saved = conv_states.get(key, {})
            conv_status = saved.get("status", "new")
            manually_reviewed = saved.get("manually_reviewed", False)

            result.append({
                "customer_key": key,
                "name": c["name"],
                "phone": c["phone"],
                "email": c["email"],
                "last_message": c["last_message"],
                "last_message_at": _safe_date(c["last_message_at"]),
                "sms_count": c["sms_count"],
                "email_count": c["email_count"],
                "channels": c["channels"],
                "status": conv_status,
                "manually_reviewed": manually_reviewed,
                "notes": saved.get("notes", ""),
            })

        # ── Sort by last message ───────────────────────────────────────
        result.sort(key=lambda x: x["last_message_at"] or "", reverse=True)

        # ── Filter ────────────────────────────────────────────────────
        if status:
            result = [r for r in result if r["status"] == status]

        if search:
            s = search.lower()
            result = [r for r in result if
                      s in r["name"].lower() or
                      s in r["phone"].lower() or
                      s in r["email"].lower() or
                      s in r["last_message"].lower()]

        total = len(result)
        result = result[skip: skip + limit]

        return {"conversations": result, "total": total}

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET CONVERSATION THREAD (SMS + Email mixed)
# ============================================

@router.get("/thread")
async def get_conversation_thread(
    customer_key: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Return unified chronological thread of SMS + Email messages for a customer.
    customer_key format: "phone:+1234567890" or "email:user@example.com"
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        key_type, key_value = customer_key.split(":", 1)
        messages = []

        if key_type == "phone":
            sms_cursor = db.sms_logs.find({
                "user_id": user_id,
                "$or": [
                    {"from_number": key_value},
                    {"to_number": key_value}
                ]
            }).sort("created_at", 1)
            sms_docs = await sms_cursor.to_list(length=500)
            for s in sms_docs:
                messages.append({
                    "id": str(s["_id"]),
                    "type": "sms",
                    "direction": s.get("direction", "outbound"),
                    "content": s.get("message", ""),
                    "subject": None,
                    "status": s.get("status", ""),
                    "created_at": _safe_date(s.get("created_at")),
                    "from": s.get("from_number", ""),
                    "to": s.get("to_number", ""),
                })

            # Also get emails if we have email linked
            conv_state = await db.conversation_statuses.find_one({
                "user_id": user_id,
                "customer_key": customer_key
            })
            linked_email = conv_state.get("email", "") if conv_state else ""
            if linked_email:
                email_cursor = db.email_logs.find({
                    "user_id": user_id,
                    "to_email": linked_email
                }).sort("created_at", 1)
                email_docs = await email_cursor.to_list(length=200)
                for e in email_docs:
                    messages.append({
                        "id": str(e["_id"]),
                        "type": "email",
                        "direction": e.get("direction", "outbound"),
                        "content": e.get("text_content") or e.get("content", ""),
                        "subject": e.get("subject", ""),
                        "status": e.get("status", ""),
                        "created_at": _safe_date(e.get("created_at")),
                        "from": e.get("from_email", ""),
                        "to": e.get("to_email", ""),
                    })

        elif key_type == "email":
            email_cursor = db.email_logs.find({
                "user_id": user_id,
                "to_email": key_value
            }).sort("created_at", 1)
            email_docs = await email_cursor.to_list(length=500)
            for e in email_docs:
                messages.append({
                    "id": str(e["_id"]),
                    "type": "email",
                    "direction": e.get("direction", "outbound"),
                    "content": e.get("text_content") or e.get("content", ""),
                    "subject": e.get("subject", ""),
                    "status": e.get("status", ""),
                    "created_at": _safe_date(e.get("created_at")),
                    "from": e.get("from_email", ""),
                    "to": e.get("to_email", ""),
                })

        # Sort all messages chronologically
        messages.sort(key=lambda x: x["created_at"] or "")

        # Get conversation status
        conv_state = await db.conversation_statuses.find_one({
            "user_id": user_id,
            "customer_key": customer_key
        })

        return {
            "messages": messages,
            "status": conv_state.get("status", "new") if conv_state else "new",
            "notes": conv_state.get("notes", "") if conv_state else "",
            "manually_reviewed": conv_state.get("manually_reviewed", False) if conv_state else False,
        }

    except Exception as e:
        logger.error(f"Error getting thread: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE CONVERSATION STATUS (manual review)
# ============================================

from pydantic import BaseModel

class StatusUpdate(BaseModel):
    customer_key: str
    status: str
    notes: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


@router.put("/status")
async def update_conversation_status(
    data: StatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Manually set conversation status + optional notes."""
    try:
        if data.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

        user_id = str(current_user["_id"])
        db = await get_database()

        update_doc = {
            "user_id": user_id,
            "customer_key": data.customer_key,
            "status": data.status,
            "manually_reviewed": True,
            "updated_at": datetime.utcnow(),
        }
        if data.notes is not None:
            update_doc["notes"] = data.notes
        if data.name:
            update_doc["name"] = data.name
        if data.phone:
            update_doc["phone"] = data.phone
        if data.email:
            update_doc["email"] = data.email

        await db.conversation_statuses.update_one(
            {"user_id": user_id, "customer_key": data.customer_key},
            {"$set": update_doc},
            upsert=True
        )

        return {"success": True, "status": data.status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
