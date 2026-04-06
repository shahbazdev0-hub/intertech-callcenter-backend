# create_admin.py - Run this script to create admin user
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from passlib.context import CryptContext
from bson import ObjectId

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin_user():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["callcenter_saas"]
    users_collection = db["users"]
    
    # Check if admin already exists
    existing_admin = await users_collection.find_one({"email": "admin@callcenterpro.com"})
    if existing_admin:
        print("❌ Admin user already exists!")
        return
    
    # Hash password
    hashed_password = pwd_context.hash("admin123")
    
    # Create admin user
    admin_user = {
        "_id": str(ObjectId()),
        "email": "admin@callcenterpro.com",
        "full_name": "System Administrator",
        "company": "CallCenter Pro",
        "phone": "+1-555-ADMIN",
        "hashed_password": hashed_password,
        "is_active": True,
        "is_verified": True,
        "is_admin": True,
        "subscription_plan": "enterprise",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert admin user
    result = await users_collection.insert_one(admin_user)
    
    if result.inserted_id:
        print("✅ Admin user created successfully!")
        print("📧 Email: admin@callcenterpro.com")
        print("🔑 Password: admin123")
        print("⚠️  Please change password after first login")
    else:
        print("❌ Failed to create admin user")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_admin_user())