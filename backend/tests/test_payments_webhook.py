"""Tests for Stripe webhook hardening.

Coverage:
  - signature verification (missing, invalid, valid)
  - missing/empty webhook secret refuses to process
  - idempotency on event id
  - status transitions: checkout completed → active → past_due → canceled
  - tier resolution from price id
  - unknown event types are 200/no-op
  - unknown customer is 200/no-op (so Stripe doesn't retry forever)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime

import pytest

from database import StripeWebhookEvent, User, UserTier
from api import payments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign(payload: bytes, secret: str, *, ts: int | None = None) -> str:
    """Produce a valid `Stripe-Signature` header for a payload.

    Mirrors stripe.WebhookSignature scheme: `t=<ts>,v1=<hmac_sha256>`.
    """
    ts = ts or int(time.time())
    signed = f"{ts}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _post_event(client, event: dict, *, secret: str, sign: bool = True) -> object:
    payload = json.dumps(event).encode()
    headers = {"content-type": "application/json"}
    if sign:
        headers["stripe-signature"] = _sign(payload, secret)
    return client.post("/payments/webhook", content=payload, headers=headers)


def _make_user(db_session, **overrides) -> User:
    user = User(
        email=overrides.get("email", "alice@example.com"),
        password_hash="x",
        stripe_customer_id=overrides.get("stripe_customer_id", "cus_test_alice"),
        tier=overrides.get("tier", UserTier.FREE.value),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _subscription_event(
    *,
    event_id: str,
    event_type: str,
    customer_id: str,
    subscription_id: str = "sub_test_1",
    status: str = "active",
    price_id: str = "price_pro_test",
    period_end_ts: int | None = None,
    cancel_at_period_end: bool = False,
) -> dict:
    period_end_ts = period_end_ts or (int(time.time()) + 30 * 24 * 3600)
    # `object: "event"` marks this as a v1 event (vs v2.core.event) so
    # the Stripe SDK's construct_event happy-paths through.
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {
            "object": {
                "id": subscription_id,
                "object": "subscription",
                "customer": customer_id,
                "status": status,
                "current_period_end": period_end_ts,
                "cancel_at_period_end": cancel_at_period_end,
                "items": {
                    "object": "list",
                    "data": [{"price": {"id": price_id, "object": "price"}}],
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def test_webhook_rejects_missing_signature(client, webhook_secret):
    res = client.post(
        "/payments/webhook",
        content=b'{"id":"evt_x","type":"ping"}',
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()


def test_webhook_rejects_invalid_signature(client, webhook_secret):
    res = client.post(
        "/payments/webhook",
        content=b'{"id":"evt_x","type":"ping"}',
        headers={
            "content-type": "application/json",
            "stripe-signature": "t=1,v1=deadbeef",
        },
    )
    assert res.status_code == 400


def test_webhook_rejects_when_secret_unconfigured(client, monkeypatch):
    # Simulate prod misconfig: secret is empty.
    from config import settings as live_settings

    monkeypatch.setattr(live_settings, "STRIPE_WEBHOOK_SECRET", "")
    res = client.post(
        "/payments/webhook",
        content=b'{}',
        headers={
            "content-type": "application/json",
            "stripe-signature": "t=1,v1=deadbeef",
        },
    )
    assert res.status_code == 503


def test_webhook_accepts_valid_signature(client, db_session, webhook_secret, price_ids):
    user = _make_user(db_session)
    event = _subscription_event(
        event_id="evt_signed_1",
        event_type="customer.subscription.created",
        customer_id=user.stripe_customer_id,
        price_id=price_ids["pro"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_webhook_is_idempotent_on_event_id(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session)
    event = _subscription_event(
        event_id="evt_dupe_1",
        event_type="customer.subscription.created",
        customer_id=user.stripe_customer_id,
        price_id=price_ids["starter"],
    )

    first = _post_event(client, event, secret=webhook_secret)
    second = _post_event(client, event, secret=webhook_secret)

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    # Only one event row was recorded.
    rows = db_session.query(StripeWebhookEvent).filter_by(event_id="evt_dupe_1").all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def test_checkout_completed_marks_user_active(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session)
    event = {
        "id": "evt_checkout_1",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "object": "checkout.session",
                "customer": user.stripe_customer_id,
                "subscription": "sub_test_99",
                "client_reference_id": user.id,
                "metadata": {"user_id": user.id, "tier": "pro"},
            }
        },
    }
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.tier == "pro"
    assert refreshed.subscription_status == "active"
    assert refreshed.stripe_subscription_id == "sub_test_99"


def test_subscription_created_resolves_tier_from_price_id(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session, tier=UserTier.FREE.value)
    event = _subscription_event(
        event_id="evt_subcreated_1",
        event_type="customer.subscription.created",
        customer_id=user.stripe_customer_id,
        price_id=price_ids["max"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.tier == UserTier.MAX.value
    assert refreshed.subscription_status == "active"
    assert refreshed.stripe_subscription_id == "sub_test_1"
    assert refreshed.current_period_end is not None
    assert isinstance(refreshed.current_period_end, datetime)


def test_subscription_updated_to_past_due_keeps_access(
    client, db_session, webhook_secret, price_ids
):
    """past_due is in ACTIVE_STATUSES — Stripe keeps trying to charge."""
    user = _make_user(db_session, tier=UserTier.PRO.value)
    user.stripe_subscription_id = "sub_test_1"
    db_session.commit()

    event = _subscription_event(
        event_id="evt_pastdue_1",
        event_type="customer.subscription.updated",
        customer_id=user.stripe_customer_id,
        status="past_due",
        price_id=price_ids["pro"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.subscription_status == "past_due"
    # Tier preserved while Stripe retries the charge.
    assert refreshed.tier == UserTier.PRO.value


def test_subscription_updated_to_canceled_drops_to_free(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session, tier=UserTier.PRO.value)
    event = _subscription_event(
        event_id="evt_canceled_1",
        event_type="customer.subscription.updated",
        customer_id=user.stripe_customer_id,
        status="canceled",
        price_id=price_ids["pro"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.tier == UserTier.FREE.value
    assert refreshed.subscription_status == "canceled"


def test_subscription_deleted_drops_to_free(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session, tier=UserTier.MAX.value)
    user.stripe_subscription_id = "sub_test_1"
    user.cancel_at_period_end = True
    db_session.commit()

    event = _subscription_event(
        event_id="evt_deleted_1",
        event_type="customer.subscription.deleted",
        customer_id=user.stripe_customer_id,
        status="canceled",
        price_id=price_ids["max"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.tier == UserTier.FREE.value
    assert refreshed.subscription_status == "canceled"
    assert refreshed.stripe_subscription_id is None
    # Stale cancel flag from before deletion should be cleared so the
    # user can re-subscribe cleanly.
    assert refreshed.cancel_at_period_end is False


def test_subscription_updated_persists_cancel_at_period_end(
    client, db_session, webhook_secret, price_ids
):
    """Stripe's authoritative `cancel_at_period_end` is mirrored to the
    user record so the UI can show 'cancels on <date>' without fetching
    Stripe on every page load.
    """
    user = _make_user(db_session, tier=UserTier.PRO.value)

    pending_cancel = _subscription_event(
        event_id="evt_cancel_pending_1",
        event_type="customer.subscription.updated",
        customer_id=user.stripe_customer_id,
        price_id=price_ids["pro"],
        cancel_at_period_end=True,
    )
    res = _post_event(client, pending_cancel, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.cancel_at_period_end is True
    # Tier is preserved — they keep paid access until period end.
    assert refreshed.tier == UserTier.PRO.value

    # Reverse the cancellation via Stripe (resume).
    resumed = _subscription_event(
        event_id="evt_cancel_resumed_1",
        event_type="customer.subscription.updated",
        customer_id=user.stripe_customer_id,
        price_id=price_ids["pro"],
        cancel_at_period_end=False,
    )
    res = _post_event(client, resumed, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.cancel_at_period_end is False


def test_invoice_payment_failed_marks_past_due(
    client, db_session, webhook_secret, price_ids
):
    user = _make_user(db_session, tier=UserTier.PRO.value)
    event = {
        "id": "evt_invoice_failed_1",
        "object": "event",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test_1",
                "object": "invoice",
                "customer": user.stripe_customer_id,
            }
        },
    }
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.subscription_status == "past_due"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_event_type_is_noop(client, db_session, webhook_secret):
    event = {
        "id": "evt_unknown_1",
        "object": "event",
        "type": "charge.refunded",
        "data": {"object": {}},
    }
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_unknown_customer_is_noop(client, db_session, webhook_secret, price_ids):
    """Stripe sometimes sends events for customers we don't have yet
    (race between checkout and our DB write). Don't 500 — that triggers
    retry storms."""
    event = _subscription_event(
        event_id="evt_unknown_cust_1",
        event_type="customer.subscription.created",
        customer_id="cus_does_not_exist",
        price_id=price_ids["pro"],
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200


def test_tier_resolution_unknown_price_keeps_status(
    client, db_session, webhook_secret, price_ids
):
    """If Stripe sends a price id we don't recognize, we set status but
    don't guess at a tier."""
    user = _make_user(db_session, tier=UserTier.FREE.value)
    event = _subscription_event(
        event_id="evt_unknown_price_1",
        event_type="customer.subscription.created",
        customer_id=user.stripe_customer_id,
        price_id="price_unknown_xyz",
    )
    res = _post_event(client, event, secret=webhook_secret)
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.subscription_status == "active"
    assert refreshed.tier == UserTier.FREE.value


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_price_id_to_tier_map_skips_unset_ids(monkeypatch):
    from config import settings as live_settings

    monkeypatch.setattr(live_settings, "STRIPE_PRICE_ID_STARTER", "price_s")
    monkeypatch.setattr(live_settings, "STRIPE_PRICE_ID_PRO", "")
    monkeypatch.setattr(live_settings, "STRIPE_PRICE_ID_MAX", "price_m")

    mapping = payments._price_id_to_tier_map()
    assert mapping == {"price_s": UserTier.STARTER, "price_m": UserTier.MAX}


def test_extract_price_id_returns_none_when_no_items():
    assert payments._extract_price_id({"items": {"data": []}}) is None
    assert payments._extract_price_id({}) is None
    assert (
        payments._extract_price_id({"items": {"data": [{"price": {"id": "p_1"}}]}})
        == "p_1"
    )
