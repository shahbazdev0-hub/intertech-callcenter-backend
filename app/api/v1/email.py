# backend/app/api/v1/email.py - MILESTONE 3 COMPLETE FIXED

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Optional
from datetime import datetime

from app.schemas.email import (
    EmailCampaignCreate,
    EmailCampaignUpdate,
    EmailCampaignResponse,
    EmailTemplateCreate,
    EmailTemplateResponse,
    SendEmailRequest
)
from app.api.deps import get_current_user
from app.database import get_database
from app.services.email_automation import email_service
from app.tasks.email_tasks import send_campaign_task
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/campaigns", response_model=dict)
async def get_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get all email campaigns for the current user"""
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"Fetching campaigns for user: {user_id}")
        
        # Build query
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        # Get total count
        total = await db.email_campaigns.count_documents(query)
        
        # Get campaigns
        cursor = db.email_campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
        campaigns = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for campaign in campaigns:
            campaign["_id"] = str(campaign["_id"])
            campaign["id"] = str(campaign["_id"])
        
        logger.info(f"Found {total} campaigns for user {user_id}")
        
        return {
            "campaigns": campaigns,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/campaigns/{campaign_id}", response_model=dict)
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get a specific campaign"""
    try:
        user_id = str(current_user["_id"])
        
        campaign = await db.email_campaigns.find_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        campaign["_id"] = str(campaign["_id"])
        campaign["id"] = str(campaign["_id"])
        
        return campaign
        
    except Exception as e:
        logger.error(f"Error fetching campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/campaigns", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign: EmailCampaignCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Create a new email campaign"""
    try:
        user_id = str(current_user["_id"])
        
        campaign_data = {
            "user_id": user_id,
            "name": campaign.name,
            "subject": campaign.subject,
            "content": campaign.content,
            "recipients": campaign.recipients,
            "status": "draft",
            "send_immediately": campaign.send_immediately,
            "scheduled_at": campaign.scheduled_at,
            "recipient_count": len(campaign.recipients),
            "sent_count": 0,
            "delivered_count": 0,
            "opened_count": 0,
            "clicked_count": 0,
            "failed_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.email_campaigns.insert_one(campaign_data)
        campaign_data["_id"] = str(result.inserted_id)
        campaign_data["id"] = str(result.inserted_id)
        
        logger.info(f"Created campaign {result.inserted_id} for user {user_id}")
        
        return {
            "message": "Campaign created successfully",
            "campaign": campaign_data
        }
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/campaigns/{campaign_id}", response_model=dict)
async def update_campaign(
    campaign_id: str,
    campaign: EmailCampaignUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Update a campaign"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if campaign exists
        existing = await db.email_campaigns.find_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Build update data
        update_data = {"updated_at": datetime.utcnow()}
        
        if campaign.name is not None:
            update_data["name"] = campaign.name
        if campaign.subject is not None:
            update_data["subject"] = campaign.subject
        if campaign.content is not None:
            update_data["content"] = campaign.content
        if campaign.recipients is not None:
            update_data["recipients"] = campaign.recipients
            update_data["recipient_count"] = len(campaign.recipients)
        if campaign.scheduled_at is not None:
            update_data["scheduled_at"] = campaign.scheduled_at
        
        # Update campaign
        await db.email_campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": update_data}
        )
        
        logger.info(f"Updated campaign {campaign_id}")
        
        return {"message": "Campaign updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/campaigns/{campaign_id}", response_model=dict)
async def delete_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete a campaign"""
    try:
        user_id = str(current_user["_id"])
        
        result = await db.email_campaigns.delete_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        logger.info(f"Deleted campaign {campaign_id}")
        
        return {"message": "Campaign deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/campaigns/{campaign_id}/send", response_model=dict)
async def send_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Send a campaign"""
    try:
        user_id = str(current_user["_id"])
        
        # Get campaign
        campaign = await db.email_campaigns.find_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        if campaign["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign has already been sent or is in progress"
            )
        
        # Update status to sending
        await db.email_campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {
                "$set": {
                    "status": "sending",
                    "sent_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Queue campaign for sending
        send_campaign_task.delay(campaign_id, user_id)
        
        logger.info(f"Campaign {campaign_id} queued for sending")
        
        return {
            "message": "Campaign queued for sending",
            "campaign_id": campaign_id
        }
        
    except Exception as e:
        logger.error(f"Error sending campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send", response_model=dict)
async def send_email(
    email_request: SendEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a single email"""
    try:
        user_id = str(current_user["_id"])
        
        result = await email_service.send_email(
            to_email=email_request.to_email,
            subject=email_request.subject,
            content=email_request.content,
            user_id=user_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/templates", response_model=dict)
async def get_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get all email templates for the current user"""
    try:
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        
        # Get total count
        total = await db.email_templates.count_documents(query)
        
        # Get templates
        cursor = db.email_templates.find(query).sort("created_at", -1).skip(skip).limit(limit)
        templates = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for template in templates:
            template["_id"] = str(template["_id"])
            template["id"] = str(template["_id"])
        
        return {
            "templates": templates,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/templates", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: EmailTemplateCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Create a new email template"""
    try:
        user_id = str(current_user["_id"])
        
        template_data = {
            "user_id": user_id,
            "name": template.name,
            "subject": template.subject,
            "content": template.content,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.email_templates.insert_one(template_data)
        template_data["_id"] = str(result.inserted_id)
        template_data["id"] = str(result.inserted_id)
        
        logger.info(f"Created email template {result.inserted_id} for user {user_id}")
        
        return {
            "message": "Template created successfully",
            "template": template_data
        }
        
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )