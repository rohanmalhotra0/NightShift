"""End-to-end paywall integration test.

Walks the whole user journey through real HTTP endpoints:

  1. Sign up      → POST /auth/signup
  2. Hit gate     → POST /applications/apply  (expect 402)
  3. Checkout     → POST /payments/checkout   (Stripe stubbed)
  4. Webhook in   → POST /payments/webhook    (real signature)
  5. Verify state → GET  /auth/me             (subscription_status=active)
  6. Pass gate    → POST /applications/apply  (no longer 402)

Stripe HTTP calls are stubbed so no key is needed, but the webhook
itself is signed with the real HMAC scheme and verified by the live
endpoint. That's the high-value bit — it's where forged events would
sneak in if the verification ever regressed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from typing import Any

import pytest
import stripe


SECRET = "whsec_test_dummy"


def _sign(payload: bytes, secret: str = SECRET) -> str:
    ts = int(time.time())
    signed = f"{ts}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


@pytest.fixture
def no_bot(monkeypatch):
    """Don't actually launch Playwright when /apply is hit."""
    monkeypatch.setattr(
        "api.applications.run_application_batch",
        lambda *a, **kw: None,
    )


def test_full_signup_pay_access_journey(
    client, db_session, monkeypatch, webhook_secret, price_ids, no_bot
):
    # --- 1. Sign up ----------------------------------------------------
    signup_res = client.post(
        "/auth/signup",
        json={"email": "journey@example.com", "password": "hunter2hunter2"},
    )
    assert signup_res.status_code == 200, signup_res.text
    token = signup_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Fresh user is on the free tier with no subscription.
    me_initial = client.get("/auth/me", headers=auth_headers).json()
    assert me_initial["tier"] == "free"
    assert me_initial["subscription_status"] is None

    # --- 2. Try to use the gated feature → blocked --------------------
    blocked = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers=auth_headers,
    )
    assert blocked.status_code == 402
    detail = blocked.json()["detail"]
    assert detail["code"] == "subscription_required"
    assert detail["upgrade_url"] == "/pricing"

    # --- 3. Start checkout (Stripe stubbed) ----------------------------
    captured_session: dict[str, Any] = {}

    def fake_customer_create(**kwargs):
        return SimpleNamespace(id="cus_journey")

    def fake_session_create(**kwargs):
        captured_session.update(kwargs)
        return SimpleNamespace(
            id="cs_journey", url="https://checkout.stripe.test/cs_journey"
        )

    monkeypatch.setattr(stripe.Customer, "create", fake_customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create", fake_session_create)

    checkout_res = client.post(
        "/payments/checkout",
        json={
            "tier": "pro",
            "success_url": "https://app.test/checkout/success",
            "cancel_url": "https://app.test/checkout/cancel",
        },
        headers=auth_headers,
    )
    assert checkout_res.status_code == 200
    assert checkout_res.json()["session_id"] == "cs_journey"
    # The session was wired with the right tier-to-price mapping.
    assert captured_session["line_items"][0]["price"] == price_ids["pro"]
    user_id = captured_session["client_reference_id"]

    # --- 4. Stripe POSTs back the webhook ------------------------------
    # checkout.session.completed: the user just paid.
    completed_event = {
        "id": "evt_journey_completed",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_journey",
                "object": "checkout.session",
                "customer": "cus_journey",
                "subscription": "sub_journey",
                "client_reference_id": user_id,
                "metadata": {"user_id": user_id, "tier": "pro"},
            }
        },
    }
    payload = json.dumps(completed_event).encode()
    res = client.post(
        "/payments/webhook",
        content=payload,
        headers={
            "content-type": "application/json",
            "stripe-signature": _sign(payload),
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ok"

    # Stripe also sends customer.subscription.updated with authoritative
    # state — simulate it. After this, status should be active and tier
    # resolved from price id.
    sub_event = {
        "id": "evt_journey_sub_updated",
        "object": "event",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_journey",
                "object": "subscription",
                "customer": "cus_journey",
                "status": "active",
                "current_period_end": int(time.time()) + 30 * 24 * 3600,
                "items": {
                    "object": "list",
                    "data": [
                        {"price": {"id": price_ids["pro"], "object": "price"}}
                    ],
                },
            }
        },
    }
    payload = json.dumps(sub_event).encode()
    res = client.post(
        "/payments/webhook",
        content=payload,
        headers={
            "content-type": "application/json",
            "stripe-signature": _sign(payload),
        },
    )
    assert res.status_code == 200, res.text

    # --- 5. /auth/me reflects the subscription -------------------------
    me_paid = client.get("/auth/me", headers=auth_headers).json()
    assert me_paid["tier"] == "pro"
    assert me_paid["subscription_status"] == "active"
    assert me_paid["current_period_end"] is not None

    # --- 6. The same gated call now succeeds ---------------------------
    allowed = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers=auth_headers,
    )
    assert allowed.status_code != 402, allowed.text


def test_journey_cancellation_revokes_access(
    client, db_session, monkeypatch, webhook_secret, price_ids, no_bot
):
    """Active → canceled webhook should immediately re-paywall the user."""
    # Bootstrap: signup + simulate active sub via direct DB write so the
    # body of the test focuses on the cancel path.
    signup_res = client.post(
        "/auth/signup",
        json={"email": "ex-paid@example.com", "password": "hunter2hunter2"},
    )
    token = signup_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]

    # Promote to pro/active in the DB.
    from database import User as UserModel
    user = db_session.query(UserModel).filter_by(id=user_id).one()
    user.tier = "pro"
    user.subscription_status = "active"
    user.stripe_customer_id = "cus_to_be_canceled"
    user.stripe_subscription_id = "sub_to_be_canceled"
    db_session.commit()

    # Sanity: gate is open right now.
    pre = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers=auth_headers,
    )
    assert pre.status_code != 402

    # Stripe sends customer.subscription.deleted.
    cancel_event = {
        "id": "evt_journey_canceled",
        "object": "event",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_to_be_canceled",
                "object": "subscription",
                "customer": "cus_to_be_canceled",
                "status": "canceled",
            }
        },
    }
    payload = json.dumps(cancel_event).encode()
    res = client.post(
        "/payments/webhook",
        content=payload,
        headers={
            "content-type": "application/json",
            "stripe-signature": _sign(payload),
        },
    )
    assert res.status_code == 200

    # Gate slammed shut.
    post = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers=auth_headers,
    )
    assert post.status_code == 402
    assert post.json()["detail"]["code"] == "subscription_required"
