# backend/app/services/stripe_service.py

import stripe
import logging
from datetime import datetime, timedelta
from app.config import settings
from app.database import get_collection

logger = logging.getLogger(__name__)


class StripeService:
    def __init__(self):
        self._initialized = False

    def _ensure_initialized(self):
        if not self._initialized and settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            self._initialized = True
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("STRIPE_SECRET_KEY is not configured")

    def get_price_id(self, tier_id: str, billing: str) -> str:
        """Map tier + billing cycle to a Stripe Price ID from config."""
        price_map = {
            ("starter", "monthly"): settings.STRIPE_STARTER_MONTHLY_PRICE_ID,
            ("starter", "yearly"): settings.STRIPE_STARTER_YEARLY_PRICE_ID,
            ("pro", "monthly"): settings.STRIPE_PRO_MONTHLY_PRICE_ID,
            ("pro", "yearly"): settings.STRIPE_PRO_YEARLY_PRICE_ID,
            ("enterprise", "monthly"): settings.STRIPE_ENTERPRISE_MONTHLY_PRICE_ID,
            ("enterprise", "yearly"): settings.STRIPE_ENTERPRISE_YEARLY_PRICE_ID,
        }
        price_id = price_map.get((tier_id.lower(), billing.lower()))
        if not price_id:
            raise ValueError(f"No price configured for tier={tier_id}, billing={billing}")
        return price_id

    async def create_customer(self, email: str, name: str, user_id: str) -> str:
        """Create a Stripe Customer and return the customer ID."""
        self._ensure_initialized()
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id},
            )
            # Store stripe_customer_id on user doc
            users = await get_collection("users")
            from bson import ObjectId
            await users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"stripe_customer_id": customer.id, "updated_at": datetime.utcnow()}}
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        user_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout Session and return the session URL."""
        self._ensure_initialized()
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": user_id},
                subscription_data={"metadata": {"user_id": user_id}},
            )
            logger.info(f"Created checkout session {session.id} for user {user_id}")
            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session creation failed: {e}")
            raise

    def construct_webhook_event(self, payload: bytes, sig_header: str):
        """Verify and construct a Stripe webhook event."""
        self._ensure_initialized()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    async def handle_checkout_completed(self, session: dict):
        """Handle checkout.session.completed event."""
        user_id = session.get("metadata", {}).get("user_id")
        if not user_id:
            logger.error("No user_id in checkout session metadata")
            return

        subscription_id = session.get("subscription")
        customer_id = session.get("customer")

        # Determine plan name from the subscription
        plan_name = "pro"  # default
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                if sub.get("items", {}).get("data"):
                    price_id = sub["items"]["data"][0]["price"]["id"]
                    plan_name = self._price_id_to_plan(price_id)
            except Exception as e:
                logger.warning(f"Could not retrieve subscription details: {e}")

        from bson import ObjectId

        # Update user's subscription_plan
        users = await get_collection("users")
        await users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "subscription_plan": plan_name,
                    "stripe_customer_id": customer_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Create/update subscription document
        subscriptions = await get_collection("subscriptions")
        now = datetime.utcnow()
        await subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "plan_name": plan_name,
                    "status": "active",
                    "stripe_subscription_id": subscription_id,
                    "stripe_customer_id": customer_id,
                    "current_period_start": now,
                    "current_period_end": now + timedelta(days=30),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        logger.info(f"Activated {plan_name} subscription for user {user_id}")

        # Phone number provisioning is now user-initiated via /setup/phone-number page
        logger.info(f"User {user_id} will select phone number via setup page")

    async def handle_invoice_paid(self, invoice: dict):
        """Handle invoice.paid event — renew subscription period."""
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return

        subscriptions = await get_collection("subscriptions")
        now = datetime.utcnow()
        await subscriptions.update_one(
            {"stripe_subscription_id": subscription_id},
            {
                "$set": {
                    "status": "active",
                    "current_period_start": now,
                    "current_period_end": now + timedelta(days=30),
                    "updated_at": now,
                }
            },
        )
        logger.info(f"Renewed subscription {subscription_id}")

    async def handle_subscription_deleted(self, subscription: dict):
        """Handle customer.subscription.deleted event."""
        subscription_id = subscription.get("id")
        user_id = subscription.get("metadata", {}).get("user_id")

        subscriptions_col = await get_collection("subscriptions")
        await subscriptions_col.update_one(
            {"stripe_subscription_id": subscription_id},
            {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}},
        )

        # Revert user to free plan
        if user_id:
            from bson import ObjectId
            users = await get_collection("users")
            await users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"subscription_plan": "free", "updated_at": datetime.utcnow()}},
            )
        logger.info(f"Cancelled subscription {subscription_id} for user {user_id}")

    def _price_id_to_plan(self, price_id: str) -> str:
        """Reverse-map a Stripe Price ID to a plan name."""
        starter_ids = [settings.STRIPE_STARTER_MONTHLY_PRICE_ID, settings.STRIPE_STARTER_YEARLY_PRICE_ID]
        pro_ids = [settings.STRIPE_PRO_MONTHLY_PRICE_ID, settings.STRIPE_PRO_YEARLY_PRICE_ID]
        enterprise_ids = [settings.STRIPE_ENTERPRISE_MONTHLY_PRICE_ID, settings.STRIPE_ENTERPRISE_YEARLY_PRICE_ID]

        if price_id in starter_ids:
            return "starter"
        elif price_id in pro_ids:
            return "pro"
        elif price_id in enterprise_ids:
            return "enterprise"
        return "pro"  # fallback

    async def get_user_subscription(self, user_id: str) -> dict:
        """Get the current subscription for a user."""
        subscriptions = await get_collection("subscriptions")
        sub = await subscriptions.find_one({"user_id": user_id})
        if sub:
            sub["_id"] = str(sub["_id"])
        return sub


stripe_service = StripeService()
