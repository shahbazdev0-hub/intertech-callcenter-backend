# backend/app/services/email_poller.py - IMAP Gmail Polling for Inbound Emails

import asyncio
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta
import logging
import os
import re
import traceback
from typing import Optional, Set
from functools import partial

from app.database import get_database
from app.services.openai import openai_service
from app.services.email_automation import email_automation_service
from app.services.email import email_service
from app.utils.credential_resolver import resolve_email_credentials

logger = logging.getLogger(__name__)


class EmailPollerService:
    """
    Gmail IMAP Polling Service - Checks inbox for new emails and auto-replies with AI.
    """

    def __init__(self):
        self.imap_host = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("EMAIL_FROM")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "CallCenter SaaS")
        self.polling_interval = int(os.getenv("EMAIL_POLLING_INTERVAL", "60"))
        self.is_running = False
        self.processed_uids: Set[str] = set()

    def is_configured(self) -> bool:
        return all([self.email_user, self.email_password])

    # ============================================
    # IMAP HELPERS (all synchronous - run in executor)
    # ============================================

    def _connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.email_user, self.email_password)
            return mail
        except Exception as e:
            print(f"[EMAIL-POLLER] IMAP connection failed: {e}")
            logger.error(f"IMAP connection failed: {e}")
            return None

    def _fetch_unread_emails(self, mail) -> list:
        """Fetch unread emails - runs in executor (blocking)"""
        results = []
        try:
            mail.select("INBOX")
            since_date = (datetime.utcnow() - timedelta(days=1)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(UNSEEN SINCE {since_date})')

            if status != "OK" or not messages[0]:
                return []

            email_uids = messages[0].split()
            print(f"[EMAIL-POLLER] IMAP found {len(email_uids)} UNSEEN emails")

            for uid in email_uids:
                uid_str = uid.decode()

                if uid_str in self.processed_uids:
                    continue

                try:
                    # Use BODY.PEEK[] to avoid marking as READ
                    status, msg_data = mail.fetch(uid, "(BODY.PEEK[])")
                    if status != "OK":
                        self.processed_uids.add(uid_str)
                        continue

                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    from_raw = self._decode_header_value(msg.get("From", ""))
                    to_raw = self._decode_header_value(msg.get("To", ""))
                    subject = self._decode_header_value(msg.get("Subject", ""))
                    body = self._get_email_body(msg)

                    from_email = self._extract_email_address(from_raw)
                    to_email = self._extract_email_address(to_raw)

                    results.append({
                        "uid": uid_str,
                        "from_email": from_email,
                        "to_email": to_email,
                        "subject": subject,
                        "body": body
                    })

                except Exception as e:
                    print(f"[EMAIL-POLLER] Error parsing email UID {uid_str}: {e}")
                    self.processed_uids.add(uid_str)

        except Exception as e:
            print(f"[EMAIL-POLLER] IMAP fetch error: {e}")

        # Mark processed emails as SEEN so they don't appear in next UNSEEN search
        for r in results:
            try:
                mail.store(r["uid"].encode(), '+FLAGS', '\\Seen')
            except Exception:
                pass

        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

        return results

    def _decode_header_value(self, value) -> str:
        if value is None:
            return ""
        decoded_parts = decode_header(value)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += part
        return result

    def _extract_email_address(self, email_string: str) -> str:
        if not email_string:
            return ""
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_string)
        return match.group(0).lower() if match else email_string.lower()

    def _get_email_body(self, msg) -> str:
        """Extract plain text body, strip quoted replies"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" in content_disposition:
                    continue
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body = payload.decode(charset, errors='ignore')
                            break
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except Exception:
                pass

        # Strip quoted replies
        lines = body.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('>'):
                break
            if re.match(r'^On .+ wrote:$', stripped):
                break
            if stripped == '---' or stripped.startswith('------'):
                break
            clean_lines.append(line)

        return '\n'.join(clean_lines).strip()

    # ============================================
    # MAIN POLLING LOOP
    # ============================================

    async def start_polling(self):
        """Start the IMAP polling loop"""
        if not self.is_configured():
            print("[EMAIL-POLLER] Not configured - missing EMAIL_USER or EMAIL_PASSWORD")
            return

        self.is_running = True
        print("=" * 60)
        print("[EMAIL-POLLER] STARTED")
        print(f"   User: {self.email_user}")
        print(f"   IMAP: {self.imap_host}:{self.imap_port}")
        print(f"   Interval: {self.polling_interval}s")
        print("=" * 60)

        # Wait a few seconds for DB to be ready
        await asyncio.sleep(5)

        while self.is_running:
            try:
                await self._poll_inbox()
            except Exception as e:
                print(f"[EMAIL-POLLER] Polling error: {e}")
                traceback.print_exc()

            await asyncio.sleep(self.polling_interval)

    def stop_polling(self):
        self.is_running = False
        print("[EMAIL-POLLER] Stopped")

    async def _poll_inbox(self):
        """Check Gmail inbox for new unread emails"""
        loop = asyncio.get_event_loop()

        # Run ALL blocking IMAP operations in executor
        mail = await loop.run_in_executor(None, self._connect_imap)
        if not mail:
            return

        emails = await loop.run_in_executor(None, self._fetch_unread_emails, mail)

        if not emails:
            return

        print(f"[EMAIL-POLLER] Found {len(emails)} new email(s)")

        for email_data in emails:
            uid = email_data["uid"]
            from_email = email_data["from_email"]
            to_email = email_data["to_email"]
            subject = email_data["subject"]
            body = email_data["body"]

            # Skip emails from ourselves (auto-reply loop prevention)
            if from_email.lower() == self.email_user.lower():
                print(f"[EMAIL-POLLER] Skipping self-email from {from_email}")
                self.processed_uids.add(uid)
                continue

            # Skip empty emails
            if not body.strip():
                print(f"[EMAIL-POLLER] Skipping empty email from {from_email}")
                self.processed_uids.add(uid)
                continue

            print(f"[EMAIL-POLLER] Processing: From={from_email} Subject={subject[:50]}")

            try:
                await self._process_inbound_email(
                    from_email=from_email,
                    to_email=to_email,
                    subject=subject,
                    body=body
                )
                print(f"[EMAIL-POLLER] Successfully processed email from {from_email}")
            except Exception as e:
                print(f"[EMAIL-POLLER] Error processing email from {from_email}: {e}")
                traceback.print_exc()

            self.processed_uids.add(uid)

    # ============================================
    # PROCESS INBOUND EMAIL
    # ============================================

    async def _process_inbound_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str
    ):
        """Process an inbound email - match user, generate AI response, send reply"""
        from bson import ObjectId

        db = await get_database()

        # ============================================
        # MATCH USER
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

        # Strategy 3: Previous conversation
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

        # Strategy 4: Fallback to admin
        if not primary_user:
            primary_user = await db.users.find_one({
                "is_active": True,
                "role": {"$in": ["superadmin", "admin"]}
            })

        if not primary_user:
            print(f"[EMAIL-POLLER] No matching user for to_email: {to_email}")
            return

        user_id = str(primary_user["_id"])
        print(f"[EMAIL-POLLER] Matched user: {user_id} ({primary_user.get('email')})")

        # ============================================
        # DUPLICATE CHECK (match by from + subject + body content)
        # ============================================
        existing = await db.email_logs.find_one({
            "from_email": from_email,
            "subject": subject,
            "text_content": body,
            "direction": "inbound",
            "created_at": {"$gte": datetime.utcnow() - timedelta(minutes=5)}
        })
        if existing:
            print(f"[EMAIL-POLLER] Skipping duplicate email from {from_email}")
            return

        # ============================================
        # STORE INBOUND EMAIL
        # ============================================
        email_log_data = {
            "user_id": user_id,
            "to_email": to_email,
            "from_email": from_email,
            "subject": subject,
            "content": body,
            "text_content": body,
            "status": "received",
            "direction": "inbound",
            "source": "imap_poller",
            "created_at": datetime.utcnow(),
            "opened_count": 0,
            "clicked_count": 0,
            "clicked_links": []
        }
        await db.email_logs.insert_one(email_log_data)
        print(f"[EMAIL-POLLER] Inbound email stored")

        # ============================================
        # GENERATE AI RESPONSE
        # ============================================
        # Use body for intent detection (NOT subject - subject may contain old thread text)
        full_message = f"{subject}\n\n{body}" if subject else body
        body_lower = body.lower().strip()

        ai_message = None
        source = "none"

        # Check conversation state for booking
        conversation_state = await db.email_conversation_states.find_one({
            "email_address": from_email,
            "user_id": user_id
        })

        # Only check BODY for booking intent (not subject which may have old "Appointment" text)
        booking_keywords = ["book", "book an appointment", "schedule", "reserve", "make an appointment"]
        is_booking_request = any(word in body_lower for word in booking_keywords)

        # Reschedule/Cancel intent detection
        reschedule_keywords = ["reschedule", "change appointment", "move appointment", "change my appointment", "postpone"]
        cancel_keywords = ["cancel appointment", "cancel my appointment", "cancel booking", "cancel my booking"]
        is_reschedule_request = any(phrase in body_lower for phrase in reschedule_keywords)
        is_cancel_request = any(phrase in body_lower for phrase in cancel_keywords)

        topic_change_keywords = [
            "price", "pricing", "cost", "pay", "payment", "fee",
            "support", "help", "issue", "problem",
            "refund", "question", "info", "information",
            "service", "offering", "offer", "what do you"
        ]
        is_topic_change = any(word in body_lower for word in topic_change_keywords)

        # PRIORITY 1: Active booking continuation
        if conversation_state and conversation_state.get("booking_in_progress") and not is_topic_change:
            print(f"[EMAIL-POLLER] Continuing booking for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_booking
            booking_result = await _process_email_appointment_booking(
                body, conversation_state, user_id, from_email, db
            )
            ai_message = booking_result["response"]
            source = "appointment_booking"

        # PRIORITY 1.5a: Active reschedule continuation
        elif conversation_state and conversation_state.get("reschedule_in_progress"):
            print(f"[EMAIL-POLLER] Continuing reschedule for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_reschedule
            reschedule_result = await _process_email_appointment_reschedule(
                body, conversation_state, user_id, from_email, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        # PRIORITY 1.5b: Active cancel continuation
        elif conversation_state and conversation_state.get("cancel_in_progress"):
            print(f"[EMAIL-POLLER] Continuing cancel for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_cancel
            cancel_result = await _process_email_appointment_cancel(
                body, conversation_state, user_id, from_email, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # PRIORITY 1.6: New reschedule request
        elif is_reschedule_request:
            print(f"[EMAIL-POLLER] Starting reschedule for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_reschedule, _update_email_conversation_state
            await _update_email_conversation_state(
                from_email, user_id,
                {"reschedule_in_progress": True, "reschedule_data": {}}, db
            )
            reschedule_result = await _process_email_appointment_reschedule(
                body, {"reschedule_data": {}}, user_id, from_email, db
            )
            ai_message = reschedule_result["response"]
            source = "appointment_reschedule"

        # PRIORITY 1.7: New cancel request
        elif is_cancel_request:
            print(f"[EMAIL-POLLER] Starting cancel for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_cancel, _update_email_conversation_state
            await _update_email_conversation_state(
                from_email, user_id,
                {"cancel_in_progress": True, "cancel_data": {}}, db
            )
            cancel_result = await _process_email_appointment_cancel(
                body, {"cancel_data": {}}, user_id, from_email, db
            )
            ai_message = cancel_result["response"]
            source = "appointment_cancel"

        # PRIORITY 2: New booking request
        elif is_booking_request and not is_topic_change:
            print(f"[EMAIL-POLLER] Starting new booking for {from_email}")
            from app.api.v1.email_webhook import _process_email_appointment_booking, _update_email_conversation_state
            await _update_email_conversation_state(
                from_email, user_id,
                {"booking_in_progress": True, "current_step": "ai_collecting", "collected_data": {}},
                db
            )
            booking_result = await _process_email_appointment_booking(
                body, {"current_step": "ai_collecting", "collected_data": {}},
                user_id, from_email, db
            )
            ai_message = booking_result["response"]
            source = "appointment_booking"

        # PRIORITY 3: Reset booking on topic change
        elif is_topic_change and conversation_state and conversation_state.get("booking_in_progress"):
            from app.api.v1.email_webhook import _update_email_conversation_state
            await _update_email_conversation_state(
                from_email, user_id,
                {"booking_in_progress": False, "current_step": None, "collected_data": {}},
                db
            )

        # PRIORITY 4: Campaign Builder
        if not ai_message:
            from app.api.v1.email_webhook import _match_email_campaign_workflow
            campaign_match = await _match_email_campaign_workflow(
                user_input=full_message, user_id=user_id, db=db
            )
            if campaign_match and campaign_match.get("found"):
                ai_message = campaign_match["response"]
                source = "campaign"
                print(f"[EMAIL-POLLER] Campaign match: {campaign_match['workflow_name']}")

            # PRIORITY 5: OpenAI
            else:
                print(f"[EMAIL-POLLER] Using OpenAI for response")
                try:
                    # Build conversation context from history
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
                            conversation_context.append({"role": role, "content": content})

                    conversation_context.append({"role": "user", "content": full_message})

                    print(f"[EMAIL-POLLER] Sending to OpenAI with {len(conversation_context)} messages")

                    # Build dynamic system prompt from business profile
                    from app.api.v1.business_profile import get_business_context_for_ai
                    business_context = await get_business_context_for_ai(user_id, db)

                    base_prompt = """You are a helpful AI assistant responding to emails.
You help answer customer questions about services, pricing, appointments, and general inquiries.
Be professional, friendly, and thorough in your email responses.
Format your responses appropriately for email communication.
Keep responses under 300 words."""

                    if business_context:
                        system_prompt = f"{base_prompt}\n\nHere is the business information you should use to answer questions:\n\n{business_context}"
                    else:
                        system_prompt = base_prompt

                    ai_response = await openai_service.generate_chat_response(
                        messages=conversation_context,
                        system_prompt=system_prompt,
                        max_tokens=500
                    )

                    if ai_response.get("success"):
                        ai_message = ai_response.get("response", "Thank you for your email. Our team will get back to you shortly!")
                        source = "openai"
                        print(f"[EMAIL-POLLER] OpenAI response: {ai_message[:100]}...")
                    else:
                        print(f"[EMAIL-POLLER] OpenAI failed: {ai_response.get('error')}")
                        ai_message = "Thank you for your email. Our team will review your message and respond shortly!"
                        source = "fallback"

                except Exception as e:
                    print(f"[EMAIL-POLLER] OpenAI error: {e}")
                    traceback.print_exc()
                    ai_message = "Thank you for your email. Our team will review your message and respond shortly!"
                    source = "fallback"

        # ============================================
        # SEND AI RESPONSE
        # ============================================
        if ai_message:
            reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

            # Use user-specific SMTP if available
            smtp_config = resolve_email_credentials(primary_user)
            reply_from_email = smtp_config.get("from_email") or self.from_email
            reply_from_name = smtp_config.get("from_name") or self.from_name

            print(f"[EMAIL-POLLER] Sending reply from {reply_from_email} to {from_email}")

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

            try:
                has_custom_smtp = smtp_config.get("smtp_host") and smtp_config.get("smtp_password")

                if has_custom_smtp:
                    await email_service.send_email_with_credentials(
                        to_email=from_email,
                        subject=reply_subject,
                        html_content=html_content,
                        smtp_config=smtp_config,
                        text_content=ai_message
                    )
                else:
                    await email_automation_service.send_email(
                        to_email=from_email,
                        subject=reply_subject,
                        html_content=html_content,
                        user_id=user_id,
                        text_content=ai_message
                    )

                # Log outbound response
                response_log = {
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
                    "source": "imap_poller",
                    "original_email_subject": subject,
                    "created_at": datetime.utcnow(),
                    "sent_at": datetime.utcnow(),
                    "opened_count": 0,
                    "clicked_count": 0,
                    "clicked_links": []
                }
                await db.email_logs.insert_one(response_log)

                print(f"[EMAIL-POLLER] AI reply SENT to {from_email} (source: {source})")

            except Exception as e:
                print(f"[EMAIL-POLLER] FAILED to send reply: {e}")
                traceback.print_exc()


# Singleton instance
email_poller_service = EmailPollerService()
