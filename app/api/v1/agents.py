
# backend/app/api/v1/agents.py
# ✅ ENHANCED: Added context regeneration triggers and agent management endpoints

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
import logging

from app.api.deps import get_current_user, get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# AGENT TEST ENDPOINT (EXISTING - PRESERVED)
# ============================================

@router.post("/agents/{agent_id}/test")
async def test_agent(
    agent_id: str,
    test_message: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Test an AI agent with a message"""
    try:
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        user_id = str(current_user["_id"])
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # ✅ ENHANCED: Use agent executor for actual testing
        try:
            from app.services.agent_executor import agent_executor
            
            response = await agent_executor.process_user_message(
                user_input=test_message,
                agent_config=agent,
                user_id=user_id,
                call_id=f"test_{agent_id}_{datetime.utcnow().timestamp()}",
                db=db
            )
            
            return {
                "success": True,
                "response": response,
                "agent_id": agent_id,
                "agent_name": agent.get("name"),
                "has_context": agent.get("has_context", False),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as exec_error:
            logger.error(f"❌ Agent executor error: {exec_error}")
            return {
                "success": True,
                "response": f"Hey! This is a test response from agent {agent.get('name', agent_id)}",
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat(),
                "warning": "Used fallback response"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error testing agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test agent: {str(e)}"
        )


# ============================================
# ✅ NEW: UPDATE AGENT SCRIPT WITH CONTEXT REGENERATION
# ============================================

@router.put("/{agent_id}/script")
@router.patch("/{agent_id}/script")
async def update_agent_script(
    agent_id: str,
    script_data: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ NEW: Update agent's AI script and regenerate context
    
    This endpoint specifically handles script updates and ensures
    the agent context is regenerated for fast responses.
    
    Body:
    {
        "ai_script": "New script text...",
        "system_prompt": "Optional system prompt...",
        "greeting_message": "Optional greeting..."
    }
    """
    try:
        user_id = str(current_user["_id"])
        
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Extract script fields
        ai_script = script_data.get("ai_script")
        system_prompt = script_data.get("system_prompt")
        greeting_message = script_data.get("greeting_message")
        
        if not ai_script and not system_prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either ai_script or system_prompt must be provided"
            )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📝 UPDATING AGENT SCRIPT")
        logger.info(f"{'='*60}")
        logger.info(f"   Agent ID: {agent_id}")
        logger.info(f"   Agent Name: {agent.get('name')}")
        logger.info(f"   New script length: {len(ai_script) if ai_script else 0}")
        logger.info(f"{'='*60}\n")
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        if ai_script:
            update_data["ai_script"] = ai_script
        if system_prompt:
            update_data["system_prompt"] = system_prompt
        if greeting_message:
            update_data["greeting_message"] = greeting_message
        
        # Update agent in database
        await db.voice_agents.update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": update_data}
        )
        
        logger.info(f"✅ Agent script updated in database")
        
        # ✅ REGENERATE CONTEXT
        context_regenerated = False
        context_error = None
        
        try:
            from app.services.rag_service import rag_service
            
            logger.info(f"🧠 Regenerating agent context...")
            
            context_result = await rag_service.update_agent_context_on_script_change(
                agent_id=agent_id,
                user_id=user_id,
                new_script=ai_script or system_prompt,
                db=db
            )
            
            if context_result.get("success"):
                context_regenerated = True
                logger.info(f"✅ Agent context regenerated successfully")
            else:
                context_error = context_result.get("error", "Unknown error")
                logger.warning(f"⚠️ Context regeneration failed: {context_error}")
                
        except Exception as ctx_error:
            context_error = str(ctx_error)
            logger.error(f"❌ Context regeneration error: {ctx_error}")
        
        # Fetch updated agent
        updated_agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
        updated_agent["_id"] = str(updated_agent["_id"])
        
        return {
            "success": True,
            "message": "Agent script updated successfully",
            "agent_id": agent_id,
            "agent_name": updated_agent.get("name"),
            "script_updated": True,
            "context_regenerated": context_regenerated,
            "context_error": context_error,
            "has_context": updated_agent.get("has_context", False),
            "updated_at": updated_agent.get("updated_at").isoformat() if updated_agent.get("updated_at") else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating agent script: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent script: {str(e)}"
        )


# ============================================
# ✅ NEW: GET AGENT CONTEXT
# ============================================

@router.get("/{agent_id}/context")
async def get_agent_context(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ NEW: Get the current agent context (pre-generated summary)
    
    Returns the structured context that's injected into every call
    for fast contextual responses.
    """
    try:
        user_id = str(current_user["_id"])
        
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        context = agent.get("agent_context")
        has_context = agent.get("has_context", False)
        context_generated_at = agent.get("context_generated_at")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "has_context": has_context,
            "context": context,
            "generated_at": context_generated_at.isoformat() if context_generated_at else None,
            "source_documents": context.get("source_documents", []) if context else [],
            "script_included": context.get("script_included", False) if context else False,
            "has_training_docs": agent.get("has_training_docs", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting agent context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent context: {str(e)}"
        )


# ============================================
# ✅ NEW: REGENERATE AGENT CONTEXT
# ============================================

@router.post("/{agent_id}/regenerate-context")
async def regenerate_agent_context(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ NEW: Manually regenerate agent context
    
    Use this endpoint to:
    - Force refresh context after changes
    - Fix context if it becomes out of sync
    - Generate context for agents created before this feature
    """
    try:
        user_id = str(current_user["_id"])
        
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 MANUAL CONTEXT REGENERATION")
        logger.info(f"{'='*60}")
        logger.info(f"   Agent ID: {agent_id}")
        logger.info(f"   Agent Name: {agent.get('name')}")
        logger.info(f"{'='*60}\n")
        
        # Import RAG service
        from app.services.rag_service import rag_service
        
        # Force regenerate context
        result = await rag_service.generate_agent_context(
            agent_id=agent_id,
            user_id=user_id,
            db=db,
            force_regenerate=True
        )
        
        if result.get("success"):
            context = result.get("context", {})
            
            return {
                "success": True,
                "message": "Agent context regenerated successfully",
                "agent_id": agent_id,
                "agent_name": agent.get("name"),
                "context_summary": {
                    "identity": context.get("identity", {}),
                    "services_count": len(context.get("company_info", {}).get("services", [])),
                    "faqs_count": len(context.get("faqs", [])),
                    "procedures_count": len(context.get("procedures", [])),
                    "source_documents": context.get("source_documents", []),
                    "script_included": context.get("script_included", False)
                },
                "generated_at": context.get("generated_at"),
                "cached": result.get("cached", False)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to regenerate context")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error regenerating context: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate context: {str(e)}"
        )


# ============================================
# ✅ NEW: GET AGENT SYSTEM PROMPT (For Debugging)
# ============================================

@router.get("/{agent_id}/system-prompt")
async def get_agent_system_prompt(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ NEW: Get the generated system prompt for an agent
    
    This shows exactly what system prompt will be sent to OpenAI
    during calls. Useful for debugging and fine-tuning.
    """
    try:
        user_id = str(current_user["_id"])
        
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        context = agent.get("agent_context")
        
        if not context:
            return {
                "success": True,
                "agent_id": agent_id,
                "has_context": False,
                "system_prompt": None,
                "message": "No context available. Use /regenerate-context to generate."
            }
        
        # Generate system prompt from context
        from app.services.openai import openai_service
        
        system_prompt = openai_service.build_contextual_system_prompt(
            agent_context=context,
            agent_name=agent.get("name"),
            ai_script=agent.get("ai_script", "")
        )
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "has_context": True,
            "system_prompt": system_prompt,
            "prompt_length": len(system_prompt),
            "generated_at": context.get("generated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting system prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system prompt: {str(e)}"
        )


# ============================================
# ✅ NEW: BULK REGENERATE CONTEXT FOR ALL AGENTS
# ============================================

@router.post("/regenerate-all-contexts")
async def regenerate_all_agent_contexts(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ NEW: Regenerate context for all user's agents
    
    Use this to:
    - Update all agents after system upgrade
    - Fix all contexts at once
    - Generate contexts for legacy agents
    """
    try:
        user_id = str(current_user["_id"])
        
        # Get all user's agents
        agents = await db.voice_agents.find({"user_id": user_id}).to_list(length=None)
        
        if not agents:
            return {
                "success": True,
                "message": "No agents found",
                "total": 0,
                "regenerated": 0,
                "failed": 0
            }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 BULK CONTEXT REGENERATION")
        logger.info(f"{'='*60}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Total agents: {len(agents)}")
        logger.info(f"{'='*60}\n")
        
        from app.services.rag_service import rag_service
        
        results = {
            "total": len(agents),
            "regenerated": 0,
            "failed": 0,
            "details": []
        }
        
        for agent in agents:
            agent_id = str(agent["_id"])
            agent_name = agent.get("name", "Unknown")
            
            try:
                result = await rag_service.generate_agent_context(
                    agent_id=agent_id,
                    user_id=user_id,
                    db=db,
                    force_regenerate=True
                )
                
                if result.get("success"):
                    results["regenerated"] += 1
                    results["details"].append({
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "status": "success"
                    })
                    logger.info(f"✅ Regenerated context for: {agent_name}")
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "status": "failed",
                        "error": result.get("error")
                    })
                    logger.warning(f"⚠️ Failed for {agent_name}: {result.get('error')}")
                    
            except Exception as agent_error:
                results["failed"] += 1
                results["details"].append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "status": "error",
                    "error": str(agent_error)
                })
                logger.error(f"❌ Error for {agent_name}: {agent_error}")
        
        logger.info(f"\n✅ Bulk regeneration complete: {results['regenerated']}/{results['total']} succeeded")
        
        return {
            "success": True,
            "message": f"Regenerated context for {results['regenerated']}/{results['total']} agents",
            **results
        }
        
    except Exception as e:
        logger.error(f"❌ Error in bulk regeneration: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate contexts: {str(e)}"
        )


# ============================================
# AGENT PERFORMANCE ENDPOINT (EXISTING - PRESERVED)
# ============================================

@router.get("/agents/{agent_id}/performance")
async def get_agent_performance(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get performance metrics for an agent"""
    try:
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        user_id = str(current_user["_id"])
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Get call statistics
        total_calls = await db.calls.count_documents({"agent_id": agent_id})
        completed_calls = await db.calls.count_documents({
            "agent_id": agent_id,
            "status": "completed"
        })
        
        # Calculate success rate
        success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
        
        # Get average call duration
        pipeline = [
            {"$match": {"agent_id": agent_id, "duration": {"$exists": True, "$gt": 0}}},
            {"$group": {"_id": None, "avg_duration": {"$avg": "$duration"}}}
        ]
        duration_result = await db.calls.aggregate(pipeline).to_list(length=1)
        avg_duration = duration_result[0]["avg_duration"] if duration_result else 0
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "performance": {
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "success_rate": round(success_rate, 2),
                "average_duration_seconds": round(avg_duration, 2),
                "has_context": agent.get("has_context", False),
                "has_training_docs": agent.get("has_training_docs", False),
                "training_doc_count": len(agent.get("training_doc_ids", []))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting agent performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance: {str(e)}"
        )


# ============================================
# CLONE AGENT ENDPOINT (EXISTING - PRESERVED)
# ============================================

@router.post("/agents/{agent_id}/clone")
async def clone_agent(
    agent_id: str,
    new_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Clone an existing agent with a new name"""
    try:
        if not ObjectId.is_valid(agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid agent ID"
            )
        
        user_id = str(current_user["_id"])
        
        # Get original agent
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Create clone
        clone_data = {k: v for k, v in agent.items() if k != "_id"}
        clone_data["name"] = new_name
        clone_data["created_at"] = datetime.utcnow()
        clone_data["updated_at"] = datetime.utcnow()
        clone_data["total_calls"] = 0
        clone_data["successful_calls"] = 0
        clone_data["in_call"] = False
        # Don't copy context - will be regenerated
        clone_data["agent_context"] = None
        clone_data["has_context"] = False
        clone_data["context_generated_at"] = None
        # Don't copy training docs - need to be re-uploaded
        clone_data["has_training_docs"] = False
        clone_data["training_doc_ids"] = []
        
        result = await db.voice_agents.insert_one(clone_data)
        new_agent_id = str(result.inserted_id)
        
        logger.info(f"✅ Cloned agent {agent_id} to {new_agent_id}")
        
        # ✅ Generate context for cloned agent
        try:
            from app.services.rag_service import rag_service
            
            await rag_service.generate_agent_context(
                agent_id=new_agent_id,
                user_id=user_id,
                db=db,
                script_text=clone_data.get("ai_script"),
                force_regenerate=True
            )
            logger.info(f"✅ Context generated for cloned agent")
        except Exception as ctx_error:
            logger.warning(f"⚠️ Context generation for clone failed: {ctx_error}")
        
        return {
            "success": True,
            "message": f"Agent cloned successfully",
            "original_agent_id": agent_id,
            "new_agent_id": new_agent_id,
            "new_agent_name": new_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cloning agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone agent: {str(e)}"
        )