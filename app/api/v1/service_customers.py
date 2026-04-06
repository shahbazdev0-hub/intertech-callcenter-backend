"""
Service Customers API — Actual customers who use our services
Separate from CRM/RBAC customers module
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
import logging
import csv
import io

from app.api.deps import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "service_customers"


# ============================================
# SCHEMAS
# ============================================

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list] = []


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list] = None


def _fmt(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "phone": doc.get("phone", ""),
        "address": doc.get("address", ""),
        "city": doc.get("city", ""),
        "state": doc.get("state", ""),
        "zip_code": doc.get("zip_code", ""),
        "company": doc.get("company", ""),
        "notes": doc.get("notes", ""),
        "tags": doc.get("tags", []),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


# ============================================
# LIST
# ============================================

@router.get("/")
async def list_customers(
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
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
                {"company": {"$regex": search, "$options": "i"}},
            ]
        if tag:
            query["tags"] = tag

        total = await db[COLLECTION].count_documents(query)
        cursor = db[COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return {
            "customers": [_fmt(d) for d in docs],
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit,
        }
    except Exception as e:
        logger.error(f"Error listing service customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# STATS
# ============================================

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        total = await db[COLLECTION].count_documents({"user_id": user_id})
        with_email = await db[COLLECTION].count_documents({"user_id": user_id, "email": {"$ne": ""}})
        with_phone = await db[COLLECTION].count_documents({"user_id": user_id, "phone": {"$ne": ""}})
        return {"total": total, "with_email": with_email, "with_phone": with_phone}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CREATE
# ============================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        doc = {
            "user_id": user_id,
            "name": data.name,
            "email": data.email or "",
            "phone": data.phone or "",
            "address": data.address or "",
            "city": data.city or "",
            "state": data.state or "",
            "zip_code": data.zip_code or "",
            "company": data.company or "",
            "notes": data.notes or "",
            "tags": data.tags or [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await db[COLLECTION].insert_one(doc)
        return {"success": True, "id": str(result.inserted_id), "message": "Customer created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET ONE
# ============================================

@router.get("/{customer_id}")
async def get_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        doc = await db[COLLECTION].find_one({"_id": ObjectId(customer_id), "user_id": user_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Customer not found")
        return _fmt(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE
# ============================================

@router.put("/{customer_id}")
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        update_data = data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        result = await db[COLLECTION].update_one(
            {"_id": ObjectId(customer_id), "user_id": user_id},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Customer not found")

        updated = await db[COLLECTION].find_one({"_id": ObjectId(customer_id)})
        return _fmt(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DELETE
# ============================================

@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        result = await db[COLLECTION].delete_one({"_id": ObjectId(customer_id), "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"success": True, "message": "Customer deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# BULK DELETE
# ============================================

@router.post("/bulk-delete")
async def bulk_delete(
    ids: list[str],
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        object_ids = [ObjectId(i) for i in ids]
        result = await db[COLLECTION].delete_many({
            "_id": {"$in": object_ids},
            "user_id": user_id
        })
        return {"success": True, "deleted": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CSV IMPORT
# ============================================

@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        content = await file.read()
        text = content.decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))

        docs = []
        skipped = 0
        now = datetime.utcnow()

        # Normalize header names
        for row in reader:
            normalized = {k.strip().lower().replace(' ', '_'): v.strip() for k, v in row.items() if v}
            name = (
                normalized.get('name') or
                normalized.get('customer_name') or
                normalized.get('full_name') or
                f"{normalized.get('first_name', '')} {normalized.get('last_name', '')}".strip()
            )
            if not name:
                skipped += 1
                continue

            docs.append({
                "user_id": user_id,
                "name": name,
                "email": normalized.get('email') or normalized.get('email_address') or "",
                "phone": normalized.get('phone') or normalized.get('phone_number') or normalized.get('mobile') or "",
                "address": normalized.get('address') or normalized.get('street') or "",
                "city": normalized.get('city') or "",
                "state": normalized.get('state') or normalized.get('province') or "",
                "zip_code": normalized.get('zip_code') or normalized.get('zip') or normalized.get('postal_code') or "",
                "company": normalized.get('company') or normalized.get('company_name') or normalized.get('organization') or "",
                "notes": normalized.get('notes') or normalized.get('note') or "",
                "tags": [t.strip() for t in (normalized.get('tags') or "").split(',') if t.strip()],
                "created_at": now,
                "updated_at": now,
            })

        imported = 0
        if docs:
            result = await db[COLLECTION].insert_many(docs)
            imported = len(result.inserted_ids)

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "message": f"Imported {imported} customers, skipped {skipped} rows"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CSV EXPORT
# ============================================

@router.get("/export/csv")
async def export_csv(current_user: dict = Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        cursor = db[COLLECTION].find({"user_id": user_id}).sort("created_at", -1)
        docs = await cursor.to_list(length=10000)

        output = io.StringIO()
        headers = ["Name", "Email", "Phone", "Address", "City", "State", "Zip Code", "Company", "Notes", "Tags"]
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for doc in docs:
            writer.writerow({
                "Name": doc.get("name", ""),
                "Email": doc.get("email", ""),
                "Phone": doc.get("phone", ""),
                "Address": doc.get("address", ""),
                "City": doc.get("city", ""),
                "State": doc.get("state", ""),
                "Zip Code": doc.get("zip_code", ""),
                "Company": doc.get("company", ""),
                "Notes": doc.get("notes", ""),
                "Tags": ", ".join(doc.get("tags", [])),
            })

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=customers_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
