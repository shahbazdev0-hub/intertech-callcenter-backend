# backend/main.py
# ============================================
# FORCE LOAD ENVIRONMENT VARIABLES FIRST
# ============================================
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Depends, WebSocket
# Load .env file with override to ensure fresh values
load_dotenv(override=True)

# ============================================
# NOW IMPORT FASTAPI AND OTHER MODULES
# ============================================
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection

# Milestone 1 imports
from app.api.v1 import auth, users, admin, demo

# Milestone 2 imports
from app.api.v1 import calls, agents, conversations, analytics
from app.api.v1.voice import router as voice_router

# Milestone 3 imports
from app.api.v1 import sms, email, automation, workflows
from app.api.v1.flows import router as flows_router

# Appointments import
from app.api.v1 import appointments

# ✅ SMS & Email Logs imports
from app.api.v1 import sms_logs, email_logs

# ✅ SMS Chat import
from app.api.v1 import sms_chat

# 🆕 SMS Campaigns import
from app.api.v1 import sms_campaigns

# 🆕 Email Campaigns import
from app.api.v1 import email_campaigns

# ✅ CRM & API Keys imports
from app.api.v1 import customers, api_keys
from app.api.public.v1 import customers as public_customers

# ✅ Email Webhook import
from app.api.v1 import email_webhook

# ✅ Payments (Stripe) import
from app.api.v1 import payments

# ✅ Call Payment Details (voice-collected card details) import
from app.api.v1 import call_payments

# ✅ Phone Numbers import
from app.api.v1 import phone_numbers

# Integration (multi-tenant Twilio + Email)
from app.api.v1 import integration
from app.api.v1 import business_profile
from app.api.v1 import estimates_invoices
from app.api.v1 import service_customers
from app.api.v1 import technicians
from app.api.v1 import jobs
from app.api.v1 import customer_conversations

# Import authentication dependency
from app.api.v1.auth import get_current_user

import logging

logger = logging.getLogger(__name__)

from app.services.openai import openai_service
from app.services.email_poller import email_poller_service
from app.services.appointment_reminder import appointment_reminder_service
print(f"🤖 AI Service initialized - Provider: {openai_service.provider}, Model: {openai_service.model if openai_service.configured else 'NOT CONFIGURED'}")
# ============================================
# LIFESPAN CONTEXT MANAGER
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    # Startup
    logger.info("=" * 80)
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("=" * 80)
    
    logger.info("📊 Connecting to MongoDB...")
    await connect_to_mongo()
    logger.info("✅ MongoDB connected successfully!")
    
    # ⭐ NEW: Create static audio directory for ElevenLabs
    audio_dir = Path("static/audio/generated")
    audio_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"🎵 Audio directory ready: {audio_dir}")
    
    # ⭐ NEW: Create uploads directory for RAG documents
    uploads_dir = Path("uploads/agent_documents")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📄 Uploads directory ready: {uploads_dir}")

    # Start Email IMAP Poller (for auto-replying to inbound emails)
    import asyncio
    email_poller_task = None
    if os.getenv("EMAIL_IMAP_POLLING_ENABLED", "false").lower() == "true":
        if email_poller_service.is_configured():
            email_poller_task = asyncio.create_task(email_poller_service.start_polling())
            logger.info("📧 Email IMAP Poller started!")
        else:
            logger.warning("Email IMAP polling enabled but EMAIL_USER/PASSWORD not configured")
    else:
        logger.info("📧 Email IMAP Polling disabled (set EMAIL_IMAP_POLLING_ENABLED=true to enable)")

    # Start Appointment Reminder Service (sends email 30 min before appointments)
    reminder_task = asyncio.create_task(appointment_reminder_service.start())
    logger.info("⏰ Appointment Reminder Service started!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down CallCenter SaaS API...")

    # Stop email poller
    if email_poller_task:
        email_poller_service.stop_polling()
        email_poller_task.cancel()
        logger.info("📧 Email poller stopped")

    # Stop appointment reminder
    appointment_reminder_service.stop()
    reminder_task.cancel()
    logger.info("⏰ Appointment reminder stopped")

    logger.info("📊 Closing MongoDB connection...")
    await close_mongo_connection()
    logger.info("✅ Cleanup completed!")


# ============================================
# CREATE FASTAPI APP
# ============================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Call Center SaaS Platform with CRM & Public API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# ============================================
# CORS MIDDLEWARE
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/api/v1/voice/ws/test-direct")
async def test_direct_websocket(websocket: WebSocket):
    print("🔌 DIRECT WEBSOCKET HIT!")
    await websocket.accept()
    await websocket.send_text("Direct WebSocket works!")
    await websocket.close()

# ============================================
# MEDIA STREAM WEBSOCKET - Registered directly on app
# (Router-level @router.websocket may not register correctly)
# ============================================
@app.websocket("/api/v1/voice/ws/media-stream")
async def media_stream_ws(websocket: WebSocket):
    """Forward to the actual handler in voice.py"""
    print("🟢 MEDIA-STREAM WEBSOCKET HIT (from main.py)!")
    from app.api.v1.voice import media_stream_websocket
    await media_stream_websocket(websocket)
# ============================================
# STATIC FILES (For ElevenLabs audio)
# ============================================
static_dir = Path("static")
static_dir.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# ⭐ NEW: Mount uploads directory (optional - for direct file access)
# Note: This is optional since we're serving files through API endpoints
uploads_dir = Path("uploads")
if uploads_dir.exists():
    app.mount(
        "/uploads",
        StaticFiles(directory="uploads"),
        name="uploads"
    )


# ============================================
# INCLUDE ROUTERS - MILESTONE 1
# ============================================
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"]
)

app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["Admin"]
)

app.include_router(
    demo.router,
    prefix="/api/v1/demo",
    tags=["Demo Bookings"]
)


# ============================================
# INCLUDE ROUTERS - MILESTONE 2
# ============================================
app.include_router(
    voice_router,
    prefix="/api/v1/voice",
    tags=["Voice & AI Agents"]
)

app.include_router(
    calls.router,
    prefix="/api/v1/calls",
    tags=["Calls"]
)

app.include_router(
    agents.router,
    prefix="/api/v1/agents", 
    tags=["AI Agents"]
)

app.include_router(
    conversations.router, 
    prefix="/api/v1/conversations", 
    tags=["Conversations"]
)

app.include_router(
    analytics.router, 
    prefix="/api/v1/analytics", 
    tags=["Analytics"]
)


# ============================================
# INCLUDE ROUTERS - MILESTONE 3
# ============================================
app.include_router(
    sms.router, 
    prefix="/api/v1/sms", 
    tags=["SMS"]
)

app.include_router(
    email.router, 
    prefix="/api/v1/email", 
    tags=["Email"]
)

app.include_router(
    automation.router, 
    prefix="/api/v1/automation", 
    tags=["Automation"]
)

app.include_router(
    workflows.router, 
    prefix="/api/v1/workflows", 
    tags=["Workflows"]
)

app.include_router(
    flows_router, 
    prefix="/api/v1/flows", 
    tags=["AI Campaign Flows"]
)


# ============================================
# INCLUDE ROUTERS - APPOINTMENTS
# ============================================
app.include_router(
    appointments.router,
    prefix="/api/v1/appointments",
    tags=["Appointments"],
    dependencies=[Depends(get_current_user)]
)


# ============================================
# ✅ SMS & EMAIL LOGS ROUTERS
# ============================================
app.include_router(
    sms_logs.router,
    prefix="/api/v1/sms-logs",
    tags=["SMS Logs"]
)

app.include_router(
    email_logs.router,
    prefix="/api/v1/email-logs",
    tags=["Email Logs"]
)


# ============================================
# ✅ SMS CHAT ROUTER
# ============================================
app.include_router(
    sms_chat.router,
    prefix="/api/v1/sms-logs",
    tags=["SMS Chat"]
)


# ============================================
# 🆕 SMS CAMPAIGNS ROUTER
# ============================================
app.include_router(
    sms_campaigns.router,
    prefix="/api/v1/sms-campaigns",
    tags=["SMS Campaigns"]
)


# ============================================
# 🆕 EMAIL CAMPAIGNS ROUTER
# ============================================
app.include_router(
    email_campaigns.router,
    prefix="/api/v1/email-campaigns",
    tags=["Email Campaigns"]
)


# ============================================
# ✅ CUSTOMERS (CRM) ROUTER
# ============================================
app.include_router(
    customers.router,
    prefix="/api/v1/customers",
    tags=["Customers"]
)


# ============================================
# ✅ API KEYS ROUTER
# ============================================
app.include_router(
    api_keys.router,
    prefix="/api/v1/api-keys",
    tags=["API Keys"]
)


# ============================================
# ✅ PUBLIC API ROUTER
# ============================================
app.include_router(
    public_customers.router,
    prefix="/api/public/v1",
    tags=["Public API"]
)


# ============================================
# ✅ EMAIL WEBHOOK ROUTER
# ============================================
app.include_router(
    email_webhook.router,
    prefix="/api/v1/email-webhook",
    tags=["Email Webhook"]
)


# ============================================
# ✅ PAYMENTS (STRIPE) ROUTER
# ============================================
app.include_router(
    payments.router,
    prefix="/api/v1/payments",
    tags=["Payments"]
)


# ============================================
# ✅ CALL PAYMENT DETAILS ROUTER
# ============================================
app.include_router(
    call_payments.router,
    prefix="/api/v1/call-payments",
    tags=["Call Payment Details"],
)


# ============================================
# ✅ PHONE NUMBERS ROUTER
# ============================================
app.include_router(
    phone_numbers.router,
    prefix="/api/v1/phone-numbers",
    tags=["Phone Numbers"]
)

app.include_router(
    integration.router,
    prefix="/api/v1/integration",
    tags=["Integration"]
)

app.include_router(
    business_profile.router,
    prefix="/api/v1/business-profile",
    tags=["Business Profile"]
)

app.include_router(
    estimates_invoices.router,
    prefix="/api/v1/estimates-invoices",
    tags=["Estimates & Invoices"]
)

app.include_router(
    service_customers.router,
    prefix="/api/v1/service-customers",
    tags=["Service Customers"]
)

app.include_router(
    technicians.router,
    prefix="/api/v1/technicians",
    tags=["Technicians"]
)

app.include_router(
    jobs.router,
    prefix="/api/v1/jobs",
    tags=["Jobs"]
)

app.include_router(
    customer_conversations.router,
    prefix="/api/v1/customer-conversations",
    tags=["Customer Conversations"]
)


# ============================================
# ROOT & HEALTH CHECK ENDPOINTS
# ============================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "features": {
            "milestone_1": "✅ Authentication & User Management",
            "milestone_2": "✅ Voice AI & Call Center",
            "milestone_3": "✅ SMS, Email & Automation",
            "milestone_4": "✅ CRM & Customer Management",
            "appointments": "✅ Appointment Booking with Google Calendar",
            "communication_logs": "✅ SMS & Email Logs with Reply Functionality",
            "sms_chat": "✅ AI-Powered SMS Chat Interface",
            "sms_campaigns": "✅ Bulk SMS Campaigns with Reply Tracking",
            "public_api": "✅ Public API with API Key Authentication",
            "email_webhook": "✅ Email Webhook for Reply Handling",
            # ⭐ NEW FEATURES
            "bulk_calling": "✅ Bulk Voice Campaign Execution",
            "rag_training": "✅ RAG Document Training for AI Agents",
            "multi_agent": "✅ Multiple Independent AI Agents",
            "4step_executor": "✅ Intelligent 4-Step Response Priority"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint with service status"""
    from app.services.twilio import twilio_service
    from app.services.ai_agent import ai_agent_service
    from app.services.google_calendar import google_calendar_service
    from app.services.rag_service import rag_service  # ⭐ NEW
    
    elevenlabs_configured = bool(os.getenv("ELEVENLABS_API_KEY"))
    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    
    # ⭐ NEW: Check uploads directory
    uploads_dir_exists = Path("uploads/agent_documents").exists()
    
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "twilio": "configured" if twilio_service.is_configured() else "not_configured",
            "openai": "configured" if openai_configured else "not_configured",
            "elevenlabs": "configured" if elevenlabs_configured else "not_configured",
            "google_calendar": "configured" if google_calendar_service.is_configured() else "not_configured",
            # ⭐ NEW
            "rag_service": "ready" if openai_configured else "openai_key_required",
            "uploads_directory": "ready" if uploads_dir_exists else "not_created"
        },
        "features": {
            "authentication": True,
            "voice_calls": True,
            "ai_agents": True,
            "campaign_builder": True,
            "workflows": True,
            "sms": True,
            "email": True,
            "automation": True,
            "appointments": True,
            "sms_logs": True,
            "email_logs": True,
            "sms_chat": True,
            "sms_campaigns": True,
            "customers": True,
            "api_keys": True,
            "public_api": True,
            "email_webhook": True
        }
    }


# ============================================
# STARTUP EVENT
# ============================================

@app.on_event("startup")
async def startup_info():
    """Log startup information"""
    from app.services.twilio import twilio_service
    from app.services.ai_agent import ai_agent_service
    from app.services.sms import sms_service
    from app.services.google_calendar import google_calendar_service
    
    logger.info("=" * 80)
    logger.info("📍 API ENDPOINTS:")
    logger.info(f"📖 Docs: http://localhost:8000/docs")
    logger.info(f"📚 ReDoc: http://localhost:8000/redoc")
    logger.info(f"❤️  Health: http://localhost:8000/health")
    logger.info(f"🎵 Static Audio: http://localhost:8000/static/audio/")
    logger.info(f"📄 Uploads: http://localhost:8000/uploads/")  # ⭐ NEW
    logger.info(f"🔗 API Base URL: http://localhost:8000/api/v1")
    logger.info(f"🌐 Public API URL: http://localhost:8000/api/public/v1")
    logger.info(f"📧 Email Webhook URL: http://localhost:8000/api/v1/email-webhook")
    logger.info(f"📅 Appointments API: http://localhost:8000/api/v1/appointments")
    logger.info("=" * 80)
    logger.info("📦 IMPLEMENTED MILESTONES:")
    logger.info("   ✅ MILESTONE 1: Authentication & User Management")
    logger.info("   ✅ MILESTONE 2: Voice AI & Call Center")
    logger.info("   ✅ MILESTONE 3: SMS, Email & Automation")
    logger.info("   ✅ MILESTONE 4: CRM & Customer Management")
    logger.info("   ✅ FEATURE: AI Campaign Builder Integration")
    logger.info("   ✅ FEATURE: ElevenLabs Voice in Live Calls")
    logger.info("   ✅ FEATURE: Appointment Booking with Google Calendar")
    logger.info("   ✅ FEATURE: SMS & Email Logs with Reply Functionality")
    logger.info("   ✅ FEATURE: AI-Powered SMS Chat Interface")
    logger.info("   ✅ FEATURE: Bulk SMS Campaigns with Reply Tracking")
    logger.info("   ✅ FEATURE: Public API with API Key Authentication")
    logger.info("   ✅ FEATURE: Email Webhook for Reply Handling")
    # ⭐ NEW FEATURES
    logger.info("   ✅ FEATURE: Bulk Voice Campaign Execution")
    logger.info("   ✅ FEATURE: RAG Document Training (AI Knowledge Base)")
    logger.info("   ✅ FEATURE: Multiple Independent AI Agents")
    logger.info("   ✅ FEATURE: 4-Step Intelligent Response Priority")
    logger.info("=" * 80)
    
    logger.info("📌 Service Status:")
    logger.info(f"   Twilio: {'✅ Configured' if twilio_service.is_configured() else '⚠️ Not Configured'}")
    logger.info(f"   OpenAI: {'✅ Configured' if ai_agent_service.is_configured() else '⚠️ Not Configured'}")
    logger.info(f"   SMS: {'✅ Configured' if sms_service.is_configured() else '⚠️ Not Configured'}")
    logger.info(f"   ElevenLabs: {'✅ Configured' if os.getenv('ELEVENLABS_API_KEY') else '⚠️ Not Configured'}")
    logger.info(f"   Google Calendar: {'✅ Configured' if google_calendar_service.is_configured() else '⚠️ Not Configured'}")
    # ⭐ NEW: Check RAG service
    logger.info(f"   RAG Service: {'✅ Ready' if os.getenv('OPENAI_API_KEY') else '⚠️ OpenAI Key Required'}")
    logger.info("=" * 80)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )