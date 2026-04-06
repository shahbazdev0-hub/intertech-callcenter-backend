# backend/app/services/automation.py

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import asyncio

from app.config import settings
from app.database import get_database
from app.services.email import email_service
from app.services.sms import sms_service


class AutomationService:
    """Automation Service - Trigger-based automation engine"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database connection"""
        if not self.db:
            self.db = await get_database()
        return self.db
    
    async def create_automation(
        self,
        user_id: str,
        name: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        actions: List[Dict[str, Any]],
        description: Optional[str] = None,
        is_active: bool = True
    ) -> Dict[str, Any]:
        """
        Create automation
        
        Args:
            user_id: User ID
            name: Automation name
            trigger_type: Type of trigger (call_completed, demo_booked, etc.)
            trigger_config: Trigger configuration
            actions: List of actions to execute
            description: Description (optional)
            is_active: Is automation active
            
        Returns:
            Dict with automation details
        """
        db = await self.get_db()
        
        automation_data = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "actions": actions,
            "is_active": is_active,
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "max_executions": None,
            "execution_timeout": settings.AUTOMATION_EXECUTION_TIMEOUT,
            "retry_on_failure": True,
            "max_retries": 3,
            "metadata": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.automations.insert_one(automation_data)
        automation_data["_id"] = str(result.inserted_id)
        
        return automation_data
    
    async def get_automations(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get automations for user"""
        db = await self.get_db()
        
        query = {"user_id": user_id}
        if is_active is not None:
            query["is_active"] = is_active
        
        total = await db.automations.count_documents(query)
        
        cursor = db.automations.find(query).sort("created_at", -1).skip(skip).limit(limit)
        automations = await cursor.to_list(length=limit)
        
        for automation in automations:
            automation["_id"] = str(automation["_id"])
        
        return {
            "automations": automations,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
    
    async def get_automation(self, automation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get automation by ID"""
        db = await self.get_db()
        
        automation = await db.automations.find_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        if automation:
            automation["_id"] = str(automation["_id"])
        
        return automation
    
    async def update_automation(
        self,
        automation_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update automation"""
        db = await self.get_db()
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.automations.update_one(
            {"_id": ObjectId(automation_id), "user_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await self.get_automation(automation_id, user_id)
        
        return None
    
    async def delete_automation(self, automation_id: str, user_id: str) -> bool:
        """Delete automation"""
        db = await self.get_db()
        
        result = await db.automations.delete_one({
            "_id": ObjectId(automation_id),
            "user_id": user_id
        })
        
        return result.deleted_count > 0
    
    async def toggle_automation(
        self,
        automation_id: str,
        user_id: str,
        is_active: bool
    ) -> Optional[Dict[str, Any]]:
        """Toggle automation active status"""
        return await self.update_automation(
            automation_id,
            user_id,
            {"is_active": is_active}
        )
    
    async def trigger_automation(
        self,
        automation_id: str,
        trigger_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger automation execution
        
        Args:
            automation_id: Automation ID
            trigger_data: Data from trigger event
            
        Returns:
            Dict with execution results
        """
        db = await self.get_db()
        
        automation = await db.automations.find_one({"_id": ObjectId(automation_id)})
        if not automation:
            return {"success": False, "error": "Automation not found"}
        
        if not automation.get("is_active"):
            return {"success": False, "error": "Automation is not active"}
        
        # Create execution log
        log_data = {
            "automation_id": automation_id,
            "user_id": automation["user_id"],
            "status": "running",
            "trigger_data": trigger_data,
            "actions_executed": [],
            "started_at": datetime.utcnow()
        }
        
        log_result = await db.automation_logs.insert_one(log_data)
        log_id = str(log_result.inserted_id)
        
        try:
            # Execute actions
            actions_executed = []
            
            for action in automation["actions"]:
                action_result = await self._execute_action(
                    action,
                    trigger_data,
                    automation["user_id"]
                )
                actions_executed.append(action_result)
            
            # Update success
            duration = (datetime.utcnow() - log_data["started_at"]).total_seconds()
            
            await db.automation_logs.update_one(
                {"_id": ObjectId(log_id)},
                {
                    "$set": {
                        "status": "success",
                        "actions_executed": actions_executed,
                        "completed_at": datetime.utcnow(),
                        "duration_seconds": duration
                    }
                }
            )
            
            # Update automation stats
            await db.automations.update_one(
                {"_id": ObjectId(automation_id)},
                {
                    "$inc": {
                        "execution_count": 1,
                        "success_count": 1
                    },
                    "$set": {
                        "last_executed_at": datetime.utcnow()
                    }
                }
            )
            
            return {
                "success": True,
                "log_id": log_id,
                "actions_executed": actions_executed
            }
            
        except Exception as e:
            # Update failure
            duration = (datetime.utcnow() - log_data["started_at"]).total_seconds()
            
            await db.automation_logs.update_one(
                {"_id": ObjectId(log_id)},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow(),
                        "duration_seconds": duration
                    }
                }
            )
            
            # Update automation stats
            await db.automations.update_one(
                {"_id": ObjectId(automation_id)},
                {
                    "$inc": {
                        "execution_count": 1,
                        "failure_count": 1
                    },
                    "$set": {
                        "last_executed_at": datetime.utcnow()
                    }
                }
            )
            
            return {
                "success": False,
                "error": str(e),
                "log_id": log_id
            }
    
    async def _execute_action(
        self,
        action: Dict[str, Any],
        trigger_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute a single action"""
        action_type = action.get("type")
        action_config = action.get("config", {})
        
        try:
            if action_type == "send_email":
                # Send email action
                result = await email_service.send_email(
                    to_email=action_config.get("to_email"),
                    subject=action_config.get("subject"),
                    html_content=self._render_template(
                        action_config.get("content"),
                        trigger_data
                    )
                )
                return {
                    "action_type": action_type,
                    "status": "success",
                    "result": result
                }
            
            elif action_type == "send_sms":
                # Send SMS action
                result = await sms_service.send_sms(
                    to_number=action_config.get("to_number"),
                    message=self._render_template(
                        action_config.get("message"),
                        trigger_data
                    ),
                    user_id=user_id
                )
                return {
                    "action_type": action_type,
                    "status": "success",
                    "result": result
                }
            
            elif action_type == "delay":
                # Delay action
                delay_seconds = action_config.get("seconds", 0)
                await asyncio.sleep(delay_seconds)
                return {
                    "action_type": action_type,
                    "status": "success",
                    "delayed_seconds": delay_seconds
                }
            
            elif action_type == "webhook":
                # Webhook action (future implementation)
                return {
                    "action_type": action_type,
                    "status": "skipped",
                    "message": "Webhook action not implemented yet"
                }
            
            else:
                return {
                    "action_type": action_type,
                    "status": "error",
                    "error": f"Unknown action type: {action_type}"
                }
        
        except Exception as e:
            return {
                "action_type": action_type,
                "status": "error",
                "error": str(e)
            }
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Simple template rendering"""
        result = template
        for key, value in data.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
    
    async def get_automation_logs(
        self,
        automation_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get automation execution logs"""
        db = await self.get_db()
        
        query = {
            "automation_id": automation_id,
            "user_id": user_id
        }
        
        total = await db.automation_logs.count_documents(query)
        
        cursor = db.automation_logs.find(query).sort("started_at", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        for log in logs:
            log["_id"] = str(log["_id"])
        
        return {
            "logs": logs,
            "total": total
        }
    
    async def get_automation_stats(self, user_id: str) -> Dict[str, Any]:
        """Get automation statistics"""
        db = await self.get_db()
        
        # Total automations
        total = await db.automations.count_documents({"user_id": user_id})
        active = await db.automations.count_documents({"user_id": user_id, "is_active": True})
        
        # Aggregate execution stats
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
        stats = await stats_cursor.to_list(length=1)
        
        if stats:
            stats_data = stats[0]
        else:
            stats_data = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0
            }
        
        # Average duration from logs
        avg_pipeline = [
            {"$match": {"user_id": user_id, "status": "success"}},
            {"$group": {
                "_id": None,
                "average_duration": {"$avg": "$duration_seconds"}
            }}
        ]
        
        avg_cursor = db.automation_logs.aggregate(avg_pipeline)
        avg_result = await avg_cursor.to_list(length=1)
        
        average_duration = avg_result[0]["average_duration"] if avg_result else 0
        
        return {
            "total_automations": total,
            "active_automations": active,
            "total_executions": stats_data["total_executions"],
            "successful_executions": stats_data["successful_executions"],
            "failed_executions": stats_data["failed_executions"],
            "average_duration": round(average_duration, 2)
        }
    
    async def find_automations_by_trigger(
        self,
        trigger_type: str,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find automations by trigger type"""
        db = await self.get_db()
        
        query = {
            "trigger_type": trigger_type,
            "is_active": True
        }
        
        if user_id:
            query["user_id"] = user_id
        
        cursor = db.automations.find(query)
        automations = await cursor.to_list(length=None)
        
        for automation in automations:
            automation["_id"] = str(automation["_id"])
        
        return automations


# Create singleton instance
automation_service = AutomationService()