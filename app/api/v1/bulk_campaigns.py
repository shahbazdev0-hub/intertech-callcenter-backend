# backend/app/api/v1/bulk_campaigns.py - 
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from app.api.deps import get_current_user, get_database
from app.schemas.bulk_campaign import (
    BulkCampaignCreate,
    ManualRecipientsAdd,
    CampaignStartRequest
)
from app.services.bulk_call_service import BulkCallService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/bulk-campaigns", status_code=status.HTTP_201_CREATED)
async def create_bulk_campaign(
    campaign_data: BulkCampaignCreate,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create new bulk call campaign"""
    try:
        # ✅ FIXED: Access dict key instead of object attribute
        user_email = current_user.get("email", "unknown")
        user_id = str(current_user["_id"])  # ✅ FIXED: Use _id from dict
        
        logger.info(f"Creating bulk campaign for user: {user_email}")
        
        bulk_service = BulkCallService(db)
        campaign = await bulk_service.create_campaign(
            user_id=user_id,  # ✅ FIXED: Use extracted user_id
            campaign_data=campaign_data.dict()
        )
        
        return {
            'success': True,
            'message': 'Campaign created successfully',
            'campaign': campaign.dict(by_alias=True)
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating campaign: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/upload-csv")
async def upload_csv_recipients(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Upload CSV/Excel file with recipients"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Uploading CSV for campaign: {campaign_id}")
        
        # Validate file type
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Please upload CSV or Excel file."
            )
        
        # Read file content
        contents = await file.read()
        
        bulk_service = BulkCallService(db)
        result = await bulk_service.upload_csv_recipients(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id,
            file_content=contents,
            filename=file.filename
        )
        
        return result
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading CSV: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading CSV: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/add-manual")
async def add_manual_recipients(
    campaign_id: str,
    recipients_data: ManualRecipientsAdd,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add recipients manually"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Adding manual recipients to campaign: {campaign_id}")
        
        bulk_service = BulkCallService(db)
        result = await bulk_service.add_manual_recipients(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id,
            recipients=recipients_data.recipients
        )
        
        return result
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding recipients: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error adding recipients: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    start_request: CampaignStartRequest,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Start bulk calling campaign"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Starting campaign: {campaign_id}")
        bulk_service = BulkCallService(db)

        result = await bulk_service.start_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id,
            max_concurrent_calls=start_request.max_concurrent_calls
        )
        
        return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting campaign: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Pause running campaign"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Pausing campaign: {campaign_id}")
        bulk_service = BulkCallService(db)

        result = await bulk_service.pause_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        
        return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error pausing campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error pausing campaign: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Resume paused campaign"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Resuming campaign: {campaign_id}")
        bulk_service = BulkCallService(db)

        result = await bulk_service.resume_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        
        return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error resuming campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resuming campaign: {str(e)}")


@router.post("/bulk-campaigns/{campaign_id}/stop")
async def stop_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Stop campaign completely"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Stopping campaign: {campaign_id}")
        bulk_service = BulkCallService(db)

        result = await bulk_service.stop_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        
        return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error stopping campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error stopping campaign: {str(e)}")


@router.get("/bulk-campaigns/{campaign_id}/status")
async def get_campaign_status(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get campaign progress and statistics"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        bulk_service = BulkCallService(db)
        status_data = await bulk_service.get_campaign_status(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        return status_data

    except ValueError as e:
        logger.error(f"Campaign not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.get("/bulk-campaigns/{campaign_id}/recipients")
async def get_campaign_recipients(
    campaign_id: str,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get list of recipients with call status"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        bulk_service = BulkCallService(db)
        recipients = await bulk_service.get_campaign_recipients(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id,
            skip=skip,
            limit=limit
        )
        return {
            'success': True,
            'recipients': recipients,
            'count': len(recipients)
        }

    except Exception as e:
        logger.error(f"Error getting recipients: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting recipients: {str(e)}")


@router.get("/bulk-campaigns")
async def get_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all bulk campaigns for current user"""
    try:
        user_id = str(current_user["_id"])
        
        # Get campaigns
        campaigns = await db.bulk_campaigns.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
        
        # Convert ObjectIds to strings
        for campaign in campaigns:
            campaign["_id"] = str(campaign["_id"])
            if campaign.get("workflow_id"):
                campaign["workflow_id"] = str(campaign["workflow_id"])
        
        # Get total count
        total = await db.bulk_campaigns.count_documents({"user_id": user_id})
        
        return {
            "campaigns": campaigns,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/bulk-campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get campaign details"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        bulk_service = BulkCallService(db)
        campaign = await bulk_service.get_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return {
            'success': True,
            'campaign': campaign
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting campaign: {str(e)}")


@router.delete("/bulk-campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),  # ✅ Changed from User to dict
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a campaign"""
    try:
        user_id = str(current_user["_id"])  # ✅ FIXED
        logger.info(f"Deleting campaign: {campaign_id}")
        
        bulk_service = BulkCallService(db)
        result = await bulk_service.delete_campaign(
            user_id=user_id,  # ✅ FIXED
            campaign_id=campaign_id
        )
        
        return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting campaign: {str(e)}")