# # backend/app/services/sms_campaign.py - 

# import logging
# import asyncio
# import csv
# import io
# import re
# from typing import Dict, Any, List, Optional
# from datetime import datetime, timedelta
# from bson import ObjectId

# from app.database import get_database
# from app.services.sms import sms_service

# logger = logging.getLogger(__name__)


# class SMSCampaignService:
#     """Service for handling bulk SMS campaigns"""
    
#     def __init__(self):
#         self.db = None
    
#     async def get_db(self):
#         """Get database instance - FIXED"""
#         if self.db is None:  # ✅ FIXED: Changed from 'if not self.db'
#             self.db = await get_database()
#         return self.db
    
#     # ============================================
#     # PHONE NUMBER VALIDATION & CLEANING
#     # ============================================
    
#     def clean_phone_number(self, phone: str) -> Optional[str]:
#         """
#         Clean and validate phone number
        
#         Edge cases:
#         - Handles spaces, dashes, parentheses
#         - Adds + prefix if missing
#         - Validates length (10-15 digits)
#         - Returns None if invalid
#         """
#         if not phone:
#             return None
        
#         # Remove all non-digit characters except +
#         cleaned = re.sub(r'[^\d+]', '', str(phone).strip())
        
#         # If no + prefix, add it (assume it's needed)
#         if not cleaned.startswith('+'):
#             cleaned = '+' + cleaned
        
#         # Validate format: + followed by 10-15 digits
#         if re.match(r'^\+\d{10,15}$', cleaned):
#             return cleaned
        
#         logger.warning(f"Invalid phone number format: {phone}")
#         return None
    
#     def validate_phone_numbers(self, phone_numbers: List[str]) -> Dict[str, Any]:
#         """
#         Validate list of phone numbers
        
#         Returns:
#             Dict with valid numbers, invalid numbers, and duplicates
#         """
#         valid = []
#         invalid = []
#         seen = set()
#         duplicates = []
        
#         for phone in phone_numbers:
#             cleaned = self.clean_phone_number(phone)
            
#             if not cleaned:
#                 invalid.append(phone)
#                 continue
            
#             if cleaned in seen:
#                 duplicates.append(cleaned)
#                 continue
            
#             seen.add(cleaned)
#             valid.append(cleaned)
        
#         return {
#             "valid": valid,
#             "invalid": invalid,
#             "duplicates": duplicates,
#             "total_valid": len(valid),
#             "total_invalid": len(invalid),
#             "total_duplicates": len(duplicates)
#         }
    
#     # ============================================
#     # CSV/EXCEL PARSING
#     # ============================================
    
#     async def parse_csv_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
#         """
#         Parse CSV file and extract phone numbers
        
#         Edge cases:
#         - Handles different CSV formats
#         - Detects headers automatically
#         - Finds phone column by common names
#         - Extracts name column if available
#         - Validates all numbers
#         """
#         try:
#             # Decode file content
#             content = file_content.decode('utf-8-sig')  # Handle BOM
            
#             # Parse CSV
#             csv_reader = csv.DictReader(io.StringIO(content))
            
#             # Try to detect phone and name columns
#             fieldnames = csv_reader.fieldnames
            
#             if not fieldnames:
#                 return {
#                     "success": False,
#                     "error": "CSV file is empty or has no headers"
#                 }
            
#             # Common phone column names
#             phone_columns = ['phone', 'phone_number', 'mobile', 'cell', 'number', 'telephone', 'contact']
#             name_columns = ['name', 'customer_name', 'full_name', 'contact_name', 'first_name']
            
#             # Find phone column
#             phone_col = None
#             for col in fieldnames:
#                 if col.lower().strip() in phone_columns:
#                     phone_col = col
#                     break
            
#             if not phone_col:
#                 # Try first column as phone
#                 phone_col = fieldnames[0]
#                 logger.warning(f"No phone column detected, using first column: {phone_col}")
            
#             # Find name column
#             name_col = None
#             for col in fieldnames:
#                 if col.lower().strip() in name_columns:
#                     name_col = col
#                     break
            
#             # Extract data
#             recipients = []
#             row_errors = []
            
#             for idx, row in enumerate(csv_reader, start=2):  # Start at 2 (after header)
#                 phone = row.get(phone_col, '').strip()
#                 name = row.get(name_col, '').strip() if name_col else None
                
#                 if not phone:
#                     row_errors.append(f"Row {idx}: Empty phone number")
#                     continue
                
#                 cleaned_phone = self.clean_phone_number(phone)
                
#                 if not cleaned_phone:
#                     row_errors.append(f"Row {idx}: Invalid phone number '{phone}'")
#                     continue
                
#                 recipients.append({
#                     "phone_number": cleaned_phone,
#                     "name": name or None
#                 })
            
#             # Validate all phone numbers
#             phone_numbers = [r["phone_number"] for r in recipients]
#             validation = self.validate_phone_numbers(phone_numbers)
            
#             # Remove duplicates from recipients
#             unique_recipients = []
#             seen = set()
            
#             for recipient in recipients:
#                 phone = recipient["phone_number"]
#                 if phone not in seen:
#                     seen.add(phone)
#                     unique_recipients.append(recipient)
            
#             return {
#                 "success": True,
#                 "recipients": unique_recipients,
#                 "total_recipients": len(unique_recipients),
#                 "validation": validation,
#                 "row_errors": row_errors,
#                 "detected_columns": {
#                     "phone": phone_col,
#                     "name": name_col
#                 }
#             }
        
#         except Exception as e:
#             logger.error(f"CSV parsing error: {e}")
#             return {
#                 "success": False,
#                 "error": f"Failed to parse CSV: {str(e)}"
#             }
    
#     # ============================================
#     # CAMPAIGN CREATION
#     # ============================================
    
#     async def create_campaign(
#         self,
#         user_id: str,
#         campaign_id: str,
#         message: str,
#         from_number: Optional[str],
#         recipients: List[Dict[str, Any]] = None,
#         campaign_name: Optional[str] = None,
#         batch_size: int = 25,
#         enable_replies: bool = True,
#         track_responses: bool = True
#     ) -> Dict[str, Any]:
#         """
#         Create new SMS campaign
        
#         Edge cases:
#         - Validates campaign_id uniqueness
#         - Validates all phone numbers
#         - Handles empty recipient list
#         - Calculates total batches
#         """
#         try:
#             db = await self.get_db()
            
#             logger.info(f"📝 Creating campaign: {campaign_id} for user: {user_id}")
            
#             # Check if campaign_id already exists for this user
#             existing = await db.sms_campaigns.find_one({
#                 "user_id": user_id,
#                 "campaign_id": campaign_id
#             })
            
#             if existing:
#                 logger.warning(f"Campaign ID '{campaign_id}' already exists")
#                 return {
#                     "success": False,
#                     "error": f"Campaign ID '{campaign_id}' already exists"
#                 }
            
#             # Prepare recipients
#             recipients = recipients or []
#             recipient_objects = []
            
#             for recipient in recipients:
#                 phone = self.clean_phone_number(recipient.get("phone_number", ""))
#                 if phone:
#                     recipient_objects.append({
#                         "phone_number": phone,
#                         "name": recipient.get("name"),
#                         "status": "pending",
#                         "twilio_sid": None,
#                         "error_message": None,
#                         "sent_at": None,
#                         "delivered_at": None
#                     })
            
#             total_recipients = len(recipient_objects)
#             total_batches = (total_recipients // batch_size) + (1 if total_recipients % batch_size else 0)
            
#             # Get from_number
#             if not from_number:
#                 import os
#                 from_number = os.getenv("TWILIO_PHONE_NUMBER")
            
#             logger.info(f"✅ Campaign will have {total_recipients} recipients in {total_batches} batches")
            
#             # Create campaign document
#             campaign_data = {
#                 "user_id": user_id,
#                 "campaign_id": campaign_id,
#                 "campaign_name": campaign_name,
#                 "message": message,
#                 "from_number": from_number,
#                 "recipients": recipient_objects,
#                 "total_recipients": total_recipients,
#                 "status": "pending",
#                 "sent_count": 0,
#                 "delivered_count": 0,
#                 "failed_count": 0,
#                 "upload_source": "manual",
#                 "uploaded_file_name": None,
#                 "batch_size": batch_size,
#                 "current_batch": 0,
#                 "total_batches": total_batches,
#                 "enable_replies": enable_replies,
#                 "track_responses": track_responses,
#                 "created_at": datetime.utcnow(),
#                 "started_at": None,
#                 "completed_at": None,
#                 "updated_at": datetime.utcnow(),
#                 "errors": []
#             }
            
#             result = await db.sms_campaigns.insert_one(campaign_data)
#             campaign_data["_id"] = str(result.inserted_id)
            
#             logger.info(f"✅ Campaign created: {campaign_id} with {total_recipients} recipients")
            
#             return {
#                 "success": True,
#                 "campaign": campaign_data
#             }
        
#         except Exception as e:
#             logger.error(f"❌ Error creating campaign: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     # ============================================
#     # ADD RECIPIENTS TO CAMPAIGN
#     # ============================================
    
#     async def add_recipients_to_campaign(
#         self,
#         campaign_id: str,
#         user_id: str,
#         recipients: List[Dict[str, Any]],
#         source: str = "manual"
#     ) -> Dict[str, Any]:
#         """
#         Add recipients to existing campaign
        
#         Edge cases:
#         - Campaign must be in 'pending' status
#         - Validates all phone numbers
#         - Removes duplicates
#         - Updates batch count
#         """
#         try:
#             db = await self.get_db()
            
#             # Get campaign
#             campaign = await db.sms_campaigns.find_one({
#                 "campaign_id": campaign_id,
#                 "user_id": user_id
#             })
            
#             if not campaign:
#                 return {
#                     "success": False,
#                     "error": "Campaign not found"
#                 }
            
#             if campaign["status"] != "pending":
#                 return {
#                     "success": False,
#                     "error": f"Cannot add recipients to campaign with status '{campaign['status']}'"
#                 }
            
#             # Get existing phone numbers
#             existing_phones = set(r["phone_number"] for r in campaign.get("recipients", []))
            
#             # Prepare new recipients
#             new_recipients = []
#             duplicates = 0
            
#             for recipient in recipients:
#                 phone = self.clean_phone_number(recipient.get("phone_number", ""))
                
#                 if not phone:
#                     continue
                
#                 if phone in existing_phones:
#                     duplicates += 1
#                     continue
                
#                 existing_phones.add(phone)
#                 new_recipients.append({
#                     "phone_number": phone,
#                     "name": recipient.get("name"),
#                     "status": "pending",
#                     "twilio_sid": None,
#                     "error_message": None,
#                     "sent_at": None,
#                     "delivered_at": None
#                 })
            
#             if not new_recipients:
#                 return {
#                     "success": False,
#                     "error": "No valid new recipients to add",
#                     "duplicates": duplicates
#                 }
            
#             # Update campaign
#             updated_total = campaign["total_recipients"] + len(new_recipients)
#             batch_size = campaign["batch_size"]
#             updated_batches = (updated_total // batch_size) + (1 if updated_total % batch_size else 0)
            
#             await db.sms_campaigns.update_one(
#                 {"_id": ObjectId(campaign["_id"])},
#                 {
#                     "$push": {"recipients": {"$each": new_recipients}},
#                     "$set": {
#                         "total_recipients": updated_total,
#                         "total_batches": updated_batches,
#                         "updated_at": datetime.utcnow()
#                     }
#                 }
#             )
            
#             logger.info(f"✅ Added {len(new_recipients)} recipients to campaign {campaign_id}")
            
#             return {
#                 "success": True,
#                 "added_count": len(new_recipients),
#                 "duplicates": duplicates,
#                 "total_recipients": updated_total
#             }
        
#         except Exception as e:
#             logger.error(f"Error adding recipients: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     # ============================================
#     # START CAMPAIGN
#     # ============================================
    
#     async def start_campaign(
#         self,
#         campaign_id: str,
#         user_id: str
#     ) -> Dict[str, Any]:
#         """
#         Start sending campaign
        
#         Edge cases:
#         - Campaign must be 'pending'
#         - Must have at least one recipient
#         - Validates Twilio configuration
#         - Sends in batches with delays
#         """
#         try:
#             db = await self.get_db()
            
#             # Get campaign
#             campaign = await db.sms_campaigns.find_one({
#                 "campaign_id": campaign_id,
#                 "user_id": user_id
#             })
            
#             if not campaign:
#                 return {
#                     "success": False,
#                     "error": "Campaign not found"
#                 }
            
#             if campaign["status"] not in ["pending", "failed"]:
#                 return {
#                     "success": False,
#                     "error": f"Campaign status is '{campaign['status']}', cannot start"
#                 }
            
#             if campaign["total_recipients"] == 0:
#                 return {
#                     "success": False,
#                     "error": "Campaign has no recipients"
#                 }
            
#             # Update status to in_progress
#             await db.sms_campaigns.update_one(
#                 {"_id": ObjectId(campaign["_id"])},
#                 {
#                     "$set": {
#                         "status": "in_progress",
#                         "started_at": datetime.utcnow(),
#                         "updated_at": datetime.utcnow()
#                     }
#                 }
#             )
            
#             logger.info(f"🚀 Starting campaign: {campaign_id}")
            
#             # Start sending in background
#             asyncio.create_task(self._send_campaign_batches(str(campaign["_id"]), user_id))
            
#             return {
#                 "success": True,
#                 "message": "Campaign started",
#                 "campaign_id": campaign_id
#             }
        
#         except Exception as e:
#             logger.error(f"Error starting campaign: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def _send_campaign_batches(
#         self,
#         campaign_object_id: str,
#         user_id: str
#     ):
#         """
#         Send campaign in batches (background task)
        
#         Edge cases:
#         - Handles Twilio rate limits
#         - Retries failed messages
#         - Updates status in real-time
#         - Logs all sends to sms_messages and sms_logs
#         """
#         try:
#             db = await self.get_db()
            
#             # Get campaign
#             campaign = await db.sms_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            
#             if not campaign:
#                 logger.error("Campaign not found")
#                 return
            
#             campaign_id = campaign["campaign_id"]
#             message = campaign["message"]
#             from_number = campaign["from_number"]
#             batch_size = campaign["batch_size"]
#             recipients = campaign["recipients"]
            
#             logger.info(f"📤 Sending {len(recipients)} messages in batches of {batch_size}")
            
#             # Process in batches
#             for batch_num, i in enumerate(range(0, len(recipients), batch_size), start=1):
#                 batch_recipients = recipients[i:i + batch_size]
                
#                 logger.info(f"📦 Batch {batch_num}/{campaign['total_batches']}: Sending {len(batch_recipients)} messages")
                
#                 # Update current batch
#                 await db.sms_campaigns.update_one(
#                     {"_id": ObjectId(campaign_object_id)},
#                     {"$set": {"current_batch": batch_num}}
#                 )
                
#                 # Send messages in this batch
#                 for idx, recipient in enumerate(batch_recipients):
#                     phone = recipient["phone_number"]
                    
#                     try:
#                         # Send SMS
#                         result = await sms_service.send_sms(
#                             to_number=phone,
#                             message=message,
#                             from_number=from_number,
#                             user_id=user_id,
#                             campaign_id=campaign_id,
#                             customer_name=recipient.get("name")
#                         )
                        
#                         if result.get("success"):
#                             # Update recipient status
#                             await db.sms_campaigns.update_one(
#                                 {
#                                     "_id": ObjectId(campaign_object_id),
#                                     "recipients.phone_number": phone
#                                 },
#                                 {
#                                     "$set": {
#                                         "recipients.$.status": "sent",
#                                         "recipients.$.twilio_sid": result.get("twilio_sid"),
#                                         "recipients.$.sent_at": datetime.utcnow()
#                                     },
#                                     "$inc": {"sent_count": 1}
#                                 }
#                             )
                            
#                             logger.info(f"  ✅ {idx+1}/{len(batch_recipients)}: Sent to {phone}")
                        
#                         else:
#                             # Update recipient as failed
#                             error_msg = result.get("error", "Unknown error")
                            
#                             await db.sms_campaigns.update_one(
#                                 {
#                                     "_id": ObjectId(campaign_object_id),
#                                     "recipients.phone_number": phone
#                                 },
#                                 {
#                                     "$set": {
#                                         "recipients.$.status": "failed",
#                                         "recipients.$.error_message": error_msg
#                                     },
#                                     "$inc": {"failed_count": 1},
#                                     "$push": {
#                                         "errors": {
#                                             "phone": phone,
#                                             "error": error_msg,
#                                             "timestamp": datetime.utcnow()
#                                         }
#                                     }
#                                 }
#                             )
                            
#                             logger.error(f"  ❌ {idx+1}/{len(batch_recipients)}: Failed to {phone}: {error_msg}")
                    
#                     except Exception as e:
#                         logger.error(f"  ❌ Error sending to {phone}: {e}")
                        
#                         await db.sms_campaigns.update_one(
#                             {
#                                 "_id": ObjectId(campaign_object_id),
#                                 "recipients.phone_number": phone
#                             },
#                             {
#                                 "$set": {
#                                     "recipients.$.status": "failed",
#                                     "recipients.$.error_message": str(e)
#                                 },
#                                 "$inc": {"failed_count": 1},
#                                 "$push": {
#                                     "errors": {
#                                         "phone": phone,
#                                         "error": str(e),
#                                         "timestamp": datetime.utcnow()
#                                     }
#                                 }
#                             }
#                         )
                    
#                     # Small delay between messages to avoid rate limits
#                     await asyncio.sleep(0.5)
                
#                 # Delay between batches (avoid Twilio rate limits)
#                 if batch_num < campaign["total_batches"]:
#                     logger.info(f"⏳ Waiting 10 seconds before next batch...")
#                     await asyncio.sleep(10)
            
#             # Mark campaign as completed
#             final_campaign = await db.sms_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            
#             final_status = "completed"
#             if final_campaign["sent_count"] == 0:
#                 final_status = "failed"
#             elif final_campaign["failed_count"] > 0:
#                 final_status = "completed_with_errors"
            
#             await db.sms_campaigns.update_one(
#                 {"_id": ObjectId(campaign_object_id)},
#                 {
#                     "$set": {
#                         "status": final_status,
#                         "completed_at": datetime.utcnow(),
#                         "updated_at": datetime.utcnow()
#                     }
#                 }
#             )
            
#             logger.info(f"✅ Campaign completed: {campaign_id}")
#             logger.info(f"   Sent: {final_campaign['sent_count']}")
#             logger.info(f"   Failed: {final_campaign['failed_count']}")
        
#         except Exception as e:
#             logger.error(f"Error in campaign batch processing: {e}")
#             import traceback
#             traceback.print_exc()
            
#             # Mark campaign as failed
#             try:
#                 await db.sms_campaigns.update_one(
#                     {"_id": ObjectId(campaign_object_id)},
#                     {
#                         "$set": {
#                             "status": "failed",
#                             "updated_at": datetime.utcnow()
#                         },
#                         "$push": {
#                             "errors": {
#                                 "error": f"Campaign processing failed: {str(e)}",
#                                 "timestamp": datetime.utcnow()
#                             }
#                         }
#                     }
#                 )
#             except:
#                 pass
    
#     # ============================================
#     # GET CAMPAIGNS
#     # ============================================
    
#     async def get_campaign(
#         self,
#         campaign_id: str,
#         user_id: str
#     ) -> Optional[Dict[str, Any]]:
#         """Get campaign by ID"""
#         try:
#             db = await self.get_db()
            
#             campaign = await db.sms_campaigns.find_one({
#                 "campaign_id": campaign_id,
#                 "user_id": user_id
#             })
            
#             if campaign:
#                 campaign["_id"] = str(campaign["_id"])
#                 return campaign
            
#             return None
        
#         except Exception as e:
#             logger.error(f"Error getting campaign: {e}")
#             return None
    
#     async def get_campaigns(
#         self,
#         user_id: str,
#         skip: int = 0,
#         limit: int = 50,
#         status: Optional[str] = None
#     ) -> List[Dict[str, Any]]:
#         """Get list of campaigns"""
#         try:
#             db = await self.get_db()
            
#             query = {"user_id": user_id}
#             if status:
#                 query["status"] = status
            
#             cursor = db.sms_campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
#             campaigns = await cursor.to_list(length=limit)
            
#             # Convert ObjectId to string
#             for campaign in campaigns:
#                 campaign["_id"] = str(campaign["_id"])
            
#             return campaigns
        
#         except Exception as e:
#             logger.error(f"Error getting campaigns: {e}")
#             return []
    
#     # ============================================
#     # DELETE CAMPAIGN
#     # ============================================
    
#     async def delete_campaign(
#         self,
#         campaign_id: str,
#         user_id: str
#     ) -> bool:
#         """
#         Delete campaign
        
#         Edge case: Can only delete if status is pending, completed, or failed
#         """
#         try:
#             db = await self.get_db()
            
#             campaign = await db.sms_campaigns.find_one({
#                 "campaign_id": campaign_id,
#                 "user_id": user_id
#             })
            
#             if not campaign:
#                 return False
            
#             if campaign["status"] == "in_progress":
#                 logger.warning(f"Cannot delete campaign {campaign_id} - in progress")
#                 return False
            
#             result = await db.sms_campaigns.delete_one({
#                 "campaign_id": campaign_id,
#                 "user_id": user_id
#             })
            
#             return result.deleted_count > 0
        
#         except Exception as e:
#             logger.error(f"Error deleting campaign: {e}")
#             return False


# # Create singleton instance
# sms_campaign_service = SMSCampaignService()


# backend/app/services/sms_campaign.py - UPDATED WITH CUSTOM AI SCRIPT

import logging
import asyncio
import csv
import io
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from app.database import get_database
from app.services.sms import sms_service

logger = logging.getLogger(__name__)


class SMSCampaignService:
    """Service for handling bulk SMS campaigns"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database instance - FIXED"""
        if self.db is None:  # ✅ FIXED: Changed from 'if not self.db'
            self.db = await get_database()
        return self.db
    
    # ============================================
    # PHONE NUMBER VALIDATION & CLEANING
    # ============================================
    
    def clean_phone_number(self, phone: str) -> Optional[str]:
        """
        Clean and validate phone number
        
        Edge cases:
        - Handles spaces, dashes, parentheses
        - Adds + prefix if missing
        - Validates length (10-15 digits)
        - Returns None if invalid
        """
        if not phone:
            return None
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', str(phone).strip())
        
        # If no + prefix, add it (assume it's needed)
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        # Validate format: + followed by 10-15 digits
        if re.match(r'^\+\d{10,15}$', cleaned):
            return cleaned
        
        logger.warning(f"Invalid phone number format: {phone}")
        return None
    
    def validate_phone_numbers(self, phone_numbers: List[str]) -> Dict[str, Any]:
        """
        Validate list of phone numbers
        
        Returns:
            Dict with valid numbers, invalid numbers, and duplicates
        """
        valid = []
        invalid = []
        seen = set()
        duplicates = []
        
        for phone in phone_numbers:
            cleaned = self.clean_phone_number(phone)
            
            if not cleaned:
                invalid.append(phone)
                continue
            
            if cleaned in seen:
                duplicates.append(cleaned)
                continue
            
            seen.add(cleaned)
            valid.append(cleaned)
        
        return {
            "valid": valid,
            "invalid": invalid,
            "duplicates": duplicates,
            "total_valid": len(valid),
            "total_invalid": len(invalid),
            "total_duplicates": len(duplicates)
        }
    
    # ============================================
    # CSV/EXCEL PARSING
    # ============================================
    
    async def parse_csv_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse CSV file and extract phone numbers
        
        Edge cases:
        - Handles different CSV formats
        - Detects headers automatically
        - Finds phone column by common names
        - Extracts name column if available
        - Validates all numbers
        """
        try:
            # Decode file content
            content = file_content.decode('utf-8-sig')  # Handle BOM
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # Try to detect phone and name columns
            fieldnames = csv_reader.fieldnames
            
            if not fieldnames:
                return {
                    "success": False,
                    "error": "CSV file is empty or has no headers"
                }
            
            # Common phone column names
            phone_columns = ['phone', 'phone_number', 'mobile', 'cell', 'number', 'telephone', 'contact']
            name_columns = ['name', 'customer_name', 'full_name', 'contact_name', 'first_name']
            
            # Find phone column
            phone_col = None
            for col in fieldnames:
                if col.lower().strip() in phone_columns:
                    phone_col = col
                    break
            
            if not phone_col:
                # Try first column as phone
                phone_col = fieldnames[0]
                logger.warning(f"No phone column detected, using first column: {phone_col}")
            
            # Find name column
            name_col = None
            for col in fieldnames:
                if col.lower().strip() in name_columns:
                    name_col = col
                    break
            
            # Extract data
            recipients = []
            row_errors = []
            
            for idx, row in enumerate(csv_reader, start=2):  # Start at 2 (after header)
                phone = row.get(phone_col, '').strip()
                name = row.get(name_col, '').strip() if name_col else None
                
                if not phone:
                    row_errors.append(f"Row {idx}: Empty phone number")
                    continue
                
                cleaned_phone = self.clean_phone_number(phone)
                
                if not cleaned_phone:
                    row_errors.append(f"Row {idx}: Invalid phone number '{phone}'")
                    continue
                
                recipients.append({
                    "phone_number": cleaned_phone,
                    "name": name or None
                })
            
            # Validate all phone numbers
            phone_numbers = [r["phone_number"] for r in recipients]
            validation = self.validate_phone_numbers(phone_numbers)
            
            # Remove duplicates from recipients
            unique_recipients = []
            seen = set()
            
            for recipient in recipients:
                phone = recipient["phone_number"]
                if phone not in seen:
                    seen.add(phone)
                    unique_recipients.append(recipient)
            
            return {
                "success": True,
                "recipients": unique_recipients,
                "total_recipients": len(unique_recipients),
                "validation": validation,
                "row_errors": row_errors,
                "detected_columns": {
                    "phone": phone_col,
                    "name": name_col
                }
            }
        
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            return {
                "success": False,
                "error": f"Failed to parse CSV: {str(e)}"
            }
    
    # ============================================
    # CAMPAIGN CREATION - 🆕 UPDATED WITH CUSTOM AI SCRIPT
    # ============================================
    
    async def create_campaign(
        self,
        user_id: str,
        campaign_id: str,
        message: str,
        from_number: Optional[str],
        recipients: List[Dict[str, Any]] = None,
        campaign_name: Optional[str] = None,
        batch_size: int = 25,
        enable_replies: bool = True,
        track_responses: bool = True,
        custom_ai_script: Optional[str] = None  # 🆕 NEW PARAMETER ADDED
    ) -> Dict[str, Any]:
        """
        Create new SMS campaign
        
        Edge cases:
        - Validates campaign_id uniqueness
        - Validates all phone numbers
        - Handles empty recipient list
        - Calculates total batches
        - 🆕 Validates and stores custom AI script
        """
        try:
            db = await self.get_db()
            
            logger.info(f"📝 Creating campaign: {campaign_id} for user: {user_id}")
            
            # 🆕 VALIDATE CUSTOM AI SCRIPT
            if custom_ai_script:
                custom_ai_script = custom_ai_script.strip()
                if len(custom_ai_script) < 10:
                    logger.warning(f"Custom AI script too short, ignoring")
                    custom_ai_script = None
                else:
                    logger.info(f"✅ Custom AI script provided: {len(custom_ai_script)} characters")
            
            # Check if campaign_id already exists for this user
            existing = await db.sms_campaigns.find_one({
                "user_id": user_id,
                "campaign_id": campaign_id
            })
            
            if existing:
                logger.warning(f"Campaign ID '{campaign_id}' already exists")
                return {
                    "success": False,
                    "error": f"Campaign ID '{campaign_id}' already exists"
                }
            
            # Prepare recipients
            recipients = recipients or []
            recipient_objects = []
            
            for recipient in recipients:
                phone = self.clean_phone_number(recipient.get("phone_number", ""))
                if phone:
                    recipient_objects.append({
                        "phone_number": phone,
                        "name": recipient.get("name"),
                        "status": "pending",
                        "twilio_sid": None,
                        "error_message": None,
                        "sent_at": None,
                        "delivered_at": None
                    })
            
            total_recipients = len(recipient_objects)
            total_batches = (total_recipients // batch_size) + (1 if total_recipients % batch_size else 0)
            
            # Get from_number
            if not from_number:
                import os
                from_number = os.getenv("TWILIO_PHONE_NUMBER")
            
            logger.info(f"✅ Campaign will have {total_recipients} recipients in {total_batches} batches")
            
            # Create campaign document
            campaign_data = {
                "user_id": user_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "message": message,
                "from_number": from_number,
                "custom_ai_script": custom_ai_script,  # 🆕 STORE CUSTOM SCRIPT
                "recipients": recipient_objects,
                "total_recipients": total_recipients,
                "status": "pending",
                "sent_count": 0,
                "delivered_count": 0,
                "failed_count": 0,
                "upload_source": "manual",
                "uploaded_file_name": None,
                "batch_size": batch_size,
                "current_batch": 0,
                "total_batches": total_batches,
                "enable_replies": enable_replies,
                "track_responses": track_responses,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "updated_at": datetime.utcnow(),
                "errors": []
            }
            
            result = await db.sms_campaigns.insert_one(campaign_data)
            campaign_data["_id"] = str(result.inserted_id)
            
            logger.info(f"✅ Campaign created: {campaign_id} with {total_recipients} recipients")
            if custom_ai_script:
                logger.info(f"   📝 Custom AI script: Enabled")
            
            return {
                "success": True,
                "campaign": campaign_data
            }
        
        except Exception as e:
            logger.error(f"❌ Error creating campaign: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============================================
    # ADD RECIPIENTS TO CAMPAIGN
    # ============================================
    
    async def add_recipients_to_campaign(
        self,
        campaign_id: str,
        user_id: str,
        recipients: List[Dict[str, Any]],
        source: str = "manual"
    ) -> Dict[str, Any]:
        """
        Add recipients to existing campaign
        
        Edge cases:
        - Campaign must be in 'pending' status
        - Validates all phone numbers
        - Removes duplicates
        - Updates batch count
        """
        try:
            db = await self.get_db()
            
            # Get campaign
            campaign = await db.sms_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            
            if not campaign:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            if campaign["status"] != "pending":
                return {
                    "success": False,
                    "error": f"Cannot add recipients to campaign with status '{campaign['status']}'"
                }
            
            # Get existing phone numbers
            existing_phones = set(r["phone_number"] for r in campaign.get("recipients", []))
            
            # Prepare new recipients
            new_recipients = []
            duplicates = 0
            
            for recipient in recipients:
                phone = self.clean_phone_number(recipient.get("phone_number", ""))
                
                if not phone:
                    continue
                
                if phone in existing_phones:
                    duplicates += 1
                    continue
                
                existing_phones.add(phone)
                new_recipients.append({
                    "phone_number": phone,
                    "name": recipient.get("name"),
                    "status": "pending",
                    "twilio_sid": None,
                    "error_message": None,
                    "sent_at": None,
                    "delivered_at": None
                })
            
            if not new_recipients:
                return {
                    "success": False,
                    "error": "No valid new recipients to add",
                    "duplicates": duplicates
                }
            
            # Update campaign
            updated_total = campaign["total_recipients"] + len(new_recipients)
            batch_size = campaign["batch_size"]
            updated_batches = (updated_total // batch_size) + (1 if updated_total % batch_size else 0)
            
            await db.sms_campaigns.update_one(
                {"_id": ObjectId(campaign["_id"])},
                {
                    "$push": {"recipients": {"$each": new_recipients}},
                    "$set": {
                        "total_recipients": updated_total,
                        "total_batches": updated_batches,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Added {len(new_recipients)} recipients to campaign {campaign_id}")
            
            return {
                "success": True,
                "added_count": len(new_recipients),
                "duplicates": duplicates,
                "total_recipients": updated_total
            }
        
        except Exception as e:
            logger.error(f"Error adding recipients: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============================================
    # START CAMPAIGN
    # ============================================
    
    async def start_campaign(
        self,
        campaign_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Start sending campaign
        
        Edge cases:
        - Campaign must be 'pending'
        - Must have at least one recipient
        - Validates Twilio configuration
        - Sends in batches with delays
        """
        try:
            db = await self.get_db()
            
            # Get campaign
            campaign = await db.sms_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            
            if not campaign:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            if campaign["status"] not in ["pending", "failed"]:
                return {
                    "success": False,
                    "error": f"Campaign status is '{campaign['status']}', cannot start"
                }
            
            if campaign["total_recipients"] == 0:
                return {
                    "success": False,
                    "error": "Campaign has no recipients"
                }
            
            # Update status to in_progress
            await db.sms_campaigns.update_one(
                {"_id": ObjectId(campaign["_id"])},
                {
                    "$set": {
                        "status": "in_progress",
                        "started_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"🚀 Starting campaign: {campaign_id}")
            
            # Start sending in background
            asyncio.create_task(self._send_campaign_batches(str(campaign["_id"]), user_id))
            
            return {
                "success": True,
                "message": "Campaign started",
                "campaign_id": campaign_id
            }
        
        except Exception as e:
            logger.error(f"Error starting campaign: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_campaign_batches(
        self,
        campaign_object_id: str,
        user_id: str
    ):
        """
        Send campaign in batches (background task)
        
        Edge cases:
        - Handles Twilio rate limits
        - Retries failed messages
        - Updates status in real-time
        - Logs all sends to sms_messages and sms_logs
        """
        try:
            db = await self.get_db()
            
            # Get campaign
            campaign = await db.sms_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            
            if not campaign:
                logger.error("Campaign not found")
                return
            
            campaign_id = campaign["campaign_id"]
            message = campaign["message"]
            from_number = campaign["from_number"]
            batch_size = campaign["batch_size"]
            recipients = campaign["recipients"]
            
            logger.info(f"📤 Sending {len(recipients)} messages in batches of {batch_size}")
            
            # Process in batches
            for batch_num, i in enumerate(range(0, len(recipients), batch_size), start=1):
                batch_recipients = recipients[i:i + batch_size]
                
                logger.info(f"📦 Batch {batch_num}/{campaign['total_batches']}: Sending {len(batch_recipients)} messages")
                
                # Update current batch
                await db.sms_campaigns.update_one(
                    {"_id": ObjectId(campaign_object_id)},
                    {"$set": {"current_batch": batch_num}}
                )
                
                # Send messages in this batch
                for idx, recipient in enumerate(batch_recipients):
                    phone = recipient["phone_number"]
                    
                    try:
                        # Send SMS
                        result = await sms_service.send_sms(
                            to_number=phone,
                            message=message,
                            from_number=from_number,
                            user_id=user_id,
                            campaign_id=campaign_id,
                            customer_name=recipient.get("name")
                        )
                        
                        if result.get("success"):
                            # Update recipient status
                            await db.sms_campaigns.update_one(
                                {
                                    "_id": ObjectId(campaign_object_id),
                                    "recipients.phone_number": phone
                                },
                                {
                                    "$set": {
                                        "recipients.$.status": "sent",
                                        "recipients.$.twilio_sid": result.get("twilio_sid"),
                                        "recipients.$.sent_at": datetime.utcnow()
                                    },
                                    "$inc": {"sent_count": 1}
                                }
                            )
                            
                            logger.info(f"  ✅ {idx+1}/{len(batch_recipients)}: Sent to {phone}")
                        
                        else:
                            # Update recipient as failed
                            error_msg = result.get("error", "Unknown error")
                            
                            await db.sms_campaigns.update_one(
                                {
                                    "_id": ObjectId(campaign_object_id),
                                    "recipients.phone_number": phone
                                },
                                {
                                    "$set": {
                                        "recipients.$.status": "failed",
                                        "recipients.$.error_message": error_msg
                                    },
                                    "$inc": {"failed_count": 1},
                                    "$push": {
                                        "errors": {
                                            "phone": phone,
                                            "error": error_msg,
                                            "timestamp": datetime.utcnow()
                                        }
                                    }
                                }
                            )
                            
                            logger.error(f"  ❌ {idx+1}/{len(batch_recipients)}: Failed to {phone}: {error_msg}")
                    
                    except Exception as e:
                        logger.error(f"  ❌ Error sending to {phone}: {e}")
                        
                        await db.sms_campaigns.update_one(
                            {
                                "_id": ObjectId(campaign_object_id),
                                "recipients.phone_number": phone
                            },
                            {
                                "$set": {
                                    "recipients.$.status": "failed",
                                    "recipients.$.error_message": str(e)
                                },
                                "$inc": {"failed_count": 1},
                                "$push": {
                                    "errors": {
                                        "phone": phone,
                                        "error": str(e),
                                        "timestamp": datetime.utcnow()
                                    }
                                }
                            }
                        )
                    
                    # Small delay between messages to avoid rate limits
                    await asyncio.sleep(0.5)
                
                # Delay between batches (avoid Twilio rate limits)
                if batch_num < campaign["total_batches"]:
                    logger.info(f"⏳ Waiting 10 seconds before next batch...")
                    await asyncio.sleep(10)
            
            # Mark campaign as completed
            final_campaign = await db.sms_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            
            final_status = "completed"
            if final_campaign["sent_count"] == 0:
                final_status = "failed"
            elif final_campaign["failed_count"] > 0:
                final_status = "completed_with_errors"
            
            await db.sms_campaigns.update_one(
                {"_id": ObjectId(campaign_object_id)},
                {
                    "$set": {
                        "status": final_status,
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Campaign completed: {campaign_id}")
            logger.info(f"   Sent: {final_campaign['sent_count']}")
            logger.info(f"   Failed: {final_campaign['failed_count']}")
        
        except Exception as e:
            logger.error(f"Error in campaign batch processing: {e}")
            import traceback
            traceback.print_exc()
            
            # Mark campaign as failed
            try:
                await db.sms_campaigns.update_one(
                    {"_id": ObjectId(campaign_object_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "updated_at": datetime.utcnow()
                        },
                        "$push": {
                            "errors": {
                                "error": f"Campaign processing failed: {str(e)}",
                                "timestamp": datetime.utcnow()
                            }
                        }
                    }
                )
            except:
                pass
    
    # ============================================
    # GET CAMPAIGNS
    # ============================================
    
    async def get_campaign(
        self,
        campaign_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get campaign by ID"""
        try:
            db = await self.get_db()
            
            campaign = await db.sms_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            
            if campaign:
                campaign["_id"] = str(campaign["_id"])
                return campaign
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting campaign: {e}")
            return None
    
    async def get_campaigns(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of campaigns"""
        try:
            db = await self.get_db()
            
            query = {"user_id": user_id}
            if status:
                query["status"] = status
            
            cursor = db.sms_campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
            campaigns = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for campaign in campaigns:
                campaign["_id"] = str(campaign["_id"])
            
            return campaigns
        
        except Exception as e:
            logger.error(f"Error getting campaigns: {e}")
            return []
    
    # ============================================
    # DELETE CAMPAIGN
    # ============================================
    
    async def delete_campaign(
        self,
        campaign_id: str,
        user_id: str
    ) -> bool:
        """
        Delete campaign
        
        Edge case: Can only delete if status is pending, completed, or failed
        """
        try:
            db = await self.get_db()
            
            campaign = await db.sms_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            
            if not campaign:
                return False
            
            if campaign["status"] == "in_progress":
                logger.warning(f"Cannot delete campaign {campaign_id} - in progress")
                return False
            
            result = await db.sms_campaigns.delete_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            
            return result.deleted_count > 0
        
        except Exception as e:
            logger.error(f"Error deleting campaign: {e}")
            return False


# Create singleton instance
sms_campaign_service = SMSCampaignService()