


# backend/app/database.py - with ai follow up steps and calender event integration 
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None

    @property
    def users(self):
        return self.database.users

    @property
    def calls(self):
        return self.database.calls

    @property
    def voice_agents(self):
        return self.database.voice_agents

    @property
    def conversations(self):
        return self.database.conversations

    @property
    def call_logs(self):
        return self.database.call_logs

    @property
    def sms_messages(self):
        return self.database.sms_messages

    @property
    def email_campaigns(self):
        return self.database.email_campaigns

    @property
    def automations(self):
        return self.database.automations

    @property
    def workflows(self):
        return self.database.workflows

    @property
    def appointments(self):
        return self.database.appointments

    @property
    def flows(self):
        return self.database.flows
    
    @property
    def demo_bookings(self):
        return self.database.demo_bookings

    @property
    def processed_calendar_events(self):
        return self.database.processed_calendar_events


database = Database()


async def connect_to_mongo():
    """Connect to MongoDB"""
    try:
        database.client = AsyncIOMotorClient(settings.MONGODB_URL)
        database.database = database.client[settings.DATABASE_NAME]
        
        # Test connection
        await database.client.admin.command('ping')
        logger.info("✅ Connected to MongoDB successfully")
        
        # Create indexes
        await create_indexes()
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection"""
    try:
        if database.client:
            database.client.close()
            logger.info("✅ MongoDB connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing MongoDB connection: {e}")


async def get_database():
    """Get database instance"""
    if database.database is None:
        await connect_to_mongo()
    return database.database


async def get_collection(collection_name: str):
    """Get specific collection"""
    if database.database is None:
        await connect_to_mongo()
    return database.database[collection_name]


async def create_indexes():
    """Create database indexes for better performance"""
    try:
        logger.info("📊 Creating database indexes...")
        
        # Users collection indexes
        try:
            await database.users.create_index("email", unique=True)
        except:
            pass  # Index might already exist
        await database.users.create_index("verification_token")
        await database.users.create_index("reset_token")
        await database.users.create_index("created_at")
        logger.info("✅ Users indexes created")
        
        # Demo bookings collection indexes
        await database.demo_bookings.create_index("email")
        await database.demo_bookings.create_index("status")
        await database.demo_bookings.create_index("created_at")
        logger.info("✅ Demo bookings indexes created")
        
        # ✅ Calls collection indexes - FIXED SPARSE INDEX
        await database.calls.create_index([("user_id", 1), ("created_at", -1)])
        
        # ✅ CRITICAL FIX: Check if index exists before creating
        existing_indexes = await database.calls.index_information()
        
        if "call_sid_1" in existing_indexes:
            # Check if it's already sparse
            if not existing_indexes["call_sid_1"].get("sparse"):
                # Drop and recreate as sparse
                try:
                    await database.calls.drop_index("call_sid_1")
                    await database.calls.create_index("call_sid", unique=True, sparse=True)
                    logger.info("✅ Recreated call_sid index as sparse")
                except Exception as e:
                    logger.warning(f"⚠️  Could not recreate call_sid index: {e}")
        else:
            # Create new sparse index
            try:
                await database.calls.create_index("call_sid", unique=True, sparse=True)
                logger.info("✅ Created call_sid sparse index")
            except Exception as e:
                logger.warning(f"⚠️  Could not create call_sid index: {e}")
        
        # Create other call indexes
        try:
            await database.calls.create_index("twilio_call_sid", sparse=True)
        except:
            pass
        await database.calls.create_index("status")
        await database.calls.create_index("direction")
        await database.calls.create_index([("user_id", 1), ("status", 1)])
        logger.info("✅ Calls indexes created")
        
        # Voice agents collection indexes
        await database.voice_agents.create_index([("user_id", 1), ("created_at", -1)])
        await database.voice_agents.create_index("is_active")
        await database.voice_agents.create_index([("user_id", 1), ("is_active", 1)])
        logger.info("✅ Voice agents indexes created")
        
        # Conversations collection indexes
        await database.conversations.create_index([("user_id", 1), ("created_at", -1)])
        await database.conversations.create_index("call_id")
        await database.conversations.create_index("agent_id")
        await database.conversations.create_index([("call_id", 1), ("created_at", -1)])
        logger.info("✅ Conversations indexes created")
        
        # Call logs collection indexes
        await database.call_logs.create_index([("user_id", 1), ("created_at", -1)])
        await database.calls.create_index("call_id")
        try:
            await database.call_logs.create_index("call_sid", sparse=True)
        except:
            pass
        logger.info("✅ Call logs indexes created")
        
        # SMS messages collection indexes
        await database.sms_messages.create_index("user_id")
        await database.sms_messages.create_index("status")
        await database.sms_messages.create_index("direction")
        await database.sms_messages.create_index("created_at")
        await database.sms_messages.create_index([("user_id", 1), ("created_at", -1)])
        await database.sms_messages.create_index([("user_id", 1), ("status", 1)])
        await database.sms_messages.create_index("to_number")
        await database.sms_messages.create_index("from_number")
        logger.info("✅ SMS messages indexes created")
        
        # Email campaigns collection indexes
        await database.email_campaigns.create_index("user_id")
        await database.email_campaigns.create_index("status")
        await database.email_campaigns.create_index("created_at")
        await database.email_campaigns.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("✅ Email campaigns indexes created")
        
        # Automations collection indexes
        await database.automations.create_index("user_id")
        await database.automations.create_index("trigger_type")
        await database.automations.create_index("is_active")
        await database.automations.create_index([("user_id", 1), ("is_active", 1)])
        logger.info("✅ Automations indexes created")
        
        # Workflows collection indexes
        await database.workflows.create_index("user_id")
        await database.workflows.create_index("status")
        await database.workflows.create_index("created_at")
        await database.workflows.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("✅ Workflows indexes created")
        
        # Appointments collection indexes
        await database.appointments.create_index("user_id")
        await database.appointments.create_index("status")
        await database.appointments.create_index("appointment_date")
        await database.appointments.create_index("customer_email")
        await database.appointments.create_index([("user_id", 1), ("appointment_date", 1)])
        logger.info("✅ Appointments indexes created")
        
        # ✅ NEW: Processed calendar events collection indexes
        try:
            await database.processed_calendar_events.create_index("event_id", unique=True)
            await database.processed_calendar_events.create_index("processed_at")
            await database.processed_calendar_events.create_index([("processed_at", -1)])
            logger.info("✅ Processed calendar events indexes created")
        except Exception as e:
            logger.warning(f"⚠️ Could not create processed_calendar_events indexes: {e}")
            # Collection might not exist yet, which is okay
        
        # Flows collection indexes
        await database.flows.create_index("user_id")
        await database.flows.create_index("is_active")
        await database.flows.create_index([("user_id", 1), ("is_active", 1)])
        logger.info("✅ Flows indexes created")

        # SMS logs indexes
        await database.sms_logs.create_index("user_id")
        await database.sms_logs.create_index([("user_id", 1), ("direction", 1)])
        await database.sms_logs.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("✅ SMS logs indexes created")

        # Email logs indexes
        await database.email_logs.create_index("user_id")
        await database.email_logs.create_index([("user_id", 1), ("direction", 1)])
        await database.email_logs.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("✅ Email logs indexes created")

        logger.info("✅ (voice_agents indexes already created above)")

        # Twilio phone number lookup (for incoming call routing)
        await database.users.create_index("twilio_phone_number", sparse=True)
        logger.info("✅ Twilio phone number index created")

        logger.info("✅ All database indexes created successfully")
        
    except Exception as e:
        logger.error(f"❌ Error creating indexes: {e}")
        # Don't raise exception, just log - app can still work