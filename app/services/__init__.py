# # backend/app/services/__init__.py - UPDATED WITH NEW SERVICES

# """
# Services Package
# """

# from .email import email_service
# from .auth import auth_service
# from .twilio import twilio_service
# from .ai_agent import ai_agent_service
# from .elevenlabs import elevenlabs_service
# from .call_handler import CallHandlerService, get_call_handler
# from .google_calendar import google_calendar_service
# from .appointment import appointment_service
# from .workflow_engine import workflow_engine
# from .customer import customer_service
# from .rag_service import rag_service 
# from .agent_executor import agent_executor 
# from .communication_handler import communication_handler  
# from .campaign_scheduler import campaign_scheduler

# __all__ = [
#     "email_service",
#     "auth_service",
#     "twilio_service",
#     "ai_agent_service",
#     "elevenlabs_service",
#     "CallHandlerService",
#     "get_call_handler",
#     "google_calendar_service",
#     "appointment_service",
#     "workflow_engine",
#     "customer_service",
#     "rag_service",  
#     "agent_executor",  
#     "communication_handler", 
#     "campaign_scheduler",
# ] 

# backend/app/services/__init__.py - UPDATED WITH NEW SERVICES

"""
Services Package
"""
# ✅ ADD THIS AT THE VERY TOP
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)
from .email import email_service
from .auth import auth_service
from .twilio import twilio_service
from .ai_agent import ai_agent_service
from .elevenlabs import elevenlabs_service
from .call_handler import CallHandlerService, get_call_handler
from .google_calendar import google_calendar_service
from .appointment import appointment_service
from .workflow_engine import workflow_engine
from .customer import customer_service
from .rag_service import rag_service 
from .agent_executor import agent_executor 
from .communication_handler import communication_handler  
from .campaign_scheduler import campaign_scheduler
from .cache_service import cache_service
from .call_memory import call_memory_service

__all__ = [
    "email_service",
    "auth_service",
    "twilio_service",
    "ai_agent_service",
    "elevenlabs_service",
    "CallHandlerService",
    "get_call_handler",
    "google_calendar_service",
    "appointment_service",
    "workflow_engine",
    "customer_service",
    "rag_service",  
    "agent_executor",  
    "communication_handler", 
    "campaign_scheduler",
    "cache_service",
    "call_memory_service",
]