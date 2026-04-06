# # backend/app/services/appointment.py - COMPLETE WITH EMAIL LOGGING FIX AND FIXED get_db

# from typing import Optional, Dict, Any, List
# from datetime import datetime, timedelta
# from bson import ObjectId
# import logging

# from app.database import get_database
# from app.services.google_calendar import google_calendar_service
# from app.services.email_automation import email_automation_service
# from app.services.customer import customer_service  # ✅ NEW

# logger = logging.getLogger(__name__)


# class AppointmentService:
#     """Service for managing appointments"""
    
#     def __init__(self):
#         self.db = None
    
#     async def get_db(self):
#         """Get database connection - FIXED: Proper None comparison"""
#         if self.db is None:
#             self.db = await get_database()
#         return self.db
    
#     async def create_appointment(
#         self,
#         user_id: str,
#         customer_name: str,
#         customer_email: str,
#         customer_phone: str,
#         service_type: str,
#         appointment_date: datetime,
#         duration_minutes: int = 60,
#         notes: Optional[str] = None,
#         call_id: Optional[str] = None,
#         workflow_id: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """
#         Create a new appointment
        
#         Args:
#             user_id: User ID
#             customer_name: Customer name
#             customer_email: Customer email
#             customer_phone: Customer phone
#             service_type: Type of service
#             appointment_date: Appointment date/time
#             duration_minutes: Duration in minutes (default 60)
#             notes: Additional notes
#             call_id: Associated call ID
#             workflow_id: Associated workflow ID
            
#         Returns:
#             Dict with appointment details and Google Calendar event
#         """
#         try:
#             logger.info(f"📅 Creating appointment for {customer_name}")
            
#             # ✅ NEW - Auto-create customer if not exists
#             customer_result = await customer_service.find_or_create_customer(
#                 user_id=user_id,
#                 name=customer_name,
#                 email=customer_email,
#                 phone=customer_phone
#             )
            
#             if customer_result.get("success"):
#                 if customer_result.get("created"):
#                     logger.info(f"✅ New customer created: {customer_name}")
#                 else:
#                     logger.info(f"✅ Existing customer found: {customer_name}")
            
#             # Create Google Calendar event
#             calendar_result = await google_calendar_service.create_event(
#                 summary=f"{service_type} - {customer_name}",
#                 description=f"Service: {service_type}\nCustomer: {customer_name}\nPhone: {customer_phone}\nEmail: {customer_email}\n\nNotes: {notes or 'N/A'}",
#                 start_time=appointment_date,
#                 duration_minutes=duration_minutes,
#                 attendee_email=customer_email
#             )
            
#             if not calendar_result.get("success"):
#                 raise Exception(f"Failed to create calendar event: {calendar_result.get('error')}")
            
#             # Save to database
#             db = await self.get_db()
            
#             appointment_data = {
#                 "user_id": user_id,
#                 "customer_name": customer_name,
#                 "customer_email": customer_email,
#                 "customer_phone": customer_phone,
#                 "service_type": service_type,
#                 "appointment_date": appointment_date,
#                 "duration_minutes": duration_minutes,
#                 "notes": notes,
#                 "status": "scheduled",
#                 "google_calendar_event_id": calendar_result.get("event_id"),
#                 "google_calendar_link": calendar_result.get("event_link"),
#                 "call_id": call_id,
#                 "workflow_id": workflow_id,
#                 "created_at": datetime.utcnow(),
#                 "updated_at": datetime.utcnow()
#             }
            
#             result = await db.appointments.insert_one(appointment_data)
#             appointment_id = str(result.inserted_id)
            
#             logger.info(f"✅ Appointment created: {appointment_id}")
            
#             # ✅ NEW - Update customer appointment count
#             if customer_result.get("success") and customer_result.get("customer"):
#                 customer_id = customer_result["customer"].get("id")
#                 if customer_id:
#                     await db.customers.update_one(
#                         {"_id": ObjectId(customer_id)},
#                         {
#                             "$inc": {"total_appointments": 1, "total_interactions": 1},
#                             "$set": {"last_contact_at": datetime.utcnow()}
#                         }
#                     )
            
#             # Send confirmation email using email_automation_service
#             try:
#                 formatted_date = appointment_date.strftime("%A, %B %d, %Y at %I:%M %p")
                
#                 await email_automation_service.send_appointment_confirmation(
#                     to_email=customer_email,
#                     customer_name=customer_name,
#                     customer_phone=customer_phone,
#                     service_type=service_type,
#                     appointment_date=formatted_date,
#                     user_id=user_id,
#                     appointment_id=appointment_id,
#                     call_id=call_id
#                 )
                
#                 logger.info(f"✅ Confirmation email sent and logged to {customer_email}")
                
#             except Exception as email_error:
#                 logger.error(f"❌ Failed to send confirmation email: {email_error}")
#                 # Don't fail the appointment creation if email fails
            
#             return {
#                 "success": True,
#                 "appointment_id": appointment_id,
#                 "google_calendar_event_id": calendar_result.get("event_id"),
#                 "google_calendar_link": calendar_result.get("event_link"),
#                 "message": "Appointment created successfully"
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Error creating appointment: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def get_appointments(
#         self,
#         user_id: str,
#         skip: int = 0,
#         limit: int = 50,
#         status_filter: Optional[str] = None,
#         from_date: Optional[datetime] = None,
#         to_date: Optional[datetime] = None
#     ) -> Dict[str, Any]:
#         """Get appointments for a user"""
#         try:
#             db = await self.get_db()
            
#             # Build query
#             query = {"user_id": user_id}
            
#             if status_filter:
#                 query["status"] = status_filter
            
#             if from_date or to_date:
#                 date_query = {}
#                 if from_date:
#                     date_query["$gte"] = from_date
#                 if to_date:
#                     date_query["$lte"] = to_date
#                 if date_query:
#                     query["appointment_date"] = date_query
            
#             # Get total count
#             total = await db.appointments.count_documents(query)
            
#             # Get appointments
#             cursor = db.appointments.find(query).sort("appointment_date", -1).skip(skip).limit(limit)
#             appointments = await cursor.to_list(length=limit)
            
#             # Format appointments
#             for appointment in appointments:
#                 appointment["_id"] = str(appointment["_id"])
#                 if appointment.get("call_id"):
#                     appointment["call_id"] = str(appointment["call_id"])
#                 if appointment.get("workflow_id"):
#                     appointment["workflow_id"] = str(appointment["workflow_id"])
            
#             return {
#                 "appointments": appointments,
#                 "total": total,
#                 "page": skip // limit + 1,
#                 "page_size": limit
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Error getting appointments: {e}")
#             return {
#                 "appointments": [],
#                 "total": 0,
#                 "error": str(e)
#             }
    
#     async def get_appointment(
#         self,
#         appointment_id: str,
#         user_id: str
#     ) -> Optional[Dict[str, Any]]:
#         """Get a specific appointment"""
#         try:
#             db = await self.get_db()
            
#             appointment = await db.appointments.find_one({
#                 "_id": ObjectId(appointment_id),
#                 "user_id": user_id
#             })
            
#             if appointment:
#                 appointment["_id"] = str(appointment["_id"])
#                 if appointment.get("call_id"):
#                     appointment["call_id"] = str(appointment["call_id"])
#                 if appointment.get("workflow_id"):
#                     appointment["workflow_id"] = str(appointment["workflow_id"])
            
#             return appointment
            
#         except Exception as e:
#             logger.error(f"❌ Error getting appointment: {e}")
#             return None
    
#     async def update_appointment(
#         self,
#         appointment_id: str,
#         user_id: str,
#         update_data: Dict[str, Any]
#     ) -> Optional[Dict[str, Any]]:
#         """Update an appointment"""
#         try:
#             db = await self.get_db()
            
#             update_data["updated_at"] = datetime.utcnow()
            
#             result = await db.appointments.update_one(
#                 {"_id": ObjectId(appointment_id), "user_id": user_id},
#                 {"$set": update_data}
#             )
            
#             if result.modified_count > 0:
#                 return await self.get_appointment(appointment_id, user_id)
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error updating appointment: {e}")
#             return None
    
#     async def cancel_appointment(
#         self,
#         appointment_id: str,
#         user_id: str,
#         reason: Optional[str] = None
#     ) -> bool:
#         """Cancel an appointment"""
#         try:
#             # Get appointment
#             appointment = await self.get_appointment(appointment_id, user_id)
#             if not appointment:
#                 return False
            
#             # Cancel Google Calendar event
#             if appointment.get("google_calendar_event_id"):
#                 await google_calendar_service.delete_event(
#                     appointment["google_calendar_event_id"]
#                 )
            
#             # Update status in database
#             db = await self.get_db()
#             await db.appointments.update_one(
#                 {"_id": ObjectId(appointment_id)},
#                 {
#                     "$set": {
#                         "status": "cancelled",
#                         "cancellation_reason": reason,
#                         "cancelled_at": datetime.utcnow(),
#                         "updated_at": datetime.utcnow()
#                     }
#                 }
#             )
            
#             logger.info(f"✅ Appointment {appointment_id} cancelled")
#             return True
            
#         except Exception as e:
#             logger.error(f"❌ Error cancelling appointment: {e}")
#             return False
    
#     async def get_appointment_stats(self, user_id: str) -> Dict[str, int]:
#         """Get appointment statistics"""
#         try:
#             db = await self.get_db()
            
#             # Total appointments
#             total = await db.appointments.count_documents({"user_id": user_id})
            
#             # By status
#             scheduled = await db.appointments.count_documents({
#                 "user_id": user_id,
#                 "status": "scheduled"
#             })
            
#             completed = await db.appointments.count_documents({
#                 "user_id": user_id,
#                 "status": "completed"
#             })
            
#             cancelled = await db.appointments.count_documents({
#                 "user_id": user_id,
#                 "status": "cancelled"
#             })
            
#             # This month
#             month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#             this_month = await db.appointments.count_documents({
#                 "user_id": user_id,
#                 "created_at": {"$gte": month_start}
#             })
            
#             return {
#                 "total": total,
#                 "scheduled": scheduled,
#                 "completed": completed,
#                 "cancelled": cancelled,
#                 "this_month": this_month
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Error getting appointment stats: {e}")
#             return {
#                 "total": 0,
#                 "scheduled": 0,
#                 "completed": 0,
#                 "cancelled": 0,
#                 "this_month": 0
#             }


# # Create singleton instance
# appointment_service = AppointmentService()   


# backend/app/services/appointment.py - ✅ COMPLETE FIXED WITH DEEP OBJECTID HANDLING
"""
Appointment Service - FIXED with complete ObjectId serialization
✅ ALL ObjectId fields properly converted to strings (including nested)
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database import get_database
from app.services.google_calendar import google_calendar_service
from app.services.email_automation import email_automation_service

logger = logging.getLogger(__name__)


class AppointmentService:
    """Service for managing appointments"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def _format_appointment(self, appointment: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ FIXED: Format appointment document by converting ALL ObjectId fields to strings
        This prevents FastAPI serialization errors
        """
        if not appointment:
            return None
        
        # Create a copy to avoid modifying the original
        formatted = {}
        
        for key, value in appointment.items():
            # Convert ObjectId to string
            if isinstance(value, ObjectId):
                formatted[key] = str(value)
            # Convert datetime to ISO format string
            elif isinstance(value, datetime):
                formatted[key] = value.isoformat()
            # Handle nested dicts
            elif isinstance(value, dict):
                formatted[key] = self._format_nested_dict(value)
            # Handle lists
            elif isinstance(value, list):
                formatted[key] = [
                    str(item) if isinstance(item, ObjectId) else item
                    for item in value
                ]
            else:
                formatted[key] = value
        
        # Ensure _id is always converted to id
        if "_id" in formatted:
            formatted["id"] = formatted["_id"]
        
        return formatted
    
    def _format_nested_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively format nested dictionaries"""
        formatted = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                formatted[key] = str(value)
            elif isinstance(value, datetime):
                formatted[key] = value.isoformat()
            elif isinstance(value, dict):
                formatted[key] = self._format_nested_dict(value)
            elif isinstance(value, list):
                formatted[key] = [
                    str(item) if isinstance(item, ObjectId) else item
                    for item in value
                ]
            else:
                formatted[key] = value
        return formatted
    
    async def create_appointment(
        self,
        user_id: str,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        appointment_date: datetime,
        appointment_time: str,
        service_type: Optional[str] = None,
        notes: Optional[str] = None,
        call_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new appointment with Google Calendar integration"""
        try:
            logger.info(f"📅 Creating appointment for {customer_name}")

            # Check for time slot conflicts (60 min duration)
            db = await self.get_db()
            duration_minutes = 60
            appointment_end = appointment_date + timedelta(minutes=duration_minutes)

            conflict = await db.appointments.find_one({
                "user_id": user_id,
                "status": {"$in": ["scheduled", "confirmed"]},
                "$or": [
                    # New appointment starts during an existing one
                    {
                        "appointment_date": {"$lte": appointment_date},
                        "$expr": {
                            "$gt": [
                                {"$add": ["$appointment_date", {"$multiply": [{"$ifNull": ["$duration_minutes", 60]}, 60000]}]},
                                appointment_date
                            ]
                        }
                    },
                    # New appointment overlaps with an existing one (same start time)
                    {
                        "appointment_date": {
                            "$gte": appointment_date,
                            "$lt": appointment_end
                        }
                    }
                ]
            })

            if conflict:
                conflict_time = conflict.get("appointment_date")
                conflict_name = conflict.get("customer_name", "another customer")
                logger.warning(f"⚠️ Time slot conflict: {appointment_date} overlaps with {conflict_name} at {conflict_time}")
                return {
                    "success": False,
                    "error": "time_conflict",
                    "conflict_time": conflict_time.strftime("%I:%M %p") if conflict_time else appointment_time,
                    "conflict_name": conflict_name
                }

            # Create Google Calendar event
            calendar_result = await google_calendar_service.create_event(
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                duration_minutes=60,
                service_type=service_type,
                notes=notes
            )
            
            if not calendar_result.get("success"):
                return {
                    "success": False,
                    "error": calendar_result.get("error", "Failed to create calendar event")
                }
            
            # Save to database
            db = await self.get_db()
            
            appointment_data = {
                "user_id": user_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "service_type": service_type or "General",
                "notes": notes,
                "status": "scheduled",
                "google_calendar_event_id": calendar_result.get("event_id"),
                "google_calendar_link": calendar_result.get("html_link"),
                "call_id": call_id,
                "agent_id": agent_id,
                "workflow_id": workflow_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db.appointments.insert_one(appointment_data)
            appointment_id = str(result.inserted_id)
            
            # Send confirmation email
            try:
                formatted_date = appointment_date.strftime("%A, %B %d, %Y at %I:%M %p")
                
                await email_automation_service.send_appointment_confirmation(
                    to_email=customer_email,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    service_type=service_type or "General",
                    appointment_date=formatted_date,
                    user_id=user_id,
                    appointment_id=appointment_id,
                    call_id=call_id
                )
                
                logger.info(f"✅ Confirmation email sent to {customer_email}")
                
            except Exception as e:
                logger.warning(f"⚠️ Could not send confirmation email: {e}")
            
            logger.info(f"✅ Appointment created: {appointment_id}")
            
            return {
                "success": True,
                "appointment_id": appointment_id,
                "google_calendar_event_id": calendar_result.get("event_id"),
                "google_calendar_link": calendar_result.get("html_link"),
                "message": "Appointment created successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating appointment: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_appointments(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get appointments for a user - ✅ FIXED with proper formatting"""
        try:
            db = await self.get_db()

            # Build query
            query = {"user_id": user_id}

            if status:
                query["status"] = status

            # Add date range filter
            if from_date or to_date:
                date_query = {}
                if from_date:
                    date_query["$gte"] = from_date
                if to_date:
                    date_query["$lte"] = to_date
                if date_query:
                    query["appointment_date"] = date_query

            print(f"[APPOINTMENTS-DEBUG] Query: {query}")

            # Get total count
            total = await db.appointments.count_documents(query)

            print(f"[APPOINTMENTS-DEBUG] Total found: {total}")

            # Get appointments
            cursor = db.appointments.find(query).sort("appointment_date", -1).skip(skip).limit(limit)
            appointments = await cursor.to_list(length=limit)

            print(f"[APPOINTMENTS-DEBUG] Fetched {len(appointments)} appointments")
            
            # ✅ FIXED: Format all appointments to convert ObjectId to strings
            formatted_appointments = []
            for appointment in appointments:
                formatted = self._format_appointment(appointment)
                if formatted:
                    formatted_appointments.append(formatted)
            
            return {
                "appointments": formatted_appointments,
                "total": total,
                "page": skip // limit + 1 if limit > 0 else 1,
                "page_size": limit
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting appointments: {e}")
            import traceback
            traceback.print_exc()
            return {
                "appointments": [],
                "total": 0,
                "error": str(e)
            }
    
    async def get_appointment(
        self,
        appointment_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific appointment"""
        try:
            db = await self.get_db()
            
            appointment = await db.appointments.find_one({
                "_id": ObjectId(appointment_id),
                "user_id": user_id
            })
            
            # ✅ FIXED: Use _format_appointment to handle ObjectId conversion
            return self._format_appointment(appointment) if appointment else None
            
        except Exception as e:
            logger.error(f"❌ Error getting appointment: {e}")
            return None
    
    async def update_appointment(
        self,
        appointment_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an appointment"""
        try:
            db = await self.get_db()
            
            update_data["updated_at"] = datetime.utcnow()
            
            result = await db.appointments.update_one(
                {"_id": ObjectId(appointment_id), "user_id": user_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return await self.get_appointment(appointment_id, user_id)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error updating appointment: {e}")
            return None
    
    async def cancel_appointment(
        self,
        appointment_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel an appointment"""
        try:
            # Get appointment
            appointment = await self.get_appointment(appointment_id, user_id)
            if not appointment:
                return False
            
            # Cancel Google Calendar event
            if appointment.get("google_calendar_event_id"):
                await google_calendar_service.cancel_event(
                    appointment["google_calendar_event_id"]
                )
            
            # Update status in database
            db = await self.get_db()
            await db.appointments.update_one(
                {"_id": ObjectId(appointment_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancellation_reason": reason,
                        "cancelled_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Appointment {appointment_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cancelling appointment: {e}")
            return False
    
    async def get_available_slots(
        self,
        user_id: str,
        date: datetime,
        duration_minutes: int = 60
    ) -> List[str]:
        """Get available time slots for a given date"""
        try:
            db = await self.get_db()
            
            # Get all appointments for the date
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            appointments = await db.appointments.find({
                "user_id": user_id,
                "appointment_date": {
                    "$gte": start_of_day,
                    "$lt": end_of_day
                },
                "status": {"$in": ["scheduled", "confirmed"]}
            }).to_list(length=100)
            
            # Define working hours (9 AM to 5 PM)
            working_start = 9
            working_end = 17
            
            # Generate all possible slots
            all_slots = []
            for hour in range(working_start, working_end):
                all_slots.append(f"{hour:02d}:00")
                if hour + 1 < working_end:  # Don't add :30 if it would go past working hours
                    all_slots.append(f"{hour:02d}:30")
            
            # Remove booked slots
            booked_times = set()
            for apt in appointments:
                apt_time = apt.get("appointment_time", "")
                if apt_time:
                    booked_times.add(apt_time)
            
            available_slots = [slot for slot in all_slots if slot not in booked_times]
            
            return available_slots
            
        except Exception as e:
            logger.error(f"❌ Error getting available slots: {e}")
            return []
    
    async def get_appointment_stats(self, user_id: str) -> Dict[str, int]:
        """Get appointment statistics"""
        try:
            db = await self.get_db()
            
            # Total appointments
            total = await db.appointments.count_documents({"user_id": user_id})
            
            # By status
            scheduled = await db.appointments.count_documents({
                "user_id": user_id,
                "status": "scheduled"
            })
            
            completed = await db.appointments.count_documents({
                "user_id": user_id,
                "status": "completed"
            })
            
            cancelled = await db.appointments.count_documents({
                "user_id": user_id,
                "status": "cancelled"
            })
            
            # This month
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month = await db.appointments.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": month_start}
            })
            
            return {
                "total": total,
                "scheduled": scheduled,
                "completed": completed,
                "cancelled": cancelled,
                "this_month": this_month
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting appointment stats: {e}")
            return {
                "total": 0,
                "scheduled": 0,
                "completed": 0,
                "cancelled": 0,
                "this_month": 0
            }


# Create singleton instance
appointment_service = AppointmentService()