# # backend/app/services/workflow_engine.py - COMPLETE FILE WITH GMT+5 FIX(appointment booked and user recieve email and sms )

# import logging
# import re
# from typing import Dict, Any, Optional, List
# from datetime import datetime, timedelta
# from bson import ObjectId

# from app.database import get_database
# from app.services.google_calendar import google_calendar_service
# from app.services.email import email_service

# logger = logging.getLogger(__name__)

# # ✅ USER TIMEZONE CONFIGURATION
# USER_TIMEZONE_OFFSET = 5 


# class WorkflowEngine:
#     """Campaign Builder Workflow Engine"""
    
#     def __init__(self):
#         self.workflow_cache = {}
#         self.booking_locks = set()
    
#     async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
#         """Get workflow"""
#         try:
#             db = await get_database()
            
#             if isinstance(workflow_id, str):
#                 if not ObjectId.is_valid(workflow_id):
#                     return None
#                 workflow_id = ObjectId(workflow_id)
            
#             workflow = await db.flows.find_one({"_id": workflow_id})
            
#             if workflow:
#                 logger.info(f"✅ Loaded workflow: {workflow.get('name')}")
            
#             return workflow
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             return None
    
#     async def find_start_node(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#         """Find start node"""
#         try:
#             nodes = workflow.get("nodes", [])
#             if not nodes:
#                 return None
            
#             for node in nodes:
#                 if node.get("type") == "begin":
#                     return node
            
#             for node in nodes:
#                 if node.get("type") in ["welcome", "message"]:
#                     return node
            
#             return nodes[0]
            
#         except:
#             return None
    
#     async def process_conversation_turn(
#         self,
#         workflow_id: str,
#         user_input: str,
#         call_id: str,
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """Main processing"""
#         try:
#             logger.info(f"\n{'='*80}")
#             logger.info(f"🎯 Processing: '{user_input}'")
#             logger.info(f"{'='*80}\n")
            
#             workflow = await self.get_workflow(workflow_id)
#             if not workflow:
#                 return await self._fallback_to_openai(user_input, call_id, agent_config)
            
#             conversation_state = await self._get_conversation_state(call_id, workflow)
            
#             result = await self._process_with_campaign(
#                 user_input, 
#                 conversation_state, 
#                 workflow,
#                 agent_config
#             )
            
#             if result.get("found_in_campaign"):
#                 return result
#             else:
#                 return await self._fallback_to_openai(user_input, call_id, agent_config)
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
#             return await self._fallback_to_openai(user_input, call_id, agent_config)
    
#     async def _process_with_campaign(
#         self,
#         user_input: str,
#         conversation_state: Dict[str, Any],
#         workflow: Dict[str, Any],
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """Process with campaign"""
#         try:
#             current_node = conversation_state["current_node"]
#             logger.info(f"🔍 Current node: {current_node.get('id')}")
            
#             previous_field = conversation_state.get("previous_field")
            
#             if previous_field:
#                 db = await get_database()
#                 conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
#                 existing_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
                
#                 if not existing_data.get(previous_field):
#                     logger.info(f"📥 Collecting {previous_field} from: '{user_input}'")
#                     await self._collect_field_data(
#                         user_input, 
#                         previous_field, 
#                         conversation_state["call_id"],
#                         conversation_state
#                     )
#                 else:
#                     logger.info(f"⏭️ Skipping {previous_field} - already collected: {existing_data.get(previous_field)}")
            
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
#             collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
#             conversation_state["collected_data"] = collected_data
            
#             just_collected_email = previous_field == "email" and collected_data.get("email")
#             has_name = bool(collected_data.get("name"))
#             has_email = bool(collected_data.get("email"))
            
#             call_id = conversation_state["call_id"]
#             already_booked = await self._check_appointment_exists(call_id)
#             is_locked = call_id in self.booking_locks
            
#             logger.info(f"📊 Booking check:")
#             logger.info(f"   Just collected email: {just_collected_email}")
#             logger.info(f"   Has name: {has_name}, email: {has_email}")
#             logger.info(f"   Already booked: {already_booked}, Locked: {is_locked}")
#             logger.info(f"   📋 Collected data: {collected_data}")
            
#             if just_collected_email and has_name and has_email and not already_booked and not is_locked:
#                 logger.info(f"🎯 BOOKING APPOINTMENT NOW!")
#                 logger.info(f"📋 Final booking data: {collected_data}")
                
#                 self.booking_locks.add(call_id)
                
#                 try:
#                     booking_result = await self._attempt_appointment_booking(
#                         collected_data,
#                         conversation_state["call_id"]
#                     )
                    
#                     if booking_result.get("success"):
#                         logger.info(f"✅ BOOKING SUCCESS!")
#                         return {
#                             "success": True,
#                             "found_in_campaign": True,
#                             "response": booking_result.get("response"),
#                             "node_id": "booking_confirmation",
#                             "node_type": "confirmation",
#                             "is_end": False
#                         }
#                 finally:
#                     self.booking_locks.discard(call_id)
            
#             possible_next_nodes = await self._find_next_nodes_by_keywords(
#                 current_node,
#                 user_input,
#                 workflow.get("connections", []),
#                 workflow.get("nodes", [])
#             )
            
#             if possible_next_nodes:
#                 next_node = possible_next_nodes[0]
                
#                 response = await self._get_exact_node_message(next_node, conversation_state)
                
#                 await self._update_conversation_state(
#                     conversation_state["call_id"],
#                     next_node,
#                     user_input,
#                     response
#                 )
                
#                 return {
#                     "success": True,
#                     "found_in_campaign": True,
#                     "response": response,
#                     "node_id": next_node.get("id"),
#                     "node_type": next_node.get("type"),
#                     "is_end": False
#                 }
#             else:
#                 logger.warning(f"⚠️ NO MATCHES FOUND")
#                 return {
#                     "success": True,
#                     "found_in_campaign": False,
#                     "response": None
#                 }
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": None
#             }
    
#     async def _check_appointment_exists(self, call_id: str) -> bool:
#         """Check if appointment exists"""
#         try:
#             db = await get_database()
#             appointment = await db.appointments.find_one({"call_id": ObjectId(call_id)})
#             return bool(appointment)
#         except:
#             return False
    
#     async def _find_next_nodes_by_keywords(
#         self,
#         current_node: Dict[str, Any],
#         user_input: str,
#         connections: List[Dict[str, Any]],
#         all_nodes: List[Dict[str, Any]]
#     ) -> List[Dict[str, Any]]:
#         """Find next nodes"""
#         try:
#             user_input_lower = user_input.lower().strip()
#             possible_matches = []
            
#             outgoing_connections = [
#                 conn for conn in connections 
#                 if conn.get("from") == current_node.get("id")
#             ]
            
#             for connection in outgoing_connections:
#                 keywords = connection.get("keywords", [])
                
#                 if not keywords:
#                     target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
#                     if target_node:
#                         possible_matches.append(target_node)
#                     continue
                
#                 for keyword in keywords:
#                     if keyword and keyword.lower() in user_input_lower:
#                         target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
#                         if target_node:
#                             possible_matches.append(target_node)
#                             break
            
#             if not possible_matches:
#                 is_collecting = await self._is_data_collection_node(current_node)
                
#                 if is_collecting and outgoing_connections:
#                     target_node = next((n for n in all_nodes if n.get("id") == outgoing_connections[0].get("to")), None)
#                     if target_node:
#                         possible_matches.append(target_node)
            
#             return possible_matches
            
#         except:
#             return []
    
#     async def _is_data_collection_node(self, node: Dict[str, Any]) -> bool:
#         """Check if node collects data"""
#         node_data = node.get("data", {})
#         message = node_data.get("message", "").lower()
#         indicators = ["name", "email", "phone", "service", "date", "time"]
#         return any(ind in message for ind in indicators)
    
#     async def _get_conversation_state(
#         self,
#         call_id: str,
#         workflow: Dict[str, Any]
#     ) -> Dict[str, Any]:
#         """Get conversation state"""
#         try:
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
#             if not conversation:
#                 start_node = await self.find_start_node(workflow)
#                 return {
#                     "call_id": call_id,
#                     "workflow_id": str(workflow["_id"]),
#                     "current_node": start_node or workflow["nodes"][0],
#                     "collected_data": {},
#                     "conversation_history": [],
#                     "previous_field": None
#                 }
            
#             messages = conversation.get("messages", [])
#             current_node = None
#             previous_field = None
            
#             for msg in reversed(messages):
#                 if msg.get("role") == "assistant":
#                     metadata = msg.get("metadata", {})
#                     node_id = metadata.get("node_id")
#                     previous_field = metadata.get("collecting_field")
                    
#                     if node_id:
#                         current_node = next(
#                             (n for n in workflow["nodes"] if n.get("id") == node_id),
#                             None
#                         )
#                         break
            
#             if not current_node:
#                 current_node = await self.find_start_node(workflow)
            
#             collected_data = conversation.get("metadata", {}).get("appointment_data", {})
            
#             return {
#                 "call_id": call_id,
#                 "workflow_id": str(workflow["_id"]),
#                 "current_node": current_node,
#                 "collected_data": collected_data,
#                 "conversation_history": messages,
#                 "previous_field": previous_field
#             }
            
#         except Exception as e:
#             start_node = await self.find_start_node(workflow)
#             return {
#                 "call_id": call_id,
#                 "workflow_id": str(workflow["_id"]),
#                 "current_node": start_node or workflow["nodes"][0],
#                 "collected_data": {},
#                 "conversation_history": [],
#                 "previous_field": None
#             }
    
#     async def _update_conversation_state(
#         self,
#         call_id: str,
#         new_node: Dict[str, Any],
#         user_input: str,
#         response: str
#     ):
#         """Update conversation state"""
#         try:
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
#             if not conversation:
#                 return
            
#             collecting_field = await self._detect_collecting_field(new_node)
            
#             metadata = {
#                 "workflow_id": str(conversation.get("metadata", {}).get("workflow_id")),
#                 "node_id": new_node.get("id"),
#                 "node_type": new_node.get("type"),
#                 "collecting_field": collecting_field
#             }
            
#             await db.conversations.update_one(
#                 {"_id": conversation["_id"]},
#                 {
#                     "$push": {
#                         "messages": {
#                             "$each": [
#                                 {
#                                     "role": "user",
#                                     "content": user_input,
#                                     "timestamp": datetime.utcnow(),
#                                     "metadata": metadata
#                                 },
#                                 {
#                                     "role": "assistant",
#                                     "content": response,
#                                     "timestamp": datetime.utcnow(),
#                                     "metadata": metadata
#                                 }
#                             ]
#                         }
#                     },
#                     "$set": {"updated_at": datetime.utcnow()}
#                 }
#             )
            
#         except:
#             pass
    
#     async def _detect_collecting_field(self, node: Dict[str, Any]) -> Optional[str]:
#         """Detect field"""
#         node_data = node.get("data", {})
#         message = node_data.get("message", "").lower()
        
#         patterns = {
#             "name": ["name", "called"],
#             "email": ["email", "e-mail"],
#             "phone": ["phone", "number"],
#             "service": ["service", "help"],
#             "date": ["date", "when", "schedule"]
#         }
        
#         for field, keywords in patterns.items():
#             if any(kw in message for kw in keywords):
#                 return field
        
#         return None
    
#     async def _get_exact_node_message(
#         self,
#         node: Dict[str, Any],
#         conversation_state: Dict[str, Any]
#     ) -> str:
#         """Get node message"""
#         try:
#             node_data = node.get("data", {})
#             message = node_data.get("message", "")
            
#             collected_data = conversation_state.get("collected_data", {})
            
#             if "{name}" in message and collected_data.get("name"):
#                 message = message.replace("{name}", collected_data["name"])
#             if "{date}" in message and collected_data.get("date"):
#                 message = message.replace("{date}", collected_data["date"])
            
#             if not message:
#                 message = "How can I help you?"
            
#             return message
            
#         except:
#             return "How can I help you?"
    
#     async def _collect_field_data(
#         self,
#         user_input: str,
#         field_type: str,
#         call_id: str,
#         conversation_state: Dict[str, Any]
#     ):
#         """Collect field data"""
#         try:
#             logger.info(f"📥 Extracting {field_type} from: '{user_input}'")
            
#             extracted_value = await self._extract_field_value(user_input, field_type)
            
#             if extracted_value:
#                 logger.info(f"✅ Collected {field_type}: {extracted_value}")
                
#                 db = await get_database()
                
#                 update_result = await db.conversations.update_one(
#                     {"call_id": ObjectId(call_id)},
#                     {
#                         "$set": {
#                             f"metadata.appointment_data.{field_type}": extracted_value,
#                             "updated_at": datetime.utcnow()
#                         }
#                     }
#                 )
                
#                 logger.info(f"💾 Saved {field_type} to database (modified: {update_result.modified_count})")
                
#                 verification = await db.conversations.find_one({"call_id": ObjectId(call_id)})
#                 saved_value = verification.get("metadata", {}).get("appointment_data", {}).get(field_type)
#                 logger.info(f"🔍 Verification - {field_type} in DB: {saved_value}")
                
#                 conversation_state["collected_data"][field_type] = extracted_value
#             else:
#                 logger.warning(f"⚠️ Failed to extract {field_type}")
            
#         except Exception as e:
#             logger.error(f"❌ Error collecting {field_type}: {e}")
#             import traceback
#             traceback.print_exc()
    
#     async def _extract_field_value(self, user_input: str, field_type: str) -> Optional[str]:
#         """Extract field value"""
#         try:
#             if field_type == "email":
#                 logger.info(f"📧 Extracting email from: '{user_input}'")
                
#                 user_input_lower = user_input.lower().strip()
                
#                 email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#                 match = re.search(email_pattern, user_input_lower, re.IGNORECASE)
#                 if match:
#                     email = match.group(0)
#                     logger.info(f"✅ Extracted (standard): {email}")
#                     return email
                
#                 domain_map = {
#                     'gmail': 'gmail.com',
#                     'g mail': 'gmail.com',
#                     'gb': 'gmail.com',
#                     'gee mail': 'gmail.com',
#                     'hotmail': 'hotmail.com',
#                     'yahoo': 'yahoo.com',
#                     'outlook': 'outlook.com',
#                 }
                
#                 domain = None
#                 for provider, full_domain in domain_map.items():
#                     if provider in user_input_lower:
#                         domain = full_domain
#                         logger.info(f"✅ Found domain: {domain}")
#                         break
                
#                 if not domain:
#                     logger.warning(f"⚠️ No domain found, using default")
#                     domain = "gmail.com"
#                     logger.info(f"✅ Using default: {domain}")
                
#                 filler_words = {
#                     'okay', 'ok', 'my', 'email', 'is', 'the', 'a', 'an', 'uh', 'um',
#                     'at', 'dot', 'com', 'gmail', 'hotmail', 'rate', 'red', 'gb',
#                     'thank', 'you', 'thanks', 'please', 'and', 'or', 'listen', 'carefully'
#                 }
                
#                 words = re.split(r'[\s,.\?!]+', user_input_lower)
                
#                 letters = []
#                 for word in words:
#                     if word in filler_words:
#                         continue
#                     cleaned = re.sub(r'[^a-z0-9]', '', word)
#                     if cleaned and len(cleaned) <= 10:
#                         letters.append(cleaned)
                
#                 username = ''.join(letters)
                
#                 if username:
#                     email = f"{username}@{domain}"
#                     logger.info(f"✅ CONSTRUCTED: {email}")
#                     return email
                
#                 logger.warning(f"⚠️ Could not construct email")
#                 return None
            
#             elif field_type == "phone":
#                 match = re.search(r'[\d\s\-\(\)\.]+\d{3,}', user_input)
#                 if match:
#                     digits = re.sub(r'\D', '', match.group(0))
#                     if len(digits) >= 10:
#                         return digits
#                 return None
            
#             elif field_type in ["name", "service"]:
#                 cleaned = user_input.strip()
#                 prefixes = ["my name is", "i am", "i'm", "i want", "book", "to book"]
                
#                 for prefix in prefixes:
#                     if cleaned.lower().startswith(prefix):
#                         cleaned = cleaned[len(prefix):].strip()
                
#                 cleaned = cleaned.rstrip('.').rstrip(',')
                
#                 if len(cleaned) > 1 and len(cleaned) < 50:
#                     return cleaned.title() if field_type == "name" else cleaned
                
#                 return None
            
#             elif field_type == "date":
#                 date_value = user_input.strip()
#                 logger.info(f"📅 Date field collected: '{date_value}'")
#                 return date_value
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error extracting {field_type}: {e}")
#             return None
    
#     async def _attempt_appointment_booking(
#         self,
#         collected_data: Dict[str, Any],
#         call_id: str
#     ) -> Dict[str, Any]:
#         """Book appointment"""
#         try:
#             logger.info(f"\n{'='*80}")
#             logger.info(f"📅 BOOKING APPOINTMENT")
#             logger.info(f"📋 Collected Data from parameter: {collected_data}")
#             logger.info(f"{'='*80}\n")
            
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
#             fresh_collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
            
#             logger.info(f"📋 Fresh data from database: {fresh_collected_data}")
            
#             collected_data = fresh_collected_data
            
#             required = ["name", "email"]
#             missing = [f for f in required if not collected_data.get(f)]
            
#             if missing:
#                 logger.error(f"❌ Missing: {missing}")
#                 return {
#                     "success": False,
#                     "error": f"Missing: {', '.join(missing)}"
#                 }
            
#             appointment_date = None
#             if collected_data.get("date"):
#                 logger.info(f"📅 Parsing date from collected data: '{collected_data.get('date')}'")
#                 appointment_date = await self._parse_date(collected_data["date"])
            
#             if not appointment_date:
#                 logger.warning(f"⚠️ No valid date, using tomorrow")
#                 appointment_date = datetime.utcnow() + timedelta(days=1)
#                 appointment_date = appointment_date.replace(hour=10, minute=0, second=0, microsecond=0)
            
#             logger.info(f"✅ Final appointment date (UTC): {appointment_date}")
            
#             appointment_time = appointment_date.strftime("%H:%M")
            
#             customer_name = collected_data.get("name", "Customer")
#             customer_email = collected_data.get("email", "")
#             service_type = collected_data.get("service", "House Painting")
            
#             # ✅ Calculate local time for display (GMT+5)
#             local_datetime = appointment_date + timedelta(hours=USER_TIMEZONE_OFFSET)
            
#             logger.info(f"📋 Final booking details:")
#             logger.info(f"   Name: {customer_name}")
#             logger.info(f"   Email: {customer_email}")
#             logger.info(f"   Service: {service_type}")
#             logger.info(f"   Date (UTC): {appointment_date}")
#             logger.info(f"   Date (GMT+{USER_TIMEZONE_OFFSET}): {local_datetime}")
#             logger.info(f"   Time: {appointment_time}")
            
#             calendar_event = None
#             try:
#                 logger.info("📆 Creating Google Calendar event...")
                
#                 calendar_result = await google_calendar_service.create_event(
#                     customer_name=customer_name,
#                     customer_email=customer_email,
#                     customer_phone=collected_data.get("phone", ""),
#                     appointment_date=appointment_date,
#                     appointment_time=appointment_time,
#                     duration_minutes=60,
#                     service_type=service_type,
#                     notes=None
#                 )
                
#                 if calendar_result.get("success"):
#                     calendar_event = calendar_result
#                     logger.info(f"✅ Calendar event created!")
#                     logger.info(f"   Event ID: {calendar_result.get('event_id')}")
#                 else:
#                     logger.warning(f"⚠️ Calendar failed: {calendar_result.get('error')}")
                    
#             except Exception as e:
#                 logger.error(f"⚠️ Calendar error: {e}")
#                 import traceback
#                 traceback.print_exc()
            
#             appointment_data = {
#                 "call_id": ObjectId(call_id),
#                 "customer_name": customer_name,
#                 "customer_email": customer_email,
#                 "customer_phone": collected_data.get("phone", ""),
#                 "service": service_type,
#                 "appointment_date": appointment_date,
#                 "status": "confirmed",
#                 "google_calendar_event_id": calendar_event.get("event_id") if calendar_event else None,
#                 "google_calendar_link": calendar_event.get("html_link") if calendar_event else None,
#                 "created_at": datetime.utcnow()
#             }
            
#             result = await db.appointments.insert_one(appointment_data)
#             appointment_id = str(result.inserted_id)
            
#             logger.info(f"✅ Appointment saved: {appointment_id}")
            
#             try:
#                 logger.info(f"📧 Sending email to {customer_email}...")
                
#                 # ✅ Use local time for email
#                 date_str = local_datetime.strftime("%A, %B %d, %Y")
#                 time_str = local_datetime.strftime("%I:%M %p")
                
#                 await email_service.send_appointment_confirmation(
#                     to_email=customer_email,
#                     customer_name=customer_name,
#                     appointment_date=date_str,
#                     appointment_time=time_str,
#                     service_type=service_type
#                 )
                
#                 logger.info(f"✅ Email sent!")
#             except Exception as e:
#                 logger.error(f"⚠️ Email error: {e}")
#                 import traceback
#                 traceback.print_exc()
            
#             # ✅ Use local time for response
#             date_str = local_datetime.strftime("%A, %B %d at %I:%M %p")
            
#             response = f"Perfect! Your appointment for {service_type} is confirmed for {date_str}. A confirmation email has been sent to {customer_email}. Is there anything else I can help you with?"
            
#             logger.info(f"\n{'='*80}")
#             logger.info(f"✅ BOOKING COMPLETE!")
#             logger.info(f"   Appointment ID: {appointment_id}")
#             logger.info(f"   Google Event: {calendar_event.get('event_id') if calendar_event else 'N/A'}")
#             logger.info(f"   Email: Sent to {customer_email}")
#             logger.info(f"{'='*80}\n")
            
#             return {
#                 "success": True,
#                 "response": response,
#                 "appointment_id": appointment_id
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Booking error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": str(e),
#                 "response": "I apologize, there was an issue booking your appointment."
#             }
    
#     async def _parse_date(self, date_string: str) -> Optional[datetime]:
#         """✅ COMPLETE FIX: Parse date with GMT+5 to UTC conversion"""
#         try:
#             date_str = date_string.lower().strip()
#             now = datetime.utcnow()
            
#             logger.info(f"📅 Parsing date string: '{date_str}'")
#             logger.info(f"🌍 User timezone: GMT+{USER_TIMEZONE_OFFSET}")
            
#             # Enhanced time pattern to handle "10:00 a.m." format
#             time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)'
            
#             if "today" in date_str:
#                 hour = 10
#                 minute = 0
#                 time_match = re.search(time_pattern, date_str, re.IGNORECASE)
#                 if time_match:
#                     hour = int(time_match.group(1))
#                     minute = int(time_match.group(2)) if time_match.group(2) else 0
#                     meridiem = time_match.group(3)
                    
#                     if 'p' in meridiem and hour != 12:
#                         hour += 12
#                     elif 'a' in meridiem and hour == 12:
#                         hour = 0
                    
#                     logger.info(f"✅ Extracted time: {hour}:{minute:02d} from '{date_str}'")
                
#                 result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
#                 # ✅ Convert GMT+5 to UTC
#                 result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
#                 logger.info(f"✅ Parsed 'today' as {hour}:{minute:02d} GMT+{USER_TIMEZONE_OFFSET}")
#                 logger.info(f"✅ Converted to UTC: {result}")
#                 return result
            
#             if "tomorrow" in date_str:
#                 tomorrow = now + timedelta(days=1)
#                 hour = 10
#                 minute = 0
#                 time_match = re.search(time_pattern, date_str, re.IGNORECASE)
#                 if time_match:
#                     hour = int(time_match.group(1))
#                     minute = int(time_match.group(2)) if time_match.group(2) else 0
#                     meridiem = time_match.group(3)
                    
#                     if 'p' in meridiem and hour != 12:
#                         hour += 12
#                     elif 'a' in meridiem and hour == 12:
#                         hour = 0
                    
#                     logger.info(f"✅ Extracted time: {hour}:{minute:02d} from '{date_str}'")
                
#                 result = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
#                 # ✅ Convert GMT+5 to UTC
#                 result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
#                 logger.info(f"✅ Parsed 'tomorrow' as {hour}:{minute:02d} GMT+{USER_TIMEZONE_OFFSET}")
#                 logger.info(f"✅ Converted to UTC: {result}")
#                 return result
            
#             # Handle weekday names
#             weekdays = {
#                 'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
#                 'friday': 4, 'saturday': 5, 'sunday': 6
#             }
            
#             for day_name, day_num in weekdays.items():
#                 if day_name in date_str:
#                     current_weekday = now.weekday()
#                     days_until = (day_num - current_weekday) % 7
#                     if days_until == 0:
#                         days_until = 7
                    
#                     target_day = now + timedelta(days=days_until)
                    
#                     hour = 10
#                     minute = 0
                    
#                     time_match = re.search(time_pattern, date_str, re.IGNORECASE)
#                     if time_match:
#                         hour = int(time_match.group(1))
#                         minute = int(time_match.group(2)) if time_match.group(2) else 0
#                         meridiem = time_match.group(3)
                        
#                         if 'p' in meridiem and hour != 12:
#                             hour += 12
#                         elif 'a' in meridiem and hour == 12:
#                             hour = 0
                        
#                         logger.info(f"✅ Extracted time: {hour}:{minute:02d} from '{date_str}'")
#                     else:
#                         logger.warning(f"⚠️ No time found in '{date_str}', using default 10:00 AM")
                    
#                     result = target_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
#                     # ✅ CRITICAL: Convert GMT+5 to UTC
#                     result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
                    
#                     logger.info(f"✅ Parsed '{day_name}' at {hour}:{minute:02d} GMT+{USER_TIMEZONE_OFFSET}")
#                     logger.info(f"✅ Converted to UTC: {result}")
#                     return result
            
#             logger.warning(f"⚠️ Could not parse date: {date_str}, using tomorrow at 10:00 AM")
#             tomorrow = datetime.utcnow() + timedelta(days=1)
#             result = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
#             result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
#             return result
            
#         except Exception as e:
#             logger.error(f"❌ Date parse error: {e}")
#             import traceback
#             traceback.print_exc()
#             return None
    
#     async def _fallback_to_openai(
#         self,
#         user_input: str,
#         call_id: str,
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """OpenAI fallback"""
#         try:
#             from app.services.ai_agent import ai_agent_service
            
#             logger.info(f"🤖 Using OpenAI")
            
#             response = await ai_agent_service._process_with_openai(
#                 user_input,
#                 call_id,
#                 agent_config
#             )
            
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": response,
#                 "node_id": "openai_fallback",
#                 "node_type": "fallback",
#                 "is_end": False
#             }
            
#         except Exception as e:
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": "How can I help you?",
#                 "node_id": "openai_fallback",
#                 "node_type": "fallback",
#                 "is_end": False
#             }


# workflow_engine = WorkflowEngine()


# # backend/app/services/workflow_engine.py - COMPLETE FILE WITH EMAIL LOGGING FIX without crm  most latest 

# import logging
# import re
# from typing import Dict, Any, Optional, List
# from datetime import datetime, timedelta
# from bson import ObjectId

# from app.database import get_database
# from app.services.google_calendar import google_calendar_service
# from app.services.email import email_service
# # ✅ ADD: Also import email_automation_service for logging only
# from app.services.email_automation import email_automation_service

# logger = logging.getLogger(__name__)

# # ✅ USER TIMEZONE CONFIGURATION
# USER_TIMEZONE_OFFSET = 5 


# class WorkflowEngine:
#     """Campaign Builder Workflow Engine"""
    
#     def __init__(self):
#         self.workflow_cache = {}
#         self.booking_locks = set()
    
#     async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
#         """Get workflow"""
#         try:
#             db = await get_database()
            
#             if isinstance(workflow_id, str):
#                 if not ObjectId.is_valid(workflow_id):
#                     return None
#                 workflow_id = ObjectId(workflow_id)
            
#             workflow = await db.flows.find_one({"_id": workflow_id})
            
#             if workflow:
#                 logger.info(f"✅ Loaded workflow: {workflow.get('name')}")
            
#             return workflow
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             return None
    
#     async def find_start_node(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#         """Find start node"""
#         try:
#             nodes = workflow.get("nodes", [])
#             if not nodes:
#                 return None
            
#             for node in nodes:
#                 if node.get("type") == "begin":
#                     return node
            
#             for node in nodes:
#                 if node.get("type") in ["welcome", "message"]:
#                     return node
            
#             return nodes[0]
            
#         except:
#             return None
    
#     async def process_conversation_turn(
#         self,
#         workflow_id: str,
#         user_input: str,
#         call_id: str,
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """Main processing"""
#         try:
#             logger.info(f"\n{'='*80}")
#             logger.info(f"🎯 Processing: '{user_input}'")
#             logger.info(f"{'='*80}\n")
            
#             workflow = await self.get_workflow(workflow_id)
#             if not workflow:
#                 return await self._fallback_to_openai(user_input, call_id, agent_config)
            
#             conversation_state = await self._get_conversation_state(call_id, workflow)
            
#             result = await self._process_with_campaign(
#                 user_input, 
#                 conversation_state, 
#                 workflow,
#                 agent_config
#             )
            
#             if result.get("found_in_campaign"):
#                 return result
#             else:
#                 return await self._fallback_to_openai(user_input, call_id, agent_config)
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
#             return await self._fallback_to_openai(user_input, call_id, agent_config)
    
#     async def _process_with_campaign(
#         self,
#         user_input: str,
#         conversation_state: Dict[str, Any],
#         workflow: Dict[str, Any],
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """Process with campaign"""
#         try:
#             current_node = conversation_state["current_node"]
#             logger.info(f"📍 Current node: {current_node.get('id')}")
            
#             previous_field = conversation_state.get("previous_field")
            
#             if previous_field:
#                 db = await get_database()
#                 conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
#                 existing_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
                
#                 if not existing_data.get(previous_field):
#                     logger.info(f"📥 Collecting {previous_field} from: '{user_input}'")
#                     await self._collect_field_data(
#                         user_input, 
#                         previous_field, 
#                         conversation_state["call_id"],
#                         conversation_state
#                     )
            
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
#             collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
            
#             has_name = bool(collected_data.get("name"))
#             has_email = bool(collected_data.get("email"))
            
#             call_id = conversation_state["call_id"]
#             already_booked = await self._check_appointment_exists(call_id)
#             is_locked = call_id in self.booking_locks
            
#             if has_name and has_email and not already_booked and not is_locked:
#                 logger.info(f"🎯 BOOKING APPOINTMENT NOW!")
#                 logger.info(f"📋 Final booking data: {collected_data}")
                
#                 self.booking_locks.add(call_id)
                
#                 try:
#                     booking_result = await self._attempt_appointment_booking(
#                         collected_data,
#                         conversation_state["call_id"]
#                     )
                    
#                     if booking_result.get("success"):
#                         logger.info(f"✅ BOOKING SUCCESS!")
#                         return {
#                             "success": True,
#                             "found_in_campaign": True,
#                             "response": booking_result.get("response"),
#                             "node_id": "booking_confirmation",
#                             "node_type": "confirmation",
#                             "is_end": False
#                         }
#                 finally:
#                     self.booking_locks.discard(call_id)
            
#             possible_next_nodes = await self._find_next_nodes_by_keywords(
#                 current_node,
#                 user_input,
#                 workflow.get("connections", []),
#                 workflow.get("nodes", [])
#             )
            
#             if possible_next_nodes:
#                 next_node = possible_next_nodes[0]
                
#                 response = await self._get_exact_node_message(next_node, conversation_state)
                
#                 await self._update_conversation_state(
#                     conversation_state["call_id"],
#                     next_node,
#                     user_input,
#                     response
#                 )
                
#                 return {
#                     "success": True,
#                     "found_in_campaign": True,
#                     "response": response,
#                     "node_id": next_node.get("id"),
#                     "node_type": next_node.get("type"),
#                     "is_end": False
#                 }
#             else:
#                 logger.warning(f"⚠️ NO MATCHES FOUND")
#                 return {
#                     "success": True,
#                     "found_in_campaign": False,
#                     "response": None
#                 }
            
#         except Exception as e:
#             logger.error(f"❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": None
#             }
    
#     async def _check_appointment_exists(self, call_id: str) -> bool:
#         """Check if appointment exists"""
#         try:
#             db = await get_database()
#             appointment = await db.appointments.find_one({"call_id": ObjectId(call_id)})
#             return bool(appointment)
#         except:
#             return False
    
#     async def _find_next_nodes_by_keywords(
#         self,
#         current_node: Dict[str, Any],
#         user_input: str,
#         connections: List[Dict[str, Any]],
#         all_nodes: List[Dict[str, Any]]
#     ) -> List[Dict[str, Any]]:
#         """Find next nodes"""
#         try:
#             user_input_lower = user_input.lower().strip()
#             possible_matches = []
            
#             outgoing_connections = [
#                 conn for conn in connections 
#                 if conn.get("from") == current_node.get("id")
#             ]
            
#             for connection in outgoing_connections:
#                 keywords = connection.get("keywords", [])
                
#                 if not keywords:
#                     target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
#                     if target_node:
#                         possible_matches.append(target_node)
#                     continue
                
#                 for keyword in keywords:
#                     if keyword and keyword.lower() in user_input_lower:
#                         target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
#                         if target_node:
#                             possible_matches.append(target_node)
#                             break
            
#             if not possible_matches:
#                 is_collecting = await self._is_data_collection_node(current_node)
                
#                 if is_collecting and outgoing_connections:
#                     target_node = next((n for n in all_nodes if n.get("id") == outgoing_connections[0].get("to")), None)
#                     if target_node:
#                         possible_matches.append(target_node)
            
#             return possible_matches
            
#         except:
#             return []
    
#     async def _is_data_collection_node(self, node: Dict[str, Any]) -> bool:
#         """Check if node collects data"""
#         node_data = node.get("data", {})
#         message = node_data.get("message", "").lower()
#         indicators = ["name", "email", "phone", "service", "date", "time"]
#         return any(ind in message for ind in indicators)
    
#     async def _get_conversation_state(
#         self,
#         call_id: str,
#         workflow: Dict[str, Any]
#     ) -> Dict[str, Any]:
#         """Get conversation state"""
#         try:
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
#             if not conversation:
#                 start_node = await self.find_start_node(workflow)
#                 return {
#                     "call_id": call_id,
#                     "workflow_id": str(workflow["_id"]),
#                     "current_node": start_node or workflow["nodes"][0],
#                     "collected_data": {},
#                     "conversation_history": [],
#                     "previous_field": None
#                 }
            
#             messages = conversation.get("messages", [])
#             current_node = None
#             previous_field = None
            
#             for msg in reversed(messages):
#                 if msg.get("role") == "assistant":
#                     metadata = msg.get("metadata", {})
#                     node_id = metadata.get("node_id")
#                     previous_field = metadata.get("collecting_field")
                    
#                     if node_id:
#                         current_node = next(
#                             (n for n in workflow["nodes"] if n.get("id") == node_id),
#                             None
#                         )
#                         break
            
#             if not current_node:
#                 current_node = await self.find_start_node(workflow)
            
#             collected_data = conversation.get("metadata", {}).get("appointment_data", {})
            
#             return {
#                 "call_id": call_id,
#                 "workflow_id": str(workflow["_id"]),
#                 "current_node": current_node,
#                 "collected_data": collected_data,
#                 "conversation_history": messages,
#                 "previous_field": previous_field
#             }
            
#         except Exception as e:
#             start_node = await self.find_start_node(workflow)
#             return {
#                 "call_id": call_id,
#                 "workflow_id": str(workflow["_id"]),
#                 "current_node": start_node or workflow["nodes"][0],
#                 "collected_data": {},
#                 "conversation_history": [],
#                 "previous_field": None
#             }
    
#     async def _update_conversation_state(
#         self,
#         call_id: str,
#         new_node: Dict[str, Any],
#         user_input: str,
#         response: str
#     ):
#         """Update conversation state"""
#         try:
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
#             if not conversation:
#                 return
            
#             collecting_field = await self._detect_collecting_field(new_node)
            
#             metadata = {
#                 "workflow_id": str(conversation.get("metadata", {}).get("workflow_id")),
#                 "node_id": new_node.get("id"),
#                 "node_type": new_node.get("type"),
#                 "collecting_field": collecting_field
#             }
            
#             await db.conversations.update_one(
#                 {"_id": conversation["_id"]},
#                 {
#                     "$push": {
#                         "messages": {
#                             "$each": [
#                                 {
#                                     "role": "user",
#                                     "content": user_input,
#                                     "timestamp": datetime.utcnow(),
#                                     "metadata": metadata
#                                 },
#                                 {
#                                     "role": "assistant",
#                                     "content": response,
#                                     "timestamp": datetime.utcnow(),
#                                     "metadata": metadata
#                                 }
#                             ]
#                         }
#                     },
#                     "$set": {"updated_at": datetime.utcnow()}
#                 }
#             )
            
#         except:
#             pass
    
#     async def _detect_collecting_field(self, node: Dict[str, Any]) -> Optional[str]:
#         """Detect field"""
#         node_data = node.get("data", {})
#         message = node_data.get("message", "").lower()
        
#         patterns = {
#             "name": ["name", "called"],
#             "email": ["email", "e-mail"],
#             "phone": ["phone", "number"],
#             "service": ["service", "help"],
#             "date": ["date", "when", "schedule"]
#         }
        
#         for field, keywords in patterns.items():
#             if any(kw in message for kw in keywords):
#                 return field
        
#         return None
    
#     async def _get_exact_node_message(
#         self,
#         node: Dict[str, Any],
#         conversation_state: Dict[str, Any]
#     ) -> str:
#         """Get node message"""
#         try:
#             node_data = node.get("data", {})
#             message = node_data.get("message", "")
            
#             collected_data = conversation_state.get("collected_data", {})
            
#             if "{name}" in message and collected_data.get("name"):
#                 message = message.replace("{name}", collected_data["name"])
#             if "{date}" in message and collected_data.get("date"):
#                 message = message.replace("{date}", collected_data["date"])
            
#             if not message:
#                 message = "How can I help you?"
            
#             return message
            
#         except:
#             return "How can I help you?"
    
#     async def _collect_field_data(
#         self,
#         user_input: str,
#         field_type: str,
#         call_id: str,
#         conversation_state: Dict[str, Any]
#     ):
#         """Collect field data"""
#         try:
#             logger.info(f"📥 Extracting {field_type} from: '{user_input}'")
            
#             extracted_value = await self._extract_field_value(user_input, field_type)
            
#             if extracted_value:
#                 logger.info(f"✅ Collected {field_type}: {extracted_value}")
                
#                 db = await get_database()
                
#                 update_result = await db.conversations.update_one(
#                     {"call_id": ObjectId(call_id)},
#                     {
#                         "$set": {
#                             f"metadata.appointment_data.{field_type}": extracted_value,
#                             "updated_at": datetime.utcnow()
#                         }
#                     }
#                 )
                
#                 logger.info(f"💾 Saved {field_type} to database (modified: {update_result.modified_count})")
                
#                 verification = await db.conversations.find_one({"call_id": ObjectId(call_id)})
#                 saved_value = verification.get("metadata", {}).get("appointment_data", {}).get(field_type)
#                 logger.info(f"🔍 Verification - {field_type} in DB: {saved_value}")
                
#                 conversation_state["collected_data"][field_type] = extracted_value
#             else:
#                 logger.warning(f"⚠️ Failed to extract {field_type}")
            
#         except Exception as e:
#             logger.error(f"❌ Error collecting {field_type}: {e}")
#             import traceback
#             traceback.print_exc()
    
#     async def _extract_field_value(self, user_input: str, field_type: str) -> Optional[str]:
#         """Extract field value"""
#         try:
#             if field_type == "email":
#                 logger.info(f"📧 Extracting email from: '{user_input}'")
                
#                 user_input_lower = user_input.lower().strip()
                
#                 email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#                 match = re.search(email_pattern, user_input_lower, re.IGNORECASE)
#                 if match:
#                     email = match.group(0)
#                     logger.info(f"✅ Extracted (standard): {email}")
#                     return email
                
#                 domain_map = {
#                     'gmail': 'gmail.com',
#                     'g mail': 'gmail.com',
#                     'gb': 'gmail.com',
#                     'gee mail': 'gmail.com',
#                     'hotmail': 'hotmail.com',
#                     'yahoo': 'yahoo.com',
#                     'outlook': 'outlook.com',
#                 }
                
#                 domain = None
#                 for provider, full_domain in domain_map.items():
#                     if provider in user_input_lower:
#                         domain = full_domain
#                         logger.info(f"✅ Found domain: {domain}")
#                         break
                
#                 if not domain:
#                     logger.warning(f"⚠️ No domain found, using default")
#                     domain = "gmail.com"
#                     logger.info(f"✅ Using default: {domain}")
                
#                 filler_words = {
#                     'okay', 'ok', 'my', 'email', 'is', 'the', 'a', 'an', 'uh', 'um',
#                     'at', 'dot', 'com', 'gmail', 'hotmail', 'rate', 'red', 'gb',
#                     'thank', 'you', 'thanks', 'please', 'and', 'or', 'listen', 'carefully'
#                 }
                
#                 words = re.split(r'[\s,.\?!]+', user_input_lower)
                
#                 letters = []
#                 for word in words:
#                     if word in filler_words:
#                         continue
#                     cleaned = re.sub(r'[^a-z0-9]', '', word)
#                     if cleaned and len(cleaned) <= 10:
#                         letters.append(cleaned)
                
#                 username = ''.join(letters)
                
#                 if username:
#                     email = f"{username}@{domain}"
#                     logger.info(f"✅ CONSTRUCTED: {email}")
#                     return email
                
#                 logger.warning(f"⚠️ Could not construct email")
#                 return None
            
#             elif field_type == "phone":
#                 match = re.search(r'[\d\s\-\(\)\.]+\d{3,}', user_input)
#                 if match:
#                     digits = re.sub(r'\D', '', match.group(0))
#                     if len(digits) >= 10:
#                         return digits
#                 return None
            
#             elif field_type in ["name", "service"]:
#                 cleaned = user_input.strip()
#                 prefixes = ["my name is", "i am", "i'm", "i want", "book", "to book"]
                
#                 for prefix in prefixes:
#                     if cleaned.lower().startswith(prefix):
#                         cleaned = cleaned[len(prefix):].strip()
                
#                 cleaned = cleaned.rstrip('.').rstrip(',')
                
#                 if len(cleaned) > 1 and len(cleaned) < 50:
#                     return cleaned.title() if field_type == "name" else cleaned
                
#                 return None
            
#             elif field_type == "date":
#                 date_value = user_input.strip()
#                 logger.info(f"📅 Date field collected: '{date_value}'")
#                 return date_value
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error extracting {field_type}: {e}")
#             return None
    
#     async def _attempt_appointment_booking(
#         self,
#         collected_data: Dict[str, Any],
#         call_id: str
#     ) -> Dict[str, Any]:
#         """Book appointment with email logging"""
#         try:
#             logger.info(f"\n{'='*80}")
#             logger.info(f"📅 BOOKING APPOINTMENT")
#             logger.info(f"📋 Collected Data from parameter: {collected_data}")
#             logger.info(f"{'='*80}\n")
            
#             db = await get_database()
#             conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
#             fresh_collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
            
#             logger.info(f"📋 Fresh data from database: {fresh_collected_data}")
            
#             collected_data = fresh_collected_data
            
#             required = ["name", "email"]
#             missing = [f for f in required if not collected_data.get(f)]
            
#             if missing:
#                 logger.error(f"❌ Missing: {missing}")
#                 return {
#                     "success": False,
#                     "error": f"Missing: {', '.join(missing)}"
#                 }
            
#             appointment_date = None
#             if collected_data.get("date"):
#                 logger.info(f"📅 Parsing date from collected data: '{collected_data.get('date')}'")
#                 appointment_date = await self._parse_date(collected_data["date"])
            
#             if not appointment_date:
#                 logger.warning(f"⚠️ No valid date, using tomorrow")
#                 appointment_date = datetime.utcnow() + timedelta(days=1)
#                 appointment_date = appointment_date.replace(hour=10, minute=0, second=0, microsecond=0)
            
#             logger.info(f"✅ Final appointment date (UTC): {appointment_date}")
            
#             appointment_time = appointment_date.strftime("%H:%M")
            
#             customer_name = collected_data.get("name", "Customer")
#             customer_email = collected_data.get("email", "")
#             service_type = collected_data.get("service", "House Painting")
            
#             # ✅ Calculate local time for display (GMT+5)
#             local_datetime = appointment_date + timedelta(hours=USER_TIMEZONE_OFFSET)
            
#             logger.info(f"📋 Final booking details:")
#             logger.info(f"   Name: {customer_name}")
#             logger.info(f"   Email: {customer_email}")
#             logger.info(f"   Service: {service_type}")
#             logger.info(f"   Date (UTC): {appointment_date}")
#             logger.info(f"   Date (GMT+{USER_TIMEZONE_OFFSET}): {local_datetime}")
#             logger.info(f"   Time: {appointment_time}")
            
#             # Get user_id from call record for email logging
#             call_record = await db.calls.find_one({"_id": ObjectId(call_id)})
#             user_id = str(call_record.get("user_id")) if call_record else None
            
#             calendar_event = None
#             try:
#                 logger.info("📆 Creating Google Calendar event...")
                
#                 calendar_result = await google_calendar_service.create_event(
#                     customer_name=customer_name,
#                     customer_email=customer_email,
#                     customer_phone=collected_data.get("phone", ""),
#                     appointment_date=appointment_date,
#                     appointment_time=appointment_time,
#                     duration_minutes=60,
#                     service_type=service_type,
#                     notes=None
#                 )
                
#                 if calendar_result.get("success"):
#                     calendar_event = calendar_result
#                     logger.info(f"✅ Calendar event created!")
#                     logger.info(f"   Event ID: {calendar_result.get('event_id')}")
#                 else:
#                     logger.warning(f"⚠️ Calendar failed: {calendar_result.get('error')}")
                    
#             except Exception as e:
#                 logger.error(f"⚠️ Calendar error: {e}")
#                 import traceback
#                 traceback.print_exc()
            
#             appointment_data = {
#                 "call_id": ObjectId(call_id),
#                 "customer_name": customer_name,
#                 "customer_email": customer_email,
#                 "customer_phone": collected_data.get("phone", ""),
#                 "service": service_type,
#                 "appointment_date": appointment_date,
#                 "status": "confirmed",
#                 "google_calendar_event_id": calendar_event.get("event_id") if calendar_event else None,
#                 "google_calendar_link": calendar_event.get("html_link") if calendar_event else None,
#                 "created_at": datetime.utcnow()
#             }
            
#             result = await db.appointments.insert_one(appointment_data)
#             appointment_id = str(result.inserted_id)
            
#             logger.info(f"✅ Appointment saved: {appointment_id}")
            
#             # ✅ UPDATED EMAIL SENDING WITH LOGGING
#             try:
#                 logger.info(f"📧 Sending email to {customer_email}...")
                
#                 date_str = local_datetime.strftime("%A, %B %d, %Y")
#                 time_str = local_datetime.strftime("%I:%M %p")
                
#                 # First send the email using the original email service (keeps existing functionality)
#                 await email_service.send_appointment_confirmation(
#                     to_email=customer_email,
#                     customer_name=customer_name,
#                     appointment_date=date_str,
#                     appointment_time=time_str,
#                     service_type=service_type
#                 )
                
#                 logger.info(f"✅ Email sent successfully!")
                
#                 # ✅ NEW: Also log it to email_logs for frontend visibility
#                 try:
#                     formatted_appointment_date = f"{date_str} at {time_str}"
#                     await email_automation_service.log_appointment_email(
#                         to_email=customer_email,
#                         customer_name=customer_name,
#                         customer_phone=collected_data.get("phone", ""),
#                         service_type=service_type,
#                         appointment_date=formatted_appointment_date,
#                         user_id=user_id,
#                         appointment_id=appointment_id,
#                         call_id=call_id
#                     )
#                     logger.info(f"✅ Email logged to email_logs collection!")
#                 except Exception as log_error:
#                     logger.warning(f"⚠️ Failed to log email: {log_error}")
#                     # Don't fail the booking if logging fails
                
#             except Exception as e:
#                 logger.error(f"⚠️ Email error: {e}")
#                 import traceback
#                 traceback.print_exc()
            
#             date_str = local_datetime.strftime("%A, %B %d at %I:%M %p")
            
#             response = f"Perfect! Your appointment for {service_type} is confirmed for {date_str}. A confirmation email has been sent to {customer_email}. Is there anything else I can help you with?"
            
#             logger.info(f"\n{'='*80}")
#             logger.info(f"✅ BOOKING COMPLETE!")
#             logger.info(f"   Appointment ID: {appointment_id}")
#             logger.info(f"   Google Event: {calendar_event.get('event_id') if calendar_event else 'N/A'}")
#             logger.info(f"   Email: Sent to {customer_email}")
#             logger.info(f"{'='*80}\n")
            
#             return {
#                 "success": True,
#                 "response": response,
#                 "appointment_id": appointment_id
#             }
            
#         except Exception as e:
#             logger.error(f"❌ Booking error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "error": str(e),
#                 "response": "I apologize, there was an issue booking your appointment."
#             }
    
#     async def _parse_date(self, date_string: str) -> Optional[datetime]:
#         """✅ COMPLETE FIX: Parse date with GMT+5 to UTC conversion"""
#         try:
#             date_str = date_string.lower().strip()
#             now = datetime.utcnow()
            
#             logger.info(f"📅 Parsing date string: '{date_str}'")
#             logger.info(f"🌍 User timezone: GMT+{USER_TIMEZONE_OFFSET}")
            
#             # Enhanced time pattern to handle "10:00 a.m." format
#             time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)'
            
#             # Common day names
#             days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
#             # Check for day names with optional time
#             for day_name in days:
#                 if day_name in date_str:
#                     logger.info(f"✅ Found day: {day_name}")
                    
#                     # Calculate days until next occurrence
#                     today_weekday = now.weekday()
#                     target_weekday = days.index(day_name)
                    
#                     days_ahead = target_weekday - today_weekday
#                     if days_ahead <= 0:
#                         days_ahead += 7
                    
#                     result = now + timedelta(days=days_ahead)# Check for time in the input
#                     time_match = re.search(time_pattern, date_str, re.IGNORECASE)
#                     if time_match:
#                         hour = int(time_match.group(1))
#                         minute = int(time_match.group(2) or 0)
#                         am_pm = time_match.group(3).replace('.', '').lower()
                        
#                         if am_pm == 'pm' and hour != 12:
#                             hour += 12
#                         elif am_pm == 'am' and hour == 12:
#                             hour = 0
#                     else:
#                         # Default to 10:00 AM if no time specified
#                         hour = 10
#                         minute = 0
                    
#                     result = result.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
#                     # ✅ CRITICAL: Convert GMT+5 to UTC
#                     result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
                    
#                     logger.info(f"✅ Parsed '{day_name}' at {hour}:{minute:02d} GMT+{USER_TIMEZONE_OFFSET}")
#                     logger.info(f"✅ Converted to UTC: {result}")
#                     return result
            
#             logger.warning(f"⚠️ Could not parse date: {date_str}, using tomorrow at 10:00 AM")
#             tomorrow = datetime.utcnow() + timedelta(days=1)
#             result = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
#             result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
#             return result
            
#         except Exception as e:
#             logger.error(f"❌ Date parse error: {e}")
#             import traceback
#             traceback.print_exc()
#             return None
    
#     async def _fallback_to_openai(
#         self,
#         user_input: str,
#         call_id: str,
#         agent_config: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """OpenAI fallback"""
#         try:
#             from app.services.ai_agent import ai_agent_service
            
#             logger.info(f"🤖 Using OpenAI")
            
#             response = await ai_agent_service._process_with_openai(
#                 user_input,
#                 call_id,
#                 agent_config
#             )
            
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": response,
#                 "node_id": "openai_fallback",
#                 "node_type": "fallback",
#                 "is_end": False
#             }
            
#         except Exception as e:
#             return {
#                 "success": True,
#                 "found_in_campaign": False,
#                 "response": "How can I help you?",
#                 "node_id": "openai_fallback",
#                 "node_type": "fallback",
#                 "is_end": False
#             }


# workflow_engine = WorkflowEngine()

# backend/app/services/workflow_engine.py - COMPLETE FILE WITH CUSTOMER INTEGRATION testing with crm 

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId

from app.database import get_database
from app.services.google_calendar import google_calendar_service
from app.services.email import email_service
# ✅ ADD: Also import email_automation_service for logging only
from app.services.email_automation import email_automation_service
# ✅ NEW: Import customer_service for automatic customer creation
from app.services.customer import customer_service

logger = logging.getLogger(__name__)

# ✅ USER TIMEZONE CONFIGURATION
USER_TIMEZONE_OFFSET = 5 


class WorkflowEngine:
    """Campaign Builder Workflow Engine"""
    
    def __init__(self):
        self.workflow_cache = {}
        self.booking_locks = set()
    
    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow"""
        try:
            db = await get_database()
            
            if isinstance(workflow_id, str):
                if not ObjectId.is_valid(workflow_id):
                    return None
                workflow_id = ObjectId(workflow_id)
            
            workflow = await db.flows.find_one({"_id": workflow_id})
            
            if workflow:
                logger.info(f"✅ Loaded workflow: {workflow.get('name')}")
            
            return workflow
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None
    
    async def find_start_node(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find start node"""
        try:
            nodes = workflow.get("nodes", [])
            if not nodes:
                return None
            
            for node in nodes:
                if node.get("type") == "begin":
                    return node
            
            for node in nodes:
                if node.get("type") in ["welcome", "message"]:
                    return node
            
            return nodes[0]
            
        except:
            return None
    
    async def process_conversation_turn(
        self,
        workflow_id: str,
        user_input: str,
        call_id: str,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main processing"""
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"🎯 Processing: '{user_input}'")
            logger.info(f"{'='*80}\n")
            
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                return await self._fallback_to_openai(user_input, call_id, agent_config)
            
            conversation_state = await self._get_conversation_state(call_id, workflow)
            
            result = await self._process_with_campaign(
                user_input, 
                conversation_state, 
                workflow,
                agent_config
            )
            
            if result.get("found_in_campaign"):
                return result
            else:
                return await self._fallback_to_openai(user_input, call_id, agent_config)
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return await self._fallback_to_openai(user_input, call_id, agent_config)
    
    async def _process_with_campaign(
        self,
        user_input: str,
        conversation_state: Dict[str, Any],
        workflow: Dict[str, Any],
        agent_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process with campaign"""
        try:
            current_node = conversation_state["current_node"]
            logger.info(f"📍 Current node: {current_node.get('id')}")
            
            previous_field = conversation_state.get("previous_field")
            
            if previous_field:
                db = await get_database()
                conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
                existing_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
                
                if not existing_data.get(previous_field):
                    logger.info(f"📥 Collecting {previous_field} from: '{user_input}'")
                    await self._collect_field_data(
                        user_input, 
                        previous_field, 
                        conversation_state["call_id"],
                        conversation_state
                    )
            
            db = await get_database()
            conversation = await db.conversations.find_one({"call_id": ObjectId(conversation_state["call_id"])})
            collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
            
            has_name = bool(collected_data.get("name"))
            has_email = bool(collected_data.get("email"))
            
            call_id = conversation_state["call_id"]
            already_booked = await self._check_appointment_exists(call_id)
            is_locked = call_id in self.booking_locks
            
            if has_name and has_email and not already_booked and not is_locked:
                logger.info(f"🎯 BOOKING APPOINTMENT NOW!")
                logger.info(f"📋 Final booking data: {collected_data}")
                
                self.booking_locks.add(call_id)
                
                try:
                    booking_result = await self._attempt_appointment_booking(
                        collected_data,
                        conversation_state["call_id"]
                    )
                    
                    if booking_result.get("success"):
                        logger.info(f"✅ BOOKING SUCCESS!")
                        return {
                            "success": True,
                            "found_in_campaign": True,
                            "response": booking_result.get("response"),
                            "node_id": "booking_confirmation",
                            "node_type": "confirmation",
                            "is_end": False
                        }
                finally:
                    self.booking_locks.discard(call_id)
            
            possible_next_nodes = await self._find_next_nodes_by_keywords(
                current_node,
                user_input,
                workflow.get("connections", []),
                workflow.get("nodes", [])
            )
            
            if possible_next_nodes:
                next_node = possible_next_nodes[0]
                
                response = await self._get_exact_node_message(next_node, conversation_state)
                
                await self._update_conversation_state(
                    conversation_state["call_id"],
                    next_node,
                    user_input,
                    response
                )
                
                return {
                    "success": True,
                    "found_in_campaign": True,
                    "response": response,
                    "node_id": next_node.get("id"),
                    "node_type": next_node.get("type"),
                    "is_end": False
                }
            else:
                logger.warning(f"⚠️ NO MATCHES FOUND")
                return {
                    "success": True,
                    "found_in_campaign": False,
                    "response": None
                }
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": True,
                "found_in_campaign": False,
                "response": None
            }
    
    async def _check_appointment_exists(self, call_id: str) -> bool:
        """Check if appointment exists"""
        try:
            db = await get_database()
            appointment = await db.appointments.find_one({"call_id": ObjectId(call_id)})
            return bool(appointment)
        except:
            return False
    
    async def _find_next_nodes_by_keywords(
        self,
        current_node: Dict[str, Any],
        user_input: str,
        connections: List[Dict[str, Any]],
        all_nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find next nodes"""
        try:
            user_input_lower = user_input.lower().strip()
            possible_matches = []
            
            outgoing_connections = [
                conn for conn in connections 
                if conn.get("from") == current_node.get("id")
            ]
            
            for connection in outgoing_connections:
                keywords = connection.get("keywords", [])
                
                if not keywords:
                    target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
                    if target_node:
                        possible_matches.append(target_node)
                    continue
                
                for keyword in keywords:
                    if keyword and keyword.lower() in user_input_lower:
                        target_node = next((n for n in all_nodes if n.get("id") == connection.get("to")), None)
                        if target_node:
                            possible_matches.append(target_node)
                            break
            
            if not possible_matches:
                is_collecting = await self._is_data_collection_node(current_node)
                
                if is_collecting and outgoing_connections:
                    target_node = next((n for n in all_nodes if n.get("id") == outgoing_connections[0].get("to")), None)
                    if target_node:
                        possible_matches.append(target_node)
            
            return possible_matches
            
        except:
            return []
    
    async def _is_data_collection_node(self, node: Dict[str, Any]) -> bool:
        """Check if node collects data"""
        node_data = node.get("data", {})
        message = node_data.get("message", "").lower()
        indicators = ["name", "email", "phone", "service", "date", "time"]
        return any(ind in message for ind in indicators)
    
    async def _get_conversation_state(
        self,
        call_id: str,
        workflow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get conversation state"""
        try:
            db = await get_database()
            conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
            if not conversation:
                start_node = await self.find_start_node(workflow)
                return {
                    "call_id": call_id,
                    "workflow_id": str(workflow["_id"]),
                    "current_node": start_node or workflow["nodes"][0],
                    "collected_data": {},
                    "conversation_history": [],
                    "previous_field": None
                }
            
            messages = conversation.get("messages", [])
            current_node = None
            previous_field = None
            
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    metadata = msg.get("metadata", {})
                    node_id = metadata.get("node_id")
                    previous_field = metadata.get("collecting_field")
                    
                    if node_id:
                        current_node = next(
                            (n for n in workflow["nodes"] if n.get("id") == node_id),
                            None
                        )
                        break
            
            if not current_node:
                current_node = await self.find_start_node(workflow)
            
            collected_data = conversation.get("metadata", {}).get("appointment_data", {})
            
            return {
                "call_id": call_id,
                "workflow_id": str(workflow["_id"]),
                "current_node": current_node,
                "collected_data": collected_data,
                "conversation_history": messages,
                "previous_field": previous_field
            }
            
        except Exception as e:
            start_node = await self.find_start_node(workflow)
            return {
                "call_id": call_id,
                "workflow_id": str(workflow["_id"]),
                "current_node": start_node or workflow["nodes"][0],
                "collected_data": {},
                "conversation_history": [],
                "previous_field": None
            }
    
    async def _update_conversation_state(
        self,
        call_id: str,
        new_node: Dict[str, Any],
        user_input: str,
        response: str
    ):
        """Update conversation state"""
        try:
            db = await get_database()
            conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            
            if not conversation:
                return
            
            collecting_field = await self._detect_collecting_field(new_node)
            
            metadata = {
                "workflow_id": str(conversation.get("metadata", {}).get("workflow_id")),
                "node_id": new_node.get("id"),
                "node_type": new_node.get("type"),
                "collecting_field": collecting_field
            }
            
            await db.conversations.update_one(
                {"_id": conversation["_id"]},
                {
                    "$push": {
                        "messages": {
                            "$each": [
                                {
                                    "role": "user",
                                    "content": user_input,
                                    "timestamp": datetime.utcnow(),
                                    "metadata": metadata
                                },
                                {
                                    "role": "assistant",
                                    "content": response,
                                    "timestamp": datetime.utcnow(),
                                    "metadata": metadata
                                }
                            ]
                        }
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
        except:
            pass
    
    async def _detect_collecting_field(self, node: Dict[str, Any]) -> Optional[str]:
        """Detect field"""
        node_data = node.get("data", {})
        message = node_data.get("message", "").lower()
        
        patterns = {
            "name": ["name", "called"],
            "email": ["email", "e-mail"],
            "phone": ["phone", "number"],
            "service": ["service", "help"],
            "date": ["date", "when", "schedule"]
        }
        
        for field, keywords in patterns.items():
            if any(kw in message for kw in keywords):
                return field
        
        return None
    
    async def _get_exact_node_message(
        self,
        node: Dict[str, Any],
        conversation_state: Dict[str, Any]
    ) -> str:
        """Get node message"""
        try:
            node_data = node.get("data", {})
            message = node_data.get("message", "")
            
            collected_data = conversation_state.get("collected_data", {})
            
            if "{name}" in message and collected_data.get("name"):
                message = message.replace("{name}", collected_data["name"])
            if "{date}" in message and collected_data.get("date"):
                message = message.replace("{date}", collected_data["date"])
            
            if not message:
                message = "How can I help you?"
            
            return message
            
        except:
            return "How can I help you?"
    
    async def _collect_field_data(
        self,
        user_input: str,
        field_type: str,
        call_id: str,
        conversation_state: Dict[str, Any]
    ):
        """Collect field data"""
        try:
            logger.info(f"📥 Extracting {field_type} from: '{user_input}'")
            
            extracted_value = await self._extract_field_value(user_input, field_type)
            
            if extracted_value:
                logger.info(f"✅ Collected {field_type}: {extracted_value}")
                
                db = await get_database()
                
                update_result = await db.conversations.update_one(
                    {"call_id": ObjectId(call_id)},
                    {
                        "$set": {
                            f"metadata.appointment_data.{field_type}": extracted_value,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                logger.info(f"💾 Saved {field_type} to database (modified: {update_result.modified_count})")
                
                verification = await db.conversations.find_one({"call_id": ObjectId(call_id)})
                saved_value = verification.get("metadata", {}).get("appointment_data", {}).get(field_type)
                logger.info(f"🔍 Verification - {field_type} in DB: {saved_value}")
                
                conversation_state["collected_data"][field_type] = extracted_value
            else:
                logger.warning(f"⚠️ Failed to extract {field_type}")
            
        except Exception as e:
            logger.error(f"❌ Error collecting {field_type}: {e}")
            import traceback
            traceback.print_exc()
    
    async def _extract_field_value(self, user_input: str, field_type: str) -> Optional[str]:
        """Extract field value"""
        try:
            if field_type == "email":
                logger.info(f"📧 Extracting email from: '{user_input}'")
                
                user_input_lower = user_input.lower().strip()
                
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                match = re.search(email_pattern, user_input_lower, re.IGNORECASE)
                if match:
                    email = match.group(0)
                    logger.info(f"✅ Extracted (standard): {email}")
                    return email
                
                domain_map = {
                    'gmail': 'gmail.com',
                    'g mail': 'gmail.com',
                    'gb': 'gmail.com',
                    'gee mail': 'gmail.com',
                    'hotmail': 'hotmail.com',
                    'yahoo': 'yahoo.com',
                    'outlook': 'outlook.com',
                }
                
                domain = None
                for provider, full_domain in domain_map.items():
                    if provider in user_input_lower:
                        domain = full_domain
                        logger.info(f"✅ Found domain: {domain}")
                        break
                
                if not domain:
                    logger.warning(f"⚠️ No domain found, using default")
                    domain = "gmail.com"
                    logger.info(f"✅ Using default: {domain}")
                
                filler_words = {
                    'okay', 'ok', 'my', 'email', 'is', 'the', 'a', 'an', 'uh', 'um',
                    'at', 'dot', 'com', 'gmail', 'hotmail', 'rate', 'red', 'gb',
                    'thank', 'you', 'thanks', 'please', 'and', 'or', 'listen', 'carefully'
                }
                
                words = re.split(r'[\s,.\?!]+', user_input_lower)
                
                letters = []
                for word in words:
                    if word in filler_words:
                        continue
                    cleaned = re.sub(r'[^a-z0-9]', '', word)
                    if cleaned and len(cleaned) <= 10:
                        letters.append(cleaned)
                
                username = ''.join(letters)
                
                if username:
                    email = f"{username}@{domain}"
                    logger.info(f"✅ CONSTRUCTED: {email}")
                    return email
                
                logger.warning(f"⚠️ Could not construct email")
                return None
            
            elif field_type == "phone":
                match = re.search(r'[\d\s\-\(\)\.]+\d{3,}', user_input)
                if match:
                    digits = re.sub(r'\D', '', match.group(0))
                    if len(digits) >= 10:
                        return digits
                return None
            
            elif field_type in ["name", "service"]:
                cleaned = user_input.strip()
                prefixes = ["my name is", "i am", "i'm", "i want", "book", "to book"]
                
                for prefix in prefixes:
                    if cleaned.lower().startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                
                cleaned = cleaned.rstrip('.').rstrip(',')
                
                if len(cleaned) > 1 and len(cleaned) < 50:
                    return cleaned.title() if field_type == "name" else cleaned
                
                return None
            
            elif field_type == "date":
                date_value = user_input.strip()
                logger.info(f"📅 Date field collected: '{date_value}'")
                return date_value
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting {field_type}: {e}")
            return None
    
    async def _attempt_appointment_booking(
        self,
        collected_data: Dict[str, Any],
        call_id: str
    ) -> Dict[str, Any]:
        """Book appointment with email logging and automatic customer creation"""
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"📅 BOOKING APPOINTMENT")
            logger.info(f"📋 Collected Data from parameter: {collected_data}")
            logger.info(f"{'='*80}\n")
            
            db = await get_database()
            conversation = await db.conversations.find_one({"call_id": ObjectId(call_id)})
            fresh_collected_data = conversation.get("metadata", {}).get("appointment_data", {}) if conversation else {}
            
            logger.info(f"📋 Fresh data from database: {fresh_collected_data}")
            
            collected_data = fresh_collected_data
            
            required = ["name", "email"]
            missing = [f for f in required if not collected_data.get(f)]
            
            if missing:
                logger.error(f"❌ Missing: {missing}")
                return {
                    "success": False,
                    "error": f"Missing: {', '.join(missing)}"
                }
            
            appointment_date = None
            if collected_data.get("date"):
                logger.info(f"📅 Parsing date from collected data: '{collected_data.get('date')}'")
                appointment_date = await self._parse_date(collected_data["date"])
            
            if not appointment_date:
                logger.warning(f"⚠️ No valid date, using tomorrow")
                appointment_date = datetime.utcnow() + timedelta(days=1)
                appointment_date = appointment_date.replace(hour=10, minute=0, second=0, microsecond=0)
            
            logger.info(f"✅ Final appointment date (UTC): {appointment_date}")
            
            appointment_time = appointment_date.strftime("%H:%M")
            
            customer_name = collected_data.get("name", "Customer")
            customer_email = collected_data.get("email", "")
            customer_phone = collected_data.get("phone", "")
            service_type = collected_data.get("service", "House Painting")
            
            # ✅ Calculate local time for display (GMT+5)
            local_datetime = appointment_date + timedelta(hours=USER_TIMEZONE_OFFSET)
            
            logger.info(f"📋 Final booking details:")
            logger.info(f"   Name: {customer_name}")
            logger.info(f"   Email: {customer_email}")
            logger.info(f"   Phone: {customer_phone}")
            logger.info(f"   Service: {service_type}")
            logger.info(f"   Date (UTC): {appointment_date}")
            logger.info(f"   Date (GMT+{USER_TIMEZONE_OFFSET}): {local_datetime}")
            logger.info(f"   Time: {appointment_time}")
            
            # Get user_id from call record for email logging
            call_record = await db.calls.find_one({"_id": ObjectId(call_id)})
            user_id = str(call_record.get("user_id")) if call_record else None
            
            # ✅ NEW: Find or create customer automatically
            customer_id = None
            if user_id:
                try:
                    logger.info(f"👤 Checking if customer exists...")
                    
                    customer_result = await customer_service.find_or_create_customer(
                        user_id=user_id,
                        name=customer_name,
                        email=customer_email,
                        phone=customer_phone
                    )
                    
                    if customer_result.get("success"):
                        customer_id = customer_result["customer"]["id"]
                        
                        if customer_result.get("created"):
                            logger.info(f"✅ NEW customer created: {customer_id}")
                        else:
                            logger.info(f"✅ EXISTING customer found: {customer_id}")
                        
                        # Update customer's appointment count
                        await db.customers.update_one(
                            {"_id": ObjectId(customer_id)},
                            {
                                "$inc": {"total_appointments": 1},
                                "$set": {"last_contact_at": datetime.utcnow()}
                            }
                        )
                        logger.info(f"✅ Customer appointment count updated")
                    else:
                        logger.warning(f"⚠️ Customer creation failed: {customer_result.get('error')}")
                        
                except Exception as customer_error:
                    logger.warning(f"⚠️ Customer service error: {customer_error}")
                    # Don't fail booking if customer creation fails
            
            calendar_event = None
            try:
                logger.info("📆 Creating Google Calendar event...")
                
                calendar_result = await google_calendar_service.create_event(
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    duration_minutes=60,
                    service_type=service_type,
                    notes=None
                )
                
                if calendar_result.get("success"):
                    calendar_event = calendar_result
                    logger.info(f"✅ Calendar event created!")
                    logger.info(f"   Event ID: {calendar_result.get('event_id')}")
                else:
                    logger.warning(f"⚠️ Calendar failed: {calendar_result.get('error')}")
                    
            except Exception as e:
                logger.error(f"⚠️ Calendar error: {e}")
                import traceback
                traceback.print_exc()
            
            appointment_data = {
                "call_id": ObjectId(call_id),
                "customer_id": ObjectId(customer_id) if customer_id else None,  # ✅ NEW: Link to customer
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "service": service_type,
                "appointment_date": appointment_date,
                "status": "confirmed",
                "google_calendar_event_id": calendar_event.get("event_id") if calendar_event else None,
                "google_calendar_link": calendar_event.get("html_link") if calendar_event else None,
                "user_id": user_id,  # ✅ NEW: Add user_id for filtering
                "created_at": datetime.utcnow()
            }
            
            result = await db.appointments.insert_one(appointment_data)
            appointment_id = str(result.inserted_id)
            
            logger.info(f"✅ Appointment saved: {appointment_id}")
            
            # ✅ UPDATED EMAIL SENDING WITH LOGGING
            try:
                logger.info(f"📧 Sending email to {customer_email}...")
                
                date_str = local_datetime.strftime("%A, %B %d, %Y")
                time_str = local_datetime.strftime("%I:%M %p")
                
                # First send the email using the original email service (keeps existing functionality)
                await email_service.send_appointment_confirmation(
                    to_email=customer_email,
                    customer_name=customer_name,
                    appointment_date=date_str,
                    appointment_time=time_str,
                    service_type=service_type
                )
                
                logger.info(f"✅ Email sent successfully!")
                
                # ✅ NEW: Also log it to email_logs for frontend visibility
                try:
                    formatted_appointment_date = f"{date_str} at {time_str}"
                    await email_automation_service.log_appointment_email(
                        to_email=customer_email,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        service_type=service_type,
                        appointment_date=formatted_appointment_date,
                        user_id=user_id,
                        appointment_id=appointment_id,
                        call_id=call_id
                    )
                    logger.info(f"✅ Email logged to email_logs collection!")
                except Exception as log_error:
                    logger.warning(f"⚠️ Failed to log email: {log_error}")
                    # Don't fail the booking if logging fails
                
            except Exception as e:
                logger.error(f"⚠️ Email error: {e}")
                import traceback
                traceback.print_exc()
            
            date_str = local_datetime.strftime("%A, %B %d at %I:%M %p")
            
            response = f"Perfect! Your appointment for {service_type} is confirmed for {date_str}. A confirmation email has been sent to {customer_email}. Is there anything else I can help you with?"
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ BOOKING COMPLETE!")
            logger.info(f"   Appointment ID: {appointment_id}")
            logger.info(f"   Customer ID: {customer_id if customer_id else 'N/A'}")
            logger.info(f"   Google Event: {calendar_event.get('event_id') if calendar_event else 'N/A'}")
            logger.info(f"   Email: Sent to {customer_email}")
            logger.info(f"{'='*80}\n")
            
            return {
                "success": True,
                "response": response,
                "appointment_id": appointment_id,
                "customer_id": customer_id
            }
            
        except Exception as e:
            logger.error(f"❌ Booking error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "response": "I apologize, there was an issue booking your appointment."
            }
    
    async def _parse_date(self, date_string: str) -> Optional[datetime]:
        """✅ COMPLETE FIX: Parse date with GMT+5 to UTC conversion"""
        try:
            date_str = date_string.lower().strip()
            now = datetime.utcnow()
            
            logger.info(f"📅 Parsing date string: '{date_str}'")
            logger.info(f"🌍 User timezone: GMT+{USER_TIMEZONE_OFFSET}")
            
            # Enhanced time pattern to handle "10:00 a.m." format
            time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)'
            
            # Common day names
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            # Check for day names with optional time
            for day_name in days:
                if day_name in date_str:
                    logger.info(f"✅ Found day: {day_name}")
                    
                    # Calculate days until next occurrence
                    today_weekday = now.weekday()
                    target_weekday = days.index(day_name)
                    
                    days_ahead = target_weekday - today_weekday
                    if days_ahead <= 0:
                        days_ahead += 7
                    
                    result = now + timedelta(days=days_ahead)
                    
                    # Check for time in the input
                    time_match = re.search(time_pattern, date_str, re.IGNORECASE)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2) or 0)
                        am_pm = time_match.group(3).replace('.', '').lower()
                        
                        if am_pm == 'pm' and hour != 12:
                            hour += 12
                        elif am_pm == 'am' and hour == 12:
                            hour = 0
                    else:
                        # Default to 10:00 AM if no time specified
                        hour = 10
                        minute = 0
                    
                    result = result.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # ✅ CRITICAL: Convert GMT+5 to UTC
                    result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
                    
                    logger.info(f"✅ Parsed '{day_name}' at {hour}:{minute:02d} GMT+{USER_TIMEZONE_OFFSET}")
                    logger.info(f"✅ Converted to UTC: {result}")
                    return result
            
            logger.warning(f"⚠️ Could not parse date: {date_str}, using tomorrow at 10:00 AM")
            tomorrow = datetime.utcnow() + timedelta(days=1)
            result = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
            result = result - timedelta(hours=USER_TIMEZONE_OFFSET)
            return result
            
        except Exception as e:
            logger.error(f"❌ Date parse error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _fallback_to_openai(
        self,
        user_input: str,
        call_id: str,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """OpenAI fallback"""
        try:
            from app.services.ai_agent import ai_agent_service
            
            logger.info(f"🤖 Using OpenAI")
            
            response = await ai_agent_service._process_with_openai(
                user_input,
                call_id,
                agent_config
            )
            
            return {
                "success": True,
                "found_in_campaign": False,
                "response": response,
                "node_id": "openai_fallback",
                "node_type": "fallback",
                "is_end": False
            }
            
        except Exception as e:
            return {
                "success": True,
                "found_in_campaign": False,
                "response": "How can I help you?",
                "node_id": "openai_fallback",
                "node_type": "fallback",
                "is_end": False
            }


workflow_engine = WorkflowEngine()