# backend/app/tasks/automation_tasks.py

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from app.tasks.celery import celery_app
from app.services.automation import automation_service
from app.database import get_database


@celery_app.task(name="app.tasks.automation_tasks.trigger_automation_task")
def trigger_automation_task(automation_id: str, trigger_data: Dict[str, Any]):
    """
    Trigger automation execution (Celery task)
    
    Args:
        automation_id: Automation ID
        trigger_data: Trigger event data
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            automation_service.trigger_automation(automation_id, trigger_data)
        )
        
        return {
            "success": True,
            "automation_id": automation_id,
            "result": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "automation_id": automation_id,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.automation_tasks.process_call_completed")
def process_call_completed(call_data: Dict[str, Any]):
    """
    Process call completed event and trigger automations
    
    Args:
        call_data: Call completion data
    """
    try:
        async def _process():
            # Find automations with call_completed trigger
            automations = await automation_service.find_automations_by_trigger(
                trigger_type="call_completed",
                user_id=call_data.get("user_id")
            )
            
            # Trigger each automation
            for automation in automations:
                trigger_automation_task.delay(
                    automation["_id"],
                    call_data
                )
            
            return len(automations)
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        triggered = loop.run_until_complete(_process())
        
        return {
            "success": True,
            "automations_triggered": triggered
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.automation_tasks.process_demo_booked")
def process_demo_booked(demo_data: Dict[str, Any]):
    """
    Process demo booking event and trigger automations
    
    Args:
        demo_data: Demo booking data
    """
    try:
        async def _process():
            # Find automations with demo_booked trigger
            automations = await automation_service.find_automations_by_trigger(
                trigger_type="demo_booked"
            )
            
            # Trigger each automation
            for automation in automations:
                trigger_automation_task.delay(
                    automation["_id"],
                    demo_data
                )
            
            return len(automations)
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        triggered = loop.run_until_complete(_process())
        
        return {
            "success": True,
            "automations_triggered": triggered
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(name="app.tasks.automation_tasks.cleanup_old_logs")
def cleanup_old_logs():
    """
    Clean up old automation logs (runs daily via Celery Beat)
    Keeps logs for 30 days
    """
    try:
        async def _cleanup():
            db = await get_database()
            
            # Delete logs older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            result = await db.automation_logs.delete_many({
                "started_at": {"$lt": cutoff_date}
            })
            
            return result.deleted_count
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        deleted = loop.run_until_complete(_cleanup())
        
        return {
            "success": True,
            "deleted_logs": deleted
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }