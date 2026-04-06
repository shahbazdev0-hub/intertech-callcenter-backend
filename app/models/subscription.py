# backend/app/models/subscription.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class SubscriptionPlan(BaseModel):
    name: str
    price: float
    billing_cycle: str  # monthly, yearly
    features: List[str]
    max_calls: int
    max_users: int
    support_level: str

class Subscription(BaseModel):
    id: Optional[str] = Field(default_factory=str, alias="_id")
    user_id: str
    plan_name: str
    status: str  # active, cancelled, expired, trial
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    usage_stats: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}