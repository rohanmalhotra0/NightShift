# NightShift — Autopilot Backlog

The `nightshift-autopilot` scheduled task reads this file at the start of every run and works on items **top to bottom**. To steer it, just reorder, edit, or add items here. Check items off with `[x]` when done (autopilot will do this in its PR when it ships an item).

## Paywall — End of Week Goal

### 1. Stripe checkout + subscriptions (test mode)
- [x] Add `stripe` SDK + env vars (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_*`) to `.env.example`
- [ ] Create at least one test-mode Product + Price (monthly) — document the price ID in README *(needs Rohan's Stripe dashboard)*
- [x] `/api/checkout` endpoint that creates a Stripe Checkout Session for the logged-in user
- [x] `/api/webhooks/stripe` endpoint with signature verification — handles `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
- [x] Persist `stripe_customer_id`, `subscription_status`, `current_period_end` on the user record
- [x] Tests: webhook signature verification, status transitions (active → canceled → past_due)

### 2. Auth + gated routes
- [x] Pick auth approach (NextAuth / Clerk / Supabase / custom) and document the choice in README — custom JWT (FastAPI + bcrypt + jwt)
- [x] Sign up + log in flows
- [x] Session middleware (FastAPI `HTTPBearer` + `get_current_user` dep; frontend `AuthProvider`)
- [x] `require_paid_user()` dep that returns 402 + `upgrade_url`; frontend `useRequirePaid()` hook redirects to `/pricing`
- [x] Apply gating to actual paid routes/features — `/applications/apply`, `/applications/{id}/retry`
- [x] Tests: free user → 402, paid user (active/trialing/past_due) → access granted, canceled sub → 402, admin → bypass

### 3. Pricing page + upgrade UX
- [x] `/pricing` route — public, lists plans, "Upgrade" CTA → `/payments/checkout`
- [x] `/checkout/success` — polls `/auth/me` until subscription_status flips active; 30s timeout fallback
- [x] `/checkout/cancel` — graceful return
- [ ] Account/billing page — current plan, "Manage subscription" → Stripe Billing Portal
- [x] Empty/loading/error states (skeleton tiers, Suspense boundaries, 503/401 handling on checkout)

### 4. Tests + deploy
- [ ] Set up CI (GitHub Actions): lint, typecheck, test, build on every PR
- [ ] Add deploy config (Vercel/Netlify) — preview deploys per PR
- [ ] Add e2e or integration test covering: sign up → pay → access gated route
- [ ] Production env vars documented in README

## Post-paywall (only after the above ships)
- [ ] Annual plan + discount
- [ ] Trial period
- [ ] Coupon support
- [ ] Email receipts / failed-payment dunning
- [ ] Admin dashboard for subscription management

---

**Notes for the autopilot:**
- Pick the topmost unchecked item that isn't already in an open `autopilot/*` PR.
- Items can be split across multiple PRs — fine to ship a partial slice as long as it's coherent and tested.
- If an item is blocked (e.g. needs a Stripe API key Rohan hasn't added), open a DRAFT PR with a placeholder + note explaining the blocker, and move to the next item.
