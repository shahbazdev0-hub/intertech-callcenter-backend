# backend/app/tasks/sms_tasks.py

import asyncio
from typing import List

from app.tasks.celery import celery_app
from app.services.sms import sms_service


@celery_app.task(name="app.tasks.sms_tasks.send_sms_task")
def send_sms_task(to_number: str, message: str, user_id: str, metadata: dict = None):
    """
    Send SMS message (Celery task)
    
    Args:
        to_number: Recipient phone number
        message: SMS message
        user_id: User ID
        metadata: Additional metadata
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sms_service.send_sms(
                to_number=to_number,
                message=message,
                user_id=user_id,
                metadata=metadata or {}
            )
        )
        
        return {
            "success": True,
            "to_number": to_number,
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "to_number": to_number,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.sms_tasks.send_bulk_sms_task")
def send_bulk_sms_task(to_numbers: List[str], message: str, user_id: str, campaign_id: str = None):
    """
    Send bulk SMS messages (Celery task)
    
    Args:
        to_numbers: List of recipient phone numbers
        message: SMS message
        user_id: User ID
        campaign_id: Campaign ID (optional)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sms_service.send_bulk_sms(
                to_numbers=to_numbers,
                message=message,
                user_id=user_id,
                campaign_id=campaign_id
            )
        )
        
        return {
            "success": True,
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.sms_tasks.send_scheduled_sms")
def send_scheduled_sms(to_number: str, message: str, user_id: str, delay_seconds: int = 0):
    """
    Send scheduled SMS with delay
    
    Args:
        to_number: Recipient phone number
        message: SMS message
        user_id: User ID
        delay_seconds: Delay before sending (seconds)
    """
    import time
    
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    
    return send_sms_task(to_number, message, user_id)