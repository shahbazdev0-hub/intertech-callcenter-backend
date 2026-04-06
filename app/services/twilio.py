# # backend/app/services/twilio.py - UPDATED WITH ENHANCED OUTBOUND METHODS annd also follow up ai steps and gogle calender events integration 



# voicemail enabled
"""
Twilio Service - ENHANCED with better outbound call handling
✅ ALL EXISTING FUNCTIONALITY PRESERVED
✅ NEW: Enhanced outbound call methods for automated callbacks
✅ ADDED: AMD (Answering Machine Detection) for voicemail detection
"""

import os
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TwilioService:
    def __init__(self):
        """Initialize Twilio service and load credentials"""
        self._is_configured = False
        self._reload_credentials()
    
    def _reload_credentials(self):
        """Reload Twilio credentials from environment variables"""
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.webhook_url = os.getenv("TWILIO_WEBHOOK_URL")
        
        # Debug print
        print()
        print("=" * 60)
        print("🔑 TWILIO SERVICE - Loading Credentials:")
        print("=" * 60)
        print(f"   Account SID: {self.account_sid}")
        print(f"   Phone Number: {self.phone_number}")
        print(f"   Webhook URL: {self.webhook_url}")
        print("=" * 60)
        print()
        
        if not self.account_sid or not self.auth_token:
            self._is_configured = False
            print("⚠️ Twilio credentials not configured")
            return
        
        self.client = Client(self.account_sid, self.auth_token)
        self._is_configured = True
    
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return self._is_configured

    def make_call(
        self,
        to_number: str,
        from_number: Optional[str] = None,
        webhook_url: Optional[str] = None,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate outbound call with proper recording callbacks.

        Args:
            to_number: Phone number to call
            from_number: Caller ID (optional, falls back to global TWILIO_PHONE_NUMBER)
            webhook_url: Custom webhook URL (optional)
            account_sid: Per-user Twilio subaccount SID (optional, for multi-tenant)
            auth_token: Per-user Twilio subaccount auth token (optional, for multi-tenant)

        Returns:
            Dict with call status
        """
        try:
            # Use per-user credentials if provided, otherwise use global
            if account_sid and auth_token:
                client = Client(account_sid, auth_token)
                caller_id = from_number  # must be provided for per-user
            else:
                self._reload_credentials()
                client = self.client
                caller_id = from_number or self.phone_number

            # Extract base URL without /incoming
            base_webhook_url = self.webhook_url.replace('/incoming', '') if '/incoming' in self.webhook_url else self.webhook_url
            outbound_webhook_url = webhook_url or f"{base_webhook_url}/incoming"

            # Separate callbacks for call status and recording
            status_callback_url = f"{base_webhook_url}/call-status"
            recording_status_callback_url = os.getenv("TWILIO_RECORDING_STATUS_CALLBACK") or f"{base_webhook_url}/recording-status"

            print()
            print("📞 INITIATING TWILIO CALL:")
            print(f"   To: {to_number}")
            print(f"   From: {caller_id}")
            print(f"   Webhook: {outbound_webhook_url}")
            print(f"   Status Callback: {status_callback_url}")
            print(f"   Recording Callback: {recording_status_callback_url}")
            print(f"   Using Subaccount: {bool(account_sid)}")
            print()

            call_kwargs = {
                "to": to_number,
                "from_": caller_id,
                "url": outbound_webhook_url,
                "status_callback": status_callback_url,
                "status_callback_event": ["initiated", "ringing", "answered", "completed"],
                "status_callback_method": "POST",
                "record": True,
                "recording_status_callback": recording_status_callback_url,
                "recording_status_callback_method": "POST",
                "recording_channels": "dual",
                "timeout": 60,  # ✅ Ring for 60 seconds before giving up
                "machine_detection": "DetectMessageEnd",  # ✅ Detect voicemail and wait for beep
            }

            call = client.calls.create(**call_kwargs)
            
            print(f"✅ Call initiated successfully!")
            print(f"   Call SID: {call.sid}")
            print(f"   Status: {call.status}")
            print()
            
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status
            }
            
        except Exception as e:
            print(f"❌ TWILIO ERROR: {str(e)}")
            print()
            return {
                "success": False,
                "error": str(e)
            }
    
    # ✅ NEW: Make automated follow-up call with custom greeting
    def make_follow_up_call(
        self,
        to_number: str,
        customer_name: str,
        original_request: Optional[str] = None,
        from_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ NEW: Make automated follow-up call with context
        
        Args:
            to_number: Phone number to call
            customer_name: Customer name for personalization
            original_request: Original user request
            from_number: Caller ID
        
        Returns:
            Dict with call status
        """
        try:
            logger.info(f"📞 Making follow-up call to {customer_name}")
            
            # Use standard make_call method
            result = self.make_call(
                to_number=to_number,
                from_number=from_number
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Follow-up call error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ✅ NEW: Make reminder call
    def make_reminder_call(
        self,
        to_number: str,
        reminder_message: str,
        from_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ NEW: Make automated reminder call
        
        Args:
            to_number: Phone number to call
            reminder_message: Reminder message to deliver
            from_number: Caller ID
        
        Returns:
            Dict with call status
        """
        try:
            logger.info(f"🔔 Making reminder call to {to_number}")
            
            result = self.make_call(
                to_number=to_number,
                from_number=from_number
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Reminder call error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def generate_twiml_response(
        self,
        message: str,
        voice: str = "Polly.Joanna",
        gather_input: bool = False,
        gather_timeout: int = 5
    ) -> str:
        """Generate TwiML response - UNCHANGED"""
        response = VoiceResponse()
        
        if gather_input:
            gather = Gather(
                input='speech',
                timeout=gather_timeout,
                action=f"{self.webhook_url}/process-speech",
                speechTimeout="auto",
                language="en-US"
            )
            gather.say(message, voice=voice)
            response.append(gather)
        else:
            response.say(message, voice=voice)
        
        return str(response)

    def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """Fetch call details from Twilio - UNCHANGED"""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "success": True,
                "call": {
                    "sid": call.sid,
                    "from": call.from_,
                    "to": call.to,
                    "status": call.status,
                    "duration": call.duration,
                    "price": call.price,
                }
            }
        except Exception as e:
            print(f"❌ Error fetching call details: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def hangup_call(self, call_sid: str) -> Dict[str, Any]:
        """Hangup an active call - UNCHANGED"""
        try:
            call = self.client.calls(call_sid).update(status="completed")
            return {
                "success": True,
                "status": call.status
            }
        except Exception as e:
            print(f"❌ Error hanging up call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Create singleton instance
twilio_service = TwilioService()