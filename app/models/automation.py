# backend/app/models/automation.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class Automation(BaseModel):
    """Automation Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    
    # Trigger
    trigger_type: str  # call_completed, demo_booked, form_submitted, time_based
    trigger_config: Dict[str, Any] = {}
    
    # Actions
    actions: List[Dict[str, Any]] = []  # List of actions to execute
    
    # Status
    is_active: bool = True
    
    # Stats
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_executed_at: Optional[datetime] = None
    
    # Settings
    max_executions: Optional[int] = None  # Limit total executions
    execution_timeout: int = 300  # seconds
    retry_on_failure: bool = True
    max_retries: int = 3
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class AutomationLog(BaseModel):
    """Automation Execution Log"""
    id: Optional[str] = Field(None, alias="_id")
    automation_id: str
    user_id: str
    
    # Execution details
    status: str  # success, failed, running
    trigger_data: Dict[str, Any] = {}
    actions_executed: List[Dict[str, Any]] = []
    
    # Results
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}