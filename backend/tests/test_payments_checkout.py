"""Tests for the Stripe checkout-session and billing-portal endpoints.

`/payments/checkout` and `/payments/portal` both call Stripe over the
network in production. These tests stub the Stripe SDK so the auth +
validation paths can be exercised hermetically — no network, no API
key required.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import stripe

from api import payments
from api.auth import create_access_token, hash_password
from database import User, UserPrefs, UserTier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    db_session,
    *,
    email: str = "alice@example.com",
    tier: str = UserTier.FREE.value,
    stripe_customer_id: str | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("hunter2hunter2"),
        tier=tier,
        stripe_customer_id=stripe_customer_id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserPrefs(user_id=user.id))
    db_session.commit()
    return user


def _token_for(user: User) -> str:
    token, _ = create_access_token(str(user.id), user.is_admin)
    return token


# ---------------------------------------------------------------------------
# /payments/checkout
# ---------------------------------------------------------------------------


def test_checkout_unauthenticated_returns_401_or_403(client):
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "pro",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
    )
    assert res.status_code in (401, 403)


def test_checkout_rejects_invalid_tier(client, db_session, price_ids):
    user = _make_user(db_session)
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "platinum",  # not a real tier
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400
    assert "invalid tier" in res.json()["detail"].lower()


def test_checkout_rejects_free_tier(client, db_session, price_ids):
    user = _make_user(db_session)
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "free",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400
    assert "free" in res.json()["detail"].lower()


def test_checkout_returns_503_when_price_id_unconfigured(
    client, db_session, monkeypatch
):
    """Tier with no STRIPE_PRICE_ID_* set is unbookable — fail loud."""
    from config import settings as live_settings

    monkeypatch.setattr(live_settings, "STRIPE_PRICE_ID_PRO", "")
    user = _make_user(db_session)
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "pro",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_checkout_creates_customer_when_missing(
    client, db_session, monkeypatch, price_ids
):
    """First-time checkout should mint a Stripe customer and persist the
    id back on the user — subsequent checkouts reuse it."""
    created_customers: list[dict[str, Any]] = []
    created_sessions: list[dict[str, Any]] = []

    def fake_customer_create(**kwargs):
        created_customers.append(kwargs)
        return SimpleNamespace(id="cus_freshly_minted")

    def fake_session_create(**kwargs):
        created_sessions.append(kwargs)
        return SimpleNamespace(
            id="cs_test_abc", url="https://checkout.stripe.test/cs_test_abc"
        )

    monkeypatch.setattr(stripe.Customer, "create", fake_customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create", fake_session_create)

    user = _make_user(db_session, email="new@example.com")
    assert user.stripe_customer_id is None

    res = client.post(
        "/payments/checkout",
        json={
            "tier": "pro",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["session_id"] == "cs_test_abc"
    assert body["checkout_url"].startswith("https://checkout.stripe")

    # Customer was created with this user's email and id metadata.
    assert len(created_customers) == 1
    assert created_customers[0]["email"] == "new@example.com"
    assert created_customers[0]["metadata"]["user_id"] == user.id

    # Session call wired the right price + mode.
    assert len(created_sessions) == 1
    sess = created_sessions[0]
    assert sess["customer"] == "cus_freshly_minted"
    assert sess["mode"] == "subscription"
    assert sess["line_items"][0]["price"] == price_ids["pro"]
    assert sess["client_reference_id"] == str(user.id)
    assert sess["metadata"]["tier"] == "pro"

    # Customer id was persisted.
    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(id=user.id).one()
    assert refreshed.stripe_customer_id == "cus_freshly_minted"


def test_checkout_reuses_existing_customer(
    client, db_session, monkeypatch, price_ids
):
    """User who already has a stripe_customer_id should NOT mint a
    duplicate — that's how Stripe billing duplicates compound."""
    customer_create_calls = []

    def fake_customer_create(**kwargs):
        customer_create_calls.append(kwargs)
        return SimpleNamespace(id="cus_should_not_be_called")

    def fake_session_create(**kwargs):
        return SimpleNamespace(id="cs_2", url="https://checkout.stripe.test/cs_2")

    monkeypatch.setattr(stripe.Customer, "create", fake_customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create", fake_session_create)

    user = _make_user(db_session, stripe_customer_id="cus_existing")
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "starter",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 200
    assert customer_create_calls == []  # never re-minted


def test_checkout_surfaces_stripe_error_as_500(
    client, db_session, monkeypatch, price_ids
):
    """Stripe SDK errors should bubble up as a 500 with the message —
    not a silent success or a 200 with a broken url."""

    def fake_customer_create(**kwargs):
        return SimpleNamespace(id="cus_x")

    def fake_session_create(**kwargs):
        raise stripe.error.StripeError("rate limited")

    monkeypatch.setattr(stripe.Customer, "create", fake_customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create", fake_session_create)

    user = _make_user(db_session)
    res = client.post(
        "/payments/checkout",
        json={
            "tier": "pro",
            "success_url": "https://app.test/success",
            "cancel_url": "https://app.test/cancel",
        },
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 500
    assert "stripe error" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /payments/portal
# ---------------------------------------------------------------------------


def test_portal_requires_existing_customer(client, db_session):
    """User without a stripe_customer_id has no billing history to
    manage — return 400 instead of asking Stripe to invent one."""
    user = _make_user(db_session)
    res = client.post(
        "/payments/portal?return_url=https://app.test/billing",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400
    assert "no payment history" in res.json()["detail"].lower()


def test_portal_returns_session_url(client, db_session, monkeypatch):
    captured: dict[str, Any] = {}

    def fake_portal_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://billing.stripe.test/portal_abc")

    monkeypatch.setattr(stripe.billing_portal.Session, "create", fake_portal_create)

    user = _make_user(db_session, stripe_customer_id="cus_paying")
    res = client.post(
        "/payments/portal?return_url=https%3A%2F%2Fapp.test%2Fbilling",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 200
    assert res.json()["url"] == "https://billing.stripe.test/portal_abc"
    assert captured["customer"] == "cus_paying"
    assert captured["return_url"] == "https://app.test/billing"


def test_portal_unauthenticated_returns_401_or_403(client):
    res = client.post("/payments/portal?return_url=https://app.test/billing")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /payments/pricing — public, no auth
# ---------------------------------------------------------------------------


def test_pricing_is_public_and_lists_all_tiers(client):
    res = client.get("/payments/pricing")
    assert res.status_code == 200
    tiers = {t["id"]: t for t in res.json()["tiers"]}
    assert {"starter", "pro", "max"} <= tiers.keys()
    # Each tier exposes a price + apps_per_night for the pricing UI.
    for tier in tiers.values():
        assert isinstance(tier["price"], int)
        assert isinstance(tier["apps_per_night"], int)
        assert isinstance(tier["features"], list)
