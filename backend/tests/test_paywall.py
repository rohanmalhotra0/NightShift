"""Tests for the paywall gate on protected routes.

`require_paid_user` is the dependency injected on /applications/apply and
/applications/{id}/retry. It returns 402 with `upgrade_url` for users
that don't have an active subscription, lets admins through unconditionally,
and keeps `past_due` access alive while Stripe retries the charge.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from api.auth import create_access_token, hash_password, require_paid_user
from database import Application, ApplicationStatus, Job, User, UserPrefs, UserTier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    db_session,
    *,
    tier: str = UserTier.FREE.value,
    subscription_status: str | None = None,
    is_admin: bool = False,
    email: str = "alice@example.com",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("hunter2hunter2"),
        tier=tier,
        subscription_status=subscription_status,
        is_admin=is_admin,
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


def _make_job(db_session, **overrides) -> Job:
    job = Job(
        source=overrides.get("source", "linkedin"),
        title=overrides.get("title", "Senior Engineer"),
        company=overrides.get("company", "Acme"),
        url=overrides.get("url", "https://example.com/job/1"),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def no_bot(monkeypatch):
    """Replace the background bot runner with a no-op so /apply doesn't try
    to spin up Playwright in tests."""
    monkeypatch.setattr(
        "api.applications.run_application_batch",
        lambda *a, **kw: None,
    )


# ---------------------------------------------------------------------------
# /applications/apply
# ---------------------------------------------------------------------------


def test_apply_unauthenticated_returns_401(client, no_bot):
    res = client.post("/applications/apply", json={"job_ids": [1]})
    # FastAPI's HTTPBearer returns 403 when no creds are sent; either is fine
    # as a deny — we just want it nowhere near the paywall.
    assert res.status_code in (401, 403)


def test_apply_free_user_gets_402_with_upgrade_url(client, db_session, no_bot):
    user = _make_user(db_session, tier=UserTier.FREE.value)
    token = _token_for(user)

    # Auth dependencies resolve before body validation in FastAPI, so the
    # 402 fires regardless of payload shape.
    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 402
    body = res.json()
    detail = body["detail"]
    assert detail["code"] == "subscription_required"
    assert detail["upgrade_url"] == "/pricing"
    assert detail["tier"] == "free"


def test_apply_paid_user_with_active_status_passes_gate(
    client, db_session, no_bot
):
    """Pro + active sub: gate lets us through. We weakly assert `!= 402`
    because the underlying /apply endpoint has known schema quirks
    (`job_ids: list[int]` vs. UUID-string Job.id) that are out of
    scope for the paywall change."""
    user = _make_user(
        db_session, tier=UserTier.PRO.value, subscription_status="active"
    )
    token = _token_for(user)

    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code != 402


def test_apply_paid_user_with_trialing_passes_gate(client, db_session, no_bot):
    user = _make_user(
        db_session,
        tier=UserTier.STARTER.value,
        subscription_status="trialing",
        email="trial@example.com",
    )
    token = _token_for(user)

    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code != 402


def test_apply_paid_user_with_past_due_keeps_access(client, db_session, no_bot):
    """past_due is a courtesy window while Stripe retries — keep them in."""
    user = _make_user(
        db_session,
        tier=UserTier.PRO.value,
        subscription_status="past_due",
        email="latepayer@example.com",
    )
    token = _token_for(user)

    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code != 402


def test_apply_canceled_subscription_blocks_with_402(client, db_session, no_bot):
    """Once status flips to canceled, the gate must close immediately,
    even if the tier column hasn't been pushed back to free yet."""
    user = _make_user(
        db_session,
        tier=UserTier.PRO.value,
        subscription_status="canceled",
        email="exuser@example.com",
    )
    token = _token_for(user)

    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 402
    assert res.json()["detail"]["code"] == "subscription_required"


def test_apply_admin_user_bypasses_paywall(client, db_session, no_bot):
    """Admin should never be paywalled even at tier=free with no sub."""
    user = _make_user(
        db_session,
        tier=UserTier.ADMIN.value,
        is_admin=True,
        email="ops@nightshift.app",
    )
    token = _token_for(user)

    res = client.post(
        "/applications/apply",
        json={"job_ids": [1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code != 402


# ---------------------------------------------------------------------------
# /applications/{id}/retry
# ---------------------------------------------------------------------------


def test_retry_free_user_gets_402(client, db_session, no_bot):
    user = _make_user(db_session, tier=UserTier.FREE.value)
    job = _make_job(db_session, url="https://example.com/job/5")
    application = Application(
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.FAILED.value,
    )
    db_session.add(application)
    db_session.commit()

    token = _token_for(user)
    res = client.post(
        f"/applications/{application.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 402
    assert res.json()["detail"]["code"] == "subscription_required"


def test_retry_paid_user_gets_through(client, db_session, no_bot):
    user = _make_user(
        db_session,
        tier=UserTier.MAX.value,
        subscription_status="active",
        email="bigspender@example.com",
    )
    job = _make_job(db_session, url="https://example.com/job/6")
    application = Application(
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.FAILED.value,
    )
    db_session.add(application)
    db_session.commit()

    token = _token_for(user)
    res = client.post(
        f"/applications/{application.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# /auth/me exposes subscription state
# ---------------------------------------------------------------------------


def test_me_exposes_subscription_status_and_period_end(client, db_session):
    period_end = datetime.utcnow() + timedelta(days=14)
    user = _make_user(
        db_session,
        tier=UserTier.PRO.value,
        subscription_status="active",
        email="me@example.com",
    )
    user.current_period_end = period_end
    db_session.commit()
    token = _token_for(user)

    res = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tier"] == "pro"
    assert body["subscription_status"] == "active"
    assert body["current_period_end"] is not None


# ---------------------------------------------------------------------------
# Direct unit tests on the dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_paid_user_admin_passes_without_subscription():
    user = User(
        email="admin@x.com",
        password_hash="x",
        tier=UserTier.ADMIN.value,
        is_admin=True,
    )
    # No subscription_status set.
    out = await require_paid_user(current_user=user)
    assert out is user


@pytest.mark.asyncio
async def test_require_paid_user_free_user_raises_402():
    user = User(
        email="free@x.com",
        password_hash="x",
        tier=UserTier.FREE.value,
        is_admin=False,
        subscription_status=None,
    )
    with pytest.raises(HTTPException) as exc:
        await require_paid_user(current_user=user)
    assert exc.value.status_code == 402
    assert exc.value.detail["upgrade_url"] == "/pricing"


@pytest.mark.asyncio
async def test_require_paid_user_paid_active_passes():
    user = User(
        email="pro@x.com",
        password_hash="x",
        tier=UserTier.PRO.value,
        is_admin=False,
        subscription_status="active",
    )
    out = await require_paid_user(current_user=user)
    assert out is user


@pytest.mark.asyncio
async def test_require_paid_user_pro_but_canceled_raises_402():
    """If tier hasn't synced yet but status went canceled, deny."""
    user = User(
        email="ex@x.com",
        password_hash="x",
        tier=UserTier.PRO.value,
        is_admin=False,
        subscription_status="canceled",
    )
    with pytest.raises(HTTPException) as exc:
        await require_paid_user(current_user=user)
    assert exc.value.status_code == 402
