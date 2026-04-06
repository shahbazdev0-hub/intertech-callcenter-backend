

# backend/app/api/v1/sms.py - ✅ COMPLETE FILE WITH HISTORY CLEARING FOR CUSTOM SCRIPTS

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import Response
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import os

from app.database import get_database
from app.api.deps import get_current_user
from app.schemas.sms import SMSSendRequest, SMSBulkRequest, SMSResponse, SMSStatsResponse
from app.services.sms import sms_service
from app.services.openai import openai_service
from bson import ObjectId

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# HELPER: Get conversation state
# ============================================
async def _get_conversation_state(phone_number: str, user_id: str, db) -> Dict[str, Any]:
    """Get conversation state for appointment booking"""
    state = await db.conversation_states.find_one({
        "phone_number": phone_number,
        "user_id": user_id
    })
    
    if not state:
        return {
            "booking_in_progress": False,
            "current_step": None,
            "collected_data": {}
        }
    
    return state


# ============================================
# HELPER: Update conversation state
# ============================================
async def _update_conversation_state(
    phone_number: str, 
    user_id: str, 
    updates: Dict[str, Any], 
    db
):
    """Update conversation state"""
    updates["updated_at"] = datetime.utcnow()
    
    await db.conversation_states.update_one(
        {"phone_number": phone_number, "user_id": user_id},
        {"$set": updates},
        upsert=True
    )


# ============================================
# HELPER: Process appointment booking
# ============================================
async def _process_appointment_booking(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    phone_number: str,
    db
) -> Dict[str, Any]:
    """Process appointment booking using AI-powered entity extraction"""
    from app.services.appointment import appointment_service
    from app.services.booking_extractor import extract_booking_fields, validate_and_parse_datetime
    from app.api.v1.business_profile import get_business_context_for_ai

    collected_data = conversation_state.get("collected_data", {})
    print(f"[SMS-BOOKING] AI extraction - collected so far: {collected_data}")

    # 1. Load conversation history
    history_cursor = db.sms_logs.find({
        "user_id": user_id,
        "$or": [
            {"to_number": phone_number},
            {"from_number": phone_number}
        ]
    }).sort("created_at", -1).limit(10)
    history = await history_cursor.to_list(length=10)
    history.reverse()

    conversation_history = []
    for msg in history:
        role = "user" if msg.get("direction") == "inbound" else "assistant"
        conversation_history.append({"role": role, "content": msg.get("message", "")})

    # 2. Get business context
    business_context = await get_business_context_for_ai(user_id, db)

    # 3. AI extraction
    extraction = await extract_booking_fields(
        current_message=user_message,
        conversation_history=conversation_history,
        already_collected=collected_data,
        business_context=business_context,
        channel="sms"
    )

    # 4. Handle non-booking messages (user asked a question mid-booking)
    if not extraction.get("is_booking_response", True):
        return {"response": extraction.get("response", "How can I help? Let me know when you're ready to continue booking.")}

    # 5. Merge extracted data
    extracted = extraction.get("extracted", {})
    for field in ["name", "email", "service"]:
        if extracted.get(field):
            collected_data[field] = extracted[field]
    if extracted.get("datetime_text"):
        collected_data["datetime_text"] = extracted["datetime_text"]

    print(f"[SMS-BOOKING] After merge: {collected_data}")

    # 6. If all fields present, validate datetime and create appointment
    if extraction.get("all_complete") or all(collected_data.get(f) for f in ["name", "email", "service", "datetime_text"]):
        dt_result = await validate_and_parse_datetime(
            collected_data.get("datetime_text", ""),
            business_context
        )

        if not dt_result["success"]:
            if dt_result.get("error") == "weekend":
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data}, db
                )
                return {"response": f"That falls on a weekend — we're available Monday to Friday. How about {dt_result['suggestion']} instead?"}
            elif dt_result.get("error") == "outside_hours":
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data}, db
                )
                return {"response": f"That's outside our business hours (9 AM - 5 PM). Would {dt_result['suggestion']} work for you?"}
            else:
                collected_data.pop("datetime_text", None)
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data}, db
                )
                return {"response": "I couldn't determine the date from that. Could you say something like 'tomorrow at 2pm' or 'next Monday at 10am'?"}

        parsed_date = dt_result["parsed_date"]

        try:
            appointment_result = await appointment_service.create_appointment(
                user_id=user_id,
                customer_name=collected_data["name"],
                customer_email=collected_data["email"],
                customer_phone=phone_number,
                appointment_date=parsed_date,
                appointment_time=parsed_date.strftime("%H:%M"),
                service_type=collected_data.get("service", "Consultation"),
                notes="Booked via SMS"
            )

            if appointment_result.get("success"):
                await _update_conversation_state(
                    phone_number, user_id,
                    {"booking_in_progress": False, "current_step": None, "collected_data": {}},
                    db
                )
                formatted_date = parsed_date.strftime("%A, %B %d at %I:%M %p")
                return {"response": f"Your appointment for {collected_data.get('service', 'consultation')} is confirmed for {formatted_date}. A confirmation email has been sent to {collected_data['email']}!"}
            elif appointment_result.get("error") == "time_conflict":
                conflict_time = appointment_result.get("conflict_time", "that time")
                collected_data.pop("datetime_text", None)
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data}, db
                )
                return {"response": f"Sorry, the {conflict_time} slot is already booked. Could you pick a different time? Our hours are Monday-Friday, 9 AM to 5 PM."}
            else:
                return {"response": "I'm having trouble booking that time. Please try a different time or contact us directly."}

        except Exception as e:
            logger.error(f"Appointment booking error: {e}")
            return {"response": "There was an error booking your appointment. Please try again or contact us directly."}

    # 7. Fields still missing — save progress and ask
    await _update_conversation_state(
        phone_number, user_id,
        {"current_step": "ai_collecting", "collected_data": collected_data},
        db
    )

    return {"response": extraction.get("response", "Could you provide the remaining booking details?")}


# ============================================
# HELPER: Process appointment reschedule via SMS
# ============================================
async def _process_appointment_reschedule(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    phone_number: str,
    db
) -> Dict[str, Any]:
    """Process appointment reschedule using AI extraction"""
    from app.services.appointment import appointment_service
    from app.services.booking_extractor import extract_reschedule_fields, validate_and_parse_datetime

    reschedule_data = conversation_state.get("reschedule_data", {})
    appointment_id = reschedule_data.get("appointment_id")

    # Find customer's active appointment if not already tracked
    if not appointment_id:
        appointment = await db.appointments.find_one({
            "user_id": user_id,
            "customer_phone": phone_number,
            "status": {"$in": ["scheduled", "confirmed"]}
        }, sort=[("appointment_date", -1)])

        if not appointment:
            await _update_conversation_state(
                phone_number, user_id,
                {"reschedule_in_progress": False, "reschedule_data": {}}, db
            )
            return {"response": "I couldn't find an active appointment for your number. Would you like to book a new one?"}

        appointment_id = str(appointment["_id"])
        reschedule_data["appointment_id"] = appointment_id
        reschedule_data["appointment"] = {
            "service_type": appointment.get("service_type", "appointment"),
            "appointment_date": appointment.get("appointment_date"),
            "customer_name": appointment.get("customer_name", "")
        }

    existing_appointment = reschedule_data.get("appointment", {})

    # Load conversation history
    history_cursor = db.sms_logs.find({
        "user_id": user_id,
        "$or": [{"to_number": phone_number}, {"from_number": phone_number}]
    }).sort("created_at", -1).limit(6)
    history = await history_cursor.to_list(length=6)
    history.reverse()
    conversation_history = [
        {"role": "user" if m.get("direction") == "inbound" else "assistant", "content": m.get("message", "")}
        for m in history
    ]

    # AI extraction
    extraction = await extract_reschedule_fields(
        current_message=user_message,
        conversation_history=conversation_history,
        existing_appointment=existing_appointment,
        channel="sms"
    )

    print(f"[SMS-RESCHEDULE] Extraction: {extraction}")

    # Handle cancel request mid-reschedule
    if extraction.get("is_cancel_request"):
        await _update_conversation_state(
            phone_number, user_id,
            {"reschedule_in_progress": False, "reschedule_data": {},
             "cancel_in_progress": True, "cancel_data": {"appointment_id": appointment_id, "appointment": existing_appointment}},
            db
        )
        appt_date = existing_appointment.get("appointment_date", "")
        if isinstance(appt_date, datetime):
            appt_date = appt_date.strftime("%A, %B %d at %I:%M %p")
        return {"response": f"Would you like to cancel your {existing_appointment.get('service_type', 'appointment')} on {appt_date}? Reply YES to confirm cancellation."}

    # If new datetime provided, validate and update
    if extraction.get("new_datetime_text"):
        from app.api.v1.business_profile import get_business_context_for_ai
        business_context = await get_business_context_for_ai(user_id, db)
        dt_result = await validate_and_parse_datetime(extraction["new_datetime_text"], business_context)

        if not dt_result["success"]:
            if dt_result.get("error") == "weekend":
                return {"response": f"That falls on a weekend. How about {dt_result['suggestion']} instead?"}
            elif dt_result.get("error") == "outside_hours":
                return {"response": f"That's outside business hours (9 AM - 5 PM). Would {dt_result['suggestion']} work?"}
            else:
                return {"response": "I couldn't understand that date. Could you say something like 'next Tuesday at 2pm'?"}

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
            return {"response": f"Sorry, that time slot is already booked. Could you pick a different time?"}

        # Update appointment
        try:
            result = await appointment_service.update_appointment(
                appointment_id=appointment_id,
                user_id=user_id,
                update_data={
                    "appointment_date": parsed_date,
                    "appointment_time": parsed_date.strftime("%H:%M"),
                    "status": "scheduled"
                }
            )
            if result:
                await _update_conversation_state(
                    phone_number, user_id,
                    {"reschedule_in_progress": False, "reschedule_data": {}}, db
                )
                formatted_date = parsed_date.strftime("%A, %B %d at %I:%M %p")
                return {"response": f"Your {existing_appointment.get('service_type', 'appointment')} has been rescheduled to {formatted_date}. See you then!"}
            else:
                return {"response": "I had trouble updating your appointment. Please try again or contact us directly."}
        except Exception as e:
            logger.error(f"Reschedule error: {e}")
            return {"response": "There was an error rescheduling. Please try again or contact us directly."}

    # No datetime yet — save state and ask
    await _update_conversation_state(
        phone_number, user_id,
        {"reschedule_in_progress": True, "reschedule_data": reschedule_data}, db
    )
    return {"response": extraction.get("response", "When would you like to reschedule your appointment to?")}


# ============================================
# HELPER: Process appointment cancellation via SMS
# ============================================
async def _process_appointment_cancel(
    user_message: str,
    conversation_state: Dict[str, Any],
    user_id: str,
    phone_number: str,
    db
) -> Dict[str, Any]:
    """Process appointment cancellation with confirmation"""
    from app.services.appointment import appointment_service

    cancel_data = conversation_state.get("cancel_data", {})
    appointment_id = cancel_data.get("appointment_id")
    awaiting_confirmation = cancel_data.get("awaiting_confirmation", False)

    # If awaiting confirmation, check for yes/no
    if awaiting_confirmation and appointment_id:
        lower = user_message.lower().strip()
        if lower in ["yes", "yeah", "yep", "confirm", "ok", "okay", "sure", "y"]:
            try:
                result = await appointment_service.cancel_appointment(
                    appointment_id=appointment_id,
                    user_id=user_id,
                    reason="Cancelled by customer via SMS"
                )
                await _update_conversation_state(
                    phone_number, user_id,
                    {"cancel_in_progress": False, "cancel_data": {}}, db
                )
                if result:
                    return {"response": "Your appointment has been cancelled. If you'd like to book a new one, just let me know!"}
                else:
                    return {"response": "I had trouble cancelling. Please try again or contact us directly."}
            except Exception as e:
                logger.error(f"Cancel error: {e}")
                return {"response": "There was an error. Please try again or contact us directly."}
        elif lower in ["no", "nah", "nope", "n", "nevermind", "never mind", "keep", "keep it"]:
            await _update_conversation_state(
                phone_number, user_id,
                {"cancel_in_progress": False, "cancel_data": {}}, db
            )
            return {"response": "No worries! Your appointment is still confirmed. Is there anything else I can help with?"}
        else:
            return {"response": "Please reply YES to confirm cancellation, or NO to keep your appointment."}

    # First time: find appointment and ask for confirmation
    if not appointment_id:
        appointment = await db.appointments.find_one({
            "user_id": user_id,
            "customer_phone": phone_number,
            "status": {"$in": ["scheduled", "confirmed"]}
        }, sort=[("appointment_date", -1)])

        if not appointment:
            await _update_conversation_state(
                phone_number, user_id,
                {"cancel_in_progress": False, "cancel_data": {}}, db
            )
            return {"response": "I couldn't find an active appointment for your number. Would you like to book a new one?"}

        appointment_id = str(appointment["_id"])
        appt_date = appointment.get("appointment_date", "")
        if isinstance(appt_date, datetime):
            appt_date = appt_date.strftime("%A, %B %d at %I:%M %p")
        service = appointment.get("service_type", "appointment")

        await _update_conversation_state(
            phone_number, user_id,
            {"cancel_in_progress": True, "cancel_data": {
                "appointment_id": appointment_id,
                "awaiting_confirmation": True,
                "appointment": {"service_type": service, "appointment_date": appt_date}
            }}, db
        )
        return {"response": f"Are you sure you want to cancel your {service} appointment on {appt_date}? Reply YES to confirm or NO to keep it."}

    # Shouldn't reach here, but handle gracefully
    return {"response": "Please reply YES to confirm cancellation, or NO to keep your appointment."}


# ============================================
# HELPER: Match Campaign Builder workflow
# ============================================
async def _match_campaign_workflow(user_input: str, user_id: str, db) -> Optional[Dict]:
    """Match user input against Campaign Builder workflows"""
    try:
        workflows_cursor = db.flows.find({
            "user_id": user_id,
            "active": True
        })
        workflows = await workflows_cursor.to_list(length=None)
        
        if not workflows:
            return None
        
        user_input_lower = user_input.lower().strip()
        
        for workflow in workflows:
            workflow_name = workflow.get("name", "Unnamed")
            nodes = workflow.get("nodes", [])
            
            for node in nodes:
                node_data = node.get("data", {})
                node_message = node_data.get("message", "")
                node_transitions = node_data.get("transitions", [])
                
                if not node_transitions or not node_message:
                    continue
                
                for keyword in node_transitions:
                    if not keyword:
                        continue
                    
                    keyword_clean = str(keyword).strip().lower()
                    
                    if keyword_clean and keyword_clean in user_input_lower:
                        logger.info(f"✅ Campaign match: '{keyword_clean}'")
                        
                        return {
                            "found": True,
                            "response": node_message,
                            "workflow_id": str(workflow["_id"]),
                            "workflow_name": workflow_name,
                            "node_id": node.get("id"),
                            "matched_keyword": keyword_clean
                        }
        
        logger.info(f"❌ No campaign match")
        return None
        
    except Exception as e:
        logger.error(f"Campaign matching error: {e}")
        return None


# ============================================
# ✅ SMS WEBHOOK WITH IMPROVED CUSTOM SCRIPT HANDLING
# ============================================

@router.post("/webhook")
async def sms_webhook(
    request: Request,
    db = Depends(get_database)
):
    """
    ✅ Handle incoming SMS webhook with:
    - 🆕 Custom AI script from campaign (Priority 0)
    - Priority 1: Appointment booking flow
    - Priority 2: Campaign Builder responses
    - Priority 3: OpenAI fallback
    """
    try:
        # Extract Twilio form data
        form_data = await request.form()

        from_number = form_data.get("From")
        to_number = form_data.get("To")
        body = form_data.get("Body")
        message_sid = form_data.get("MessageSid")
        sms_status = form_data.get("SmsStatus")

        print(f"\n[SMS-WEBHOOK] From: {from_number} | To: {to_number} | Message: {body}")

        # Deduplication: skip if we already processed this MessageSid
        if message_sid:
            existing = await db.sms_messages.find_one({
                "twilio_sid": message_sid,
                "direction": "inbound"
            })
            if existing:
                print(f"[SMS-WEBHOOK] Skipping duplicate MessageSid: {message_sid}")
                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                    media_type="application/xml"
                )
        
        # ============================================
        # 🆕 STEP 0: Check if reply is from bulk campaign
        # ============================================
        
        campaign_id = None
        original_campaign = None
        custom_ai_script = None  # 🆕 STORE CUSTOM SCRIPT
        
        try:
            # Find if this customer received a message from a campaign
            original_sms = await db.sms_messages.find_one({
                "to_number": from_number,
                "direction": "outbound",
                "campaign_id": {"$exists": True, "$ne": None}
            }, sort=[("created_at", -1)])  # Get most recent
            
            if original_sms:
                campaign_id = original_sms.get("campaign_id")
                
                # Get campaign details
                original_campaign = await db.sms_campaigns.find_one({
                    "campaign_id": campaign_id
                })
                
                if original_campaign:
                    logger.info(f"🎯 Reply is from bulk campaign: {campaign_id}")
                    
                    # 🆕 GET CUSTOM AI SCRIPT FROM CAMPAIGN
                    custom_ai_script = original_campaign.get("custom_ai_script")
                    
                    if custom_ai_script:
                        # ✅ ENSURE IT'S A VALID STRING
                        custom_ai_script = str(custom_ai_script).strip()
                        
                        if len(custom_ai_script) >= 10:
                            logger.info(f"📝 Custom AI script found: {len(custom_ai_script)} characters")
                            logger.info(f"   First 100 chars: {custom_ai_script[:100]}...")
                            
                            # ✅ 🆕 CLEAR OLD CONVERSATION HISTORY FOR FRESH START
                            logger.info(f"🧹 Clearing old conversation history for fresh start with custom script")
                            
                            delete_result = await db.sms_logs.delete_many({
                                "$or": [
                                    {"to_number": from_number},
                                    {"from_number": from_number}
                                ]
                            })
                            
                            logger.info(f"   ✅ Deleted {delete_result.deleted_count} old messages from history")
                        else:
                            logger.warning(f"⚠️ Custom AI script too short ({len(custom_ai_script)} chars), ignoring")
                            custom_ai_script = None
                    else:
                        logger.info(f"ℹ️ No custom AI script for this campaign")
                    
                    # Update campaign recipient status
                    await db.sms_campaigns.update_one(
                        {
                            "_id": original_campaign["_id"],
                            "recipients.phone_number": from_number
                        },
                        {
                            "$set": {
                                "recipients.$.status": "replied"
                            }
                        }
                    )
        except Exception as e:
            logger.warning(f"Error checking campaign: {e}")
        
        # ============================================
        # STEP 1: Find users and store incoming SMS
        # ============================================
        
        users = await db.users.find({"role": {"$ne": "admin"}}).to_list(length=100)
        
        if not users:
            logger.warning("⚠️ No users found")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                media_type="application/xml"
            )
        
        # Store incoming SMS for ALL users
        for user in users:
            user_id = str(user["_id"])
            
            sms_data = {
                "user_id": user_id,
                "to_number": to_number,
                "from_number": from_number,
                "message": body,
                "status": "received",
                "direction": "inbound",
                "twilio_sid": message_sid,
                "twilio_status": sms_status,
                "campaign_id": campaign_id,
                "created_at": datetime.utcnow()
            }
            
            await db.sms_messages.insert_one(sms_data.copy())
            
            sms_log_data = sms_data.copy()
            sms_log_data["is_reply"] = True if campaign_id else False
            sms_log_data["has_replies"] = False
            sms_log_data["reply_count"] = 0
            
            await db.sms_logs.insert_one(sms_log_data)
        
        logger.info(f"✅ Incoming message stored for {len(users)} users")
        
        # ============================================
        # STEP 2: Generate AI Response
        # ============================================
        
        ai_message = None
        source = "none"

        # Match the correct user who owns the Twilio number being texted
        matched_user = None
        env_phone = os.getenv("TWILIO_PHONE_NUMBER", "")
        is_shared_number = (to_number == env_phone)

        print(f"[SMS-WEBHOOK] to_number={to_number}, env_phone={env_phone}, is_shared={is_shared_number}")

        # Strategy 1: Match by user-specific Twilio number (NOT the shared env number)
        if not is_shared_number:
            for u in users:
                user_twilio = u.get("twilio_phone_number")
                twilio_config = u.get("integration_config", {}).get("twilio", {})
                config_phone = twilio_config.get("phone_number")
                if (user_twilio == to_number) or (config_phone == to_number):
                    matched_user = u
                    print(f"[SMS-WEBHOOK] Strategy 1: Matched by user-specific number: {u.get('email')}")
                    break

        # Strategy 2: For shared env number — find user with business profile that has services
        if not matched_user and is_shared_number:
            profiles = await db.business_profiles.find({
                "services": {"$exists": True, "$ne": []}
            }).to_list(length=10)
            if profiles:
                profile_user_ids = [p["user_id"] for p in profiles]
                for u in users:
                    if str(u["_id"]) in profile_user_ids:
                        matched_user = u
                        print(f"[SMS-WEBHOOK] Strategy 2: Matched by business profile: {u.get('email')}")
                        break

        # Strategy 3: Find admin/superadmin
        if not matched_user:
            owner = await db.users.find_one({
                "is_active": True,
                "role": {"$in": ["superadmin", "admin"]}
            })
            if owner:
                matched_user = owner
                print(f"[SMS-WEBHOOK] Strategy 3: Matched admin: {owner.get('email')}")

        # Strategy 4: Previous SMS conversation
        if not matched_user:
            prev_sms = await db.sms_logs.find_one({
                "to_number": from_number,
                "direction": "outbound",
                "user_id": {"$exists": True}
            }, sort=[("created_at", -1)])
            if prev_sms:
                from bson import ObjectId
                prev_user = await db.users.find_one({"_id": ObjectId(prev_sms["user_id"])})
                if prev_user:
                    matched_user = prev_user
                    print(f"[SMS-WEBHOOK] Strategy 4: Matched by previous conversation: {prev_user.get('email')}")

        # Fallback: first user
        if not matched_user:
            matched_user = users[0]
            print(f"[SMS-WEBHOOK] Fallback: Using first user: {matched_user.get('email')}")

        user_id = str(matched_user["_id"])
        print(f"[SMS-WEBHOOK] Matched user: {user_id} ({matched_user.get('email', 'unknown')})")
        
        # Get conversation state
        conversation_state = await _get_conversation_state(from_number, user_id, db)
        
        # ============================================
        # 🆕 PRIORITY 0: Use Custom AI Script (if from campaign and not booking)
        # ============================================
        print(f"[SMS-WEBHOOK] custom_ai_script={bool(custom_ai_script)}, booking={conversation_state.get('booking_in_progress')}, reschedule={conversation_state.get('reschedule_in_progress')}, cancel={conversation_state.get('cancel_in_progress')}")
        if custom_ai_script and not conversation_state.get("booking_in_progress") and not conversation_state.get("reschedule_in_progress") and not conversation_state.get("cancel_in_progress"):
            logger.info(f"\n{'='*80}")
            logger.info(f"🎯 PRIORITY 0: USING CUSTOM CAMPAIGN AI SCRIPT")
            logger.info(f"{'='*80}")
            logger.info(f"   Script length: {len(custom_ai_script)} characters")
            logger.info(f"   Customer message: '{body}'")
            logger.info(f"{'='*80}\n")

            body_lower = body.lower()

            # Check if appointment booking keywords
            if any(word in body_lower for word in ["book", "appointment", "schedule", "reserve"]):
                logger.info("📅 Switching to appointment booking flow with AI extraction...")

                await _update_conversation_state(
                    from_number, user_id,
                    {"booking_in_progress": True, "current_step": "ai_collecting", "collected_data": {}},
                    db
                )

                booking_result = await _process_appointment_booking(
                    body,
                    {"current_step": "ai_collecting", "collected_data": {}},
                    user_id, from_number, db
                )
                ai_message = booking_result["response"]
                source = "appointment_booking"

            # Check reschedule keywords
            elif any(phrase in body_lower for phrase in ["reschedule", "change appointment", "move appointment", "change my appointment", "postpone"]):
                logger.info("📅 Switching to reschedule flow...")
                await _update_conversation_state(
                    from_number, user_id,
                    {"reschedule_in_progress": True, "reschedule_data": {}}, db
                )
                reschedule_result = await _process_appointment_reschedule(
                    body, {"reschedule_data": {}}, user_id, from_number, db
                )
                ai_message = reschedule_result["response"]
                source = "appointment_reschedule"

            # Check cancel keywords
            elif any(phrase in body_lower for phrase in ["cancel appointment", "cancel my appointment", "cancel booking", "cancel my booking"]):
                logger.info("📅 Switching to cancel flow...")
                await _update_conversation_state(
                    from_number, user_id,
                    {"cancel_in_progress": True, "cancel_data": {}}, db
                )
                cancel_result = await _process_appointment_cancel(
                    body, {"cancel_data": {}}, user_id, from_number, db
                )
                ai_message = cancel_result["response"]
                source = "appointment_cancel"

            else:
                # ✅ Use custom script with OpenAI - NO HISTORY
                try:
                    # ✅ 🆕 DON'T USE HISTORY - START FRESH WITH CUSTOM SCRIPT
                    conversation_context = []

                    # Only add current message
                    conversation_context.append({
                        "role": "user",
                        "content": body
                    })

                    # Enrich custom script with business profile data
                    from app.api.v1.business_profile import get_business_context_for_ai
                    business_context = await get_business_context_for_ai(user_id, db)

                    # Language instruction at TOP for highest priority
                    lang_instruction = """LANGUAGE RULE (HIGHEST PRIORITY — OVERRIDES EVERYTHING BELOW):
You MUST detect the language of the customer's message and respond ENTIRELY in that SAME language.
If the customer writes in French, you respond in French. If Urdu, respond in Urdu. If Hindi, respond in Hindi.
If Spanish, respond in Spanish. If German, respond in German. If English, respond in English.
NEVER respond in a different language than the customer used. This rule overrides all other instructions.\n\n"""

                    enriched_script = lang_instruction + custom_ai_script
                    if business_context:
                        enriched_script += f"\n\nHere is the business information you should use:\n\n{business_context}"

                    logger.info(f"🤖 Calling OpenAI with custom script + business profile...")
                    logger.info(f"   System prompt length: {len(enriched_script)} chars")
                    logger.info(f"   System prompt preview: {enriched_script[:200]}...")
                    logger.info(f"   🆕 Using FRESH conversation (no history)")
                    logger.info(f"   User message: {body}")

                    # 🆕 USE CUSTOM AI SCRIPT + BUSINESS PROFILE AS SYSTEM PROMPT
                    ai_response = await openai_service.generate_chat_response(
                        messages=conversation_context,
                        system_prompt=enriched_script,  # ✅ CUSTOM SCRIPT + BUSINESS DATA
                        max_tokens=150
                    )
                    
                    if ai_response.get("success"):
                        ai_message = ai_response.get("response", "Thank you for your message!")
                        source = "custom_ai_script"
                        
                        logger.info(f"✅ Custom AI script response generated successfully")
                        logger.info(f"   Response length: {len(ai_message)} chars")
                        logger.info(f"   Response preview: {ai_message[:100]}...")
                    else:
                        logger.error(f"❌ OpenAI failed: {ai_response.get('error')}")
                        ai_message = "Thank you for your message. Our team will get back to you shortly!"
                        source = "fallback"
                        
                except Exception as e:
                    logger.error(f"❌ Custom AI script error: {e}")
                    import traceback
                    traceback.print_exc()
                    ai_message = "Thank you for your message. Our team will get back to you shortly!"
                    source = "fallback"
        
        # ============================================
        # PRIORITY 1: Handle Active Appointment Booking
        # ============================================
        elif conversation_state.get("booking_in_progress"):
            print("[SMS-WEBHOOK] Priority 1: Continuing booking")

            booking_result = await _process_appointment_booking(
                body, conversation_state, user_id, from_number, db
            )

            ai_message = booking_result["response"]
            source = "appointment_booking"

        # ============================================
        # PRIORITY 1.5a: Handle Active Reschedule Flow
        # ============================================
        elif conversation_state.get("reschedule_in_progress"):
            print("[SMS-WEBHOOK] Priority 1.5a: Continuing reschedule")
            reschedule_result = await _process_appointment_reschedule(
                body, conversation_state, user_id, from_number, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        # ============================================
        # PRIORITY 1.5b: Handle Active Cancel Flow
        # ============================================
        elif conversation_state.get("cancel_in_progress"):
            print("[SMS-WEBHOOK] Priority 1.5b: Continuing cancel")
            cancel_result = await _process_appointment_cancel(
                body, conversation_state, user_id, from_number, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # ============================================
        # PRIORITY 1.6: New Reschedule/Cancel Request
        # ============================================
        elif any(phrase in body.lower() for phrase in ["reschedule", "change appointment", "move appointment", "change my appointment", "postpone"]):
            print("[SMS-WEBHOOK] Priority 1.6: New reschedule request")
            await _update_conversation_state(
                from_number, user_id,
                {"reschedule_in_progress": True, "reschedule_data": {}}, db
            )
            reschedule_result = await _process_appointment_reschedule(
                body, {"reschedule_data": {}}, user_id, from_number, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        elif any(phrase in body.lower() for phrase in ["cancel appointment", "cancel my appointment", "cancel booking", "cancel my booking"]):
            print("[SMS-WEBHOOK] Priority 1.6: New cancel request")
            await _update_conversation_state(
                from_number, user_id,
                {"cancel_in_progress": True, "cancel_data": {}}, db
            )
            cancel_result = await _process_appointment_cancel(
                body, {"cancel_data": {}}, user_id, from_number, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # ============================================
        # PRIORITY 2: Check if User Wants to Book
        # ============================================
        elif any(word in body.lower() for word in ["book", "appointment", "schedule", "reserve"]):
            print("[SMS-WEBHOOK] Priority 2: New booking request with AI extraction")

            await _update_conversation_state(
                from_number, user_id,
                {"booking_in_progress": True, "current_step": "ai_collecting", "collected_data": {}},
                db
            )

            # Run AI extraction on the triggering message itself
            booking_result = await _process_appointment_booking(
                body,
                {"current_step": "ai_collecting", "collected_data": {}},
                user_id, from_number, db
            )
            ai_message = booking_result["response"]
            source = "appointment_booking"
        
        # ============================================
        # PRIORITY 3: Check Campaign Builder
        # ============================================
        elif not ai_message:  # Only if not already handled by custom script
            print(f"[SMS-WEBHOOK] Priority 3: Checking campaign builder")
            campaign_match = await _match_campaign_workflow(
                user_input=body,
                user_id=user_id,
                db=db
            )
            
            if campaign_match and campaign_match.get("found"):
                ai_message = campaign_match["response"]
                source = "campaign"
                logger.info(f"✅ Using Campaign: {campaign_match['workflow_name']}")
            
            # ============================================
            # PRIORITY 4: Use OpenAI (default)
            # ============================================
            else:
                print(f"[SMS-WEBHOOK] Priority 4: Using OpenAI with business profile for user {user_id}")
                
                try:
                    history_cursor = db.sms_logs.find({
                        "user_id": user_id,
                        "$or": [
                            {"to_number": from_number},
                            {"from_number": from_number}
                        ]
                    }).sort("created_at", -1).limit(10)
                    
                    history = await history_cursor.to_list(length=10)
                    history.reverse()
                    
                    conversation_context = []
                    for msg in history:
                        role = "user" if msg["direction"] == "inbound" else "assistant"
                        conversation_context.append({
                            "role": role,
                            "content": msg["message"]
                        })
                    
                    conversation_context.append({
                        "role": "user",
                        "content": body
                    })
                    
                    # Build dynamic system prompt from business profile
                    from app.api.v1.business_profile import get_business_context_for_ai
                    business_context = await get_business_context_for_ai(user_id, db)

                    sms_base_prompt = """LANGUAGE RULE (HIGHEST PRIORITY — OVERRIDES EVERYTHING BELOW):
You MUST detect the language of the customer's message and respond ENTIRELY in that SAME language.
If the customer writes in French, you respond in French. If Urdu, respond in Urdu. If Hindi, respond in Hindi.
If Spanish, respond in Spanish. If German, respond in German. If English, respond in English.
NEVER respond in a different language than the customer used. This rule overrides all other instructions.

You are a helpful AI assistant responding to SMS messages.
You help answer customer questions about services, pricing, appointments, and general inquiries.
Be professional, friendly, and helpful. Keep responses under 150 words."""

                    if business_context:
                        sms_system_prompt = f"{sms_base_prompt}\n\nHere is the business information you should use:\n\n{business_context}"
                    else:
                        sms_system_prompt = sms_base_prompt

                    ai_response = await openai_service.generate_chat_response(
                        messages=conversation_context,
                        system_prompt=sms_system_prompt
                    )
                    
                    if ai_response.get("success"):
                        ai_message = ai_response.get("response", "I'm here to help! How can I assist you?")
                        source = "openai"
                    else:
                        ai_message = "Thank you for your message. Our team will get back to you shortly!"
                        source = "fallback"
                except Exception as e:
                    logger.error(f"OpenAI error: {e}")
                    ai_message = "Thank you for your message. Our team will get back to you shortly!"
                    source = "fallback"
        
        # ============================================
        # STEP 3: Send AI response via Twilio
        # ============================================
        
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📤 SENDING AI RESPONSE")
        logger.info(f"{'='*80}")
        logger.info(f"   Source: {source}")
        logger.info(f"   Response: {ai_message[:100]}...")
        logger.info(f"{'='*80}\n")
        
        try:
            send_result = await sms_service.send_sms(
                to_number=from_number,
                message=ai_message,
                from_number=twilio_phone,
                user_id=user_id,
                campaign_id=campaign_id
            )
            
            if send_result.get("success"):
                logger.info(f"✅ AI response sent to customer")
            else:
                logger.error(f"❌ Failed to send: {send_result.get('error')}")
        except Exception as e:
            logger.error(f"❌ Error sending SMS: {e}")
        
        # ============================================
        # STEP 4: Store AI response for ALL users
        # ============================================
        
        for user in users:
            uid = str(user["_id"])
            
            ai_sms_data = {
                "user_id": uid,
                "to_number": from_number,
                "from_number": twilio_phone,
                "message": ai_message,
                "status": "sent",
                "direction": "outbound",
                "campaign_id": campaign_id,
                "created_at": datetime.utcnow()
            }
            
            await db.sms_messages.insert_one(ai_sms_data.copy())
            
            ai_sms_log = ai_sms_data.copy()
            ai_sms_log["is_reply"] = True
            ai_sms_log["has_replies"] = False
            ai_sms_log["reply_count"] = 0
            
            await db.sms_logs.insert_one(ai_sms_log)
        
        logger.info(f"✅ Complete! Response sent via {source}")
        
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml",
            status_code=500
        )


# ============================================
# REST OF THE FILE REMAINS UNCHANGED
# ============================================

@router.post("/send", response_model=dict, status_code=status.HTTP_201_CREATED)
async def send_sms(
    request: SMSSendRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Send a single SMS"""
    try:
        user_id = str(current_user["_id"])

        # Resolve user's Twilio phone number if not explicitly provided
        from_number = request.from_number
        if not from_number:
            from app.utils.credential_resolver import resolve_twilio_credentials
            _, _, from_number = resolve_twilio_credentials(current_user)

        result = await sms_service.send_sms(
            to_number=request.to_number,
            message=request.message,
            from_number=from_number,
            user_id=user_id
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to send SMS")
            )
        
        return {
            "success": True,
            "message": "SMS sent successfully",
            "sms_id": result.get("sms_id"),
            "twilio_sid": result.get("twilio_sid")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/bulk", response_model=dict)
async def send_bulk_sms(
    request: SMSBulkRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Send bulk SMS"""
    try:
        user_id = str(current_user["_id"])
        
        result = await sms_service.send_bulk_sms(
            to_numbers=request.to_numbers,
            message=request.message,
            from_number=request.from_number,
            user_id=user_id,
            batch_size=request.batch_size
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending bulk SMS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=list)
async def list_sms(
    skip: int = 0,
    limit: int = 50,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """List SMS messages"""
    try:
        user_id = str(current_user["_id"])
        
        messages = await sms_service.get_sms_list(
            user_id=user_id,
            skip=skip,
            limit=limit,
            direction=direction,
            status=status
        )
        
        return messages
        
    except Exception as e:
        logger.error(f"Error listing SMS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats", response_model=SMSStatsResponse)
async def get_sms_stats(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get SMS statistics"""
    try:
        user_id = str(current_user["_id"])
        
        stats = await sms_service.get_sms_stats(user_id)
        
        return SMSStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error getting SMS stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{sms_id}")
async def delete_sms(
    sms_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete SMS message"""
    try:
        user_id = str(current_user["_id"])
        
        success = await sms_service.delete_sms(sms_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMS not found"
            )
        
        return {"success": True, "message": "SMS deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting SMS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )