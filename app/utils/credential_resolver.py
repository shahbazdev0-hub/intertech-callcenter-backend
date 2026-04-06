"""
Credential resolver with fallback chain for multi-tenant Twilio and Email.

Priority for Twilio:
  1. user.integration_config.twilio (custom credentials)
  2. user.twilio_subaccount_sid/auth_token/phone_number (provisioned from phone purchase)
  3. settings.TWILIO_* (env defaults)

Priority for Email:
  1. user.integration_config.email (custom SMTP)
  2. settings.EMAIL_* (env defaults)
"""

import logging
from typing import Tuple, Optional, Dict, Any
from app.utils.encryption import decrypt
from app.config import settings

logger = logging.getLogger(__name__)


def resolve_twilio_credentials(user: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Resolve Twilio credentials for a user with fallback chain.
    Returns: (account_sid, auth_token, phone_number)
    """
    # Priority 1: Custom integration config
    integration = user.get("integration_config", {}).get("twilio", {})
    if integration.get("account_sid") and integration.get("auth_token"):
        try:
            return (
                integration["account_sid"],
                decrypt(integration["auth_token"]),
                integration.get("phone_number")
            )
        except Exception as e:
            logger.error(f"Failed to decrypt custom Twilio credentials: {e}")

    # Priority 2: Provisioned subaccount (from phone purchase flow)
    if user.get("twilio_subaccount_sid") and user.get("twilio_auth_token"):
        return (
            user["twilio_subaccount_sid"],
            user["twilio_auth_token"],
            user.get("twilio_phone_number")
        )

    # Priority 3: Env defaults
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        return (
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_PHONE_NUMBER
        )

    return (None, None, None)


def resolve_email_credentials(user: dict) -> Dict[str, Any]:
    """
    Resolve Email SMTP credentials for a user with fallback chain.
    Returns dict with smtp_host, smtp_port, smtp_username, smtp_password,
    from_email, from_name.
    """
    # Priority 1: Custom integration config
    integration = user.get("integration_config", {}).get("email", {})
    if integration.get("smtp_host") and integration.get("smtp_password"):
        try:
            return {
                "smtp_host": integration["smtp_host"],
                "smtp_port": integration.get("smtp_port", 587),
                "smtp_username": integration["smtp_username"],
                "smtp_password": decrypt(integration["smtp_password"]),
                "from_email": integration.get("from_email"),
                "from_name": integration.get("from_name", "CallCenter SaaS")
            }
        except Exception as e:
            logger.error(f"Failed to decrypt custom Email credentials: {e}")

    # Priority 2: Env defaults
    return {
        "smtp_host": settings.EMAIL_HOST,
        "smtp_port": settings.EMAIL_PORT,
        "smtp_username": settings.EMAIL_USER,
        "smtp_password": settings.EMAIL_PASSWORD,
        "from_email": settings.EMAIL_FROM,
        "from_name": settings.EMAIL_FROM_NAME
    }
