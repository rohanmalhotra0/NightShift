"""Stripe payments API routes.

Webhook handler is the trust boundary between Stripe and the database.
Everything in this module is structured around three invariants:

  1. Signature verification runs before any state read or write.
  2. Each event id is processed at most once (idempotency).
  3. The user record is the single source of truth for tier and
     subscription status — every subscription event updates it.
"""

from datetime import datetime
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import stripe

from config import settings
from database import get_db, StripeWebhookEvent, User, UserTier
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def _price_id_to_tier_map() -> dict[str, UserTier]:
    """Build the price-id → tier map from settings at call time.

    Built lazily so tests can override settings before the map is read.
    """
    mapping: dict[str, UserTier] = {}
    if settings.STRIPE_PRICE_ID_STARTER:
        mapping[settings.STRIPE_PRICE_ID_STARTER] = UserTier.STARTER
    if settings.STRIPE_PRICE_ID_PRO:
        mapping[settings.STRIPE_PRICE_ID_PRO] = UserTier.PRO
    if settings.STRIPE_PRICE_ID_MAX:
        mapping[settings.STRIPE_PRICE_ID_MAX] = UserTier.MAX
    return mapping


def _tier_to_price_id(tier: UserTier) -> Optional[str]:
    """Reverse lookup for checkout."""
    if tier is UserTier.STARTER:
        return settings.STRIPE_PRICE_ID_STARTER or None
    if tier is UserTier.PRO:
        return settings.STRIPE_PRICE_ID_PRO or None
    if tier is UserTier.MAX:
        return settings.STRIPE_PRICE_ID_MAX or None
    return None


# Subscription statuses Stripe considers "the customer has access".
# Anything else (canceled, incomplete_expired, unpaid) flips the user
# back to FREE.
ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


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
    status: Optional[str]
    current_period_end: Optional[str]
    cancel_at_period_end: bool


class PricingResponse(BaseModel):
    tiers: list[dict]


class PortalRequest(BaseModel):
    return_url: str


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

    if tier is UserTier.FREE or tier is UserTier.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free tier does not require payment",
        )

    price_id = _tier_to_price_id(tier)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tier {tier.value} is not configured for checkout",
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

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            client_reference_id=str(current_user.id),
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
    """Get current subscription status from the user record.

    Reads the persisted columns rather than calling Stripe — webhooks
    keep these fields fresh, so the API is fast and works offline from
    Stripe.
    """
    return SubscriptionResponse(
        tier=current_user.tier if isinstance(current_user.tier, str) else current_user.tier.value,
        status=current_user.subscription_status,
        current_period_end=(
            current_user.current_period_end.isoformat()
            if current_user.current_period_end
            else None
        ),
        cancel_at_period_end=bool(current_user.cancel_at_period_end),
    )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription at period end.

    The user keeps access until `current_period_end`. The
    `customer.subscription.updated` webhook will land shortly after
    Stripe accepts the modify call and overwrite the flag with
    Stripe's authoritative value, but we set it now so the UI
    reflects the change immediately without waiting for the round trip.
    """
    if not current_user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription",
        )

    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )

    current_user.cancel_at_period_end = True
    db.commit()
    return {
        "message": "Subscription will be cancelled at period end",
        "cancel_at_period_end": True,
    }


@router.post("/resume")
async def resume_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Undo a pending cancellation.

    Only valid while the subscription is still active and scheduled
    to cancel — once Stripe deletes the subscription at period end,
    the user has to go through checkout again.
    """
    if not current_user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription",
        )

    if not current_user.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not scheduled for cancellation",
        )

    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=False,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )

    current_user.cancel_at_period_end = False
    db.commit()
    return {
        "message": "Subscription resumed",
        "cancel_at_period_end": False,
    }


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------


def _find_user_for_subscription(
    db: Session,
    *,
    customer_id: Optional[str],
    user_id: Optional[str],
) -> Optional[User]:
    """Locate the user record for a subscription event.

    Prefers the explicit metadata user_id (set on checkout) and falls
    back to looking up by stripe_customer_id.
    """
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
    if customer_id:
        return (
            db.query(User)
            .filter(User.stripe_customer_id == customer_id)
            .first()
        )
    return None


def _extract_price_id(subscription: dict) -> Optional[str]:
    """Pull the price id from a Stripe subscription object.

    Subscriptions can have multiple items but for our single-product
    pricing the first item's price is authoritative.
    """
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    return price.get("id")


def _resolve_tier(price_id: Optional[str]) -> Optional[UserTier]:
    if not price_id:
        return None
    return _price_id_to_tier_map().get(price_id)


def _apply_subscription_state(
    db: Session,
    user: User,
    subscription: dict,
) -> None:
    """Sync a subscription dict from Stripe onto the user record."""
    sub_status = subscription.get("status")
    user.stripe_subscription_id = subscription.get("id")
    user.subscription_status = sub_status
    user.cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))

    period_end = subscription.get("current_period_end")
    user.current_period_end = (
        datetime.utcfromtimestamp(period_end) if period_end else None
    )

    if sub_status in ACTIVE_STATUSES:
        tier = _resolve_tier(_extract_price_id(subscription))
        if tier is not None:
            user.tier = tier.value
    else:
        user.tier = UserTier.FREE.value

    db.commit()


def _mark_subscription_ended(db: Session, user: User, subscription: dict) -> None:
    """Subscription was deleted — drop the user back to free."""
    user.tier = UserTier.FREE.value
    user.subscription_status = subscription.get("status") or "canceled"
    user.stripe_subscription_id = None
    user.cancel_at_period_end = False
    period_end = subscription.get("current_period_end")
    user.current_period_end = (
        datetime.utcfromtimestamp(period_end) if period_end else None
    )
    db.commit()


def _record_event_or_skip(db: Session, event: dict) -> bool:
    """Record event id atomically. Returns False if already processed.

    We use the primary-key uniqueness of stripe_webhook_events to
    guarantee at-most-once processing under concurrent webhook delivery.
    """
    event_id = event.get("id")
    event_type = event.get("type", "")
    if not event_id:
        # No id means we can't dedupe; treat as fresh and let it run,
        # but log so it's visible.
        logger.warning("stripe webhook missing event id: %s", event_type)
        return True

    record = StripeWebhookEvent(event_id=event_id, event_type=event_type)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def _handle_event(db: Session, event: dict) -> None:
    """Dispatch a verified Stripe event to the right handler."""
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        # Stripe sends the subscription id but not the full subscription
        # object. We can either fetch it or wait for the
        # customer.subscription.created event that Stripe also sends —
        # we update what we can here for fast UX, and the subsequent
        # subscription event will overwrite with authoritative data.
        user_id = (obj.get("metadata") or {}).get("user_id") or obj.get(
            "client_reference_id"
        )
        customer_id = obj.get("customer")
        user = _find_user_for_subscription(
            db, customer_id=customer_id, user_id=user_id
        )
        if not user:
            logger.warning(
                "checkout.session.completed: no user for customer=%s user_id=%s",
                customer_id,
                user_id,
            )
            return
        if customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = customer_id
        sub_id = obj.get("subscription")
        if sub_id:
            user.stripe_subscription_id = sub_id
        # Optimistic: if we know the intended tier from metadata, apply
        # it now. The subscription.updated event will confirm.
        meta_tier = (obj.get("metadata") or {}).get("tier")
        if meta_tier:
            try:
                user.tier = UserTier(meta_tier).value
                user.subscription_status = "active"
            except ValueError:
                pass
        db.commit()
        return

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        customer_id = obj.get("customer")
        user = _find_user_for_subscription(
            db, customer_id=customer_id, user_id=None
        )
        if not user:
            logger.warning(
                "%s: no user for customer=%s", event_type, customer_id
            )
            return
        _apply_subscription_state(db, user, obj)
        return

    if event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        user = _find_user_for_subscription(
            db, customer_id=customer_id, user_id=None
        )
        if not user:
            return
        _mark_subscription_ended(db, user, obj)
        return

    if event_type == "invoice.payment_failed":
        # Stripe will send subscription.updated to past_due as well, but
        # surfacing this explicitly lets us reach a status sooner.
        customer_id = obj.get("customer")
        user = _find_user_for_subscription(
            db, customer_id=customer_id, user_id=None
        )
        if not user:
            return
        user.subscription_status = "past_due"
        db.commit()
        return

    # Unknown / unhandled event types are a no-op — Stripe sends many
    # events we don't care about, and returning 200 prevents retry
    # storms.
    logger.debug("stripe webhook: ignoring event type %s", event_type)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhooks.

    Order of operations is load-bearing: signature first, idempotency
    second, dispatch third. Any handler failure rolls back its own
    write but the event id stays recorded so Stripe doesn't retry into
    a corrupt half-state.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature header")

    if not settings.STRIPE_WEBHOOK_SECRET:
        # Refuse to run unsigned in any environment — silent acceptance
        # is the path to forged events.
        logger.error("STRIPE_WEBHOOK_SECRET not configured; rejecting webhook")
        raise HTTPException(
            status_code=503,
            detail="Webhook secret not configured",
        )

    try:
        # Verify signature (raises on tamper / wrong secret).
        stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Re-parse the payload as a plain dict. construct_event returns a
    # StripeObject whose `.get`/attribute access is intercepted, which
    # makes downstream handlers brittle. Once the signature is verified
    # the bytes are trusted, so json.loads is safe.
    try:
        event = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid payload")

    if not _record_event_or_skip(db, event):
        # Already processed — return 200 so Stripe stops retrying.
        return {"status": "duplicate", "event_id": event.get("id")}

    try:
        _handle_event(db, event)
    except Exception:
        # Roll back any partial state, but the event id record stays.
        # Re-raising returns 500 to Stripe, which will retry — and the
        # idempotency check will short-circuit the retry. This is
        # intentional: better to surface the failure in logs than to
        # silently swallow it. Tune later if it becomes noisy.
        db.rollback()
        logger.exception("stripe webhook handler failed for %s", event.get("id"))
        raise HTTPException(
            status_code=500, detail="Webhook handler error"
        )

    return {"status": "ok", "event_id": event.get("id")}


@router.post("/portal")
async def create_portal_session(
    request: PortalRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe customer portal session.

    The portal lets the user manage their card, invoices, and (if
    Stripe is configured for it) cancel/resume from Stripe's hosted UI.
    Frontends pass `return_url` so Stripe knows where to send users
    when they're done.
    """
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No payment history",
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.return_url,
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )
