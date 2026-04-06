# backend/app/api/v1/business_profile.py - Business Profile CRUD API

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from app.api.deps import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# PYDANTIC MODELS
# ============================================

class ServiceItem(BaseModel):
    name: str
    description: Optional[str] = ""
    price: Optional[str] = ""

class FAQItem(BaseModel):
    question: str
    answer: str

class BusinessProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    industry: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    working_hours: Optional[str] = None
    services: Optional[List[ServiceItem]] = None
    faqs: Optional[List[FAQItem]] = None
    custom_ai_instructions: Optional[str] = None


# ============================================
# GET BUSINESS PROFILE
# ============================================
@router.get("/")
async def get_business_profile(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get the business profile for the current user"""
    user_id = str(current_user["_id"])

    profile = await db.business_profiles.find_one({"user_id": user_id})

    if not profile:
        # Return empty profile structure
        return {
            "exists": False,
            "profile": {
                "company_name": current_user.get("company", ""),
                "company_description": "",
                "industry": "",
                "contact_phone": "",
                "contact_email": current_user.get("email", ""),
                "website": "",
                "address": "",
                "working_hours": "",
                "services": [],
                "faqs": [],
                "custom_ai_instructions": ""
            }
        }

    # Convert ObjectId
    profile["id"] = str(profile.pop("_id"))
    return {"exists": True, "profile": profile}


# ============================================
# CREATE / UPDATE BUSINESS PROFILE
# ============================================
@router.put("/")
async def update_business_profile(
    data: BusinessProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Create or update the business profile"""
    user_id = str(current_user["_id"])

    update_data = data.model_dump(exclude_unset=True)
    update_data["user_id"] = user_id
    update_data["updated_at"] = datetime.utcnow()

    # Convert service/faq pydantic models to dicts
    if "services" in update_data:
        update_data["services"] = [s if isinstance(s, dict) else s for s in update_data["services"]]
    if "faqs" in update_data:
        update_data["faqs"] = [f if isinstance(f, dict) else f for f in update_data["faqs"]]

    existing = await db.business_profiles.find_one({"user_id": user_id})

    if existing:
        await db.business_profiles.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    else:
        update_data["created_at"] = datetime.utcnow()
        await db.business_profiles.insert_one(update_data)

    # Fetch updated profile
    profile = await db.business_profiles.find_one({"user_id": user_id})
    profile["id"] = str(profile.pop("_id"))

    return {"success": True, "message": "Business profile updated", "profile": profile}


# ============================================
# HELPER: Build AI system prompt from profile
# ============================================
async def get_business_context_for_ai(user_id: str, db=None) -> str:
    """
    Build a dynamic system prompt section from the user's business profile.
    Used by email poller, SMS handler, and other AI response generators.
    Returns a string to inject into the system prompt.
    """
    if db is None:
        db = await get_database()

    profile = await db.business_profiles.find_one({"user_id": user_id})

    if not profile:
        print(f"[BUSINESS-PROFILE] No profile found for user_id: {user_id}")
        return ""

    print(f"[BUSINESS-PROFILE] Found profile for user_id: {user_id} - Company: {profile.get('company_name')}")

    parts = []

    company_name = profile.get("company_name")
    if company_name:
        parts.append(f"You work for {company_name}.")

    description = profile.get("company_description")
    if description:
        parts.append(f"About the company: {description}")

    industry = profile.get("industry")
    if industry:
        parts.append(f"Industry: {industry}")

    # Services
    services = profile.get("services", [])
    if services:
        service_lines = []
        for s in services:
            name = s.get("name", "")
            desc = s.get("description", "")
            price = s.get("price", "")
            line = f"- {name}"
            if desc:
                line += f": {desc}"
            if price:
                line += f" (Price: {price})"
            service_lines.append(line)
        parts.append("Services offered:\n" + "\n".join(service_lines))

    # Contact info
    contact_parts = []
    if profile.get("contact_phone"):
        contact_parts.append(f"Phone: {profile['contact_phone']}")
    if profile.get("contact_email"):
        contact_parts.append(f"Email: {profile['contact_email']}")
    if profile.get("website"):
        contact_parts.append(f"Website: {profile['website']}")
    if profile.get("address"):
        contact_parts.append(f"Address: {profile['address']}")
    if contact_parts:
        parts.append("Contact information:\n" + "\n".join(contact_parts))

    # Working hours
    if profile.get("working_hours"):
        parts.append(f"Working hours: {profile['working_hours']}")

    # FAQs
    faqs = profile.get("faqs", [])
    if faqs:
        faq_lines = []
        for f in faqs:
            faq_lines.append(f"Q: {f.get('question', '')}\nA: {f.get('answer', '')}")
        parts.append("Frequently Asked Questions:\n" + "\n\n".join(faq_lines))

    # Custom AI instructions
    if profile.get("custom_ai_instructions"):
        parts.append(f"Additional instructions: {profile['custom_ai_instructions']}")

    return "\n\n".join(parts)
