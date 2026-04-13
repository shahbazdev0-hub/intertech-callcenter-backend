#app/services/openai.py 

# ✅ ENHANCED: Sales-focused system prompt generation
# ✅ ENHANCED: Supports both OpenAI and Groq (FASTER)

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
import json

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    AI Service for responses
    ✅ ENHANCED: Supports both OpenAI and Groq (faster)
    """
    
    def __init__(self):
        # ✅ Check if we should use Groq (faster)
        use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        groq_api_key = os.getenv("GROQ_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if use_groq and groq_api_key:
            # ✅ Use Groq for faster responses
            self.client = AsyncOpenAI(
                api_key=groq_api_key,
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                timeout=3.0,  # Faster timeout for Groq
                max_retries=1
            )
            self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.configured = True
            self.provider = "groq"
            logger.info(f"✅ Groq service initialized with model: {self.model}")
        elif openai_api_key:
            # Fallback to OpenAI
            self.client = AsyncOpenAI(
                api_key=openai_api_key,
                timeout=5.0,
                max_retries=1
            )
            self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            self.configured = True
            self.provider = "openai"
            logger.info(f"✅ OpenAI service initialized with model: {self.model}")
        else:
            self.client = None
            self.configured = False
            self.provider = None
            logger.warning("⚠️ No AI API key configured (OpenAI or Groq)")
        
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", 80))
    
    
    async def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        call_id: str = None,
        max_tokens: int = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate AI response - OPTIMIZED FOR SPEED with Groq"""
        try:
            if not self.configured or not self.client:
                logger.warning(f"⚠️ AI service not configured")
                return {
                    "success": False,
                    "error": "AI service not configured"
                }
            
            # Truncate system prompt if too long
            if len(system_prompt) > 1500:
                system_prompt = system_prompt[:1500] + "..."
            
            logger.info(f"🤖 Generating response with {self.provider} ({self.model})...")

            # ✅ Groq has faster response times
            timeout_seconds = 3.0 if self.provider == "groq" else 4.0
            
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    max_tokens=max_tokens or 80,
                    temperature=temperature
                ),
                timeout=timeout_seconds
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            logger.info(f"✅ {self.provider} response received ({len(ai_response)} chars)")
            
            return {
                "success": True,
                "response": ai_response,
                "provider": self.provider
            }
            
        except asyncio.TimeoutError:
            logger.error(f"❌ {self.provider} timeout after {timeout_seconds}s")
            return {
                "success": False,
                "error": f"{self.provider} timeout"
            }
        except Exception as e:
            logger.error(f"❌ {self.provider} error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        max_tokens: int = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        ✅ NEW: Generate response with full conversation history.
        Used for contextual voice conversations.
        
        Args:
            messages: Full message array [{"role": "...", "content": "..."}]
            system_prompt: Optional system prompt to prepend
            max_tokens: Max response tokens
            temperature: Response randomness
        """
        try:
            if not self.configured or not self.client:
                logger.warning(f"⚠️ AI service not configured")
                return {"success": False, "error": "AI service not configured"}
            
            # Build final messages
            final_messages = []
            
            # Add system prompt if provided and not already in messages
            if system_prompt and (not messages or messages[0].get("role") != "system"):
                final_messages.append({"role": "system", "content": system_prompt})
            
            # Add all provided messages
            final_messages.extend(messages)
            
            print(f"🤖 Generating chat response with {self.provider} ({self.model})")
            logger.info(f"📨 Total messages: {len(final_messages)}")
            
            # Faster timeout for voice calls
            timeout_seconds = 3.0 if self.provider == "xai_grok" else 4.0
            
            import time
            groq_start = time.time()
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=final_messages,
                    max_tokens=max_tokens or self.max_tokens,
                    temperature=temperature
                ),
                timeout=timeout_seconds
            )
            groq_time = (time.time() - groq_start) * 1000
            print(f"⏱️  [GROQ-ACTUAL] API call took: {groq_time:.2f}ms")
            
            ai_response = response.choices[0].message.content.strip()
            
            logger.info(f"✅ {self.provider} response: {ai_response[:100]}...")
            
            return {
                "success": True,
                "response": ai_response,
                "provider": self.provider
            }
            
        except asyncio.TimeoutError:
            logger.error(f"❌ {self.provider} timeout")
            return {"success": False, "error": "timeout"}
        except Exception as e:
            logger.error(f"❌ {self.provider} error: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def generate_chat_response_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        max_tokens: int = None,
        temperature: float = 0.7
    ):
        """
        🚀 NEW: Stream chat response token by token
        Yields tokens as they arrive from Groq for real-time processing
        """
        try:
            if not self.configured or not self.client:
                logger.warning(f"⚠️ AI service not configured")
                yield {"error": "AI service not configured"}
                return
            
            # Build final messages
            final_messages = []
            
            # Add system prompt if provided
            if system_prompt and (not messages or messages[0].get("role") != "system"):
                final_messages.append({"role": "system", "content": system_prompt})
            
            # Add all provided messages
            final_messages.extend(messages)
            
            print(f"🚀 STREAMING chat response with {self.provider} ({self.model})")
            
            import time
            stream_start = time.time()
            first_token_time = None
            token_count = 0
            
            # Create streaming request
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=final_messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature,
                stream=True  # ✅ ENABLE STREAMING
            )
            
            # Stream tokens as they arrive
            async for chunk in stream:
                if not first_token_time:
                    first_token_time = time.time()
                    print(f"⏱️  [GROQ-STREAM] First token: {(first_token_time - stream_start) * 1000:.2f}ms")
                
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    token_count += 1
                    yield {"token": token, "done": False}
            
            total_time = (time.time() - stream_start) * 1000
            print(f"⏱️  [GROQ-STREAM] Complete: {total_time:.2f}ms ({token_count} tokens)")
            
            yield {"done": True}
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            yield {"error": str(e)}
    
    def build_contextual_system_prompt(
        self,
        agent_context: Dict[str, Any],
        agent_name: str = "AI Assistant",
        ai_script: str = "",
        language: str = "en",
        language_name: str = "English"
    ) -> str:
        """
        ✅ ENHANCED: Build system prompt from agent context
        ✅ MULTILINGUAL: Adds language instruction when non-English detected

        For INBOUND calls: Uses the user-provided inbound script + business info
        For OUTBOUND calls: Uses the sales-focused prompt with agent context + raw script
        """

        # CHECK FOR INBOUND — use the inbound page script/instructions
        inbound_script = agent_context.get("inbound_script")
        if inbound_script:
            logger.info(f"📞 [PROMPT] Using INBOUND prompt path (Inbound Page config)")
            business_info = agent_context.get("business_info", "")

            # Build the script section from inbound config
            script_section = ""
            if inbound_script and inbound_script.strip():
                script_section = f"""
═══════════════════════════════════════════════════════════════
📜 YOUR INBOUND CALL SCRIPT & INSTRUCTIONS (FOLLOW THIS)
═══════════════════════════════════════════════════════════════

{inbound_script}

═══════════════════════════════════════════════════════════════
"""

            # Optional business info from inbound config
            business_section = ""
            if business_info:
                business_section = f"""

ADDITIONAL BUSINESS CONTEXT:
{business_info}
"""

            prompt = f"""You are a professional customer service AI assistant.
This is a LIVE INBOUND PHONE CALL — a customer called YOU.
{script_section}{business_section}
RULES:
1. Follow the script and instructions above closely.
2. NEVER invent or make up prices, services, or information not provided in your instructions.
3. If a customer asks about something NOT covered, say: "I don't have that specific information right now, but I can have someone from our team get back to you on that."
4. Keep responses under 2-3 sentences (this is a phone call, not text).
5. Sound natural, friendly, and helpful.
6. Never use lists, bullets, or long explanations on the phone.

APPOINTMENT BOOKING:
- If the customer wants to book an appointment, guide them through providing their name, email, preferred date and time.

EMAIL DETAILS:
- If the customer wants details sent to their email, ask for their email address."""

            # ✅ MULTILINGUAL: Add language instruction for non-English
            if language and language != "en":
                prompt += f"""

LANGUAGE INSTRUCTION (CRITICAL):
The customer is speaking in {language_name}. You MUST respond ENTIRELY in {language_name}.
- Translate your responses naturally into {language_name}.
- Maintain the same tone, professionalism, and helpfulness.
- Do NOT mix languages — respond fully in {language_name}.
- Keep the same conversation context and information accuracy."""
                logger.info(f"🌐 [PROMPT] Added {language_name} language instruction to INBOUND prompt")

            return prompt

        # OUTBOUND: Extract identity information for sales prompt
        identity = agent_context.get("identity", {})
        ai_name = identity.get("name") or agent_name
        company_name = identity.get("company") or "our company"
        role = identity.get("role")
        if role:
            role_description = f"You are {ai_name}, a {role} at {company_name}."
        else:
            role_description = f"You are {ai_name}, a professional representative from {company_name}."
        
        # Extract company information
        company_info = agent_context.get("company_info", {})
        company_description = company_info.get("description", "")
        services = company_info.get("services", [])
        value_propositions = company_info.get("value_propositions", [])
        
        # Extract knowledge base
        knowledge_base = agent_context.get("knowledge_base", {})
        products = knowledge_base.get("products", [])
        support_channels = knowledge_base.get("support_channels", [])
        working_hours = knowledge_base.get("working_hours", "")
        
        # Extract FAQs
        faqs = agent_context.get("faqs", [])
        
        # Extract procedures
        procedures = agent_context.get("procedures", [])
        
        # Build services section
        services_text = ""
        if services:
            services_text = "\n🎯 OUR KEY SERVICES:\n" + "\n".join([f"  • {s}" for s in services[:8]])
        
        # Build products section
        products_text = ""
        if products:
            products_text = "\n📦 OUR PRODUCTS:\n" + "\n".join([f"  • {p}" for p in products[:8]])
        
        # Build value propositions
        value_props_text = ""
        if value_propositions:
            value_props_text = "\n💎 WHY CHOOSE US:\n" + "\n".join([f"  • {v}" for v in value_propositions[:5]])
        
        # Build FAQ section
        faq_text = ""
        if faqs:
            faq_text = "\n❓ COMMON QUESTIONS & ANSWERS:\n"
            for faq in faqs[:10]:
                q = faq.get("question", "")
                a = faq.get("answer", "")
                if q and a:
                    faq_text += f"  Q: {q}\n  A: {a}\n\n"
        
        # Build the complete SALES-FOCUSED system prompt
        # Inject raw script at the TOP for maximum priority
        script_block = ""
        if ai_script and ai_script.strip():
            script_block = f"""
═══════════════════════════════════════════════════════════════
📜 YOUR EXACT SCRIPT & INSTRUCTIONS (HIGHEST PRIORITY — FOLLOW THIS ABOVE ALL ELSE)
═══════════════════════════════════════════════════════════════

The following is your EXACT script from your manager. You MUST follow these
instructions word-for-word. They OVERRIDE everything else in this prompt.
If this script mentions specific services, pricing, behavior, or strategies,
use ONLY what is written here. Do NOT make up information not in this script.
Do NOT mention services or prices not described here.

YOUR SCRIPT:
{ai_script}

═══════════════════════════════════════════════════════════════
"""
            logger.info(f"📜 [PROMPT] Injecting raw ai_script ({len(ai_script)} chars) at TOP of system prompt")

        # When a custom script is provided, use a tighter prompt that defers to it
        has_custom_script = bool(ai_script and ai_script.strip())

        # Sentence limit: allow up to 4 sentences when explaining coverage/benefits
        # (the script has multi-sentence explanations by design); default is 2 for chitchat
        sentence_rule = (
            "- MAXIMUM 2-3 SENTENCES PER RESPONSE — even when explaining coverage or benefits. "
            "Pick the most important point from your script and say it concisely. "
            "Keep the customer engaged — never monologue."
            if has_custom_script
            else "- MAXIMUM 2 SENTENCES PER RESPONSE — no exceptions on a voice call."
        )

        # When a script is loaded, drop the generic sales framework questions — the script
        # already tells the agent exactly what to ask and when.
        objection_note = (
            "- For objections, follow the OBJECTION HANDLING section of your script above. "
            "Do NOT use generic objection frameworks — use the exact responses from your script."
            if has_custom_script
            else "- Handle objections using the techniques listed below."
        )

        prompt = f"""You are {ai_name}, a professional OUTBOUND SALES REPRESENTATIVE for {company_name}. {role_description}
This is a live phone call. Respond like a real human — warm, concise, and conversational.
Your goal is to follow your script step-by-step, build rapport, and guide the customer toward enrollment.
{script_block}
ABSOLUTE RULES FOR EVERY RESPONSE:
THIS IS A LIVE PHONE CALL — NOT TEXT CHAT.
{sentence_rule}
- LISTEN FIRST — ALWAYS directly address what the customer just said before anything else.
- ONE QUESTION ONLY — end with exactly one short question to move forward.
- NO LISTS, NO BULLETS — this is a spoken phone call.
- Sound confident, friendly, and persuasive — like a real human salesperson.
- Always guide the call forward using your script flow.
{objection_note}

══════════════════════════════════════════════════════
🚫 PAYMENT RULES — NEVER BREAK THESE
══════════════════════════════════════════════════════
1. NEVER offer to send a payment link via email. NEVER say "I'll send you a secure link", "I'll email you a payment link", or anything similar. ALL card details are collected on THIS call only.
2. NEVER ask for card details yourself. Do NOT ask for card number, expiry date, CVC, or security code. A separate secure system handles that automatically after the customer agrees to enroll.
3. NEVER assume you already have any card or payment information. Each call is a brand-new customer — you have ZERO prior data about them. Do not say "I see you have a Mastercard on file" or reference any prior card details.
4. When the customer agrees to enroll, say ONLY: "Perfect! Let me get your details started now." Then STOP — the secure payment system will take over and ask for everything step by step (name on card first, then card number, then expiry, then security code, then bank name, phone, and address).
5. NEVER start with CVC or expiry. The collection always starts with the cardholder name. Do not jump ahead.
══════════════════════════════════════════════════════
🧠 FRESH START — EVERY CALL
══════════════════════════════════════════════════════
- Every call is with a BRAND NEW customer. You have NO information about them from any previous call.
- Do not reference any past interaction, prior payment data, card details, or previous conversations.
- Start completely fresh — gather all information naturally during this call only.
══════════════════════════════════════════════════════

If the customer says they're busy, not interested, or wants to hang up:
- DO NOT say goodbye or end the call
- Acknowledge briefly in ONE short phrase ("I completely understand—")
- Immediately pivot to your single strongest benefit or a compelling offer
- Ask ONE short closing question to re-engage them
- Keep it under 2 sentences total
- EXAMPLE: "I completely understand — just 20 seconds, this plan covers repairs other warranties ignore. Can I tell you the one thing that makes it different?"

:ear: CRITICAL LISTENING RULES :ear:
LISTEN BEFORE YOU SELL.
- If user asks a specific question, ANSWER IT FIRST in one sentence
- Then connect to your value proposition
- If user shares a problem, ACKNOWLEDGE IT FIRST
- Then offer your solution
- NEVER give a generic pitch when user asked a specific question
- Example:
  User: "How can you help with lead conversion?"
  BAD: "We help businesses grow. Want to schedule a demo?"
  GOOD: "We optimize your outreach timing and messaging. That typically boosts conversion 30-50%. What's your current rate?"
:no_entry_sign: CRITICAL: NEVER REPEAT YOURSELF :no_entry_sign:
- Check conversation history BEFORE asking questions
- If you already asked "Would you like to hear success stories?" → DON'T ask it again
- If user already agreed to demo → DON'T ask for demo again
- If user already answered a question → DON'T ask the same question
- Move the conversation FORWARD, not in circles

Examples of what NOT to do:
You: "Would you like a demo?"
   User: "Yes"
   You: "Great! Would you like a demo?" ← WRONG! Already agreed!

You: "Would you like a demo?"
   User: "Yes"
   You: "Perfect! Ask the Time that Best work for User" ← CORRECT! Move forward!
:dart: SALES BEHAVIOR GUIDELINES
- Assume the prospect is busy
- Lead with a benefit, not a feature
- Address a common pain point for their business
- Create curiosity, not a full pitch
- If they hesitate, reframe value briefly and ask again

GOOD EXAMPLE:
"Hi, this is {ai_name} from {company_name}. We help businesses cut call costs while improving reach. Are you handling telecom in-house today?"

BAD EXAMPLE:
Long explanations, multiple services, lists, or non-sales talk.


═══════════════════════════════════════════════════════════════
🏢 ABOUT {company_name.upper() if company_name and company_name != "our company" else "OUR COMPANY"}
═══════════════════════════════════════════════════════════════
{company_description}
{services_text}
{products_text}
{value_props_text}

{f"⏰ Working Hours: {working_hours}" if working_hours else ""}
{faq_text}

═══════════════════════════════════════════════════════════════
🎯 SALES MISSION - CRITICAL INSTRUCTIONS
═══════════════════════════════════════════════════════════════

You are NOT just a helpful assistant. You are a SALES PROFESSIONAL whose primary goal is to:
1. Follow your script step-by-step to guide the customer toward enrolling
2. CONVERT conversations into a successful enrollment or scheduled follow-up
3. Answer questions briefly (1 sentence), then continue your script flow
4. Ask ONE forward-moving question from your script

Check conversation history — never repeat a question you already asked.
If your script has already covered a topic in this call, do NOT revisit it.

📌 GOLDEN RULES FOR EVERY RESPONSE:

1. **FOLLOW THE SCRIPT FIRST**
   - Use the step-by-step flow from your script above
   - Do not skip steps or jump ahead
   - If the customer goes off-topic, answer briefly then steer back to your script step

2. **ANSWER BRIEFLY, THEN CONTINUE YOUR SCRIPT**
   - Address the customer's question or comment in 1 sentence
   - Then continue from where you were in the script
   - Do NOT pivot to generic "what challenges are you facing" questions — use your script's next step

3. **ALWAYS END WITH YOUR SCRIPT'S NEXT QUESTION**
   Use the next natural question from your script. Only fall back to these if your script doesn't specify:
   - "Does that make sense?"
   - "Any questions about that?"
   - "Would you like to go ahead and get started today?"

3. **CREATE GENTLE URGENCY**
   - Mention limited availability when appropriate
   - Reference current promotions or special offers if any
   - Emphasize the cost of NOT taking action

4. **USE SOCIAL PROOF**
   - Reference other satisfied customers
   - Mention success stories when relevant
   - Use phrases like "Many of our clients..." or "Companies like yours have found..."

5. **HANDLE OBJECTIONS SMOOTHLY**
   
   Common Objection Patterns & Responses:
   
   "Not interested"
   - "I understand! Can I ask - what would make this interesting for you?"
   - "Many clients felt the same way initially. What's your biggest concern right now with [pain point]?"
   
   "Too expensive" / "Can't afford it"
   - "I hear you! Let me ask - what would the cost be if you DON'T solve [pain point]?"
   - "Our clients find that the ROI pays for itself in [timeframe]. What's your current cost for [problem]?"
   
   "No time" / "Too busy"
   - "That's exactly why we built this - to save you time! What's taking up most of your time right now?"
   - "I understand busy schedules. What if I could show you how to save [X hours] per week?"
   
   "Need to think about it"
   - "Absolutely! What specific aspect would you like to think about? Pricing? Implementation?"
   - "Fair enough! What questions can I answer to help your decision?"
   
   "Using someone else already"
   - "That's great you're already taking action! What's working well? What could be better?"
   - "I'm curious - what made you choose them? And what would make you consider switching?"
   
   "Tried it before, didn't work"
   - "I appreciate you sharing that. What specifically didn't work? That helps me understand your needs better."
   - "Many of our best clients had similar experiences elsewhere. What would success look like for you?"
   
   "How is this different?"
   - "Great question! Unlike others, we [unique value]. What's your main priority - [option A] or [option B]?"
   
   CRITICAL: After handling objection, ALWAYS ask a follow-up question to re-engage!

═══════════════════════════════════════════════════════════════
🎯 REBUTTAL & PERSUASION STRATEGIES
═══════════════════════════════════════════════════════════════

When user shows resistance, use these proven techniques:

1. **FEEL, FELT, FOUND Technique**
   "I understand how you feel. Many of our clients felt the same way. 
    What they found was [benefit]. Would you be open to hearing how?"

2. **ISOLATE THE OBJECTION**
   User: "I don't think this is for me"
   You: "I appreciate your honesty! Is it the [price/timing/features], 
         or is there something else I should know about?"

3. **REFRAME THE PROBLEM**
   User: "This is too expensive"
   You: "I hear you! Instead of cost, let's talk about value. 
         What's it worth to you to solve [pain point]?"

4. **CREATE URGENCY (GENTLE)**
   "I totally understand wanting to think it over. Just so you know,
    we're running a limited promotion this month. When would be a good
    time for a quick follow-up - end of week?"

5. **SOCIAL PROOF**
   "I hear your concern! [Similar company/person] had the same worry.
    They've been with us for [time] and seen [result]. 
    Would you like to hear their story?"

6. **TRIAL CLOSE**
   After handling objection: "If I could address [concern], 
   would you be ready to move forward today?"

6. **NEVER JUST ANSWER AND STOP**
   ❌ WRONG: "Yes, we offer that service."
   ✅ RIGHT: " Our [service] has helped many businesses like yours achieve [benefit]. What specific goals are you hoping to accomplish? I'd love to see how we can tailor a solution for you."

═══════════════════════════════════════════════════════════════
💬 RESPONSE EXAMPLES
═══════════════════════════════════════════════════════════════

SCENARIO: Customer asks about pricing
❌ BAD: Making up prices or using generic numbers. NEVER invent pricing.
✅ GOOD: If your custom script above has pricing info, use EXACTLY those numbers. Otherwise say: "Great question! Our pricing depends on your specific needs. To give you an accurate quote, I'd love to understand more about your requirements. What's the main challenge you're trying to solve?"

SCENARIO: Customer asks unrelated question
❌ BAD: "I'm not sure about that."
✅ GOOD: "That's an interesting question! While I specialize in {company_name}'s services, I'm curious - what made you reach out to us today? I'd love to see how we can help with your [business/needs]."

SCENARIO: Customer seems hesitant
❌ BAD: "Let me know if you have questions."
✅ GOOD: "I understand you want to make the right decision. Many of our happiest customers felt the same way initially. What would help you feel more confident? A quick demo? References from similar companies? I'm here to help you get all the information you need."

SCENARIO: Customer says goodbye
❌ BAD: "Goodbye, have a nice day."
✅ GOOD: "Before you go, I'd love to stay in touch! Should I send you some information about [relevant service]? Or better yet, would you like to schedule a quick 15-minute call where I can show you exactly how we can help? No pressure at all - just want to make sure you have everything you need."

═══════════════════════════════════════════════════════════════
⚡ QUICK REMINDERS
═══════════════════════════════════════════════════════════════

• Be conversational and warm, not pushy
• Listen to their needs, then connect to your solutions
• Every response = Brief answer + Company connection + Engagement question
• Your goal: Book appointments, schedule demos, close sales
• Keep responses concise (2-4 sentences) but impactful
• Always maintain a helpful, consultative tone

Remember: You represent {company_name}. Every conversation is an opportunity to create a new customer relationship!"""

        # ✅ MULTILINGUAL: Add language instruction for non-English
        if language and language != "en":
            prompt += f"""

═══════════════════════════════════════════════════════════════
🌐 LANGUAGE INSTRUCTION (HIGHEST PRIORITY)
═══════════════════════════════════════════════════════════════

The customer is speaking in {language_name}. You MUST respond ENTIRELY in {language_name}.
- Translate ALL your responses naturally into {language_name}.
- Maintain the same sales tone, professionalism, and persuasion techniques.
- Do NOT mix languages — respond fully in {language_name}.
- Keep the same conversation context, product information, and sales strategies.
- Adapt culturally where appropriate while maintaining sales effectiveness."""
            logger.info(f"🌐 [PROMPT] Added {language_name} language instruction to OUTBOUND prompt")

        return prompt
    
    
    async def generate_agent_summary(
        self,
        document_text: Optional[str] = None,
        script_text: Optional[str] = None,
        existing_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured summary/context from documents and script
        Used for pre-building agent context
        """
        try:
            if not self.configured or not self.client:
                logger.warning("⚠️ AI service not configured for summary generation")
                return {
                    "success": False,
                    "error": "AI service not configured"
                }
            
            # Combine available text
            combined_text = ""
            if script_text:
                combined_text += f"AI SCRIPT:\n{script_text}\n\n"
            if document_text:
                combined_text += f"TRAINING DOCUMENTS:\n{document_text}\n\n"
            
            if not combined_text.strip():
                return {
                    "success": False,
                    "error": "No text provided for summary generation"
                }
            
            # Truncate if too long
            max_chars = 15000
            if len(combined_text) > max_chars:
                combined_text = combined_text[:max_chars] + "\n...[truncated]"
            
            extraction_prompt = """Analyze the following text and extract a structured summary for a SALES AI agent.

Return a JSON object with this EXACT structure:
{
    "identity": {
        "name": "Agent's name if mentioned, otherwise null",
        "company": "Company name if mentioned, otherwise null",
        "role": "Agent's role/title if explicitly mentioned (e.g., 'Sales Representative' , 'Sales Manager'), otherwise null.
    },
    "company_info": {
        "description": "Brief company description",
        "industry": "Industry/sector",
        "services": ["service1", "service2", ...],
        "value_propositions": ["why choose us 1", "why choose us 2", ...]
    },
    "knowledge_base": {
        "products": ["product1", "product2", ...],
        "services": ["service1", "service2", ...],
        "support_channels": ["email", "phone", ...],
        "working_hours": "e.g., 9 AM - 5 PM EST"
    },
    "faqs": [
        {"question": "Common question 1", "answer": "Answer 1"},
        {"question": "Common question 2", "answer": "Answer 2"}
    ],
    "procedures": [
        {"name": "Procedure name", "steps": ["step1", "step2"]}
    ],
    "sales_points": {
        "unique_selling_points": ["USP 1", "USP 2"],
        "target_audience": "Who are ideal customers",
        "common_objections": ["objection 1", "objection 2"],
        "closing_techniques": ["technique 1", "technique 2"]
    }
}
IMPORTANT RULES FOR ROLE EXTRACTION:
- Only extract role if it's explicitly mentioned in the text
- Do NOT assume anything from yours own knowledge or make inferences
- If no role is mentioned, set role to null
- Examples of valid roles: "Customer Success Manager", "Sales Director"
- Only use what's actually written in the text

TEXT TO ANALYZE:
""" + combined_text
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts structured information from text. Always respond with valid JSON only, no markdown formatting."
                    },
                    {"role": "user", "content": extraction_prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            try:
                # Remove markdown code blocks if present
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
                
                context = json.loads(result_text)
                
                logger.info("✅ Agent summary generated successfully")
                
                return {
                    "success": True,
                    "context": context,
                    "provider": self.provider
                }
                
            except json.JSONDecodeError as je:
                logger.error(f"❌ Failed to parse JSON: {je}")
                
                # Return a basic context structure
                return {
                    "success": True,
                    "context": {
                        "identity": {"name": "AI Assistant", "company": "Our Company", "role": "Sales Representative"},
                        "company_info": {"description": script_text[:500] if script_text else "", "services": []},
                        "knowledge_base": {},
                        "faqs": [],
                        "procedures": [],
                        "summary_text": combined_text[:2000]
                    },
                    "provider": self.provider
                }
            
        except Exception as e:
            logger.error(f"❌ Error generating agent summary: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    
    async def generate_call_summary(
        self,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Generate a summary of a call from transcript messages"""
        try:
            if not self.configured or not self.client:
                return {"success": False, "error": "AI service not configured"}
            
            # Format messages for summary
            transcript = "\n".join([
                f"{msg.get('speaker', 'Unknown')}: {msg.get('text', '')}"
                for msg in messages
            ])
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes sales calls. Provide a brief, professional summary including: main topics discussed, customer's needs/interests, outcome, and recommended follow-up actions."
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize this sales call:\n\n{transcript}"
                    }
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "summary": summary,
                "provider": self.provider
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating call summary: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def select_key_messages(
        self,
        messages: List[Dict[str, str]],
        max_messages: int = 5
    ) -> Dict[str, Any]:
        """Select the most important messages from a conversation"""
        try:
            if not self.configured or not self.client:
                return {"success": False, "error": "AI service not configured"}
            
            # Format messages
            transcript = "\n".join([
                f"{i+1}. {msg.get('speaker', 'Unknown')}: {msg.get('text', '')}"
                for i, msg in enumerate(messages)
            ])
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Select the {max_messages} most important messages from this conversation. Return only the message numbers separated by commas."
                    },
                    {"role": "user", "content": transcript}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the numbers
            try:
                indices = [int(x.strip()) - 1 for x in result.split(",")]
                key_messages = [messages[i] for i in indices if 0 <= i < len(messages)]
            except:
                key_messages = messages[:max_messages]
            
            return {
                "success": True,
                "key_messages": key_messages,
                "provider": self.provider
            }
            
        except Exception as e:
            logger.error(f"❌ Error selecting key messages: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def determine_call_outcome(
        self,
        transcript: str
    ) -> Dict[str, Any]:
        """Determine the outcome of a call from transcript"""
        try:
            if not self.configured or not self.client:
                return {"success": False, "error": "AI service not configured"}
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze this sales call and determine the outcome. Return one of: 'appointment_booked', 'interested_follow_up', 'not_interested', 'callback_scheduled', 'sale_closed', 'information_provided', 'unknown'"
                    },
                    {"role": "user", "content": f"Call transcript:\n{transcript[:2000]}"}
                ],
                max_tokens=20,
                temperature=0.3
            )
            
            outcome = response.choices[0].message.content.strip().lower()
            
            # Validate outcome
            valid_outcomes = [
                'appointment_booked', 'interested_follow_up', 'not_interested',
                'callback_scheduled', 'sale_closed', 'information_provided', 'unknown'
            ]
            
            if outcome not in valid_outcomes:
                outcome = 'unknown'
            
            return {
                "success": True,
                "outcome": outcome,
                "provider": self.provider
            }
            
        except Exception as e:
            logger.error(f"❌ Error determining call outcome: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def generate_response_with_fallback(
        self,
        user_input: str,
        system_prompt: str,
        call_id: str = None,
        max_tokens: int = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate AI response with local fallback when both providers fail"""
        try:
            if not self.configured or not self.client:
                logger.warning(f"⚠️ AI service not configured")
                return self._generate_local_fallback_response(user_input, system_prompt)
            
            # Truncate system prompt if too long
            if len(system_prompt) > 1500:
                system_prompt = system_prompt[:1500] + "..."
            
            logger.info(f"🤖 Generating response with {self.provider} ({self.model})...")

            # ✅ Groq has faster response times
            timeout_seconds = 3.0 if self.provider == "groq" else 4.0
            
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_input}
                        ],
                        max_tokens=max_tokens or 80,
                        temperature=temperature
                    ),
                    timeout=timeout_seconds
                )
                
                ai_response = response.choices[0].message.content.strip()
                
                logger.info(f"✅ {self.provider} response received ({len(ai_response)} chars)")
                
                return {
                    "success": True,
                    "response": ai_response,
                    "provider": self.provider
                }
                
            except asyncio.TimeoutError:
                logger.error(f"❌ {self.provider} timeout after {timeout_seconds}s")
                return self._generate_local_fallback_response(user_input, system_prompt)
            except Exception as e:
                logger.error(f"❌ {self.provider} error: {e}")
                # Try to extract if it's a credit/403 error
                error_str = str(e)
                if "doesn't have any credits" in error_str or "403" in error_str or "permission" in error_str.lower():
                    logger.warning(f"⚠️ {self.provider} has credit/access issue, using local fallback")
                return self._generate_local_fallback_response(user_input, system_prompt)
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in generate_response: {e}")
            return self._generate_local_fallback_response(user_input, system_prompt)
    
    
    def _generate_local_fallback_response(self, user_input: str, system_prompt: str) -> Dict[str, Any]:
        """Generate a local fallback response when AI services fail"""
        
        # Extract company name from system prompt
        company_name = "our company"  # Default
        if "Venderia" in system_prompt:
            company_name = "Venderia"
        elif "company" in system_prompt.lower():
            # Try to extract company name
            import re
            match = re.search(r"for (.+?)\.", system_prompt)
            if match:
                company_name = match.group(1).split()[0]
        
        # Simple keyword-based responses
        user_lower = user_input.lower()
        
        # Common sales conversation responses
        if any(word in user_lower for word in ["hello", "hi", "hey"]):
            response = f"Hello! Thank you for reaching out to {company_name}. How can I assist you today? Are you interested in learning about our services?"
        
        elif any(word in user_lower for word in ["service", "provide", "offer", "what do you do"]):
            response = f"I'd love to tell you more about how {company_name} can help you. What specific challenges are you currently facing?"
        
        elif any(word in user_lower for word in ["price", "cost", "discount", "how much"]):
            response = f"Great question! Our solutions are customized based on your specific needs. What's your biggest priority right now?"
        
        elif any(word in user_lower for word in ["help", "support", "assist"]):
            response = f"I'm here to help! {company_name} has helped many customers like you. Would you like to hear about our most popular solutions?"
        
        elif "?" in user_input:
            response = f"That's an excellent question! At {company_name}, we focus on providing tailored solutions. What specific goal are you hoping to achieve?"
        
        else:
            # Generic engaging response
            responses = [
                f"Thanks for sharing that! At {company_name}, we specialize in helping businesses like yours. What's the main challenge you're looking to solve?",
                f"I appreciate you reaching out! {company_name} offers comprehensive solutions. Would you like me to explain how we can help with that?",
                f"That's interesting! Many of our clients at {company_name} have similar needs. What specific outcome are you hoping for?",
                f"Great to hear from you! {company_name} has various solutions available. What aspect are you most curious about?",
                f"Thank you for connecting! At {company_name}, we pride ourselves on delivering results. What would success look like for you?"
            ]
            import random
            response = random.choice(responses)
        
        logger.info(f"🔄 Using LOCAL FALLBACK response ({len(response)} chars)")
        
        return {
            "success": True,
            "response": response,
            "provider": "local_fallback",
            "was_fallback": True
        }


# Create singleton instance
openai_service = OpenAIService()


