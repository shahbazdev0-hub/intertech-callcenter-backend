#  # backend/app/models/voice_agent.py - COMPLETE WITH ALL NEW FIELDS

# from datetime import datetime
# from typing import Optional, List, Dict, Any
# from pydantic import BaseModel, Field, validator
# from bson import ObjectId


# class VoiceAgent(BaseModel):
#     """
#     Voice Agent Model - COMPLETE VERSION
#     Supports: Single/Bulk calling, RAG training, Multi-channel communication
#     """
    
#     # ============================================
#     # BASIC IDENTIFICATION
#     # ============================================
#     id: Optional[str] = Field(None, alias="_id")
#     user_id: str
#     name: str
#     description: Optional[str] = None
    
#     # ============================================
#     # VOICE SETTINGS (ElevenLabs)
#     # ============================================
#     voice_id: str  # ElevenLabs voice ID - MUST be dynamic per agent
#     voice_settings: Dict[str, Any] = Field(
#         default_factory=lambda: {
#             "stability": 0.5,
#             "similarity_boost": 0.75
#         }
#     )
    
#     # ============================================
#     # CALLING CONFIGURATION (NEW)
#     # ============================================
#     calling_mode: str = Field(
#         default="single",
#         description="Calling mode: 'single' or 'bulk'"
#     )
    
#     contacts: List[Dict[str, str]] = Field(
#         default_factory=list,
#         description="List of contacts for calling. Format: [{'name': '', 'phone': '', 'email': ''}]"
#     )
    
#     # ============================================
#     # AI CONFIGURATION (NEW - Custom Script)
#     # ============================================
#     ai_script: Optional[str] = Field(
#         None,
#         description="Custom AI agent script - used when no training docs available"
#     )
    
#     system_prompt: Optional[str] = Field(
#         None,
#         description="Legacy system prompt - deprecated in favor of ai_script"
#     )
    
#     greeting_message: Optional[str] = Field(
#         None,
#         description="Initial greeting message"
#     )
    
#     personality_traits: List[str] = Field(
#         default_factory=list,
#         description="Personality traits for the agent"
#     )
    
#     knowledge_base: Dict[str, Any] = Field(
#         default_factory=dict,
#         description="Legacy knowledge base"
#     )
    
#     # ============================================
#     # AGENT INTELLIGENCE SETTINGS (NEW)
#     # ============================================
#     logic_level: str = Field(
#         default="medium",
#         description="Agent intelligence level: 'low', 'medium', 'high'"
#     )
    
#     contact_frequency: int = Field(
#         default=3,
#         ge=1,
#         le=30,
#         description="Days between contacts (1-30)"
#     )
    
#     # ============================================
#     # COMMUNICATION CHANNELS (NEW)
#     # ============================================
#     enable_calls: bool = Field(
#         default=True,
#         description="Enable voice calling"
#     )
    
#     enable_emails: bool = Field(
#         default=False,
#         description="Enable email communications"
#     )
    
#     enable_sms: bool = Field(
#         default=False,
#         description="Enable SMS communications"
#     )
    
#     # ============================================
#     # RAG TRAINING DOCUMENTS (NEW)
#     # ============================================
#     has_training_docs: bool = Field(
#         default=False,
#         description="Whether agent has uploaded training documents"
#     )
    
#     training_doc_ids: List[str] = Field(
#         default_factory=list,
#         description="IDs of uploaded training documents"
#     )
    
#     # ============================================
#     # WORKFLOW INTEGRATION (Existing - Keep)
#     # ============================================
#     workflow_id: Optional[str] = Field(
#         None,
#         description="AI Campaign workflow ID"
#     )
    
#     appointment_rules: Optional[Dict[str, Any]] = Field(
#         None,
#         description="Workflow appointment rules"
#     )
    
#     # ============================================
#     # STATUS & METRICS
#     # ============================================
#     is_active: bool = Field(
#         default=True,
#         description="Whether agent is active"
#     )
    
#     in_call: bool = Field(
#         default=False,
#         description="Whether agent is currently in a call"
#     )
    
#     total_calls: int = Field(
#         default=0,
#         description="Total number of calls made by this agent"
#     )
    
#     successful_calls: int = Field(
#         default=0,
#         description="Number of successful calls"
#     )
    
#     # ============================================
#     # BULK CAMPAIGN TRACKING (NEW)
#     # ============================================
#     last_campaign_run: Optional[datetime] = Field(
#         None,
#         description="Last time bulk campaign was executed"
#     )
    
#     campaign_status: Optional[str] = Field(
#         None,
#         description="Current campaign status: 'idle', 'running', 'paused', 'completed'"
#     )
    
#     # ============================================
#     # METADATA
#     # ============================================
#     metadata: Dict[str, Any] = Field(
#         default_factory=dict,
#         description="Additional metadata"
#     )
    
#     # ============================================
#     # TIMESTAMPS
#     # ============================================
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     updated_at: datetime = Field(default_factory=datetime.utcnow)
    
#     # ============================================
#     # VALIDATORS
#     # ============================================
#     @validator('calling_mode')
#     def validate_calling_mode(cls, v):
#         if v not in ['single', 'bulk']:
#             raise ValueError("calling_mode must be 'single' or 'bulk'")
#         return v
    
#     @validator('logic_level')
#     def validate_logic_level(cls, v):
#         if v not in ['low', 'medium', 'high']:
#             raise ValueError("logic_level must be 'low', 'medium', or 'high'")
#         return v
    
#     @validator('contacts')
#     def validate_contacts(cls, v, values):
#         """Validate contacts based on calling mode"""
#         calling_mode = values.get('calling_mode', 'single')
        
#         if calling_mode == 'bulk' and len(v) == 0:
#             raise ValueError("Bulk calling mode requires at least one contact")
        
#         # Validate each contact has required fields
#         for contact in v:
#             if 'name' not in contact or not contact['name']:
#                 raise ValueError("Each contact must have a 'name'")
#             if 'phone' not in contact or not contact['phone']:
#                 raise ValueError("Each contact must have a 'phone'")
        
#         return v
    
#     @validator('contact_frequency')
#     def validate_contact_frequency(cls, v):
#         if not 1 <= v <= 30:
#             raise ValueError("contact_frequency must be between 1 and 30 days")
#         return v
    
#     class Config:
#         populate_by_name = True
#         json_encoders = {
#             ObjectId: str,
#             datetime: lambda v: v.isoformat()
#         }
#         json_schema_extra = {
#             "example": {
#                 "name": "Customer Support Agent",
#                 "description": "Handles customer inquiries and support",
#                 "voice_id": "21m00Tcm4TlvDq8ikWAM",
#                 "calling_mode": "bulk",
#                 "contacts": [
#                     {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"},
#                     {"name": "Jane Smith", "phone": "+0987654321", "email": "jane@example.com"}
#                 ],
#                 "ai_script": "You are a helpful customer support agent...",
#                 "logic_level": "high",
#                 "contact_frequency": 7,
#                 "enable_calls": True,
#                 "enable_emails": True,
#                 "enable_sms": False,
#                 "has_training_docs": True,
#                 "training_doc_ids": ["doc123", "doc456"]
#             }
#         }  


# backend/app/models/voice_agent.py
# ✅ ENHANCED: Added agent_context field for dynamic summary caching

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class VoiceAgentModel(BaseModel):
    """
    Voice Agent Database Model
    
    ✅ ENHANCED: Now includes agent_context for fast contextual responses
    
    The agent_context field stores pre-generated summary from:
    - RAG documents (knowledge base)
    - Custom AI script
    
    This enables 1-2 second response times instead of 4-7 seconds
    """
    
    # ============================================
    # IDENTIFICATION
    # ============================================
    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="Owner user ID")
    
    # ============================================
    # BASIC INFO
    # ============================================
    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = Field(None, max_length=500, description="Agent description")
    
    # ============================================
    # VOICE SETTINGS
    # ============================================
    voice_id: str = Field(..., description="ElevenLabs voice ID")
    voice_settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "stability": 0.5,
            "similarity_boost": 0.75
        },
        description="ElevenLabs voice settings"
    )
    
    # ============================================
    # CALLING CONFIGURATION
    # ============================================
    calling_mode: str = Field(
        default="single",
        description="'single' or 'bulk' calling mode"
    )
    contacts: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of contacts for calling"
    )
    
    # ============================================
    # AI CONFIGURATION
    # ============================================
    ai_script: Optional[str] = Field(
        None,
        max_length=5000,
        description="Custom AI agent script/greeting"
    )
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
    personality_traits: List[str] = Field(
        default_factory=lambda: ["friendly", "professional", "helpful"],
        description="Personality traits for the agent"
    )
    
    # ============================================
    # ✅ NEW: AGENT CONTEXT (Dynamic Summary Cache)
    # ============================================
    agent_context: Optional[Dict[str, Any]] = Field(
        None,
        description="""
        Pre-generated context summary for fast responses.
        
        Structure:
        {
            "identity": {
                "name": "James",
                "company": "Vendria",
                "role": "Sales Representative"
            },
            "company_info": {
                "description": "...",
                "services": [...],
                "value_propositions": [...]
            },
            "knowledge_base": {
                "products": [...],
                "services": [...],
                "support_channels": [...],
                "working_hours": "..."
            },
            "faqs": [
                {"question": "...", "answer": "..."}
            ],
            "procedures": [
                {"name": "...", "steps": [...]}
            ],
            "summary_text": "...",
            "generated_at": "ISO timestamp",
            "source_documents": ["filename1.pdf", ...],
            "script_included": true/false
        }
        """
    )
    
    has_context: bool = Field(
        default=False,
        description="Whether agent has pre-generated context"
    )
    
    context_generated_at: Optional[datetime] = Field(
        None,
        description="When the context was last generated"
    )
    
    # ============================================
    # TRAINING DOCUMENTS (RAG)
    # ============================================
    has_training_docs: bool = Field(
        default=False,
        description="Whether agent has training documents"
    )
    training_doc_ids: List[str] = Field(
        default_factory=list,
        description="List of training document IDs"
    )
    
    # ============================================
    # WORKFLOW INTEGRATION
    # ============================================
    workflow_id: Optional[str] = Field(
        None,
        description="Associated workflow/campaign ID"
    )
    
    # ============================================
    # AGENT SETTINGS
    # ============================================
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
    
    # ============================================
    # COMMUNICATION CHANNELS
    # ============================================
    enable_calls: bool = Field(True, description="Enable voice calls")
    enable_emails: bool = Field(False, description="Enable email campaigns")
    enable_sms: bool = Field(False, description="Enable SMS messaging")
    
    # ============================================
    # TEMPLATES
    # ============================================
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
    
    # ============================================
    # STATUS & STATISTICS
    # ============================================
    is_active: bool = Field(True, description="Whether agent is active")
    in_call: bool = Field(False, description="Whether agent is currently in a call")
    total_calls: int = Field(default=0, ge=0, description="Total calls made")
    successful_calls: int = Field(default=0, ge=0, description="Successful calls")
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "name": "Sales Assistant",
                "description": "AI agent for sales calls",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                },
                "calling_mode": "bulk",
                "contacts": [
                    {"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}
                ],
                "ai_script": "Hello, this is James from Vendria...",
                "system_prompt": "You are a helpful sales assistant",
                "greeting_message": "Hello! Thanks for taking my call.",
                "personality_traits": ["friendly", "professional"],
                "agent_context": {
                    "identity": {"name": "James", "company": "Vendria"},
                    "company_info": {"services": ["lead generation", "sales"]},
                    "faqs": [],
                    "generated_at": "2024-01-01T00:00:00Z"
                },
                "has_context": True,
                "context_generated_at": "2024-01-01T00:00:00Z",
                "has_training_docs": True,
                "training_doc_ids": ["doc1", "doc2"],
                "workflow_id": None,
                "logic_level": "high",
                "contact_frequency": 7,
                "enable_calls": True,
                "enable_emails": True,
                "enable_sms": False,
                "email_template": "Hello {name}...",
                "sms_template": "Hi {name}...",
                "is_active": True,
                "in_call": False,
                "total_calls": 100,
                "successful_calls": 85,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }


# ============================================
# HELPER FUNCTIONS
# ============================================

def voice_agent_to_dict(agent: VoiceAgentModel) -> Dict[str, Any]:
    """Convert VoiceAgentModel to dictionary for MongoDB"""
    data = agent.model_dump(by_alias=True, exclude_none=True)
    
    # Remove _id if None (for new documents)
    if "_id" in data and data["_id"] is None:
        del data["_id"]
    
    return data


def dict_to_voice_agent(data: Dict[str, Any]) -> VoiceAgentModel:
    """Convert MongoDB document to VoiceAgentModel"""
    if "_id" in data:
        data["_id"] = str(data["_id"])
    if "user_id" in data:
        data["user_id"] = str(data["user_id"])
    
    return VoiceAgentModel(**data)