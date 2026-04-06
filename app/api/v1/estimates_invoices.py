"""
Estimates & Invoices API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field
import logging

from app.api.deps import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class LineItem(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float = 0
    amount: float = 0  # quantity * unit_price


class DocumentCreate(BaseModel):
    """Create an estimate or invoice"""
    doc_type: str = Field(..., pattern=r"^(estimate|invoice)$")
    title: str = Field(..., min_length=1, max_length=200)
    customer_name: str = Field(..., min_length=1)
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None

    items: List[LineItem] = []
    subtotal: float = 0
    tax_rate: float = 0  # percentage
    tax_amount: float = 0
    discount: float = 0  # flat discount amount
    discount_type: str = "flat"  # "flat" or "percent"
    total: float = 0

    notes: Optional[str] = None
    terms: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "draft"  # draft, sent, accepted, declined, paid, overdue


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    items: Optional[List[LineItem]] = None
    subtotal: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    discount: Optional[float] = None
    discount_type: Optional[str] = None
    total: Optional[float] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None


def _format_doc(doc: dict) -> dict:
    """Format a MongoDB document for JSON response"""
    return {
        "id": str(doc["_id"]),
        "doc_type": doc.get("doc_type", "invoice"),
        "doc_number": doc.get("doc_number", ""),
        "title": doc.get("title", ""),
        "customer_name": doc.get("customer_name", ""),
        "customer_email": doc.get("customer_email", ""),
        "customer_phone": doc.get("customer_phone", ""),
        "customer_address": doc.get("customer_address", ""),
        "items": doc.get("items", []),
        "subtotal": doc.get("subtotal", 0),
        "tax_rate": doc.get("tax_rate", 0),
        "tax_amount": doc.get("tax_amount", 0),
        "discount": doc.get("discount", 0),
        "discount_type": doc.get("discount_type", "flat"),
        "total": doc.get("total", 0),
        "notes": doc.get("notes", ""),
        "terms": doc.get("terms", ""),
        "due_date": doc.get("due_date").isoformat() if doc.get("due_date") else None,
        "status": doc.get("status", "draft"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        "user_id": str(doc.get("user_id", "")),
    }


async def _generate_doc_number(db, user_id: str, doc_type: str) -> str:
    """Generate sequential document number like EST-0001 or INV-0001"""
    prefix = "EST" if doc_type == "estimate" else "INV"
    count = await db.estimates_invoices.count_documents({
        "user_id": user_id,
        "doc_type": doc_type
    })
    return f"{prefix}-{str(count + 1).zfill(4)}"


# ============================================
# ENDPOINTS
# ============================================

@router.get("/")
async def list_documents(
    doc_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List estimates and/or invoices"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        query = {"user_id": user_id}
        if doc_type:
            query["doc_type"] = doc_type
        if status_filter:
            query["status"] = status_filter
        if search:
            query["$or"] = [
                {"customer_name": {"$regex": search, "$options": "i"}},
                {"title": {"$regex": search, "$options": "i"}},
                {"doc_number": {"$regex": search, "$options": "i"}},
            ]

        total = await db.estimates_invoices.count_documents(query)
        cursor = db.estimates_invoices.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return {
            "documents": [_format_doc(d) for d in docs],
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit,
        }
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    doc_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get stats for estimates/invoices"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        base_query = {"user_id": user_id}
        if doc_type:
            base_query["doc_type"] = doc_type

        total = await db.estimates_invoices.count_documents(base_query)
        draft = await db.estimates_invoices.count_documents({**base_query, "status": "draft"})
        sent = await db.estimates_invoices.count_documents({**base_query, "status": "sent"})
        paid = await db.estimates_invoices.count_documents({**base_query, "status": "paid"})
        accepted = await db.estimates_invoices.count_documents({**base_query, "status": "accepted"})

        # Total revenue from paid invoices
        pipeline = [
            {"$match": {**base_query, "status": {"$in": ["paid", "accepted"]}}},
            {"$group": {"_id": None, "total_revenue": {"$sum": "$total"}}}
        ]
        agg = await db.estimates_invoices.aggregate(pipeline).to_list(1)
        total_revenue = agg[0]["total_revenue"] if agg else 0

        return {
            "total": total,
            "draft": draft,
            "sent": sent,
            "paid": paid,
            "accepted": accepted,
            "total_revenue": total_revenue,
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new estimate or invoice"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        doc_number = await _generate_doc_number(db, user_id, data.doc_type)

        doc = {
            "user_id": user_id,
            "doc_type": data.doc_type,
            "doc_number": doc_number,
            "title": data.title,
            "customer_name": data.customer_name,
            "customer_email": data.customer_email or "",
            "customer_phone": data.customer_phone or "",
            "customer_address": data.customer_address or "",
            "items": [item.model_dump() for item in data.items],
            "subtotal": data.subtotal,
            "tax_rate": data.tax_rate,
            "tax_amount": data.tax_amount,
            "discount": data.discount,
            "discount_type": data.discount_type,
            "total": data.total,
            "notes": data.notes or "",
            "terms": data.terms or "",
            "due_date": data.due_date,
            "status": data.status or "draft",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await db.estimates_invoices.insert_one(doc)

        return {
            "success": True,
            "id": str(result.inserted_id),
            "doc_number": doc_number,
            "message": f"{data.doc_type.capitalize()} created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single estimate or invoice"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        doc = await db.estimates_invoices.find_one({
            "_id": ObjectId(doc_id),
            "user_id": user_id
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return _format_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{doc_id}")
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an estimate or invoice"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        update_data = data.model_dump(exclude_unset=True)
        if "items" in update_data and update_data["items"] is not None:
            update_data["items"] = [
                item if isinstance(item, dict) else item.model_dump()
                for item in update_data["items"]
            ]
        update_data["updated_at"] = datetime.utcnow()

        result = await db.estimates_invoices.update_one(
            {"_id": ObjectId(doc_id), "user_id": user_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        updated = await db.estimates_invoices.find_one({"_id": ObjectId(doc_id)})
        return _format_doc(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an estimate or invoice"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        result = await db.estimates_invoices.delete_one({
            "_id": ObjectId(doc_id),
            "user_id": user_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"success": True, "message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/send")
async def send_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Send estimate/invoice to customer email"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        doc = await db.estimates_invoices.find_one({
            "_id": ObjectId(doc_id),
            "user_id": user_id
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        customer_email = doc.get("customer_email")
        if not customer_email:
            raise HTTPException(status_code=400, detail="Customer email is required to send")

        doc_type = doc.get("doc_type", "invoice").capitalize()
        doc_number = doc.get("doc_number", "")
        title = doc.get("title", "")
        total = doc.get("total", 0)
        items = doc.get("items", [])

        # Build items HTML
        items_html = ""
        for item in items:
            items_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.get('description', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.get('quantity', 1)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${item.get('unit_price', 0):.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${item.get('amount', 0):.2f}</td>
            </tr>"""

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{doc_type} {doc_number}</h2>
            <p style="color: #666;">{title}</p>
            <hr style="border: 1px solid #eee;">
            <p><strong>Customer:</strong> {doc.get('customer_name', '')}</p>
            {f'<p><strong>Due Date:</strong> {doc.get("due_date").strftime("%B %d, %Y") if doc.get("due_date") else "N/A"}</p>' if doc.get('due_date') else ''}
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="background: #f8f8f8;">
                        <th style="padding: 8px; text-align: left;">Description</th>
                        <th style="padding: 8px; text-align: center;">Qty</th>
                        <th style="padding: 8px; text-align: right;">Price</th>
                        <th style="padding: 8px; text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>{items_html}</tbody>
            </table>
            <div style="text-align: right; margin-top: 10px;">
                <p>Subtotal: ${doc.get('subtotal', 0):.2f}</p>
                {f'<p>Tax ({doc.get("tax_rate", 0)}%): ${doc.get("tax_amount", 0):.2f}</p>' if doc.get('tax_rate') else ''}
                {f'<p>Discount: -${doc.get("discount", 0):.2f}</p>' if doc.get('discount') else ''}
                <p style="font-size: 18px; font-weight: bold;">Total: ${total:.2f}</p>
            </div>
            {f'<div style="margin-top: 20px; padding: 10px; background: #f8f8f8; border-radius: 4px;"><strong>Notes:</strong><br>{doc.get("notes")}</div>' if doc.get('notes') else ''}
            {f'<div style="margin-top: 10px; padding: 10px; background: #f8f8f8; border-radius: 4px;"><strong>Terms & Conditions:</strong><br>{doc.get("terms")}</div>' if doc.get('terms') else ''}
        </div>
        """

        # Send email
        from app.services.email_automation import email_automation_service
        await email_automation_service.send_email(
            to_email=customer_email,
            subject=f"{doc_type} {doc_number} - {title}",
            html_content=html_body
        )

        # Update status to sent
        await db.estimates_invoices.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "sent", "updated_at": datetime.utcnow()}}
        )

        return {"success": True, "message": f"{doc_type} sent to {customer_email}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/convert")
async def convert_estimate_to_invoice(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Convert an estimate to an invoice"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        doc = await db.estimates_invoices.find_one({
            "_id": ObjectId(doc_id),
            "user_id": user_id,
            "doc_type": "estimate"
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Estimate not found")

        # Create invoice from estimate
        doc_number = await _generate_doc_number(db, user_id, "invoice")
        invoice_doc = {
            "user_id": user_id,
            "doc_type": "invoice",
            "doc_number": doc_number,
            "title": doc.get("title", "").replace("Estimate", "Invoice"),
            "customer_name": doc.get("customer_name", ""),
            "customer_email": doc.get("customer_email", ""),
            "customer_phone": doc.get("customer_phone", ""),
            "customer_address": doc.get("customer_address", ""),
            "items": doc.get("items", []),
            "subtotal": doc.get("subtotal", 0),
            "tax_rate": doc.get("tax_rate", 0),
            "tax_amount": doc.get("tax_amount", 0),
            "discount": doc.get("discount", 0),
            "discount_type": doc.get("discount_type", "flat"),
            "total": doc.get("total", 0),
            "notes": doc.get("notes", ""),
            "terms": doc.get("terms", ""),
            "due_date": doc.get("due_date"),
            "status": "draft",
            "converted_from": str(doc["_id"]),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await db.estimates_invoices.insert_one(invoice_doc)

        # Mark estimate as accepted
        await db.estimates_invoices.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}}
        )

        return {
            "success": True,
            "invoice_id": str(result.inserted_id),
            "doc_number": doc_number,
            "message": "Estimate converted to invoice"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting estimate: {e}")
        raise HTTPException(status_code=500, detail=str(e))
