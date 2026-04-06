

# backend/app/api/v1/contact.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from app.services.email import email_service
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str
    phone: Optional[str] = None
    company: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v.strip()) > 100:
            raise ValueError('Name must be less than 100 characters')
        return v.strip()

    @validator('subject')
    def validate_subject(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Subject must be at least 3 characters long')
        if len(v.strip()) > 200:
            raise ValueError('Subject must be less than 200 characters')
        return v.strip()

    @validator('message')
    def validate_message(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Message must be at least 10 characters long')
        if len(v.strip()) > 2000:
            raise ValueError('Message must be less than 2000 characters')
        return v.strip()

@router.post("/send")
async def send_contact_message(contact_data: ContactMessage):
    """
    Send a contact message via email
    """
    try:
        logger.info(f"Contact form submission from: {contact_data.email}")
        
        # Create email content for admin notification
        admin_html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">New Contact Form Submission</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <div style="background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
                    <h2 style="color: #667eea; margin-top: 0; border-bottom: 2px solid #667eea; padding-bottom: 10px;">Contact Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; color: #555;">Name:</td>
                            <td style="padding: 10px 0;">{contact_data.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; color: #555;">Email:</td>
                            <td style="padding: 10px 0;"><a href="mailto:{contact_data.email}" style="color: #667eea; text-decoration: none;">{contact_data.email}</a></td>
                        </tr>
                        {f'<tr><td style="padding: 10px 0; font-weight: bold; color: #555;">Phone:</td><td style="padding: 10px 0;">{contact_data.phone}</td></tr>' if contact_data.phone else ''}
                        {f'<tr><td style="padding: 10px 0; font-weight: bold; color: #555;">Company:</td><td style="padding: 10px 0;">{contact_data.company}</td></tr>' if contact_data.company else ''}
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; color: #555;">Subject:</td>
                            <td style="padding: 10px 0;">{contact_data.subject}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #667eea; margin-top: 0; border-bottom: 2px solid #667eea; padding-bottom: 10px;">Message</h2>
                    <p style="white-space: pre-wrap; line-height: 1.8; color: #555;">{contact_data.message}</p>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #e8f4f8; border-left: 4px solid #667eea; border-radius: 5px;">
                    <p style="margin: 0; font-size: 14px; color: #666;">
                        <strong>📧 Quick Reply:</strong> Click the email address above to respond directly to {contact_data.name}
                    </p>
                </div>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 20px; text-align: center;">
                <p style="color: #666; font-size: 12px; margin: 0;">
                    This message was sent from the CallCenter SaaS contact form.<br>
                    &copy; 2025 CallCenter SaaS. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """

        admin_text_content = f"""
        NEW CONTACT FORM SUBMISSION
        ===========================

        CONTACT DETAILS:
        ----------------
        Name: {contact_data.name}
        Email: {contact_data.email}
        {f'Phone: {contact_data.phone}' if contact_data.phone else ''}
        {f'Company: {contact_data.company}' if contact_data.company else ''}
        Subject: {contact_data.subject}

        MESSAGE:
        --------
        {contact_data.message}

        ---
        This message was sent from the CallCenter SaaS contact form.
        Reply to: {contact_data.email}
        """

        # Send email to admin
        admin_email_sent = await email_service.send_email(
            to_email=settings.EMAIL_FROM,
            subject=f"📬 Contact Form: {contact_data.subject}",
            html_content=admin_html_content,
            text_content=admin_text_content
        )

        if not admin_email_sent:
            logger.error(f"Failed to send admin notification for contact from {contact_data.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send message. Please try again later."
            )

        # Send confirmation email to user
        user_html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Thank You for Contacting Us!</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9f9f9;">
                <div style="background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <p style="font-size: 16px; color: #555;">Hi <strong>{contact_data.name}</strong>,</p>
                    
                    <p style="font-size: 16px; color: #555;">
                        Thank you for reaching out to <strong>CallCenter SaaS</strong>! We've successfully received your message and our team will review it shortly.
                    </p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #667eea;">
                        <h3 style="color: #667eea; margin-top: 0;">Your Message Summary</h3>
                        <p style="margin: 10px 0;"><strong>Subject:</strong> {contact_data.subject}</p>
                        <p style="margin: 10px 0;"><strong>Message:</strong></p>
                        <p style="white-space: pre-wrap; color: #555; background-color: white; padding: 15px; border-radius: 5px;">{contact_data.message}</p>
                    </div>
                    
                    <div style="background-color: #e8f4f8; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <h3 style="color: #667eea; margin-top: 0;">📞 Need Immediate Assistance?</h3>
                        <p style="margin: 10px 0;">
                            <strong>Email:</strong> <a href="mailto:{settings.EMAIL_FROM}" style="color: #667eea; text-decoration: none;">{settings.EMAIL_FROM}</a>
                        </p>
                        <p style="margin: 10px 0;">
                            <strong>Phone:</strong> +1 (555) 123-4567
                        </p>
                        <p style="margin: 10px 0; font-size: 14px; color: #666;">
                            Our support team is available Monday - Friday, 9 AM - 6 PM EST
                        </p>
                    </div>
                    
                    <p style="font-size: 16px; color: #555;">
                        We typically respond within 24 hours. If your inquiry is urgent, please don't hesitate to call us directly.
                    </p>
                    
                    <p style="font-size: 16px; color: #555; margin-top: 30px;">
                        Best regards,<br>
                        <strong>The CallCenter SaaS Team</strong>
                    </p>
                </div>
            </div>
            
            <div style="background-color: #f0f0f0; padding: 20px; text-align: center;">
                <p style="color: #666; font-size: 12px; margin: 0;">
                    This is an automated confirmation email.<br>
                    &copy; 2025 CallCenter SaaS. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """

        user_text_content = f"""
        THANK YOU FOR CONTACTING US!
        ============================

        Hi {contact_data.name},

        Thank you for reaching out to CallCenter SaaS! We've successfully received your message and our team will review it shortly.

        YOUR MESSAGE SUMMARY:
        --------------------
        Subject: {contact_data.subject}
        Message: {contact_data.message}

        NEED IMMEDIATE ASSISTANCE?
        --------------------------
        Email: {settings.EMAIL_FROM}
        Phone: +1 (555) 123-4567
        Hours: Monday - Friday, 9 AM - 6 PM EST

        We typically respond within 24 hours. If your inquiry is urgent, please don't hesitate to call us directly.

        Best regards,
        The CallCenter SaaS Team

        ---
        This is an automated confirmation email.
        © 2025 CallCenter SaaS. All rights reserved.
        """

        # Send confirmation to user
        user_email_sent = await email_service.send_email(
            to_email=contact_data.email,
            subject=f"✅ We received your message - {contact_data.subject}",
            html_content=user_html_content,
            text_content=user_text_content
        )

        if user_email_sent:
            logger.info(f"Confirmation email sent to user: {contact_data.email}")
        else:
            logger.warning(f"Failed to send confirmation email to user: {contact_data.email}")

        logger.info(f"Contact message processed successfully from {contact_data.email}")
        
        return {
            "message": "Message sent successfully! We'll get back to you soon.",
            "status": "success",
            "confirmation_sent": user_email_sent
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact form error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Please try again later."
        )