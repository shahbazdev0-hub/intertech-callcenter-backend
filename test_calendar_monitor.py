# backend/cleanup_calendar.py
"""
ONE-TIME CLEANUP SCRIPT
Deletes test/old calendar events from Google Calendar
Keeps only "Kevin" appointments
Does NOT touch database records
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
CREDENTIALS_FILE = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials/callcenter-saas-appointments-d9ebf066283e.json")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# Names to KEEP (won't be deleted)
NAMES_TO_KEEP = ["kevin"]  # Add more names if needed

# Names/patterns to DELETE
PATTERNS_TO_DELETE = [
    "customer",
    "follow-up",
    "follow up", 
    "i mean",
    "said hes been",
    "saying in",
    "okay, i want",
    "want to an",
    "cammy",
    "mra",
    "myra",
    "john cena",
    "ilahi",
    "william",
    "test",
    "callback"
]


def get_calendar_service():
    """Initialize Google Calendar service"""
    try:
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=credentials)
        print("✅ Google Calendar service initialized")
        return service
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return None


def should_delete_event(event_summary: str) -> bool:
    """Check if event should be deleted"""
    summary_lower = event_summary.lower()
    
    # Check if it's a name to KEEP
    for keep_name in NAMES_TO_KEEP:
        if keep_name.lower() in summary_lower:
            return False  # Don't delete
    
    # Check if it matches patterns to DELETE
    for pattern in PATTERNS_TO_DELETE:
        if pattern.lower() in summary_lower:
            return True  # Delete
    
    return False  # Default: don't delete


def cleanup_calendar():
    """Main cleanup function"""
    service = get_calendar_service()
    if not service:
        return
    
    print(f"\n{'='*60}")
    print("🗑️  CALENDAR CLEANUP SCRIPT")
    print(f"{'='*60}")
    print(f"Calendar ID: {CALENDAR_ID}")
    print(f"Names to KEEP: {NAMES_TO_KEEP}")
    print(f"{'='*60}\n")
    
    # Get events from past 60 days to future 60 days
    now = datetime.utcnow()
    time_min = (now - timedelta(days=60)).isoformat() + 'Z'
    time_max = (now + timedelta(days=60)).isoformat() + 'Z'
    
    try:
        # Get all events
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=500,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        print(f"📋 Found {len(events)} total events\n")
        
        # Categorize events
        to_delete = []
        to_keep = []
        
        for event in events:
            event_id = event.get('id')
            summary = event.get('summary', 'No Title')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
            
            if should_delete_event(summary):
                to_delete.append({
                    'id': event_id,
                    'summary': summary,
                    'start': start
                })
            else:
                to_keep.append({
                    'id': event_id,
                    'summary': summary,
                    'start': start
                })
        
        # Show what will be kept
        print(f"✅ Events to KEEP ({len(to_keep)}):")
        print("-" * 40)
        for event in to_keep:
            print(f"   📌 {event['summary'][:40]}")
        
        # Show what will be deleted
        print(f"\n🗑️  Events to DELETE ({len(to_delete)}):")
        print("-" * 40)
        for event in to_delete:
            print(f"   ❌ {event['summary'][:40]} - {event['start'][:10]}")
        
        if not to_delete:
            print("\n✅ No events to delete!")
            return
        
        # Confirm deletion
        print(f"\n{'='*60}")
        confirm = input(f"⚠️  Delete {len(to_delete)} events? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("❌ Cancelled. No events deleted.")
            return
        
        # Delete events
        print("\n🗑️  Deleting events...")
        deleted_count = 0
        failed_count = 0
        
        for event in to_delete:
            try:
                service.events().delete(
                    calendarId=CALENDAR_ID,
                    eventId=event['id']
                ).execute()
                print(f"   ✅ Deleted: {event['summary'][:40]}")
                deleted_count += 1
            except HttpError as e:
                print(f"   ❌ Failed: {event['summary'][:40]} - {e}")
                failed_count += 1
        
        print(f"\n{'='*60}")
        print(f"✅ CLEANUP COMPLETE")
        print(f"   Deleted: {deleted_count}")
        print(f"   Failed: {failed_count}")
        print(f"   Kept: {len(to_keep)}")
        print(f"{'='*60}\n")
        
    except HttpError as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    cleanup_calendar()