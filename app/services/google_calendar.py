# # backend/app/services/google_calendar.py - without follow up caldener events and integration 
# import os
# import json
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError
# from datetime import datetime, timedelta, timezone
# from typing import Dict, Any, Optional, List
# import logging

# logger = logging.getLogger(__name__)


# class GoogleCalendarService:
#     """Google Calendar Service for appointment management"""
    
#     def __init__(self):
#         self.service = None
#         self.calendar_id = None
#         self._is_configured = False
#         self._init_calendar()
    
#     def _init_calendar(self):
#         """Initialize Google Calendar service"""
#         try:
#             credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
#             calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
            
#             if not credentials_file or not calendar_id:
#                 logger.warning("⚠️ Google Calendar not configured - missing credentials or calendar ID")
#                 return
            
#             # Check if credentials file exists
#             if not os.path.exists(credentials_file):
#                 logger.error(f"❌ Credentials file not found: {credentials_file}")
#                 return
            
#             # Load credentials
#             credentials = service_account.Credentials.from_service_account_file(
#                 credentials_file,
#                 scopes=['https://www.googleapis.com/auth/calendar']
#             )
            
#             # Build service
#             self.service = build('calendar', 'v3', credentials=credentials)
#             self.calendar_id = calendar_id
#             self._is_configured = True
            
#             logger.info("✅ Google Calendar service initialized successfully")
#             logger.info(f"📅 Using calendar ID: {calendar_id}")
            
#         except Exception as e:
#             logger.error(f"❌ Failed to initialize Google Calendar: {e}")
#             import traceback
#             traceback.print_exc()
    
#     def is_configured(self) -> bool:
#         """Check if service is properly configured"""
#         return self._is_configured and self.service is not None
    
#     async def create_event(
#         self,
#         customer_name: str,
#         customer_email: str,
#         customer_phone: str,
#         appointment_date: datetime,
#         appointment_time: str,
#         duration_minutes: int = 60,
#         service_type: Optional[str] = None,
#         notes: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """
#         ✅ FIXED: Create a Google Calendar event with correct timezone handling
        
#         Args:
#             customer_name: Customer name
#             customer_email: Customer email
#             customer_phone: Customer phone
#             appointment_date: FULL datetime with date AND time already set correctly
#             appointment_time: Time as "HH:MM" (for reference/logging only)
#             duration_minutes: Duration
#             service_type: Type of service
#             notes: Additional notes
        
#         Returns:
#             Dictionary with event details
#         """
#         try:
#             if not self.is_configured():
#                 logger.warning("⚠️ Google Calendar not configured")
#                 return {
#                     "success": False,
#                     "error": "Google Calendar not configured"
#                 }
            
#             # ✅ CRITICAL FIX: Don't parse appointment_time and replace!
#             # The appointment_date ALREADY has the correct datetime from _parse_date_time()
#             # Just use it directly!
#             start_datetime = appointment_date
#             end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
#             logger.info(f"\n{'='*80}")
#             logger.info(f"📅 CREATING GOOGLE CALENDAR EVENT")
#             logger.info(f"   Customer: {customer_name}")
#             logger.info(f"   Start (UTC): {start_datetime}")
#             logger.info(f"   End (UTC): {end_datetime}")
#             logger.info(f"   Start (formatted): {start_datetime.strftime('%A, %B %d, %Y at %I:%M %p UTC')}")
#             logger.info(f"{'='*80}\n")
            
#             # Build event summary and description
#             summary = f"Appointment: {customer_name}"
#             if service_type:
#                 summary += f" - {service_type}"
            
#             description = f"Customer: {customer_name}\n"
#             description += f"Email: {customer_email}\n"
#             description += f"Phone: {customer_phone}\n"
#             if notes:
#                 description += f"\nNotes: {notes}"
            
#             # ✅ FIXED: Create event WITHOUT attendees (service accounts can't invite attendees)
#             event = {
#                 'summary': summary,
#                 'description': description,
#                 'start': {
#                     'dateTime': start_datetime.isoformat(),
#                     'timeZone': 'UTC',
#                 },
#                 'end': {
#                     'dateTime': end_datetime.isoformat(),
#                     'timeZone': 'UTC',
#                 },
#                 # ❌ REMOVED: attendees field that caused 403 error
#                 # 'attendees': [{'email': customer_email}],
#                 'reminders': {
#                     'useDefault': False,
#                     'overrides': [
#                         {'method': 'email', 'minutes': 24 * 60},  # 1 day before
#                         {'method': 'popup', 'minutes': 60},  # 1 hour before
#                     ],
#                 },
#             }
            
#             # ✅ FIXED: Insert event WITHOUT sendUpdates parameter
#             created_event = self.service.events().insert(
#                 calendarId=self.calendar_id,
#                 body=event
#                 # ❌ REMOVED: sendUpdates='all' - this would try to email attendees
#             ).execute()
            
#             logger.info(f"✅ Created Google Calendar event: {created_event['id']}")
#             logger.info(f"🔗 Event link: {created_event.get('htmlLink')}")
            
#             return {
#                 "success": True,
#                 "event_id": created_event['id'],
#                 "html_link": created_event.get('htmlLink'),
#                 "message": "Event created successfully"
#             }
            
#         except HttpError as e:
#             logger.error(f"❌ Google Calendar API error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": f"Calendar API error: {str(e)}"
#             }
#         except Exception as e:
#             logger.error(f"❌ Error creating calendar event: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def update_event(
#         self,
#         event_id: str,
#         customer_name: Optional[str] = None,
#         appointment_date: Optional[datetime] = None,
#         appointment_time: Optional[str] = None,
#         duration_minutes: int = 60
#     ) -> Dict[str, Any]:
#         """Update a Google Calendar event"""
#         try:
#             if not self.is_configured():
#                 return {
#                     "success": False,
#                     "error": "Google Calendar not configured"
#                 }
            
#             # Get existing event
#             event = self.service.events().get(
#                 calendarId=self.calendar_id,
#                 eventId=event_id
#             ).execute()
            
#             # Update time if provided
#             if appointment_date and appointment_time:
#                 hour, minute = map(int, appointment_time.split(':'))
#                 start_datetime = appointment_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
#                 end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                
#                 event['start'] = {
#                     'dateTime': start_datetime.isoformat(),
#                     'timeZone': 'UTC',
#                 }
#                 event['end'] = {
#                     'dateTime': end_datetime.isoformat(),
#                     'timeZone': 'UTC',
#                 }
            
#             # ✅ FIXED: Update without sendUpdates parameter
#             updated_event = self.service.events().update(
#                 calendarId=self.calendar_id,
#                 eventId=event_id,
#                 body=event
#                 # ❌ REMOVED: sendUpdates='all'
#             ).execute()
            
#             logger.info(f"✅ Updated Google Calendar event: {event_id}")
            
#             return {
#                 "success": True,
#                 "event_id": updated_event['id'],
#                 "message": "Event updated successfully"
#             }
            
#         except HttpError as e:
#             logger.error(f"❌ Error updating event: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def delete_event(self, event_id: str) -> Dict[str, Any]:
#         """Delete a Google Calendar event"""
#         try:
#             if not self.is_configured():
#                 return {
#                     "success": False,
#                     "error": "Google Calendar not configured"
#                 }
            
#             self.service.events().delete(
#                 calendarId=self.calendar_id,
#                 eventId=event_id
#             ).execute()
            
#             logger.info(f"✅ Deleted Google Calendar event: {event_id}")
            
#             return {
#                 "success": True,
#                 "message": "Event deleted successfully"
#             }
            
#         except HttpError as e:
#             logger.error(f"❌ Error deleting event: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def get_event(self, event_id: str) -> Dict[str, Any]:
#         """Get a Google Calendar event"""
#         try:
#             if not self.is_configured():
#                 return {
#                     "success": False,
#                     "error": "Google Calendar not configured"
#                 }
            
#             event = self.service.events().get(
#                 calendarId=self.calendar_id,
#                 eventId=event_id
#             ).execute()
            
#             return {
#                 "success": True,
#                 "event": event
#             }
            
#         except HttpError as e:
#             logger.error(f"❌ Error getting event: {e}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def check_availability(
#         self,
#         date: datetime,
#         duration_minutes: int = 60,
#         working_hours: Optional[Dict[str, str]] = None
#     ) -> Dict[str, Any]:
#         """Check available time slots for a given date"""
#         try:
#             if not self.is_configured():
#                 logger.warning("⚠️ Google Calendar not configured")
#                 return {
#                     "success": False,
#                     "error": "Google Calendar not configured"
#                 }
            
#             if not working_hours:
#                 working_hours = {"start": "09:00", "end": "17:00"}
            
#             # ✅ FIX: Ensure date is timezone-aware
#             if date.tzinfo is None:
#                 date = date.replace(tzinfo=timezone.utc)
            
#             start_time = datetime.combine(date.date(), datetime.strptime(working_hours["start"], "%H:%M").time())
#             end_time = datetime.combine(date.date(), datetime.strptime(working_hours["end"], "%H:%M").time())
            
#             # ✅ FIX: Make start_time and end_time timezone-aware
#             if start_time.tzinfo is None:
#                 start_time = start_time.replace(tzinfo=timezone.utc)
#             if end_time.tzinfo is None:
#                 end_time = end_time.replace(tzinfo=timezone.utc)
            
#             events_result = self.service.events().list(
#                 calendarId=self.calendar_id,
#                 timeMin=start_time.isoformat(),
#                 timeMax=end_time.isoformat(),
#                 singleEvents=True,
#                 orderBy='startTime'
#             ).execute()
            
#             events = events_result.get('items', [])
            
#             available_slots = []
#             current_time = start_time
            
#             while current_time + timedelta(minutes=duration_minutes) <= end_time:
#                 slot_end = current_time + timedelta(minutes=duration_minutes)
                
#                 is_available = True
#                 for event in events:
#                     event_start_str = event['start'].get('dateTime', event['start'].get('date'))
#                     event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                    
#                     # Parse event times
#                     event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
#                     event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                    
#                     # ✅ FIX: Ensure event times are timezone-aware
#                     if event_start.tzinfo is None:
#                         event_start = event_start.replace(tzinfo=timezone.utc)
#                     if event_end.tzinfo is None:
#                         event_end = event_end.replace(tzinfo=timezone.utc)
                    
#                     if (current_time < event_end and slot_end > event_start):
#                         is_available = False
#                         break
                
#                 if is_available:
#                     available_slots.append(current_time.strftime("%H:%M"))
                
#                 current_time += timedelta(minutes=30)
            
#             logger.info(f"✅ Found {len(available_slots)} available slots for {date.date()}")
            
#             return {
#                 "success": True,
#                 "date": date.date().isoformat(),
#                 "available_slots": available_slots,
#                 "total_slots": len(available_slots)
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Error checking availability: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": str(e)
#             }


# # Create singleton instance
# google_calendar_service = GoogleCalendarService()


# backend/app/services/google_calender.py with follow up google calender events and integration 


"""
Google Calendar Service - ENHANCED with event metadata and tags
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Google Calendar integration service - ENHANCED"""
    
    def __init__(self):
        self.credentials = None
        self.service = None
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        
        if credentials_file and os.path.exists(credentials_file):
            try:
                SCOPES = ['https://www.googleapis.com/auth/calendar']
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_file,
                    scopes=SCOPES
                )
                self.service = build('calendar', 'v3', credentials=self.credentials)
                logger.info("✅ Google Calendar service initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Google Calendar: {e}")
        else:
            logger.warning("⚠️ Google Calendar credentials not found")
    
    def is_configured(self) -> bool:
        """Check if service is configured"""
        return self.service is not None and self.calendar_id is not None
    
    async def create_event(
        self,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        appointment_date: datetime,
        appointment_time: str,
        duration_minutes: int = 60,
        service_type: Optional[str] = None,
        notes: Optional[str] = None,
        event_type: str = "appointment",  # ✅ NEW parameter
        action_type: Optional[str] = None,  # ✅ NEW parameter
        original_request: Optional[str] = None , # ✅ NEW parameter
        user_id: Optional[str] = None,      # ✅ ADD THIS
        agent_id: Optional[str] = None      # ✅ ADD THIS
    ) -> Dict[str, Any]:
        """
        Create Google Calendar event - ENHANCED with metadata
        
        Args:
            customer_name: Customer name
            customer_email: Customer email
            customer_phone: Customer phone
            appointment_date: Appointment date
            appointment_time: Time in HH:MM format
            duration_minutes: Duration in minutes
            service_type: Type of service
            notes: Additional notes
            event_type: Type of event (appointment, follow_up_call, reminder, callback) ✅ NEW
            action_type: Action to trigger (call, sms, email) ✅ NEW
            original_request: Original user request text ✅ NEW
        
        Returns:
            Dictionary with event details
        """
        try:
            if not self.is_configured():
                logger.warning("⚠️ Google Calendar not configured")
                return {
                    "success": False,
                    "error": "Google Calendar not configured"
                }
            
            # Parse time
            hour, minute = map(int, appointment_time.split(':'))
            start_datetime = appointment_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
            # ✅ Build event summary based on event type
            if event_type == "follow_up_call":
                summary = f"Follow-up Call: {customer_name}"
            elif event_type == "callback":
                summary = f"Callback: {customer_name}"
            elif event_type == "reminder":
                summary = f"Reminder: {customer_name}"
            else:
                summary = f"Appointment: {customer_name}"
                if service_type:
                    summary += f" - {service_type}"
            
            # Build description with all metadata
            description = f"Customer: {customer_name}\n"
            description += f"Email: {customer_email}\n"
            description += f"Phone: {customer_phone}\n"
            
            # ✅ Add event metadata to description
            description += f"\n--- Event Details ---\n"
            description += f"Event Type: {event_type}\n"
            if action_type:
                description += f"Action Type: {action_type}\n"
            if original_request:
                description += f"Original Request: {original_request}\n"
            
            if notes:
                description += f"\nNotes: {notes}"
            
            # ✅ Create event with extended properties for metadata
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'extendedProperties': {
    'private': {
        'event_type': event_type,
        'action_type': action_type or 'none',
        'customer_phone': customer_phone,
        'customer_email': customer_email,
        'customer_name': customer_name,
        'original_request': original_request or '',
        'is_automated': 'true' if event_type in ['follow_up_call', 'callback', 'reminder'] else 'false',
        'user_id': user_id or '',       # ✅ ADD THIS
        'agent_id': agent_id or ''      # ✅ ADD THIS
    }
},
                # ✅ NEW: Add color coding for different event types
                'colorId': self._get_color_id(event_type),
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                    ],
                },
            }
            
            # Create event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            logger.info(f"✅ Created Google Calendar event: {created_event['id']} (type: {event_type})")
            
            return {
                "success": True,
                "event_id": created_event['id'],
                "event_link": created_event.get('htmlLink'),
                "event_type": event_type,
                "message": "Event created successfully"
            }
            
        except HttpError as e:
            logger.error(f"❌ Google Calendar API error: {e}")
            return {
                "success": False,
                "error": f"Google Calendar API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Error creating event: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_color_id(self, event_type: str) -> str:
        """
        ✅ NEW: Get color ID based on event type
        Google Calendar color IDs:
        1=Lavender, 2=Sage, 3=Grape, 4=Flamingo, 5=Banana,
        6=Tangerine, 7=Peacock, 8=Graphite, 9=Blueberry, 10=Basil, 11=Tomato
        """
        color_map = {
            'appointment': '9',  # Blueberry
            'follow_up_call': '5',  # Banana (yellow)
            'callback': '6',  # Tangerine (orange)
            'reminder': '10',  # Basil (green)
        }
        return color_map.get(event_type, '1')  # Default lavender
    
    async def cancel_event(self, event_id: str) -> Dict[str, Any]:
        """Cancel a Google Calendar event - UNCHANGED"""
        try:
            if not self.is_configured():
                return {
                    "success": False,
                    "error": "Google Calendar not configured"
                }
            
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"✅ Cancelled Google Calendar event: {event_id}")
            
            return {
                "success": True,
                "message": "Event cancelled successfully"
            }
            
        except HttpError as e:
            logger.error(f"❌ Error cancelling event: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_event(
        self,
        event_id: str,
        appointment_date: Optional[datetime] = None,
        appointment_time: Optional[str] = None,
        duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """Update a Google Calendar event - UNCHANGED"""
        try:
            if not self.is_configured():
                return {
                    "success": False,
                    "error": "Google Calendar not configured"
                }
            
            # Get existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Update time if provided
            if appointment_date and appointment_time:
                hour, minute = map(int, appointment_time.split(':'))
                start_datetime = appointment_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                
                event['start'] = {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'UTC',
                }
                event['end'] = {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'UTC',
                }
            
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"✅ Updated Google Calendar event: {event_id}")
            
            return {
                "success": True,
                "event_id": updated_event['id'],
                "message": "Event updated successfully"
            }
            
        except HttpError as e:
            logger.error(f"❌ Error updating event: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ✅ NEW METHOD: Query events by time range
    async def get_events(
        self,
        time_min: datetime,
        time_max: datetime,
        event_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get events within time range
        
        Args:
            time_min: Start time
            time_max: End time
            event_type: Filter by event type (optional)
        
        Returns:
            List of events
        """
        try:
            if not self.is_configured():
                return {
                    "success": False,
                    "error": "Google Calendar not configured"
                }
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Filter by event type if specified
            if event_type:
                filtered_events = []
                for event in events:
                    props = event.get('extendedProperties', {}).get('private', {})
                    if props.get('event_type') == event_type:
                        filtered_events.append(event)
                events = filtered_events
            
            logger.info(f"✅ Retrieved {len(events)} events")
            
            return {
                "success": True,
                "events": events,
                "count": len(events)
            }
            
        except HttpError as e:
            logger.error(f"❌ Error retrieving events: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Create singleton instance
google_calendar_service = GoogleCalendarService()