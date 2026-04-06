# backend/app/tasks/campaign_tasks.py - CELERY SCHEDULED TASKS

import logging
from celery import shared_task
from app.services.campaign_scheduler import campaign_scheduler

logger = logging.getLogger(__name__)


@shared_task(name="run_campaign_scheduler")
def run_campaign_scheduler():
    """
    Celery task to run campaign scheduler
    
    Scheduled to run every hour
    Checks if it's 10 AM Canada time and executes campaigns
    """
    try:
        logger.info("⏰ Starting campaign scheduler task")
        
        # Run async function
        import asyncio
        asyncio.run(campaign_scheduler.check_and_execute_campaigns())
        
        logger.info("✅ Campaign scheduler task completed")
        
    except Exception as e:
        logger.error(f"❌ Campaign scheduler task error: {e}", exc_info=True)
        raise