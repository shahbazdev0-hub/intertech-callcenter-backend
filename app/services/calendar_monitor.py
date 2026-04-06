# backend/app/services/calendar_monitor.py - ✅ FIXED VERSION WITH DUPLICATE PREVENTION

"""
Calendar Monitor Service

✅ FIXED: Added proper duplicate call prevention
✅ FIXED: Checks if call already initiated before making another
✅ FIXED: Updates status immediately to prevent race conditions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.database import get_database
from app.services.google_calendar import google_calendar_service
from app.services.twilio import twilio_service
from app.services.sms import sms_service
from app.services.email_automation import email_automation_service
from app.config import settings
from app.services.outbound_call import OutboundCallService

# Create service instance
outbound_call_service = OutboundCallService()
logger = logging.getLogger(__name__)


class CalendarMonitorService:
    """
    Calendar Monitor Service
    
    Scans every 2 minutes for:
    1. ✅ Database follow_ups collection (PRIMARY - most reliable)
    2. ✅ Database appointments collection with follow-up calls
    3. ✅ Google Calendar events (SECONDARY - for reminders)
    
    ✅ FIXED: Proper duplicate prevention across all sources
    """
    
    def __init__(self):
        self.scan_interval_minutes = 2
        self.reminder_buffer_minutes = 10
        # ✅ NEW: Track processed items in current scan to prevent duplicates
        self._processed_phones_this_scan = set()
    
    async def scan_and_process_events(self) -> Dict[str, Any]:
        """Main scanning method - scans BOTH database and Google Calendar"""
        try:
            logger.info("\n" + "="*80)
            logger.info("📅 CALENDAR MONITOR - Starting scan")
            logger.info("="*80)
            
            now = datetime.utcnow()
            
            # ✅ RESET: Clear processed phones for this scan
            self._processed_phones_this_scan = set()
            
            results = {
                "success": True,
                "total_events": 0,
                "follow_up_calls": 0,
                "reminders_sent": 0,
                "appointment_reminders": 0,
                "skipped_duplicates": 0,
                "errors": []
            }
            
            # ✅ STEP 1: Scan database for pending follow-ups (MOST IMPORTANT)
            logger.info("\n📊 STEP 1: Scanning database for pending follow-ups...")
            await self._scan_database_follow_ups(now, results)
            
            # ✅ STEP 2: Scan appointments collection for pending actions
            logger.info("\n📊 STEP 2: Scanning appointments for pending actions...")
            await self._scan_database_appointments(now, results)
            
            # ✅ STEP 3: Scan Google Calendar (for other events/reminders)
            logger.info("\n📊 STEP 3: Scanning Google Calendar...")
            await self._scan_google_calendar(now, results)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ SCAN COMPLETE")
            logger.info(f"   Follow-up calls initiated: {results['follow_up_calls']}")
            logger.info(f"   Skipped duplicates: {results['skipped_duplicates']}")
            logger.info(f"   Reminders sent: {results['reminders_sent']}")
            logger.info(f"   Appointment reminders: {results['appointment_reminders']}")
            logger.info(f"   Errors: {len(results['errors'])}")
            logger.info(f"{'='*80}\n")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Calendar monitor error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _scan_database_follow_ups(self, now: datetime, results: Dict[str, Any]):
        """
        Scan follow_ups collection for scheduled callbacks
        ✅ FIXED: Only processes follow-ups with status 'scheduled' or 'pending'
        ✅ FIXED: Immediately marks as 'processing' to prevent duplicates
        """
        try:
            db = await get_database()
            
            # Find all scheduled follow-ups that are due
            scan_start = now - timedelta(minutes=5)
            scan_end = now + timedelta(minutes=1)
            
            logger.info(f"   Scanning follow_ups: {scan_start} to {scan_end}")
            
            # ✅ FIXED: Only get follow-ups that haven't been processed
            pending_follow_ups = await db.follow_ups.find({
                "status": {"$in": ["scheduled", "pending"]},  # ✅ Only these statuses
                "scheduled_time": {
                    "$gte": scan_start,
                    "$lte": scan_end
                }
            }).to_list(length=100)
            
            logger.info(f"   Found {len(pending_follow_ups)} pending follow-ups in database")
            
            for follow_up in pending_follow_ups:
                try:
                    await self._process_database_follow_up(follow_up, results)
                except Exception as e:
                    logger.error(f"❌ Error processing follow-up {follow_up.get('_id')}: {e}")
                    results["errors"].append({
                        "follow_up_id": str(follow_up.get("_id")),
                        "error": str(e)
                    })
            
        except Exception as e:
            logger.error(f"❌ Error scanning database follow-ups: {e}", exc_info=True)
            results["errors"].append({"source": "database_follow_ups", "error": str(e)})
    
    async def _process_database_follow_up(self, follow_up: Dict[str, Any], results: Dict[str, Any]):
        """Process a follow-up from the database with duplicate prevention"""
        try:
            follow_up_id = str(follow_up["_id"])
            customer_phone = follow_up.get("customer_phone")
            customer_name = follow_up.get("customer_name", "Customer")
            user_id = follow_up.get("user_id")
            agent_id = follow_up.get("agent_id")
            original_request = follow_up.get("original_request", "")
            scheduled_time = follow_up.get("scheduled_time")
            
            logger.info(f"\n📞 Processing follow-up: {follow_up_id}")
            logger.info(f"   Customer: {customer_name}")
            logger.info(f"   Phone: {customer_phone}")
            logger.info(f"   Scheduled: {scheduled_time}")
            logger.info(f"   Status: {follow_up.get('status')}")
            
            if not customer_phone:
                logger.error(f"❌ No phone number for follow-up {follow_up_id}")
                return
            
            # ✅ DUPLICATE CHECK 1: Already processed this phone in current scan?
            if customer_phone in self._processed_phones_this_scan:
                logger.info(f"⏭️ Phone {customer_phone} already processed in this scan, skipping")
                results["skipped_duplicates"] += 1
                return
            
            db = await get_database()
            
            # ✅ DUPLICATE CHECK 2: Already has an active/recent call?
            recent_call = await db.calls.find_one({
                "to_number": customer_phone,
                "call_type": "follow_up_call",
                "created_at": {"$gte": datetime.utcnow() - timedelta(minutes=10)},
                "status": {"$in": ["initiated", "queued", "ringing", "in-progress", "completed"]}
            })
            
            if recent_call:
                logger.info(f"⏭️ Recent call already exists for {customer_phone}, skipping")
                logger.info(f"   Existing call: {recent_call.get('call_sid')} - Status: {recent_call.get('status')}")
                results["skipped_duplicates"] += 1
                
                # ✅ Update follow-up status to prevent future scans
                await db.follow_ups.update_one(
                    {"_id": follow_up["_id"]},
                    {
                        "$set": {
                            "status": "call_already_made",
                            "existing_call_id": str(recent_call.get("_id")),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                return
            
            # ✅ DUPLICATE CHECK 3: Follow-up status changed since query?
            current_follow_up = await db.follow_ups.find_one({"_id": follow_up["_id"]})
            if current_follow_up and current_follow_up.get("status") not in ["scheduled", "pending"]:
                logger.info(f"⏭️ Follow-up {follow_up_id} status changed to {current_follow_up.get('status')}, skipping")
                results["skipped_duplicates"] += 1
                return
            
            # ✅ IMMEDIATELY mark as processing to prevent race conditions
            update_result = await db.follow_ups.update_one(
                {
                    "_id": follow_up["_id"],
                    "status": {"$in": ["scheduled", "pending"]}  # ✅ Only update if still pending
                },
                {
                    "$set": {
                        "status": "processing",
                        "processing_started_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # ✅ If no document was modified, another process got it first
            if update_result.modified_count == 0:
                logger.info(f"⏭️ Follow-up {follow_up_id} already being processed by another worker")
                results["skipped_duplicates"] += 1
                return
            
            # ✅ Mark phone as processed for this scan
            self._processed_phones_this_scan.add(customer_phone)
            
            logger.info(f"✅ Locked follow-up {follow_up_id} for processing")
            
            # ✅ INITIATE THE CALL
            call_response = await outbound_call_service.initiate_follow_up_call(
                customer_phone=customer_phone,
                customer_name=customer_name,
                user_id=user_id or "system",
                agent_id=agent_id,
                appointment_id=follow_up_id,
                original_request=original_request,
                callback_reason="follow_up"
            )
            
            if call_response.get("success"):
                logger.info(f"✅ CALL INITIATED SUCCESSFULLY!")
                logger.info(f"   Call SID: {call_response.get('call_sid')}")
                
                # Update follow-up with call info
                await db.follow_ups.update_one(
                    {"_id": follow_up["_id"]},
                    {
                        "$set": {
                            "status": "call_initiated",
                            "call_id": call_response.get("call_id"),
                            "call_sid": call_response.get("call_sid"),
                            "call_initiated_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                results["follow_up_calls"] += 1
                
            else:
                logger.error(f"❌ Call initiation failed: {call_response.get('error')}")
                
                # Update follow-up with error
                await db.follow_ups.update_one(
                    {"_id": follow_up["_id"]},
                    {
                        "$set": {
                            "status": "call_failed",
                            "error": call_response.get("error"),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                results["errors"].append({
                    "follow_up_id": follow_up_id,
                    "error": call_response.get("error")
                })
            
        except Exception as e:
            logger.error(f"❌ Error processing database follow-up: {e}", exc_info=True)
            raise
    
    async def _scan_database_appointments(self, now: datetime, results: Dict[str, Any]):
        """
        Scan appointments collection for pending follow-up actions
        ✅ FIXED: Checks for duplicates before processing
        """
        try:
            db = await get_database()
            
            scan_start = now - timedelta(minutes=5)
            scan_end = now + timedelta(minutes=1)
            
            logger.info(f"   Scanning appointments: {scan_start} to {scan_end}")
            
            # ✅ FIXED: Only get appointments that haven't been completed
            pending_appointments = await db.appointments.find({
                "event_type": "follow_up_call",
                "action_completed": {"$ne": True},
                "status": {"$in": ["pending_action", "scheduled"]},  # ✅ Not 'in_progress' or 'processing'
                "appointment_date": {
                    "$gte": scan_start,
                    "$lte": scan_end
                }
            }).to_list(length=100)
            
            logger.info(f"   Found {len(pending_appointments)} pending appointments")
            
            for appointment in pending_appointments:
                try:
                    await self._process_database_appointment(appointment, results)
                except Exception as e:
                    logger.error(f"❌ Error processing appointment {appointment.get('_id')}: {e}")
                    results["errors"].append({
                        "appointment_id": str(appointment.get("_id")),
                        "error": str(e)
                    })
            
        except Exception as e:
            logger.error(f"❌ Error scanning database appointments: {e}", exc_info=True)
            results["errors"].append({"source": "database_appointments", "error": str(e)})
    
    async def _process_database_appointment(self, appointment: Dict[str, Any], results: Dict[str, Any]):
        """Process an appointment from the database with duplicate prevention"""
        try:
            appointment_id = str(appointment["_id"])
            customer_phone = appointment.get("customer_phone")
            customer_name = appointment.get("customer_name", "Customer")
            user_id = appointment.get("user_id")
            agent_id = appointment.get("agent_id")
            original_request = appointment.get("notes") or appointment.get("original_user_request", "")
            
            logger.info(f"\n📅 Processing appointment: {appointment_id}")
            logger.info(f"   Customer: {customer_name}")
            logger.info(f"   Phone: {customer_phone}")
            
            if not customer_phone:
                logger.error(f"❌ No phone number for appointment {appointment_id}")
                return
            
            # ✅ DUPLICATE CHECK 1: Already processed this phone in current scan?
            if customer_phone in self._processed_phones_this_scan:
                logger.info(f"⏭️ Phone {customer_phone} already processed in this scan, skipping appointment")
                results["skipped_duplicates"] += 1
                return
            
            db = await get_database()
            
            # ✅ DUPLICATE CHECK 2: Already has an active/recent call?
            recent_call = await db.calls.find_one({
                "to_number": customer_phone,
                "call_type": "follow_up_call",
                "created_at": {"$gte": datetime.utcnow() - timedelta(minutes=10)},
                "status": {"$in": ["initiated", "queued", "ringing", "in-progress", "completed"]}
            })
            
            if recent_call:
                logger.info(f"⏭️ Recent call already exists for {customer_phone}, skipping appointment")
                results["skipped_duplicates"] += 1
                
                # ✅ Mark appointment as already handled
                await db.appointments.update_one(
                    {"_id": appointment["_id"]},
                    {
                        "$set": {
                            "action_completed": True,
                            "action_result": "call_already_made",
                            "existing_call_id": str(recent_call.get("_id")),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                return
            
            # ✅ IMMEDIATELY mark as processing
            update_result = await db.appointments.update_one(
                {
                    "_id": appointment["_id"],
                    "status": {"$in": ["pending_action", "scheduled"]}
                },
                {
                    "$set": {
                        "status": "processing",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count == 0:
                logger.info(f"⏭️ Appointment {appointment_id} already being processed")
                results["skipped_duplicates"] += 1
                return
            
            # ✅ Mark phone as processed
            self._processed_phones_this_scan.add(customer_phone)
            
            # ✅ INITIATE THE CALL
            call_response = await outbound_call_service.initiate_follow_up_call(
                customer_phone=customer_phone,
                customer_name=customer_name,
                user_id=user_id or "system",
                agent_id=agent_id,
                appointment_id=appointment_id,
                original_request=original_request,
                callback_reason="follow_up"
            )
            
            if call_response.get("success"):
                logger.info(f"✅ CALL INITIATED SUCCESSFULLY!")
                
                await db.appointments.update_one(
                    {"_id": appointment["_id"]},
                    {
                        "$set": {
                            "action_completed": True,
                            "action_completed_at": datetime.utcnow(),
                            "action_result": "call_initiated",
                            "call_id": call_response.get("call_id"),
                            "call_sid": call_response.get("call_sid"),
                            "status": "call_initiated"
                        }
                    }
                )
                
                results["follow_up_calls"] += 1
                
            else:
                logger.error(f"❌ Call initiation failed: {call_response.get('error')}")
                
                await db.appointments.update_one(
                    {"_id": appointment["_id"]},
                    {
                        "$set": {
                            "status": "call_failed",
                            "action_result": "call_failed",
                            "action_error": call_response.get("error")
                        }
                    }
                )
            
        except Exception as e:
            logger.error(f"❌ Error processing appointment: {e}", exc_info=True)
            raise
    
    async def _scan_google_calendar(self, now: datetime, results: Dict[str, Any]):
        """Scan Google Calendar for events (original logic)"""
        try:
            scan_window_start = now - timedelta(minutes=self.reminder_buffer_minutes)
            scan_window_end = now + timedelta(minutes=self.reminder_buffer_minutes)
            
            logger.info(f"   Scan window: {scan_window_start} to {scan_window_end}")
            
            # Get events from Google Calendar
            calendar_events = await google_calendar_service.get_events(
                time_min=scan_window_start,
                time_max=scan_window_end
            )
            
            if not calendar_events.get("success"):
                logger.warning(f"⚠️ Could not retrieve calendar events: {calendar_events.get('error')}")
                return
            
            events = calendar_events.get("events", [])
            logger.info(f"   Found {len(events)} Google Calendar events")
            
            results["total_events"] += len(events)
            
            for event in events:
                try:
                    await self._process_google_calendar_event(event, results)
                except Exception as e:
                    logger.error(f"❌ Error processing event {event.get('id')}: {e}")
                    results["errors"].append({
                        "event_id": event.get("id"),
                        "error": str(e)
                    })
            
        except Exception as e:
            logger.error(f"❌ Error scanning Google Calendar: {e}", exc_info=True)
            results["errors"].append({"source": "google_calendar", "error": str(e)})
    
    async def _process_google_calendar_event(self, event: Dict[str, Any], results: Dict[str, Any]):
        """Process a single Google Calendar event with duplicate prevention"""
        try:
            event_id = event.get("id")
            event_summary = event.get("summary", "Unknown")
            
            # Get extended properties (our metadata)
            ext_props = event.get("extendedProperties", {}).get("private", {})
            event_type = ext_props.get("event_type", "appointment")
            action_type = ext_props.get("action_type", "none")
            customer_phone = ext_props.get("customer_phone")
            
            logger.info(f"\n📌 Processing Google Calendar event: {event_summary}")
            logger.info(f"   Event ID: {event_id}")
            logger.info(f"   Type: {event_type}")
            logger.info(f"   Action: {action_type}")
            
            # Check if already processed
            if await self._is_event_processed(event_id):
                logger.info(f"⏭️ Event already processed, skipping")
                results["skipped_duplicates"] += 1
                return
            
            # ✅ DUPLICATE CHECK: Phone already processed in this scan?
            if customer_phone and customer_phone in self._processed_phones_this_scan:
                logger.info(f"⏭️ Phone {customer_phone} already processed in this scan, skipping calendar event")
                results["skipped_duplicates"] += 1
                await self._mark_event_processed(event_id, "skipped_duplicate", None)
                return
            
            # Route to appropriate handler
            if event_type == "follow_up_call" and action_type == "call":
                await self._handle_follow_up_call(event, ext_props, results)
            
            elif event_type == "reminder":
                await self._handle_reminder(event, ext_props, results)
            
            elif event_type == "appointment":
                await self._handle_appointment_reminder(event, ext_props, results)
            
        except Exception as e:
            logger.error(f"❌ Error processing Google Calendar event: {e}", exc_info=True)
            raise
    
    async def _handle_follow_up_call(
        self,
        event: Dict[str, Any],
        ext_props: Dict[str, Any],
        results: Dict[str, Any]
    ):
        """Handle follow-up call event from Google Calendar with duplicate prevention"""
        try:
            logger.info("📞 HANDLING FOLLOW-UP CALL FROM GOOGLE CALENDAR")
            
            event_id = event.get("id")
            customer_phone = ext_props.get("customer_phone")
            customer_name = ext_props.get("customer_name", "Customer")
            original_request = ext_props.get("original_request", "")
            user_id = ext_props.get("user_id")
            agent_id = ext_props.get("agent_id")
            
            if not customer_phone:
                logger.error("❌ No customer phone number in event")
                return
            
            # ✅ DUPLICATE CHECK: Phone already processed?
            if customer_phone in self._processed_phones_this_scan:
                logger.info(f"⏭️ Phone {customer_phone} already called, skipping")
                results["skipped_duplicates"] += 1
                await self._mark_event_processed(event_id, "skipped_duplicate", None)
                return
            
            db = await get_database()
            
            # ✅ DUPLICATE CHECK: Recent call exists?
            recent_call = await db.calls.find_one({
                "to_number": customer_phone,
                "call_type": "follow_up_call",
                "created_at": {"$gte": datetime.utcnow() - timedelta(minutes=10)},
                "status": {"$in": ["initiated", "queued", "ringing", "in-progress", "completed"]}
            })
            
            if recent_call:
                logger.info(f"⏭️ Recent call already exists for {customer_phone}")
                results["skipped_duplicates"] += 1
                await self._mark_event_processed(event_id, "call_already_made", str(recent_call.get("_id")))
                return
            
            # ✅ Mark phone as processed
            self._processed_phones_this_scan.add(customer_phone)
            
            # Initiate call
            call_response = await outbound_call_service.initiate_follow_up_call(
                customer_phone=customer_phone,
                customer_name=customer_name,
                user_id=user_id or "system",
                agent_id=agent_id,
                appointment_id=None,
                original_request=original_request,
                callback_reason="follow_up"
            )
            
            if call_response.get("success"):
                logger.info(f"✅ Call initiated successfully!")
                await self._mark_event_processed(event_id, "call_initiated", call_response.get("call_id"))
                results["follow_up_calls"] += 1
            else:
                logger.error(f"❌ Call initiation failed: {call_response.get('error')}")
                await self._mark_event_processed(event_id, "call_failed", None)
            
        except Exception as e:
            logger.error(f"❌ Error handling follow-up call: {e}", exc_info=True)
            raise
    
    async def _handle_reminder(
        self,
        event: Dict[str, Any],
        ext_props: Dict[str, Any],
        results: Dict[str, Any]
    ):
        """Handle reminder event"""
        try:
            logger.info("📢 HANDLING REMINDER")
            
            event_id = event.get("id")
            customer_phone = ext_props.get("customer_phone")
            customer_email = ext_props.get("customer_email")
            customer_name = ext_props.get("customer_name", "Customer")
            action_type = ext_props.get("action_type", "sms")
            original_request = ext_props.get("original_request", "")
            
            reminder_message = f"Hi {customer_name}, this is a friendly reminder: {original_request}"
            
            if action_type == "sms" and customer_phone:
                logger.info(f"📱 Sending SMS to {customer_phone}")
                
                sms_result = await sms_service.send_sms(
                    to_number=customer_phone,
                    message=reminder_message,
                    user_id=ext_props.get("user_id", "system"),
                    metadata={"event_id": event_id, "type": "reminder"}
                )
                
                if sms_result.get("success"):
                    logger.info("✅ Reminder SMS sent")
                    results["reminders_sent"] += 1
                    await self._mark_event_processed(event_id, "reminder_sent", None)
                else:
                    logger.error(f"❌ SMS failed: {sms_result.get('error')}")
            
            elif action_type == "email" and customer_email:
                logger.info(f"📧 Sending email to {customer_email}")
                
                email_result = await email_automation_service.send_email(
                    to_email=customer_email,
                    subject="Reminder",
                    html_content=f"<p>{reminder_message}</p>",
                    text_content=reminder_message,
                    user_id=ext_props.get("user_id", "system")
                )
                
                if email_result:
                    logger.info("✅ Reminder email sent")
                    results["reminders_sent"] += 1
                    await self._mark_event_processed(event_id, "reminder_sent", None)
                else:
                    logger.error("❌ Email failed")
            
        except Exception as e:
            logger.error(f"❌ Error handling reminder: {e}", exc_info=True)
            raise
    
    async def _handle_appointment_reminder(
        self,
        event: Dict[str, Any],
        ext_props: Dict[str, Any],
        results: Dict[str, Any]
    ):
        """Handle appointment reminder"""
        try:
            logger.info("📅 HANDLING APPOINTMENT REMINDER")
            
            event_id = event.get("id")
            customer_phone = ext_props.get("customer_phone")
            customer_name = ext_props.get("customer_name", "Customer")
            
            if customer_phone:
                reminder_message = f"Hi {customer_name}, this is a reminder that your appointment is coming up soon!"
                
                sms_result = await sms_service.send_sms(
                    to_number=customer_phone,
                    message=reminder_message,
                    user_id=ext_props.get("user_id", "system")
                )
                
                if sms_result.get("success"):
                    logger.info("✅ Appointment reminder sent")
                    results["appointment_reminders"] += 1
                    await self._mark_event_processed(event_id, "reminder_sent", None)
                else:
                    logger.error(f"❌ Reminder failed: {sms_result.get('error')}")
            
        except Exception as e:
            logger.error(f"❌ Error sending appointment reminder: {e}", exc_info=True)
            raise
    
    async def _is_event_processed(self, event_id: str) -> bool:
        """Check if event has already been processed"""
        try:
            db = await get_database()
            
            processed = await db.processed_calendar_events.find_one({
                "event_id": event_id
            })
            
            return processed is not None
            
        except Exception as e:
            logger.error(f"Error checking if event processed: {e}")
            return False
    
    async def _mark_event_processed(
        self,
        event_id: str,
        action_taken: str,
        call_id: Optional[str] = None
    ):
        """Mark event as processed"""
        try:
            db = await get_database()
            
            processed_data = {
                "event_id": event_id,
                "action_taken": action_taken,
                "call_id": call_id,
                "processed_at": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }
            
            await db.processed_calendar_events.insert_one(processed_data)
            
            logger.info(f"✅ Marked event {event_id} as processed")
            
        except Exception as e:
            logger.error(f"Error marking event processed: {e}")


# Singleton instance
calendar_monitor_service = CalendarMonitorService()
