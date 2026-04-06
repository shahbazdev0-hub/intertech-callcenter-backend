

# backend/app/services/email_automation.py - ✅ FIXED WITH SIMPLIFIED SMTP

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import asyncio
from jinja2 import Template
import aiosmtplib  # ✅ Using aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings
from app.database import get_database
from app.services.email import email_service
import logging

logger = logging.getLogger(__name__)


class EmailAutomationService:
    """Email Automation Service - Simplified SMTP (No Pooling)"""
    
    def __init__(self):
        self.db = None
        self.smtp_host = settings.EMAIL_HOST
        self.smtp_port = settings.EMAIL_PORT
        self.smtp_user = settings.EMAIL_USER
        self.smtp_password = settings.EMAIL_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME
    
    async def get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    # ============================================
    # ✅ SIMPLIFIED: ONE CONNECTION PER EMAIL
    # ============================================
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        user_id: Optional[str] = None,
        recipient_name: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        campaign_id: Optional[str] = None,
        automation_id: Optional[str] = None,
        call_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email - SIMPLIFIED VERSION (No Connection Pooling)
        ✅ Creates fresh connection for each email
        """
        try:
            logger.info(f"📧 Sending email to {to_email}")
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Add text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, "plain")
                message.attach(part1)
            
            part2 = MIMEText(html_content, "html")
            message.attach(part2)
            
            # ✅ FIXED: Use start_tls parameter instead of calling starttls()
            smtp = None
            try:
                # ✅ CRITICAL FIX: Use start_tls=True in constructor
                smtp = aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    timeout=30,
                    use_tls=False,  # Don't use direct TLS
                    start_tls=True  # ✅ THIS FIXES THE ISSUE - enables STARTTLS automatically
                )
                
                # Connect and authenticate (TLS upgrade happens automatically)
                await smtp.connect()
                logger.info("✅ Connected to SMTP server with STARTTLS")
                
                await smtp.login(self.smtp_user, self.smtp_password)
                logger.info("✅ SMTP authenticated")
                
                # Send message
                await smtp.send_message(message)
                logger.info(f"✅ Email sent successfully to {to_email}")
                
                # Close connection
                await smtp.quit()
                
            except Exception as smtp_error:
                logger.error(f"❌ SMTP error: {smtp_error}")
                if smtp:
                    try:
                        await smtp.quit()
                    except:
                        pass
                raise
            
            # Rest of your logging code remains unchanged...
            # (all the email_log_data code)
            
            # Prepare email log data
            email_log_data = {
                "to_email": to_email,
                "from_email": self.from_email,
                "subject": subject,
                "content": html_content,
                "text_content": text_content,
                "status": "sent",
                "direction": "outbound",
                "smtp_message_id": message.get("Message-ID"),
                "created_at": datetime.utcnow(),
                "sent_at": datetime.utcnow(),
                "opened_count": 0,
                "clicked_count": 0,
                "clicked_links": []
            }
            
            if user_id:
                email_log_data["user_id"] = user_id
            
            if recipient_name:
                email_log_data["recipient_name"] = recipient_name
            
            if recipient_phone:
                email_log_data["recipient_phone"] = recipient_phone
            
            if campaign_id:
                email_log_data["campaign_id"] = campaign_id
            
            if automation_id:
                email_log_data["automation_id"] = automation_id
            
            if call_id:
                email_log_data["call_id"] = call_id
            
            if appointment_id:
                email_log_data["appointment_id"] = appointment_id
            
            # Get database
            db = await self.get_db()
            
            # Store in email_logs collection
            result = await db.email_logs.insert_one(email_log_data)
            
            logger.info(f"✅ Email logged in email_logs collection")
            
            return {
                "success": True,
                "email_id": str(result.inserted_id),
                "to_email": to_email,
                "subject": subject,
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}", exc_info=True)
            
            # Log failed email
            try:
                db = await self.get_db()
                
                failed_email_data = {
                    "to_email": to_email,
                    "from_email": self.from_email,
                    "subject": subject,
                    "content": html_content,
                    "text_content": text_content,
                    "status": "failed",
                    "direction": "outbound",
                    "error_message": str(e),
                    "created_at": datetime.utcnow(),
                    "opened_count": 0,
                    "clicked_count": 0
                }
                
                if user_id:
                    failed_email_data["user_id"] = user_id
                
                if recipient_name:
                    failed_email_data["recipient_name"] = recipient_name
                
                if recipient_phone:
                    failed_email_data["recipient_phone"] = recipient_phone
                
                if call_id:
                    failed_email_data["call_id"] = call_id
                
                if appointment_id:
                    failed_email_data["appointment_id"] = appointment_id
                
                await db.email_logs.insert_one(failed_email_data)
                
            except Exception as log_error:
                logger.error(f"❌ Error logging failed email: {log_error}")
            
            raise
    
    # ============================================
    # ALL ORIGINAL METHODS BELOW - UNCHANGED
    # ============================================
    
    async def send_appointment_confirmation(
        self,
        to_email: str,
        customer_name: str,
        customer_phone: str,
        service_type: str,
        appointment_date: str,
        user_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send appointment confirmation email"""
        
        subject = f"Appointment Confirmation - {service_type}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 20px; }}
                .appointment-details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #4F46E5; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Appointment Confirmed</h1>
                </div>
                <div class="content">
                    <p>Dear {customer_name},</p>
                    <p>Your appointment has been successfully scheduled!</p>
                    
                    <div class="appointment-details">
                        <h3>Appointment Details:</h3>
                        <p><strong>Service:</strong> {service_type}</p>
                        <p><strong>Date & Time:</strong> {appointment_date}</p>
                        <p><strong>Contact:</strong> {customer_phone}</p>
                    </div>
                    
                    <p>We look forward to seeing you!</p>
                    <p>If you need to reschedule or cancel, please contact us as soon as possible.</p>
                </div>
                <div class="footer">
                    <p>This is an automated message. Please do not reply to this email.</p>
                    <p>&copy; 2024 CallCenter SaaS. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Appointment Confirmed
        
        Dear {customer_name},
        
        Your appointment has been successfully scheduled!
        
        Appointment Details:
        Service: {service_type}
        Date & Time: {appointment_date}
        Contact: {customer_phone}
        
        We look forward to seeing you!
        
        If you need to reschedule or cancel, please contact us as soon as possible.
        """
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            user_id=user_id,
            recipient_name=customer_name,
            recipient_phone=customer_phone,
            appointment_id=appointment_id,
            call_id=call_id
        )
    
    async def log_appointment_email(
        self,
        to_email: str,
        customer_name: str,
        customer_phone: str,
        service_type: str,
        appointment_date: str,
        user_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        call_id: Optional[str] = None
    ) -> None:
        """Just log the appointment email to email_logs without sending"""
        try:
            logger.info(f"📝 Logging appointment email to email_logs collection")
            
            subject = f"✅ Appointment Confirmed!"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #4caf50; margin-bottom: 20px;">✅ Appointment Confirmed!</h2>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Hello {customer_name},
                    </p>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Your appointment has been successfully scheduled. Here are the details:
                    </p>
                    
                    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>📅 Date:</strong> {appointment_date.split(' at ')[0] if ' at ' in appointment_date else appointment_date}</p>
                        <p style="margin: 5px 0;"><strong>🕐 Time:</strong> {appointment_date.split(' at ')[1] if ' at ' in appointment_date else '10:00 AM'}</p>
                        <p style="margin: 5px 0;"><strong>📋 Service:</strong> {service_type}</p>
                    </div>
                    
                    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #856404;">
                            <strong>🔔 Reminder:</strong> Please arrive 5 minutes early for your appointment.
                        </p>
                    </div>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6; margin-top: 25px;">
                        We look forward to seeing you!
                    </p>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 15px;">
                        If you need to reschedule or cancel, please contact us as soon as possible.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="font-size: 14px; color: #333; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>Your Service Team</strong>
                    </p>
                    
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        This is an automated confirmation. Please do not reply to this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Appointment Confirmed!
            
            Hello {customer_name},
            
            Your appointment has been successfully scheduled:
            
            📅 Date: {appointment_date}
            📋 Service: {service_type}
            
            Please arrive 5 minutes early for your appointment.
            
            We look forward to seeing you!
            
            If you need to reschedule or cancel, please contact us as soon as possible.
            
            Best regards,
            Your Service Team
            """
            
            email_log_data = {
                "to_email": to_email,
                "from_email": self.from_email,
                "subject": subject,
                "content": html_content,
                "text_content": text_content,
                "status": "sent",
                "direction": "outbound",
                "created_at": datetime.utcnow(),
                "sent_at": datetime.utcnow(),
                "opened_count": 0,
                "clicked_count": 0,
                "clicked_links": [],
                "recipient_name": customer_name,
                "recipient_phone": customer_phone
            }
            
            if user_id:
                email_log_data["user_id"] = user_id
            
            if appointment_id:
                email_log_data["appointment_id"] = appointment_id
                
            if call_id:
                email_log_data["call_id"] = call_id
            
            db = await self.get_db()
            await db.email_logs.insert_one(email_log_data)
            
            logger.info(f"✅ Email logged in email_logs collection for {to_email}")
            
        except Exception as e:
            logger.error(f"❌ Error logging appointment email: {e}", exc_info=True)
    
    async def create_campaign(
        self,
        user_id: str,
        name: str,
        subject: str,
        content: str,
        recipients: List[str],
        scheduled_at: Optional[datetime] = None,
        send_immediately: bool = False,
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create email campaign"""
        db = await self.get_db()
        
        campaign_data = {
            "user_id": user_id,
            "name": name,
            "subject": subject,
            "content": content,
            "template_id": template_id,
            "recipients": recipients,
            "recipient_count": len(recipients),
            "status": "scheduled" if scheduled_at else ("sending" if send_immediately else "draft"),
            "scheduled_at": scheduled_at,
            "send_immediately": send_immediately,
            "sent_count": 0,
            "delivered_count": 0,
            "opened_count": 0,
            "clicked_count": 0,
            "failed_count": 0,
            "send_rate_limit": settings.CAMPAIGN_SEND_RATE_LIMIT,
            "batch_size": settings.EMAIL_BATCH_SIZE,
            "metadata": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.email_campaigns.insert_one(campaign_data)
        campaign_data["_id"] = str(result.inserted_id)
        
        if send_immediately:
            from app.tasks.email_tasks import send_campaign_task
            send_campaign_task.delay(str(result.inserted_id))
        
        return campaign_data
    
    async def get_campaigns(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get email campaigns for user"""
        db = await self.get_db()
        
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        total = await db.email_campaigns.count_documents(query)
        
        cursor = db.email_campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
        campaigns = await cursor.to_list(length=limit)
        
        for campaign in campaigns:
            campaign["_id"] = str(campaign["_id"])
        
        return {
            "campaigns": campaigns,
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
    
    async def get_campaign(self, campaign_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get campaign by ID"""
        db = await self.get_db()
        
        campaign = await db.email_campaigns.find_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        if campaign:
            campaign["_id"] = str(campaign["_id"])
        
        return campaign
    
    async def update_campaign(
        self,
        campaign_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update campaign"""
        db = await self.get_db()
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.email_campaigns.update_one(
            {"_id": ObjectId(campaign_id), "user_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await self.get_campaign(campaign_id, user_id)
        
        return None
    
    async def delete_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Delete campaign"""
        db = await self.get_db()
        
        result = await db.email_campaigns.delete_one({
            "_id": ObjectId(campaign_id),
            "user_id": user_id
        })
        
        return result.deleted_count > 0
    
    async def send_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Send campaign emails - called by Celery task"""
        db = await self.get_db()
        
        campaign = await db.email_campaigns.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            return {"success": False, "error": "Campaign not found"}
        
        # Update status
        await db.email_campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {"status": "sending", "started_at": datetime.utcnow()}}
        )
        
        results = {"total": len(campaign["recipients"]), "sent": 0, "failed": 0}
        
        # Send emails in batches
        batch_size = campaign.get("batch_size", settings.EMAIL_BATCH_SIZE)
        recipients = campaign["recipients"]
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            for recipient in batch:
                try:
                    await email_service.send_email(
                        to_email=recipient,
                        subject=campaign["subject"],
                        html_content=campaign["content"]
                    )
                    results["sent"] += 1
                    
                    await db.email_campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$inc": {"sent_count": 1}}
                    )
                    
                except Exception as e:
                    results["failed"] += 1
                    await db.email_campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$inc": {"failed_count": 1}}
                    )
            
            await asyncio.sleep(1)
        
        # Update final status
        await db.email_campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {"status": "sent", "completed_at": datetime.utcnow()}}
        )
        
        return results
    
    async def create_template(
        self,
        user_id: str,
        name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        variables: List[str] = []
    ) -> Dict[str, Any]:
        """Create email template"""
        db = await self.get_db()
        
        template_data = {
            "user_id": user_id,
            "name": name,
            "subject": subject,
            "html_content": html_content,
            "text_content": text_content,
            "variables": variables,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.email_templates.insert_one(template_data)
        template_data["_id"] = str(result.inserted_id)
        
        return template_data
    
    async def get_templates(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get email templates"""
        db = await self.get_db()
        
        total = await db.email_templates.count_documents({"user_id": user_id})
        
        cursor = db.email_templates.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
        templates = await cursor.to_list(length=limit)
        
        for template in templates:
            template["_id"] = str(template["_id"])
        
        return {
            "templates": templates,
            "total": total
        }
    
    async def render_template(
        self,
        template_id: str,
        variables: Dict[str, Any]
    ) -> str:
        """Render email template with variables"""
        db = await self.get_db()
        
        template = await db.email_templates.find_one({"_id": ObjectId(template_id)})
        if not template:
            raise ValueError("Template not found")
        
        jinja_template = Template(template["html_content"])
        return jinja_template.render(**variables)
    
    # ============================================
    # INBOUND EMAIL AI RESPONSE METHODS
    # ============================================
    
    async def handle_inbound_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle incoming email and store in email_logs"""
        try:
            db = await self.get_db()
            
            email_log_data = {
                "to_email": to_email,
                "from_email": from_email,
                "subject": subject,
                "content": body,
                "text_content": body,
                "html_content": html_body,
                "status": "received",
                "direction": "inbound",
                "created_at": datetime.utcnow(),
                "opened_count": 0,
                "clicked_count": 0,
                "clicked_links": []
            }
            
            if user_id:
                email_log_data["user_id"] = user_id
            
            result = await db.email_logs.insert_one(email_log_data)
            email_log_data["_id"] = str(result.inserted_id)
            
            logger.info(f"✅ Inbound email stored from {from_email}")
            
            return {
                "success": True,
                "email_id": str(result.inserted_id),
                "data": email_log_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error storing inbound email: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_auto_reply(
        self,
        to_email: str,
        subject: str,
        ai_response: str,
        user_id: Optional[str] = None,
        original_subject: Optional[str] = None,
        ai_source: str = "openai"
    ) -> Dict[str, Any]:
        """Send AI-generated auto-reply email"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        {ai_response.replace(chr(10), '<br>')}
                    </div>
                    <div class="footer">
                        <p>This is an automated response. Our team will follow up if needed.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            result = await self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=ai_response,
                user_id=user_id
            )
            
            if result.get("success"):
                db = await self.get_db()
                
                await db.email_logs.update_one(
                    {"_id": ObjectId(result.get("email_id", ""))},
                    {
                        "$set": {
                            "is_auto_reply": True,
                            "ai_source": ai_source,
                            "original_subject": original_subject
                        }
                    }
                )
                
                logger.info(f"✅ Auto-reply sent to {to_email} (source: {ai_source})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending auto-reply: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_email_conversation_history(
        self,
        email_address: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get email conversation history with a specific email address"""
        try:
            db = await self.get_db()
            
            cursor = db.email_logs.find({
                "user_id": user_id,
                "$or": [
                    {"to_email": email_address},
                    {"from_email": email_address}
                ]
            }).sort("created_at", -1).limit(limit)
            
            history = await cursor.to_list(length=limit)
            history.reverse()
            
            for email in history:
                email["_id"] = str(email["_id"])
            
            return history
            
        except Exception as e:
            logger.error(f"❌ Error getting email history: {e}", exc_info=True)
            return []
    
    async def get_email_stats(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get email statistics for a user"""
        try:
            db = await self.get_db()
            
            # Total counts
            total_sent = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "outbound"
            })
            
            total_received = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "inbound"
            })
            
            total_auto_replies = await db.email_logs.count_documents({
                "user_id": user_id,
                "is_auto_reply": True
            })
            
            # Today's counts
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            today_sent = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "outbound",
                "created_at": {"$gte": today_start}
            })
            
            today_received = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "inbound",
                "created_at": {"$gte": today_start}
            })
            
            # This week
            week_start = today_start - timedelta(days=today_start.weekday())
            
            week_sent = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "outbound",
                "created_at": {"$gte": week_start}
            })
            
            week_received = await db.email_logs.count_documents({
                "user_id": user_id,
                "direction": "inbound",
                "created_at": {"$gte": week_start}
            })
            
            return {
                "total_sent": total_sent,
                "total_received": total_received,
                "total_auto_replies": total_auto_replies,
                "today_sent": today_sent,
                "today_received": today_received,
                "this_week_sent": week_sent,
                "this_week_received": week_received
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting email stats: {e}", exc_info=True)
            return {
                "total_sent": 0,
                "total_received": 0,
                "total_auto_replies": 0,
                "today_sent": 0,
                "today_received": 0,
                "this_week_sent": 0,
                "this_week_received": 0
            }


# Create singleton instance
email_automation_service = EmailAutomationService()