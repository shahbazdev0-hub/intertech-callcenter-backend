
# backend/app/services/sms_chat.py - COMPLETE FILE WITH FIXED DATE PARSING

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import re

from app.api.deps import get_current_user, get_database
from app.services.openai import openai_service
from app.services.google_calendar import google_calendar_service
from app.services.email_automation import email_automation_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# CONVERSATION STATE MANAGEMENT
# ============================================

async def _get_conversation_state(
    phone_number: str,
    user_id: str,
    db
) -> Dict:
    """Get or create conversation state for SMS chat"""
    try:
        # Try to find existing conversation state
        state = await db.sms_conversation_states.find_one({
            "phone_number": phone_number,
            "user_id": user_id
        })
        
        if not state:
            # Create new conversation state
            state = {
                "phone_number": phone_number,
                "user_id": user_id,
                "booking_in_progress": False,
                "collected_data": {},
                "current_step": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.sms_conversation_states.insert_one(state)
            state["_id"] = result.inserted_id
        
        return state
        
    except Exception as e:
        logger.error(f"Error getting conversation state: {e}")
        return {
            "phone_number": phone_number,
            "user_id": user_id,
            "booking_in_progress": False,
            "collected_data": {},
            "current_step": None
        }


async def _update_conversation_state(
    phone_number: str,
    user_id: str,
    updates: Dict,
    db
):
    """Update conversation state"""
    try:
        await db.sms_conversation_states.update_one(
            {
                "phone_number": phone_number,
                "user_id": user_id
            },
            {
                "$set": {
                    **updates,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating conversation state: {e}")


async def _clear_conversation_state(
    phone_number: str,
    user_id: str,
    db
):
    """Clear conversation state after booking"""
    try:
        await db.sms_conversation_states.delete_one({
            "phone_number": phone_number,
            "user_id": user_id
        })
    except Exception as e:
        logger.error(f"Error clearing conversation state: {e}")


# ============================================
# DATA EXTRACTION - ✅ FIXED DATE PARSING
# ============================================

def _extract_email(text: str) -> Optional[str]:
    """Extract email from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0).lower() if match else None


def _extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text"""
    # Remove common words
    text = re.sub(r'\b(phone|number|is|my)\b', '', text, flags=re.IGNORECASE)
    phone_pattern = r'[\d\s\-\(\)\.]+\d'
    match = re.search(phone_pattern, text)
    if match:
        phone = re.sub(r'[^\d]', '', match.group(0))
        if len(phone) >= 10:
            return phone
    return None


def _extract_name(text: str) -> Optional[str]:
    """Extract name from text"""
    if not text or len(text) < 2:
        return None
    
    # Remove common prefixes
    name = text
    for prefix in ["my name is", "i am", "i'm", "this is", "it's", "call me"]:
        if name.lower().startswith(prefix):
            name = name[len(prefix):].strip()
    
    # Remove special characters except spaces and hyphens
    name = re.sub(r'[^\w\s\-]', '', name)
    
    # Capitalize
    return name.title() if name else None


def _parse_date_time(text: str) -> Optional[datetime]:
    """
    ✅ FIXED: Parse date/time from text with support for day names and proper timezone handling
    
    Supports formats like:
    - "tomorrow at 2pm"
    - "next Monday at 10am"
    - "Friday at 3:30pm"
    - "today at 4pm"
    """
    text_lower = text.lower().strip()
    now = datetime.utcnow()
    
    logger.info(f"📅 Parsing date/time from: '{text}'")
    
    # Define day names with their weekday numbers (0 = Monday, 6 = Sunday)
    days_map = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }
    
    # Extract time (patterns like "2pm", "14:00", "2:30 pm", "10 am")
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?'
    time_match = re.search(time_pattern, text_lower)
    
    hour = 10  # Default hour
    minute = 0  # Default minute
    
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        
        # Handle AM/PM conversion
        if meridiem:
            meridiem_clean = meridiem.replace('.', '').strip()
            if 'pm' in meridiem_clean or 'p.m' in meridiem_clean:
                if hour != 12:
                    hour += 12
            elif ('am' in meridiem_clean or 'a.m' in meridiem_clean) and hour == 12:
                hour = 0
        
        logger.info(f"✅ Extracted time: {hour:02d}:{minute:02d}")
    
    # Determine base date
    base_date = None
    
    # Check for "tomorrow"
    if "tomorrow" in text_lower:
        base_date = now + timedelta(days=1)
        logger.info(f"📅 Detected: tomorrow")
    
    # Check for "today"
    elif "today" in text_lower:
        base_date = now
        logger.info(f"📅 Detected: today")
    
    # Check for "next week"
    elif "next week" in text_lower:
        base_date = now + timedelta(days=7)
        logger.info(f"📅 Detected: next week")
    
    # Check for day names (Monday, Tuesday, etc.)
    else:
        for day_name, target_weekday in days_map.items():
            if day_name in text_lower:
                current_weekday = now.weekday()
                
                # Calculate days until next occurrence of this weekday
                days_ahead = (target_weekday - current_weekday) % 7
                
                # If "next" is mentioned explicitly, add 7 days
                if "next" in text_lower and days_ahead == 0:
                    days_ahead = 7
                elif days_ahead == 0:
                    # If it's the same day but no "next", assume next week
                    days_ahead = 7
                
                base_date = now + timedelta(days=days_ahead)
                logger.info(f"📅 Detected day: {day_name.capitalize()} (in {days_ahead} days)")
                break
    
    # Default to tomorrow if no date detected
    if not base_date:
        base_date = now + timedelta(days=1)
        logger.info(f"⚠️ No specific date detected, defaulting to tomorrow")
    
    # Set the time on the base date
    appointment_datetime = base_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )
    
    logger.info(f"✅ Final parsed datetime (UTC): {appointment_datetime}")
    logger.info(f"   → {appointment_datetime.strftime('%A, %B %d, %Y at %I:%M %p UTC')}")
    
    return appointment_datetime


# ============================================
# CAMPAIGN WORKFLOW MATCHING
# ============================================

async def _match_campaign_workflow(
    user_input: str,
    user_id: str,
    db
) -> Optional[Dict]:
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
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 SMS CHAT - Campaign Matching")
        logger.info(f"   User input: '{user_input}'")
        logger.info(f"{'='*80}\n")
        
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
                            "match_type": "keyword_match",
                            "matched_keyword": keyword_clean,
                            "confidence": 1.0
                        }
        
        return None
        
    except Exception as e:
        logger.error(f"Error matching campaign: {e}")
        return None


# ============================================
# APPOINTMENT BOOKING LOGIC
# ============================================

async def _process_appointment_booking(
    user_message: str,
    conversation_state: Dict,
    user_id: str,
    phone_number: str,
    db
) -> Dict:
    """Process appointment booking conversation"""
    try:
        current_step = conversation_state.get("current_step")
        collected_data = conversation_state.get("collected_data", {})
        
        logger.info(f"\n📅 Appointment Booking - Step: {current_step}")
        logger.info(f"   Collected so far: {list(collected_data.keys())}")
        
        # Determine next step based on what's missing
        if not collected_data.get("name"):
            # Extract name
            name = _extract_name(user_message)
            if name:
                collected_data["name"] = name
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data, "current_step": "name"},
                    db
                )
                return {
                    "response": f"Thank you, {name}! What's your email address so I can send you a confirmation?",
                    "booking_complete": False
                }
            else:
                return {
                    "response": "I didn't catch your name. Could you please tell me your name?",
                    "booking_complete": False
                }
        
        elif not collected_data.get("email"):
            # Extract email
            email = _extract_email(user_message)
            if email:
                collected_data["email"] = email
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data, "current_step": "email"},
                    db
                )
                return {
                    "response": "Perfect! When would you like to schedule the appointment? You can say something like 'tomorrow at 2pm' or 'next Monday at 10am'.",
                    "booking_complete": False
                }
            else:
                return {
                    "response": "I didn't find a valid email address. Could you please provide your email?",
                    "booking_complete": False
                }
        
        elif not collected_data.get("date"):
            # Extract date/time
            appointment_datetime = _parse_date_time(user_message)
            if appointment_datetime:
                collected_data["date"] = appointment_datetime.isoformat()
                await _update_conversation_state(
                    phone_number, user_id,
                    {"collected_data": collected_data, "current_step": "date"},
                    db
                )
                
                # All data collected - create appointment!
                return await _create_appointment(
                    collected_data, user_id, phone_number, db
                )
            else:
                return {
                    "response": "I didn't understand the date/time. Please try again with something like 'tomorrow at 2pm' or 'Friday at 10am'.",
                    "booking_complete": False
                }
        
        else:
            # Shouldn't reach here, but handle anyway
            return await _create_appointment(
                collected_data, user_id, phone_number, db
            )
            
    except Exception as e:
        logger.error(f"Error processing appointment: {e}", exc_info=True)
        return {
            "response": "I apologize, but there was an error processing your appointment. Please try again or contact us directly.",
            "booking_complete": True
        }


async def _create_appointment(
    collected_data: Dict,
    user_id: str,
    phone_number: str,
    db
) -> Dict:
    """Create the appointment in Google Calendar and send email"""
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"📅 CREATING APPOINTMENT")
        logger.info(f"   Name: {collected_data.get('name')}")
        logger.info(f"   Email: {collected_data.get('email')}")
        logger.info(f"   Date: {collected_data.get('date')}")
        logger.info(f"{'='*80}\n")
        
        customer_name = collected_data["name"]
        customer_email = collected_data["email"]
        appointment_date = datetime.fromisoformat(collected_data["date"])
        service_type = collected_data.get("service", "General Appointment")
        appointment_time = appointment_date.strftime("%H:%M")
        
        # ✅ FIXED: Use correct parameter names for google_calendar_service.create_event()
        calendar_result = await google_calendar_service.create_event(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=phone_number,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=60,
            service_type=service_type,
            notes=None
        )
        
        if not calendar_result.get("success"):
            raise Exception(f"Calendar error: {calendar_result.get('error')}")
        
        # Save to database
        appointment_data = {
            "user_id": user_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": phone_number,
            "service": service_type,  # ✅ Changed from "service_type" to "service"
            "appointment_date": appointment_date,
            "status": "confirmed",
            "google_calendar_event_id": calendar_result.get("event_id"),
            "google_calendar_link": calendar_result.get("html_link"),
            "booking_source": "sms_chat",
            "created_at": datetime.utcnow()
        }
        
        result = await db.appointments.insert_one(appointment_data)
        appointment_id = str(result.inserted_id)
        
        logger.info(f"✅ Appointment saved: {appointment_id}")
        
        # Send confirmation email and log it
        try:
            formatted_date = appointment_date.strftime("%A, %B %d, %Y at %I:%M %p")
            
            # ✅ Use email_automation_service which handles both sending AND logging
            await email_automation_service.send_appointment_confirmation(
                to_email=customer_email,
                customer_name=customer_name,
                customer_phone=phone_number,
                service_type=service_type,
                appointment_date=formatted_date,
                user_id=user_id,
                appointment_id=appointment_id,
                call_id=None  # SMS booking, no call_id
            )
            
            logger.info(f"✅ Confirmation email sent to {customer_email}")
            
        except Exception as e:
            logger.error(f"Email error: {e}")
        
        # Clear conversation state
        await _clear_conversation_state(phone_number, user_id, db)
        
        # Format response
        date_str = appointment_date.strftime("%A, %B %d at %I:%M %p")
        response = f"Perfect! Your appointment is confirmed for {date_str}. I've sent a confirmation email to {customer_email}. Looking forward to seeing you!"
        
        logger.info(f"✅ BOOKING COMPLETE!")
        
        return {
            "response": response,
            "booking_complete": True
        }
        
    except Exception as e:
        logger.error(f"Error creating appointment: {e}", exc_info=True)
        
        # Clear conversation state even on error
        await _clear_conversation_state(phone_number, user_id, db)
        
        return {
            "response": "I apologize, but there was an error creating your appointment. Please try again or contact us directly.",
            "booking_complete": True
        }


# ============================================
# API ENDPOINTS
# ============================================

@router.get("/chat/{phone_number}")
async def get_chat_history(
    phone_number: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get SMS chat history with a phone number"""
    try:
        user_id = str(current_user["_id"])
        
        # Get messages
        cursor = db.sms_logs.find({
            "user_id": user_id,
            "$or": [
                {"to_number": phone_number},
                {"from_number": phone_number}
            ]
        }).sort("created_at", 1)
        
        messages = await cursor.to_list(length=None)
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": str(msg["_id"]),
                "content": msg["message"],
                "role": "user" if msg.get("direction", "outbound") == "inbound" else "assistant",
                "timestamp": msg["created_at"].isoformat(),
                "status": msg.get("status", "sent")
            })
        
        # Get customer info from first message
        customer_info = None
        for log in messages:
            if log.get("customer_name") or log.get("customer_email"):
                customer_info = {
                    "name": log.get("customer_name", "Unknown"),
                    "email": log.get("customer_email"),
                    "phone": log.get("from_number")
                }
        
        if not customer_info:
            customer_info = {
                "name": "Customer",
                "email": None,
                "phone": phone_number
            }
        
        return {
            "success": True,
            "messages": formatted_messages,
            "customer_info": customer_info
        }
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/chat/send")
async def send_chat_message(
    data: Dict,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Send message and get response - WITH APPOINTMENT BOOKING"""
    try:
        user_id = str(current_user["_id"])
        phone_number = data.get("phone_number")
        user_message = data.get("message", "").strip()
        
        if not phone_number or not user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number and message required"
            )
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📩 SMS: '{user_message}' from {phone_number}")
        logger.info(f"{'='*80}\n")
        
        # Get conversation state
        conversation_state = await _get_conversation_state(phone_number, user_id, db)
        
        # ============================================
        # PRIORITY 1: Handle Active Appointment Booking
        # ============================================
        if conversation_state.get("booking_in_progress"):
            logger.info("📅 Continuing appointment booking...")
            
            booking_result = await _process_appointment_booking(
                user_message, conversation_state, user_id, phone_number, db
            )
            
            ai_message = booking_result["response"]
            source = "appointment_booking"
            campaign_matched = False
            workflow_info = None
            
        # ============================================
        # PRIORITY 2: Check if User Wants to Book
        # ============================================
        elif any(word in user_message.lower() for word in ["book", "appointment", "schedule", "reserve"]):
            logger.info("📅 Starting new appointment booking...")
            
            # Start booking process
            await _update_conversation_state(
                phone_number, user_id,
                {"booking_in_progress": True, "current_step": "start", "collected_data": {}},
                db
            )
            
            ai_message = "Great! I can help you book an appointment. First, may I have your name?"
            source = "appointment_booking"
            campaign_matched = False
            workflow_info = None
            
        # ============================================
        # PRIORITY 3: Check Campaign Builder
        # ============================================
        else:
            campaign_match = await _match_campaign_workflow(
                user_input=user_message,
                user_id=user_id,
                db=db
            )
            
            if campaign_match and campaign_match.get("found"):
                # Use campaign response
                ai_message = campaign_match["response"]
                source = "campaign"
                campaign_matched = True
                workflow_info = {
                    "workflow_id": campaign_match["workflow_id"],
                    "workflow_name": campaign_match["workflow_name"],
                    "node_id": campaign_match["node_id"],
                    "matched_keyword": campaign_match.get("matched_keyword"),
                    "confidence": campaign_match.get("confidence", 1.0)
                }
                
                logger.info(f"✅ Using Campaign: {workflow_info['workflow_name']}")
                
            else:
                # ============================================
                # PRIORITY 4: Use OpenAI
                # ============================================
                logger.info(f"🤖 Using OpenAI")
                
                history_cursor = db.sms_logs.find({
                    "user_id": user_id,
                    "$or": [
                        {"to_number": phone_number},
                        {"from_number": phone_number}
                    ]
                }).sort("created_at", -1).limit(10)
                
                history = await history_cursor.to_list(length=10)
                history.reverse()
                
                conversation_context = []
                for msg in history:
                    role = "user" if msg.get("direction", "outbound") == "inbound" else "assistant"
                    conversation_context.append({
                        "role": role,
                        "content": msg["message"]
                    })
                
                conversation_context.append({
                    "role": "user",
                    "content": user_message
                })
                
                # Build dynamic system prompt from business profile
                from app.api.v1.business_profile import get_business_context_for_ai
                business_context = await get_business_context_for_ai(user_id, db)

                chat_base_prompt = """You are a helpful AI assistant responding to SMS messages.
You help answer customer questions about services, pricing, appointments, and general inquiries.
Be professional, friendly, and helpful. Keep responses under 150 words."""

                if business_context:
                    chat_system_prompt = f"{chat_base_prompt}\n\nHere is the business information you should use:\n\n{business_context}"
                else:
                    chat_system_prompt = chat_base_prompt

                ai_response = await openai_service.generate_chat_response(
                    messages=conversation_context,
                    system_prompt=chat_system_prompt
                )
                
                ai_message = ai_response.get("response", "I'm here to help! How can I assist you?")
                source = "openai"
                campaign_matched = False
                workflow_info = None
        
        # ============================================
        # STORE MESSAGES IN DATABASE
        # ============================================
        
        # Store user message
        user_msg_doc = {
            "user_id": user_id,
            "from_number": phone_number,
            "to_number": "+14388177856",  # Your Twilio number
            "message": user_message,
            "direction": "inbound",
            "status": "received",
            "created_at": datetime.utcnow()
        }
        
        user_result = await db.sms_logs.insert_one(user_msg_doc)
        user_msg_id = str(user_result.inserted_id)
        
        # Store AI response
        ai_msg_doc = {
            "user_id": user_id,
            "from_number": "+14388177856",
            "to_number": phone_number,
            "message": ai_message,
            "direction": "outbound",
            "status": "sent",
            "created_at": datetime.utcnow()
        }
        
        ai_result = await db.sms_logs.insert_one(ai_msg_doc)
        ai_msg_id = str(ai_result.inserted_id)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ SMS CHAT RESPONSE")
        logger.info(f"   Response: '{ai_message[:100]}...'")
        logger.info(f"   Source: {source.upper()}\n")
        
        return {
            "success": True,
            "user_message": {
                "id": user_msg_id,
                "content": user_message,
                "timestamp": user_msg_doc["created_at"].isoformat()
            },
            "ai_response": {
                "id": ai_msg_id,
                "content": ai_message,
                "timestamp": ai_msg_doc["created_at"].isoformat(),
                "source": source,
                "campaign_matched": campaign_matched,
                "workflow_info": workflow_info
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
