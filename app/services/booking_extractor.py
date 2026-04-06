"""
AI-powered booking entity extraction for SMS and Email appointment flows.
Uses Groq/OpenAI to extract name, email, service, and datetime from conversation history.
Also handles reschedule/cancel intent extraction.
"""

import json
import re
import logging
import dateparser
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.services.openai import openai_service

logger = logging.getLogger(__name__)

BOOKING_FIELDS = ["name", "email", "service", "datetime_text"]


async def extract_booking_fields(
    current_message: str,
    conversation_history: List[Dict[str, str]],
    already_collected: Dict[str, Any],
    business_context: str = "",
    channel: str = "sms"
) -> Dict[str, Any]:
    """
    Use AI to extract booking fields from the current message and conversation history.

    Returns:
    {
        "extracted": {"name": "...", "email": "...", "service": "...", "datetime_text": "..."},
        "missing_fields": ["email", "datetime_text"],
        "response": "natural language message to send",
        "is_booking_response": True/False,
        "all_complete": True/False
    }
    """
    today_str = datetime.utcnow().strftime("%A, %B %d, %Y at %I:%M %p UTC")

    # Build a summary of what's already collected
    collected_summary = {}
    for k, v in already_collected.items():
        if v:
            collected_summary[k] = v

    max_words = "150" if channel == "sms" else "200"

    system_prompt = f"""You are an appointment booking assistant. Today is {today_str}.

Your job: Extract appointment booking details from the conversation. Look at the ENTIRE conversation history, not just the latest message.

Fields to extract:
- name: Customer's full name
- email: Customer's email address (must contain @)
- service: The service they want (e.g., window cleaning, gutter cleaning, consultation)
- datetime_text: When they want the appointment as a natural date/time string (e.g., "tomorrow at 2pm", "Friday March 7 at 10am")

Already collected: {json.dumps(collected_summary) if collected_summary else "Nothing yet"}

{f'Business context: {business_context}' if business_context else ''}

RULES:
1. If a field was already collected AND the user is NOT correcting it, keep the existing value.
2. If the user says "I mentioned earlier", "as I said", "I already told you", etc., search the conversation history for that information and extract it.
3. For datetime_text: extract the natural language text exactly as the user said it. Do NOT parse or convert it.
4. If the latest message is NOT providing booking info (e.g., asking a question, making conversation), set "is_booking_response" to false and write a helpful answer in "response" that also gently reminds them about the booking.
5. If the user provides multiple pieces of info in one message, extract ALL of them.
6. For missing fields, write a natural "response" that asks for ALL missing items in one friendly message. Do not ask one at a time.
7. Keep response under {max_words} words.
8. If all 4 fields are present, set "all_complete" to true and write a confirmation summary in "response".

Respond with ONLY valid JSON (no markdown, no code blocks, no extra text):
{{"extracted": {{"name": "<value or null>", "email": "<value or null>", "service": "<value or null>", "datetime_text": "<value or null>"}}, "missing_fields": ["<field1>"], "response": "<your message>", "is_booking_response": true, "all_complete": false}}"""

    # Build messages: last 8 from history + current message
    messages = []
    for msg in conversation_history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": current_message})

    try:
        result = await openai_service.generate_chat_response(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.1
        )

        if not result.get("success"):
            logger.error(f"[BOOKING-EXTRACTOR] AI extraction failed: {result.get('error')}")
            return _fallback_extraction(current_message, already_collected, channel)

        response_text = result["response"]

        # Strip markdown code blocks if the model wraps in ```json
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

        parsed = json.loads(response_text)
        print(f"[BOOKING-EXTRACTOR] Extracted: {parsed.get('extracted', {})}")
        print(f"[BOOKING-EXTRACTOR] Missing: {parsed.get('missing_fields', [])}")
        print(f"[BOOKING-EXTRACTOR] All complete: {parsed.get('all_complete', False)}")
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"[BOOKING-EXTRACTOR] JSON parse error: {e} | Raw: {result.get('response', '')[:200]}")
        return _fallback_extraction(current_message, already_collected, channel)
    except Exception as e:
        logger.error(f"[BOOKING-EXTRACTOR] Error: {e}")
        return _fallback_extraction(current_message, already_collected, channel)


def _fallback_extraction(
    current_message: str,
    already_collected: Dict[str, Any],
    channel: str = "sms"
) -> Dict[str, Any]:
    """Simple regex fallback if AI fails."""
    extracted = dict(already_collected)

    # Try to detect email
    email_match = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w+', current_message)
    if email_match and not extracted.get("email"):
        extracted["email"] = email_match.group(0)

    # Try to detect a name (if message is short and looks like a name)
    if not extracted.get("name") and len(current_message.split()) <= 3 and not email_match:
        if not any(word in current_message.lower() for word in ["book", "appointment", "schedule", "clean", "when", "what"]):
            extracted["name"] = current_message.strip()

    missing = [f for f in BOOKING_FIELDS if not extracted.get(f)]

    if not missing:
        return {
            "extracted": extracted,
            "missing_fields": [],
            "response": "I have all the details. Let me book that for you!",
            "is_booking_response": True,
            "all_complete": True
        }

    # Build a natural prompt for missing fields
    field_prompts = {
        "name": "your name",
        "email": "your email address",
        "service": "what service you'd like",
        "datetime_text": "your preferred date and time (e.g., 'tomorrow at 2pm')"
    }
    missing_descriptions = [field_prompts.get(f, f) for f in missing]

    if len(missing_descriptions) == 1:
        ask_text = f"Could you provide {missing_descriptions[0]}?"
    else:
        ask_text = f"I still need: {', '.join(missing_descriptions[:-1])}, and {missing_descriptions[-1]}. Could you provide these?"

    return {
        "extracted": extracted,
        "missing_fields": missing,
        "response": ask_text,
        "is_booking_response": True,
        "all_complete": False
    }


async def validate_and_parse_datetime(
    datetime_text: str,
    business_context: str = ""
) -> Dict[str, Any]:
    """
    Parse natural-language datetime and validate against business hours.

    Returns:
    {
        "success": True/False,
        "parsed_date": datetime or None,
        "suggestion": "nearest valid time" or None,
        "error": "weekend" | "outside_hours" | "parse_failed" | None
    }
    """
    parsed = dateparser.parse(
        datetime_text,
        settings={'PREFER_DATES_FROM': 'future', 'TIMEZONE': 'UTC'}
    )

    if not parsed:
        return {
            "success": False,
            "parsed_date": None,
            "suggestion": None,
            "error": "parse_failed"
        }

    print(f"[BOOKING-EXTRACTOR] Parsed datetime: {parsed} from '{datetime_text}'")

    # Check weekend
    if parsed.weekday() >= 5:
        days_until_monday = 7 - parsed.weekday()
        suggested = parsed + timedelta(days=days_until_monday)
        suggested = suggested.replace(hour=max(9, min(parsed.hour, 16)), minute=0, second=0)
        return {
            "success": False,
            "parsed_date": parsed,
            "suggestion": suggested.strftime("%A, %B %d at %I:%M %p"),
            "error": "weekend"
        }

    # Check business hours (default 9 AM - 5 PM)
    if parsed.hour < 9 or parsed.hour >= 17:
        if parsed.hour < 9:
            suggested = parsed.replace(hour=9, minute=0, second=0)
        else:
            suggested = (parsed + timedelta(days=1)).replace(hour=9, minute=0, second=0)
            # Skip weekend for the suggestion
            while suggested.weekday() >= 5:
                suggested += timedelta(days=1)
        return {
            "success": False,
            "parsed_date": parsed,
            "suggestion": suggested.strftime("%A, %B %d at %I:%M %p"),
            "error": "outside_hours"
        }

    return {
        "success": True,
        "parsed_date": parsed,
        "suggestion": None,
        "error": None
    }


async def extract_reschedule_fields(
    current_message: str,
    conversation_history: List[Dict[str, str]],
    existing_appointment: Dict[str, Any],
    channel: str = "sms"
) -> Dict[str, Any]:
    """
    Use AI to extract reschedule details from conversation.

    Returns:
    {
        "new_datetime_text": "tomorrow at 3pm" or null,
        "is_cancel_request": True/False,
        "is_confirmation": True/False,
        "response": "natural language message to send"
    }
    """
    today_str = datetime.utcnow().strftime("%A, %B %d, %Y at %I:%M %p UTC")

    appt_date = existing_appointment.get("appointment_date", "")
    if isinstance(appt_date, datetime):
        appt_date = appt_date.strftime("%A, %B %d, %Y at %I:%M %p")
    appt_service = existing_appointment.get("service_type", "appointment")
    appt_name = existing_appointment.get("customer_name", "")

    max_words = "100" if channel == "sms" else "150"

    system_prompt = f"""You are an appointment management assistant. Today is {today_str}.

The customer has an existing appointment:
- Service: {appt_service}
- Date/Time: {appt_date}
- Name: {appt_name}

Your job: Understand if the customer wants to reschedule or cancel, and extract the new date/time if rescheduling.

RULES:
1. If the customer provides a new date/time, extract it as "new_datetime_text" (natural language, don't parse).
2. If the customer confirms (says "yes", "confirm", "correct", etc.), set "is_confirmation" to true.
3. If the customer wants to cancel instead of reschedule, set "is_cancel_request" to true.
4. If no new date/time is provided, ask for it in "response".
5. Keep response under {max_words} words.
6. Be friendly and reference their existing appointment details.

Respond with ONLY valid JSON (no markdown, no code blocks):
{{"new_datetime_text": "<value or null>", "is_cancel_request": false, "is_confirmation": false, "response": "<your message>"}}"""

    messages = []
    for msg in conversation_history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": current_message})

    try:
        result = await openai_service.generate_chat_response(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=200,
            temperature=0.1
        )

        if not result.get("success"):
            logger.error(f"[RESCHEDULE-EXTRACTOR] AI extraction failed: {result.get('error')}")
            return _fallback_reschedule(current_message)

        response_text = result["response"].strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

        parsed = json.loads(response_text)
        print(f"[RESCHEDULE-EXTRACTOR] Result: {parsed}")
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"[RESCHEDULE-EXTRACTOR] JSON parse error: {e}")
        return _fallback_reschedule(current_message)
    except Exception as e:
        logger.error(f"[RESCHEDULE-EXTRACTOR] Error: {e}")
        return _fallback_reschedule(current_message)


def _fallback_reschedule(current_message: str) -> Dict[str, Any]:
    """Simple fallback for reschedule extraction."""
    lower = current_message.lower().strip()

    # Check for confirmation
    if lower in ["yes", "yeah", "yep", "confirm", "ok", "okay", "sure", "y"]:
        return {
            "new_datetime_text": None,
            "is_cancel_request": False,
            "is_confirmation": True,
            "response": ""
        }

    # Check for cancel intent
    if any(w in lower for w in ["cancel", "remove", "delete", "nevermind", "never mind"]):
        return {
            "new_datetime_text": None,
            "is_cancel_request": True,
            "is_confirmation": False,
            "response": "Would you like to cancel your appointment? Reply YES to confirm."
        }

    # Try dateparser on the whole message
    parsed = dateparser.parse(lower, settings={'PREFER_DATES_FROM': 'future'})
    if parsed:
        return {
            "new_datetime_text": current_message.strip(),
            "is_cancel_request": False,
            "is_confirmation": False,
            "response": f"I'll reschedule your appointment to {parsed.strftime('%A, %B %d at %I:%M %p')}. Does that work?"
        }

    return {
        "new_datetime_text": None,
        "is_cancel_request": False,
        "is_confirmation": False,
        "response": "When would you like to reschedule your appointment to? Please provide a new date and time."
    }
