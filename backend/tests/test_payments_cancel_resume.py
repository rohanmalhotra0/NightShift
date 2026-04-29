"""Tests for the /payments/cancel and /payments/resume endpoints and
the cancel_at_period_end column persistence.

The endpoints proxy to Stripe but the user record is the source of
truth the UI reads, so each test confirms both the Stripe call shape
and the persisted state.
"""

from __future__ import annotations

from typing import Any

import pytest
import stripe

from api.auth import create_access_token, hash_password
from database import User, UserPrefs, UserTier


def _make_user(
    db_session,
    *,
    email: str = "alice@example.com",
    tier: str = UserTier.PRO.value,
    stripe_customer_id: str | None = "cus_paying",
    stripe_subscription_id: str | None = "sub_123",
    subscription_status: str | None = "active",
    cancel_at_period_end: bool = False,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("hunter2hunter2"),
        tier=tier,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        subscription_status=subscription_status,
        cancel_at_period_end=cancel_at_period_end,
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


def _stub_subscription_modify(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_modify(sub_id, **kwargs):
        captured["sub_id"] = sub_id
        captured.update(kwargs)
        return {"id": sub_id, **kwargs}

    monkeypatch.setattr(stripe.Subscription, "modify", fake_modify)
    return captured


# ---------------------------------------------------------------------------
# /payments/cancel
# ---------------------------------------------------------------------------


def test_cancel_requires_active_subscription(client, db_session):
    user = _make_user(db_session, stripe_subscription_id=None)
    res = client.post(
        "/payments/cancel",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400
    assert "no active subscription" in res.json()["detail"].lower()


def test_cancel_calls_stripe_and_persists_flag(client, db_session, monkeypatch):
    captured = _stub_subscription_modify(monkeypatch)
    user = _make_user(db_session)

    res = client.post(
        "/payments/cancel",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["cancel_at_period_end"] is True
    assert captured["sub_id"] == "sub_123"
    assert captured["cancel_at_period_end"] is True

    db_session.refresh(user)
    assert user.cancel_at_period_end is True
    # Tier is still PRO until period-end webhook arrives — the user
    # paid for the rest of the billing period and should keep access.
    assert user.tier == UserTier.PRO.value


def test_cancel_unauthenticated_returns_401_or_403(client):
    res = client.post("/payments/cancel")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /payments/resume
# ---------------------------------------------------------------------------


def test_resume_requires_active_subscription(client, db_session):
    user = _make_user(
        db_session,
        stripe_subscription_id=None,
        cancel_at_period_end=True,
    )
    res = client.post(
        "/payments/resume",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400


def test_resume_requires_pending_cancel(client, db_session):
    """Resume on an already-active subscription is a no-op error."""
    user = _make_user(db_session, cancel_at_period_end=False)
    res = client.post(
        "/payments/resume",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 400
    assert "not scheduled for cancellation" in res.json()["detail"].lower()


def test_resume_clears_flag_and_calls_stripe(client, db_session, monkeypatch):
    captured = _stub_subscription_modify(monkeypatch)
    user = _make_user(db_session, cancel_at_period_end=True)

    res = client.post(
        "/payments/resume",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["cancel_at_period_end"] is False
    assert captured["sub_id"] == "sub_123"
    assert captured["cancel_at_period_end"] is False

    db_session.refresh(user)
    assert user.cancel_at_period_end is False


def test_resume_unauthenticated_returns_401_or_403(client):
    res = client.post("/payments/resume")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /payments/subscription surfaces cancel_at_period_end
# ---------------------------------------------------------------------------


def test_subscription_endpoint_returns_cancel_flag(client, db_session):
    user = _make_user(db_session, cancel_at_period_end=True)
    res = client.get(
        "/payments/subscription",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cancel_at_period_end"] is True
    assert body["status"] == "active"
    assert body["tier"] == UserTier.PRO.value


def test_subscription_endpoint_defaults_cancel_flag_false(client, db_session):
    user = _make_user(db_session, cancel_at_period_end=False)
    res = client.get(
        "/payments/subscription",
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )
    assert res.status_code == 200
    assert res.json()["cancel_at_period_end"] is False
