# backend/app/services/post_call.py - POST-CALL SMS SERVICE

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from app.database import get_database
from app.services.sms import sms_service

logger = logging.getLogger(__name__)


class PostCallService:
    """Service to handle post-call actions like SMS"""
    
    async def send_post_call_sms(
        self,
        call_id: str,
        to_number: str,
        call_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send SMS after call completion
        
        Args:
            call_id: Call ID
            to_number: Customer phone number
            call_summary: Optional call summary
            
        Returns:
            Dict with success status
        """
        try:
            logger.info(f"📱 Preparing post-call SMS for {to_number}")
            
            # Get call details
            db = await get_database()
            call = await db.calls.find_one({"_id": ObjectId(call_id)})
            
            if not call:
                logger.error(f"❌ Call not found: {call_id}")
                return {"success": False, "error": "Call not found"}
            
            # Build SMS message
            if call_summary:
                message = f"Thank you for your call! Summary: {call_summary}\n\nIf you need further assistance, please call us back. Have a great day!"
            else:
                message = "Thank you for calling! We appreciate your business. If you need any further assistance, please don't hesitate to contact us. Have a great day!"
            
            # Send SMS
            logger.info(f"📤 Sending post-call SMS...")
            result = await sms_service.send_sms(
                to_number=to_number,
                message=message,
                metadata={"call_id": call_id, "type": "post_call"}
            )
            
            if result.get("success"):
                logger.info(f"✅ Post-call SMS sent successfully to {to_number}")
                return {"success": True, "message_sid": result.get("twilio_sid")}
            else:
                logger.error(f"❌ Failed to send post-call SMS: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
            
        except Exception as e:
            logger.error(f"❌ Error sending post-call SMS: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}


# Create singleton instance
post_call_service = PostCallService()