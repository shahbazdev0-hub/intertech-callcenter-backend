# backend/app/api/v1/payments.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from app.api.deps import get_current_active_user
from app.services.stripe_service import stripe_service
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class CheckoutRequest(BaseModel):
    tier_id: str  # starter, pro, enterprise
    billing: str  # monthly, yearly


@router.post("/create-checkout-session")
async def create_checkout_session(
    data: CheckoutRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """Create a Stripe Checkout Session for the authenticated user."""
    try:
        # Validate tier and billing
        price_id = stripe_service.get_price_id(data.tier_id, data.billing)

        user_id = str(current_user["_id"])
        email = current_user.get("email", "")
        name = current_user.get("full_name", "")

        # Create or reuse Stripe Customer
        customer_id = current_user.get("stripe_customer_id")
        if not customer_id:
            customer_id = await stripe_service.create_customer(email, name, user_id)

        # Build success/cancel URLs
        frontend_url = settings.FRONTEND_URL
        success_url = f"{frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{frontend_url}/payment/cancel"

        # Create Checkout Session
        checkout_url = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            user_id=user_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {"url": checkout_url}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events. No auth required — verified by signature."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})

    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        await stripe_service.handle_checkout_completed(data_object)
    elif event_type == "invoice.paid":
        await stripe_service.handle_invoice_paid(data_object)
    elif event_type == "customer.subscription.deleted":
        await stripe_service.handle_subscription_deleted(data_object)
    else:
        logger.info(f"Unhandled Stripe event type: {event_type}")

    return {"status": "ok"}


@router.post("/verify-session")
async def verify_session(
    request: Request,
    current_user: dict = Depends(get_current_active_user),
):
    """Verify a Stripe checkout session and activate subscription immediately.

    Called by the frontend after Stripe redirects back with session_id.
    This avoids relying on webhook timing.
    """
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        import stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Verify session belongs to this user
        session_user_id = session.get("metadata", {}).get("user_id", "")
        current_user_id = str(current_user["_id"])
        if session_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to this user")

        # Only process completed sessions
        if session.get("payment_status") != "paid":
            raise HTTPException(status_code=400, detail="Payment not completed")

        # Reuse the same logic as the webhook handler
        await stripe_service.handle_checkout_completed(dict(session))
        logger.info(f"Session {session_id} verified and subscription activated for user {current_user_id}")

        return {"status": "ok", "message": "Subscription activated"}

    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify session")


@router.get("/subscription")
async def get_subscription(
    current_user: dict = Depends(get_current_active_user),
):
    """Get the current user's subscription status."""
    user_id = str(current_user["_id"])
    subscription = await stripe_service.get_user_subscription(user_id)

    if not subscription:
        return {
            "plan_name": current_user.get("subscription_plan", "free"),
            "status": "active" if current_user.get("subscription_plan", "free") != "free" else "none",
            "stripe_subscription_id": None,
        }

    return subscription
