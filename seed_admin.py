"""
Seed script to create a Super Admin user.
Run: python seed_admin.py
"""

import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Super Admin Credentials ──────────────────────
ADMIN_EMAIL = "superadmin@vendira.com"
ADMIN_USERNAME = "superadmin"
ADMIN_PASSWORD = "Admin@2025"
ADMIN_FULL_NAME = "Super Admin"
ADMIN_COMPANY = "Vendira"
# ─────────────────────────────────────────────────

# MongoDB connection (same as .env)
MONGODB_URL = "mongodb+srv://maira:maira_12@cluster0.5sesguk.mongodb.net/callcenter_saas?retryWrites=true&w=majority&appName=Cluster0"
DATABASE_NAME = "callcenter_saas"


async def seed():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Check if admin already exists
    existing = await db.users.find_one({
        "$or": [
            {"email": ADMIN_EMAIL},
            {"username": ADMIN_USERNAME}
        ]
    })

    if existing:
        # Update existing user to be admin
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "is_admin": True,
                "is_active": True,
                "is_verified": True,
                "role": "admin",
                "updated_at": datetime.utcnow()
            }}
        )
        print(f"[OK] Existing user '{existing.get('username', existing.get('email'))}' updated to Super Admin!")
    else:
        # Create new admin user
        hashed_password = pwd_context.hash(ADMIN_PASSWORD)
        admin_doc = {
            "email": ADMIN_EMAIL,
            "username": ADMIN_USERNAME,
            "full_name": ADMIN_FULL_NAME,
            "company": ADMIN_COMPANY,
            "phone": None,
            "hashed_password": hashed_password,
            "is_active": True,
            "is_verified": True,
            "is_admin": True,
            "subscription_plan": "enterprise",
            "role": "admin",
            "allowed_services": ["call_center", "communication", "campaigns", "crm"],
            "notification_preferences": {
                "email_campaigns": True,
                "sms_alerts": True,
                "call_summaries": True,
                "weekly_reports": True,
                "security_alerts": True
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": None
        }
        await db.users.insert_one(admin_doc)
        print("[OK] Super Admin created successfully!")

    print("")
    print("===========================================")
    print("       SUPER ADMIN CREDENTIALS             ")
    print("===========================================")
    print(f"  Email:    {ADMIN_EMAIL}")
    print(f"  Username: {ADMIN_USERNAME}")
    print(f"  Password: {ADMIN_PASSWORD}")
    print("===========================================")
    print("  Admin Routes:                            ")
    print("  /dashboard/admin        - Admin Panel    ")
    print("  /dashboard/admin/users  - User Mgmt      ")
    print("  /dashboard/admin/settings - Settings     ")
    print("===========================================")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
