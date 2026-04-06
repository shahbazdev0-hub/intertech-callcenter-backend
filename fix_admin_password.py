# Create this file: backend/fix_admin_password.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import connect_to_mongo, get_collection
from app.core.security import get_password_hash
from datetime import datetime

async def fix_admin_password():
    try:
        await connect_to_mongo()
        print("Connected to MongoDB...")
        
        users_collection = await get_collection("users")
        
        # Generate the correct hash for "admin123"
        correct_hash = get_password_hash("admin123")
        print(f"Generated hash for 'admin123': {correct_hash}")
        
        # Update the admin user with correct password hash
        result = await users_collection.update_one(
            {"email": "admin@callcenter.com"},
            {
                "$set": {
                    "hashed_password": correct_hash,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print("✅ Successfully updated admin password!")
            print("📧 Email: admin@callcenter.com")
            print("🔑 Password: admin123")
        else:
            print("❌ No user found or no changes made")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(fix_admin_password())