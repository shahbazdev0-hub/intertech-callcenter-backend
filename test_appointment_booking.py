# backend/test_appointment_booking.py - CORRECTED VERSION

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_appointment_system():
    """Test the complete appointment booking system"""
    
    print("=" * 70)
    print("🧪 TESTING APPOINTMENT BOOKING SYSTEM")
    print("=" * 70)
    
    # Import services
    from app.services.google_calendar import google_calendar_service
    from app.services.appointment import appointment_service
    from app.database import connect_to_mongo
    
    # Connect to database
    print("\n1️⃣ Connecting to MongoDB...")
    await connect_to_mongo()
    print("✅ Database connected")
    
    # Test 1: Check Google Calendar configuration
    print("\n2️⃣ Checking Google Calendar configuration...")
    if google_calendar_service.is_configured():
        print("✅ Google Calendar is configured")
    else:
        print("❌ Google Calendar is NOT configured")
        return
    
    # Test 2: Check availability
    print("\n3️⃣ Checking calendar availability...")
    
    # ✅ FIXED: Use timezone-aware datetime
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    
    availability = await appointment_service.check_availability(
        date=tomorrow,
        duration_minutes=60
    )
    
    if availability.get("success"):
        print(f"✅ Availability check successful")
        print(f"   Date: {availability.get('date')}")
        print(f"   Available slots: {len(availability.get('available_slots', []))}")
        print(f"   First 5 slots: {availability.get('available_slots', [])[:5]}")
    else:
        print(f"❌ Availability check failed: {availability.get('error')}")
        return
    
    # Test 3: Create test appointment
    print("\n4️⃣ Creating test appointment...")
    
    # Use first available slot
    slots = availability.get('available_slots', [])
    if not slots:
        print("❌ No available slots found")
        return
    
    test_time = slots[0]  # Use first available slot
    
    result = await appointment_service.create_appointment(
        customer_name="Test Customer",
        customer_email="test@example.com",
        customer_phone="555-123-4567",
        appointment_date=tomorrow,
        appointment_time=test_time,
        service_type="Test Consultation",
        notes="This is an automated test appointment"
    )
    
    if result.get("success"):
        print(f"✅ Appointment created successfully")
        print(f"   Appointment ID: {result.get('appointment_id')}")
        print(f"   Google Event ID: {result.get('google_event_id')}")
        
        if result.get('google_event_id'):
            print(f"   🎉 SUCCESS! Event created in Google Calendar!")
            print(f"   📅 Check your calendar for: {tomorrow.date()} at {test_time}")
        else:
            print(f"   ⚠️ Appointment saved but no Google Calendar event")
    else:
        print(f"❌ Appointment creation failed: {result.get('error')}")
        return
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\n📋 NEXT STEPS:")
    print("1. Check your Google Calendar at: https://calendar.google.com/")
    print(f"2. Look for appointment on: {tomorrow.date()} at {test_time}")
    print("3. Verify appointment details match test data")
    print("=" * 70)

# Run the test
if __name__ == "__main__":
    asyncio.run(test_appointment_system())