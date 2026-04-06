# backend/app/tasks/reminder_tasks.py - NEW FILE
"""
Reminder Tasks - Celery tasks for sending reminders
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.tasks.celery import celery_app
from app.services.sms import sms_service
from app.services.email import email_service
from app.services.outbound_call import outbound_call_service

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.reminder_tasks.send_sms_reminder")
def send_sms_reminder(
    to_number: str,
    customer_name: str,
    reminder_message: str,
    user_id: str,
    appointment_id: Optional[str] = None
):
    """
    Send SMS reminder (Celery task)
    
    Args:
        to_number: Phone number
        customer_name: Customer name
        reminder_message: Reminder message
        user_id: User ID
        appointment_id: Associated appointment ID
    """
    try:
        logger.info(f"📱 Sending SMS reminder to {customer_name}")
        
        # Format message
        message = f"Hi {customer_name}, {reminder_message}"
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sms_service.send_sms(
                to_number=to_number,
                message=message,
                user_id=user_id,
                metadata={
                    "type": "reminder",
                    "appointment_id": appointment_id,
                    "automated": True
                }
            )
        )
        
        if result.get("success"):
            logger.info(f"✅ SMS reminder sent to {customer_name}")
        else:
            logger.error(f"❌ SMS reminder failed: {result.get('error')}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ SMS reminder task error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.reminder_tasks.send_email_reminder")
def send_email_reminder(
    to_email: str,
    customer_name: str,
    reminder_subject: str,
    reminder_message: str,
    appointment_id: Optional[str] = None
):
    """
    Send email reminder (Celery task)
    
    Args:
        to_email: Email address
        customer_name: Customer name
        reminder_subject: Email subject
        reminder_message: Reminder message
        appointment_id: Associated appointment ID
    """
    try:
        logger.info(f"📧 Sending email reminder to {customer_name}")
        
        # Format HTML email
        html_content = f"""
        <html>
        <body>
            <h2>Reminder</h2>
            <p>Hi {customer_name},</p>
            <p>{reminder_message}</p>
            <br>
            <p>Best regards,<br>Your Team</p>
        </body>
        </html>
        """
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            email_service.send_email(
                to_email=to_email,
                subject=reminder_subject,
                html_content=html_content,
                text_content=reminder_message
            )
        )
        
        if result.get("success"):
            logger.info(f"✅ Email reminder sent to {customer_name}")
        else:
            logger.error(f"❌ Email reminder failed: {result.get('error')}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Email reminder task error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.reminder_tasks.send_call_reminder")
def send_call_reminder(
    to_number: str,
    customer_name: str,
    reminder_message: str,
    user_id: str,
    agent_id: Optional[str] = None,
    appointment_id: Optional[str] = None
):
    """
    Send call reminder (Celery task)
    
    Args:
        to_number: Phone number
        customer_name: Customer name
        reminder_message: Reminder message
        user_id: User ID
        agent_id: Voice agent ID
        appointment_id: Associated appointment ID
    """
    try:
        logger.info(f"📞 Sending call reminder to {customer_name}")
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            outbound_call_service.initiate_reminder_call(
                customer_phone=to_number,
                customer_name=customer_name,
                reminder_message=reminder_message,
                user_id=user_id,
                agent_id=agent_id
            )
        )
        
        if result.get("success"):
            logger.info(f"✅ Call reminder initiated for {customer_name}")
        else:
            logger.error(f"❌ Call reminder failed: {result.get('error')}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Call reminder task error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }