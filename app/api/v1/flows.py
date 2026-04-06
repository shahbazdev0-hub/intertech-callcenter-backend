# backend/app/api/v1/flows.py - NEW FILE FOR AI CAMPAIGN WORKFLOWS

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
import logging

from app.api.deps import get_current_user, get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# PYDANTIC SCHEMAS
# ============================================

class FlowCreate(BaseModel):
    """Schema for creating a campaign flow"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    active: bool = True


class FlowUpdate(BaseModel):
    """Schema for updating a campaign flow"""
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    connections: Optional[List[Dict[str, Any]]] = None
    active: Optional[bool] = None


# ============================================
# ENDPOINTS
# ============================================

@router.get("/")
async def get_flows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all campaign flows for current user"""
    try:
        user_id = str(current_user["_id"])
        
        # Build query
        query = {"user_id": user_id}
        if active is not None:
            query["active"] = active
        
        # Get total count
        total = await db.flows.count_documents(query)
        
        # Get flows
        cursor = db.flows.find(query).sort("created_at", -1).skip(skip).limit(limit)
        flows = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for flow in flows:
            flow["_id"] = str(flow["_id"])
        
        logger.info(f"✅ Retrieved {len(flows)} flows for user {user_id}")
        
        return {
            "flows": flows,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching flows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{flow_id}")
async def get_flow(
    flow_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific campaign flow"""
    try:
        if not ObjectId.is_valid(flow_id):
            raise HTTPException(status_code=400, detail="Invalid flow ID")
        
        user_id = str(current_user["_id"])
        
        flow = await db.flows.find_one({
            "_id": ObjectId(flow_id),
            "user_id": user_id
        })
        
        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )
        
        flow["_id"] = str(flow["_id"])
        
        return flow
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/")
async def create_flow(
    flow_data: FlowCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new campaign flow"""
    try:
        user_id = str(current_user["_id"])
        
        # Create flow document
        flow_dict = {
            "user_id": user_id,
            "name": flow_data.name,
            "description": flow_data.description,
            "nodes": flow_data.nodes,
            "connections": flow_data.connections,
            "active": flow_data.active,
            "version": 1,
            "total_uses": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert into database
        result = await db.flows.insert_one(flow_dict)
        flow_dict["_id"] = str(result.inserted_id)
        
        logger.info(f"✅ Created flow: {flow_data.name} (ID: {result.inserted_id})")
        
        return flow_dict
        
    except Exception as e:
        logger.error(f"❌ Error creating flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{flow_id}")
async def update_flow(
    flow_id: str,
    flow_data: FlowUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update an existing campaign flow"""
    try:
        if not ObjectId.is_valid(flow_id):
            raise HTTPException(status_code=400, detail="Invalid flow ID")
        
        user_id = str(current_user["_id"])
        
        # Check if flow exists
        existing = await db.flows.find_one({
            "_id": ObjectId(flow_id),
            "user_id": user_id
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )
        
        # Build update data
        update_data = {"updated_at": datetime.utcnow()}
        
        if flow_data.name is not None:
            update_data["name"] = flow_data.name
        if flow_data.description is not None:
            update_data["description"] = flow_data.description
        if flow_data.nodes is not None:
            update_data["nodes"] = flow_data.nodes
            update_data["version"] = existing.get("version", 1) + 1
        if flow_data.connections is not None:
            update_data["connections"] = flow_data.connections
        if flow_data.active is not None:
            update_data["active"] = flow_data.active
        
        # Update flow
        await db.flows.update_one(
            {"_id": ObjectId(flow_id)},
            {"$set": update_data}
        )
        
        logger.info(f"✅ Updated flow: {flow_id}")
        
        return {"message": "Flow updated successfully", "flow_id": flow_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{flow_id}")
async def delete_flow(
    flow_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a campaign flow"""
    try:
        if not ObjectId.is_valid(flow_id):
            raise HTTPException(status_code=400, detail="Invalid flow ID")
        
        user_id = str(current_user["_id"])
        
        result = await db.flows.delete_one({
            "_id": ObjectId(flow_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )
        
        logger.info(f"✅ Deleted flow: {flow_id}")
        
        return {"message": "Flow deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )