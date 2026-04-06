# backend/test_twilio.py - TWILIO DIAGNOSTIC SCRIPT
# Run this with: python test_twilio.py

import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*80)
print("🔍 TWILIO CREDENTIALS DIAGNOSTIC")
print("="*80 + "\n")

# Get credentials
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
phone_number = os.getenv("TWILIO_PHONE_NUMBER")

print("📋 STEP 1: Check Environment Variables")
print("-"*60)
print(f"   TWILIO_ACCOUNT_SID: {account_sid}")
print(f"   TWILIO_ACCOUNT_SID length: {len(account_sid) if account_sid else 0}")
print(f"   TWILIO_ACCOUNT_SID starts with 'AC': {account_sid.startswith('AC') if account_sid else False}")
print()
print(f"   TWILIO_AUTH_TOKEN: {'*' * 20 + auth_token[-4:] if auth_token else 'NOT SET'}")
print(f"   TWILIO_AUTH_TOKEN length: {len(auth_token) if auth_token else 0}")
print()
print(f"   TWILIO_PHONE_NUMBER: {phone_number}")
print()

# Check for common issues
print("📋 STEP 2: Check for Common Issues")
print("-"*60)

issues_found = False

if not account_sid:
    print("   ❌ TWILIO_ACCOUNT_SID is not set!")
    issues_found = True
elif not account_sid.startswith("AC"):
    print(f"   ❌ TWILIO_ACCOUNT_SID should start with 'AC', got: {account_sid[:5]}")
    issues_found = True
elif len(account_sid) != 34:
    print(f"   ❌ TWILIO_ACCOUNT_SID should be 34 characters, got: {len(account_sid)}")
    issues_found = True
else:
    print("   ✅ TWILIO_ACCOUNT_SID format looks correct")

if not auth_token:
    print("   ❌ TWILIO_AUTH_TOKEN is not set!")
    issues_found = True
elif len(auth_token) != 32:
    print(f"   ❌ TWILIO_AUTH_TOKEN should be 32 characters, got: {len(auth_token)}")
    issues_found = True
else:
    print("   ✅ TWILIO_AUTH_TOKEN length looks correct (32 chars)")

if not phone_number:
    print("   ❌ TWILIO_PHONE_NUMBER is not set!")
    issues_found = True
elif not phone_number.startswith("+"):
    print(f"   ⚠️ TWILIO_PHONE_NUMBER should start with '+', got: {phone_number}")
else:
    print("   ✅ TWILIO_PHONE_NUMBER format looks correct")

# Check for hidden characters
if account_sid:
    clean_sid = account_sid.strip()
    if clean_sid != account_sid:
        print(f"   ⚠️ TWILIO_ACCOUNT_SID has hidden whitespace characters!")
        issues_found = True

if auth_token:
    clean_token = auth_token.strip()
    if clean_token != auth_token:
        print(f"   ⚠️ TWILIO_AUTH_TOKEN has hidden whitespace characters!")
        issues_found = True

print()

# Test Twilio connection
print("📋 STEP 3: Test Twilio API Connection")
print("-"*60)

try:
    from twilio.rest import Client
    
    # Clean credentials
    account_sid_clean = account_sid.strip() if account_sid else ""
    auth_token_clean = auth_token.strip() if auth_token else ""
    
    print(f"   Creating Twilio client...")
    client = Client(account_sid_clean, auth_token_clean)
    
    print(f"   Fetching account info...")
    account = client.api.accounts(account_sid_clean).fetch()
    
    print(f"   ✅ CONNECTION SUCCESSFUL!")
    print(f"   Account SID: {account.sid}")
    print(f"   Account Status: {account.status}")
    print(f"   Account Name: {account.friendly_name}")
    print()
    
except Exception as e:
    print(f"   ❌ CONNECTION FAILED!")
    print(f"   Error: {e}")
    print()
    
    if "20003" in str(e):
        print("   🔴 ERROR 20003: Authentication Failed")
        print("   This means your Account SID or Auth Token is WRONG.")
        print()
        print("   👉 SOLUTION:")
        print("   1. Go to https://console.twilio.com/")
        print("   2. Copy your Account SID (starts with 'AC')")
        print("   3. Copy your Auth Token (click 'Show' to reveal)")
        print("   4. Update your .env file with the correct values")
        print("   5. Make sure there are NO SPACES around the = sign")
        print()
    
    issues_found = True

# Test SMS capability
if not issues_found:
    print("📋 STEP 4: Test SMS Capability")
    print("-"*60)
    
    try:
        # Check if the phone number can send SMS
        phone_number_clean = phone_number.strip() if phone_number else ""
        
        print(f"   Checking phone number capabilities...")
        
        # List incoming phone numbers
        incoming_numbers = client.incoming_phone_numbers.list(phone_number=phone_number_clean)
        
        if incoming_numbers:
            number_info = incoming_numbers[0]
            print(f"   ✅ Phone number found: {number_info.phone_number}")
            print(f"   SMS Capable: {number_info.capabilities.get('sms', False)}")
            print(f"   Voice Capable: {number_info.capabilities.get('voice', False)}")
            print(f"   MMS Capable: {number_info.capabilities.get('mms', False)}")
            
            if not number_info.capabilities.get('sms', False):
                print()
                print("   ⚠️ WARNING: This phone number is NOT SMS capable!")
                print("   You need to use an SMS-enabled Twilio number.")
        else:
            print(f"   ⚠️ Phone number {phone_number_clean} not found in your account")
            print("   Available numbers:")
            all_numbers = client.incoming_phone_numbers.list(limit=5)
            for num in all_numbers:
                print(f"      - {num.phone_number} (SMS: {num.capabilities.get('sms', False)})")
        
        print()
        
    except Exception as e:
        print(f"   ❌ Error checking SMS capability: {e}")
        print()

# Final summary
print("="*80)
print("📊 DIAGNOSTIC SUMMARY")
print("="*80)

if issues_found:
    print("❌ Issues were found. Please fix them before using SMS.")
    print()
    print("🔧 MOST COMMON FIX:")
    print("   1. Go to Twilio Console: https://console.twilio.com/")
    print("   2. Copy your Auth Token (it may have been regenerated)")
    print("   3. Update TWILIO_AUTH_TOKEN in your .env file")
    print("   4. Restart your backend server")
else:
    print("✅ All checks passed! Your Twilio configuration looks good.")
    print()
    print("If SMS is still not working, the issue might be:")
    print("   - Your Twilio account balance is $0")
    print("   - The destination phone number is blocked")
    print("   - Trial account restrictions (can only send to verified numbers)")

print()
print("="*80 + "\n")