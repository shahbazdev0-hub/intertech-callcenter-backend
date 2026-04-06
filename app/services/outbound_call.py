
# # # backend/app/services/outbound_call.py 

# """
# Outbound Call Service - Handles automated outbound calling
# Used by calendar monitor for follow-up calls
# """

# import logging
# from datetime import datetime
# from typing import Dict, Any, Optional
# from bson import ObjectId

# from app.database import get_database
# from app.services.twilio import twilio_service
# from app.services.call_handler import call_handler_service
# from app.config import settings

# logger = logging.getLogger(__name__)


# class OutboundCallService:
#     """
#     Outbound Call Service
    
#     Manages automated outbound calls triggered by:
#     - Calendar monitor for follow-ups
#     - Scheduled reminders
#     - Campaign automation
#     """
    
#     def __init__(self):
#         self.twilio = twilio_service
#         self.call_handler = call_handler_service
    
#     async def initiate_follow_up_call(
#         self,
#         customer_phone: str,
#         customer_name: str,
#         user_id: str,
#         agent_id: Optional[str] = None,
#         appointment_id: Optional[str] = None,
#         original_request: Optional[str] = None,
#         callback_reason: str = "follow_up"
#     ) -> Dict[str, Any]:
#         """
#         Initiate automated follow-up call
        
#         Args:
#             customer_phone: Phone number to call
#             customer_name: Customer name
#             user_id: Business owner user ID
#             agent_id: Voice agent to use
#             appointment_id: Associated appointment ID
#             original_request: Original user request (e.g., "call me in 2 hours")
#             callback_reason: Reason for callback
        
#         Returns:
#             Dict with call status and details
#         """
#         try:
#             logger.info("\n" + "="*80)
#             logger.info("📞 INITIATING AUTOMATED FOLLOW-UP CALL")
#             logger.info("="*80)
#             logger.info(f"   Customer: {customer_name}")
#             logger.info(f"   Phone: {customer_phone}")
#             logger.info(f"   Reason: {callback_reason}")
#             logger.info(f"   Original request: {original_request}")
#             logger.info("="*80 + "\n")
            
#             # Get database
#             db = await get_database()
            
#             # Get agent configuration if agent_id provided
#             agent = None
#             if agent_id and ObjectId.is_valid(agent_id):
#                 agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
            
#             # If no agent specified, try to find user's default agent
#             if not agent:
#                 agent = await db.voice_agents.find_one({
#                     "user_id": user_id,
#                     "is_active": True
#                 })
                
#                 if agent:
#                     agent_id = str(agent["_id"])
#                     logger.info(f"✅ Using default agent: {agent.get('name')}")
            
#             # Create call record
#             call_data = {
#                 "user_id": user_id,
#                 "agent_id": agent_id,
#                 "from_number": settings.TWILIO_PHONE_NUMBER,
#                 "to_number": customer_phone,
#                 "direction": "outbound",
#                 "status": "initiated",
#                 "call_type": "follow_up_call",
#                 "customer_name": customer_name,
#                 "appointment_id": appointment_id,
#                 "triggered_by": "calendar_monitor",
#                 "callback_reason": callback_reason,
#                 "original_request": original_request,
#                 "metadata": {
#                     "automated": True,
#                     "callback_type": callback_reason,
#                     "original_request": original_request
#                 },
#                 "created_at": datetime.utcnow(),
#                 "updated_at": datetime.utcnow()
#             }
            
#             call_result = await db.calls.insert_one(call_data)
#             call_id = str(call_result.inserted_id)
            
#             logger.info(f"✅ Call record created: {call_id}")
            
#             # Initiate call through Twilio directly
#             from app.services.twilio import twilio_service

#             call_response = twilio_service.make_call(
#                 to_number=customer_phone,
#                 from_number=settings.TWILIO_PHONE_NUMBER
#             )

#             # If call_response is awaitable, await it
#             if hasattr(call_response, '__await__'):
#                 call_response = await call_response
            
#             if call_response.get("success"):
#                 twilio_call_sid = call_response.get("call_sid")
                
#                 logger.info(f"✅ Twilio call initiated: {twilio_call_sid}")
                
#                 # Update call record with Twilio SID
#                 await db.calls.update_one(
#                     {"_id": ObjectId(call_id)},
#                     {
#                         "$set": {
#                             "twilio_call_sid": twilio_call_sid,
#                             "status": call_response.get("status", "ringing"),
#                             "updated_at": datetime.utcnow()
#                         }
#                     }
#                 )
                
#                 return {
#                     "success": True,
#                     "call_id": call_id,
#                     "twilio_call_sid": twilio_call_sid,
#                     "status": call_response.get("status"),
#                     "message": f"Follow-up call initiated to {customer_name}"
#                 }
            
#             else:
#                 error_msg = call_response.get("error", "Unknown error")
#                 logger.error(f"❌ Call initiation failed: {error_msg}")
                
#                 # Update call record with failure
#                 await db.calls.update_one(
#                     {"_id": ObjectId(call_id)},
#                     {
#                         "$set": {
#                             "status": "failed",
#                             "error_message": error_msg,
#                             "updated_at": datetime.utcnow()
#                         }
#                     }
#                 )
                
#                 return {
#                     "success": False,
#                     "call_id": call_id,
#                     "error": error_msg,
#                     "message": f"Failed to initiate call to {customer_name}"
#                 }
            
#         except Exception as e:
#             logger.error(f"❌ Error initiating follow-up call: {e}", exc_info=True)
#             return {
#                 "success": False,
#                 "error": str(e),
#                 "message": "Error initiating automated call"
#             }
    
#     async def initiate_reminder_call(
#         self,
#         customer_phone: str,
#         customer_name: str,
#         reminder_message: str,
#         user_id: str,
#         agent_id: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """
#         Initiate automated reminder call
        
#         Args:
#             customer_phone: Phone number to call
#             customer_name: Customer name
#             reminder_message: Message to deliver
#             user_id: Business owner user ID
#             agent_id: Voice agent to use
        
#         Returns:
#             Dict with call status
#         """
#         try:
#             logger.info(f"📞 Initiating reminder call to {customer_name}")
            
#             return await self.initiate_follow_up_call(
#                 customer_phone=customer_phone,
#                 customer_name=customer_name,
#                 user_id=user_id,
#                 agent_id=agent_id,
#                 appointment_id=None,
#                 original_request=reminder_message,
#                 callback_reason="reminder"
#             )
            
#         except Exception as e:
#             logger.error(f"❌ Error initiating reminder call: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def get_call_status(self, call_id: str) -> Dict[str, Any]:
#         """
#         Get status of outbound call
        
#         Args:
#             call_id: Call ID
        
#         Returns:
#             Dict with call status
#         """
#         try:
#             db = await get_database()
            
#             if not ObjectId.is_valid(call_id):
#                 return {
#                     "success": False,
#                     "error": "Invalid call ID"
#                 }
            
#             call = await db.calls.find_one({"_id": ObjectId(call_id)})
            
#             if not call:
#                 return {
#                     "success": False,
#                     "error": "Call not found"
#                 }
            
#             return {
#                 "success": True,
#                 "call_id": call_id,
#                 "status": call.get("status"),
#                 "duration": call.get("duration"),
#                 "started_at": call.get("started_at"),
#                 "ended_at": call.get("ended_at"),
#                 "twilio_call_sid": call.get("twilio_call_sid")
#             }
            
#         except Exception as e:
#             logger.error(f"Error getting call status: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }


# # Create singleton instance
# outbound_call_service = OutboundCallService()


























# # backend/app/services/outbound_call.py 

"""
Outbound Call Service - Handles automated outbound calling
Used by calendar monitor for follow-up calls

✅ FIXED: Call record now includes both 'call_sid' and 'twilio_call_sid' fields
✅ FIXED: Call record created AFTER Twilio call with correct call_sid
✅ FIXED: Added 'greeting_text' for personalized callback greeting
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.services.twilio import twilio_service
from app.config import settings

logger = logging.getLogger(__name__)


class OutboundCallService:
    """
    Outbound Call Service
    
    Manages automated outbound calls triggered by:
    - Calendar monitor for follow-ups
    - Scheduled reminders
    - Campaign automation
    """
    
    def __init__(self):
        self.twilio = twilio_service
    
    async def initiate_follow_up_call(
        self,
        customer_phone: str,
        customer_name: str,
        user_id: str,
        agent_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        original_request: Optional[str] = None,
        callback_reason: str = "follow_up"
    ) -> Dict[str, Any]:
        """
        Initiate automated follow-up call
        
        ✅ FIXED: Creates call record with correct fields AFTER making Twilio call
        ✅ FIXED: Includes greeting_text for personalized callback greeting
        
        Args:
            customer_phone: Phone number to call
            customer_name: Customer name
            user_id: Business owner user ID
            agent_id: Voice agent to use
            appointment_id: Associated appointment ID
            original_request: Original user request (e.g., "call me in 2 hours")
            callback_reason: Reason for callback
        
        Returns:
            Dict with call status and details
        """
        try:
            logger.info("\n" + "="*80)
            logger.info("📞 INITIATING AUTOMATED FOLLOW-UP CALL")
            logger.info("="*80)
            logger.info(f"   Customer: {customer_name}")
            logger.info(f"   Phone: {customer_phone}")
            logger.info(f"   Reason: {callback_reason}")
            logger.info(f"   Original request: {original_request}")
            logger.info(f"   Agent ID: {agent_id}")
            logger.info("="*80 + "\n")
            
            # Get database
            db = await get_database()
            
            # Get agent configuration if agent_id provided
            agent = None
            if agent_id and ObjectId.is_valid(agent_id):
                agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
                if agent:
                    logger.info(f"✅ Found agent: {agent.get('name')}")
            
            # If no agent specified, try to find user's default agent
            if not agent:
                agent = await db.voice_agents.find_one({
                    "user_id": user_id,
                    "is_active": True
                })
                
                if agent:
                    agent_id = str(agent["_id"])
                    logger.info(f"✅ Using default agent: {agent.get('name')}")
                else:
                    logger.warning("⚠️ No agent found, using system defaults")
            
            # ✅ NEW: Build personalized callback greeting
            greeting_text = self._build_callback_greeting(customer_name, original_request, agent)
            logger.info(f"📝 Callback greeting: {greeting_text[:100]}...")
            
            # ✅ STEP 1: Initiate Twilio call FIRST to get the call_sid
            logger.info("📞 Initiating Twilio call...")
            
            call_response = twilio_service.make_call(
                to_number=customer_phone,
                from_number=settings.TWILIO_PHONE_NUMBER
            )
            
            if not call_response.get("success"):
                error_msg = call_response.get("error", "Unknown error")
                logger.error(f"❌ Twilio call initiation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Failed to initiate call to {customer_name}"
                }
            
            twilio_call_sid = call_response.get("call_sid")
            logger.info(f"✅ Twilio call initiated: {twilio_call_sid}")
            
            # ✅ STEP 2: Create call record with BOTH call_sid and twilio_call_sid
            # This is CRITICAL - the webhook looks for call_sid field!
            call_data = {
                "user_id": user_id,
                "agent_id": agent_id,
                "from_number": settings.TWILIO_PHONE_NUMBER,
                "to_number": customer_phone,
                "phone_number": customer_phone,
                "direction": "outbound",
                "status": call_response.get("status", "initiated"),
                "call_type": "follow_up_call",
                "customer_name": customer_name,
                "contact_name": customer_name,
                "appointment_id": appointment_id,
                "triggered_by": "calendar_monitor",
                "callback_reason": callback_reason,
                "original_request": original_request,
                # ✅ CRITICAL: Include BOTH fields so webhook can find the record
                "call_sid": twilio_call_sid,
                "twilio_call_sid": twilio_call_sid,
                # ✅ NEW: Store greeting for the WebSocket handler to use
                "greeting_text": greeting_text,
                # ✅ Metadata for tracking
                "metadata": {
                    "automated": True,
                    "callback_type": callback_reason,
                    "original_request": original_request,
                    "is_callback": True
                },
                # ✅ Initialize counters
                "greeting_count": 0,
                "empty_speech_count": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            call_result = await db.calls.insert_one(call_data)
            call_id = str(call_result.inserted_id)
            
            logger.info(f"✅ Call record created: {call_id}")
            logger.info(f"✅ Call SID stored: {twilio_call_sid}")
            
            return {
                "success": True,
                "call_id": call_id,
                "call_sid": twilio_call_sid,
                "twilio_call_sid": twilio_call_sid,
                "status": call_response.get("status"),
                "message": f"Follow-up call initiated to {customer_name}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error initiating follow-up call: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Error initiating automated call"
            }
    
    def _build_callback_greeting(
        self,
        customer_name: str,
        original_request: Optional[str],
        agent: Optional[Dict[str, Any]]
    ) -> str:
        """
        ✅ NEW: Build a personalized greeting for callback calls
        
        This greeting will be played when the customer answers
        """
        # Get agent/company name
        agent_name = "your assistant"
        company_name = ""
        
        if agent:
            agent_context = agent.get("agent_context", {})
            if agent_context and isinstance(agent_context, dict):
                identity = agent_context.get("identity", {})
                if isinstance(identity, dict):
                    agent_name = identity.get("name", agent.get("name", "your assistant"))
                    company_name = identity.get("company", "")
            else:
                agent_name = agent.get("name", "your assistant")
        
        # Build greeting based on context
        if company_name:
            greeting = f"Hi {customer_name}! This is {agent_name} from {company_name} calling you back as you requested."
        else:
            greeting = f"Hi {customer_name}! This is {agent_name} calling you back as you requested."
        
        # Add context
        greeting += " How can I help you today?"
        
        return greeting
    
    async def initiate_reminder_call(
        self,
        customer_phone: str,
        customer_name: str,
        reminder_message: str,
        user_id: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate automated reminder call
        
        Args:
            customer_phone: Phone number to call
            customer_name: Customer name
            reminder_message: Message to deliver
            user_id: Business owner user ID
            agent_id: Voice agent to use
        
        Returns:
            Dict with call status
        """
        try:
            logger.info(f"📞 Initiating reminder call to {customer_name}")
            
            return await self.initiate_follow_up_call(
                customer_phone=customer_phone,
                customer_name=customer_name,
                user_id=user_id,
                agent_id=agent_id,
                appointment_id=None,
                original_request=reminder_message,
                callback_reason="reminder"
            )
            
        except Exception as e:
            logger.error(f"❌ Error initiating reminder call: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get status of outbound call
        
        Args:
            call_id: Call ID
        
        Returns:
            Dict with call status
        """
        try:
            db = await get_database()
            
            if not ObjectId.is_valid(call_id):
                return {
                    "success": False,
                    "error": "Invalid call ID"
                }
            
            call = await db.calls.find_one({"_id": ObjectId(call_id)})
            
            if not call:
                return {
                    "success": False,
                    "error": "Call not found"
                }
            
            return {
                "success": True,
                "call_id": call_id,
                "status": call.get("status"),
                "duration": call.get("duration"),
                "started_at": call.get("started_at"),
                "ended_at": call.get("ended_at"),
                "twilio_call_sid": call.get("twilio_call_sid")
            }
            
        except Exception as e:
            logger.error(f"Error getting call status: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Create singleton instance
outbound_call_service = OutboundCallService()
