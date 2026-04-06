# backend/app/tasks/email_tasks.py

from datetime import datetime
import asyncio
from typing import Dict, Any

from app.tasks.celery import celery_app
from app.services.email_automation import email_automation_service
from app.database import get_database


@celery_app.task(name="app.tasks.email_tasks.send_campaign_task")
def send_campaign_task(campaign_id: str):
    """
    Send email campaign (Celery task)
    
    Args:
        campaign_id: Campaign ID to send
    """
    try:
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            email_automation_service.send_campaign(campaign_id)
        )
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.email_tasks.send_email_task")
def send_email_task(to_email: str, subject: str, content: str):
    """
    Send single email (Celery task)
    
    Args:
        to_email: Recipient email
        subject: Email subject
        content: Email content (HTML)
    """
    try:
        from app.services.email import email_service
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            email_service.send_email(
                to_email=to_email,
                subject=subject,
                html_content=content
            )
        )
        
        return {
            "success": True,
            "to_email": to_email,
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "to_email": to_email,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.email_tasks.send_scheduled_email")
def send_scheduled_email(to_email: str, subject: str, content: str, delay_seconds: int = 0):
    """
    Send scheduled email with delay
    
    Args:
        to_email: Recipient email
        subject: Email subject
        content: Email content
        delay_seconds: Delay before sending (seconds)
    """
    import time
    
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    
    return send_email_task(to_email, subject, content)


@celery_app.task(name="app.tasks.email_tasks.process_scheduled_campaigns")
def process_scheduled_campaigns():
    """
    Process scheduled campaigns (runs every minute via Celery Beat)
    """
    try:
        async def _process():
            db = await get_database()
            
            # Find campaigns scheduled for now or earlier
            now = datetime.utcnow()
            
            campaigns = await db.email_campaigns.find({
                "status": "scheduled",
                "scheduled_at": {"$lte": now}
            }).to_list(length=100)
            
            for campaign in campaigns:
                # Trigger campaign sending
                send_campaign_task.delay(str(campaign["_id"]))
            
            return len(campaigns)
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        processed = loop.run_until_complete(_process())
        
        return {
            "success": True,
            "processed_campaigns": processed
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.email_tasks.send_bulk_emails")
def send_bulk_emails(recipients: list, subject: str, content: str, batch_size: int = 50):
    """
    Send bulk emails in batches
    
    Args:
        recipients: List of email addresses
        subject: Email subject
        content: Email content
        batch_size: Batch size for sending
    """
    results = {
        "total": len(recipients),
        "sent": 0,
        "failed": 0
    }
    
    # Send in batches
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i + batch_size]
        
        for recipient in batch:
            try:
                send_email_task.delay(recipient, subject, content)
                results["sent"] += 1
            except Exception:
                results["failed"] += 1
    
    return results