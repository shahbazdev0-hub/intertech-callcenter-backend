# backend/app/api/v1/automation.py - MILESTONE 3 COMPLETE

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime

from app.schemas.automation import (
    AutomationCreate,
    AutomationUpdate,
    AutomationResponse,
    AutomationStats,
    TriggerAutomationRequest
)
from app.api.deps import get_current_user
from app.database import get_database
from app.services.automation import automation_service
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict)
async def get_automations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get all automations for the current user"""
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"Fetching automations for user: {user_id}")
        
        # Build query
        query = {"user_id": user_id}
        if is_active is not None:
            query["is_active"] = is_active
        if trigger_type:
            query["trigger_type"] = trigger_type
        
        # Get total count
        total = await db.automations.count_documents(query)
        
        # Get automations
        cursor = db.automations.find(query).sort("created_at", -1).skip(skip).limit(limit)
        automations = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for auto in automations:
            auto["_id"] = str(auto["_id"])
            auto["id"] = str(auto["_id"])
        
        logger.info(f"Found {total} automations for user {user_id}")
        
        return {
            "automations": automations,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching automations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats", response_model=dict)
async def get_automation_stats(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get automation statistics for the current user"""
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"Fetching automation stats for user: {user_id}")
        
        # Total automations
        total_automations = await db.automations.count_documents({"user_id": user_id})
        
        # Active automations
        active_automations = await db.automations.count_documents({
            "user_id": user_id,
            "is_active": True
        })
        
        # Get execution stats
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_executions": {"$sum": "$execution_count"},
                "successful_executions": {"$sum": "$success_count"},
                "failed_executions": {"$sum": "$failure_count"}
            }}
        ]
        
        stats_cursor = db.automations.aggregate(pipeline)
        stats_list = await stats_cursor.to_list(length=1)
        
        if stats_list:
            stats = stats_list[0]
        else:
            stats = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0
            }
        
        result = {
            "total_automations": total_automations,
            "active_automations": active_automations,
            "total_executions": stats["total_executions"],
            "successful_executions": stats["successful_executions"],
            "failed_executions": stats["failed_executions"]
        }
        
        logger.info(f"Automation stats for user {user_id}: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching automation stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{automation_id}", response_model=dict)
async def get_automation(
    automation_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get a specific automation"""
    try:
        user_id = str(current_user["_id"])
        
        automation = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        automation["_id"] = str(automation["_id"])
        automation["id"] = str(automation["_id"])
        
        return automation
        
    except Exception as e:
        logger.error(f"Error fetching automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_automation(
    automation: AutomationCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Create a new automation"""
    try:
        user_id = str(current_user["_id"])
        
        automation_data = {
            "user_id": user_id,
            "name": automation.name,
            "description": automation.description,
            "trigger_type": automation.trigger_type,
            "trigger_config": automation.trigger_config,
            "actions": [action.dict() for action in automation.actions],
            "is_active": automation.is_active,
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_executed_at": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.automations.insert_one(automation_data)
        automation_data["_id"] = str(result.inserted_id)
        automation_data["id"] = str(result.inserted_id)
        
        logger.info(f"Created automation {result.inserted_id} for user {user_id}")
        
        return {
            "message": "Automation created successfully",
            "automation": automation_data
        }
        
    except Exception as e:
        logger.error(f"Error creating automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{automation_id}", response_model=dict)
async def update_automation(
    automation_id: str,
    automation: AutomationUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Update an automation"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if automation exists
        existing = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        # Build update data
        update_data = {"updated_at": datetime.utcnow()}
        
        if automation.name is not None:
            update_data["name"] = automation.name
        if automation.description is not None:
            update_data["description"] = automation.description
        if automation.trigger_type is not None:
            update_data["trigger_type"] = automation.trigger_type
        if automation.trigger_config is not None:
            update_data["trigger_config"] = automation.trigger_config
        if automation.actions is not None:
            update_data["actions"] = [action.dict() for action in automation.actions]
        if automation.is_active is not None:
            update_data["is_active"] = automation.is_active
        
        # Update automation
        await db.automations.update_one(
            {"_id": ObjectId(automation_id)},
            {"$set": update_data}
        )
        
        logger.info(f"Updated automation {automation_id}")
        
        return {"message": "Automation updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{automation_id}", response_model=dict)
async def delete_automation(
    automation_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete an automation"""
    try:
        user_id = str(current_user["_id"])
        
        result = await db.automations.delete_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        logger.info(f"Deleted automation {automation_id}")
        
        return {"message": "Automation deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{automation_id}/trigger", response_model=dict)
async def trigger_automation(
    automation_id: str,
    trigger_data: TriggerAutomationRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Manually trigger an automation"""
    try:
        user_id = str(current_user["_id"])
        
        # Get automation
        automation = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        # Trigger automation via service
        result = await automation_service.trigger_automation(
            automation_id=automation_id,
            trigger_data=trigger_data.dict()
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error triggering automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{automation_id}/test", response_model=dict)
async def test_automation(
    automation_id: str,
    test_data: dict,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Test an automation without executing actions"""
    try:
        user_id = str(current_user["_id"])
        
        automation = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        return {
            "message": "Test successful",
            "automation": automation["name"],
            "would_execute": len(automation["actions"]),
            "actions": automation["actions"]
        }
        
    except Exception as e:
        logger.error(f"Error testing automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{automation_id}/toggle", response_model=dict)
async def toggle_automation(
    automation_id: str,
    is_active: bool = Query(...),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Toggle automation active status"""
    try:
        user_id = str(current_user["_id"])
        
        result = await db.automations.update_one(
            {
                "_id": ObjectId(automation_id),
                "user_id": user_id
            },
            {
                "$set": {
                    "is_active": is_active,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        logger.info(f"Toggled automation {automation_id} to {is_active}")
        
        return {
            "message": f"Automation {'activated' if is_active else 'deactivated'} successfully"
        }
        
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{automation_id}/logs", response_model=dict)
async def get_automation_logs(
    automation_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get execution logs for an automation"""
    try:
        user_id = str(current_user["_id"])
        
        # Verify automation belongs to user
        automation = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )
        
        # Get logs
        query = {"automation_id": automation_id}
        total = await db.automation_logs.count_documents(query)
        
        cursor = db.automation_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        for log in logs:
            log["_id"] = str(log["_id"])
        
        return {
            "logs": logs,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching automation logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )