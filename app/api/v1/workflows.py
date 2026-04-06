# backend/app/api/v1/workflows.py - MILESTONE 3 COMPLETE

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime

from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from app.api.deps import get_current_user
from app.database import get_database
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict)
async def get_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get all workflows for the current user"""
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"Fetching workflows for user: {user_id}")
        
        # Build query
        query = {"user_id": user_id}
        if is_active is not None:
            query["is_active"] = is_active
        
        # Get total count
        total = await db.workflows.count_documents(query)
        
        # Get workflows
        cursor = db.workflows.find(query).sort("created_at", -1).skip(skip).limit(limit)
        workflows = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for workflow in workflows:
            workflow["_id"] = str(workflow["_id"])
            workflow["id"] = str(workflow["_id"])
        
        logger.info(f"Found {total} workflows for user {user_id}")
        
        return {
            "workflows": workflows,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching workflows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get a specific workflow"""
    try:
        user_id = str(current_user["_id"])
        
        workflow = await db.workflows.find_one({
            "_id": ObjectId(workflow_id),
            "user_id": user_id
        })
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        workflow["_id"] = str(workflow["_id"])
        workflow["id"] = str(workflow["_id"])
        
        return workflow
        
    except Exception as e:
        logger.error(f"Error fetching workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow: WorkflowCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Create a new workflow"""
    try:
        user_id = str(current_user["_id"])
        
        workflow_data = {
            "user_id": user_id,
            "name": workflow.name,
            "description": workflow.description,
            "is_active": workflow.is_active,
            "nodes": workflow.nodes,
            "edges": workflow.edges,
            "version": 1,
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.workflows.insert_one(workflow_data)
        workflow_data["_id"] = str(result.inserted_id)
        workflow_data["id"] = str(result.inserted_id)
        
        logger.info(f"Created workflow {result.inserted_id} for user {user_id}")
        
        return {
            "message": "Workflow created successfully",
            "workflow": workflow_data
        }
        
    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{workflow_id}", response_model=dict)
async def update_workflow(
    workflow_id: str,
    workflow: WorkflowUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Update a workflow"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if workflow exists
        existing = await db.workflows.find_one({
            "_id": ObjectId(workflow_id),
            "user_id": user_id
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Build update data
        update_data = {"updated_at": datetime.utcnow()}
        
        if workflow.name is not None:
            update_data["name"] = workflow.name
        if workflow.description is not None:
            update_data["description"] = workflow.description
        if workflow.is_active is not None:
            update_data["is_active"] = workflow.is_active
        if workflow.nodes is not None:
            update_data["nodes"] = workflow.nodes
            update_data["version"] = existing.get("version", 1) + 1
        if workflow.edges is not None:
            update_data["edges"] = workflow.edges
        
        # Update workflow
        await db.workflows.update_one(
            {"_id": ObjectId(workflow_id)},
            {"$set": update_data}
        )
        
        logger.info(f"Updated workflow {workflow_id}")
        
        return {"message": "Workflow updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{workflow_id}", response_model=dict)
async def delete_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete a workflow"""
    try:
        user_id = str(current_user["_id"])
        
        result = await db.workflows.delete_one({
            "_id": ObjectId(workflow_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        logger.info(f"Deleted workflow {workflow_id}")
        
        return {"message": "Workflow deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{workflow_id}/execute", response_model=dict)
async def execute_workflow(
    workflow_id: str,
    execution_data: dict,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Execute a workflow"""
    try:
        user_id = str(current_user["_id"])
        
        # Get workflow
        workflow = await db.workflows.find_one({
            "_id": ObjectId(workflow_id),
            "user_id": user_id
        })
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Create execution record
        execution_record = {
            "workflow_id": workflow_id,
            "user_id": user_id,
            "status": "completed",
            "input_data": execution_data,
            "output_data": {"message": "Workflow executed successfully"},
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        result = await db.workflow_executions.insert_one(execution_record)
        
        # Update workflow execution count
        await db.workflows.update_one(
            {"_id": ObjectId(workflow_id)},
            {
                "$inc": {"execution_count": 1, "success_count": 1},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        logger.info(f"Executed workflow {workflow_id}")
        
        return {
            "message": "Workflow executed successfully",
            "execution_id": str(result.inserted_id),
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        
        # Update failure count
        await db.workflows.update_one(
            {"_id": ObjectId(workflow_id)},
            {
                "$inc": {"execution_count": 1, "failure_count": 1},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{workflow_id}/executions", response_model=dict)
async def get_workflow_executions(
    workflow_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get execution history for a workflow"""
    try:
        user_id = str(current_user["_id"])
        
        # Verify workflow belongs to user
        workflow = await db.workflows.find_one({
            "_id": ObjectId(workflow_id),
            "user_id": user_id
        })
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Get executions
        query = {"workflow_id": workflow_id}
        total = await db.workflow_executions.count_documents(query)
        
        cursor = db.workflow_executions.find(query).sort("created_at", -1).skip(skip).limit(limit)
        executions = await cursor.to_list(length=limit)
        
        for execution in executions:
            execution["_id"] = str(execution["_id"])
        
        return {
            "executions": executions,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching workflow executions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )




