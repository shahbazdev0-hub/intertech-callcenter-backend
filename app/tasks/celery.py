# backend/app/tasks/celery.py - FIXED VERSION
# ✅ ADD THIS AT THE VERY TOP
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

import os
print(f"✅ Celery: OPENAI_API_KEY loaded: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"✅ Celery: TWILIO_ACCOUNT_SID loaded: {bool(os.getenv('TWILIO_ACCOUNT_SID'))}")
from celery import Celery
from celery.schedules import crontab
import os

# Get broker URL from environment
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Initialize Celery
celery_app = Celery(
    'callcenter',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.calendar_monitor_tasks',  # ✅ EXPLICITLY INCLUDE THIS
        'app.tasks.email_tasks',
        'app.tasks.sms_tasks',
        'app.tasks.automation_tasks',
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,  # ✅ FIX WARNING
)

# ✅ Beat schedule with calendar monitor
celery_app.conf.beat_schedule = {
    # ✅ Calendar monitor - runs every 2 minutes (CHANGED FROM 10 TO 2)
    'scan-calendar-events-every-2-minutes': {  # ✅ CHANGED FROM 10 TO 2
        'task': 'app.tasks.calendar_monitor_tasks.scan_calendar_events',
        'schedule': 120.0,  # ✅ Every 2 minutes (120 seconds) - CHANGED FROM 600.0
        'options': {
            'expires': 60,  # Expire after 1 minute if not executed - CHANGED FROM 300
        }
    },
    
    # Campaign scheduler
    'run-campaign-scheduler-every-hour': {
        'task': 'run_campaign_scheduler',
        'schedule': crontab(minute=0),
        'options': {
            'expires': 3600,
        }
    },
    
    # Process scheduled campaigns
    'process-scheduled-campaigns': {
        'task': 'app.tasks.email_tasks.process_scheduled_campaigns',
        'schedule': 60.0,
    },
    
    # Cleanup old logs
    'cleanup-old-logs': {
        'task': 'app.tasks.automation_tasks.cleanup_old_logs',
        'schedule': 86400.0,
    },
}

# ✅ IMPORTANT: This forces task discovery
celery_app.autodiscover_tasks([
    'app.tasks',
], force=True)

# Task routes
celery_app.conf.task_routes = {
    'app.tasks.calendar_monitor_tasks.*': {'queue': 'celery'},
    'run_campaign_scheduler': {'queue': 'celery'},
    'app.tasks.email_tasks.*': {'queue': 'celery'},
    'app.tasks.sms_tasks.*': {'queue': 'celery'},
    'app.tasks.automation_tasks.*': {'queue': 'celery'},
}

if __name__ == '__main__':
    celery_app.start()