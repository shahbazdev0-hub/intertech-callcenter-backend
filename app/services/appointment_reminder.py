# backend/app/services/appointment_reminder.py - Sends reminder emails 30 min before appointments

import asyncio
import logging
import traceback
from datetime import datetime, timedelta

from app.database import get_database
from app.services.email_automation import email_automation_service

logger = logging.getLogger(__name__)


class AppointmentReminderService:
    """
    Background service that checks for upcoming appointments
    and sends reminder emails 30 minutes before the scheduled time.
    """

    def __init__(self):
        self.is_running = False
        self.check_interval = 60  # Check every 60 seconds

    async def start(self):
        """Start the reminder checking loop"""
        self.is_running = True
        print("=" * 60)
        print("[APPOINTMENT-REMINDER] STARTED")
        print(f"   Check interval: {self.check_interval}s")
        print(f"   Reminder window: 30 minutes before appointment")
        print("=" * 60)

        # Wait for DB to be ready
        await asyncio.sleep(10)

        while self.is_running:
            try:
                await self._check_and_send_reminders()
            except Exception as e:
                print(f"[APPOINTMENT-REMINDER] Error: {e}")
                traceback.print_exc()

            await asyncio.sleep(self.check_interval)

    def stop(self):
        self.is_running = False
        print("[APPOINTMENT-REMINDER] Stopped")

    async def _check_and_send_reminders(self):
        """Find appointments coming up in 30 minutes and send reminders"""
        db = await get_database()

        now = datetime.utcnow()
        reminder_window_start = now + timedelta(minutes=25)
        reminder_window_end = now + timedelta(minutes=35)

        # Find appointments in the 30-min window that haven't been reminded yet
        cursor = db.appointments.find({
            "appointment_date": {
                "$gte": reminder_window_start,
                "$lte": reminder_window_end
            },
            "status": {"$in": ["scheduled", "pending", "confirmed"]},
            "reminder_sent": {"$ne": True},
            "customer_email": {"$exists": True, "$ne": ""}
        })

        appointments = await cursor.to_list(length=50)

        if not appointments:
            return

        print(f"[APPOINTMENT-REMINDER] Found {len(appointments)} appointments needing reminders")

        for apt in appointments:
            try:
                await self._send_reminder(apt, db)
            except Exception as e:
                print(f"[APPOINTMENT-REMINDER] Failed to send reminder for {apt.get('_id')}: {e}")
                traceback.print_exc()

    async def _send_reminder(self, appointment: dict, db):
        """Send a reminder email for a single appointment"""
        customer_email = appointment.get("customer_email")
        customer_name = appointment.get("customer_name", "Valued Customer")
        service_type = appointment.get("service_type", "Appointment")
        appointment_date = appointment.get("appointment_date")
        appointment_time = appointment.get("appointment_time", "")

        if not customer_email:
            return

        if isinstance(appointment_date, datetime):
            formatted_date = appointment_date.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            formatted_date = str(appointment_date)

        subject = f"Reminder: Your {service_type} appointment is in 30 minutes"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #F59E0B; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; }}
                .details {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #F59E0B; border-radius: 4px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Appointment Reminder</h1>
                    <p>Your appointment is coming up soon!</p>
                </div>
                <div class="content">
                    <p>Dear {customer_name},</p>
                    <p>This is a friendly reminder that your appointment is <strong>in 30 minutes</strong>.</p>

                    <div class="details">
                        <h3>Appointment Details:</h3>
                        <p><strong>Service:</strong> {service_type}</p>
                        <p><strong>Date & Time:</strong> {formatted_date}</p>
                    </div>

                    <p>Please make sure to be available on time. If you need to reschedule, please contact us immediately.</p>
                </div>
                <div class="footer">
                    <p>This is an automated reminder from CallCenter SaaS.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""Appointment Reminder

Dear {customer_name},

This is a friendly reminder that your appointment is in 30 minutes.

Appointment Details:
- Service: {service_type}
- Date & Time: {formatted_date}

Please make sure to be available on time.
"""

        user_id = appointment.get("user_id")

        await email_automation_service.send_email(
            to_email=customer_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            user_id=user_id
        )

        # Mark reminder as sent
        await db.appointments.update_one(
            {"_id": appointment["_id"]},
            {
                "$set": {
                    "reminder_sent": True,
                    "reminder_sent_at": datetime.utcnow()
                }
            }
        )

        print(f"[APPOINTMENT-REMINDER] Sent reminder to {customer_email} for appointment at {formatted_date}")


# Singleton instance
appointment_reminder_service = AppointmentReminderService()
