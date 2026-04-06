# # backend/app/schemas/voice.py  without new approach contexetual approach 
# from typing import Optional, List, Dict, Any
# from pydantic import BaseModel, Field, EmailStr, validator


# # ============================================
# # CONTACT SCHEMA
# # ============================================

# class ContactCreate(BaseModel):
#     """Single contact for calling"""
#     name: str = Field(..., min_length=1, max_length=200)
#     phone: str = Field(..., min_length=10, max_length=20)
#     email: Optional[EmailStr] = None
    
#     @validator('phone')
#     def validate_phone(cls, v):
#         # Remove spaces and dashes
#         phone = v.replace(' ', '').replace('-', '')
#         # Must start with + for international format
#         if not phone.startswith('+'):
#             raise ValueError("Phone number must start with + (e.g., +1234567890)")
#         # Must be numeric after +
#         if not phone[1:].isdigit():
#             raise ValueError("Phone number must contain only digits after +")
#         return phone


# # ============================================
# # VOICE AGENT CREATE SCHEMAS
# # ============================================

# class VoiceAgentCreate(BaseModel):
#     """Basic schema for creating a new voice agent"""
    
#     # Basic info
#     name: str = Field(..., min_length=1, max_length=100)
#     description: Optional[str] = Field(None, max_length=500)
    
#     # Voice settings
#     voice_id: str = Field(..., description="ElevenLabs voice ID")
#     voice_settings: Optional[Dict[str, Any]] = Field(
#         default_factory=lambda: {
#             "stability": 0.5,
#             "similarity_boost": 0.75
#         }
#     )
    
#     # Calling configuration
#     calling_mode: str = Field(
#         default="single",
#         description="'single' or 'bulk'"
#     )
#     contacts: List[ContactCreate] = Field(
#         default_factory=list,
#         description="List of contacts"
#     )
    
#     # AI configuration
#     ai_script: str = Field(
#         ...,
#         min_length=50,
#         max_length=5000,
#         description="Custom AI agent script"
#     )
    
#     # Agent settings
#     logic_level: str = Field(
#         default="medium",
#         description="Logic sophistication: 'low', 'medium', 'high'"
#     )
#     contact_frequency: int = Field(
#         default=7,
#         ge=1,
#         le=30,
#         description="Days between contacts"
#     )
    
#     # Status
#     is_active: bool = Field(True, description="Whether agent is active")
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "name": "Sales Assistant",
#                 "description": "AI agent for sales calls",
#                 "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                 "calling_mode": "bulk",
#                 "contacts": [
#                     {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}
#                 ],
#                 "ai_script": "You are a friendly sales agent...",
#                 "logic_level": "high",
#                 "contact_frequency": 7,
#                 "is_active": True
#             }
#         }


# class VoiceAgentCreateExtended(VoiceAgentCreate):
#     """
#     Extended schema for creating voice agent with additional features
    
#     Includes:
#     - Communication channels (calls, emails, SMS)
#     - Workflow integration
#     - Advanced AI settings
#     """
    
#     # Communication channels
#     enable_calls: bool = Field(True, description="Enable voice calls")
#     enable_emails: bool = Field(False, description="Enable email campaigns")
#     enable_sms: bool = Field(False, description="Enable SMS messaging")
    
#     # Workflow integration
#     workflow_id: Optional[str] = Field(None, description="Associated workflow ID")
    
#     # Advanced AI settings
#     system_prompt: Optional[str] = Field(
#         None,
#         max_length=2000,
#         description="System prompt for AI behavior"
#     )
#     greeting_message: Optional[str] = Field(
#         None,
#         max_length=500,
#         description="Custom greeting message"
#     )
#     personality_traits: Optional[List[str]] = Field(
#         default_factory=list,
#         description="Personality traits for the agent"
#     )
    
#     # ✅ NEW: Email & SMS Templates
#     email_template: Optional[str] = Field(
#         None,
#         max_length=2000,
#         description="Custom email message template"
#     )
#     sms_template: Optional[str] = Field(
#         None,
#         max_length=500,
#         description="Custom SMS message template"
#     )
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "name": "Sales Assistant",
#                 "description": "AI agent for sales calls",
#                 "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                 "calling_mode": "bulk",
#                 "contacts": [
#                     {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}
#                 ],
#                 # "ai_script": "You are a friendly sales agent helping customers...",
#                 # "system_prompt": "Always be professional and helpful",
#                 # "greeting_message": "Hello! Thanks for taking my call today.",
#                 "ai_script": "You are James, a professional and friendly AI sales agent for Vendria. Your role is to greet customers warmly, understand their needs, provide clear solutions, offer relevant AI-powered call center and sales services, and schedule appointments when appropriate. Always speak in a helpful and approachable way, aiming to improve customer engagement and drive business growth.",
#                 "system_prompt": "Always be professional, friendly, and solution-oriented. Focus on Vendria's AI-powered call center and sales solutions, provide clear guidance, listen carefully, and help convert leads while maintaining a positive customer experience.",
#                 "greeting_message": "Hi, this is James from Vendria! We help businesses save time and increase sales with AI-driven call center solutions. How’s your day going so far?",
#                 "personality_traits": ["friendly", "professional", "helpful"],
#                 "logic_level": "high",
#                 "contact_frequency": 7,
#                 "enable_calls": True,
#                 "enable_emails": True,
#                 "enable_sms": False,
#                 "workflow_id": None,
#                 "email_template": "Hello {name},\n\nThis is a follow-up email...",
#                 "sms_template": "Hi {name}, just following up on our call...",
#                 "is_active": True
#             }
#         }


# # ============================================
# # VOICE AGENT UPDATE SCHEMA
# # ============================================

# class VoiceAgentUpdate(BaseModel):
#     """Schema for updating an existing voice agent"""
#     name: Optional[str] = Field(None, min_length=1, max_length=100)
#     description: Optional[str] = Field(None, max_length=500)
#     voice_id: Optional[str] = None
#     voice_settings: Optional[Dict[str, Any]] = None
    
#     calling_mode: Optional[str] = None
#     contacts: Optional[List[ContactCreate]] = None
    
#     ai_script: Optional[str] = Field(None, min_length=50, max_length=5000)
#     workflow_id: Optional[str] = None
#     system_prompt: Optional[str] = None
#     greeting_message: Optional[str] = None
#     personality_traits: Optional[List[str]] = None
    
#     logic_level: Optional[str] = None
#     contact_frequency: Optional[int] = Field(None, ge=1, le=30)
    
#     enable_calls: Optional[bool] = None
#     enable_emails: Optional[bool] = None
#     enable_sms: Optional[bool] = None
    
#     # ✅ NEW
#     email_template: Optional[str] = None
#     sms_template: Optional[str] = None
    
#     is_active: Optional[bool] = None
#     in_call: Optional[bool] = None
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "name": "Updated Agent Name",
#                 "description": "Updated description",
#                 "email_template": "Updated email template...",
#                 "sms_template": "Updated SMS template...",
#                 "is_active": True
#             }
#         }


# # ============================================
# # VOICE AGENT RESPONSE SCHEMA
# # ============================================

# class VoiceAgentResponse(BaseModel):
#     """Schema for voice agent API responses"""
#     id: str = Field(..., alias="_id")
#     user_id: str
#     name: str
#     description: Optional[str]
#     voice_id: str
#     calling_mode: str
#     contacts: List[Dict[str, str]]
#     ai_script: Optional[str]
#     logic_level: str
#     contact_frequency: int
#     enable_calls: bool
#     enable_emails: bool
#     enable_sms: bool
    
#     # ✅ NEW
#     email_template: Optional[str] = None
#     sms_template: Optional[str] = None
    
#     has_training_docs: bool
#     training_doc_ids: List[str]
#     is_active: bool
#     in_call: bool
#     total_calls: int
#     successful_calls: int
#     created_at: str
#     updated_at: str

#     class Config:
#         populate_by_name = True
#         json_schema_extra = {
#             "example": {
#                 "_id": "507f1f77bcf86cd799439011",
#                 "user_id": "507f1f77bcf86cd799439012",
#                 "name": "Sales Assistant",
#                 "description": "AI agent for sales",
#                 "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                 "calling_mode": "bulk",
#                 "contacts": [],
#                 "ai_script": "You are a helpful assistant",
#                 "logic_level": "high",
#                 "contact_frequency": 7,
#                 "enable_calls": True,
#                 "enable_emails": False,
#                 "enable_sms": False,
#                 "email_template": "Hello {name}, following up on our call...",
#                 "sms_template": "Hi {name}, thanks for speaking!",
#                 "has_training_docs": False,
#                 "training_doc_ids": [],
#                 "is_active": True,
#                 "in_call": False,
#                 "total_calls": 0,
#                 "successful_calls": 0,
#                 "created_at": "2024-01-01T00:00:00",
#                 "updated_at": "2024-01-01T00:00:00"
#             }
#         }


# # ============================================
# # VOICE TEST SCHEMAS
# # ============================================

# class VoiceTestRequest(BaseModel):
#     """Schema for testing a voice"""
#     voice_id: str = Field(..., description="ElevenLabs voice ID to test")
#     text: str = Field(
#         default="Hello! This is a test of the voice synthesis.",
#         max_length=500,
#         description="Text to synthesize"
#     )
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                 "text": "Hello! This is a test message."
#             }
#         }


# class VoiceListResponse(BaseModel):
#     """Schema for list of available voices"""
#     success: bool = True
#     voices: List[Dict[str, Any]]
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "voices": [
#                     {
#                         "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                         "name": "Rachel",
#                         "category": "premade"
#                     }
#                 ]
#             }
#         }


# # ============================================
# # BULK CAMPAIGN SCHEMAS
# # ============================================

# class BulkCampaignConfig(BaseModel):
#     """Schema for bulk campaign configuration"""
#     agent_id: str = Field(..., description="Agent ID to use for campaign")
#     delay_between_calls: int = Field(
#         default=30,
#         ge=10,
#         le=300,
#         description="Seconds between calls"
#     )
#     max_concurrent_calls: int = Field(
#         default=1,
#         ge=1,
#         le=5,
#         description="Maximum simultaneous calls"
#     )
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "agent_id": "507f1f77bcf86cd799439011",
#                 "delay_between_calls": 30,
#                 "max_concurrent_calls": 1
#             }
#         }


# class BulkCampaignResult(BaseModel):
#     """Schema for bulk campaign results"""
#     success: bool
#     message: str
#     results: Dict[str, Any]
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "message": "Bulk campaign completed",
#                 "results": {
#                     "total": 10,
#                     "initiated": 8,
#                     "failed": 2,
#                     "calls": []
#                 }
#             }
#         }


# # ============================================
# # DOCUMENT UPLOAD SCHEMAS (RAG)
# # ============================================

# class DocumentUploadResponse(BaseModel):
#     """Schema for document upload response"""
#     success: bool
#     message: str
#     document_id: str
#     filename: str
#     file_size: int
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "message": "Document uploaded successfully",
#                 "document_id": "507f1f77bcf86cd799439011",
#                 "filename": "training_data.pdf",
#                 "file_size": 1024000
#             }
#         }


# class DocumentListResponse(BaseModel):
#     """Schema for document list response"""
#     success: bool
#     documents: List[Dict[str, Any]]
#     total: int
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "documents": [
#                     {
#                         "_id": "507f1f77bcf86cd799439011",
#                         "filename": "training.pdf",
#                         "file_size": 1024000,
#                         "upload_date": "2024-01-01T00:00:00",
#                         "processed": True
#                     }
#                 ],
#                 "total": 1
#             }
#         }


# # ============================================
# # AGENT STATISTICS SCHEMAS
# # ============================================

# class AgentStatistics(BaseModel):
#     """Schema for agent statistics"""
#     success: bool
#     stats: Dict[str, Any]
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "stats": {
#                     "total_calls": 100,
#                     "completed_calls": 85,
#                     "failed_calls": 15,
#                     "average_duration": 180.5,
#                     "total_duration": 18050,
#                     "success_rate": 85.0,
#                     "has_training_docs": True,
#                     "training_doc_count": 3
#                 }
#             }
#         }  


# backend/app/schemas/voice.py new approach contexetual
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator


# ============================================
# CONTACT SCHEMA
# ============================================

class ContactCreate(BaseModel):
    """Single contact for calling"""
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove spaces and dashes
        phone = v.replace(' ', '').replace('-', '')
        # Must start with + for international format
        if not phone.startswith('+'):
            raise ValueError("Phone number must start with + (e.g., +1234567890)")
        # Must be numeric after +
        if not phone[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        return phone


# ============================================
# ✅ NEW: AGENT CONTEXT SCHEMA (Dynamic Summary)
# ============================================

class AgentIdentity(BaseModel):
    """Agent identity information"""
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    
class CompanyInfo(BaseModel):
    """Company information extracted from documents/script"""
    description: Optional[str] = None
    industry: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    value_propositions: List[str] = Field(default_factory=list)
    
class KnowledgeBase(BaseModel):
    """Knowledge base from RAG documents"""
    products: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    support_channels: List[str] = Field(default_factory=list)
    working_hours: Optional[str] = None
    
class FAQItem(BaseModel):
    """FAQ item"""
    question: str
    answer: str
    
class ProcedureItem(BaseModel):
    """Procedure item"""
    name: str
    steps: List[str] = Field(default_factory=list)

class AgentContext(BaseModel):
    """
    ✅ NEW: Complete agent context for fast voice responses
    This is pre-generated when documents/scripts are uploaded
    and injected into every call for instant contextual responses
    """
    # Agent identity
    identity: AgentIdentity = Field(default_factory=AgentIdentity)
    
    # Company information
    company_info: CompanyInfo = Field(default_factory=CompanyInfo)
    
    # Knowledge base from RAG documents
    knowledge_base: KnowledgeBase = Field(default_factory=KnowledgeBase)
    
    # FAQs extracted from documents
    faqs: List[FAQItem] = Field(default_factory=list)
    
    # Procedures extracted from documents
    procedures: List[ProcedureItem] = Field(default_factory=list)
    
    # Raw summary text (fallback)
    summary_text: Optional[str] = None
    
    # Metadata
    generated_at: Optional[str] = None
    source_documents: List[str] = Field(default_factory=list)
    script_included: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "identity": {
                    "name": "James",
                    "company": "Vendria",
                    "role": "Sales Representative"
                },
                "company_info": {
                    "description": "AI-powered call center solutions",
                    "services": ["lead generation", "customer support"],
                    "value_propositions": ["save time", "increase conversions"]
                },
                "knowledge_base": {
                    "products": ["Telecom plans", "CRM software"],
                    "working_hours": "24/7"
                },
                "faqs": [
                    {"question": "How to handle angry customers?", "answer": "Stay calm, listen, empathize"}
                ],
                "procedures": [
                    {"name": "Refund Process", "steps": ["Verify order", "Check eligibility"]}
                ],
                "generated_at": "2024-01-01T00:00:00Z",
                "source_documents": ["knowledge_base.pdf"],
                "script_included": True
            }
        }


# ============================================
# VOICE AGENT CREATE SCHEMAS
# ============================================

class VoiceAgentCreate(BaseModel):
    """Basic schema for creating a new voice agent"""
    
    # Basic info
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Voice settings
    voice_id: str = Field(..., description="ElevenLabs voice ID")
    voice_settings: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    )
    
    # Calling configuration
    calling_mode: str = Field(
        default="single",
        description="'single' or 'bulk'"
    )
    contacts: List[ContactCreate] = Field(
        default_factory=list,
        description="List of contacts"
    )
    
    # AI configuration
    ai_script: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Custom AI agent script"
    )
    
    # Agent settings
    logic_level: str = Field(
        default="medium",
        description="Logic sophistication: 'low', 'medium', 'high'"
    )
    contact_frequency: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days between contacts"
    )
    
    # Status
    is_active: bool = Field(True, description="Whether agent is active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Assistant",
                "description": "AI agent for sales calls",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "calling_mode": "bulk",
                "contacts": [
                    {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}
                ],
                "ai_script": "You are a friendly sales agent...",
                "logic_level": "high",
                "contact_frequency": 7,
                "is_active": True
            }
        }


class VoiceAgentCreateExtended(VoiceAgentCreate):
    """
    Extended schema for creating voice agent with additional features
    
    Includes:
    - Communication channels (calls, emails, SMS)
    - Workflow integration
    - Advanced AI settings
    """
    
    # Communication channels
    enable_calls: bool = Field(True, description="Enable voice calls")
    enable_emails: bool = Field(False, description="Enable email campaigns")
    enable_sms: bool = Field(False, description="Enable SMS messaging")
    
    # Workflow integration
    workflow_id: Optional[str] = Field(None, description="Associated workflow ID")
    
    # Advanced AI settings
    system_prompt: Optional[str] = Field(
        None,
        max_length=2000,
        description="System prompt for AI behavior"
    )
    greeting_message: Optional[str] = Field(
        None,
        max_length=500,
        description="Custom greeting message"
    )
    personality_traits: Optional[List[str]] = Field(
        default_factory=list,
        description="Personality traits for the agent"
    )
    
    # ✅ Email & SMS Templates
    email_template: Optional[str] = Field(
        None,
        max_length=2000,
        description="Custom email message template"
    )
    sms_template: Optional[str] = Field(
        None,
        max_length=500,
        description="Custom SMS message template"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Assistant",
                "description": "AI agent for sales calls",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "calling_mode": "bulk",
                "contacts": [
                    {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}
                ],
                "ai_script": "You are a friendly sales agent helping customers...",
                "system_prompt": "Always be professional and helpful",
                "greeting_message": "Hello! Thanks for taking my call today.",
                "personality_traits": ["friendly", "professional", "helpful"],
                "logic_level": "high",
                "contact_frequency": 7,
                "enable_calls": True,
                "enable_emails": True,
                "enable_sms": False,
                "workflow_id": None,
                "email_template": "Hello {name},\n\nThis is a follow-up email...",
                "sms_template": "Hi {name}, just following up on our call...",
                "is_active": True
            }
        }


# ============================================
# VOICE AGENT UPDATE SCHEMA
# ============================================

class VoiceAgentUpdate(BaseModel):
    """Schema for updating an existing voice agent"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    voice_id: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    
    calling_mode: Optional[str] = None
    contacts: Optional[List[ContactCreate]] = None
    
    ai_script: Optional[str] = Field(None, min_length=50, max_length=5000)
    workflow_id: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting_message: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    
    logic_level: Optional[str] = None
    contact_frequency: Optional[int] = Field(None, ge=1, le=30)
    
    enable_calls: Optional[bool] = None
    enable_emails: Optional[bool] = None
    enable_sms: Optional[bool] = None
    
    # ✅ Email & SMS Templates
    email_template: Optional[str] = None
    sms_template: Optional[str] = None
    
    is_active: Optional[bool] = None
    in_call: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Agent Name",
                "description": "Updated description",
                "email_template": "Updated email template...",
                "sms_template": "Updated SMS template...",
                "is_active": True
            }
        }


# ============================================
# VOICE AGENT RESPONSE SCHEMA
# ============================================

class VoiceAgentResponse(BaseModel):
    """Schema for voice agent API responses"""
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    description: Optional[str]
    voice_id: str
    calling_mode: str
    contacts: List[Dict[str, str]]
    ai_script: Optional[str]
    logic_level: str
    contact_frequency: int
    enable_calls: bool
    enable_emails: bool
    enable_sms: bool
    
    # ✅ Email & SMS Templates
    email_template: Optional[str] = None
    sms_template: Optional[str] = None
    
    # ✅ NEW: Agent Context (Dynamic Summary)
    agent_context: Optional[Dict[str, Any]] = None
    has_context: bool = False
    
    has_training_docs: bool
    training_doc_ids: List[str]
    is_active: bool
    in_call: bool
    total_calls: int
    successful_calls: int
    created_at: str
    updated_at: str

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "name": "Sales Assistant",
                "description": "AI agent for sales",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "calling_mode": "bulk",
                "contacts": [],
                "ai_script": "You are a helpful assistant",
                "logic_level": "high",
                "contact_frequency": 7,
                "enable_calls": True,
                "enable_emails": False,
                "enable_sms": False,
                "email_template": "Hello {name}, following up on our call...",
                "sms_template": "Hi {name}, thanks for speaking!",
                "agent_context": None,
                "has_context": False,
                "has_training_docs": False,
                "training_doc_ids": [],
                "is_active": True,
                "in_call": False,
                "total_calls": 0,
                "successful_calls": 0,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }


# ============================================
# VOICE TEST SCHEMAS
# ============================================

class VoiceTestRequest(BaseModel):
    """Schema for testing a voice"""
    voice_id: str = Field(..., description="ElevenLabs voice ID to test")
    text: str = Field(
        default="Hello! This is a test of the voice synthesis.",
        max_length=500,
        description="Text to synthesize"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "text": "Hello! This is a test message."
            }
        }


class VoiceListResponse(BaseModel):
    """Schema for list of available voices"""
    success: bool = True
    voices: List[Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "voices": [
                    {
                        "voice_id": "21m00Tcm4TlvDq8ikWAM",
                        "name": "Rachel",
                        "category": "premade"
                    }
                ]
            }
        }


# ============================================
# BULK CAMPAIGN SCHEMAS
# ============================================

class BulkCampaignConfig(BaseModel):
    """Schema for bulk campaign configuration"""
    agent_id: str = Field(..., description="Agent ID to use for campaign")
    delay_between_calls: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Seconds between calls"
    )
    max_concurrent_calls: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Maximum simultaneous calls"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "507f1f77bcf86cd799439011",
                "delay_between_calls": 30,
                "max_concurrent_calls": 1
            }
        }


class BulkCampaignResult(BaseModel):
    """Schema for bulk campaign results"""
    success: bool
    message: str
    results: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Bulk campaign completed",
                "results": {
                    "total": 10,
                    "initiated": 8,
                    "failed": 2,
                    "calls": []
                }
            }
        }


# ============================================
# DOCUMENT UPLOAD SCHEMAS (RAG)
# ============================================

class DocumentUploadResponse(BaseModel):
    """Schema for document upload response"""
    success: bool
    message: str
    document_id: str
    filename: str
    file_size: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Document uploaded successfully",
                "document_id": "507f1f77bcf86cd799439011",
                "filename": "training_data.pdf",
                "file_size": 1024000
            }
        }


class DocumentListResponse(BaseModel):
    """Schema for document list response"""
    success: bool
    documents: List[Dict[str, Any]]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "documents": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "filename": "training.pdf",
                        "file_size": 1024000,
                        "upload_date": "2024-01-01T00:00:00",
                        "processed": True
                    }
                ],
                "total": 1
            }
        }


# ============================================
# AGENT STATISTICS SCHEMAS
# ============================================

class AgentStatistics(BaseModel):
    """Schema for agent statistics"""
    success: bool
    stats: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "stats": {
                    "total_calls": 100,
                    "completed_calls": 85,
                    "failed_calls": 15,
                    "average_duration": 180.5,
                    "total_duration": 18050,
                    "success_rate": 85.0,
                    "has_training_docs": True,
                    "training_doc_count": 3
                }
            }
        }