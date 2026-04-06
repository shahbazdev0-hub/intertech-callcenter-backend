# app/services/twilio_provisioning.py

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from twilio.rest import Client
from bson import ObjectId

from app.config import settings
from app.database import get_collection

logger = logging.getLogger(__name__)


class TwilioProvisioningService:
    """Handles creating Twilio subaccounts and purchasing phone numbers for new users."""

    def __init__(self):
        self._main_client: Optional[Client] = None

    def _get_main_client(self) -> Client:
        """Lazily initialize the main Twilio client."""
        if not self._main_client:
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                raise ValueError("Main Twilio credentials not configured")
            self._main_client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
        return self._main_client

    # --- Low-level sync operations (wrapped via asyncio.to_thread) ---

    def _create_subaccount(self, friendly_name: str) -> Dict[str, str]:
        """Create a Twilio subaccount. Returns {sid, auth_token}."""
        client = self._get_main_client()
        account = client.api.accounts.create(friendly_name=friendly_name)
        logger.info(f"Created Twilio subaccount: {account.sid}")
        return {
            "sid": account.sid,
            "auth_token": account.auth_token,
        }

    def _purchase_phone_number(
        self,
        subaccount_sid: str,
        subaccount_auth_token: str,
        country_code: str,
        area_code: Optional[str] = None,
    ) -> Dict[str, str]:
        """Search for and purchase a phone number on the subaccount."""
        sub_client = Client(subaccount_sid, subaccount_auth_token)

        # Search for available local numbers
        search_kwargs = {"voice_enabled": True, "limit": 1}
        if area_code:
            search_kwargs["area_code"] = area_code

        available = sub_client.available_phone_numbers(country_code).local.list(
            **search_kwargs
        )

        # Fallback: try without area code if no numbers found
        if not available and area_code:
            logger.warning(
                f"No numbers for area_code={area_code}, trying without area code"
            )
            available = sub_client.available_phone_numbers(country_code).local.list(
                voice_enabled=True, limit=1
            )

        if not available:
            raise RuntimeError(
                f"No phone numbers available for country={country_code}"
            )

        chosen = available[0]

        # Purchase the number
        incoming = sub_client.incoming_phone_numbers.create(
            phone_number=chosen.phone_number
        )

        logger.info(f"Purchased phone number: {incoming.phone_number} (SID: {incoming.sid})")
        return {
            "phone_number": incoming.phone_number,
            "phone_number_sid": incoming.sid,
        }

    def _configure_webhooks(
        self,
        subaccount_sid: str,
        subaccount_auth_token: str,
        phone_number_sid: str,
        webhook_base_url: str,
    ) -> None:
        """Set the voice URL and status callback on the purchased number."""
        sub_client = Client(subaccount_sid, subaccount_auth_token)
        sub_client.incoming_phone_numbers(phone_number_sid).update(
            voice_url=f"{webhook_base_url}/incoming",
            voice_method="POST",
            status_callback=f"{webhook_base_url}/status",
            status_callback_method="POST",
        )
        logger.info(f"Configured webhooks for number {phone_number_sid}")

    # --- Search available numbers (no purchase) ---

    def search_available_numbers(
        self,
        country_code: str = "CA",
        area_code: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """Search available phone numbers WITHOUT purchasing."""
        client = self._get_main_client()
        search_kwargs = {"voice_enabled": True, "sms_enabled": True, "limit": limit}
        if area_code:
            search_kwargs["area_code"] = area_code

        available = client.available_phone_numbers(country_code).local.list(
            **search_kwargs
        )

        return [
            {
                "phone_number": num.phone_number,
                "friendly_name": num.friendly_name,
                "locality": getattr(num, "locality", "") or "",
                "region": getattr(num, "region", "") or "",
                "country_code": country_code,
            }
            for num in available
        ]

    # --- Provision with user-selected number ---

    async def provision_user_with_selected_number(
        self, user_id: str, phone_number: str, country_code: str = "CA"
    ) -> Dict[str, Any]:
        """
        Provision flow with a user-selected phone number:
        1. Check idempotency
        2. Create subaccount
        3. Purchase the SPECIFIC number on the subaccount
        4. Configure webhooks
        5. Store on user document
        """
        users = await get_collection("users")
        user = await users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.get("twilio_subaccount_sid"):
            logger.info(f"User {user_id} already provisioned, skipping")
            return {
                "already_provisioned": True,
                "twilio_phone_number": user.get("twilio_phone_number"),
            }

        friendly_name = f"Vendira - {user.get('full_name', user.get('email', user_id))}"

        # Step 1: Create subaccount
        logger.info(f"Creating Twilio subaccount for user {user_id}")
        sub = await asyncio.to_thread(self._create_subaccount, friendly_name)

        # Step 2: Purchase the SPECIFIC number on subaccount
        logger.info(f"Purchasing selected number {phone_number} on subaccount {sub['sid']}")
        sub_client = Client(sub["sid"], sub["auth_token"])
        incoming = await asyncio.to_thread(
            lambda: sub_client.incoming_phone_numbers.create(phone_number=phone_number)
        )
        number_info = {
            "phone_number": incoming.phone_number,
            "phone_number_sid": incoming.sid,
        }

        # Step 3: Configure webhooks
        webhook_base_url = settings.TWILIO_WEBHOOK_URL
        if webhook_base_url and webhook_base_url.endswith("/incoming"):
            webhook_base_url = webhook_base_url.replace("/incoming", "")
        logger.info(f"Configuring webhooks for {number_info['phone_number']}")
        await asyncio.to_thread(
            self._configure_webhooks,
            sub["sid"],
            sub["auth_token"],
            number_info["phone_number_sid"],
            webhook_base_url,
        )

        # Step 4: Store on user document
        await users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "twilio_subaccount_sid": sub["sid"],
                    "twilio_auth_token": sub["auth_token"],
                    "twilio_phone_number": number_info["phone_number"],
                    "twilio_phone_number_sid": number_info["phone_number_sid"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"Provisioned {number_info['phone_number']} for user {user_id} "
            f"(subaccount {sub['sid']})"
        )

        return {
            "already_provisioned": False,
            "twilio_subaccount_sid": sub["sid"],
            "twilio_phone_number": number_info["phone_number"],
            "twilio_phone_number_sid": number_info["phone_number_sid"],
        }

    # --- High-level async orchestrator (legacy auto-provision) ---

    async def provision_user_phone(self, user_id: str) -> Dict[str, Any]:
        """
        Full provisioning flow:
        1. Check if already provisioned (idempotent)
        2. Create Twilio subaccount
        3. Purchase phone number
        4. Configure webhooks
        5. Store on user document
        """
        users = await get_collection("users")
        user = await users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Skip if already provisioned
        if user.get("twilio_subaccount_sid"):
            logger.info(f"User {user_id} already has Twilio subaccount, skipping")
            return {
                "already_provisioned": True,
                "twilio_phone_number": user.get("twilio_phone_number"),
            }

        friendly_name = f"Vendira - {user.get('full_name', user.get('email', user_id))}"

        # Step 1: Create subaccount
        logger.info(f"Creating Twilio subaccount for user {user_id}")
        sub = await asyncio.to_thread(self._create_subaccount, friendly_name)

        # Step 2: Purchase phone number
        logger.info(f"Purchasing phone number for subaccount {sub['sid']}")
        number = await asyncio.to_thread(
            self._purchase_phone_number,
            sub["sid"],
            sub["auth_token"],
            settings.TWILIO_DEFAULT_COUNTRY_CODE,
            settings.TWILIO_DEFAULT_AREA_CODE,
        )

        # Step 3: Configure webhooks
        webhook_base_url = settings.TWILIO_WEBHOOK_URL
        if webhook_base_url and webhook_base_url.endswith("/incoming"):
            webhook_base_url = webhook_base_url.replace("/incoming", "")
        logger.info(f"Configuring webhooks for {number['phone_number']}")
        await asyncio.to_thread(
            self._configure_webhooks,
            sub["sid"],
            sub["auth_token"],
            number["phone_number_sid"],
            webhook_base_url,
        )

        # Step 4: Store on user document
        await users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "twilio_subaccount_sid": sub["sid"],
                    "twilio_auth_token": sub["auth_token"],
                    "twilio_phone_number": number["phone_number"],
                    "twilio_phone_number_sid": number["phone_number_sid"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"Provisioned {number['phone_number']} for user {user_id} "
            f"(subaccount {sub['sid']})"
        )

        return {
            "already_provisioned": False,
            "twilio_subaccount_sid": sub["sid"],
            "twilio_phone_number": number["phone_number"],
            "twilio_phone_number_sid": number["phone_number_sid"],
        }


# Singleton
twilio_provisioning_service = TwilioProvisioningService()
