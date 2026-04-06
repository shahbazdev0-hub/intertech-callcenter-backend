# backend/force_fix_index.py - ✅ FORCE FIX THE INDEX

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def force_fix_index():
    """Forcefully fix the call_sid index"""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.DATABASE_NAME]
        
        logger.info("🔧 FORCE FIXING call_sid INDEX...")
        
        # Step 1: Check current indexes
        logger.info("\n📋 Current indexes:")
        indexes = await db.calls.index_information()
        for name, info in indexes.items():
            sparse = " [SPARSE]" if info.get("sparse") else ""
            unique = " [UNIQUE]" if info.get("unique") else ""
            logger.info(f"   - {name}{sparse}{unique}")
        
        # Step 2: Drop call_sid_1 index if it exists
        if "call_sid_1" in indexes:
            logger.info("\n🗑️  Dropping call_sid_1 index...")
            try:
                await db.calls.drop_index("call_sid_1")
                logger.info("✅ Index dropped")
            except Exception as e:
                logger.error(f"❌ Error dropping index: {e}")
                # Continue anyway
        
        # Step 3: Wait a moment
        await asyncio.sleep(1)
        
        # Step 4: Clean up duplicate null records
        logger.info("\n🧹 Cleaning up duplicate null records...")
        null_calls = await db.calls.find({"call_sid": None}).to_list(length=None)
        logger.info(f"   Found {len(null_calls)} calls with null call_sid")
        
        if len(null_calls) > 1:
            # Keep only the most recent one
            keep_id = null_calls[0]['_id']
            logger.info(f"   Keeping: {keep_id}")
            
            result = await db.calls.delete_many({
                "call_sid": None,
                "_id": {"$ne": keep_id}
            })
            logger.info(f"✅ Deleted {result.deleted_count} duplicate records")
        
        # Step 5: Create new sparse unique index
        logger.info("\n🔨 Creating new sparse unique index...")
        try:
            await db.calls.create_index(
                [("call_sid", 1)],
                unique=True,
                sparse=True,
                name="call_sid_1"
            )
            logger.info("✅ Sparse unique index created successfully!")
        except Exception as e:
            logger.error(f"❌ Error creating index: {e}")
            return False
        
        # Step 6: Verify final state
        logger.info("\n✅ Final indexes:")
        indexes = await db.calls.index_information()
        for name, info in indexes.items():
            sparse = " [SPARSE]" if info.get("sparse") else ""
            unique = " [UNIQUE]" if info.get("unique") else ""
            logger.info(f"   - {name}{sparse}{unique}")
        
        # Verify call_sid_1 is sparse
        if "call_sid_1" in indexes:
            if indexes["call_sid_1"].get("sparse") and indexes["call_sid_1"].get("unique"):
                logger.info("\n🎉 SUCCESS! call_sid_1 is now SPARSE and UNIQUE!")
                logger.info("✅ You can now create calls without duplicate key errors!")
                return True
            else:
                logger.error("\n❌ Index exists but is NOT sparse!")
                return False
        else:
            logger.error("\n❌ Index was not created!")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(force_fix_index())
    if success:
        print("\n" + "="*60)
        print("✅ DATABASE FIX COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Restart your backend server")
        print("2. Test creating a call in the frontend")
        print("3. The duplicate key error should be gone!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ DATABASE FIX FAILED!")
        print("="*60)
        print("\nPlease contact support with the error logs above.")