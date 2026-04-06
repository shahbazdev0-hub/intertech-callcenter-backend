# backend/app/services/email.py - COMPLETE UPDATED VERSION

import os
import logging
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending emails via SMTP"""
    
    def __init__(self):
        self.host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("EMAIL_PORT", 587))
        self.username = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("EMAIL_FROM")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "CallCenter SaaS")
        
        if not all([self.username, self.password, self.from_email]):
            logger.warning("⚠️ Email configuration incomplete")
    
    def is_configured(self) -> bool:
        """Check if email is properly configured"""
        return all([self.username, self.password, self.from_email])
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self.is_configured():
                logger.error("❌ Email not configured")
                return False
            
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
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=True
            )
            
            logger.info(f"✅ Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False
    
    async def send_email_with_credentials(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        smtp_config: dict,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email using provided SMTP credentials (for per-tenant email).

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            smtp_config: Dict with smtp_host, smtp_port, smtp_username, smtp_password, from_email, from_name
            text_content: Plain text email body (optional)
        """
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{smtp_config.get('from_name', 'CallCenter SaaS')} <{smtp_config['from_email']}>"
            message["To"] = to_email

            if text_content:
                message.attach(MIMEText(text_content, "plain"))
            message.attach(MIMEText(html_content, "html"))

            await aiosmtplib.send(
                message,
                hostname=smtp_config["smtp_host"],
                port=smtp_config.get("smtp_port", 587),
                username=smtp_config["smtp_username"],
                password=smtp_config["smtp_password"],
                start_tls=True
            )

            logger.info(f"✅ Email sent successfully to {to_email} (custom SMTP)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email} (custom SMTP): {e}")
            return False

    async def send_verification_email(
        self,
        to_email: str,
        verification_token: str,
        frontend_url: str
    ) -> bool:
        """Send email verification"""
        try:
            verification_link = f"{frontend_url}/verify-email?token={verification_token}"
            
            subject = "Verify Your Email Address"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #f2070d; margin-bottom: 20px;">Welcome to CallCenter SaaS!</h2>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Thank you for signing up. Please verify your email address to activate your account.
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verification_link}" 
                           style="background-color: #f2070d; color: white; padding: 14px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            Verify Email Address
                        </a>
                    </div>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 20px;">
                        Or copy and paste this link into your browser:
                    </p>
                    <p style="font-size: 12px; color: #999; word-break: break-all;">
                        {verification_link}
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #999;">
                        If you didn't create an account, you can safely ignore this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Welcome to CallCenter SaaS!
            
            Please verify your email address by clicking the link below:
            {verification_link}
            
            If you didn't create an account, you can safely ignore this email.
            """
            
            return await self.send_email(to_email, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"❌ Failed to send verification email: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        frontend_url: str
    ) -> bool:
        """Send password reset email"""
        try:
            reset_link = f"{frontend_url}/reset-password?token={reset_token}"
            
            subject = "Reset Your Password"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #f2070d; margin-bottom: 20px;">Password Reset Request</h2>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        We received a request to reset your password. Click the button below to create a new password.
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" 
                           style="background-color: #f2070d; color: white; padding: 14px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            Reset Password
                        </a>
                    </div>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 20px;">
                        Or copy and paste this link into your browser:
                    </p>
                    <p style="font-size: 12px; color: #999; word-break: break-all;">
                        {reset_link}
                    </p>
                    
                    <p style="font-size: 14px; color: #ff6b6b; margin-top: 20px; padding: 10px; background-color: #fff5f5; border-radius: 5px;">
                        ⚠️ This link will expire in 1 hour.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #999;">
                        If you didn't request a password reset, you can safely ignore this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Password Reset Request
            
            We received a request to reset your password. Click the link below to create a new password:
            {reset_link}
            
            This link will expire in 1 hour.
            
            If you didn't request a password reset, you can safely ignore this email.
            """
            
            return await self.send_email(to_email, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"❌ Failed to send password reset email: {e}")
            return False
    
    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        frontend_url: str
    ) -> bool:
        """Send welcome email after successful verification"""
        try:
            subject = "🎉 Welcome to CallCenter SaaS!"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #f2070d; margin-bottom: 20px;">Welcome to CallCenter SaaS! 🎉</h2>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Hi {user_name},
                    </p>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Your account is now active! You can start using our AI-powered call center platform.
                    </p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #333; margin-top: 0;">Getting Started:</h3>
                        <ul style="color: #666; line-height: 1.8;">
                            <li>📞 Set up your first voice agent</li>
                            <li>🎙️ Configure voice settings</li>
                            <li>🔄 Create automation workflows</li>
                            <li>📊 Monitor your analytics</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{frontend_url}/dashboard" 
                           style="background-color: #f2070d; color: white; padding: 14px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            Go to Dashboard
                        </a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #999;">
                        Need help? Contact our support team anytime.
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Welcome to CallCenter SaaS!
            
            Hi {user_name},
            
            Your account is now active! You can start using our AI-powered call center platform.
            
            Getting Started:
            - Set up your first voice agent
            - Configure voice settings
            - Create automation workflows
            - Monitor your analytics
            
            Visit your dashboard: {frontend_url}/dashboard
            
            Need help? Contact our support team anytime.
            """
            
            return await self.send_email(to_email, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"❌ Failed to send welcome email: {e}")
            return False
    
    async def send_appointment_confirmation(
        self,
        to_email: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        service_type: str = "General Consultation",
        additional_notes: Optional[str] = None
    ) -> bool:
        """
        🆕 Send appointment confirmation email
        
        Args:
            to_email: Customer email
            customer_name: Customer name
            appointment_date: Formatted date string (e.g., "January 15, 2025")
            appointment_time: Time string (e.g., "14:00" or "2:00 PM")
            service_type: Type of service
            additional_notes: Optional additional information
        
        Returns:
            True if sent successfully
        """
        try:
            logger.info(f"📧 Sending appointment confirmation to {to_email}")
            
            subject = f"✅ Appointment Confirmed - {appointment_date}"
            
            # Format time nicely
            try:
                from datetime import datetime
                time_obj = datetime.strptime(appointment_time, "%H:%M")
                formatted_time = time_obj.strftime("%I:%M %p")
            except:
                formatted_time = appointment_time
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #f2070d; margin-bottom: 20px;">✅ Appointment Confirmed!</h2>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Hello {customer_name},
                    </p>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Your appointment has been successfully scheduled. Here are the details:
                    </p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 12px 0; border-bottom: 1px solid #e9ecef;">
                                    <strong style="color: #495057;">📅 Date:</strong>
                                </td>
                                <td style="padding: 12px 0; border-bottom: 1px solid #e9ecef; text-align: right; color: #212529;">
                                    {appointment_date}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 0; border-bottom: 1px solid #e9ecef;">
                                    <strong style="color: #495057;">🕐 Time:</strong>
                                </td>
                                <td style="padding: 12px 0; border-bottom: 1px solid #e9ecef; text-align: right; color: #212529;">
                                    {formatted_time}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 0;">
                                    <strong style="color: #495057;">📋 Service:</strong>
                                </td>
                                <td style="padding: 12px 0; text-align: right; color: #212529;">
                                    {service_type}
                                </td>
                            </tr>
                        </table>
                    </div>
                    
                    {f'<div style="background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #0066cc;"><p style="margin: 0; color: #004085; font-size: 14px;"><strong>📝 Note:</strong> {additional_notes}</p></div>' if additional_notes else ''}
                    
                    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                        <p style="margin: 0; color: #856404; font-size: 14px;">
                            <strong>⏰ Reminder:</strong> Please arrive 5 minutes early for your appointment.
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
            🕐 Time: {formatted_time}
            📋 Service: {service_type}
            
            {f'Note: {additional_notes}' if additional_notes else ''}
            
            Please arrive 5 minutes early for your appointment.
            
            We look forward to seeing you!
            
            If you need to reschedule or cancel, please contact us as soon as possible.
            
            Best regards,
            Your Service Team
            """
            
            success = await self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"✅ Appointment confirmation sent to {to_email}")
            else:
                logger.error(f"❌ Failed to send appointment confirmation to {to_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error sending appointment confirmation: {e}")
            import traceback
            traceback.print_exc()
            return False


# Create singleton instance
email_service = EmailService()