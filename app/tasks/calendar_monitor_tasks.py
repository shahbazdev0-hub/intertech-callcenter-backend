# # backend/app/tasks/calendar_monitor_tasks.py 
# """
# Calendar Monitor Celery Tasks
# Scheduled background jobs for scanning calendar and triggering actions
# """

# import asyncio
# import logging
# from datetime import datetime

# from app.tasks.celery import celery_app
# from app.services.calendar_monitor import calendar_monitor_service

# logger = logging.getLogger(__name__)


# @celery_app.task(name="app.tasks.calendar_monitor_tasks.scan_calendar_events")
# def scan_calendar_events():
#     """
#     Scan Google Calendar for due events and trigger actions
    
#     Scheduled to run every 10 minutes via Celery Beat
    
#     Actions:
#     - Initiate follow-up calls
#     - Send reminders
#     - Send appointment reminders
#     """
#     try:
#         logger.info("\n" + "="*80)
#         logger.info("⏰ CELERY TASK: Calendar Monitor Scan Starting")
#         logger.info(f"   Time: {datetime.utcnow()}")
#         logger.info("="*80 + "\n")
        
#         # Run async function in sync context
#         loop = asyncio.get_event_loop()
#         if loop.is_closed():
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
        
#         result = loop.run_until_complete(
#             calendar_monitor_service.scan_and_process_events()
#         )
        
#         logger.info("\n" + "="*80)
#         logger.info("✅ CELERY TASK: Calendar Monitor Scan Complete")
#         logger.info(f"   Result: {result.get('success')}")
#         logger.info(f"   Follow-up calls: {result.get('follow_up_calls', 0)}")
#         logger.info(f"   Reminders: {result.get('reminders_sent', 0)}")
#         logger.info(f"   Appointment reminders: {result.get('appointment_reminders', 0)}")
#         logger.info("="*80 + "\n")
        
#         return result
    
#     except Exception as e:
#         logger.error(f"❌ Calendar monitor task error: {e}", exc_info=True)
#         return {
#             "success": False,
#             "error": str(e)
#         } 

# backend/app/tasks/calendar_monitor_tasks.py 
"""
Calendar Monitor Celery Tasks
Scheduled background jobs for scanning calendar and triggering actions
"""

import asyncio
import logging
from datetime import datetime

from app.tasks.celery import celery_app
from app.services.calendar_monitor import calendar_monitor_service

logger = logging.getLogger(__name__)


def get_or_create_event_loop():
    """Get existing event loop or create a new one (Windows compatible)"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        # No event loop in current thread (common on Windows with Celery)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


@celery_app.task(name="app.tasks.calendar_monitor_tasks.scan_calendar_events")
def scan_calendar_events():
    """
    Scan Google Calendar for due events and trigger actions
    
    Scheduled to run every 2 minutes via Celery Beat
    
    Actions:
    - Initiate follow-up calls
    - Send reminders
    - Send appointment reminders
    """
    try:
        logger.info("\n" + "="*80)
        logger.info("⏰ CELERY TASK: Calendar Monitor Scan Starting")
        logger.info(f"   Time: {datetime.utcnow()}")
        logger.info("="*80 + "\n")
        
        # ✅ FIXED: Use Windows-compatible event loop handling
        loop = get_or_create_event_loop()
        
        result = loop.run_until_complete(
            calendar_monitor_service.scan_and_process_events()
        )
        
        logger.info("\n" + "="*80)
        logger.info("✅ CELERY TASK: Calendar Monitor Scan Complete")
        logger.info(f"   Result: {result.get('success')}")
        logger.info(f"   Follow-up calls: {result.get('follow_up_calls', 0)}")
        logger.info(f"   Reminders: {result.get('reminders_sent', 0)}")
        logger.info(f"   Appointment reminders: {result.get('appointment_reminders', 0)}")
        logger.info("="*80 + "\n")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Calendar monitor task error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
