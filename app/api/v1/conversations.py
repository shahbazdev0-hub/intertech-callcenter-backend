# backend/app/api/v1/conversations.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from ...api.deps import get_current_user, get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()

@router.get("/")
async def get_conversations(
    skip: int = 0,
    limit: int = 50,
    call_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get conversations for the current user"""
    try:
        # Build filter
        filter_query = {"user_id": str(current_user["_id"])}
        
        if call_id:
            if ObjectId.is_valid(call_id):
                filter_query["call_id"] = call_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid call ID"
                )
        
        if agent_id:
            if ObjectId.is_valid(agent_id):
                filter_query["agent_id"] = agent_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid agent ID"
                )
        
        conversations_cursor = db.conversations.find(filter_query).skip(skip).limit(limit).sort("created_at", -1)
        conversations = await conversations_cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for conversation in conversations:
            conversation["_id"] = str(conversation["_id"])
        
        return conversations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversations: {str(e)}"
        )

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific conversation with messages"""
    try:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID"
            )
        
        conversation = await db.conversations.find_one({
            "_id": ObjectId(conversation_id),
            "user_id": str(current_user["_id"])
        })
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        conversation["_id"] = str(conversation["_id"])
        
        # Get messages for this conversation
        messages_cursor = db.messages.find({
            "conversation_id": conversation_id
        }).sort("timestamp", 1)
        
        messages = await messages_cursor.to_list(length=None)
        
        # Convert ObjectId to string for messages
        for message in messages:
            message["_id"] = str(message["_id"])
        
        conversation["messages"] = messages
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )

@router.post("/")
async def create_conversation(
    conversation_data: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new conversation"""
    try:
        # Add user_id and timestamps
        conversation_data["user_id"] = str(current_user["_id"])
        conversation_data["created_at"] = datetime.utcnow()
        conversation_data["updated_at"] = datetime.utcnow()
        conversation_data["status"] = "active"
        
        result = await db.conversations.insert_one(conversation_data)
        
        # Get the created conversation
        conversation = await db.conversations.find_one({"_id": result.inserted_id})
        conversation["_id"] = str(conversation["_id"])
        
        return conversation
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )

@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    update_data: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a conversation"""
    try:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID"
            )
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.conversations.update_one(
            {
                "_id": ObjectId(conversation_id),
                "user_id": str(current_user["_id"])
            },
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get updated conversation
        conversation = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
        conversation["_id"] = str(conversation["_id"])
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(e)}"
        )

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a conversation"""
    try:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID"
            )
        
        result = await db.conversations.delete_one({
            "_id": ObjectId(conversation_id),
            "user_id": str(current_user["_id"])
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}"
        )

@router.post("/{conversation_id}/messages")
async def add_message(
    conversation_id: str,
    message_data: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add a message to a conversation"""
    try:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID"
            )
        
        # Verify conversation exists and belongs to user
        conversation = await db.conversations.find_one({
            "_id": ObjectId(conversation_id),
            "user_id": str(current_user["_id"])
        })
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Add message data
        message_data["conversation_id"] = conversation_id
        message_data["timestamp"] = datetime.utcnow()
        
        result = await db.messages.insert_one(message_data)
        
        # Get the created message
        message = await db.messages.find_one({"_id": result.inserted_id})
        message["_id"] = str(message["_id"])
        
        # Update conversation timestamp
        await db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {"updated_at": datetime.utcnow()}}
        )
        
        return message
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message: {str(e)}"
        )

@router.get("/stats/summary")
async def get_conversation_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get conversation statistics summary"""
    try:
        user_id = str(current_user["_id"])
        
        # Get total conversations
        total_conversations = await db.conversations.count_documents({"user_id": user_id})
        
        # Get conversations today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        conversations_today = await db.conversations.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": today}
        })
        
        # Get active conversations
        active_conversations = await db.conversations.count_documents({
            "user_id": user_id,
            "status": "active"
        })
        
        return {
            "total_conversations": total_conversations,
            "conversations_today": conversations_today,
            "active_conversations": active_conversations,
            "completion_rate": 85.0  # Mock data for now
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation stats: {str(e)}"
        )