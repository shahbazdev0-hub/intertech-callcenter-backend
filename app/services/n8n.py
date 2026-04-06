# backend/app/services/n8n.py
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

class N8NService:
    """Service for integrating with N8N workflow automation"""
    
    def __init__(self):
        """Initialize N8N client"""
        self.base_url = os.getenv('N8N_API_URL', 'http://localhost:5678/api/v1')
        self.api_key = os.getenv('N8N_API_KEY', '')
        self.headers = {
            'X-N8N-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        self.timeout = 30.0
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new workflow in N8N
        
        Args:
            workflow_data: Workflow configuration
            
        Returns:
            Created workflow details
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/workflows",
                    headers=self.headers,
                    json=workflow_data
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"N8N workflow created: {result.get('id')}")
                return result
                
        except httpx.HTTPError as e:
            logger.error(f"Error creating N8N workflow: {str(e)}")
            raise Exception(f"Failed to create N8N workflow: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating N8N workflow: {str(e)}")
            raise
    
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow details from N8N
        
        Args:
            workflow_id: N8N workflow ID
            
        Returns:
            Workflow details
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/workflows/{workflow_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error fetching N8N workflow: {str(e)}")
            raise Exception(f"Failed to fetch N8N workflow: {str(e)}")
    
    async def update_workflow(
        self,
        workflow_id: str,
        workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update existing workflow in N8N
        
        Args:
            workflow_id: N8N workflow ID
            workflow_data: Updated workflow configuration
            
        Returns:
            Updated workflow details
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.base_url}/workflows/{workflow_id}",
                    headers=self.headers,
                    json=workflow_data
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"N8N workflow updated: {workflow_id}")
                return result
                
        except httpx.HTTPError as e:
            logger.error(f"Error updating N8N workflow: {str(e)}")
            raise Exception(f"Failed to update N8N workflow: {str(e)}")
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete workflow from N8N
        
        Args:
            workflow_id: N8N workflow ID
            
        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    f"{self.base_url}/workflows/{workflow_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                
                logger.info(f"N8N workflow deleted: {workflow_id}")
                return True
                
        except httpx.HTTPError as e:
            logger.error(f"Error deleting N8N workflow: {str(e)}")
            return False
    
    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Activate workflow in N8N
        
        Args:
            workflow_id: N8N workflow ID
            
        Returns:
            Activation result
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.base_url}/workflows/{workflow_id}/activate",
                    headers=self.headers
                )
                response.raise_for_status()
                
                logger.info(f"N8N workflow activated: {workflow_id}")
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error activating N8N workflow: {str(e)}")
            raise Exception(f"Failed to activate N8N workflow: {str(e)}")
    
    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Deactivate workflow in N8N
        
        Args:
            workflow_id: N8N workflow ID
            
        Returns:
            Deactivation result
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.base_url}/workflows/{workflow_id}/deactivate",
                    headers=self.headers
                )
                response.raise_for_status()
                
                logger.info(f"N8N workflow deactivated: {workflow_id}")
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error deactivating N8N workflow: {str(e)}")
            raise Exception(f"Failed to deactivate N8N workflow: {str(e)}")
    
    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute workflow manually with input data
        
        Args:
            workflow_id: N8N workflow ID
            input_data: Input data for workflow
            
        Returns:
            Execution result
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for execution
                response = await client.post(
                    f"{self.base_url}/workflows/{workflow_id}/execute",
                    headers=self.headers,
                    json=input_data
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"N8N workflow executed: {workflow_id}")
                return {
                    "success": True,
                    "workflow_id": workflow_id,
                    "execution_id": result.get('executionId'),
                    "data": result.get('data'),
                    "executed_at": datetime.utcnow()
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Error executing N8N workflow: {str(e)}")
            return {
                "success": False,
                "workflow_id": workflow_id,
                "error": str(e),
                "executed_at": datetime.utcnow()
            }
    
    async def get_execution_result(
        self,
        workflow_id: str,
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Get workflow execution result
        
        Args:
            workflow_id: N8N workflow ID
            execution_id: Execution ID
            
        Returns:
            Execution details and result
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/executions/{execution_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error fetching execution result: {str(e)}")
            raise Exception(f"Failed to fetch execution result: {str(e)}")
    
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """
        List all workflows in N8N
        
        Returns:
            List of workflows
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/workflows",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json().get('data', [])
                
        except httpx.HTTPError as e:
            logger.error(f"Error listing N8N workflows: {str(e)}")
            return []
    
    async def create_webhook_workflow(
        self,
        webhook_path: str,
        nodes_config: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create workflow with webhook trigger
        
        Args:
            webhook_path: Webhook URL path
            nodes_config: Workflow nodes configuration
            
        Returns:
            Created workflow with webhook URL
        """
        try:
            workflow_data = {
                "name": f"Webhook: {webhook_path}",
                "active": True,
                "nodes": [
                    {
                        "parameters": {
                            "path": webhook_path,
                            "options": {}
                        },
                        "name": "Webhook",
                        "type": "n8n-nodes-base.webhook",
                        "typeVersion": 1,
                        "position": [250, 300]
                    },
                    *nodes_config
                ],
                "connections": {}
            }
            
            result = await self.create_workflow(workflow_data)
            
            # Construct webhook URL
            webhook_url = f"{self.base_url.replace('/api/v1', '')}/webhook/{webhook_path}"
            result['webhook_url'] = webhook_url
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating webhook workflow: {str(e)}")
            raise
    
    def validate_workflow_structure(self, nodes: List[Dict[str, Any]]) -> bool:
        """
        Validate workflow structure
        
        Args:
            nodes: List of workflow nodes
            
        Returns:
            True if valid, False otherwise
        """
        if not nodes:
            return False
        
        # Check if there's at least one trigger node
        trigger_nodes = [n for n in nodes if n.get('type', '').endswith('.trigger')]
        if not trigger_nodes:
            return False
        
        return True


# Create singleton instance
n8n_service = N8NService()