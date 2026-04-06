"""
Technicians API — Manage technicians and their portal access
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
import logging

from app.api.deps import get_current_user
from app.database import get_database
from app.core.security import get_password_hash, verify_password, create_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "technicians"


# ============================================
# SCHEMAS
# ============================================

class TechnicianCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None
    services: List[str] = []
    is_active: bool = True


class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    services: Optional[List[str]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class TechnicianLogin(BaseModel):
    email: str
    password: str


def _safe_date(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


def _fmt(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "phone": doc.get("phone", ""),
        "services": doc.get("services", []),
        "is_active": doc.get("is_active", True),
        "user_id": str(doc.get("user_id", "")),
        "created_at": _safe_date(doc.get("created_at")),
        "updated_at": _safe_date(doc.get("updated_at")),
    }


# ============================================
# TECHNICIAN PORTAL LOGIN (no auth required)
# ============================================

@router.post("/login")
async def technician_login(data: TechnicianLogin):
    """Login for technicians to access their portal"""
    try:
        db = await get_database()
        tech = await db[COLLECTION].find_one({"email": data.email.lower().strip()})
        if not tech:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(data.password, tech.get("hashed_password", "")):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not tech.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is disabled")

        token = create_access_token(subject=str(tech["_id"]))
        return {
            "access_token": token,
            "token_type": "bearer",
            "technician": _fmt(tech)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Technician login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# TECHNICIAN PORTAL - GET MY JOBS
# ============================================

@router.get("/portal/jobs")
async def get_my_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    tech_token: str = Query(..., alias="token")
):
    """Get jobs assigned to the logged-in technician"""
    try:
        from app.core.security import decode_token
        db = await get_database()

        payload = decode_token(tech_token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")

        tech_id = payload.get("sub")
        tech = await db[COLLECTION].find_one({"_id": ObjectId(tech_id)})
        if not tech:
            raise HTTPException(status_code=401, detail="Technician not found")

        query = {"technician_id": str(tech["_id"])}
        if status_filter:
            query["status"] = status_filter

        cursor = db.jobs.find(query).sort("date", 1)
        jobs = await cursor.to_list(length=100)

        return {
            "technician": _fmt(tech),
            "jobs": [{
                "id": str(j["_id"]),
                "services": j.get("services", []),
                "date": _safe_date(j.get("date")),
                "start_time": j.get("start_time", ""),
                "duration": j.get("duration", 60),
                "priority": j.get("priority", "normal"),
                "status": j.get("status", "not_started"),
                "address": j.get("address", {}),
                "notes": j.get("notes", ""),
                "customer_name": j.get("customer_name", ""),
                "customer_phone": j.get("customer_phone", ""),
                "created_at": _safe_date(j.get("created_at")),
            } for j in jobs]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portal jobs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# TECHNICIAN PORTAL - UPDATE JOB STATUS
# ============================================

class JobStatusUpdate(BaseModel):
    status: str  # not_started, in_progress, completed, cancelled


@router.put("/portal/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    data: JobStatusUpdate,
    tech_token: str = Query(..., alias="token")
):
    """Technician updates their job status"""
    try:
        from app.core.security import decode_token
        db = await get_database()

        payload = decode_token(tech_token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")

        tech_id = payload.get("sub")

        valid_statuses = ["not_started", "in_progress", "completed", "cancelled"]
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

        result = await db.jobs.update_one(
            {"_id": ObjectId(job_id), "technician_id": tech_id},
            {"$set": {"status": data.status, "updated_at": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"success": True, "message": f"Job status updated to {data.status}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ADMIN - LIST TECHNICIANS
# ============================================

@router.get("/")
async def list_technicians(
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        query = {"user_id": user_id}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
            ]
        total = await db[COLLECTION].count_documents(query)
        cursor = db[COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return {"technicians": [_fmt(d) for d in docs], "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ADMIN - CREATE TECHNICIAN
# ============================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_technician(
    data: TechnicianCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        # Check duplicate email
        existing = await db[COLLECTION].find_one({"email": data.email.lower().strip()})
        if existing:
            raise HTTPException(status_code=400, detail="A technician with this email already exists")

        doc = {
            "user_id": user_id,
            "name": data.name,
            "email": data.email.lower().strip(),
            "hashed_password": get_password_hash(data.password),
            "phone": data.phone or "",
            "services": data.services or [],
            "is_active": data.is_active,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await db[COLLECTION].insert_one(doc)
        return {"success": True, "id": str(result.inserted_id), "message": "Technician created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ADMIN - GET / UPDATE / DELETE
# ============================================

@router.get("/{tech_id}")
async def get_technician(tech_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        doc = await db[COLLECTION].find_one({"_id": ObjectId(tech_id), "user_id": user_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Technician not found")
        return _fmt(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tech_id}")
async def update_technician(
    tech_id: str,
    data: TechnicianUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        update_data = data.model_dump(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        else:
            update_data.pop("password", None)

        if "email" in update_data:
            update_data["email"] = update_data["email"].lower().strip()

        update_data["updated_at"] = datetime.utcnow()

        result = await db[COLLECTION].update_one(
            {"_id": ObjectId(tech_id), "user_id": user_id},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Technician not found")

        updated = await db[COLLECTION].find_one({"_id": ObjectId(tech_id)})
        return _fmt(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tech_id}")
async def delete_technician(tech_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        result = await db[COLLECTION].delete_one({"_id": ObjectId(tech_id), "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Technician not found")
        return {"success": True, "message": "Technician deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
