# backend/app/api/v1/email_webhook.py - EMAIL INBOUND WEBHOOK WITH AI RESPONSE (FIXED)

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Dict, Any, Optional
import logging
import re
import json
import dateparser

from app.database import get_database
from app.services.openai import openai_service
from app.services.email_automation import email_automation_service
from app.services.email import email_service
from app.utils.credential_resolver import resolve_email_credentials

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# HELPER: Extract email address from string
# ============================================
def extract_email(email_string: str) -> str:
    """Extract email address from string like 'Name <email@example.com>'"""
    if not email_string:
        return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_string)
    return match.group(0) if match else email_string


# ============================================
# HELPER: Get conversation state for email
# ============================================
async def _get_email_conversation_state(email_address: str, user_id: str, db) -> Dict[str, Any]:
    """Get or create conversation state for email thread"""
    state = await db.email_conversation_states.find_one({
        "email_address": email_address,
        "user_id": user_id
    })
    
    if not state:
        state = {
            "email_address": email_address,
            "user_id": user_id,
            "booking_in_progress": False,
            "current_step": None,
            "collected_data": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.email_conversation_states.insert_one(state)
    
    return state


# ============================================
# HELPER: Update conversation state
# ============================================
async def _update_email_conversation_state(
    email_address: str, 
    user_id: str, 
    updates: Dict[str, Any], 
    db
):
    """Update conversation state for email thread"""
    updates["updated_at"] = datetime.utcnow()
    
    await db.email_conversation_states.update_one(
        {"email_address": email_address, "user_id": user_id},
        {"$set": updates},
        upsert=True
    )


# ============================================
# HELPER: Match Campaign Builder workflow
# ============================================
async def _match_email_campaign_workflow(
    user_input: str,
    user_id: str,
    db
) -> Optional[Dict[str, Any]]:
    """Check if user input matches any Campaign Builder workflow"""
    try:
        # Get all active workflows for user
        workflows = await db.workflows.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(length=100)
        
        if not workflows:
            return None
        
        user_input_lower = user_input.lower().strip()
        user_words = set(user_input_lower.split())
        
        for workflow in workflows:
            workflow_name = workflow.get("name", "Unknown")
            nodes = workflow.get("nodes", [])
            
            for node in nodes:
                node_data = node.get("data", {})
                keywords = node_data.get("keywords", [])
                
                if not keywords:
                    continue
                
                for keyword in keywords:
                    keyword_clean = keyword.lower().strip()
                    
                    # Check for keyword match
                    if keyword_clean in user_input_lower or keyword_clean in user_words:
                        node_message = node_data.get("message", "")
                        
                        if node_message:
                            logger.info(f"✅ Email Campaign match: '{keyword_clean}' in {workflow_name}")
                            
                            return {
                                "found": True,
                                "response": node_message,
                                "workflow_id": str(workflow["_id"]),
                                "workflow_name": workflow_name,
                                "node_id": node.get("id"),
                                "matched_keyword": keyword_clean
                            }
        
        return None
        
    except Exception as e:
        logger.error(f"Email campaign matching error: {e}")
        return None


# ============================================
# HELPER: Process appointment booking via email
# ============================================
async def _process_email_appointment_booking(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    email_address: str,
    db
) -> Dict[str, Any]:
    """Process appointment booking via email using AI-powered entity extraction"""
    from app.services.booking_extractor import extract_booking_fields, validate_and_parse_datetime
    from app.api.v1.business_profile import get_business_context_for_ai

    collected_data = conversation_state.get("collected_data", {})
    print(f"[EMAIL-BOOKING] AI extraction - collected so far: {collected_data}")

    # 1. Load conversation history from email_logs
    history_cursor = db.email_logs.find({
        "user_id": user_id,
        "$or": [
            {"to_email": email_address},
            {"from_email": email_address}
        ]
    }).sort("created_at", -1).limit(10)
    history = await history_cursor.to_list(length=10)
    history.reverse()

    conversation_history = []
    for msg in history:
        role = "user" if msg.get("direction") == "inbound" else "assistant"
        content = msg.get("content") or msg.get("text_content") or ""
        conversation_history.append({"role": role, "content": content})

    # 2. Get business context
    business_context = await get_business_context_for_ai(user_id, db)

    # 3. AI extraction (email also needs phone)
    extraction = await extract_booking_fields(
        current_message=user_message,
        conversation_history=conversation_history,
        already_collected=collected_data,
        business_context=business_context,
        channel="email"
    )

    # 4. Handle non-booking messages
    if not extraction.get("is_booking_response", True):
        return {"response": extraction.get("response", "How can I help with your booking?")}

    # 5. Merge extracted data
    extracted = extraction.get("extracted", {})
    for field in ["name", "email", "service", "phone"]:
        if extracted.get(field):
            collected_data[field] = extracted[field]
    if extracted.get("datetime_text"):
        collected_data["datetime_text"] = extracted["datetime_text"]

    # Email address is already known
    collected_data["email"] = email_address

    print(f"[EMAIL-BOOKING] After merge: {collected_data}")

    # 6. Check completeness (email booking needs: name, phone, service, datetime_text)
    required = ["name", "phone", "service", "datetime_text"]
    missing = [f for f in required if not collected_data.get(f)]

    if not missing:
        # Validate datetime
        dt_result = await validate_and_parse_datetime(
            collected_data["datetime_text"], business_context
        )

        if not dt_result["success"]:
            if dt_result.get("error") == "weekend":
                await _update_email_conversation_state(
                    email_address, user_id, {"collected_data": collected_data}, db
                )
                return {"response": f"That date falls on a weekend — we're available Monday to Friday. Would {dt_result['suggestion']} work instead?"}
            elif dt_result.get("error") == "outside_hours":
                await _update_email_conversation_state(
                    email_address, user_id, {"collected_data": collected_data}, db
                )
                return {"response": f"That's outside our business hours (9 AM - 5 PM). How about {dt_result['suggestion']}?"}
            else:
                collected_data.pop("datetime_text", None)
                await _update_email_conversation_state(
                    email_address, user_id, {"collected_data": collected_data}, db
                )
                return {"response": "I couldn't determine the date from that. Could you try something like 'Monday at 10am' or 'tomorrow at 2pm'?"}

        parsed_date = dt_result["parsed_date"]
        date_display = parsed_date.strftime("%A, %B %d, %Y at %I:%M %p")

        # Check for time slot conflicts
        duration_minutes = 60
        appointment_end = parsed_date + timedelta(minutes=duration_minutes)
        conflict = await db.appointments.find_one({
            "user_id": user_id,
            "status": {"$in": ["scheduled", "confirmed"]},
            "appointment_date": {
                "$gte": parsed_date,
                "$lt": appointment_end
            }
        })
        if conflict:
            conflict_time = conflict.get("appointment_date")
            collected_data.pop("datetime_text", None)
            await _update_email_conversation_state(
                email_address, user_id, {"collected_data": collected_data}, db
            )
            conflict_str = conflict_time.strftime("%I:%M %p") if conflict_time else "that time"
            return {"response": f"Sorry, the {conflict_str} slot is already booked. Could you pick a different time? Our hours are Monday-Friday, 9 AM to 5 PM."}

        # Create appointment in database
        appointment_data = {
            "user_id": user_id,
            "customer_name": collected_data.get("name"),
            "customer_email": email_address,
            "customer_phone": collected_data.get("phone"),
            "service_type": collected_data.get("service") or "Consultation",
            "appointment_date": parsed_date,
            "appointment_time": parsed_date.strftime("%H:%M"),
            "duration_minutes": duration_minutes,
            "status": "scheduled",
            "source": "email",
            "notes": "Booked via email conversation",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "reminder_sent": False
        }

        result = await db.appointments.insert_one(appointment_data)

        # Reset conversation state
        await _update_email_conversation_state(
            email_address, user_id,
            {"booking_in_progress": False, "current_step": None, "collected_data": {}},
            db
        )

        # Send confirmation email
        try:
            await email_automation_service.send_appointment_confirmation(
                to_email=email_address,
                customer_name=collected_data.get("name"),
                customer_phone=collected_data.get("phone", ""),
                service_type=collected_data.get("service") or "Consultation",
                appointment_date=date_display,
                user_id=user_id,
                appointment_id=str(result.inserted_id)
            )
        except Exception as e:
            logger.error(f"Failed to send appointment confirmation: {e}")

        response = f"""Your appointment has been confirmed!

Appointment Details:
- Name: {collected_data['name']}
- Phone: {collected_data['phone']}
- Service: {collected_data.get('service', 'Consultation')}
- Date & Time: {date_display}

You'll receive a reminder email 30 minutes before your appointment. If you need to reschedule, please let us know!"""

        return {"response": response, "appointment_id": str(result.inserted_id)}

    # 7. Fields still missing — save progress and ask
    await _update_email_conversation_state(
        email_address, user_id,
        {"current_step": "ai_collecting", "collected_data": collected_data},
        db
    )

    return {"response": extraction.get("response", "Could you provide the remaining booking details?")}


# ============================================
# HELPER: Process appointment reschedule via Email
# ============================================
async def _process_email_appointment_reschedule(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    email_address: str,
    db
) -> Dict[str, Any]:
    """Process appointment reschedule via email using AI extraction"""
    from app.services.booking_extractor import extract_reschedule_fields, validate_and_parse_datetime
    from app.api.v1.business_profile import get_business_context_for_ai

    reschedule_data = conversation_state.get("reschedule_data", {})
    appointment_id = reschedule_data.get("appointment_id")

    # Find customer's active appointment
    if not appointment_id:
        appointment = await db.appointments.find_one({
            "user_id": user_id,
            "customer_email": email_address,
            "status": {"$in": ["scheduled", "confirmed"]}
        }, sort=[("appointment_date", -1)])

        if not appointment:
            await _update_email_conversation_state(
                email_address, user_id,
                {"reschedule_in_progress": False, "reschedule_data": {}}, db
            )
            return {"response": "I couldn't find an active appointment for your email address. Would you like to book a new one?"}

        appointment_id = str(appointment["_id"])
        reschedule_data["appointment_id"] = appointment_id
        reschedule_data["appointment"] = {
            "service_type": appointment.get("service_type", "appointment"),
            "appointment_date": appointment.get("appointment_date"),
            "customer_name": appointment.get("customer_name", "")
        }

    existing_appointment = reschedule_data.get("appointment", {})

    # Load conversation history
    history_cursor = db.email_logs.find({
        "user_id": user_id,
        "$or": [{"to_email": email_address}, {"from_email": email_address}]
    }).sort("created_at", -1).limit(6)
    history = await history_cursor.to_list(length=6)
    history.reverse()
    conversation_history = [
        {"role": "user" if m.get("direction") == "inbound" else "assistant",
         "content": m.get("content") or m.get("text_content") or ""}
        for m in history
    ]

    # AI extraction
    extraction = await extract_reschedule_fields(
        current_message=user_message,
        conversation_history=conversation_history,
        existing_appointment=existing_appointment,
        channel="email"
    )

    print(f"[EMAIL-RESCHEDULE] Extraction: {extraction}")

    # Handle cancel request mid-reschedule
    if extraction.get("is_cancel_request"):
        from bson import ObjectId
        await db.appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {"status": "cancelled", "cancellation_reason": "Cancelled by customer via email", "cancelled_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        await _update_email_conversation_state(
            email_address, user_id,
            {"reschedule_in_progress": False, "reschedule_data": {}}, db
        )
        return {"response": "Your appointment has been cancelled. If you'd like to book a new one in the future, just let us know!"}

    # If new datetime provided, validate and update
    if extraction.get("new_datetime_text"):
        business_context = await get_business_context_for_ai(user_id, db)
        dt_result = await validate_and_parse_datetime(extraction["new_datetime_text"], business_context)

        if not dt_result["success"]:
            if dt_result.get("error") == "weekend":
                return {"response": f"That date falls on a weekend. How about {dt_result['suggestion']} instead?"}
            elif dt_result.get("error") == "outside_hours":
                return {"response": f"That's outside our business hours (9 AM - 5 PM). Would {dt_result['suggestion']} work?"}
            else:
                return {"response": "I couldn't determine the date from that. Could you try something like 'next Tuesday at 2pm'?"}

        parsed_date = dt_result["parsed_date"]

        # Check time conflict
        from bson import ObjectId
        appointment_end = parsed_date + timedelta(minutes=60)
        conflict = await db.appointments.find_one({
            "user_id": user_id,
            "_id": {"$ne": ObjectId(appointment_id)},
            "status": {"$in": ["scheduled", "confirmed"]},
            "appointment_date": {"$gte": parsed_date, "$lt": appointment_end}
        })
        if conflict:
            return {"response": "Sorry, that time slot is already booked. Could you pick a different time?"}

        # Update appointment
        await db.appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {
                "appointment_date": parsed_date,
                "appointment_time": parsed_date.strftime("%H:%M"),
                "status": "scheduled",
                "updated_at": datetime.utcnow()
            }}
        )
        await _update_email_conversation_state(
            email_address, user_id,
            {"reschedule_in_progress": False, "reschedule_data": {}}, db
        )
        formatted_date = parsed_date.strftime("%A, %B %d, %Y at %I:%M %p")
        return {"response": f"Your {existing_appointment.get('service_type', 'appointment')} has been rescheduled to {formatted_date}. We look forward to seeing you!"}

    # No datetime yet — save state and ask
    await _update_email_conversation_state(
        email_address, user_id,
        {"reschedule_in_progress": True, "reschedule_data": reschedule_data}, db
    )
    return {"response": extraction.get("response", "When would you like to reschedule your appointment to? Please provide a new date and time.")}


# ============================================
# HELPER: Process appointment cancellation via Email
# ============================================
async def _process_email_appointment_cancel(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    email_address: str,
    db
) -> Dict[str, Any]:
    """Process appointment cancellation via email"""
    from bson import ObjectId

    cancel_data = conversation_state.get("cancel_data", {})
    appointment_id = cancel_data.get("appointment_id")
    awaiting_confirmation = cancel_data.get("awaiting_confirmation", False)

    # If awaiting confirmation
    if awaiting_confirmation and appointment_id:
        lower = user_message.lower().strip()
        if any(w in lower for w in ["yes", "confirm", "ok", "okay", "sure", "go ahead", "please cancel"]):
            await db.appointments.update_one(
                {"_id": ObjectId(appointment_id)},
                {"$set": {"status": "cancelled", "cancellation_reason": "Cancelled by customer via email", "cancelled_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
            )
            await _update_email_conversation_state(
                email_address, user_id,
                {"cancel_in_progress": False, "cancel_data": {}}, db
            )
            return {"response": "Your appointment has been cancelled. If you'd like to book a new one, just let us know!"}
        elif any(w in lower for w in ["no", "nah", "keep", "nevermind", "never mind"]):
            await _update_email_conversation_state(
                email_address, user_id,
                {"cancel_in_progress": False, "cancel_data": {}}, db
            )
            return {"response": "No worries! Your appointment is still confirmed. Let us know if you need anything else."}
        else:
            return {"response": "Please reply YES to confirm cancellation, or NO to keep your appointment."}

    # Find appointment and ask for confirmation
    if not appointment_id:
        appointment = await db.appointments.find_one({
            "user_id": user_id,
            "customer_email": email_address,
            "status": {"$in": ["scheduled", "confirmed"]}
        }, sort=[("appointment_date", -1)])

        if not appointment:
            await _update_email_conversation_state(
                email_address, user_id,
                {"cancel_in_progress": False, "cancel_data": {}}, db
            )
            return {"response": "I couldn't find an active appointment for your email address. Would you like to book a new one?"}

        appointment_id = str(appointment["_id"])
        appt_date = appointment.get("appointment_date", "")
        if isinstance(appt_date, datetime):
            appt_date = appt_date.strftime("%A, %B %d at %I:%M %p")
        service = appointment.get("service_type", "appointment")

        await _update_email_conversation_state(
            email_address, user_id,
            {"cancel_in_progress": True, "cancel_data": {
                "appointment_id": appointment_id,
                "awaiting_confirmation": True,
                "appointment": {"service_type": service, "appointment_date": appt_date}
            }}, db
        )
        return {"response": f"Are you sure you want to cancel your {service} appointment on {appt_date}? Please reply YES to confirm or NO to keep it."}

    return {"response": "Please reply YES to confirm cancellation, or NO to keep your appointment."}


# ============================================
# MAIN WEBHOOK: SendGrid Inbound Parse
# ============================================
@router.post("/webhook/inbound")
async def email_inbound_webhook(
    request: Request,
    db = Depends(get_database)
):
    """
    ✅ Handle incoming email webhook with AI response logic:
    - Priority 1: Appointment booking flow (if in progress and not changing topic)
    - Priority 2: New appointment booking request
    - Priority 3: Campaign Builder responses
    - Priority 4: OpenAI fallback
    
    This endpoint receives emails from SendGrid Inbound Parse or similar services.
    """
    try:
        # Parse form data (SendGrid sends as multipart form)
        form_data = await request.form()
        
        # Extract email fields
        from_email = extract_email(form_data.get("from", ""))
        to_email = extract_email(form_data.get("to", ""))
        subject = form_data.get("subject", "")
        text_body = form_data.get("text", "")
        html_body = form_data.get("html", "")
        
        # Use text body, fallback to stripped HTML
        body = text_body.strip() if text_body else ""
        if not body and html_body:
            # Simple HTML strip
            body = re.sub(r'<[^>]+>', '', html_body).strip()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📨 INCOMING EMAIL WEBHOOK")
        logger.info(f"{'='*80}")
        logger.info(f"   From: {from_email}")
        logger.info(f"   To: {to_email}")
        logger.info(f"   Subject: {subject}")
        logger.info(f"   Body: {body[:200]}...")
        logger.info(f"{'='*80}\n")
        
        # ============================================
        # MATCH USER: Find the correct user by to_email
        # ============================================
        # Strategy 1: Match by integration_config from_email
        primary_user = await db.users.find_one({
            "integration_config.email.from_email": to_email,
            "is_active": True
        })

        # Strategy 2: Match by user's own email
        if not primary_user:
            primary_user = await db.users.find_one({
                "email": to_email,
                "is_active": True
            })

        # Strategy 3: Match by to_email domain against user emails
        if not primary_user:
            to_domain = to_email.split("@")[-1] if "@" in to_email else ""
            if to_domain:
                domain_users = await db.users.find({
                    "email": {"$regex": f"@{re.escape(to_domain)}$", "$options": "i"},
                    "is_active": True
                }).to_list(length=10)
                if domain_users:
                    primary_user = domain_users[0]

        # Strategy 4: Check if there's a previous email conversation with this sender
        if not primary_user:
            prev_email = await db.email_logs.find_one({
                "to_email": from_email,
                "direction": "outbound",
                "user_id": {"$exists": True}
            }, sort=[("created_at", -1)])
            if prev_email and prev_email.get("user_id"):
                primary_user = await db.users.find_one({
                    "_id": ObjectId(prev_email["user_id"]),
                    "is_active": True
                })

        # Strategy 5: Fallback to first active admin/superadmin user
        if not primary_user:
            primary_user = await db.users.find_one({
                "is_active": True,
                "role": {"$in": ["superadmin", "admin"]}
            })

        if not primary_user:
            logger.warning(f"⚠️ No matching user found for to_email: {to_email}")
            return JSONResponse(
                status_code=200,
                content={"status": "no_matching_user", "to_email": to_email}
            )

        user_id = str(primary_user["_id"])

        logger.info(f"📌 Matched user_id: {user_id} ({primary_user.get('email', 'Unknown')}) for to_email: {to_email}")
        
        # ============================================
        # STEP 1: Store incoming email for matched user
        # ============================================
        email_log_data = {
            "user_id": user_id,
            "to_email": to_email,
            "from_email": from_email,
            "subject": subject,
            "content": body,
            "text_content": text_body,
            "html_content": html_body,
            "status": "received",
            "direction": "inbound",
            "created_at": datetime.utcnow(),
            "opened_count": 0,
            "clicked_count": 0,
            "clicked_links": []
        }

        await db.email_logs.insert_one(email_log_data)

        logger.info(f"✅ Incoming email stored for user: {user_id}")
        
        # ============================================
        # STEP 2: Generate AI Response
        # ============================================
        
        ai_message = None
        source = "none"
        
        # Combine subject and body for processing
        full_message = f"{subject}\n\n{body}" if subject else body
        # Use BODY only for intent detection (subject may contain old thread text like "Re: Appointment")
        body_lower = body.lower().strip()

        # Get conversation state
        conversation_state = await _get_email_conversation_state(from_email, user_id, db)

        # ✅ IMPROVED: Check booking intent from BODY only (not subject)
        booking_keywords = ["book", "book an appointment", "schedule", "reserve", "make an appointment"]
        is_booking_request = any(word in body_lower for word in booking_keywords)

        # Reschedule/Cancel intent detection
        reschedule_keywords = ["reschedule", "change appointment", "move appointment", "change my appointment", "postpone"]
        cancel_keywords = ["cancel appointment", "cancel my appointment", "cancel booking", "cancel my booking"]
        is_reschedule_request = any(phrase in body_lower for phrase in reschedule_keywords)
        is_cancel_request = any(phrase in body_lower for phrase in cancel_keywords)

        # Check if this is a different topic (pricing, support, general questions, etc.)
        # Note: "cancel" removed from here — handled by cancel_keywords above
        topic_change_keywords = [
            "price", "pricing", "cost", "pay", "payment", "fee", "charge",
            "support", "help", "issue", "problem", "error", "trouble",
            "integrate", "api", "documentation", "docs", "guide",
            "refund", "question", "info", "information",
            "service", "offering", "offer", "package", "plan", "feature",
            "what do you"
        ]
        is_topic_change = any(word in body_lower for word in topic_change_keywords)

        # Also check if message is too short to be a booking step response
        is_short_response = len(body.strip()) < 5

        # PRIORITY 1: Handle Active Appointment Booking (but allow topic changes)
        if conversation_state.get("booking_in_progress") and not is_topic_change and not is_short_response:
            logger.info("📅 Continuing appointment booking via email...")

            booking_result = await _process_email_appointment_booking(
                body, conversation_state, user_id, from_email, db
            )

            ai_message = booking_result["response"]
            source = "appointment_booking"

        # PRIORITY 1.5a: Handle Active Reschedule Flow
        elif conversation_state.get("reschedule_in_progress"):
            logger.info("📅 Continuing reschedule via email...")
            reschedule_result = await _process_email_appointment_reschedule(
                body, conversation_state, user_id, from_email, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        # PRIORITY 1.5b: Handle Active Cancel Flow
        elif conversation_state.get("cancel_in_progress"):
            logger.info("📅 Continuing cancel via email...")
            cancel_result = await _process_email_appointment_cancel(
                body, conversation_state, user_id, from_email, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # PRIORITY 1.6: New Reschedule Request
        elif is_reschedule_request:
            logger.info("📅 Starting reschedule via email...")
            await _update_email_conversation_state(
                from_email, user_id,
                {"reschedule_in_progress": True, "reschedule_data": {}}, db
            )
            reschedule_result = await _process_email_appointment_reschedule(
                body, {"reschedule_data": {}}, user_id, from_email, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        # PRIORITY 1.7: New Cancel Request
        elif is_cancel_request:
            logger.info("📅 Starting cancel via email...")
            await _update_email_conversation_state(
                from_email, user_id,
                {"cancel_in_progress": True, "cancel_data": {}}, db
            )
            cancel_result = await _process_email_appointment_cancel(
                body, {"cancel_data": {}}, user_id, from_email, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # PRIORITY 2: Check if User Wants to Book (new booking request)
        elif is_booking_request and not is_topic_change:
            logger.info("📅 Starting new appointment booking via email...")

            await _update_email_conversation_state(
                from_email, user_id,
                {"booking_in_progress": True, "current_step": "ai_collecting", "collected_data": {}},
                db
            )

            booking_result = await _process_email_appointment_booking(
                body,
                {"current_step": "ai_collecting", "collected_data": {}},
                user_id,
                from_email,
                db
            )

            ai_message = booking_result["response"]
            source = "appointment_booking"

        # PRIORITY 3: Handle topic change - reset booking and continue to OpenAI
        elif is_topic_change and conversation_state.get("booking_in_progress"):
            logger.info("🔄 Topic change detected, resetting booking state...")

            await _update_email_conversation_state(
                from_email, user_id,
                {"booking_in_progress": False, "current_step": None, "collected_data": {}},
                db
            )

            # Will fall through to Campaign/OpenAI handling below
        
        # PRIORITY 4: Check Campaign Builder (if not already handled)
        if not ai_message:
            campaign_match = await _match_email_campaign_workflow(
                user_input=full_message,
                user_id=user_id,
                db=db
            )
            
            if campaign_match and campaign_match.get("found"):
                ai_message = campaign_match["response"]
                source = "campaign"
                logger.info(f"✅ Using Campaign: {campaign_match['workflow_name']}")
            
            # PRIORITY 5: Use OpenAI
            else:
                logger.info(f"🤖 Using OpenAI for email response")
                
                try:
                    # Get email conversation history
                    history_cursor = db.email_logs.find({
                        "user_id": user_id,
                        "$or": [
                            {"to_email": from_email},
                            {"from_email": from_email}
                        ]
                    }).sort("created_at", -1).limit(10)
                    
                    history = await history_cursor.to_list(length=10)
                    history.reverse()
                    
                    conversation_context = []
                    for msg in history:
                        role = "user" if msg.get("direction") == "inbound" else "assistant"
                        content = msg.get("content", "") or msg.get("text_content", "")
                        if content:
                            conversation_context.append({
                                "role": role,
                                "content": content
                            })
                    
                    conversation_context.append({
                        "role": "user",
                        "content": full_message
                    })
                    
                    # Build dynamic system prompt from business profile
                    from app.api.v1.business_profile import get_business_context_for_ai
                    business_context = await get_business_context_for_ai(user_id, db)

                    webhook_base_prompt = """LANGUAGE RULE (HIGHEST PRIORITY — OVERRIDES EVERYTHING BELOW):
You MUST detect the language of the customer's email and respond ENTIRELY in that SAME language.
If the customer writes in French, you respond in French. If Urdu, respond in Urdu. If Hindi, respond in Hindi.
If Spanish, respond in Spanish. If German, respond in German. If English, respond in English.
NEVER respond in a different language than the customer used. This rule overrides all other instructions.

You are a helpful AI assistant responding to emails.
You help answer customer questions about services, pricing, appointments, and general inquiries.
Be professional, friendly, and thorough in your email responses.
Format your responses appropriately for email communication.
Keep responses under 300 words."""

                    if business_context:
                        webhook_system_prompt = f"{webhook_base_prompt}\n\nHere is the business information you should use:\n\n{business_context}"
                    else:
                        webhook_system_prompt = webhook_base_prompt

                    ai_response = await openai_service.generate_chat_response(
                        messages=conversation_context,
                        system_prompt=webhook_system_prompt,
                        max_tokens=500
                    )
                    
                    if ai_response.get("success"):
                        ai_message = ai_response.get("response", "Thank you for your email. Our team will get back to you shortly!")
                        source = "openai"
                    else:
                        ai_message = "Thank you for your email. Our team will review your message and respond shortly!"
                        source = "fallback"
                        
                except Exception as e:
                    logger.error(f"OpenAI error: {e}")
                    ai_message = "Thank you for your email. Our team will review your message and respond shortly!"
                    source = "fallback"
        
        # ============================================
        # STEP 3: Send AI Response Email
        # ============================================
        if ai_message:
            logger.info(f"📤 Sending AI response via email ({source})")

            # Generate reply subject
            reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

            # Resolve user-specific SMTP credentials
            smtp_config = resolve_email_credentials(primary_user)
            reply_from_email = smtp_config.get("from_email") or to_email
            reply_from_name = smtp_config.get("from_name") or "CallCenter SaaS"

            logger.info(f"📧 Replying from: {reply_from_name} <{reply_from_email}>")

            html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                            .container {{ max-width: 600px; padding: 20px; }}
                            .content {{ padding: 0; text-align: left; }}
                            .footer {{ text-align: left; padding-top: 20px; color: #999; font-size: 12px; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="content">
                                {ai_message.replace(chr(10), '<br>')}
                            </div>
                            <div class="footer">
                                <p>This is an automated response from {reply_from_name}.</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """

            # Send email response using user-specific SMTP if available
            try:
                has_custom_smtp = smtp_config.get("smtp_host") and smtp_config.get("smtp_password")

                if has_custom_smtp:
                    # Use user's own SMTP credentials
                    await email_service.send_email_with_credentials(
                        to_email=from_email,
                        subject=reply_subject,
                        html_content=html_content,
                        smtp_config=smtp_config,
                        text_content=ai_message
                    )
                else:
                    # Fallback to global SMTP
                    await email_automation_service.send_email(
                        to_email=from_email,
                        subject=reply_subject,
                        html_content=html_content,
                        user_id=user_id,
                        text_content=ai_message
                    )

                # Log the outbound response
                response_log_data = {
                    "user_id": user_id,
                    "to_email": from_email,
                    "from_email": reply_from_email,
                    "subject": reply_subject,
                    "content": ai_message,
                    "text_content": ai_message,
                    "status": "sent",
                    "direction": "outbound",
                    "ai_source": source,
                    "is_auto_reply": True,
                    "original_email_subject": subject,
                    "created_at": datetime.utcnow(),
                    "sent_at": datetime.utcnow(),
                    "opened_count": 0,
                    "clicked_count": 0,
                    "clicked_links": []
                }

                await db.email_logs.insert_one(response_log_data)

                logger.info(f"✅ AI response sent to {from_email} from {reply_from_email}")

            except Exception as e:
                logger.error(f"❌ Failed to send AI response: {e}", exc_info=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "from": from_email,
                "ai_response_sent": bool(ai_message),
                "source": source
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Email webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,  # Return 200 to prevent retries
            content={"status": "error", "message": str(e)}
        )


# ============================================
# WEBHOOK STATUS ENDPOINT
# ============================================
@router.get("/webhook/status")
async def email_webhook_status():
    """Check email webhook status"""
    return {
        "status": "active",
        "webhook_url": "/api/v1/email-webhook/webhook/inbound",
        "supported_providers": ["SendGrid", "Mailgun", "Custom"],
        "features": [
            "AI auto-response",
            "Campaign Builder integration",
            "Appointment booking",
            "Conversation history",
            "Topic change detection"
        ]
    }


# ============================================
# MANUAL TEST ENDPOINT (for development)
# ============================================
@router.post("/webhook/test")
async def test_email_webhook(
    request: Request,
    db = Depends(get_database)
):
    """
    Test endpoint to simulate incoming email
    Send JSON body with: from, to, subject, text
    """
    try:
        data = await request.json()
        
        # Create a mock form-like object
        class MockForm:
            def __init__(self, data):
                self._data = data
            
            def get(self, key, default=""):
                return self._data.get(key, default)
        
        # Create mock request with form method
        class MockRequest:
            def __init__(self, form_data):
                self._form_data = form_data
            
            async def form(self):
                return MockForm(self._form_data)
        
        # Map JSON keys to form keys
        form_data = {
            "from": data.get("from", data.get("from_email", "")),
            "to": data.get("to", data.get("to_email", "")),
            "subject": data.get("subject", ""),
            "text": data.get("text", data.get("body", "")),
            "html": data.get("html", "")
        }
        
        mock_request = MockRequest(form_data)
        
        # Call the actual webhook
        return await email_inbound_webhook(mock_request, db)
        
    except Exception as e:
        logger.error(f"Test webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================
# RESET CONVERSATION STATE ENDPOINT
# ============================================
@router.post("/reset-state/{email_address}")
async def reset_email_conversation_state(
    email_address: str,
    db = Depends(get_database)
):
    """
    Reset conversation state for an email address
    Useful for testing or when user wants to start fresh
    """
    try:
        result = await db.email_conversation_states.delete_many({
            "email_address": email_address
        })
        
        return {
            "status": "success",
            "email_address": email_address,
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Reset state error: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
