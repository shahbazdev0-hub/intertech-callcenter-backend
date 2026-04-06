#   # backend/app/services/time_parser.py orgianl file
# """
# Time Parser Service - Natural Language Time Parsing
# Converts phrases like "call me in 2 minutes", "call me back in 3 minutes" into datetime
# """

# import re
# import logging
# from datetime import datetime, timedelta
# from typing import Optional, Dict, Any
# import dateparser

# logger = logging.getLogger(__name__)


# class TimeParserService:
#     """Parse natural language time expressions"""
    
#     def __init__(self):
#         # Common time patterns
#         self.relative_patterns = {
#             r'(?:in\s+)?(\d+)\s*(?:hours?|hrs?)': 'hours',
#             r'(?:in\s+)?an?\s+hour': 'hours',
#             r'couple\s+(?:of\s+)?hours?': 'hours',
#             r'few\s+hours?': 'hours',
#             r'(?:in\s+)?(\d+)\s*(?:minutes?|mins?)': 'minutes',
#             r'(?:in\s+)?half\s+(?:an\s+)?hour': 'minutes',
#             r'(?:in\s+)?(\d+)\s*days?': 'days',
#             r'tomorrow': 'tomorrow',
#             r'day\s+after\s+tomorrow': 'days',
#             r'(?:in\s+)?(\d+)\s*weeks?': 'weeks',
#             r'next\s+week': 'weeks',
#             r'later\s+(?:today|tonight)': 'later_today',
#             r'(?:call|contact|reach)\s+(?:me\s+)?later': 'later',
#             r'(?:call|contact|reach)\s+(?:me\s+)?soon': 'soon',
#         }
        
#         self.day_patterns = {
#             'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
#             'friday': 4, 'saturday': 5, 'sunday': 6,
#             'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
#             'fri': 4, 'sat': 5, 'sun': 6
#         }
    
#     async def parse_follow_up_time(self, user_input: str) -> Optional[Dict[str, Any]]:
#         """
#         Parse follow-up time from user input like:
#         - "call me in 2 minutes"
#         - "call me later"
#         - "call me tomorrow"
#         - "call me in 1 hour"
        
#         Returns:
#             Dictionary with success, datetime, confidence OR None if cannot parse
#         """
#         try:
#             import re
#             from datetime import datetime, timedelta
            
#             user_input_lower = user_input.lower()
#             now = datetime.utcnow()
            
#             # Pattern: "X minutes later" or "in X minutes" or "after X minutes"
#             minutes_match = re.search(r'(\d+)\s*(?:minute|min)', user_input_lower)
#             if minutes_match:
#                 minutes = int(minutes_match.group(1))
#                 return {
#                     "success": True,
#                     "datetime": now + timedelta(minutes=minutes),
#                     "confidence": "high",
#                     "type": "minutes"
#                 }
            
#             # Pattern: "X hours later" or "in X hours"
#             hours_match = re.search(r'(\d+)\s*(?:hour|hr)', user_input_lower)
#             if hours_match:
#                 hours = int(hours_match.group(1))
#                 return {
#                     "success": True,
#                     "datetime": now + timedelta(hours=hours),
#                     "confidence": "high",
#                     "type": "hours"
#                 }
            
#             # Pattern: "later" (default 30 minutes)
#             if 'later' in user_input_lower:
#                 return {
#                     "success": True,
#                     "datetime": now + timedelta(minutes=30),
#                     "confidence": "medium",
#                     "type": "later"
#                 }
            
#             # Pattern: "tomorrow" with optional time
#             if 'tomorrow' in user_input_lower:
#                 target = now + timedelta(days=1)
                
#                 # Check for specific time like "tomorrow at 10 pm"
#                 time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?', user_input_lower)
#                 if time_match:
#                     hour = int(time_match.group(1))
#                     minute = int(time_match.group(2) or 0)
#                     period = time_match.group(3)
                    
#                     if period and 'p' in period.lower() and hour != 12:
#                         hour += 12
#                     elif period and 'a' in period.lower() and hour == 12:
#                         hour = 0
                    
#                     target = target.replace(hour=hour, minute=minute, second=0)
#                 else:
#                     target = target.replace(hour=10, minute=0, second=0)  # Default 10 AM
                
#                 return {
#                     "success": True,
#                     "datetime": target,
#                     "confidence": "high",
#                     "type": "tomorrow"
#                 }
            
#             # Pattern: "next week"
#             if 'next week' in user_input_lower:
#                 return {
#                     "success": True,
#                     "datetime": now + timedelta(weeks=1),
#                     "confidence": "medium",
#                     "type": "next_week"
#                 }
            
#             logger.info(f"⚠️ Could not parse follow-up time from: {user_input}")
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error parsing follow-up time: {e}")
#             return None
    
#     async def parse_time_expression(self, text: str, base_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
#         """Parse natural language time expression - ENHANCED"""
#         try:
#             import dateparser
#             from datetime import datetime, timedelta
            
#             text_lower = text.lower().strip()
#             now = base_time if base_time else datetime.utcnow()
            
#             logger.info(f"📅 Parsing time expression: '{text}'")
            
#             # ✅ Handle relative time first (call me in X minutes/hours)
#             relative_patterns = [
#                 (r'(\d+)\s*(?:min|minute)', 'minutes'),
#                 (r'(\d+)\s*(?:hr|hour)', 'hours'),
#                 (r'(\d+)\s*(?:day)', 'days'),
#             ]
            
#             import re
#             for pattern, unit in relative_patterns:
#                 match = re.search(pattern, text_lower)
#                 if match:
#                     amount = int(match.group(1))
#                     if unit == 'minutes':
#                         target_dt = now + timedelta(minutes=amount)
#                     elif unit == 'hours':
#                         target_dt = now + timedelta(hours=amount)
#                     elif unit == 'days':
#                         target_dt = now + timedelta(days=amount)
                    
#                     logger.info(f"✅ Relative time parsed: {target_dt}")
#                     return {
#                         "success": True,
#                         "datetime": target_dt,
#                         "original_text": text,
#                         "confidence": 0.95,
#                         "type": "relative"
#                     }
            
#             # ✅ Handle specific dates with dateparser
#             parsed_date = dateparser.parse(
#                 text,
#                 settings={
#                     'PREFER_DATES_FROM': 'future',
#                     'RETURN_AS_TIMEZONE_AWARE': False,
#                     'RELATIVE_BASE': now
#                 }
#             )
            
#             if parsed_date:
#                 # If only date was parsed (no time), default to 10 AM
#                 if parsed_date.hour == 0 and parsed_date.minute == 0:
#                     # Check if time was mentioned
#                     has_time = any(t in text_lower for t in ['am', 'pm', ':'])
#                     if not has_time:
#                         parsed_date = parsed_date.replace(hour=10, minute=0)
                
#                 # Ensure it's in the future
#                 if parsed_date <= now:
#                     parsed_date = parsed_date + timedelta(days=1)
                
#                 logger.info(f"✅ Date parsed: {parsed_date}")
#                 return {
#                     "success": True,
#                     "datetime": parsed_date,
#                     "original_text": text,
#                     "confidence": 0.85,
#                     "type": "absolute"
#                 }
            
#             logger.warning(f"⚠️ Could not parse time from: '{text}'")
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Time parsing error: {e}")
#             return None
    
#     async def _parse_minutes(
#         self,
#         text: str,
#         base_time: datetime
#     ) -> Optional[Dict[str, Any]]:
#         """✅ NEW: Specifically parse 'X minutes' patterns"""
#         try:
#             # Pattern for "in X minutes", "X minutes", "call me back in X minutes"
#             patterns = [
#                 r'(?:in\s+)?(\d+)\s*(?:minutes?|mins?|min)',
#                 r'(?:call\s+(?:me\s+)?back\s+)?(?:in\s+)?(\d+)\s*(?:minutes?|mins?|min)',
#             ]
            
#             for pattern in patterns:
#                 match = re.search(pattern, text, re.IGNORECASE)
#                 if match:
#                     minutes = int(match.group(1))
#                     target_time = base_time + timedelta(minutes=minutes)
                    
#                     logger.info(f"✅ Parsed {minutes} minutes from: '{text}'")
#                     logger.info(f"   Target time: {target_time}")
                    
#                     return {
#                         "success": True,
#                         "datetime": target_time,
#                         "original_text": text,
#                         "confidence": "high",
#                         "type": "relative_minutes",
#                         "minutes": minutes
#                     }
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error parsing minutes: {e}")
#             return None
    
#     async def _parse_relative_time(
#         self,
#         text: str,
#         base_time: datetime
#     ) -> Optional[Dict[str, Any]]:
#         """Parse relative time expressions like 'in 2 hours'"""
#         try:
#             # Hours pattern
#             hours_match = re.search(r'(?:in\s+)?(\d+)\s*(?:hours?|hrs?)', text)
#             if hours_match:
#                 hours = int(hours_match.group(1))
#                 target_time = base_time + timedelta(hours=hours)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "high",
#                     "type": "relative_hours"
#                 }
            
#             # "an hour" / "one hour"
#             if re.search(r'(?:in\s+)?(?:an?|one)\s+hour', text):
#                 target_time = base_time + timedelta(hours=1)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "high",
#                     "type": "relative_hours"
#                 }
            
#             # "couple hours"
#             if re.search(r'couple\s+(?:of\s+)?hours?', text):
#                 target_time = base_time + timedelta(hours=2)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "medium",
#                     "type": "relative_hours"
#                 }
            
#             # "few hours"
#             if re.search(r'few\s+hours?', text):
#                 target_time = base_time + timedelta(hours=3)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "medium",
#                     "type": "relative_hours"
#                 }
            
#             # "half hour" / "30 minutes"
#             if re.search(r'half\s+(?:an?\s+)?hour', text):
#                 target_time = base_time + timedelta(minutes=30)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "high",
#                     "type": "relative_minutes"
#                 }
            
#             # Days pattern
#             days_match = re.search(r'(?:in\s+)?(\d+)\s*days?', text)
#             if days_match:
#                 days = int(days_match.group(1))
#                 target_time = base_time + timedelta(days=days)
#                 target_time = target_time.replace(hour=10, minute=0, second=0)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "high",
#                     "type": "relative_days"
#                 }
            
#             # Tomorrow
#             if 'tomorrow' in text:
#                 target_time = base_time + timedelta(days=1)
                
#                 # Check for specific time
#                 time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
#                 if time_match:
#                     hour = int(time_match.group(1))
#                     minute = int(time_match.group(2) or 0)
#                     period = time_match.group(3)
                    
#                     if period and period.lower() == 'pm' and hour != 12:
#                         hour += 12
#                     elif period and period.lower() == 'am' and hour == 12:
#                         hour = 0
                    
#                     target_time = target_time.replace(hour=hour, minute=minute, second=0)
#                 else:
#                     target_time = target_time.replace(hour=10, minute=0, second=0)
                
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "high",
#                     "type": "tomorrow"
#                 }
            
#             # Later today
#             if re.search(r'later\s+(?:today|tonight)', text):
#                 target_time = base_time + timedelta(hours=2)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "medium",
#                     "type": "later_today"
#                 }
            
#             # Generic "later" or "soon"
#             if re.search(r'(?:call|contact|reach)\s+(?:me\s+)?(?:later|soon)', text):
#                 target_time = base_time + timedelta(hours=1)
#                 return {
#                     "success": True,
#                     "datetime": target_time,
#                     "original_text": text,
#                     "confidence": "low",
#                     "type": "later"
#                 }
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error parsing relative time: {e}")
#             return None
    
#     async def _parse_specific_day(
#         self,
#         text: str,
#         base_time: datetime
#     ) -> Optional[Dict[str, Any]]:
#         """Parse specific day expressions like 'next Monday'"""
#         try:
#             for day_name, day_num in self.day_patterns.items():
#                 if day_name in text:
#                     current_day = base_time.weekday()
#                     days_ahead = day_num - current_day
                    
#                     if days_ahead <= 0:
#                         days_ahead += 7
                    
#                     if 'next' in text:
#                         days_ahead += 7
                    
#                     target_time = base_time + timedelta(days=days_ahead)
                    
#                     # Check for specific time
#                     time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
#                     if time_match:
#                         hour = int(time_match.group(1))
#                         minute = int(time_match.group(2) or 0)
#                         period = time_match.group(3)
                        
#                         if period and period.lower() == 'pm' and hour != 12:
#                             hour += 12
#                         elif period and period.lower() == 'am' and hour == 12:
#                             hour = 0
                        
#                         target_time = target_time.replace(hour=hour, minute=minute, second=0)
#                     else:
#                         target_time = target_time.replace(hour=10, minute=0, second=0)
                    
#                     return {
#                         "success": True,
#                         "datetime": target_time,
#                         "original_text": text,
#                         "confidence": "high",
#                         "type": "specific_day"
#                     }
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error parsing specific day: {e}")
#             return None
    
#     async def _parse_with_dateparser(
#         self,
#         text: str,
#         base_time: datetime
#     ) -> Optional[Dict[str, Any]]:
#         """Use dateparser library for complex expressions"""
#         try:
#             parsed = dateparser.parse(
#                 text,
#                 settings={
#                     'PREFER_DATES_FROM': 'future',
#                     'RELATIVE_BASE': base_time,
#                     'RETURN_AS_TIMEZONE_AWARE': False
#                 }
#             )
            
#             if parsed and parsed > base_time:
#                 if parsed.hour == 0 and parsed.minute == 0:
#                     parsed = parsed.replace(hour=10, minute=0)
                
#                 return {
#                     "success": True,
#                     "datetime": parsed,
#                     "original_text": text,
#                     "confidence": "medium",
#                     "type": "dateparser"
#                 }
            
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Dateparser error: {e}")
#             return None
    
#     async def detect_follow_up_intent(self, text: str) -> bool:
#         """Detect if user wants a follow-up call/reminder"""
#         try:
#             text_lower = text.lower()
            
#             follow_up_keywords = [
#                 'call me back',
#                 'call back',
#                 'callback',
#                 'call me in',
#                 'call me',
#                 'reach out',
#                 'contact me',
#                 'get back to me',
#                 'follow up',
#                 'remind me',
#                 'reminder',
#                 'schedule a call',
#                 'in a few minutes',
#                 'in a few hours',
#                 'later',
#                 'tomorrow',
#                 'next week',
#             ]
            
#             for keyword in follow_up_keywords:
#                 if keyword in text_lower:
#                     logger.info(f"✅ Follow-up intent detected: '{keyword}' in '{text}'")
#                     return True
            
#             # Also check for "X minutes" or "X hours" pattern
#             if re.search(r'\d+\s*(?:minutes?|mins?|hours?|hrs?)', text_lower):
#                 logger.info(f"✅ Follow-up intent detected: time pattern in '{text}'")
#                 return True
            
#             return False
            
#         except Exception as e:
#             logger.error(f"❌ Error detecting follow-up intent: {e}")
#             return False


# # Create singleton instance
# time_parser_service = TimeParserService() 

# backend/app/services/time_parser.py 
"""
Time Parser Service - Natural Language Time Parsing
Converts phrases like "call me in 2 minutes", "call me back in 3 minutes" into datetime
✅ ADDED: Support for "after X minutes" pattern
✅ ADDED: Support for "X minutes from now" pattern
✅ ADDED: Support for spelled-out numbers (five, ten, etc.)
✅ UPDATED: detect_follow_up_intent() to recognize "after" and "from now"
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import dateparser

logger = logging.getLogger(__name__)


class TimeParserService:
    """Parse natural language time expressions"""
    
    # ✅ NEW: Word-to-number mapping for spelled-out numbers
    WORD_TO_NUMBER = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60,
        # Common combinations
        'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23,
        'twenty-four': 24, 'twenty-five': 25, 'twenty-six': 26,
        'twenty-seven': 27, 'twenty-eight': 28, 'twenty-nine': 29,
        'thirty-one': 31, 'thirty-two': 32, 'thirty-three': 33,
        'thirty-four': 34, 'thirty-five': 35, 'thirty-six': 36,
        'thirty-seven': 37, 'thirty-eight': 38, 'thirty-nine': 39,
        'forty-five': 45, 'fifty-five': 55,
        # Also handle without hyphen
        'twenty one': 21, 'twenty two': 22, 'twenty three': 23,
        'twenty four': 24, 'twenty five': 25, 'twenty six': 26,
        'twenty seven': 27, 'twenty eight': 28, 'twenty nine': 29,
        'thirty one': 31, 'thirty two': 32, 'thirty three': 33,
        'thirty four': 34, 'thirty five': 35, 'thirty six': 36,
        'thirty seven': 37, 'thirty eight': 38, 'thirty nine': 39,
        'forty five': 45, 'fifty five': 55,
        # Common speech variations
        'a': 1, 'an': 1, 'couple': 2, 'few': 3, 'several': 5,
    }
    
    def __init__(self):
        # Common time patterns
        self.relative_patterns = {
            r'(?:in\s+)?(\d+)\s*(?:hours?|hrs?)': 'hours',
            r'(?:in\s+)?an?\s+hour': 'hours',
            r'couple\s+(?:of\s+)?hours?': 'hours',
            r'few\s+hours?': 'hours',
            r'(?:in\s+)?(\d+)\s*(?:minutes?|mins?)': 'minutes',
            r'(?:in\s+)?half\s+(?:an\s+)?hour': 'minutes',
            r'(?:in\s+)?(\d+)\s*days?': 'days',
            r'tomorrow': 'tomorrow',
            r'day\s+after\s+tomorrow': 'days',
            r'(?:in\s+)?(\d+)\s*weeks?': 'weeks',
            r'next\s+week': 'weeks',
            r'later\s+(?:today|tonight)': 'later_today',
            r'(?:call|contact|reach)\s+(?:me\s+)?later': 'later',
            r'(?:call|contact|reach)\s+(?:me\s+)?soon': 'soon',
        }
        
        self.day_patterns = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }
    
    def _extract_number(self, text: str) -> Optional[int]:
        """
        ✅ NEW: Extract number from text, supporting both digits and spelled-out words
        Examples:
            "5" -> 5
            "five" -> 5
            "twenty five" -> 25
            "twenty-five" -> 25
        """
        text = text.lower().strip()
        
        # First try to match a digit
        digit_match = re.search(r'(\d+)', text)
        if digit_match:
            return int(digit_match.group(1))
        
        # Check for spelled-out numbers (try longer phrases first)
        # Sort by length descending to match "twenty five" before "five"
        sorted_words = sorted(self.WORD_TO_NUMBER.keys(), key=len, reverse=True)
        for word in sorted_words:
            if word in text:
                return self.WORD_TO_NUMBER[word]
        
        return None
    
    def _extract_number_and_unit(self, text: str) -> Optional[Dict[str, Any]]:
        """
        ✅ NEW: Extract number and time unit from natural language
        Examples:
            "after five minutes" -> {"number": 5, "unit": "minutes"}
            "in 10 hours" -> {"number": 10, "unit": "hours"}
            "call me back in twenty minutes" -> {"number": 20, "unit": "minutes"}
        """
        text_lower = text.lower()
        
        # Build pattern for spelled-out numbers
        # Create a regex alternation for all word numbers
        word_numbers = '|'.join(sorted(self.WORD_TO_NUMBER.keys(), key=len, reverse=True))
        
        # Combined pattern: digits OR spelled-out numbers
        number_pattern = rf'(\d+|{word_numbers})'
        
        # Patterns to try (ordered by specificity)
        patterns = [
            # "after X minutes/hours"
            (rf'after\s+{number_pattern}\s*(?:minutes?|mins?|min)', 'minutes'),
            (rf'after\s+{number_pattern}\s*(?:hours?|hrs?|hr)', 'hours'),
            # "X minutes/hours from now"
            (rf'{number_pattern}\s*(?:minutes?|mins?|min)\s+(?:from\s+)?now', 'minutes'),
            (rf'{number_pattern}\s*(?:hours?|hrs?|hr)\s+(?:from\s+)?now', 'hours'),
            # "in X minutes/hours"
            (rf'(?:in\s+)?{number_pattern}\s*(?:minutes?|mins?|min)', 'minutes'),
            (rf'(?:in\s+)?{number_pattern}\s*(?:hours?|hrs?|hr)', 'hours'),
            # "X minutes/hours later"
            (rf'{number_pattern}\s*(?:minutes?|mins?|min)\s*(?:later)?', 'minutes'),
            (rf'{number_pattern}\s*(?:hours?|hrs?|hr)\s*(?:later)?', 'hours'),
        ]
        
        for pattern, unit in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                number_str = match.group(1)
                number = self._extract_number(number_str)
                if number is not None:
                    logger.info(f"✅ [TIME-PARSER] Extracted: {number} {unit} from '{text}'")
                    return {"number": number, "unit": unit}
        
        return None
    
    async def parse_follow_up_time(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Parse follow-up time from user input like:
        - "call me in 2 minutes"
        - "call me after 5 minutes" ✅ ADDED
        - "call me after five minutes" ✅ ADDED (spelled-out)
        - "call me later"
        - "call me tomorrow"
        - "call me in 1 hour"
        - "call me 5 minutes from now" ✅ ADDED
        
        Returns:
            Dictionary with success, datetime, confidence OR None if cannot parse
        """
        try:
            from datetime import datetime, timedelta
            
            user_input_lower = user_input.lower()
            now = datetime.utcnow()
            
            # ✅ NEW: Use unified number extraction
            extracted = self._extract_number_and_unit(user_input_lower)
            if extracted:
                number = extracted["number"]
                unit = extracted["unit"]
                
                if unit == "minutes":
                    logger.info(f"✅ [TIME-PARSER] Parsed {number} minutes from: '{user_input}'")
                    return {
                        "success": True,
                        "datetime": now + timedelta(minutes=number),
                        "confidence": "high",
                        "type": "minutes"
                    }
                elif unit == "hours":
                    logger.info(f"✅ [TIME-PARSER] Parsed {number} hours from: '{user_input}'")
                    return {
                        "success": True,
                        "datetime": now + timedelta(hours=number),
                        "confidence": "high",
                        "type": "hours"
                    }
            
            # Pattern: "later" (default 30 minutes)
            if 'later' in user_input_lower:
                return {
                    "success": True,
                    "datetime": now + timedelta(minutes=30),
                    "confidence": "medium",
                    "type": "later"
                }
            
            # Pattern: "tomorrow" with optional time
            if 'tomorrow' in user_input_lower:
                target = now + timedelta(days=1)
                
                # Check for specific time like "tomorrow at 10 pm"
                time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?', user_input_lower)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    period = time_match.group(3)
                    
                    if period and 'p' in period.lower() and hour != 12:
                        hour += 12
                    elif period and 'a' in period.lower() and hour == 12:
                        hour = 0
                    
                    target = target.replace(hour=hour, minute=minute, second=0)
                else:
                    target = target.replace(hour=10, minute=0, second=0)  # Default 10 AM
                
                return {
                    "success": True,
                    "datetime": target,
                    "confidence": "high",
                    "type": "tomorrow"
                }
            
            # Pattern: "next week"
            if 'next week' in user_input_lower:
                return {
                    "success": True,
                    "datetime": now + timedelta(weeks=1),
                    "confidence": "medium",
                    "type": "next_week"
                }
            
            logger.info(f"⚠️ Could not parse follow-up time from: {user_input}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing follow-up time: {e}")
            return None
    
    async def parse_time_expression(self, text: str, base_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Parse natural language time expression - ENHANCED"""
        try:
            import dateparser
            from datetime import datetime, timedelta
            
            text_lower = text.lower().strip()
            now = base_time if base_time else datetime.utcnow()
            
            logger.info(f"📅 Parsing time expression: '{text}'")
            
            # ✅ NEW: Use unified number extraction first
            extracted = self._extract_number_and_unit(text_lower)
            if extracted:
                number = extracted["number"]
                unit = extracted["unit"]
                
                if unit == "minutes":
                    target_dt = now + timedelta(minutes=number)
                elif unit == "hours":
                    target_dt = now + timedelta(hours=number)
                else:
                    target_dt = now + timedelta(days=number)
                
                logger.info(f"✅ Relative time parsed: {target_dt}")
                return {
                    "success": True,
                    "datetime": target_dt,
                    "original_text": text,
                    "confidence": 0.95,
                    "type": "relative"
                }
            
            # ✅ Handle specific dates with dateparser
            parsed_date = dateparser.parse(
                text,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'RETURN_AS_TIMEZONE_AWARE': False,
                    'RELATIVE_BASE': now
                }
            )
            
            if parsed_date:
                # If only date was parsed (no time), default to 10 AM
                if parsed_date.hour == 0 and parsed_date.minute == 0:
                    # Check if time was mentioned
                    has_time = any(t in text_lower for t in ['am', 'pm', ':'])
                    if not has_time:
                        parsed_date = parsed_date.replace(hour=10, minute=0)
                
                # Ensure it's in the future
                if parsed_date <= now:
                    parsed_date = parsed_date + timedelta(days=1)
                
                logger.info(f"✅ Date parsed: {parsed_date}")
                return {
                    "success": True,
                    "datetime": parsed_date,
                    "original_text": text,
                    "confidence": 0.85,
                    "type": "absolute"
                }
            
            logger.warning(f"⚠️ Could not parse time from: '{text}'")
            return None
            
        except Exception as e:
            logger.error(f"❌ Time parsing error: {e}")
            return None
    
    async def _parse_minutes(
        self,
        text: str,
        base_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """✅ UPDATED: Specifically parse 'X minutes' patterns with spelled-out number support"""
        try:
            # Use the new unified extraction
            extracted = self._extract_number_and_unit(text)
            if extracted and extracted["unit"] == "minutes":
                minutes = extracted["number"]
                target_time = base_time + timedelta(minutes=minutes)
                
                logger.info(f"✅ Parsed {minutes} minutes from: '{text}'")
                logger.info(f"   Target time: {target_time}")
                
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "relative_minutes",
                    "minutes": minutes
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing minutes: {e}")
            return None
    
    async def _parse_relative_time(
        self,
        text: str,
        base_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse relative time expressions like 'in 2 hours' - UPDATED with spelled-out support"""
        try:
            # ✅ Use unified extraction for hours
            extracted = self._extract_number_and_unit(text)
            if extracted and extracted["unit"] == "hours":
                hours = extracted["number"]
                target_time = base_time + timedelta(hours=hours)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "relative_hours"
                }
            
            # "an hour" / "one hour"
            if re.search(r'(?:in\s+)?(?:an?|one)\s+hour', text):
                target_time = base_time + timedelta(hours=1)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "relative_hours"
                }
            
            # "couple hours"
            if re.search(r'couple\s+(?:of\s+)?hours?', text):
                target_time = base_time + timedelta(hours=2)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "medium",
                    "type": "relative_hours"
                }
            
            # "few hours"
            if re.search(r'few\s+hours?', text):
                target_time = base_time + timedelta(hours=3)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "medium",
                    "type": "relative_hours"
                }
            
            # "half hour" / "30 minutes"
            if re.search(r'half\s+(?:an?\s+)?hour', text):
                target_time = base_time + timedelta(minutes=30)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "relative_minutes"
                }
            
            # Days pattern
            days_match = re.search(r'(?:in\s+)?(\d+)\s*days?', text)
            if days_match:
                days = int(days_match.group(1))
                target_time = base_time + timedelta(days=days)
                target_time = target_time.replace(hour=10, minute=0, second=0)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "relative_days"
                }
            
            # Tomorrow
            if 'tomorrow' in text:
                target_time = base_time + timedelta(days=1)
                
                # Check for specific time
                time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    period = time_match.group(3)
                    
                    if period and period.lower() == 'pm' and hour != 12:
                        hour += 12
                    elif period and period.lower() == 'am' and hour == 12:
                        hour = 0
                    
                    target_time = target_time.replace(hour=hour, minute=minute, second=0)
                else:
                    target_time = target_time.replace(hour=10, minute=0, second=0)
                
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "high",
                    "type": "tomorrow"
                }
            
            # Later today
            if re.search(r'later\s+(?:today|tonight)', text):
                target_time = base_time + timedelta(hours=2)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "medium",
                    "type": "later_today"
                }
            
            # Generic "later" or "soon"
            if re.search(r'(?:call|contact|reach)\s+(?:me\s+)?(?:later|soon)', text):
                target_time = base_time + timedelta(hours=1)
                return {
                    "success": True,
                    "datetime": target_time,
                    "original_text": text,
                    "confidence": "low",
                    "type": "later"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing relative time: {e}")
            return None
    
    async def _parse_specific_day(
        self,
        text: str,
        base_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse specific day expressions like 'next Monday'"""
        try:
            for day_name, day_num in self.day_patterns.items():
                if day_name in text:
                    current_day = base_time.weekday()
                    days_ahead = day_num - current_day
                    
                    if days_ahead <= 0:
                        days_ahead += 7
                    
                    if 'next' in text:
                        days_ahead += 7
                    
                    target_time = base_time + timedelta(days=days_ahead)
                    
                    # Check for specific time
                    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2) or 0)
                        period = time_match.group(3)
                        
                        if period and period.lower() == 'pm' and hour != 12:
                            hour += 12
                        elif period and period.lower() == 'am' and hour == 12:
                            hour = 0
                        
                        target_time = target_time.replace(hour=hour, minute=minute, second=0)
                    else:
                        target_time = target_time.replace(hour=10, minute=0, second=0)
                    
                    return {
                        "success": True,
                        "datetime": target_time,
                        "original_text": text,
                        "confidence": "high",
                        "type": "specific_day"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing specific day: {e}")
            return None
    
    async def _parse_with_dateparser(
        self,
        text: str,
        base_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Use dateparser library for complex expressions"""
        try:
            parsed = dateparser.parse(
                text,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'RELATIVE_BASE': base_time,
                    'RETURN_AS_TIMEZONE_AWARE': False
                }
            )
            
            if parsed and parsed > base_time:
                if parsed.hour == 0 and parsed.minute == 0:
                    parsed = parsed.replace(hour=10, minute=0)
                
                return {
                    "success": True,
                    "datetime": parsed,
                    "original_text": text,
                    "confidence": "medium",
                    "type": "dateparser"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Dateparser error: {e}")
            return None
    
    async def detect_follow_up_intent(self, text: str) -> bool:
        """Detect if user wants a follow-up call/reminder"""
        try:
            text_lower = text.lower()
            
            follow_up_keywords = [
                'call me back',
                'call back',
                'callback',
                'call me in',
                'call me',
                'reach out',
                'contact me',
                'get back to me',
                'follow up',
                'remind me',
                'reminder',
                'schedule a call',
                'in a few minutes',
                'in a few hours',
                'later',
                'tomorrow',
                'next week',
                'after',        # ✅ ADDED: Recognize "after" keyword
                'from now',     # ✅ ADDED: Recognize "from now" phrase
            ]
            
            for keyword in follow_up_keywords:
                if keyword in text_lower:
                    logger.info(f"✅ Follow-up intent detected: '{keyword}' in '{text}'")
                    return True
            
            # ✅ UPDATED: Check for digit OR spelled-out number patterns
            # Build word number pattern
            word_numbers = '|'.join(self.WORD_TO_NUMBER.keys())
            
            # Check for "X minutes" or "X hours" pattern (digits or words)
            if re.search(rf'(?:\d+|{word_numbers})\s*(?:minutes?|mins?|hours?|hrs?)', text_lower):
                logger.info(f"✅ Follow-up intent detected: time pattern in '{text}'")
                return True
            
            # ✅ ADDED: Check for "after X minutes/hours" pattern specifically
            if re.search(rf'after\s+(?:\d+|{word_numbers})\s*(?:minutes?|mins?|hours?|hrs?)', text_lower):
                logger.info(f"✅ Follow-up intent detected: 'after' time pattern in '{text}'")
                return True
            
            # ✅ ADDED: Check for "X minutes/hours from now" pattern
            if re.search(rf'(?:\d+|{word_numbers})\s*(?:minutes?|mins?|hours?|hrs?)\s+(?:from\s+)?now', text_lower):
                logger.info(f"✅ Follow-up intent detected: 'from now' pattern in '{text}'")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error detecting follow-up intent: {e}")
            return False


# Create singleton instance
time_parser_service = TimeParserService()
