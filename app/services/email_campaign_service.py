# backend/app/services/email_campaign_service.py - Bulk Email Campaign Service

import logging
import asyncio
import csv
import io
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId

from app.database import get_database
from app.services.email_automation import email_automation_service

logger = logging.getLogger(__name__)


class EmailCampaignService:
    """Service for handling bulk email campaigns"""

    def __init__(self):
        self.db = None

    async def get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    # ============================================
    # EMAIL VALIDATION
    # ============================================

    def clean_email(self, email: str) -> Optional[str]:
        """Clean and validate email address"""
        if not email:
            return None
        email = email.strip().lower()
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return email
        logger.warning(f"Invalid email format: {email}")
        return None

    def validate_emails(self, emails: List[str]) -> Dict[str, Any]:
        """Validate list of emails, return valid/invalid/duplicates"""
        valid = []
        invalid = []
        seen = set()
        duplicates = []

        for email in emails:
            cleaned = self.clean_email(email)
            if not cleaned:
                invalid.append(email)
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
    # CSV PARSING
    # ============================================

    async def parse_csv_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse CSV file and extract email addresses"""
        try:
            content = file_content.decode('utf-8-sig')
            csv_reader = csv.DictReader(io.StringIO(content))
            fieldnames = csv_reader.fieldnames

            if not fieldnames:
                return {"success": False, "error": "CSV file is empty or has no headers"}

            # Common email column names
            email_columns = ['email', 'email_address', 'e-mail', 'mail', 'contact_email']
            name_columns = ['name', 'customer_name', 'full_name', 'contact_name', 'first_name']

            # Find email column
            email_col = None
            for col in fieldnames:
                if col.lower().strip() in email_columns:
                    email_col = col
                    break
            if not email_col:
                email_col = fieldnames[0]
                logger.warning(f"No email column detected, using first column: {email_col}")

            # Find name column
            name_col = None
            for col in fieldnames:
                if col.lower().strip() in name_columns:
                    name_col = col
                    break

            recipients = []
            row_errors = []

            for idx, row in enumerate(csv_reader, start=2):
                email = row.get(email_col, '').strip()
                name = row.get(name_col, '').strip() if name_col else None

                if not email:
                    row_errors.append(f"Row {idx}: Empty email")
                    continue

                cleaned_email = self.clean_email(email)
                if not cleaned_email:
                    row_errors.append(f"Row {idx}: Invalid email '{email}'")
                    continue

                recipients.append({
                    "email": cleaned_email,
                    "name": name or None
                })

            # Remove duplicates
            unique_recipients = []
            seen = set()
            for recipient in recipients:
                if recipient["email"] not in seen:
                    seen.add(recipient["email"])
                    unique_recipients.append(recipient)

            return {
                "success": True,
                "recipients": unique_recipients,
                "total_recipients": len(unique_recipients),
                "row_errors": row_errors,
                "detected_columns": {
                    "email": email_col,
                    "name": name_col
                }
            }

        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            return {"success": False, "error": f"Failed to parse CSV: {str(e)}"}

    # ============================================
    # CAMPAIGN CREATION
    # ============================================

    async def create_campaign(
        self,
        user_id: str,
        campaign_id: str,
        subject: str,
        message: str,
        recipients: List[Dict[str, Any]] = None,
        campaign_name: Optional[str] = None,
        batch_size: int = 25,
    ) -> Dict[str, Any]:
        try:
            db = await self.get_db()
            logger.info(f"📝 Creating email campaign: {campaign_id} for user: {user_id}")

            # Check uniqueness
            existing = await db.email_bulk_campaigns.find_one({
                "user_id": user_id,
                "campaign_id": campaign_id
            })
            if existing:
                return {"success": False, "error": f"Campaign ID '{campaign_id}' already exists"}

            # Prepare recipients
            recipients = recipients or []
            recipient_objects = []
            for r in recipients:
                email = self.clean_email(r.get("email", ""))
                if email:
                    recipient_objects.append({
                        "email": email,
                        "name": r.get("name"),
                        "status": "pending",
                        "error_message": None,
                        "sent_at": None,
                    })

            total_recipients = len(recipient_objects)
            total_batches = (total_recipients // batch_size) + (1 if total_recipients % batch_size else 0)

            campaign_data = {
                "user_id": user_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "subject": subject,
                "message": message,
                "recipients": recipient_objects,
                "total_recipients": total_recipients,
                "status": "pending",
                "sent_count": 0,
                "failed_count": 0,
                "batch_size": batch_size,
                "current_batch": 0,
                "total_batches": total_batches,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "updated_at": datetime.utcnow(),
                "errors": []
            }

            result = await db.email_bulk_campaigns.insert_one(campaign_data)
            campaign_data["_id"] = str(result.inserted_id)

            logger.info(f"✅ Email campaign created: {campaign_id} with {total_recipients} recipients")

            return {"success": True, "campaign": campaign_data}

        except Exception as e:
            logger.error(f"❌ Error creating email campaign: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    # ============================================
    # ADD RECIPIENTS
    # ============================================

    async def add_recipients_to_campaign(
        self,
        campaign_id: str,
        user_id: str,
        recipients: List[Dict[str, Any]],
        source: str = "manual"
    ) -> Dict[str, Any]:
        try:
            db = await self.get_db()

            campaign = await db.email_bulk_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            if not campaign:
                return {"success": False, "error": "Campaign not found"}
            if campaign["status"] != "pending":
                return {"success": False, "error": f"Cannot add recipients to campaign with status '{campaign['status']}'"}

            existing_emails = set(r["email"] for r in campaign.get("recipients", []))
            new_recipients = []
            duplicates = 0

            for r in recipients:
                email = self.clean_email(r.get("email", ""))
                if not email:
                    continue
                if email in existing_emails:
                    duplicates += 1
                    continue
                existing_emails.add(email)
                new_recipients.append({
                    "email": email,
                    "name": r.get("name"),
                    "status": "pending",
                    "error_message": None,
                    "sent_at": None,
                })

            if not new_recipients:
                return {"success": False, "error": "No valid new recipients to add", "duplicates": duplicates}

            updated_total = campaign["total_recipients"] + len(new_recipients)
            batch_size = campaign["batch_size"]
            updated_batches = (updated_total // batch_size) + (1 if updated_total % batch_size else 0)

            await db.email_bulk_campaigns.update_one(
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

            logger.info(f"✅ Added {len(new_recipients)} email recipients to campaign {campaign_id}")
            return {
                "success": True,
                "added_count": len(new_recipients),
                "duplicates": duplicates,
                "total_recipients": updated_total
            }

        except Exception as e:
            logger.error(f"Error adding email recipients: {e}")
            return {"success": False, "error": str(e)}

    # ============================================
    # START CAMPAIGN
    # ============================================

    async def start_campaign(self, campaign_id: str, user_id: str) -> Dict[str, Any]:
        try:
            db = await self.get_db()

            campaign = await db.email_bulk_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            if not campaign:
                return {"success": False, "error": "Campaign not found"}
            if campaign["status"] not in ["pending", "failed"]:
                return {"success": False, "error": f"Campaign status is '{campaign['status']}', cannot start"}
            if campaign["total_recipients"] == 0:
                return {"success": False, "error": "Campaign has no recipients"}

            await db.email_bulk_campaigns.update_one(
                {"_id": ObjectId(campaign["_id"])},
                {"$set": {"status": "in_progress", "started_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
            )

            logger.info(f"🚀 Starting email campaign: {campaign_id}")
            asyncio.create_task(self._send_campaign_batches(str(campaign["_id"]), user_id))

            return {"success": True, "message": "Email campaign started", "campaign_id": campaign_id}

        except Exception as e:
            logger.error(f"Error starting email campaign: {e}")
            return {"success": False, "error": str(e)}

    async def _send_campaign_batches(self, campaign_object_id: str, user_id: str):
        """Send email campaign in batches (background task)"""
        try:
            db = await self.get_db()
            campaign = await db.email_bulk_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            if not campaign:
                logger.error("Email campaign not found")
                return

            campaign_id = campaign["campaign_id"]
            subject = campaign["subject"]
            message = campaign["message"]
            batch_size = campaign["batch_size"]
            recipients = campaign["recipients"]

            logger.info(f"📤 Sending {len(recipients)} emails in batches of {batch_size}")

            for batch_num, i in enumerate(range(0, len(recipients), batch_size), start=1):
                batch_recipients = recipients[i:i + batch_size]

                logger.info(f"📦 Email Batch {batch_num}/{campaign['total_batches']}: Sending {len(batch_recipients)} emails")

                await db.email_bulk_campaigns.update_one(
                    {"_id": ObjectId(campaign_object_id)},
                    {"$set": {"current_batch": batch_num}}
                )

                for idx, recipient in enumerate(batch_recipients):
                    email_addr = recipient["email"]
                    recipient_name = recipient.get("name")

                    try:
                        # Personalize message if name available
                        personalized_message = message
                        if recipient_name:
                            personalized_message = message.replace("{name}", recipient_name)

                        result = await email_automation_service.send_email(
                            to_email=email_addr,
                            subject=subject,
                            html_content=personalized_message,
                            text_content=personalized_message.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n'),
                            user_id=user_id,
                            recipient_name=recipient_name,
                            campaign_id=campaign_id
                        )

                        if result.get("success"):
                            await db.email_bulk_campaigns.update_one(
                                {"_id": ObjectId(campaign_object_id), "recipients.email": email_addr},
                                {
                                    "$set": {
                                        "recipients.$.status": "sent",
                                        "recipients.$.sent_at": datetime.utcnow()
                                    },
                                    "$inc": {"sent_count": 1}
                                }
                            )
                            logger.info(f"  ✅ {idx+1}/{len(batch_recipients)}: Sent to {email_addr}")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            await db.email_bulk_campaigns.update_one(
                                {"_id": ObjectId(campaign_object_id), "recipients.email": email_addr},
                                {
                                    "$set": {
                                        "recipients.$.status": "failed",
                                        "recipients.$.error_message": error_msg
                                    },
                                    "$inc": {"failed_count": 1},
                                    "$push": {"errors": {"email": email_addr, "error": error_msg, "timestamp": datetime.utcnow()}}
                                }
                            )
                            logger.error(f"  ❌ {idx+1}/{len(batch_recipients)}: Failed to {email_addr}: {error_msg}")

                    except Exception as e:
                        logger.error(f"  ❌ Error sending to {email_addr}: {e}")
                        await db.email_bulk_campaigns.update_one(
                            {"_id": ObjectId(campaign_object_id), "recipients.email": email_addr},
                            {
                                "$set": {"recipients.$.status": "failed", "recipients.$.error_message": str(e)},
                                "$inc": {"failed_count": 1},
                                "$push": {"errors": {"email": email_addr, "error": str(e), "timestamp": datetime.utcnow()}}
                            }
                        )

                    # Delay between emails to avoid SMTP rate limits
                    await asyncio.sleep(1.0)

                # Delay between batches
                if batch_num < campaign["total_batches"]:
                    logger.info(f"⏳ Waiting 15 seconds before next email batch...")
                    await asyncio.sleep(15)

            # Mark campaign as completed
            final_campaign = await db.email_bulk_campaigns.find_one({"_id": ObjectId(campaign_object_id)})
            final_status = "completed"
            if final_campaign["sent_count"] == 0:
                final_status = "failed"
            elif final_campaign["failed_count"] > 0:
                final_status = "completed_with_errors"

            await db.email_bulk_campaigns.update_one(
                {"_id": ObjectId(campaign_object_id)},
                {"$set": {"status": final_status, "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
            )

            logger.info(f"✅ Email campaign completed: {campaign_id}")
            logger.info(f"   Sent: {final_campaign['sent_count']}")
            logger.info(f"   Failed: {final_campaign['failed_count']}")

        except Exception as e:
            logger.error(f"Error in email campaign batch processing: {e}")
            import traceback
            traceback.print_exc()
            try:
                db = await self.get_db()
                await db.email_bulk_campaigns.update_one(
                    {"_id": ObjectId(campaign_object_id)},
                    {
                        "$set": {"status": "failed", "updated_at": datetime.utcnow()},
                        "$push": {"errors": {"error": f"Campaign processing failed: {str(e)}", "timestamp": datetime.utcnow()}}
                    }
                )
            except:
                pass

    # ============================================
    # GET CAMPAIGNS
    # ============================================

    async def get_campaign(self, campaign_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = await self.get_db()
            campaign = await db.email_bulk_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            if campaign:
                campaign["_id"] = str(campaign["_id"])
                return campaign
            return None
        except Exception as e:
            logger.error(f"Error getting email campaign: {e}")
            return None

    async def get_campaigns(self, user_id: str, skip: int = 0, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            db = await self.get_db()
            query = {"user_id": user_id}
            if status:
                query["status"] = status
            cursor = db.email_bulk_campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
            campaigns = await cursor.to_list(length=limit)
            for campaign in campaigns:
                campaign["_id"] = str(campaign["_id"])
            return campaigns
        except Exception as e:
            logger.error(f"Error getting email campaigns: {e}")
            return []

    # ============================================
    # DELETE CAMPAIGN
    # ============================================

    async def delete_campaign(self, campaign_id: str, user_id: str) -> bool:
        try:
            db = await self.get_db()
            campaign = await db.email_bulk_campaigns.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            if not campaign:
                return False
            if campaign["status"] == "in_progress":
                logger.warning(f"Cannot delete email campaign {campaign_id} - in progress")
                return False
            result = await db.email_bulk_campaigns.delete_one({
                "campaign_id": campaign_id,
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting email campaign: {e}")
            return False


# Create singleton instance
email_campaign_service = EmailCampaignService()
