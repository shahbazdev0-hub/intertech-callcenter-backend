# backend/app/services/bulk_call_service.py
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import logging

from app.models.bulk_campaign import BulkCampaign, CampaignRecipient
from app.services.twilio import TwilioService
from app.services.call_handler import get_call_handler  # ✅ ADD THIS IMPORT
from app.utils.csv_parser import CSVParser

logger = logging.getLogger(__name__)


class BulkCallService:
    """Service for managing bulk call campaigns"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.twilio_service = TwilioService()
        self.csv_parser = CSVParser()
        self.active_campaigns: Dict[str, bool] = {}
        self.call_handler = get_call_handler(db)  # ✅ INITIALIZE CALL HANDLER
    
    async def create_campaign(self, user_id: str, campaign_data: Dict) -> BulkCampaign:
        """Create a new bulk call campaign"""
        try:
            # Check if campaign_id already exists for this user
            existing = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_data['campaign_id']
            })
            
            if existing:
                raise ValueError(f"Campaign ID '{campaign_data['campaign_id']}' already exists")
            
            campaign = BulkCampaign(
                user_id=user_id,
                campaign_id=campaign_data['campaign_id'],
                campaign_name=campaign_data.get('campaign_name'),
                custom_ai_script=campaign_data.get('custom_ai_script'),
                campaign_type=campaign_data.get('campaign_type', 'call'),
                status='draft'
            )
            
            # Convert to dict and exclude None id
            campaign_dict = campaign.dict(by_alias=True, exclude_none=True)
            if '_id' in campaign_dict:
                del campaign_dict['_id']
            
            result = await self.db.bulk_campaigns.insert_one(campaign_dict)
            campaign.id = str(result.inserted_id)
            
            logger.info(f"✅ Created campaign {campaign.campaign_id} for user {user_id}")
            return campaign
        
        except Exception as e:
            logger.error(f"❌ Error creating campaign: {str(e)}")
            raise
    
    async def upload_csv_recipients(
        self, 
        user_id: str, 
        campaign_id: str, 
        file_content: bytes, 
        filename: str
    ) -> Dict:
        """Parse CSV and add recipients to campaign"""
        try:
            logger.info(f"📄 Uploading CSV for campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            # Parse CSV
            parse_result = self.csv_parser.parse_csv_file(file_content, filename)
            
            if not parse_result['success']:
                return parse_result
            
            recipients = parse_result['recipients']
            
            # Check for existing recipients in campaign
            existing_phones = set()
            existing_recipients = await self.db.campaign_recipients.find({
                'campaign_id': campaign_id,
                'user_id': user_id
            }).to_list(length=None)
            
            for recipient in existing_recipients:
                existing_phones.add(recipient['phone_number'])
            
            # Filter out duplicates
            new_recipients = []
            duplicate_count = 0
            
            for recipient in recipients:
                if recipient['phone_number'] not in existing_phones:
                    new_recipients.append(recipient)
                    existing_phones.add(recipient['phone_number'])
                else:
                    duplicate_count += 1
            
            # Insert new recipients
            if new_recipients:
                recipient_docs = []
                for recipient in new_recipients:
                    recipient_doc = CampaignRecipient(
                        campaign_id=campaign_id,
                        user_id=user_id,
                        phone_number=recipient['phone_number'],
                        name=recipient.get('name'),
                        email=recipient.get('email'),
                        call_status='pending'
                    )
                    doc_dict = recipient_doc.dict(by_alias=True, exclude_none=True)
                    if '_id' in doc_dict:
                        del doc_dict['_id']
                    recipient_docs.append(doc_dict)
                
                await self.db.campaign_recipients.insert_many(recipient_docs)
            
            # Update campaign total
            total_recipients = await self.db.campaign_recipients.count_documents({
                'campaign_id': campaign_id,
                'user_id': user_id
            })
            
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'total_recipients': total_recipients,
                        'status': 'ready' if total_recipients > 0 else 'draft',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Uploaded {len(new_recipients)} new recipients to campaign {campaign_id}")
            
            return {
                'success': True,
                'total_uploaded': parse_result['total_rows'],
                'valid_numbers': parse_result['valid_numbers'],
                'invalid_numbers': parse_result['invalid_numbers'],
                'duplicate_count': duplicate_count,
                'added_count': len(new_recipients),
                'total_recipients': total_recipients,
                'errors': [f"Row {detail['row']}: {detail['reason']}" 
                          for detail in parse_result.get('invalid_details', [])]
            }
        
        except Exception as e:
            logger.error(f"❌ Error uploading CSV: {str(e)}")
            raise
    
    async def add_manual_recipients(
        self, 
        user_id: str, 
        campaign_id: str, 
        recipients: List
    ) -> Dict:
        """Add recipients manually to campaign"""
        try:
            logger.info(f"➕ Adding {len(recipients)} manual recipients to campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            # ✅ FIX: Convert Pydantic models to dictionaries
            recipients_dict = []
            for recipient in recipients:
                if hasattr(recipient, 'dict'):
                    # It's a Pydantic model
                    recipients_dict.append(recipient.dict())
                else:
                    # It's already a dict
                    recipients_dict.append(recipient)
            
            # Validate recipients
            valid_recipients, errors = self.csv_parser.validate_bulk_recipients(recipients_dict)
            
            if not valid_recipients:
                return {
                    'success': False,
                    'error': 'No valid recipients provided',
                    'errors': errors
                }
            
            # Check for existing recipients
            existing_phones = set()
            existing_recipients = await self.db.campaign_recipients.find({
                'campaign_id': campaign_id,
                'user_id': user_id
            }).to_list(length=None)
            
            for recipient in existing_recipients:
                existing_phones.add(recipient['phone_number'])
            
            # Filter new recipients
            new_recipients = []
            duplicate_count = 0
            
            for recipient in valid_recipients:
                if recipient['phone_number'] not in existing_phones:
                    new_recipients.append(recipient)
                    existing_phones.add(recipient['phone_number'])
                else:
                    duplicate_count += 1
                    errors.append(f"Duplicate: {recipient['phone_number']}")
            
            # Insert new recipients
            if new_recipients:
                recipient_docs = []
                for recipient in new_recipients:
                    recipient_doc = CampaignRecipient(
                        campaign_id=campaign_id,
                        user_id=user_id,
                        phone_number=recipient['phone_number'],
                        name=recipient.get('name'),
                        email=recipient.get('email'),
                        call_status='pending'
                    )
                    doc_dict = recipient_doc.dict(by_alias=True, exclude_none=True)
                    if '_id' in doc_dict:
                        del doc_dict['_id']
                    recipient_docs.append(doc_dict)
                
                await self.db.campaign_recipients.insert_many(recipient_docs)
            
            # Update campaign total
            total_recipients = await self.db.campaign_recipients.count_documents({
                'campaign_id': campaign_id,
                'user_id': user_id
            })
            
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'total_recipients': total_recipients,
                        'status': 'ready' if total_recipients > 0 else 'draft',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Added {len(new_recipients)} manual recipients to campaign {campaign_id}")
            
            return {
                'success': True,
                'added_count': len(new_recipients),
                'duplicate_count': duplicate_count,
                'total_recipients': total_recipients,
                'errors': errors
            }
        
        except Exception as e:
            logger.error(f"❌ Error adding manual recipients: {str(e)}")
            raise
    
    async def start_campaign(
        self, 
        user_id: str, 
        campaign_id: str,
        max_concurrent_calls: int = 1
    ) -> Dict:
        """Start bulk calling campaign"""
        try:
            logger.info(f"🚀 Starting campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            if campaign['status'] not in ['ready', 'paused']:
                raise ValueError(f"Campaign cannot be started. Current status: {campaign['status']}")
            
            if campaign['total_recipients'] == 0:
                raise ValueError("Campaign has no recipients")
            
            # Check if campaign is already running
            if campaign_id in self.active_campaigns and self.active_campaigns[campaign_id]:
                raise ValueError("Campaign is already running")
            
            # Update campaign status
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'status': 'in_progress',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Mark campaign as active
            self.active_campaigns[campaign_id] = True
            
            # Start calling in background
            asyncio.create_task(
                self._execute_campaign_calls(
                    user_id, 
                    campaign_id, 
                    str(campaign['_id']),
                    campaign.get('custom_ai_script'),
                    max_concurrent_calls
                )
            )
            
            return {
                'success': True,
                'message': 'Campaign started successfully',
                'campaign_id': campaign_id,
                'total_recipients': campaign['total_recipients']
            }
        
        except Exception as e:
            logger.error(f"❌ Error starting campaign: {str(e)}")
            raise
    
    async def _execute_campaign_calls(
        self,
        user_id: str,
        campaign_id: str,
        campaign_object_id: str,
        custom_ai_script: Optional[str],
        max_concurrent_calls: int
    ):
        """Execute sequential calls for campaign"""
        try:
            logger.info(f"📞 Starting campaign execution: {campaign_id}")
            
            # Get all pending recipients
            recipients = await self.db.campaign_recipients.find({
                'campaign_id': campaign_id,
                'user_id': user_id,
                'call_status': 'pending'
            }).to_list(length=None)
            
            logger.info(f"Found {len(recipients)} pending recipients")
            
            for recipient in recipients:
                # Check if campaign should continue
                if not self.active_campaigns.get(campaign_id, False):
                    logger.info(f"⏸️ Campaign {campaign_id} was paused/stopped")
                    break
                
                try:
                    # Update recipient status to 'calling'
                    await self.db.campaign_recipients.update_one(
                        {'_id': recipient['_id']},
                        {
                            '$set': {
                                'call_status': 'calling',
                                'call_attempts': recipient.get('call_attempts', 0) + 1,
                                'last_call_attempt': datetime.utcnow()
                            }
                        }
                    )
                    
                    # ✅ FIXED: Initiate call USING CALL HANDLER (like single calls)
                    call_result = await self._make_campaign_call(
                        user_id=user_id,
                        campaign_id=campaign_id,
                        recipient=recipient,
                        custom_ai_script=custom_ai_script
                    )
                    
                    # Wait a moment for call to connect
                    await asyncio.sleep(3)
                    
                    # Check call status after delay
                    final_status = call_result['status']
                    call_duration = None
                    appointment_booked = False
                    keywords_matched = []
                    conversation_summary = None
                    
                    if call_result.get('call_sid'):
                        try:
                            # Get latest call status
                            current_call = await self.db.calls.find_one({
                                "twilio_call_sid": call_result['call_sid']
                            })
                            if current_call:
                                final_status = current_call.get('status', call_result['status'])
                                call_duration = current_call.get('duration')
                                
                                # Check for appointment booking
                                if call_result.get('conversation_id'):
                                    conversation = await self.db.conversations.find_one({
                                        "_id": ObjectId(call_result['conversation_id'])
                                    })
                                    if conversation:
                                        metadata = conversation.get('metadata', {})
                                        if metadata.get('appointment_data'):
                                            appointment_booked = True
                        except Exception as e:
                            logger.warning(f"⚠️ Could not fetch final call status: {e}")
                    
                    # Update recipient with call result
                    update_data = {
                        'call_status': final_status,
                        'call_sid': call_result.get('call_sid'),
                        'call_duration': call_duration,
                        'conversation_id': call_result.get('conversation_id'),
                        'updated_at': datetime.utcnow()
                    }
                    
                    if appointment_booked:
                        update_data['appointment_booked'] = True
                    
                    if keywords_matched:
                        update_data['keywords_matched'] = keywords_matched
                    
                    if conversation_summary:
                        update_data['conversation_summary'] = conversation_summary
                    
                    await self.db.campaign_recipients.update_one(
                        {'_id': recipient['_id']},
                        {'$set': update_data}
                    )
                    
                    # Update campaign statistics
                    increment_data = {'completed_calls': 1}
                    
                    if final_status == 'completed':
                        increment_data['successful_calls'] = 1
                    else:
                        increment_data['failed_calls'] = 1
                    
                    if appointment_booked:
                        increment_data['appointments_booked'] = 1
                    
                    await self.db.bulk_campaigns.update_one(
                        {'_id': ObjectId(campaign_object_id)},
                        {
                            '$inc': increment_data,
                            '$set': {'updated_at': datetime.utcnow()}
                        }
                    )
                    
                    logger.info(f"✅ Completed call to {recipient['phone_number']}: {final_status}")
                    
                    # Small delay between calls (rate limiting)
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Error calling recipient {recipient['phone_number']}: {str(e)}")
                    
                    # Mark as failed
                    await self.db.campaign_recipients.update_one(
                        {'_id': recipient['_id']},
                        {
                            '$set': {
                                'call_status': 'failed',
                                'conversation_summary': f'Error: {str(e)}',
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )
                    
                    await self.db.bulk_campaigns.update_one(
                        {'_id': ObjectId(campaign_object_id)},
                        {
                            '$inc': {'completed_calls': 1, 'failed_calls': 1},
                            '$set': {'updated_at': datetime.utcnow()}
                        }
                    )
            
            # Campaign completed
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign_object_id)},
                {
                    '$set': {
                        'status': 'completed',
                        'completed_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            self.active_campaigns[campaign_id] = False
            
            logger.info(f"✅ Campaign {campaign_id} completed")
        
        except Exception as e:
            logger.error(f"❌ Error executing campaign: {str(e)}")
            
            # Mark campaign as failed
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign_object_id)},
                {
                    '$set': {
                        'status': 'failed',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            self.active_campaigns[campaign_id] = False
    
    async def _make_campaign_call(
        self,
        user_id: str,
        campaign_id: str,
        recipient: dict,
        custom_ai_script: Optional[str] = None
    ) -> Dict:
        """Make a single campaign call with proper conversation setup"""
        try:
            logger.info(f"📞 Making campaign call to: {recipient['phone_number']}")
            
            # ✅ GET AGENT FIRST (CRITICAL)
            agent = await self.db.voice_agents.find_one({
                'user_id': user_id,
                'is_active': True
            })
            
            if not agent:
                logger.error(f"❌ No active agent found for user: {user_id}")
                return {
                    'status': 'failed',
                    'error': 'No active agent configured',
                    'call_sid': None
                }
            
            agent_id = str(agent['_id'])
            logger.info(f"✅ Using agent: {agent.get('name', 'Unnamed')} (ID: {agent_id})")
            
            # ✅ INITIATE CALL USING CALL HANDLER (like single calls)
            call_result = await self.call_handler.initiate_call(
                user_id=user_id,
                to_number=recipient['phone_number'],
                agent_id=agent_id
            )
            
            if not call_result.get('success'):
                logger.error(f"❌ Call initiation failed: {call_result.get('error')}")
                return {
                    'status': 'failed',
                    'error': call_result.get('error', 'Unknown error'),
                    'call_sid': None
                }
            
            call_sid = call_result['call_sid']
            call_id = call_result['call_id']
            
            logger.info(f"✅ Call initiated: {call_sid} (Call ID: {call_id})")
            
            # ✅ FIND THE CONVERSATION THAT WAS CREATED BY CALL HANDLER
            conversation = await self.db.conversations.find_one({
                'call_id': ObjectId(call_id)
            })
            
            if not conversation:
                logger.error(f"❌ No conversation found for call: {call_id}")
                return {
                    'status': 'failed',
                    'error': 'Conversation not created',
                    'call_sid': call_sid
                }
            
            conversation_id = str(conversation['_id'])
            
            # ✅ UPDATE CONVERSATION WITH CAMPAIGN CONTEXT
            conversation_context = {
                'campaign_id': campaign_id,
                'recipient_name': recipient.get('name'),
                'recipient_phone': recipient['phone_number'],
                'custom_ai_script': custom_ai_script,
                'is_bulk_campaign': True,
                'original_agent_config': {
                    'workflow_id': agent.get('workflow_id'),
                    'voice_id': agent.get('voice_id'),
                    'greeting_message': agent.get('greeting_message')
                }
            }
            
            await self.db.conversations.update_one(
                {'_id': ObjectId(conversation_id)},
                {
                    '$set': {
                        'campaign_id': campaign_id,
                        'context': conversation_context,
                        'phone_number': recipient['phone_number']
                    }
                }
            )
            
            logger.info(f"✅ Updated conversation {conversation_id} with campaign context")
            
            # ✅ UPDATE CAMPAIGN RECIPIENT WITH CALL INFO
            await self.db.campaign_recipients.update_one(
                {
                    'campaign_id': campaign_id,
                    'user_id': user_id,
                    'phone_number': recipient['phone_number']
                },
                {
                    '$set': {
                        'call_status': 'calling',
                        'call_sid': call_sid,
                        'conversation_id': conversation_id,
                        'last_call_attempt': datetime.utcnow(),
                        'call_attempts': 1
                    }
                }
            )
            
            # ✅ UPDATE CALL RECORD WITH CAMPAIGN INFO
            await self.db.calls.update_one(
                {'_id': ObjectId(call_id)},
                {
                    '$set': {
                        'campaign_id': campaign_id,
                        'conversation_id': conversation_id
                    }
                }
            )
            
            return {
                'status': 'calling',
                'call_sid': call_sid,
                'call_id': call_id,
                'conversation_id': conversation_id,
                'agent_id': agent_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error making campaign call: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'error': str(e),
                'call_sid': None
            }
    
    async def pause_campaign(self, user_id: str, campaign_id: str) -> Dict:
        """Pause running campaign"""
        try:
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            if campaign['status'] != 'in_progress':
                raise ValueError(f"Campaign is not running. Current status: {campaign['status']}")
            
            # Stop campaign execution
            self.active_campaigns[campaign_id] = False
            
            # Update campaign status
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'status': 'paused',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return {
                'success': True,
                'message': 'Campaign paused successfully'
            }
        
        except Exception as e:
            logger.error(f"❌ Error pausing campaign: {str(e)}")
            raise
    
    async def get_campaign_status(self, user_id: str, campaign_id: str) -> Dict:
        """Get detailed campaign status"""
        try:
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            # Get current calling recipient (if any)
            current_recipient = await self.db.campaign_recipients.find_one({
                'campaign_id': campaign_id,
                'call_status': 'calling'
            })
            
            progress = 0
            if campaign['total_recipients'] > 0:
                progress = (campaign['completed_calls'] / campaign['total_recipients']) * 100
            
            return {
                'campaign_id': campaign_id,
                'campaign_name': campaign.get('campaign_name'),
                'status': campaign['status'],
                'total_recipients': campaign['total_recipients'],
                'completed_calls': campaign['completed_calls'],
                'successful_calls': campaign['successful_calls'],
                'failed_calls': campaign['failed_calls'],
                'appointments_booked': campaign['appointments_booked'],
                'progress_percentage': round(progress, 2),
                'current_recipient': current_recipient['phone_number'] if current_recipient else None,
                'started_at': campaign.get('started_at'),
                'estimated_completion': None
            }
        
        except Exception as e:
            logger.error(f"❌ Error getting campaign status: {str(e)}")
            raise
    
    async def get_campaign_recipients(
        self, 
        user_id: str, 
        campaign_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict]:
        """Get list of campaign recipients with call status"""
        try:
            recipients = await self.db.campaign_recipients.find({
                'campaign_id': campaign_id,
                'user_id': user_id
            }).skip(skip).limit(limit).to_list(length=limit)
            
            # Convert ObjectId to string
            for recipient in recipients:
                recipient['_id'] = str(recipient['_id'])
            
            return recipients
        
        except Exception as e:
            logger.error(f"❌ Error getting campaign recipients: {str(e)}")
            raise

    # ============================================
    # ✅ NEW METHODS ADDED BELOW
    # ============================================
    
    async def list_campaigns(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None
    ) -> List[Dict]:
        """List all campaigns for a user"""
        try:
            logger.info(f"📋 Listing campaigns for user: {user_id}")
            
            # Build query
            query = {'user_id': user_id}
            if status_filter:
                query['status'] = status_filter
            
            # Get campaigns
            campaigns = await self.db.bulk_campaigns.find(query)\
                .sort('created_at', -1)\
                .skip(skip)\
                .limit(limit)\
                .to_list(length=limit)
            
            # Convert ObjectId to string
            for campaign in campaigns:
                campaign['_id'] = str(campaign['_id'])
            
            logger.info(f"✅ Found {len(campaigns)} campaigns")
            return campaigns
        
        except Exception as e:
            logger.error(f"❌ Error listing campaigns: {str(e)}")
            raise
    
    async def get_campaign(
        self,
        user_id: str,
        campaign_id: str
    ) -> Optional[Dict]:
        """Get a specific campaign"""
        try:
            logger.info(f"🔍 Getting campaign: {campaign_id} for user: {user_id}")
            
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if campaign:
                campaign['_id'] = str(campaign['_id'])
                logger.info(f"✅ Found campaign: {campaign['campaign_name']}")
            else:
                logger.warning(f"⚠️ Campaign not found: {campaign_id}")
            
            return campaign
        
        except Exception as e:
            logger.error(f"❌ Error getting campaign: {str(e)}")
            raise
    
    async def delete_campaign(
        self,
        user_id: str,
        campaign_id: str
    ) -> Dict:
        """Delete a campaign"""
        try:
            logger.info(f"🗑️ Deleting campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            # Don't allow deletion of running campaigns
            if campaign['status'] == 'in_progress':
                raise ValueError("Cannot delete a running campaign. Please stop it first.")
            
            # Delete campaign recipients first
            await self.db.campaign_recipients.delete_many({
                'campaign_id': campaign_id,
                'user_id': user_id
            })
            
            # Delete campaign
            result = await self.db.bulk_campaigns.delete_one({
                '_id': ObjectId(campaign['_id'])
            })
            
            if result.deleted_count == 0:
                raise ValueError(f"Failed to delete campaign '{campaign_id}'")
            
            logger.info(f"✅ Deleted campaign {campaign_id}")
            
            return {
                'success': True,
                'message': 'Campaign deleted successfully',
                'campaign_id': campaign_id
            }
        
        except Exception as e:
            logger.error(f"❌ Error deleting campaign: {str(e)}")
            raise
    
    async def resume_campaign(
        self,
        user_id: str,
        campaign_id: str
    ) -> Dict:
        """Resume a paused campaign"""
        try:
            logger.info(f"▶️ Resuming campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            if campaign['status'] != 'paused':
                raise ValueError(f"Campaign is not paused. Current status: {campaign['status']}")
            
            # Update campaign status
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'status': 'in_progress',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Mark campaign as active
            self.active_campaigns[campaign_id] = True
            
            # Resume calling in background
            asyncio.create_task(
                self._execute_campaign_calls(
                    user_id,
                    campaign_id,
                    str(campaign['_id']),
                    campaign.get('custom_ai_script'),
                    1  # Default to 1 concurrent call
                )
            )
            
            logger.info(f"✅ Campaign {campaign_id} resumed")
            
            return {
                'success': True,
                'message': 'Campaign resumed successfully',
                'campaign_id': campaign_id,
                'status': 'in_progress'
            }
        
        except Exception as e:
            logger.error(f"❌ Error resuming campaign: {str(e)}")
            raise
    
    async def stop_campaign(
        self,
        user_id: str,
        campaign_id: str
    ) -> Dict:
        """Stop a running campaign"""
        try:
            logger.info(f"⏹️ Stopping campaign: {campaign_id}")
            
            # Get campaign
            campaign = await self.db.bulk_campaigns.find_one({
                'user_id': user_id,
                'campaign_id': campaign_id
            })
            
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            
            if campaign['status'] not in ['in_progress', 'paused']:
                raise ValueError(f"Campaign is not running. Current status: {campaign['status']}")
            
            # Mark campaign as stopped
            self.active_campaigns[campaign_id] = False
            
            # Update campaign status
            await self.db.bulk_campaigns.update_one(
                {'_id': ObjectId(campaign['_id'])},
                {
                    '$set': {
                        'status': 'stopped',
                        'stopped_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Campaign {campaign_id} stopped")
            
            return {
                'success': True,
                'message': 'Campaign stopped successfully',
                'campaign_id': campaign_id,
                'status': 'stopped'
            }
        
        except Exception as e:
            logger.error(f"❌ Error stopping campaign: {str(e)}")
            raise