# backend/app/services/campaign_scheduler.py - ✅ AUTOMATED CAMPAIGN SCHEDULER

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import asyncio
import pytz

from app.database import get_database
from .communication_handler import communication_handler
from .twilio import twilio_service
from .sms import sms_service
from .email_automation import email_automation_service

logger = logging.getLogger(__name__)

# Canada Eastern Time (Toronto)
CANADA_TZ = pytz.timezone('America/Toronto')
SCHEDULED_HOUR = 10  # 10 AM
SCHEDULED_MINUTE = 0


class CampaignScheduler:
    """
    Automated Campaign Scheduler
    
    Runs campaigns automatically based on agent settings:
    - Contact Frequency (days)
    - Enabled Channels (Calls, Email, SMS)
    - Executes at 10 AM Canada time
    """
    
    def __init__(self):
        self.communication_handler = communication_handler
    
    
    async def check_and_execute_campaigns(self):
        """
        Main scheduler function - called every hour by Celery
        
        Process:
        1. Check if current time is 10 AM Canada time
        2. Find all active agents
        3. For each agent, check if campaign should run today
        4. Execute campaigns for eligible agents
        """
        try:
            # Get current time in Canada timezone
            now_canada = datetime.now(CANADA_TZ)
            current_hour = now_canada.hour
            current_minute = now_canada.minute
            
            logger.info(f"⏰ Campaign scheduler running at {now_canada.strftime('%Y-%m-%d %H:%M %Z')}")
            
            # Only run at 10 AM (allow 10:00 - 10:59)
            if current_hour != SCHEDULED_HOUR:
                logger.info(f"⏭️ Not campaign time (current: {current_hour}:00, scheduled: {SCHEDULED_HOUR}:00)")
                return
            
            # Get database
            db = await get_database()
            
            # Find all active agents with enabled communication channels
            agents = await db.voice_agents.find({
                "is_active": True,
                "$or": [
                    {"enable_calls": True},
                    {"enable_emails": True},
                    {"enable_sms": True}
                ]
            }).to_list(length=None)
            
            logger.info(f"📋 Found {len(agents)} active agents with enabled channels")
            
            # Process each agent
            for agent in agents:
                try:
                    await self._process_agent_campaign(agent, now_canada, db)
                except Exception as e:
                    logger.error(f"❌ Error processing agent {agent['_id']}: {e}")
                    continue
            
            logger.info(f"✅ Campaign scheduler completed")
            
        except Exception as e:
            logger.error(f"❌ Campaign scheduler error: {e}", exc_info=True)
    
    
    async def _process_agent_campaign(
        self,
        agent: Dict[str, Any],
        current_time: datetime,
        db: AsyncIOMotorDatabase
    ):
        """
        Process campaign for a single agent
        
        Checks if campaign should run today based on last execution
        """
        agent_id = str(agent["_id"])
        agent_name = agent.get("name", "Unknown")
        contact_frequency = agent.get("contact_frequency", 3)
        
        logger.info(f"🔍 Checking agent '{agent_name}' (ID: {agent_id})")
        
        # Get last campaign execution
        last_campaign = await db.campaign_history.find_one(
            {"agent_id": agent_id},
            sort=[("executed_at", -1)]
        )
        
        should_execute = False
        
        if not last_campaign:
            # First time - execute immediately
            logger.info(f"✅ First campaign for agent '{agent_name}'")
            should_execute = True
        else:
            # Check if enough days have passed
            last_executed = last_campaign.get("executed_at")
            if last_executed:
                days_since_last = (current_time.date() - last_executed.date()).days
                
                if days_since_last >= contact_frequency:
                    logger.info(f"✅ Agent '{agent_name}' - {days_since_last} days since last campaign (frequency: {contact_frequency} days)")
                    should_execute = True
                else:
                    logger.info(f"⏭️ Agent '{agent_name}' - only {days_since_last} days since last campaign (need {contact_frequency} days)")
        
        if should_execute:
            await self._execute_agent_campaign(agent, current_time, db)
    
    
    async def _execute_agent_campaign(
        self,
        agent: Dict[str, Any],
        execution_time: datetime,
        db: AsyncIOMotorDatabase
    ):
        """
        Execute campaign for an agent
        
        Sends calls/emails/SMS to all contacts based on enabled channels
        """
        agent_id = str(agent["_id"])
        agent_name = agent.get("name", "Unknown")
        user_id = agent.get("user_id")
        
        logger.info(f"🚀 EXECUTING CAMPAIGN: {agent_name}")
        
        # Get contacts
        contacts = agent.get("contacts", [])
        if not contacts:
            logger.warning(f"⚠️ No contacts for agent '{agent_name}'")
            return
        
        logger.info(f"📞 Processing {len(contacts)} contacts")
        
        # Get enabled channels
        enable_calls = agent.get("enable_calls", True)
        enable_emails = agent.get("enable_emails", False)
        enable_sms = agent.get("enable_sms", False)
        
        email_template = agent.get("email_template", "")
        sms_template = agent.get("sms_template", "")
        
        # Results tracking
        results = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "executed_at": execution_time,
            "total_contacts": len(contacts),
            "calls_attempted": 0,
            "calls_success": 0,
            "emails_sent": 0,
            "emails_failed": 0,
            "sms_sent": 0,
            "sms_failed": 0,
            "contact_results": []
        }
        
        # ✅ PARALLEL EXECUTION - All contacts at same time
        tasks = []
        for contact in contacts:
            task = self._process_contact(
                contact=contact,
                agent=agent,
                user_id=user_id,
                enable_calls=enable_calls,
                enable_emails=enable_emails,
                enable_sms=enable_sms,
                email_template=email_template,
                sms_template=sms_template,
                db=db
            )
            tasks.append(task)
        
        # Execute all in parallel
        contact_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for idx, contact_result in enumerate(contact_results):
            if isinstance(contact_result, Exception):
                logger.error(f"❌ Contact {idx} error: {contact_result}")
                results["contact_results"].append({
                    "contact": contacts[idx].get("name", "Unknown"),
                    "error": str(contact_result)
                })
            else:
                results["contact_results"].append(contact_result)
                
                # Update counters
                if contact_result.get("call_attempted"):
                    results["calls_attempted"] += 1
                    if contact_result.get("call_success"):
                        results["calls_success"] += 1
                
                if contact_result.get("email_sent"):
                    results["emails_sent"] += 1
                if contact_result.get("email_failed"):
                    results["emails_failed"] += 1
                
                if contact_result.get("sms_sent"):
                    results["sms_sent"] += 1
                if contact_result.get("sms_failed"):
                    results["sms_failed"] += 1
        
        # Save campaign history
        await db.campaign_history.insert_one({
            "agent_id": agent_id,
            "user_id": user_id,
            "executed_at": execution_time,
            "results": results,
            "created_at": datetime.utcnow()
        })
        
        logger.info(f"✅ CAMPAIGN COMPLETED: {agent_name}")
        logger.info(f"   Calls: {results['calls_success']}/{results['calls_attempted']}")
        logger.info(f"   Emails: {results['emails_sent']} sent, {results['emails_failed']} failed")
        logger.info(f"   SMS: {results['sms_sent']} sent, {results['sms_failed']} failed")
    
    
    async def _process_contact(
        self,
        contact: Dict[str, str],
        agent: Dict[str, Any],
        user_id: str,
        enable_calls: bool,
        enable_emails: bool,
        enable_sms: bool,
        email_template: str,
        sms_template: str,
        db: AsyncIOMotorDatabase
    ) -> Dict[str, Any]:
        """
        Process a single contact - execute all enabled channels
        """
        contact_name = contact.get("name", "Unknown")
        contact_phone = contact.get("phone", "")
        contact_email = contact.get("email", "")
        
        result = {
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "call_attempted": False,
            "call_success": False,
            "email_sent": False,
            "email_failed": False,
            "sms_sent": False,
            "sms_failed": False,
            "actions": []
        }
        
        # ✅ CHANNEL 1: Voice Calls
        if enable_calls and contact_phone:
            try:
                logger.info(f"📞 Calling {contact_name} at {contact_phone}")
                result["call_attempted"] = True
                
                # Make outbound call
                call_result = await self._make_call(
                    phone_number=contact_phone,
                    agent_id=str(agent["_id"]),
                    user_id=user_id,
                    db=db
                )
                
                if call_result.get("success"):
                    result["call_success"] = True
                    result["actions"].append("Call initiated")
                else:
                    result["actions"].append(f"Call failed: {call_result.get('error')}")
                
                # Retry if failed
                if not call_result.get("success"):
                    logger.info(f"🔁 Retrying call for {contact_name}...")
                    await asyncio.sleep(60)  # Wait 1 minute
                    retry_result = await self._make_call(
                        phone_number=contact_phone,
                        agent_id=str(agent["_id"]),
                        user_id=user_id,
                        db=db
                    )
                    if retry_result.get("success"):
                        result["call_success"] = True
                        result["actions"].append("Call succeeded on retry")
                
            except Exception as e:
                logger.error(f"❌ Call error for {contact_name}: {e}")
                result["actions"].append(f"Call error: {str(e)}")
        
        # ✅ CHANNEL 2: Email
        if enable_emails and contact_email:
            try:
                logger.info(f"📧 Sending email to {contact_name} at {contact_email}")
                
                # Replace variables in template
                email_content = email_template.replace("{name}", contact_name)
                email_content = email_content.replace("{date}", datetime.now().strftime("%B %d, %Y"))
                
                # Send email
                email_result = await email_automation_service.send_email(
                    to_email=contact_email,
                    subject=f"Message from {agent.get('name', 'Our Team')}",
                    html_content=f"<p>Hi {contact_name},</p><p>{email_content}</p>",
                    text_content=f"Hi {contact_name},\n\n{email_content}",
                    user_id=user_id,
                    recipient_name=contact_name,
                    recipient_phone=contact_phone
                )
                
                if email_result:
                    result["email_sent"] = True
                    result["actions"].append("Email sent")
                else:
                    result["email_failed"] = True
                    result["actions"].append("Email failed")
                    
                    # Retry if failed
                    logger.info(f"🔁 Retrying email for {contact_name}...")
                    await asyncio.sleep(30)
                    retry_result = await email_automation_service.send_email(
                        to_email=contact_email,
                        subject=f"Message from {agent.get('name', 'Our Team')}",
                        html_content=f"<p>Hi {contact_name},</p><p>{email_content}</p>",
                        text_content=f"Hi {contact_name},\n\n{email_content}",
                        user_id=user_id,
                        recipient_name=contact_name,
                        recipient_phone=contact_phone
                    )
                    if retry_result:
                        result["email_sent"] = True
                        result["email_failed"] = False
                        result["actions"].append("Email succeeded on retry")
                
            except Exception as e:
                logger.error(f"❌ Email error for {contact_name}: {e}")
                result["email_failed"] = True
                result["actions"].append(f"Email error: {str(e)}")
        
        # ✅ CHANNEL 3: SMS
        if enable_sms and contact_phone:
            try:
                logger.info(f"💬 Sending SMS to {contact_name} at {contact_phone}")
                
                # Replace variables in template
                sms_content = sms_template.replace("{name}", contact_name)
                sms_content = sms_content.replace("{date}", datetime.now().strftime("%B %d, %Y"))
                
                # Send SMS
                sms_result = await sms_service.send_sms(
                    to_number=contact_phone,
                    message=sms_content,
                    user_id=user_id
                )
                
                if sms_result.get("success"):
                    result["sms_sent"] = True
                    result["actions"].append("SMS sent")
                else:
                    result["sms_failed"] = True
                    result["actions"].append("SMS failed")
                    
                    # Retry if failed
                    logger.info(f"🔁 Retrying SMS for {contact_name}...")
                    await asyncio.sleep(30)
                    retry_result = await sms_service.send_sms(
                        to_number=contact_phone,
                        message=sms_content,
                        user_id=user_id
                    )
                    if retry_result.get("success"):
                        result["sms_sent"] = True
                        result["sms_failed"] = False
                        result["actions"].append("SMS succeeded on retry")
                
            except Exception as e:
                logger.error(f"❌ SMS error for {contact_name}: {e}")
                result["sms_failed"] = True
                result["actions"].append(f"SMS error: {str(e)}")
        
        return result
    
    
    async def _make_call(
        self,
        phone_number: str,
        agent_id: str,
        user_id: str,
        db: AsyncIOMotorDatabase
    ) -> Dict[str, Any]:
        """Make outbound call using Twilio"""
        try:
            from .call_handler import CallHandlerService
            
            call_handler = CallHandlerService()
            
            # Initiate call
            result = await call_handler.initiate_outbound_call(
                to_number=phone_number,
                agent_id=agent_id,
                user_id=user_id,
                db=db
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error making call: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
campaign_scheduler = CampaignScheduler()