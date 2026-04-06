"""
Assign the main Twilio number to a specific user.
Run: python assign_twilio.py
"""

import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# ── User to update ──────────────────────────────
USER_EMAIL = "ftdtrre@gmail.com"

# ── Main Twilio credentials (loaded from .env) ──
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
# ─────────────────────────────────────────────────

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")


async def assign():
    missing = [k for k, v in {
        "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
        "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
        "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER,
        "MONGODB_URL": MONGODB_URL,
        "DATABASE_NAME": DATABASE_NAME,
    }.items() if not v]
    if missing:
        print(f"[ERROR] Missing environment variables: {', '.join(missing)}")
        return

    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    user = await db.users.find_one({"email": USER_EMAIL})

    if not user:
        print(f"[ERROR] User with email '{USER_EMAIL}' not found.")
        client.close()
        return

    print(f"[FOUND] User: {user.get('full_name', user.get('username', 'N/A'))} ({USER_EMAIL})")

    result = await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "twilio_subaccount_sid": TWILIO_ACCOUNT_SID,
            "twilio_auth_token": TWILIO_AUTH_TOKEN,
            "twilio_phone_number": TWILIO_PHONE_NUMBER,
            "updated_at": datetime.utcnow()
        }}
    )

    if result.modified_count == 1:
        print("[OK] Twilio credentials assigned successfully!")
    else:
        print("[INFO] No changes made (credentials may already be set).")

    print("")
    print("===========================================")
    print("  TWILIO ASSIGNMENT COMPLETE               ")
    print("===========================================")
    print(f"  User:   {USER_EMAIL}")
    print(f"  Number: {TWILIO_PHONE_NUMBER}")
    print("===========================================")

    client.close()


if __name__ == "__main__":
    asyncio.run(assign())
