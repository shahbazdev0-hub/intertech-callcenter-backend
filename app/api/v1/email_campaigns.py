# backend/app/api/v1/email_campaigns.py - Bulk Email Campaign API

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Optional, List
import logging

from app.api.deps import get_current_user, get_database
from app.schemas.email_campaign import (
    EmailCampaignCreateRequest,
    EmailCampaignResponse,
    EmailCampaignDetailResponse,
    EmailCampaignStartRequest,
    EmailCampaignStatusResponse,
    EmailRecipientInput
)
from app.services.email_campaign_service import email_campaign_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# CREATE CAMPAIGN
# ============================================

@router.post("/create", response_model=EmailCampaignDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    request: EmailCampaignCreateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Create new bulk email campaign"""
    try:
        user_id = str(current_user["_id"])

        recipients = [
            {"email": r.email, "name": r.name}
            for r in request.recipients
        ]

        result = await email_campaign_service.create_campaign(
            user_id=user_id,
            campaign_id=request.campaign_id,
            subject=request.subject,
            message=request.message,
            recipients=recipients,
            campaign_name=request.campaign_name,
            batch_size=request.batch_size,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )

        campaign = result["campaign"]

        return EmailCampaignDetailResponse(
            _id=campaign["_id"],
            user_id=campaign["user_id"],
            campaign_id=campaign["campaign_id"],
            campaign_name=campaign.get("campaign_name"),
            subject=campaign["subject"],
            message=campaign["message"],
            total_recipients=campaign["total_recipients"],
            sent_count=campaign["sent_count"],
            failed_count=campaign["failed_count"],
            status=campaign["status"],
            recipients=campaign["recipients"],
            batch_size=campaign["batch_size"],
            current_batch=campaign["current_batch"],
            total_batches=campaign["total_batches"],
            errors=campaign["errors"],
            created_at=campaign["created_at"],
            started_at=campaign.get("started_at"),
            completed_at=campaign.get("completed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating email campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# UPLOAD CSV
# ============================================

@router.post("/upload-csv/{campaign_id}")
async def upload_csv(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Upload CSV file with email recipients"""
    try:
        user_id = str(current_user["_id"])

        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported"
            )

        content = await file.read()
        result = await email_campaign_service.parse_csv_file(content, file.filename)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )

        recipients = result["recipients"]

        add_result = await email_campaign_service.add_recipients_to_campaign(
            campaign_id=campaign_id,
            user_id=user_id,
            recipients=recipients,
            source="csv"
        )

        if not add_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=add_result.get("error")
            )

        return {
            "success": True,
            "message": "CSV uploaded successfully",
            "added_count": add_result["added_count"],
            "duplicates": add_result["duplicates"],
            "total_recipients": add_result["total_recipients"],
            "row_errors": result.get("row_errors", []),
            "detected_columns": result.get("detected_columns")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# ADD MANUAL RECIPIENTS
# ============================================

@router.post("/add-recipients/{campaign_id}")
async def add_manual_recipients(
    campaign_id: str,
    recipients: List[EmailRecipientInput],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Add email recipients manually to campaign"""
    try:
        user_id = str(current_user["_id"])

        recipient_dicts = [
            {"email": r.email, "name": r.name}
            for r in recipients
        ]

        result = await email_campaign_service.add_recipients_to_campaign(
            campaign_id=campaign_id,
            user_id=user_id,
            recipients=recipient_dicts,
            source="manual"
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )

        return {
            "success": True,
            "message": "Recipients added successfully",
            "added_count": result["added_count"],
            "duplicates": result.get("duplicates", 0),
            "total_recipients": result["total_recipients"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding email recipients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# START CAMPAIGN
# ============================================

@router.post("/start/{campaign_id}")
async def start_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Start sending email campaign"""
    try:
        user_id = str(current_user["_id"])

        result = await email_campaign_service.start_campaign(
            campaign_id=campaign_id,
            user_id=user_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )

        return {
            "success": True,
            "message": "Email campaign started successfully",
            "campaign_id": campaign_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting email campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# GET CAMPAIGN STATUS
# ============================================

@router.get("/status/{campaign_id}", response_model=EmailCampaignStatusResponse)
async def get_campaign_status(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get real-time email campaign status"""
    try:
        user_id = str(current_user["_id"])

        campaign = await email_campaign_service.get_campaign(campaign_id, user_id)

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        total = campaign["total_recipients"]
        sent = campaign["sent_count"]
        progress = (sent / total * 100) if total > 0 else 0

        return EmailCampaignStatusResponse(
            campaign_id=campaign["campaign_id"],
            status=campaign["status"],
            total_recipients=total,
            sent_count=sent,
            failed_count=campaign["failed_count"],
            current_batch=campaign["current_batch"],
            total_batches=campaign["total_batches"],
            progress_percentage=round(progress, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email campaign status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# GET CAMPAIGN DETAILS
# ============================================

@router.get("/{campaign_id}", response_model=EmailCampaignDetailResponse)
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get full email campaign details including recipients"""
    try:
        user_id = str(current_user["_id"])

        campaign = await email_campaign_service.get_campaign(campaign_id, user_id)

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        return EmailCampaignDetailResponse(**campaign)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# LIST CAMPAIGNS
# ============================================

@router.get("/", response_model=List[EmailCampaignResponse])
async def list_campaigns(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """List all email campaigns for user"""
    try:
        user_id = str(current_user["_id"])

        campaigns = await email_campaign_service.get_campaigns(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status
        )

        return [EmailCampaignResponse(**c) for c in campaigns]

    except Exception as e:
        logger.error(f"Error listing email campaigns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# DELETE CAMPAIGN
# ============================================

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """Delete email campaign (only if not in progress)"""
    try:
        user_id = str(current_user["_id"])

        success = await email_campaign_service.delete_campaign(campaign_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete campaign (not found or in progress)"
            )

        return {
            "success": True,
            "message": "Email campaign deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting email campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
