

# backend/app/api/v1/sms_campaigns.py with custom prompt ai 
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from app.api.deps import get_current_user, get_database
from app.schemas.sms_campaign import (
    SMSCampaignCreateRequest,
    SMSCampaignResponse,
    SMSCampaignDetailResponse,
    SMSCampaignStartRequest,
    SMSCampaignStatusResponse,
    RecipientInput
)
from app.services.sms_campaign import sms_campaign_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# CREATE CAMPAIGN
# ============================================

@router.post("/create", response_model=SMSCampaignDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    request: SMSCampaignCreateRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Create new bulk SMS campaign
    
    Edge cases handled:
    - Validates campaign_id uniqueness
    - Cleans and validates all phone numbers
    - Handles empty recipient list
    - Removes duplicate phone numbers
    - 🆕 Validates and stores custom AI script
    """
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"📝 Creating campaign: {request.campaign_id}")
        
        # Convert recipients
        recipients = [
            {"phone_number": r.phone_number, "name": r.name}
            for r in request.recipients
        ]
        
        # Create campaign
        result = await sms_campaign_service.create_campaign(
            user_id=user_id,
            campaign_id=request.campaign_id,
            message=request.message,
            from_number=request.from_number,
            recipients=recipients,
            campaign_name=request.campaign_name,
            batch_size=request.batch_size,
            enable_replies=request.enable_replies,
            track_responses=request.track_responses,
            custom_ai_script=request.custom_ai_script  # 🆕 PASS CUSTOM SCRIPT
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )
        
        campaign = result["campaign"]
        
        return SMSCampaignDetailResponse(
            _id=campaign["_id"],
            user_id=campaign["user_id"],
            campaign_id=campaign["campaign_id"],
            campaign_name=campaign.get("campaign_name"),
            message=campaign["message"],
            from_number=campaign["from_number"],
            custom_ai_script=campaign.get("custom_ai_script"),  # 🆕 INCLUDE IN RESPONSE
            total_recipients=campaign["total_recipients"],
            sent_count=campaign["sent_count"],
            delivered_count=campaign["delivered_count"],
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
        logger.error(f"Error creating campaign: {e}")
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
    db = Depends(get_database)
):
    """
    Upload CSV file with recipients
    
    Edge cases handled:
    - Validates file type (.csv)
    - Handles different CSV formats
    - Auto-detects phone and name columns
    - Validates all phone numbers
    - Removes duplicates
    - Returns detailed error report
    """
    try:
        user_id = str(current_user["_id"])
        
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Parse CSV
        result = await sms_campaign_service.parse_csv_file(content, file.filename)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error")
            )
        
        recipients = result["recipients"]
        
        # Add recipients to campaign
        add_result = await sms_campaign_service.add_recipients_to_campaign(
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
            "validation": result["validation"],
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
    recipients: List[RecipientInput],
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Add recipients manually to campaign
    
    Edge cases handled:
    - Validates all phone numbers
    - Removes duplicates
    - Campaign must be in pending status
    """
    try:
        user_id = str(current_user["_id"])
        
        recipient_dicts = [
            {"phone_number": r.phone_number, "name": r.name}
            for r in recipients
        ]
        
        result = await sms_campaign_service.add_recipients_to_campaign(
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
        logger.error(f"Error adding recipients: {e}")
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
    db = Depends(get_database)
):
    """
    Start sending campaign
    
    Edge cases handled:
    - Campaign must be in pending status
    - Must have at least one recipient
    - Validates Twilio configuration
    """
    try:
        user_id = str(current_user["_id"])
        
        result = await sms_campaign_service.start_campaign(
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
            "message": "Campaign started successfully",
            "campaign_id": campaign_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# GET CAMPAIGN STATUS
# ============================================

@router.get("/status/{campaign_id}", response_model=SMSCampaignStatusResponse)
async def get_campaign_status(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get real-time campaign status
    """
    try:
        user_id = str(current_user["_id"])
        
        campaign = await sms_campaign_service.get_campaign(campaign_id, user_id)
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Calculate progress
        total = campaign["total_recipients"]
        sent = campaign["sent_count"]
        progress = (sent / total * 100) if total > 0 else 0
        
        # Estimate time remaining
        estimated_time = None
        if campaign["status"] == "in_progress" and sent > 0:
            # Rough estimate: 1 second per message + batch delays
            remaining = total - sent
            estimated_time = remaining * 1 + (remaining // campaign["batch_size"]) * 10
        
        return SMSCampaignStatusResponse(
            campaign_id=campaign["campaign_id"],
            status=campaign["status"],
            total_recipients=total,
            sent_count=sent,
            delivered_count=campaign["delivered_count"],
            failed_count=campaign["failed_count"],
            current_batch=campaign["current_batch"],
            total_batches=campaign["total_batches"],
            progress_percentage=round(progress, 2),
            estimated_time_remaining=estimated_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# GET CAMPAIGN DETAILS
# ============================================

@router.get("/{campaign_id}", response_model=SMSCampaignDetailResponse)
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get full campaign details including recipients"""
    try:
        user_id = str(current_user["_id"])
        
        campaign = await sms_campaign_service.get_campaign(campaign_id, user_id)
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        return SMSCampaignDetailResponse(**campaign)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# LIST CAMPAIGNS
# ============================================

@router.get("/", response_model=List[SMSCampaignResponse])
async def list_campaigns(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """List all campaigns for user"""
    try:
        user_id = str(current_user["_id"])
        
        campaigns = await sms_campaign_service.get_campaigns(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status
        )
        
        return [SMSCampaignResponse(**c) for c in campaigns]
    
    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
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
    db = Depends(get_database)
):
    """
    Delete campaign
    
    Edge case: Can only delete if not in progress
    """
    try:
        user_id = str(current_user["_id"])
        
        success = await sms_campaign_service.delete_campaign(campaign_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete campaign (not found or in progress)"
            )
        
        return {
            "success": True,
            "message": "Campaign deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )