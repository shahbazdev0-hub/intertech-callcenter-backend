# backend/app/tasks/__init__.py
# ✅ ADD THIS AT THE VERY TOP
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

from app.tasks.celery import celery_app
from app.tasks.calendar_monitor_tasks import scan_calendar_events
from app.tasks.email_tasks import process_scheduled_campaigns
from app.tasks.automation_tasks import cleanup_old_logs

__all__ = [
    'celery_app',
    'scan_calendar_events',
    'process_scheduled_campaigns',
    'cleanup_old_logs',
]