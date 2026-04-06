"""
Jobs API — Job scheduling and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
import logging

from app.api.deps import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "jobs"


# ============================================
# SCHEMAS
# ============================================

class AddressSchema(BaseModel):
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


class JobCreate(BaseModel):
    technician_id: str = Field(..., min_length=1)
    services: List[str] = Field(..., min_length=1)
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    duration: int = 60  # minutes
    priority: str = "normal"  # low, normal, high, urgent
    address: AddressSchema = AddressSchema()
    notes: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    status: str = "not_started"


class JobUpdate(BaseModel):
    technician_id: Optional[str] = None
    services: Optional[List[str]] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    duration: Optional[int] = None
    priority: Optional[str] = None
    address: Optional[AddressSchema] = None
    notes: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    status: Optional[str] = None


def _fmt(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "technician_id": doc.get("technician_id", ""),
        "technician_name": doc.get("technician_name", ""),
        "services": doc.get("services", []),
        "date": doc.get("date").isoformat() if isinstance(doc.get("date"), datetime) else doc.get("date", ""),
        "start_time": doc.get("start_time", ""),
        "duration": doc.get("duration", 60),
        "priority": doc.get("priority", "normal"),
        "status": doc.get("status", "not_started"),
        "address": doc.get("address", {}),
        "notes": doc.get("notes", ""),
        "customer_name": doc.get("customer_name", ""),
        "customer_phone": doc.get("customer_phone", ""),
        "customer_email": doc.get("customer_email", ""),
        "user_id": str(doc.get("user_id", "")),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


# ============================================
# LIST JOBS
# ============================================

@router.get("/")
async def list_jobs(
    technician_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        query = {"user_id": user_id}
        if technician_id:
            query["technician_id"] = technician_id
        if status_filter:
            query["status"] = status_filter
        if priority:
            query["priority"] = priority
        if search:
            query["$or"] = [
                {"customer_name": {"$regex": search, "$options": "i"}},
                {"technician_name": {"$regex": search, "$options": "i"}},
                {"notes": {"$regex": search, "$options": "i"}},
            ]
        if date_from:
            query.setdefault("date", {})["$gte"] = date_from
        if date_to:
            query.setdefault("date", {})["$lte"] = date_to

        total = await db[COLLECTION].count_documents(query)
        cursor = db[COLLECTION].find(query).sort([("date", 1), ("start_time", 1)]).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return {"jobs": [_fmt(d) for d in docs], "total": total}
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# STATS
# ============================================

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        base = {"user_id": user_id}
        total = await db[COLLECTION].count_documents(base)
        not_started = await db[COLLECTION].count_documents({**base, "status": "not_started"})
        in_progress = await db[COLLECTION].count_documents({**base, "status": "in_progress"})
        completed = await db[COLLECTION].count_documents({**base, "status": "completed"})
        cancelled = await db[COLLECTION].count_documents({**base, "status": "cancelled"})
        return {
            "total": total, "not_started": not_started,
            "in_progress": in_progress, "completed": completed, "cancelled": cancelled,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CREATE JOB
# ============================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        # Get technician name
        tech = await db.technicians.find_one({"_id": ObjectId(data.technician_id)})
        tech_name = tech.get("name", "") if tech else ""

        valid_priorities = ["low", "normal", "high", "urgent"]
        if data.priority not in valid_priorities:
            raise HTTPException(status_code=400, detail=f"Priority must be one of: {valid_priorities}")

        doc = {
            "user_id": user_id,
            "technician_id": data.technician_id,
            "technician_name": tech_name,
            "services": data.services,
            "date": data.date,
            "start_time": data.start_time,
            "duration": data.duration,
            "priority": data.priority,
            "status": data.status or "not_started",
            "address": data.address.model_dump(),
            "notes": data.notes or "",
            "customer_name": data.customer_name or "",
            "customer_phone": data.customer_phone or "",
            "customer_email": data.customer_email or "",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await db[COLLECTION].insert_one(doc)
        return {"success": True, "id": str(result.inserted_id), "message": "Job created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET / UPDATE / DELETE
# ============================================

@router.get("/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        doc = await db[COLLECTION].find_one({"_id": ObjectId(job_id), "user_id": user_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Job not found")
        return _fmt(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{job_id}")
async def update_job(
    job_id: str,
    data: JobUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        update_data = data.model_dump(exclude_unset=True)

        if "address" in update_data and update_data["address"] is not None:
            update_data["address"] = update_data["address"] if isinstance(update_data["address"], dict) else update_data["address"].model_dump()

        # Update technician name if changed
        if "technician_id" in update_data:
            tech = await db.technicians.find_one({"_id": ObjectId(update_data["technician_id"])})
            update_data["technician_name"] = tech.get("name", "") if tech else ""

        update_data["updated_at"] = datetime.utcnow()

        result = await db[COLLECTION].update_one(
            {"_id": ObjectId(job_id), "user_id": user_id},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")

        updated = await db[COLLECTION].find_one({"_id": ObjectId(job_id)})
        return _fmt(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(job_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        result = await db[COLLECTION].delete_one({"_id": ObjectId(job_id), "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"success": True, "message": "Job deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
