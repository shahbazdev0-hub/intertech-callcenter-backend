"""
✅ NEW: Per-Call Conversational Memory System

Maintains conversation context per CallSid:
- Last 4 turns of conversation (user + assistant)
- Running summary of what happened
- Call stage tracking (opener → qualification → value → CTA)
- Prevents re-introductions
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

logger = logging.getLogger(__name__)


# ============================================
# CALL STAGES
# ============================================
CALL_STAGES = {
    "opener": {
        "name": "opener",
        "description": "Initial greeting, customer just answered",
        "next_stage": "qualification",
        "triggers": ["hello", "hi", "yes", "speaking", "this is"]
    },
    "qualification": {
        "name": "qualification", 
        "description": "Understanding customer needs and interest",
        "next_stage": "value",
        "triggers": ["interested", "tell me more", "what do you", "how does", "price", "cost", "services"]
    },
    "value": {
        "name": "value",
        "description": "Presenting value proposition and benefits",
        "next_stage": "cta",
        "triggers": ["sounds good", "okay", "that's interesting", "benefits", "how can you help"]
    },
    "cta": {
        "name": "cta",
        "description": "Call to action - booking, scheduling, closing",
        "next_stage": "cta",
        "triggers": ["yes", "sure", "let's do it", "schedule", "book", "sign up", "appointment"]
    }
}


class CallMemoryService:
    """
    Per-call memory management for voice agents.
    
    Stores:
    - Conversation history (last 4 turns)
    - Running summary
    - Call stage
    - Introduction flag
    """
    
    def __init__(self):
        # In-memory cache for active calls (faster than DB for every turn)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        logger.info("✅ CallMemoryService initialized")
    
    
    def _get_empty_memory(self, call_sid: str) -> Dict[str, Any]:
        """Create empty memory structure for a new call"""
        return {
            "call_sid": call_sid,
            "history": [],  # List of {"role": "user/assistant", "content": "..."}
            "summary": "",  # Running summary of conversation
            "stage": "opener",  # Current call stage
            "has_introduced": False,  # Track if agent introduced itself
            "turn_count": 0,
            "customer_name": None,
            "customer_interests": [],
            "objections": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    
    async def get_memory(self, call_sid: str, db: AsyncIOMotorDatabase = None) -> Dict[str, Any]:
        """
        Get conversation memory for a call.
        First checks cache, then DB, creates new if not found.
        """
        # Check cache first (fastest)
        if call_sid in self._memory_cache:
            logger.info(f"📝 Memory found in cache for {call_sid}")
            return self._memory_cache[call_sid]
        
        # Check database
        if db is not None:
            memory_doc = await db.call_memories.find_one({"call_sid": call_sid})
            if memory_doc:
                logger.info(f"📝 Memory found in DB for {call_sid}")
                self._memory_cache[call_sid] = memory_doc
                return memory_doc
        
        # Create new memory
        logger.info(f"📝 Creating new memory for {call_sid}")
        new_memory = self._get_empty_memory(call_sid)
        self._memory_cache[call_sid] = new_memory
        
        # Save to DB async
        if db is not None:
            await db.call_memories.insert_one(new_memory.copy())
        
        return new_memory
    
    
    async def add_turn(
        self,
        call_sid: str,
        user_message: str,
        assistant_message: str,
        db: AsyncIOMotorDatabase = None
    ) -> Dict[str, Any]:
        """
        Add a conversation turn (user + assistant messages).
        Keeps only last 4 turns (8 messages total).
        """
        memory = await self.get_memory(call_sid, db)
        
        # Add new messages
        memory["history"].append({"role": "user", "content": user_message})
        memory["history"].append({"role": "assistant", "content": assistant_message})
        
        # Keep only last 4 turns (8 messages)
        if len(memory["history"]) > 8:
            memory["history"] = memory["history"][-8:]
        
        # Update turn count
        memory["turn_count"] += 1
        memory["updated_at"] = datetime.utcnow()
        
        # Mark as introduced after first turn
        if memory["turn_count"] == 1:
            memory["has_introduced"] = True
        
        # Detect and update stage
        new_stage = self._detect_stage_transition(user_message, memory["stage"])
        if new_stage != memory["stage"]:
            logger.info(f"📈 Stage transition: {memory['stage']} → {new_stage}")
            memory["stage"] = new_stage
        
        # Extract customer info from user message
        self._extract_customer_info(user_message, memory)
        
        # Update summary every 2 turns
        if memory["turn_count"] % 2 == 0:
            memory["summary"] = self._generate_summary(memory)
        
        # Update cache
        self._memory_cache[call_sid] = memory
        
        # Persist to DB
        if db is not None:
            await db.call_memories.update_one(
                {"call_sid": call_sid},
                {"$set": memory},
                upsert=True
            )
        
        logger.info(f"✅ Turn added. Total turns: {memory['turn_count']}, Stage: {memory['stage']}")
        return memory
    
    
    def _detect_stage_transition(self, user_input: str, current_stage: str) -> str:
        """Detect if we should advance to the next stage based on user input"""
        user_lower = user_input.lower()
        
        # Get current stage info
        stage_info = CALL_STAGES.get(current_stage, CALL_STAGES["opener"])
        next_stage = stage_info.get("next_stage", current_stage)
        
        # Check triggers for next stage
        next_stage_info = CALL_STAGES.get(next_stage, {})
        triggers = next_stage_info.get("triggers", [])
        
        for trigger in triggers:
            if trigger in user_lower:
                return next_stage
        
        # Check if user shows clear buying signals (jump to CTA)
        cta_signals = ["yes", "sure", "definitely", "let's do it", "sign me up", "book", "schedule"]
        if any(signal in user_lower for signal in cta_signals):
            return "cta"
        
        # Check for objections (stay in current stage)
        objection_signals = ["not interested", "no thanks", "too expensive", "maybe later"]
        if any(signal in user_lower for signal in objection_signals):
            return current_stage
        
        return current_stage
    
    
    def _extract_customer_info(self, user_input: str, memory: Dict[str, Any]):
        """Extract useful customer info from their messages"""
        user_lower = user_input.lower()
        
        # Extract name if mentioned
        name_patterns = ["my name is", "this is", "i'm", "i am"]
        for pattern in name_patterns:
            if pattern in user_lower:
                # Simple extraction - get words after pattern
                idx = user_lower.find(pattern)
                after = user_input[idx + len(pattern):].strip()
                words = after.split()
                if words:
                    potential_name = words[0].strip(".,!?")
                    if len(potential_name) > 1 and potential_name.isalpha():
                        memory["customer_name"] = potential_name.title()
                        logger.info(f"👤 Extracted customer name: {memory['customer_name']}")
                        break
        
        # Extract interests
        interest_keywords = ["interested in", "looking for", "need", "want", "considering"]
        for keyword in interest_keywords:
            if keyword in user_lower:
                memory["customer_interests"].append(user_input)
                break
        
        # Track objections
        objection_keywords = ["expensive", "cost", "price", "not sure", "maybe", "think about"]
        for keyword in objection_keywords:
            if keyword in user_lower:
                memory["objections"].append(user_input)
                break
    
    
    def _generate_summary(self, memory: Dict[str, Any]) -> str:
        """Generate a brief summary of the conversation so far"""
        turns = memory["turn_count"]
        stage = memory["stage"]
        name = memory.get("customer_name", "Unknown")
        
        summary_parts = [
            f"Turn {turns}.",
            f"Stage: {stage}.",
        ]
        
        if name != "Unknown":
            summary_parts.append(f"Customer: {name}.")
        
        if memory["customer_interests"]:
            summary_parts.append(f"Interested in: {memory['customer_interests'][-1][:50]}...")
        
        if memory["objections"]:
            summary_parts.append(f"Objection raised: {memory['objections'][-1][:50]}...")
        
        return " ".join(summary_parts)
    
    
    def build_context_messages(
        self,
        memory: Dict[str, Any],
        system_prompt: str,
        current_user_input: str
    ) -> List[Dict[str, str]]:
        """
        ✅ CRITICAL: Build the full message array for LLM request.
        
        Structure:
        1. System prompt (with stage rules and no-reintro rule)
        2. Summary of conversation (if exists)
        3. Recent history (last 4 turns)
        4. Current user input
        """
        messages = []
        
        # ============================================
        # 1. SYSTEM PROMPT WITH STAGE + NO-REINTRO RULES
        # ============================================
        stage = memory.get("stage", "opener")
        stage_info = CALL_STAGES.get(stage, CALL_STAGES["opener"])
        has_introduced = memory.get("has_introduced", False)
        turn_count = memory.get("turn_count", 0)
        
        # Build enhanced system prompt
        enhanced_prompt = f"""{system_prompt}

═══════════════════════════════════════════════════════════════════
🎯 CURRENT CALL CONTEXT (CRITICAL - FOLLOW EXACTLY):
═══════════════════════════════════════════════════════════════════

📍 CALL STAGE: {stage.upper()} - {stage_info['description']}
📊 TURN NUMBER: {turn_count + 1}
"""
        
        # Add no-reintro rule after first turn
        if has_introduced or turn_count > 0:
            enhanced_prompt += """
⚠️ CRITICAL RULE - NO RE-INTRODUCTION:
You have ALREADY introduced yourself. Do NOT repeat your name, company name, 
or greeting. Do NOT say "Hi, I'm..." or "This is..." again.
Just continue the conversation naturally from where we left off.
"""
        
        # Add stage-specific instructions
        if stage == "opener":
            enhanced_prompt += """
📋 OPENER STAGE GOALS:
- Confirm you're speaking with the right person
- Build rapport quickly
- Transition to understanding their needs
"""
        elif stage == "qualification":
            enhanced_prompt += """
📋 QUALIFICATION STAGE GOALS:
- Understand their current situation
- Identify pain points and needs
- Ask discovery questions
"""
        elif stage == "value":
            enhanced_prompt += """
📋 VALUE STAGE GOALS:
- Present relevant benefits for their needs
- Share success stories/results
- Address any concerns proactively
"""
        elif stage == "cta":
            enhanced_prompt += """
📋 CTA STAGE GOALS:
- Move toward concrete next step
- Book appointment or schedule follow-up
- Get commitment or clear timeline
"""
        
        enhanced_prompt += """
═══════════════════════════════════════════════════════════════════
"""
        
        messages.append({"role": "system", "content": enhanced_prompt})
        
        # ============================================
        # 2. CONVERSATION SUMMARY (if exists)
        # ============================================
        if memory.get("summary"):
            messages.append({
                "role": "system",
                "content": f"[CONVERSATION SUMMARY: {memory['summary']}]"
            })
        
        # ============================================
        # 3. RECENT CONVERSATION HISTORY
        # ============================================
        history = memory.get("history", [])
        max_history_turns = 3  # ✅ OPTIMIZATION: Limit to last 3 turns
        
        # Only include recent history
        recent_history = history[-max_history_turns*2:] if len(history) > max_history_turns*2 else history
        
        print(f"⏱️  [CONTEXT] Sending {len(recent_history)} messages (limited from {len(history)} total)")
        
        for msg in recent_history:
            messages.append(msg)
        
        # ============================================
        # 4. CURRENT USER INPUT
        # ============================================
        messages.append({"role": "user", "content": current_user_input})
        
        logger.info(f"📨 Built context with {len(messages)} messages (history: {len(history)})")
        
        return messages
    
    
    async def clear_memory(self, call_sid: str, db: AsyncIOMotorDatabase = None):
        """Clear memory for a completed call"""
        if call_sid in self._memory_cache:
            del self._memory_cache[call_sid]
        
        if db is not None:
            await db.call_memories.delete_one({"call_sid": call_sid})
        
        logger.info(f"🗑️ Memory cleared for {call_sid}")
    
    
    async def get_call_stage(self, call_sid: str, db = None) -> str:
        """Get current stage for a call"""
        memory = await self.get_memory(call_sid, db)
        return memory.get("stage", "opener")
    
    
    async def has_introduced(self, call_sid: str, db = None) -> bool:
        """Check if agent has already introduced itself"""
        memory = await self.get_memory(call_sid, db)
        return memory.get("has_introduced", False) or memory.get("turn_count", 0) > 0


# Create singleton instance
call_memory_service = CallMemoryService()