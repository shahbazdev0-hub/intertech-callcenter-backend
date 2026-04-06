# backend/app/schemas/automation.py - MILESTONE 3 COMPLETE

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AutomationAction(BaseModel):
    """Schema for automation action"""
    type: str = Field(..., description="Action type (send_email, send_sms, delay, webhook)")
    config: Dict[str, Any] = Field(..., description="Action configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "send_email",
                "config": {
                    "to_email": "customer@example.com",
                    "subject": "Thank you!",
                    "content": "Thank you for your call."
                }
            }
        }


class AutomationCreate(BaseModel):
    """Schema for creating an automation"""
    name: str = Field(..., min_length=1, max_length=200, description="Automation name")
    description: Optional[str] = Field(None, max_length=500, description="Automation description")
    trigger_type: str = Field(..., description="Trigger type (call_completed, demo_booked, form_submitted, time_based)")
    trigger_config: Dict[str, Any] = Field(default_factory=dict, description="Trigger configuration")
    actions: List[AutomationAction] = Field(..., min_items=1, description="List of actions to execute")
    is_active: bool = Field(True, description="Whether automation is active")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Post-Call Follow-up",
                "description": "Send email after call completion",
                "trigger_type": "call_completed",
                "trigger_config": {},
                "actions": [
                    {
                        "type": "send_email",
                        "config": {
                            "to_email": "{{customer_email}}",
                            "subject": "Thank you for your call",
                            "content": "We appreciate your time."
                        }
                    }
                ],
                "is_active": True
            }
        }


class AutomationUpdate(BaseModel):
    """Schema for updating an automation"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    actions: Optional[List[AutomationAction]] = None
    is_active: Optional[bool] = None


class AutomationResponse(BaseModel):
    """Schema for automation response"""
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any]
    actions: List[Dict[str, Any]]
    is_active: bool
    execution_count: int
    success_count: int
    failure_count: int
    last_executed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class AutomationStats(BaseModel):
    """Schema for automation statistics"""
    total_automations: int
    active_automations: int
    total_executions: int
    successful_executions: int
    failed_executions: int


class TriggerAutomationRequest(BaseModel):
    """Schema for manually triggering an automation"""
    trigger_data: Dict[str, Any] = Field(default_factory=dict, description="Data to pass to automation")

    class Config:
        json_schema_extra = {
            "example": {
                "trigger_data": {
                    "customer_email": "customer@example.com",
                    "call_id": "507f1f77bcf86cd799439011"
                }
            }
        }