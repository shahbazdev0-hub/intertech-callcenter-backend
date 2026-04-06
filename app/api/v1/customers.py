# backend/app/api/v1/customers.py
"""
Customer API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from typing import Optional, List
from datetime import datetime

from app.api.deps import get_current_user
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatsResponse,
    AddNoteRequest,
    AddTagsRequest
)
from app.services.customer import customer_service

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=CustomerStatsResponse)
async def get_customer_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get customer statistics"""
    try:
        user_id = str(current_user["_id"])
        stats = await customer_service.get_stats(user_id)
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/export/csv")
async def export_customers_csv(
    search: Optional[str] = None,
    tags: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Export customers to CSV"""
    try:
        user_id = str(current_user["_id"])
        csv_data = await customer_service.export_csv(user_id, search, tags)
        
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=customers_{datetime.now().strftime('%Y%m%d')}.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error exporting CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/import/csv")
async def import_customers_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Import customers from CSV"""
    try:
        import csv, io
        user_id = str(current_user["_id"])

        from app.database import get_database
        db = await get_database()

        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            try:
                name = row.get("Name", "").strip()
                email = row.get("Email", "").strip()
                phone = row.get("Phone", "").strip()

                if not name:
                    errors.append(f"Row {i}: Missing name")
                    continue

                # Check for duplicate by email or phone
                if email:
                    existing = await db.customers.find_one({"user_id": user_id, "email": email})
                    if existing:
                        skipped += 1
                        continue
                if phone:
                    existing = await db.customers.find_one({"user_id": user_id, "phone": phone})
                    if existing:
                        skipped += 1
                        continue

                tags_str = row.get("Tags", "").strip()
                tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

                doc = {
                    "user_id": user_id,
                    "name": name,
                    "email": email or None,
                    "phone": phone or None,
                    "company": row.get("Company", "").strip() or None,
                    "address": row.get("Address", "").strip() or None,
                    "tags": tags,
                    "status": row.get("Status", "active").strip() or "active",
                    "notes": [],
                    "total_appointments": 0,
                    "total_calls": 0,
                    "total_interactions": 0,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                await db.customers.insert_one(doc)
                imported += 1
            except Exception as row_err:
                errors.append(f"Row {i}: {str(row_err)}")

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:20],
            "total_errors": len(errors)
        }

    except Exception as e:
        logger.error(f"Error importing customers CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_customers(
    q: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user)
):
    """Search customers"""
    try:
        user_id = str(current_user["_id"])
        result = await customer_service.get_customers(
            user_id=user_id,
            search=q,
            limit=20
        )
        return result
        
    except Exception as e:
        logger.error(f"❌ Error searching customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=CustomerListResponse)
async def get_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    tags: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: dict = Depends(get_current_user)
):
    """Get paginated list of customers"""
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.get_customers(
            user_id=user_id,
            page=page,
            limit=limit,
            search=search,
            tags=tags,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new customer"""
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
            notes=customer_data.notes,
            role=customer_data.role,
            password=customer_data.password,
            allowed_services=customer_data.allowed_services
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
        logger.error(f"❌ Error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single customer by ID"""
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
        logger.error(f"❌ Error getting customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{customer_id}", response_model=dict)
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a customer"""
    try:
        user_id = str(current_user["_id"])

        update_dict = customer_data.dict(exclude_unset=True)
        print(f"📝 [CUSTOMER-UPDATE] customer_id={customer_id}, payload={update_dict}")
        logger.info(f"📝 [CUSTOMER-UPDATE] customer_id={customer_id}, payload={update_dict}")

        result = await customer_service.update_customer(
            customer_id=customer_id,
            user_id=user_id,
            update_data=update_dict
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update customer")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a customer"""
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.delete_customer(customer_id, user_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Customer not found")
            )
        
        return {"message": "Customer deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{customer_id}/appointments")
async def get_customer_appointments(
    customer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get appointments for a customer"""
    try:
        user_id = str(current_user["_id"])
        result = await customer_service.get_customer_appointments(customer_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting appointments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{customer_id}/calls")
async def get_customer_calls(
    customer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get call history for a customer"""
    try:
        user_id = str(current_user["_id"])
        result = await customer_service.get_customer_calls(customer_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting calls: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{customer_id}/timeline")
async def get_customer_timeline(
    customer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get interaction timeline for a customer"""
    try:
        user_id = str(current_user["_id"])
        result = await customer_service.get_customer_timeline(customer_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting timeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{customer_id}/notes")
async def add_customer_note(
    customer_id: str,
    note_data: AddNoteRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add or update note for a customer"""
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.add_note(
            customer_id=customer_id,
            user_id=user_id,
            note=note_data.note
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to add note")
            )
        
        return {"message": "Note added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding note: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{customer_id}/tags")
async def add_customer_tags(
    customer_id: str,
    tags_data: AddTagsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add tags to a customer"""
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.add_tags(
            customer_id=customer_id,
            user_id=user_id,
            tags=tags_data.tags
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to add tags")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding tags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{customer_id}/tags/{tag}")
async def remove_customer_tag(
    customer_id: str,
    tag: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a tag from a customer"""
    try:
        user_id = str(current_user["_id"])
        
        result = await customer_service.remove_tag(
            customer_id=customer_id,
            user_id=user_id,
            tag=tag
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to remove tag")
            )
        
        return {"message": "Tag removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing tag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )