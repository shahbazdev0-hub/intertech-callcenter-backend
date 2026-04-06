 

# backend/app/services/sms.py   with ai follow up steps and calender integration 

import os
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from bson import ObjectId
import logging

from app.database import get_database

logger = logging.getLogger(__name__)


class SMSService:
    """SMS Service using Twilio"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.default_from: Optional[str] = None
        self.db = None
        self._is_configured = False
        
        # Try to initialize Twilio from environment variables
        self._init_twilio()
    
    def _init_twilio(self):
        """Initialize Twilio client from environment variables"""
        try:
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            phone_number = os.getenv("TWILIO_PHONE_NUMBER")
            
            if account_sid and auth_token:
                # Strip spaces and any hidden characters
                account_sid = account_sid.strip()
                auth_token = auth_token.strip()
                if phone_number:
                    phone_number = phone_number.strip()
                
                self.client = Client(account_sid, auth_token)
                self.default_from = phone_number
                self._is_configured = True
                logger.info("✅ SMS Service: Twilio configured")
                logger.info(f"📱 SMS From Number: {phone_number}")
            else:
                logger.warning("⚠️ SMS Service: Twilio not configured - SMS will be disabled")
                self._is_configured = False
        except Exception as e:
            logger.error(f"❌ SMS Service: Failed to initialize Twilio - {e}")
            self._is_configured = False

    def _validate_phone_numbers(self, to_number: str, from_number: str) -> bool:
        """
        Validate that to and from numbers are different
        """
        try:
            # Normalize phone numbers for comparison
            def normalize_phone(phone):
                # Remove all non-digit characters except +
                phone = re.sub(r'[^\d+]', '', phone)
                # Keep last 10 digits for comparison (US numbers)
                if len(phone) > 10:
                    return phone[-10:]
                return phone
            
            to_normalized = normalize_phone(to_number)
            from_normalized = normalize_phone(from_number)
            
            # Check if numbers are the same
            if to_normalized == from_normalized:
                logger.error(f"❌ SMS Validation Failed: 'To' and 'From' numbers are the same: {to_number}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating phone numbers: {e}")
            return True  # Allow sending if validation fails
    
    def is_configured(self) -> bool:
        """Check if SMS service is configured"""
        return self._is_configured
    
    async def get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        call_id: Optional[str] = None,
        campaign_id: Optional[str] = None,  # ✅ Campaign tracking parameter
        automation_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send SMS message and create log entries
        
        ✅ SUPPORTS: Campaign tracking for bulk SMS campaigns
        
        Args:
            to_number: Recipient phone number
            message: SMS message content
            from_number: Sender phone number (optional)
            user_id: User ID (optional)
            metadata: Additional metadata (optional)
            call_id: Associated call ID (optional)
            campaign_id: Associated campaign ID (optional) - 🆕 FOR BULK CAMPAIGNS
            automation_id: Associated automation ID (optional)
            customer_name: Customer name (optional)
            customer_email: Customer email (optional)
            
        Returns:
            Dict with success status and details
        """
        
        # Check if configured
        if not self._is_configured:
            logger.warning("⚠️ SMS Service not configured")
            return {
                "success": False,
                "error": "SMS service not configured. Please set up Twilio credentials."
            }
        
        # Clean phone numbers - strip whitespace and ensure format
        from_number = (from_number or self.default_from or "").strip()
        to_number = to_number.strip()
        
        # Validate phone numbers
        if not self._validate_phone_numbers(to_number, from_number):
            return {
                "success": False,
                "error": f"Cannot send SMS: 'To' and 'From' numbers cannot be the same",
                "error_code": "SAME_NUMBER"
            }
        
        try:
            # Enhanced logging
            logger.info(f"\n{'='*80}")
            logger.info(f"📱 SENDING SMS VIA TWILIO")
            logger.info(f"{'='*80}")
            logger.info(f"   From: '{from_number}' (length: {len(from_number)})")
            logger.info(f"   To: '{to_number}' (length: {len(to_number)})")
            logger.info(f"   Message: {message[:50]}...")
            if campaign_id:
                logger.info(f"   Campaign ID: {campaign_id}")  # 🆕 Log campaign tracking
            logger.info(f"   Account SID: {self.client.account_sid[:10]}...")
            logger.info(f"{'='*80}\n")
            
            # Ensure clean phone number format
            if not from_number.startswith('+'):
                from_number = '+' + from_number.lstrip('+')
            if not to_number.startswith('+'):
                to_number = '+' + to_number.lstrip('+')
            
            # Send via Twilio
            twilio_message = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to_number
            )
            
            logger.info(f"✅ SMS sent successfully!")
            logger.info(f"   Twilio SID: {twilio_message.sid}")
            logger.info(f"   Status: {twilio_message.status}")
            
            # Prepare SMS data
            sms_data = {
                "user_id": user_id,
                "to_number": to_number,
                "from_number": from_number,
                "message": message,
                "status": "sent",
                "direction": "outbound",
                "twilio_sid": twilio_message.sid,
                "twilio_status": twilio_message.status,
                "metadata": metadata or {},
                "campaign_id": campaign_id,  # 🆕 Store campaign ID
                "created_at": datetime.utcnow(),
                "sent_at": datetime.utcnow()
            }
            
            # Get database
            db = await self.get_db()
            
            # Store in sms_messages collection
            result = await db.sms_messages.insert_one(sms_data.copy())
            
            # Store in sms_logs collection with additional context
            sms_log_data = sms_data.copy()
            if call_id:
                sms_log_data["call_id"] = call_id
            if campaign_id:
                sms_log_data["campaign_id"] = campaign_id  # 🆕 Track in logs
            if automation_id:
                sms_log_data["automation_id"] = automation_id
            if customer_name:
                sms_log_data["customer_name"] = customer_name
            if customer_email:
                sms_log_data["customer_email"] = customer_email
            
            sms_log_data["is_reply"] = False
            sms_log_data["has_replies"] = False
            sms_log_data["reply_count"] = 0
            sms_log_data["delivered_at"] = None
            
            await db.sms_logs.insert_one(sms_log_data)
            
            if campaign_id:
                logger.info(f"✅ SMS logged with campaign tracking: {campaign_id}")
            else:
                logger.info(f"✅ SMS logged in both collections")
            
            return {
                "success": True,
                "sms_id": str(result.inserted_id),
                "twilio_sid": twilio_message.sid,
                "status": twilio_message.status,
                "to_number": to_number,
                "from_number": from_number,
                "message": "SMS sent successfully"
            }
            
        except TwilioRestException as e:
            logger.error(f"\n{'='*80}")
            logger.error(f"❌ TWILIO SMS ERROR")
            logger.error(f"{'='*80}")
            logger.error(f"   Error Code: {e.code}")
            logger.error(f"   Error Message: {e.msg}")
            logger.error(f"   From Number: '{from_number}'")
            logger.error(f"   To Number: '{to_number}'")
            if campaign_id:
                logger.error(f"   Campaign ID: {campaign_id}")
            logger.error(f"{'='*80}\n")
            
            # Save failed attempt to both collections
            db = await self.get_db()
            failed_sms_data = {
                "user_id": user_id,
                "to_number": to_number,
                "from_number": from_number,
                "message": message,
                "status": "failed",
                "direction": "outbound",
                "error_code": str(e.code),
                "error_message": str(e.msg),
                "metadata": metadata or {},
                "campaign_id": campaign_id,  # 🆕 Track campaign even in failures
                "created_at": datetime.utcnow()
            }
            
            # Store in sms_messages
            await db.sms_messages.insert_one(failed_sms_data.copy())
            
            # Store in sms_logs
            failed_sms_log = failed_sms_data.copy()
            if call_id:
                failed_sms_log["call_id"] = call_id
            if campaign_id:
                failed_sms_log["campaign_id"] = campaign_id  # 🆕 Track in logs
            if customer_name:
                failed_sms_log["customer_name"] = customer_name
            if customer_email:
                failed_sms_log["customer_email"] = customer_email
            
            failed_sms_log["is_reply"] = False
            failed_sms_log["has_replies"] = False
            failed_sms_log["reply_count"] = 0
            
            await db.sms_logs.insert_one(failed_sms_log)
            
            return {
                "success": False,
                "error": f"Twilio Error {e.code}: {e.msg}",
                "error_code": e.code
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending SMS: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": f"Failed to send SMS: {str(e)}"
            }
    
    async def send_bulk_sms(
        self,
        to_numbers: List[str],
        message: str,
        from_number: Optional[str] = None,
        user_id: Optional[str] = None,
        batch_size: int = 25,
        campaign_id: Optional[str] = None  # 🆕 ADD campaign tracking to bulk sends
    ) -> Dict[str, Any]:
        """
        Send bulk SMS messages
        
        🆕 SUPPORTS: Campaign tracking for bulk campaigns
        """
        
        if not self._is_configured:
            return {
                "success": False,
                "error": "SMS service not configured"
            }
        
        results = {
            "total": len(to_numbers),
            "sent": 0,
            "failed": 0,
            "errors": []
        }
        
        for to_number in to_numbers:
            result = await self.send_sms(
                to_number=to_number,
                message=message,
                from_number=from_number,
                user_id=user_id,
                campaign_id=campaign_id  # 🆕 Pass campaign_id to each SMS
            )
            
            if result.get("success"):
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "to_number": to_number,
                    "error": result.get("error")
                })
        
        return {
            "success": True,
            "results": results
        }
    
    async def get_sms_list(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        direction: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of SMS messages"""
        db = await self.get_db()
        
        query = {"user_id": user_id}
        
        if direction:
            query["direction"] = direction
        if status:
            query["status"] = status
        
        cursor = db.sms_messages.find(query).sort("created_at", -1).skip(skip).limit(limit)
        messages = await cursor.to_list(length=limit)
        
        # Format messages
        for msg in messages:
            msg["_id"] = str(msg["_id"])
        
        return messages
    
    async def get_sms_stats(self, user_id: str) -> Dict[str, int]:
        """Get SMS statistics"""
        db = await self.get_db()
        
        # Total counts
        total_sent = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "sent"
        })
        
        total_failed = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "failed"
        })
        
        total_pending = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "pending"
        })
        
        # Today's count
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sent = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "sent",
            "created_at": {"$gte": today_start}
        })
        
        # This week's count
        week_start = today_start - timedelta(days=today_start.weekday())
        week_sent = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "sent",
            "created_at": {"$gte": week_start}
        })
        
        # This month's count
        month_start = today_start.replace(day=1)
        month_sent = await db.sms_messages.count_documents({
            "user_id": user_id,
            "status": "sent",
            "created_at": {"$gte": month_start}
        })
        
        return {
            "total_sent": total_sent,
            "total_failed": total_failed,
            "total_pending": total_pending,
            "today_sent": today_sent,
            "this_week_sent": week_sent,
            "this_month_sent": month_sent
        }
    
    async def handle_incoming_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming SMS webhook from Twilio
        
        Creates entries in both sms_messages and sms_logs collections
        """
        db = await self.get_db()
        
        sms_data = {
            "to_number": data.get("To"),
            "from_number": data.get("From"),
            "message": data.get("Body"),
            "status": "received",
            "direction": "inbound",
            "twilio_sid": data.get("MessageSid"),
            "twilio_status": data.get("SmsStatus"),
            "created_at": datetime.utcnow()
        }
        
        # Store in sms_messages
        await db.sms_messages.insert_one(sms_data.copy())
        
        # Store in sms_logs
        sms_log_data = sms_data.copy()
        sms_log_data["is_reply"] = False
        sms_log_data["has_replies"] = False
        sms_log_data["reply_count"] = 0
        
        await db.sms_logs.insert_one(sms_log_data)
        
        return {
            "success": True,
            "message": "Incoming SMS processed"
        }
    
    async def delete_sms(self, sms_id: str, user_id: str) -> bool:
        """Delete SMS message"""
        db = await self.get_db()
        
        result = await db.sms_messages.delete_one({
            "_id": ObjectId(sms_id),
            "user_id": user_id
        })
        
        return result.deleted_count > 0

    # ✅ NEW METHOD: Send reminder SMS
    async def send_reminder_sms(
        self,
        to_number: str,
        customer_name: str,
        reminder_message: str,
        user_id: str,
        appointment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ NEW: Send reminder SMS
        
        Args:
            to_number: Phone number
            customer_name: Customer name
            reminder_message: Reminder message
            user_id: User ID
            appointment_id: Associated appointment ID
        
        Returns:
            Dict with success status
        """
        try:
            logger.info(f"📱 Sending reminder SMS to {customer_name}")
            
            # Format message with customer name
            full_message = f"Hi {customer_name}, {reminder_message}"
            
            # Send SMS with metadata
            result = await self.send_sms(
                to_number=to_number,
                message=full_message,
                user_id=user_id,
                metadata={
                    "type": "reminder",
                    "appointment_id": appointment_id,
                    "automated": True,
                    "customer_name": customer_name
                }
            )
            
            if result.get("success"):
                logger.info(f"✅ Reminder SMS sent successfully")
            else:
                logger.error(f"❌ Reminder SMS failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending reminder SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ✅ NEW METHOD: Send appointment reminder SMS
    async def send_appointment_reminder(
        self,
        to_number: str,
        customer_name: str,
        appointment_time: str,
        service_type: str,
        user_id: str,
        appointment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ NEW: Send appointment reminder SMS
        
        Args:
            to_number: Phone number
            customer_name: Customer name
            appointment_time: Formatted appointment time
            service_type: Type of service/appointment
            user_id: User ID
            appointment_id: Associated appointment ID
        
        Returns:
            Dict with success status
        """
        try:
            logger.info(f"📅 Sending appointment reminder to {customer_name}")
            
            # Format reminder message
            message = f"Hi {customer_name}, this is a reminder that your {service_type} appointment is scheduled for {appointment_time}. Looking forward to seeing you!"
            
            # Send SMS
            result = await self.send_sms(
                to_number=to_number,
                message=message,
                user_id=user_id,
                metadata={
                    "type": "appointment_reminder",
                    "appointment_id": appointment_id,
                    "automated": True,
                    "service_type": service_type
                }
            )
            
            if result.get("success"):
                logger.info(f"✅ Appointment reminder sent successfully")
            else:
                logger.error(f"❌ Appointment reminder failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending appointment reminder: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Create singleton instance
sms_service = SMSService()