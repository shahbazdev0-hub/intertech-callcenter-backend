"""
card_validator.py
Python port of CardValidator.js for the voice AI payment flow.

Includes:
- Luhn algorithm (instant, offline)
- Card type detection (Visa, Mastercard, Amex, etc.)
- Expiry date validation (not expired, not too far in future)
- CVC length validation (3 or 4 depending on card type)
- BIN lookup via binlist.net (async, non-blocking, best-effort)
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import httpx  # already in fastapi ecosystem; async-friendly

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Card type patterns (IIN/BIN ranges) — same logic as JS original
# ---------------------------------------------------------------------------
CARD_PATTERNS: Dict[str, Dict[str, Any]] = {
    "visa": {
        "pattern": re.compile(r"^4[0-9]{12}(?:[0-9]{3,6})?$"),
        "lengths": [13, 16, 19],
        "cvc_length": 3,
        "name": "Visa",
    },
    "mastercard": {
        "pattern": re.compile(
            r"^(5[1-5][0-9]{14}|2(22[1-9]|2[3-9][0-9]|[3-6][0-9]{2}|7[01][0-9]|720)[0-9]{12})$"
        ),
        "lengths": [16],
        "cvc_length": 3,
        "name": "Mastercard",
    },
    "amex": {
        "pattern": re.compile(r"^3[47][0-9]{13}$"),
        "lengths": [15],
        "cvc_length": 4,
        "name": "American Express",
    },
    "discover": {
        "pattern": re.compile(r"^6(?:011|5[0-9]{2})[0-9]{12}$"),
        "lengths": [16, 19],
        "cvc_length": 3,
        "name": "Discover",
    },
    "diners": {
        "pattern": re.compile(r"^3(?:0[0-5]|[68][0-9])[0-9]{11}$"),
        "lengths": [14],
        "cvc_length": 3,
        "name": "Diners Club",
    },
    "jcb": {
        "pattern": re.compile(r"^(?:2131|1800|35\d{3})\d{11}$"),
        "lengths": [15, 16],
        "cvc_length": 3,
        "name": "JCB",
    },
    "unionpay": {
        "pattern": re.compile(r"^62[0-9]{14,17}$"),
        "lengths": [16, 17, 18, 19],
        "cvc_length": 3,
        "name": "UnionPay",
    },
    "maestro": {
        "pattern": re.compile(
            r"^(5018|5020|5038|5893|6304|6759|6761|6762|6763)[0-9]{8,15}$"
        ),
        "lengths": list(range(12, 20)),
        "cvc_length": 3,
        "name": "Maestro",
    },
}

# BIN lookup cache: { bin_prefix: (data, timestamp) }
_bin_cache: Dict[str, tuple] = {}
_BIN_CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Core validation functions
# ---------------------------------------------------------------------------

def luhn_validate(card_number: str) -> bool:
    """Luhn algorithm (ISO/IEC 7812-1) — the standard credit card checksum."""
    total = 0
    reverse = card_number[::-1]
    for i, ch in enumerate(reverse):
        digit = int(ch)
        if i % 2 == 1:           # every second digit from the right
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def detect_card_type(card_number: str) -> Dict[str, Any]:
    """Return card type info dict based on IIN/BIN patterns."""
    for card_type, info in CARD_PATTERNS.items():
        if info["pattern"].match(card_number):
            return {
                "type": card_type,
                "name": info["name"],
                "cvc_length": info["cvc_length"],
                "valid_lengths": info["lengths"],
            }

    # Fallback: first-digit heuristics (same as JS original)
    first1 = card_number[0] if card_number else ""
    first2 = card_number[:2]
    first4 = card_number[:4]

    if first1 == "4":
        return {"type": "visa", "name": "Visa", "cvc_length": 3}
    if "51" <= first2 <= "55":
        return {"type": "mastercard", "name": "Mastercard", "cvc_length": 3}
    if first2 in ("34", "37"):
        return {"type": "amex", "name": "American Express", "cvc_length": 4}
    if first2 == "62":
        return {"type": "unionpay", "name": "UnionPay", "cvc_length": 3}
    if first4 == "6011" or first2 == "65":
        return {"type": "discover", "name": "Discover", "cvc_length": 3}

    return {"type": "unknown", "name": "Unknown", "cvc_length": 3}


def validate_card_number(card_number: str) -> Dict[str, Any]:
    """
    Validate a card number synchronously (Luhn + type detection).
    Returns dict with keys: valid, error, card_type, voice_message.
    """
    digits = re.sub(r"\D", "", card_number)

    if not digits:
        return {
            "valid": False,
            "error": "no_digits",
            "voice_message": "I didn't get any digits. Could you please read your card number again?",
        }

    if len(digits) not in range(13, 20):
        return {
            "valid": False,
            "error": "invalid_length",
            "digit_count": len(digits),
            "voice_message": (
                f"I only got {len(digits)} digits. "
                "Please say all 16 digits of your card number clearly."
            ),
        }

    if not luhn_validate(digits):
        logger.info(f"💳 [LUHN] Failed for card ending in {digits[-4:]}")
        return {
            "valid": False,
            "error": "luhn_failed",
            "voice_message": (
                "I'm sorry, but that card number doesn't appear to be valid. "
                "Could you please read the digits again slowly?"
            ),
        }

    card_type = detect_card_type(digits)
    logger.info(f"💳 [CARD-VALID] {card_type['name']} card ending in {digits[-4:]} passed Luhn")
    return {
        "valid": True,
        "card_number": digits,
        "card_type": card_type,
        "last4": digits[-4:],
        "voice_message": f"I've verified your {card_type['name']} card.",
    }


def validate_expiry(expiry: str) -> Dict[str, Any]:
    """
    Validate expiry date string in MM/YY format (as returned by _extract_expiry_date).
    Returns dict with keys: valid, error, voice_message.
    """
    try:
        parts = expiry.strip().split("/")
        if len(parts) != 2:
            raise ValueError("bad format")
        month = int(parts[0])
        year_raw = int(parts[1])
        year = year_raw + 2000 if year_raw < 100 else year_raw

        if not (1 <= month <= 12):
            return {
                "valid": False,
                "error": "invalid_month",
                "voice_message": "That month doesn't look right. Could you say the expiry date again?",
            }

        now = datetime.utcnow()
        if year < now.year or (year == now.year and month < now.month):
            return {
                "valid": False,
                "error": "expired",
                "voice_message": (
                    "I'm sorry, but that card has expired. "
                    "Do you have another card you'd like to use?"
                ),
            }

        if year > now.year + 20:
            return {
                "valid": False,
                "error": "invalid_year",
                "voice_message": (
                    "The expiry year seems incorrect. "
                    "Could you say the expiry date again?"
                ),
            }

        return {"valid": True, "month": month, "year": year}

    except Exception:
        return {
            "valid": False,
            "error": "parse_error",
            "voice_message": (
                "I didn't catch the expiry date. "
                "Please say it as month and year, for example 'twelve twenty six'."
            ),
        }


def validate_cvc(cvc: str, card_type: str) -> Dict[str, Any]:
    """
    Validate CVC length for the given card type.
    Amex requires 4 digits; all others require 3.
    """
    digits = re.sub(r"\D", "", cvc)
    expected = 4 if card_type == "amex" else 3
    if len(digits) != expected:
        card_name = "American Express" if card_type == "amex" else "this card"
        return {
            "valid": False,
            "error": "cvc_length",
            "voice_message": (
                f"The security code for {card_name} should be {expected} digits. "
                f"Could you say it again?"
            ),
        }
    return {"valid": True, "cvc": digits}


# ---------------------------------------------------------------------------
# Async BIN lookup (best-effort, non-blocking)
# ---------------------------------------------------------------------------

async def lookup_bin(card_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up BIN/IIN via binlist.net (free, no API key).
    Returns None on any failure — callers must treat this as optional.
    Times out in 4 seconds to avoid slowing the voice call.
    """
    import time

    bin_prefix = card_number[:6]
    cache_key = f"bin_{bin_prefix}"

    # Check cache
    if cache_key in _bin_cache:
        data, ts = _bin_cache[cache_key]
        if time.time() - ts < _BIN_CACHE_TTL:
            return data

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                f"https://lookup.binlist.net/{bin_prefix}",
                headers={"Accept-Version": "3"},
            )
            if resp.status_code == 200:
                raw = resp.json()
                data = {
                    "bin": bin_prefix,
                    "scheme": raw.get("scheme"),
                    "type": raw.get("type"),          # debit / credit
                    "brand": raw.get("brand"),
                    "prepaid": raw.get("prepaid"),
                    "country": (raw.get("country") or {}).get("name"),
                    "bank": (raw.get("bank") or {}).get("name"),
                }
                _bin_cache[cache_key] = (data, time.time())
                logger.info(
                    f"📊 [BIN] {data.get('scheme')} {data.get('type')} "
                    f"from {data.get('bank', 'Unknown')} ({data.get('country')})"
                )
                return data
    except Exception as e:
        logger.debug(f"⚠️ [BIN] Lookup failed (non-critical): {e}")

    return None
