 

# backend/app/config.py - COMPLETE FILE with all settings

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application Settings"""
    
    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    APP_NAME: str = "CallCenter SaaS"
    PROJECT_NAME: str = "CallCenter SaaS"  # Alias for APP_NAME (used in main.py)
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # ============================================
    # DATABASE CONFIGURATION
    # ============================================
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "callcenter_saas")
    
    # ============================================
    # SECURITY KEYS
    # ============================================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-jwt-secret")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # ============================================
    # EMAIL CONFIGURATION
    # ============================================
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER: str = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "CallCenter SaaS")
    
    # ============================================
    # FRONTEND CONFIGURATION
    # ============================================
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # ============================================
    # TWILIO CONFIGURATION
    # ============================================
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_WEBHOOK_URL: Optional[str] = None
    TWILIO_AMD_ENABLED: bool = False  # default off

    # Twilio provisioning defaults (for auto-creating subaccounts + numbers)
    TWILIO_DEFAULT_AREA_CODE: str = "438"
    TWILIO_DEFAULT_COUNTRY_CODE: str = "CA"

    # ============================================
    # STRIPE CONFIGURATION
    # ============================================
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_STARTER_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_STARTER_YEARLY_PRICE_ID: Optional[str] = None
    STRIPE_PRO_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_PRO_YEARLY_PRICE_ID: Optional[str] = None
    STRIPE_ENTERPRISE_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_ENTERPRISE_YEARLY_PRICE_ID: Optional[str] = None

    # ============================================
    # OPENAI CONFIGURATION
    # ============================================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "150"))
    
    # ============================================
    # ✅ GROQ CONFIGURATION - ⚡ FASTER AI ALTERNATIVE
    # ============================================
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    USE_GROQ: bool = os.getenv("USE_GROQ", "true").lower() == "true"
    
    # ============================================
    # ELEVENLABS CONFIGURATION
    # ============================================
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None
    ELEVENLABS_MODEL_ID: str = "eleven_turbo_v2_5"
    
    # ============================================
    # WEBSOCKET CONFIGURATION
    # ============================================
    WEBSOCKET_HOST: str = "0.0.0.0"
    WEBSOCKET_PORT: int = 8001
    DEEPGRAM_API_KEY: str = ""
    # ============================================
    # SMS CONFIGURATION
    # ============================================
    TWILIO_SMS_ENABLED: bool = True
    SMS_WEBHOOK_URL: Optional[str] = None
    
    # ============================================
    # GOOGLE CALENDAR CONFIGURATION
    # ============================================
    GOOGLE_CALENDAR_CREDENTIALS_FILE: Optional[str] = None
    GOOGLE_CALENDAR_ID: Optional[str] = None
    
    # ============================================
    # APPOINTMENT SETTINGS
    # ============================================
    DEFAULT_APPOINTMENT_DURATION: int = 60
    DEFAULT_WORKING_HOURS_START: str = "09:00"
    DEFAULT_WORKING_HOURS_END: str = "17:00"
    SEND_APPOINTMENT_REMINDERS: bool = True
    REMINDER_HOURS_BEFORE: int = 24
    
    # ============================================
    # CELERY CONFIGURATION
    # ============================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # ============================================
    # RAG CONFIGURATION
    # ============================================
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    RAG_SIMILARITY_THRESHOLD: float = 0.65
    RAG_MAX_RESULTS: int = 3
    
    # ============================================
    # AGENT CONTEXT SETTINGS
    # ============================================
    CONTEXT_GENERATION_ENABLED: bool = True
    CONTEXT_AUTO_REGENERATE: bool = True
    CONTEXT_MAX_DOCUMENT_LENGTH: int = 10000
    CONTEXT_MAX_FAQS: int = 15
    CONTEXT_MAX_PROCEDURES: int = 10
    
    # Context Caching (Optional)
    CONTEXT_CACHE_ENABLED: bool = False
    CONTEXT_CACHE_TTL: int = 3600
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Fast Response Settings
    FAST_RESPONSE_ENABLED: bool = True
    FAST_RESPONSE_MAX_TOKENS: int = 150
    FAST_RESPONSE_TIMEOUT: float = 8.0
    
    # ============================================
    # EMAIL IMAP/POLLING SETTINGS
    # ============================================
    EMAIL_IMAP_POLLING_ENABLED: bool = True
    EMAIL_POLLING_INTERVAL: int = 60
    
    # ============================================
    # TWILIO RECORDING SETTINGS
    # ============================================
    TWILIO_RECORDING_STATUS_CALLBACK: Optional[str] = None
    
    # ============================================
    # CALENDAR MONITORING SETTINGS
    # ============================================
    CALENDAR_MONITOR_INTERVAL: int = 600
    CALENDAR_REMINDER_BUFFER: int = 5
    
    # ============================================
    # EMAIL AUTOMATION SETTINGS
    # ============================================
    EMAIL_AUTOMATION_ENABLED: bool = True
    MAX_EMAILS_PER_HOUR: int = 100
    MAX_EMAILS_PER_DAY: int = 1000
    EMAIL_BATCH_SIZE: int = 50
    
    # ============================================
    # SMS LIMITS SETTINGS
    # ============================================
    MAX_SMS_PER_HOUR: int = 100
    MAX_SMS_PER_DAY: int = 500
    SMS_BATCH_SIZE: int = 25
    
    # ============================================
    # AUTOMATION/WORKFLOW SETTINGS
    # ============================================
    MAX_AUTOMATIONS_PER_USER: int = 50
    MAX_WORKFLOWS_PER_USER: int = 25
    MAX_AUTOMATION_ACTIONS: int = 20
    AUTOMATION_EXECUTION_TIMEOUT: int = 300
    WORKFLOW_MAX_NODES: int = 50
    WORKFLOW_EXECUTION_TIMEOUT: int = 600
    WORKFLOW_MAX_RETRIES: int = 3
    
    # ============================================
    # CAMPAIGN SETTINGS
    # ============================================
    MAX_CAMPAIGN_RECIPIENTS: int = 10000
    CAMPAIGN_SEND_RATE_LIMIT: int = 10
    BULK_CAMPAIGN_DEFAULT_DELAY: int = 30
    BULK_CAMPAIGN_MAX_CONCURRENT: int = 10
    BULK_CAMPAIGN_TIMEOUT: int = 3600
    
    # ============================================
    # DOCUMENT SETTINGS
    # ============================================
    MAX_DOCUMENT_SIZE_MB: int = 10
    ALLOWED_DOCUMENT_TYPES: str = "pdf,docx,doc,txt,md"
    DOCUMENTS_STORAGE_PATH: str = "uploads/agent_documents"
    
    # ============================================
    # AGENT EXECUTOR SETTINGS
    # ============================================
    AGENT_EXECUTOR_TIMEOUT: int = 60
    AGENT_EXECUTOR_MAX_RETRIES: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create settings instance
settings = get_settings()