# # backend/app/api/v1/appointments.py - without ai follow up steps and calender integration evenets created like when user commuincate with voice agnet and say call yo back at 2pm then my voice agent again callback at 2pm 

# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from typing import Optional
# from datetime import datetime
# from bson import ObjectId

# from app.api.deps import get_current_user
# from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
# from app.services.appointment import appointment_service

# import logging

# logger = logging.getLogger(__name__)
# router = APIRouter()


# @router.get("/stats")
# async def get_appointment_stats(
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get appointment statistics"""
#     try:
#         user_id = str(current_user["_id"])
#         stats = await appointment_service.get_appointment_stats(user_id)
#         return stats
        
#     except Exception as e:
#         logger.error(f"❌ Error getting appointment stats: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )


# @router.get("/")
# async def list_appointments(
#     current_user: dict = Depends(get_current_user),
#     status: Optional[str] = Query(None),
#     date_from: Optional[str] = Query(None),
#     date_to: Optional[str] = Query(None),
#     skip: int = Query(0, ge=0),
#     limit: int = Query(50, ge=1, le=100)
# ):
#     """
#     ✅ FIXED: List appointments with proper ObjectId serialization
#     """
#     try:
#         user_id = str(current_user["_id"])
        
#         from app.database import get_database
#         db = await get_database()
        
#         # Build query
#         query = {"user_id": user_id}
        
#         if status:
#             query["status"] = status
        
#         # Date range filter
#         if date_from or date_to:
#             query["appointment_date"] = {}
#             if date_from:
#                 query["appointment_date"]["$gte"] = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
#             if date_to:
#                 query["appointment_date"]["$lte"] = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        
#         logger.info(f"📅 Query: {query}")
        
#         # Get total count
#         total = await db.appointments.count_documents(query)
        
#         # Get appointments
#         cursor = db.appointments.find(query).sort("appointment_date", -1).skip(skip).limit(limit)
#         appointments = await cursor.to_list(length=limit)
        
#         # ✅ CRITICAL FIX: Convert ALL ObjectIds to strings
#         formatted_appointments = []
#         for apt in appointments:
#             formatted_apt = {
#                 "id": str(apt["_id"]),
#                 "customer_name": apt.get("customer_name", ""),
#                 "customer_email": apt.get("customer_email", ""),
#                 "customer_phone": apt.get("customer_phone", ""),
#                 "appointment_date": apt.get("appointment_date").isoformat() if apt.get("appointment_date") else None,
#                 "appointment_time": apt.get("appointment_time", ""),
#                 "service_type": apt.get("service_type", "Appointment"),
#                 "status": apt.get("status", "scheduled"),
#                 "notes": apt.get("notes"),
#                 "duration_minutes": apt.get("duration_minutes", 60),
#                 "google_calendar_event_id": apt.get("google_calendar_event_id"),
#                 "google_calendar_link": apt.get("google_calendar_link"),
#                 "call_id": str(apt["call_id"]) if apt.get("call_id") else None,
#                 "user_id": str(apt["user_id"]) if apt.get("user_id") else None,
#                 "agent_id": str(apt["agent_id"]) if apt.get("agent_id") else None,
#                 "workflow_id": str(apt["workflow_id"]) if apt.get("workflow_id") else None,
#                 "created_at": apt.get("created_at").isoformat() if apt.get("created_at") else None,
#                 "updated_at": apt.get("updated_at").isoformat() if apt.get("updated_at") else None,
#             }
#             formatted_appointments.append(formatted_apt)
        
#         logger.info(f"✅ Found {len(formatted_appointments)} appointments")
        
#         return {
#             "appointments": formatted_appointments,
#             "total": total,
#             "page": skip // limit + 1 if limit > 0 else 1,
#             "page_size": limit
#         }
        
#     except Exception as e:
#         logger.error(f"❌ Error listing appointments: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to list appointments: {str(e)}"
#         )


# @router.post("/", status_code=status.HTTP_201_CREATED)
# async def create_appointment(
#     appointment_data: AppointmentCreate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Create a new appointment"""
#     try:
#         user_id = str(current_user["_id"])
        
#         result = await appointment_service.create_appointment(
#             customer_name=appointment_data.customer_name,
#             customer_email=appointment_data.customer_email,
#             customer_phone=appointment_data.customer_phone,
#             appointment_date=appointment_data.appointment_date,
#             appointment_time=getattr(appointment_data, 'appointment_time', None),
#             service_type=appointment_data.service_type,
#             notes=appointment_data.notes,
#             user_id=user_id
#         )
        
#         if not result.get("success"):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=result.get("error", "Failed to create appointment")
#             )
        
#         return result
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Error creating appointment: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )


# @router.get("/{appointment_id}")
# async def get_appointment(
#     appointment_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get a specific appointment"""
#     try:
#         user_id = str(current_user["_id"])
        
#         appointment = await appointment_service.get_appointment(
#             appointment_id=appointment_id,
#             user_id=user_id
#         )
        
#         if not appointment:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Appointment not found"
#             )
        
#         return appointment
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Error getting appointment: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )


# @router.put("/{appointment_id}")
# async def update_appointment(
#     appointment_id: str,
#     appointment_data: AppointmentUpdate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Update an appointment"""
#     try:
#         user_id = str(current_user["_id"])
        
#         result = await appointment_service.update_appointment(
#             appointment_id=appointment_id,
#             user_id=user_id,
#             **appointment_data.dict(exclude_unset=True)
#         )
        
#         if not result.get("success"):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=result.get("error", "Failed to update appointment")
#             )
        
#         return result
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Error updating appointment: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )


# @router.delete("/{appointment_id}")
# async def delete_appointment(
#     appointment_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Delete an appointment"""
#     try:
#         user_id = str(current_user["_id"])
        
#         result = await appointment_service.delete_appointment(
#             appointment_id=appointment_id,
#             user_id=user_id
#         )
        
#         if not result.get("success"):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=result.get("error", "Failed to delete appointment")
#             )
        
#         return result
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Error deleting appointment: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )


# backend/app/api/v1/appointments.py - COMPLETE FIXED VERSION
"""
Appointments API - ENHANCED with Follow-up Management
✅ FIXED: ObjectId serialization error resolved
✅ ALL EXISTING ENDPOINTS PRESERVED
✅ NEW: Follow-up and reminder endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import csv
import io

from app.api.deps import get_current_user
from app.database import get_database
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AvailabilityRequest,
    AvailabilityResponse
)
from app.services.appointment import appointment_service
from app.services.google_calendar import google_calendar_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# EXISTING ENDPOINTS (ALL PRESERVED & FIXED)
# ============================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new appointment"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        # Try Google Calendar integration via service
        try:
            result = await appointment_service.create_appointment(
                user_id=user_id,
                customer_name=appointment_data.customer_name,
                customer_email=appointment_data.customer_email or "",
                customer_phone=appointment_data.customer_phone or "",
                appointment_date=appointment_data.appointment_date,
                appointment_time=appointment_data.appointment_time,
                service_type=appointment_data.service_type,
                notes=appointment_data.notes
            )
            if result.get("success"):
                # Add cost and duration to the created doc
                if appointment_data.cost is not None or appointment_data.duration_minutes != 60:
                    update_fields = {}
                    if appointment_data.cost is not None:
                        update_fields["cost"] = appointment_data.cost
                    if appointment_data.duration_minutes and appointment_data.duration_minutes != 60:
                        update_fields["duration_minutes"] = appointment_data.duration_minutes
                    if update_fields and result.get("appointment_id"):
                        await db.appointments.update_one(
                            {"_id": ObjectId(result["appointment_id"])},
                            {"$set": update_fields}
                        )
                return result
        except Exception as svc_err:
            logger.warning(f"⚠️ Service create failed (calendar?), falling back to direct DB insert: {svc_err}")

        # Fallback: direct DB insert without Google Calendar
        appointment_doc = {
            "user_id": user_id,
            "customer_name": appointment_data.customer_name,
            "customer_email": appointment_data.customer_email or "",
            "customer_phone": appointment_data.customer_phone or "",
            "appointment_date": appointment_data.appointment_date,
            "appointment_time": appointment_data.appointment_time,
            "service_type": appointment_data.service_type or "General",
            "cost": appointment_data.cost,
            "duration_minutes": appointment_data.duration_minutes or 60,
            "notes": appointment_data.notes,
            "status": "scheduled",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        insert_result = await db.appointments.insert_one(appointment_doc)
        return {
            "success": True,
            "appointment_id": str(insert_result.inserted_id),
            "message": "Appointment created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/")
async def list_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    event_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    ✅ FIXED: List appointments with proper ObjectId handling and timezone normalization
    """
    try:
        user_id = str(current_user["_id"])

        # Parse date strings to naive UTC datetimes (strip timezone info)
        parsed_from = None
        parsed_to = None
        if date_from:
            try:
                parsed_from = datetime.fromisoformat(date_from.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                print(f"[APPOINTMENTS] Failed to parse date_from: {date_from}")
        if date_to:
            try:
                parsed_to = datetime.fromisoformat(date_to.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                print(f"[APPOINTMENTS] Failed to parse date_to: {date_to}")

        # Debug: check total appointments for this user (no date filter)
        db = await get_database()
        total_all = await db.appointments.count_documents({"user_id": user_id})
        print(f"[APPOINTMENTS] user={user_id}, total_all={total_all}, date_from={parsed_from}, date_to={parsed_to}")

        # Call the service method that includes _format_appointment
        result = await appointment_service.get_appointments(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status_filter,
            from_date=parsed_from,
            to_date=parsed_to
        )
        
        # ✅ NEW: Filter by event_type if provided (appointments are already formatted)
        if event_type and result.get("appointments"):
            result["appointments"] = [
                apt for apt in result["appointments"]
                if apt.get("event_type") == event_type
            ]
            result["total"] = len(result["appointments"])
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error listing appointments: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/export/csv")
async def export_appointments_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    """Export appointments as CSV"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        query = {"user_id": user_id}
        if status_filter:
            query["status"] = status_filter
        if date_from or date_to:
            query["appointment_date"] = {}
            if date_from:
                query["appointment_date"]["$gte"] = datetime.fromisoformat(date_from.replace('Z', '+00:00')).replace(tzinfo=None)
            if date_to:
                query["appointment_date"]["$lte"] = datetime.fromisoformat(date_to.replace('Z', '+00:00')).replace(tzinfo=None)

        cursor = db.appointments.find(query).sort("appointment_date", -1)
        appointments = await cursor.to_list(length=10000)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Customer Name", "Email", "Phone", "Date", "Time", "Service", "Cost", "Duration (min)", "Status", "Notes", "Created At"])

        for apt in appointments:
            apt_date = apt.get("appointment_date")
            writer.writerow([
                apt.get("customer_name", ""),
                apt.get("customer_email", ""),
                apt.get("customer_phone", ""),
                apt_date.strftime("%Y-%m-%d") if apt_date else "",
                apt.get("appointment_time", ""),
                apt.get("service_type", ""),
                apt.get("cost", ""),
                apt.get("duration_minutes", 60),
                apt.get("status", "scheduled"),
                apt.get("notes", ""),
                apt.get("created_at", ""),
            ])

        output.seek(0)
        today = datetime.utcnow().strftime("%Y%m%d")
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=appointments_{today}.csv"}
        )

    except Exception as e:
        logger.error(f"Error exporting appointments CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/csv")
async def import_appointments_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Import appointments from CSV"""
    try:
        user_id = str(current_user["_id"])
        db = await get_database()

        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        imported = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            try:
                customer_name = row.get("Customer Name", "").strip()
                if not customer_name:
                    errors.append(f"Row {i}: Missing customer name")
                    continue

                date_str = row.get("Date", "").strip()
                time_str = row.get("Time", "").strip()
                if not date_str or not time_str:
                    errors.append(f"Row {i}: Missing date or time")
                    continue

                apt_date = datetime.strptime(date_str, "%Y-%m-%d")
                cost_str = row.get("Cost", "").strip()
                cost = float(cost_str) if cost_str else None
                dur_str = row.get("Duration (min)", "").strip()
                duration = int(dur_str) if dur_str else 60

                doc = {
                    "user_id": user_id,
                    "customer_name": customer_name,
                    "customer_email": row.get("Email", "").strip(),
                    "customer_phone": row.get("Phone", "").strip(),
                    "appointment_date": apt_date,
                    "appointment_time": time_str,
                    "service_type": row.get("Service", "").strip() or None,
                    "cost": cost,
                    "duration_minutes": duration,
                    "status": row.get("Status", "scheduled").strip() or "scheduled",
                    "notes": row.get("Notes", "").strip() or None,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                await db.appointments.insert_one(doc)
                imported += 1
            except Exception as row_err:
                errors.append(f"Row {i}: {str(row_err)}")

        return {
            "success": True,
            "imported": imported,
            "errors": errors[:20],
            "total_errors": len(errors)
        }

    except Exception as e:
        logger.error(f"Error importing appointments CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_appointment_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get appointment statistics"""
    try:
        user_id = str(current_user["_id"])
        
        stats = await appointment_service.get_appointment_stats(user_id)
        
        # ✅ NEW: Add follow-up stats
        db = await get_database()
        
        follow_ups_pending = await db.appointments.count_documents({
            "user_id": user_id,
            "event_type": "follow_up_call",
            "action_completed": False,
            "status": "pending_action"
        })
        
        follow_ups_completed = await db.appointments.count_documents({
            "user_id": user_id,
            "event_type": "follow_up_call",
            "action_completed": True
        })
        
        stats["follow_ups_pending"] = follow_ups_pending
        stats["follow_ups_completed"] = follow_ups_completed
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific appointment (already uses _format_appointment)"""
    try:
        user_id = str(current_user["_id"])
        
        appointment = await appointment_service.get_appointment(appointment_id, user_id)
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return appointment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    appointment_data: AppointmentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update appointment"""
    try:
        user_id = str(current_user["_id"])
        
        update_data = appointment_data.model_dump(exclude_unset=True)
        
        updated = await appointment_service.update_appointment(
            appointment_id, user_id, update_data
        )
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{appointment_id}")
async def cancel_appointment(
    appointment_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Cancel appointment"""
    try:
        user_id = str(current_user["_id"])
        
        success = await appointment_service.cancel_appointment(
            appointment_id, user_id, reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return {"message": "Appointment cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/check-availability")
async def check_availability(
    request: AvailabilityRequest,
    current_user: dict = Depends(get_current_user)
):
    """Check available appointment slots"""
    try:
        user_id = str(current_user["_id"])
        
        slots = await appointment_service.get_available_slots(
            user_id=user_id,
            date=request.date,
            duration_minutes=request.duration_minutes
        )
        
        return {
            "date": request.date.strftime("%Y-%m-%d"),
            "available_slots": slots
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# ✅ NEW: FOLLOW-UP MANAGEMENT ENDPOINTS
# ============================================

@router.get("/follow-ups/pending")
async def get_pending_follow_ups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all pending AI follow-up calls
    These are scheduled callbacks that haven't been executed yet
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Find pending follow-up appointments
        query = {
            "user_id": user_id,
            "event_type": "follow_up_call",
            "action_completed": False,
            "status": "pending_action",
            "appointment_date": {"$gte": datetime.utcnow()}
        }
        
        total = await db.appointments.count_documents(query)
        
        cursor = db.appointments.find(query).sort("appointment_date", 1).skip(skip).limit(limit)
        appointments = await cursor.to_list(length=limit)
        
        # ✅ Format all appointments using the service method
        formatted_appointments = []
        for apt in appointments:
            formatted_appointments.append(appointment_service._format_appointment(apt))
        
        return {
            "follow_ups": formatted_appointments,
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting pending follow-ups: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/follow-ups/completed")
async def get_completed_follow_ups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get completed AI follow-up calls
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        query = {
            "user_id": user_id,
            "event_type": "follow_up_call",
            "action_completed": True
        }
        
        total = await db.appointments.count_documents(query)
        
        cursor = db.appointments.find(query).sort("action_completed_at", -1).skip(skip).limit(limit)
        appointments = await cursor.to_list(length=limit)
        
        # ✅ Format all appointments
        formatted_appointments = []
        for apt in appointments:
            formatted_appointments.append(appointment_service._format_appointment(apt))
        
        return {
            "follow_ups": formatted_appointments,
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting completed follow-ups: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{appointment_id}/reschedule")
async def reschedule_follow_up(
    appointment_id: str,
    new_datetime: datetime,
    current_user: dict = Depends(get_current_user)
):
    """
    Reschedule a follow-up call to a new date/time
    Also updates Google Calendar event
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Get appointment
        appointment = await db.appointments.find_one({
            "_id": ObjectId(appointment_id),
            "user_id": user_id,
            "event_type": "follow_up_call"
        })
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Follow-up call not found"
            )
        
        # Update Google Calendar if event exists
        if appointment.get("google_calendar_event_id"):
            try:
                await google_calendar_service.update_event(
                    event_id=appointment["google_calendar_event_id"],
                    start_time=new_datetime,
                    end_time=new_datetime + timedelta(minutes=appointment.get("duration_minutes", 30))
                )
            except Exception as e:
                logger.warning(f"Could not update Google Calendar event: {e}")
        
        # Update in database
        await db.appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {
                "$set": {
                    "appointment_date": new_datetime,
                    "appointment_time": new_datetime.strftime("%H:%M"),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Get updated appointment
        updated_appointment = await appointment_service.get_appointment(appointment_id, user_id)
        
        return {
            "success": True,
            "message": "Follow-up call rescheduled successfully",
            "appointment": updated_appointment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error rescheduling follow-up: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{appointment_id}/cancel-follow-up")
async def cancel_follow_up(
    appointment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a pending follow-up call
    """
    try:
        user_id = str(current_user["_id"])
        db = await get_database()
        
        # Get appointment
        appointment = await db.appointments.find_one({
            "_id": ObjectId(appointment_id),
            "user_id": user_id,
            "event_type": "follow_up_call"
        })
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Follow-up call not found"
            )
        
        # Cancel Google Calendar event if exists
        if appointment.get("google_calendar_event_id"):
            try:
                await google_calendar_service.cancel_event(
                    appointment["google_calendar_event_id"]
                )
            except Exception as e:
                logger.warning(f"Could not cancel Google Calendar event: {e}")
        
        # Update status
        await db.appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {
                "$set": {
                    "status": "cancelled",
                    "action_completed": True,
                    "action_result": "cancelled_by_user",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "success": True,
            "message": "Follow-up call cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling follow-up: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )