# backend/app/services/customer.py
"""
Customer Service - Business logic for customer operations
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import csv
import io

from app.database import get_database
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for managing customers"""
    
    def __init__(self):
        self.db = None
    
    async def get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def create_customer(
        self,
        user_id: str,
        name: str,
        email: str,
        phone: str,
        company: Optional[str] = None,
        address: Optional[str] = None,
        tags: List[str] = None,
        notes: Optional[str] = None,
        role: Optional[str] = None,
        password: Optional[str] = None,
        allowed_services: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new customer. If role is set, also creates a user account
        with login credentials and restricted service access.
        """
        try:
            db = await self.get_db()

            # Check if customer with email already exists for this user
            existing = await db.customers.find_one({
                "user_id": user_id,
                "email": email.lower()
            })

            if existing:
                logger.warning(f"Customer with email {email} already exists")
                return {
                    "success": False,
                    "error": "Customer with this email already exists"
                }

            # Validate role-related fields
            if role and role not in ("sales_manager", "viewer"):
                return {"success": False, "error": "Invalid role. Must be 'sales_manager' or 'viewer'"}

            if role and not password:
                return {"success": False, "error": "Password is required when assigning a role"}

            if role and not allowed_services:
                return {"success": False, "error": "At least one service must be selected"}

            # Create customer document
            customer_doc = {
                "name": name,
                "email": email.lower(),
                "phone": phone,
                "company": company,
                "address": address,
                "tags": tags or [],
                "notes": notes,
                "total_appointments": 0,
                "total_calls": 0,
                "total_interactions": 0,
                "status": "active",
                "user_id": user_id,
                "role": role,
                "allowed_services": allowed_services or [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_contact_at": None
            }

            # Insert customer into database
            result = await db.customers.insert_one(customer_doc)
            customer_doc["_id"] = result.inserted_id

            # If role is set, create a user account for login
            if role and password:
                existing_user = await db.users.find_one({"email": email.lower()})
                if existing_user:
                    return {
                        "success": False,
                        "error": "A user account with this email already exists"
                    }

                user_doc = {
                    "email": email.lower(),
                    "username": email.lower().split("@")[0],
                    "full_name": name,
                    "hashed_password": get_password_hash(password),
                    "company": company,
                    "phone": phone,
                    "is_active": True,
                    "is_verified": True,
                    "is_admin": False,
                    "subscription_plan": "free",
                    "role": role,
                    "allowed_services": allowed_services or [],
                    "parent_user_id": user_id,
                    "notification_preferences": {
                        "email_campaigns": True,
                        "sms_alerts": False,
                        "call_summaries": True,
                        "weekly_reports": True,
                        "security_alerts": True
                    },
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "last_login": None
                }
                user_result = await db.users.insert_one(user_doc)
                # Store the linked user account ID on the customer record
                await db.customers.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"linked_user_id": str(user_result.inserted_id)}}
                )
                logger.info(f"✅ User account created for: {name} ({email}) with role: {role}, linked_user_id: {user_result.inserted_id}")

            logger.info(f"✅ Customer created: {name} ({email})")

            return {
                "success": True,
                "customer": self._format_customer(customer_doc)
            }

        except Exception as e:
            logger.error(f"❌ Error creating customer: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_customer(self, customer_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single customer by ID"""
        try:
            db = await self.get_db()

            customer = await db.customers.find_one({
                "_id": ObjectId(customer_id),
                "user_id": user_id
            })

            if not customer:
                return None

            # Auto-link: if customer has a role but no linked_user_id, try to find and link the user account
            if customer.get("role") and not customer.get("linked_user_id"):
                cust_email = customer.get("email", "").lower()
                cust_name = customer.get("name", "")

                # Try multiple strategies to find the linked user
                linked_user = None

                # 1. By email match
                if cust_email:
                    linked_user = await db.users.find_one({
                        "email": cust_email,
                        "is_admin": {"$ne": True}
                    })

                # 2. By name + parent_user_id
                if not linked_user and cust_name:
                    linked_user = await db.users.find_one({
                        "full_name": cust_name,
                        "parent_user_id": user_id,
                        "is_admin": {"$ne": True}
                    })

                # 3. By phone match
                if not linked_user and customer.get("phone"):
                    linked_user = await db.users.find_one({
                        "phone": customer["phone"],
                        "parent_user_id": user_id,
                        "is_admin": {"$ne": True}
                    })

                if linked_user and str(linked_user["_id"]) != user_id:
                    linked_id = str(linked_user["_id"])
                    await db.customers.update_one(
                        {"_id": customer["_id"]},
                        {"$set": {"linked_user_id": linked_id}}
                    )
                    customer["linked_user_id"] = linked_id
                    print(f"🔗 [AUTO-LINK] Linked customer {customer_id} to user {linked_id} ({linked_user.get('email')})")

            return self._format_customer(customer)
            
        except Exception as e:
            logger.error(f"❌ Error getting customer: {e}")
            return None
    
    async def get_customers(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        Get paginated list of customers
        
        Args:
            user_id: Owner user ID
            page: Page number
            limit: Items per page
            search: Search term
            tags: Comma-separated tags
            sort_by: Sort field
            sort_order: Sort direction (asc/desc)
            
        Returns:
            Dict with customers and pagination info
        """
        try:
            db = await self.get_db()
            
            # Build query
            query = {"user_id": user_id}
            
            # Add search filter
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"phone": {"$regex": search, "$options": "i"}},
                    {"company": {"$regex": search, "$options": "i"}}
                ]
            
            # Add tags filter
            if tags:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                if tag_list:
                    query["tags"] = {"$in": tag_list}
            
            # Get total count
            total = await db.customers.count_documents(query)
            
            # Calculate pagination
            skip = (page - 1) * limit
            total_pages = (total + limit - 1) // limit
            
            # Sort direction
            sort_dir = -1 if sort_order == "desc" else 1
            
            # Get customers
            cursor = db.customers.find(query).sort(sort_by, sort_dir).skip(skip).limit(limit)
            customers = await cursor.to_list(length=limit)
            
            return {
                "customers": [self._format_customer(c) for c in customers],
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting customers: {e}")
            return {
                "customers": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0
            }
    
    async def update_customer(
        self,
        customer_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a customer and sync changes to the linked user account"""
        try:
            db = await self.get_db()

            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}

            if not update_data:
                return {"success": False, "error": "No data to update"}

            # Get existing customer to find their email (for user account sync)
            existing_customer = await db.customers.find_one(
                {"_id": ObjectId(customer_id), "user_id": user_id}
            )
            if not existing_customer:
                return {"success": False, "error": "Customer not found"}

            # Add updated_at
            update_data["updated_at"] = datetime.utcnow()

            # Update customer record
            result = await db.customers.update_one(
                {"_id": ObjectId(customer_id), "user_id": user_id},
                {"$set": update_data}
            )

            # Sync role/permissions to the linked user account
            customer_email = existing_customer.get("email")
            linked_user_id = existing_customer.get("linked_user_id")

            user_update = {}
            if "role" in update_data:
                user_update["role"] = update_data["role"]
            if "allowed_services" in update_data:
                user_update["allowed_services"] = update_data["allowed_services"]
            if "name" in update_data:
                user_update["full_name"] = update_data["name"]
            if "phone" in update_data:
                user_update["phone"] = update_data["phone"]
            if "company" in update_data:
                user_update["company"] = update_data["company"]
            if "password" in update_data and update_data["password"]:
                user_update["hashed_password"] = get_password_hash(update_data["password"])
            # Also sync email changes to the user account
            if "email" in update_data:
                user_update["email"] = update_data["email"].lower()

            if user_update:
                user_update["updated_at"] = datetime.utcnow()
                print(f"📝 [USER-SYNC] linked_user_id={linked_user_id}, email={customer_email}")
                print(f"📝 [USER-SYNC] Update: role={user_update.get('role')}, allowed_services={user_update.get('allowed_services')}")

                sync_result = None

                # Strategy 1: Use linked_user_id (most reliable)
                if linked_user_id:
                    sync_result = await db.users.update_one(
                        {"_id": ObjectId(linked_user_id)},
                        {"$set": user_update}
                    )
                    print(f"📝 [USER-SYNC] By linked_user_id: matched={sync_result.matched_count}, modified={sync_result.modified_count}")

                # Strategy 2: Try email + parent_user_id
                if not sync_result or sync_result.matched_count == 0:
                    if customer_email:
                        sync_result = await db.users.update_one(
                            {"email": customer_email.lower(), "parent_user_id": user_id},
                            {"$set": user_update}
                        )
                        print(f"📝 [USER-SYNC] By email+parent: matched={sync_result.matched_count}, modified={sync_result.modified_count}")

                # Strategy 3: Find any non-admin user with this email
                if not sync_result or sync_result.matched_count == 0:
                    if customer_email:
                        found_user = await db.users.find_one({
                            "email": customer_email.lower(),
                            "is_admin": {"$ne": True}
                        })
                        if found_user and str(found_user["_id"]) != user_id:
                            user_update["parent_user_id"] = user_id
                            sync_result = await db.users.update_one(
                                {"_id": found_user["_id"]},
                                {"$set": user_update}
                            )
                            # Also save linked_user_id on customer for future syncs
                            await db.customers.update_one(
                                {"_id": ObjectId(customer_id)},
                                {"$set": {"linked_user_id": str(found_user["_id"])}}
                            )
                            print(f"✅ [USER-SYNC] Fallback by email: matched={sync_result.matched_count}, modified={sync_result.modified_count}")
                        else:
                            print(f"⚠️ [USER-SYNC] No linked user account found for this customer")

                if sync_result and sync_result.matched_count > 0:
                    logger.info(f"✅ User account synced for customer: {customer_id}")

            # Remove password from customer record (shouldn't be stored there)
            if "password" in update_data:
                await db.customers.update_one(
                    {"_id": ObjectId(customer_id)},
                    {"$unset": {"password": ""}}
                )

            # Get updated customer
            customer = await db.customers.find_one({"_id": ObjectId(customer_id)})

            logger.info(f"✅ Customer updated: {customer_id}")

            return {
                "success": True,
                "customer": self._format_customer(customer)
            }
            
        except Exception as e:
            logger.error(f"❌ Error updating customer: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_customer(self, customer_id: str, user_id: str) -> Dict[str, Any]:
        """Delete a customer and their linked user account"""
        try:
            db = await self.get_db()

            # Get customer first to find their email for user account cleanup
            customer = await db.customers.find_one({
                "_id": ObjectId(customer_id),
                "user_id": user_id
            })
            if not customer:
                return {"success": False, "error": "Customer not found"}

            # Delete customer record
            await db.customers.delete_one({"_id": ObjectId(customer_id)})

            # Delete linked user account (sub-user created with role)
            linked_user_id = customer.get("linked_user_id")
            customer_email = customer.get("email")
            deleted = False

            # Strategy 1: Delete by linked_user_id
            if linked_user_id:
                del_result = await db.users.delete_one({"_id": ObjectId(linked_user_id)})
                deleted = del_result.deleted_count > 0

            # Strategy 2: Delete by email + parent_user_id
            if not deleted and customer_email:
                del_result = await db.users.delete_one({
                    "email": customer_email.lower(),
                    "parent_user_id": user_id
                })
                deleted = del_result.deleted_count > 0

            # Strategy 3: Delete any non-admin user with this email
            if not deleted and customer_email:
                found_user = await db.users.find_one({
                    "email": customer_email.lower(),
                    "is_admin": {"$ne": True}
                })
                if found_user and str(found_user["_id"]) != user_id:
                    del_result = await db.users.delete_one({"_id": found_user["_id"]})
                    deleted = del_result.deleted_count > 0

            if deleted:
                logger.info(f"✅ User account deleted for customer: {customer_id}")

            logger.info(f"✅ Customer deleted: {customer_id}")

            return {"success": True}

        except Exception as e:
            logger.error(f"❌ Error deleting customer: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get customer statistics"""
        try:
            db = await self.get_db()
            
            # Total customers
            total_customers = await db.customers.count_documents({"user_id": user_id})
            
            # Active customers
            active_customers = await db.customers.count_documents({
                "user_id": user_id,
                "status": "active"
            })
            
            # New this month
            start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_this_month = await db.customers.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": start_of_month}
            })
            
            # Total appointments
            total_appointments = await db.appointments.count_documents({"user_id": user_id})
            
            # Upcoming appointments
            upcoming_appointments = await db.appointments.count_documents({
                "user_id": user_id,
                "appointment_date": {"$gte": datetime.utcnow()},
                "status": {"$in": ["scheduled", "confirmed"]}
            })
            
            # Completed appointments
            completed_appointments = await db.appointments.count_documents({
                "user_id": user_id,
                "status": "completed"
            })
            
            # Total interactions (calls + appointments + emails + sms)
            total_calls = await db.calls.count_documents({"user_id": user_id})
            total_interactions = total_calls + total_appointments
            
            # Average interactions per customer
            avg_interactions = total_interactions / total_customers if total_customers > 0 else 0
            
            return {
                "total_customers": total_customers,
                "new_this_month": new_this_month,
                "active_customers": active_customers,
                "total_appointments": total_appointments,
                "upcoming_appointments": upcoming_appointments,
                "completed_appointments": completed_appointments,
                "total_interactions": total_interactions,
                "avg_interactions": round(avg_interactions, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {
                "total_customers": 0,
                "new_this_month": 0,
                "active_customers": 0,
                "total_appointments": 0,
                "upcoming_appointments": 0,
                "completed_appointments": 0,
                "total_interactions": 0,
                "avg_interactions": 0
            }
    
    async def get_customer_appointments(self, customer_id: str, user_id: str) -> Dict[str, Any]:
        """Get appointments for a customer - matched by email"""
        try:
            db = await self.get_db()
            
            # Get customer to verify ownership
            customer = await db.customers.find_one({
                "_id": ObjectId(customer_id),
                "user_id": user_id
            })
            
            if not customer:
                return {"appointments": [], "error": "Customer not found"}
            
            # Get appointments by customer email (case-insensitive)
            customer_email = customer.get("email", "").lower()
            
            cursor = db.appointments.find({
                "user_id": user_id,
                "$or": [
                    {"customer_email": customer_email},
                    {"customer_email": {"$regex": f"^{customer_email}$", "$options": "i"}}
                ]
            }).sort("appointment_date", -1)
            
            appointments = await cursor.to_list(length=100)
            
            # Format appointments
            formatted = []
            for apt in appointments:
                formatted.append({
                    "id": str(apt["_id"]),
                    "customer_name": apt.get("customer_name", ""),
                    "customer_email": apt.get("customer_email", ""),
                    "customer_phone": apt.get("customer_phone", ""),
                    "appointment_date": apt.get("appointment_date"),
                    "appointment_time": apt.get("appointment_time", ""),
                    "service_type": apt.get("service_type", "General"),
                    "status": apt.get("status", "scheduled"),
                    "notes": apt.get("notes"),
                    "duration_minutes": apt.get("duration_minutes", 60),
                    "google_calendar_event_id": apt.get("google_calendar_event_id"),
                    "google_calendar_link": apt.get("google_calendar_link"),
                    "created_at": apt.get("created_at"),
                    "updated_at": apt.get("updated_at")
                })
            
            # Update customer's total_appointments count
            if len(formatted) > 0:
                await db.customers.update_one(
                    {"_id": ObjectId(customer_id)},
                    {"$set": {"total_appointments": len(formatted)}}
                )
            
            return {"appointments": formatted, "total": len(formatted)}
            
        except Exception as e:
            logger.error(f"❌ Error getting customer appointments: {e}")
            import traceback
            traceback.print_exc()
            return {"appointments": [], "total": 0}
    
    async def get_customer_calls(self, customer_id: str, user_id: str) -> Dict[str, Any]:
        """Get call history for a customer - matched by phone number"""
        try:
            db = await self.get_db()
            
            # Get customer
            customer = await db.customers.find_one({
                "_id": ObjectId(customer_id),
                "user_id": user_id
            })
            
            if not customer:
                return {"calls": [], "total": 0}
            
            # Get phone number and normalize it (remove non-digits for matching)
            customer_phone = customer.get("phone", "")
            phone_digits = ''.join(filter(str.isdigit, customer_phone))
            
            # Build query to match phone numbers
            # Match both the exact phone and normalized versions
            phone_queries = [
                {"phone_number": customer_phone},
            ]
            
            # Add regex match if we have enough digits
            if len(phone_digits) >= 10:
                phone_queries.append(
                    {"phone_number": {"$regex": phone_digits[-10:]}}
                )
            elif phone_digits:
                phone_queries.append(
                    {"phone_number": {"$regex": phone_digits}}
                )
            
            # Query calls
            cursor = db.calls.find({
                "user_id": user_id,
                "$or": phone_queries
            }).sort("created_at", -1)
            
            calls = await cursor.to_list(length=100)
            
            # Format calls - Convert ALL ObjectId fields to strings
            formatted = []
            for call in calls:
                # Convert _id to string
                call_id = call.get("_id")
                if call_id:
                    call_id = str(call_id)
                
                # Convert agent_id to string if it's an ObjectId
                agent_id = call.get("agent_id")
                if agent_id and hasattr(agent_id, '__str__'):
                    agent_id = str(agent_id)
                
                # Convert created_at and ended_at to ISO format strings
                created_at = call.get("created_at")
                if created_at and hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()
                
                ended_at = call.get("ended_at")
                if ended_at and hasattr(ended_at, 'isoformat'):
                    ended_at = ended_at.isoformat()
                
                formatted.append({
                    "id": call_id,
                    "phone_number": call.get("phone_number", ""),
                    "direction": call.get("direction", "outbound"),
                    "status": call.get("status", "completed"),
                    "duration": call.get("duration", 0),
                    "outcome": call.get("outcome"),
                    "recording_url": call.get("recording_url"),
                    "transcript": call.get("transcript"),
                    "ai_summary": call.get("ai_summary"),
                    "agent_id": agent_id,
                    "created_at": created_at,
                    "ended_at": ended_at
                })
            
            # Update customer's total_calls count
            if len(formatted) > 0:
                await db.customers.update_one(
                    {"_id": ObjectId(customer_id)},
                    {"$set": {"total_calls": len(formatted)}}
                )
            
            return {"calls": formatted, "total": len(formatted)}
            
        except Exception as e:
            logger.error(f"❌ Error getting customer calls: {e}")
            import traceback
            traceback.print_exc()
            return {"calls": [], "total": 0}
    
    async def get_customer_timeline(self, customer_id: str, user_id: str) -> Dict[str, Any]:
        """Get interaction timeline for a customer - includes calls, appointments, SMS, emails"""
        try:
            db = await self.get_db()
            
            # Get customer
            customer = await db.customers.find_one({
                "_id": ObjectId(customer_id),
                "user_id": user_id
            })
            
            if not customer:
                return {"timeline": [], "total": 0}
            
            timeline = []
            
            # Get phone number and normalize
            customer_phone = customer.get("phone", "")
            phone_digits = ''.join(filter(str.isdigit, customer_phone))
            customer_email = customer.get("email", "").lower()
            
            # 1. Get calls by phone number
            calls = await db.calls.find({
                "user_id": user_id,
                "$or": [
                    {"phone_number": customer_phone},
                    {"phone_number": {"$regex": phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits}}
                ]
            }).to_list(length=50)
            
            for call in calls:
                timeline.append({
                    "id": str(call["_id"]),
                    "type": "call",
                    "title": f"{call.get('direction', 'Outbound').title()} Call",
                    "description": f"Duration: {call.get('duration', 0)}s - Status: {call.get('status', 'completed')}",
                    "timestamp": call.get("created_at"),
                    "metadata": {
                        "call_id": str(call["_id"]),
                        "duration": call.get("duration", 0),
                        "status": call.get("status"),
                        "direction": call.get("direction")
                    }
                })
            
            # 2. Get appointments by email
            appointments = await db.appointments.find({
                "user_id": user_id,
                "$or": [
                    {"customer_email": customer_email},
                    {"customer_email": {"$regex": f"^{customer_email}$", "$options": "i"}}
                ]
            }).to_list(length=50)
            
            for apt in appointments:
                apt_date = apt.get("appointment_date")
                date_str = apt_date.strftime("%b %d, %Y at %I:%M %p") if apt_date else "N/A"
                timeline.append({
                    "id": str(apt["_id"]),
                    "type": "appointment",
                    "title": f"Appointment: {apt.get('service_type', 'General')}",
                    "description": f"Scheduled for {date_str} - Status: {apt.get('status', 'scheduled')}",
                    "timestamp": apt.get("created_at"),
                    "metadata": {
                        "appointment_id": str(apt["_id"]),
                        "service_type": apt.get("service_type"),
                        "status": apt.get("status"),
                        "appointment_date": apt_date
                    }
                })
            
            # 3. Get SMS by phone number
            sms_query = {
                "user_id": user_id,
                "$or": [
                    {"to_number": customer_phone},
                    {"to_number": {"$regex": phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits}},
                    {"from_number": customer_phone},
                    {"from_number": {"$regex": phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits}}
                ]
            }
            
            sms_logs = await db.sms_logs.find(sms_query).to_list(length=50)
            
            for sms in sms_logs:
                direction = sms.get("direction", "outbound")
                timeline.append({
                    "id": str(sms["_id"]),
                    "type": "sms",
                    "title": f"SMS {'Sent' if direction == 'outbound' else 'Received'}",
                    "description": sms.get("message", "")[:100] + ("..." if len(sms.get("message", "")) > 100 else ""),
                    "timestamp": sms.get("created_at"),
                    "metadata": {
                        "sms_id": str(sms["_id"]),
                        "direction": direction,
                        "status": sms.get("status"),
                        "to_number": sms.get("to_number"),
                        "from_number": sms.get("from_number")
                    }
                })
            
            # 4. Get emails by email address
            email_logs = await db.email_logs.find({
                "user_id": user_id,
                "$or": [
                    {"to_email": customer_email},
                    {"to_email": {"$regex": f"^{customer_email}$", "$options": "i"}}
                ]
            }).to_list(length=50)
            
            for email in email_logs:
                timeline.append({
                    "id": str(email["_id"]),
                    "type": "email",
                    "title": f"Email: {email.get('subject', 'No Subject')[:50]}",
                    "description": f"Status: {email.get('status', 'sent')}",
                    "timestamp": email.get("created_at"),
                    "metadata": {
                        "email_id": str(email["_id"]),
                        "subject": email.get("subject"),
                        "status": email.get("status")
                    }
                })
            
            # Sort by timestamp (most recent first)
            timeline.sort(
                key=lambda x: x["timestamp"] if x["timestamp"] else datetime.min, 
                reverse=True
            )
            
            # Update total interactions count
            total_interactions = len(timeline)
            if total_interactions > 0:
                await db.customers.update_one(
                    {"_id": ObjectId(customer_id)},
                    {"$set": {"total_interactions": total_interactions}}
                )
            
            return {"timeline": timeline[:100], "total": len(timeline)}
            
        except Exception as e:
            logger.error(f"❌ Error getting customer timeline: {e}")
            import traceback
            traceback.print_exc()
            return {"timeline": [], "total": 0}
    
    async def add_note(self, customer_id: str, user_id: str, note: str) -> Dict[str, Any]:
        """Add or update note for a customer"""
        try:
            db = await self.get_db()
            
            result = await db.customers.update_one(
                {"_id": ObjectId(customer_id), "user_id": user_id},
                {
                    "$set": {
                        "notes": note,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return {"success": False, "error": "Customer not found"}
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ Error adding note: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_tags(self, customer_id: str, user_id: str, tags: List[str]) -> Dict[str, Any]:
        """Add tags to a customer"""
        try:
            db = await self.get_db()
            
            result = await db.customers.update_one(
                {"_id": ObjectId(customer_id), "user_id": user_id},
                {
                    "$addToSet": {"tags": {"$each": tags}},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count == 0:
                return {"success": False, "error": "Customer not found"}
            
            # Get updated customer
            customer = await db.customers.find_one({"_id": ObjectId(customer_id)})
            
            return {
                "success": True,
                "tags": customer.get("tags", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Error adding tags: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_tag(self, customer_id: str, user_id: str, tag: str) -> Dict[str, Any]:
        """Remove a tag from a customer"""
        try:
            db = await self.get_db()
            
            result = await db.customers.update_one(
                {"_id": ObjectId(customer_id), "user_id": user_id},
                {
                    "$pull": {"tags": tag},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count == 0:
                return {"success": False, "error": "Customer not found or tag not found"}
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ Error removing tag: {e}")
            return {"success": False, "error": str(e)}
    
    async def export_csv(self, user_id: str, search: Optional[str] = None, tags: Optional[str] = None) -> bytes:
        """Export customers to CSV"""
        try:
            db = await self.get_db()
            
            # Build query
            query = {"user_id": user_id}
            
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"phone": {"$regex": search, "$options": "i"}}
                ]
            
            if tags:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                if tag_list:
                    query["tags"] = {"$in": tag_list}
            
            # Get customers
            cursor = db.customers.find(query).sort("created_at", -1)
            customers = await cursor.to_list(length=10000)
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "Name", "Email", "Phone", "Company", "Address",
                "Tags", "Status", "Total Appointments", "Total Calls",
                "Created At", "Last Contact"
            ])
            
            # Write data
            for customer in customers:
                writer.writerow([
                    customer.get("name", ""),
                    customer.get("email", ""),
                    customer.get("phone", ""),
                    customer.get("company", ""),
                    customer.get("address", ""),
                    ", ".join(customer.get("tags", [])),
                    customer.get("status", "active"),
                    customer.get("total_appointments", 0),
                    customer.get("total_calls", 0),
                    customer.get("created_at", ""),
                    customer.get("last_contact_at", "")
                ])
            
            return output.getvalue().encode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Error exporting CSV: {e}")
            return b""
    
    async def find_or_create_customer(
        self,
        user_id: str,
        name: str,
        email: str,
        phone: str
    ) -> Dict[str, Any]:
        """
        Find existing customer or create new one
        Used by AI agents when creating appointments
        """
        try:
            db = await self.get_db()
            
            # Try to find by email first
            customer = await db.customers.find_one({
                "user_id": user_id,
                "email": email.lower()
            })
            
            if customer:
                # Update last contact
                await db.customers.update_one(
                    {"_id": customer["_id"]},
                    {"$set": {"last_contact_at": datetime.utcnow()}}
                )
                return {
                    "success": True,
                    "customer": self._format_customer(customer),
                    "created": False
                }
            
            # Create new customer
            result = await self.create_customer(
                user_id=user_id,
                name=name,
                email=email,
                phone=phone
            )
            
            if result.get("success"):
                result["created"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in find_or_create_customer: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_customer(self, customer: dict) -> dict:
        """Format customer document for response"""
        return {
            "id": str(customer["_id"]),
            "name": customer.get("name", ""),
            "email": customer.get("email", ""),
            "phone": customer.get("phone", ""),
            "company": customer.get("company"),
            "address": customer.get("address"),
            "tags": customer.get("tags", []),
            "notes": customer.get("notes"),
            "total_appointments": customer.get("total_appointments", 0),
            "total_calls": customer.get("total_calls", 0),
            "total_interactions": customer.get("total_interactions", 0),
            "status": customer.get("status", "active"),
            "user_id": customer.get("user_id", ""),
            "role": customer.get("role"),
            "allowed_services": customer.get("allowed_services", []),
            "linked_user_id": customer.get("linked_user_id"),
            "created_at": customer.get("created_at"),
            "updated_at": customer.get("updated_at"),
            "last_contact_at": customer.get("last_contact_at")
        }


# Create singleton instance
customer_service = CustomerService()