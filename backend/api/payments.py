"""Stripe payments API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import stripe

from config import settings
from database import get_db, User, UserTier
from api.auth import get_current_user

router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Price IDs (configure in Stripe dashboard)
PRICE_IDS = {
    UserTier.STARTER: "price_starter_monthly",  # $19/mo
    UserTier.PRO: "price_pro_monthly",  # $39/mo
    UserTier.MAX: "price_max_monthly",  # $69/mo
}

TIER_PRICES = {
    UserTier.STARTER: 1900,  # cents
    UserTier.PRO: 3900,
    UserTier.MAX: 6900,
}


# Request/Response models
class CreateCheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    current_period_end: Optional[str]
    cancel_at_period_end: bool


class PricingResponse(BaseModel):
    tiers: list[dict]


# Routes
@router.get("/pricing", response_model=PricingResponse)
async def get_pricing():
    """Get pricing tiers."""
    return PricingResponse(
        tiers=[
            {
                "id": "starter",
                "name": "Starter",
                "price": 19,
                "apps_per_night": 3,
                "features": [
                    "3 applications per night",
                    "LinkedIn & Indeed scraping",
                    "Basic auto-fill",
                    "Google Sheets logging",
                ],
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": 39,
                "apps_per_night": 10,
                "features": [
                    "10 applications per night",
                    "All job boards",
                    "Advanced auto-fill",
                    "Custom resume selection",
                    "Priority support",
                ],
            },
            {
                "id": "max",
                "name": "Max",
                "price": 69,
                "apps_per_night": 25,
                "features": [
                    "25 applications per night",
                    "All job boards",
                    "AI cover letter generation",
                    "Custom resume + cover letter",
                    "Dedicated support",
                    "Custom scheduling",
                ],
            },
        ]
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe checkout session."""
    try:
        tier = UserTier(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}",
        )

    if tier not in PRICE_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free tier does not require payment",
        )

    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": current_user.id},
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        else:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": PRICE_IDS[tier],
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                "user_id": current_user.id,
                "tier": tier.value,
            },
        )

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
):
    """Get current subscription status."""
    if not current_user.stripe_customer_id:
        return SubscriptionResponse(
            tier=current_user.tier.value,
            status="none",
            current_period_end=None,
            cancel_at_period_end=False,
        )

    try:
        subscriptions = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status="active",
            limit=1,
        )

        if not subscriptions.data:
            return SubscriptionResponse(
                tier=current_user.tier.value,
                status="none",
                current_period_end=None,
                cancel_at_period_end=False,
            )

        sub = subscriptions.data[0]
        from datetime import datetime

        return SubscriptionResponse(
            tier=current_user.tier.value,
            status=sub.status,
            current_period_end=datetime.fromtimestamp(sub.current_period_end).isoformat(),
            cancel_at_period_end=sub.cancel_at_period_end,
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription at period end."""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription",
        )

    try:
        subscriptions = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status="active",
            limit=1,
        )

        if not subscriptions.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription",
            )

        sub = subscriptions.data[0]
        stripe.Subscription.modify(
            sub.id,
            cancel_at_period_end=True,
        )

        return {"message": "Subscription will be cancelled at period end"}

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        tier = session["metadata"].get("tier")

        if user_id and tier:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.tier = UserTier(tier)
                db.commit()

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        user = db.query(User).filter(
            User.stripe_customer_id == customer_id
        ).first()
        if user:
            user.tier = UserTier.FREE
            db.commit()

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]

        if subscription["status"] == "past_due":
            customer_id = subscription["customer"]
            user = db.query(User).filter(
                User.stripe_customer_id == customer_id
            ).first()
            # Could notify user or take action here

    return {"status": "ok"}


@router.post("/portal")
async def create_portal_session(
    return_url: str,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe customer portal session."""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No payment history",
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=return_url,
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )
