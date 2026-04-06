# # backend/app/models/workflow.py without campaign builder 

# from datetime import datetime
# from typing import Optional, List, Dict, Any
# from pydantic import BaseModel, Field
# from bson import ObjectId


# class Workflow(BaseModel):
#     """Workflow Model"""
#     id: Optional[str] = Field(None, alias="_id")
#     user_id: str
#     name: str
#     description: Optional[str] = None
    
#     # Workflow definition
#     nodes: List[Dict[str, Any]] = []  # Workflow nodes
#     edges: List[Dict[str, Any]] = []  # Connections between nodes
    
#     # Status
#     is_active: bool = True
#     version: int = 1
    
#     # Stats
#     execution_count: int = 0
#     success_count: int = 0
#     failure_count: int = 0
    
#     # Settings
#     max_nodes: int = 50
#     execution_timeout: int = 600  # seconds
    
#     # Metadata
#     metadata: Optional[Dict[str, Any]] = {}
    
#     # Timestamps
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#     updated_at: datetime = Field(default_factory=datetime.utcnow)
    
#     class Config:
#         populate_by_name = True
#         json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


# class WorkflowExecution(BaseModel):
#     """Workflow Execution Log"""
#     id: Optional[str] = Field(None, alias="_id")
#     workflow_id: str
#     user_id: str
    
#     status: str  # running, completed, failed
#     input_data: Dict[str, Any] = {}
#     output_data: Optional[Dict[str, Any]] = None
    
#     nodes_executed: List[str] = []
#     error_message: Optional[str] = None
    
#     started_at: datetime = Field(default_factory=datetime.utcnow)
#     completed_at: Optional[datetime] = None
#     duration_seconds: Optional[float] = None
    
#     class Config:
#         populate_by_name = True
#         json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


# backend/app/models/workflow.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class WorkflowNode(BaseModel):
    """Workflow node structure"""
    id: str
    type: str  # begin, welcome, question, response, appointment
    x: int
    y: int
    data: Dict[str, Any]


class WorkflowConnection(BaseModel):
    """Connection between nodes"""
    id: str
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    transition: Optional[str] = None  # Keyword for matching


class WorkflowAppointmentRules(BaseModel):
    """Appointment booking rules"""
    enabled: bool = False
    working_hours: Dict[str, str] = {"start": "09:00", "end": "17:00"}
    slot_duration: int = 60  # minutes
    buffer_time: int = 15  # minutes between appointments
    required_fields: List[str] = ["name", "phone", "email", "date", "time"]
    service_types: List[str] = []


class Workflow(BaseModel):
    """Campaign Builder Workflow Model"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    
    # Workflow structure
    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []
    
    # Appointment rules
    appointment_rules: Optional[WorkflowAppointmentRules] = None
    working_hours: Optional[Dict[str, str]] = None
    
    # Status
    active: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}