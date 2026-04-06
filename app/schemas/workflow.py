# backend/app/schemas/workflow.py - MILESTONE 3 without campaign builder 

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow"""
    name: str = Field(..., min_length=1, max_length=200, description="Workflow name")
    description: Optional[str] = Field(None, max_length=500, description="Workflow description")
    is_active: bool = Field(True, description="Whether workflow is active")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Workflow nodes")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="Workflow edges/connections")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Lead Qualification Workflow",
                "description": "Workflow to qualify and route leads",
                "is_active": True,
                "nodes": [],
                "edges": []
            }
        }


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None


class WorkflowResponse(BaseModel):
    """Schema for workflow response"""
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    version: int
    execution_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True



