# NightShift

Automated job application service that applies to jobs while you sleep.

## Features

- **Automated Job Scraping**: Uses JobSpy to scrape jobs from LinkedIn, Indeed, ZipRecruiter, and more
- **AI-Powered Auto-Fill**: Claude AI intelligently fills out application forms
- **CAPTCHA Solving**: 2Captcha integration for automated CAPTCHA solving
- **Email Verification**: Gmail API integration for handling verification codes
- **Application Logging**: Google Sheets integration to track all applications
- **Scheduled Runs**: APScheduler for nightly application runs
- **Payment Processing**: Stripe integration for subscription management

## Tech Stack

- **Backend**: Python (FastAPI), SQLAlchemy, Playwright
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Database**: SQLite (easily swappable to PostgreSQL)
- **AI**: Anthropic Claude API
- **Payments**: Stripe

## Project Structure

```
NightShift/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Environment variables
│   ├── database/               # SQLAlchemy models & DB
│   ├── scrapers/               # Job scraping (JobSpy)
│   ├── bot/                    # Application bot engine
│   │   ├── engine.py           # Main Playwright bot
│   │   ├── captcha.py          # 2captcha integration
│   │   ├── autofill.py         # Claude auto-fill
│   │   └── gmail.py            # Gmail verification
│   ├── services/               # Business logic
│   │   ├── scheduler.py        # APScheduler
│   │   ├── sheets.py           # Google Sheets
│   │   └── metrics.py          # Usage tracking
│   └── api/                    # API routes
├── frontend/
│   ├── app/                    # Next.js pages
│   ├── components/             # React components
│   └── lib/                    # Utilities & API client
├── .env.example                # Environment template
├── docker-compose.yml          # Docker setup
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Anthropic API key
- 2Captcha API key (for CAPTCHA solving)
- Google Cloud credentials (for Sheets and Gmail)
- Stripe account (for payments)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Copy environment file and configure
cp ../.env.example ../.env
# Edit .env with your API keys

# Run the server
python main.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Docker Setup

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d
```

## API Endpoints

### Authentication
- `POST /auth/signup` - Create account
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user (includes `tier`, `subscription_status`, `current_period_end`)

**Approach:** custom FastAPI auth — bcrypt for password hashing, JWT (HS256) for sessions, `HTTPBearer` on protected routes. Chosen over NextAuth/Clerk/Supabase because the backend is Python (FastAPI) and we want a single source of truth for the user record (subscription state lives in the same DB row as the auth record). The frontend stores the JWT in `localStorage` and re-hydrates the user on mount via `/auth/me`.

**Paywall gate:** `require_paid_user` (in `backend/api/auth.py`) is a FastAPI dependency that returns **402 Payment Required** with body `{"code": "subscription_required", "upgrade_url": "/pricing", ...}` when the user is on `tier=free` or has a non-access subscription_status. Statuses `active`, `trialing`, and `past_due` keep access; admins always pass. Currently applied to `POST /applications/apply` and `POST /applications/{id}/retry`.

### Users
- `GET /users/prefs` - Get preferences
- `PUT /users/prefs` - Update preferences
- `POST /users/resume` - Upload resume

### Jobs
- `GET /jobs` - List jobs matching preferences
- `GET /jobs/{id}` - Get job details

### Applications
- `GET /applications` - List applications
- `GET /applications/today` - Today's summary
- `POST /applications/apply` - Queue applications

### Payments
- `GET /payments/pricing` - Get pricing tiers
- `POST /payments/checkout` - Create checkout session
- `GET /payments/subscription` - Get subscription status (reads persisted user record, includes `cancel_at_period_end`)
- `POST /payments/cancel` - Schedule cancellation at period end (sets `cancel_at_period_end=true`)
- `POST /payments/resume` - Undo a pending cancellation (clears `cancel_at_period_end`)
- `POST /payments/portal` - Create Stripe Billing Portal session (JSON body: `{"return_url": "..."}`)
- `POST /payments/webhook` - Stripe webhook receiver (signature-verified, idempotent)

The frontend exposes `/account/billing` for users to view current plan,
schedule/undo cancellation, and open the Stripe portal. Any 402
response with `upgrade_url` is auto-redirected to `/pricing?from=gate`
by the global API client, so new gated endpoints get the same UX
without per-page handling.

#### Stripe webhook setup

The webhook endpoint at `/payments/webhook` handles:

| Event | Effect |
|-------|--------|
| `checkout.session.completed` | Optimistically marks user active for the requested tier |
| `customer.subscription.created` / `updated` | Syncs `tier`, `subscription_status`, `current_period_end`, `cancel_at_period_end`, `stripe_subscription_id` from the subscription object |
| `customer.subscription.deleted` | Drops user back to `free`, clears subscription id |
| `invoice.payment_failed` | Marks `subscription_status = past_due` |

Hardening notes:
- Requires `STRIPE_WEBHOOK_SECRET`. Returns 503 if unset (won't accept unsigned events even in dev).
- Every event id is recorded in the `stripe_webhook_events` table for at-most-once processing.
- A `past_due` status keeps the user's tier active while Stripe retries the charge — only `canceled`/`unpaid`/`incomplete_expired` flip them back to free.

Local testing with the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/payments/webhook
# In another shell:
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
```

#### Frontend paywall flow

Public pages: `/`, `/pricing`, `/auth/login`, `/auth/signup`, `/checkout/success`, `/checkout/cancel`.

When a free or expired user hits a paid action (e.g. clicking "Apply" on `/jobs`), the API returns 402 and the client-side `ApiError.isPaywall` triggers a redirect to `/pricing`. The pricing page reads tiers from `GET /payments/pricing`, and clicking "Upgrade" calls `POST /payments/checkout` then `window.location.assign(checkout_url)` to hand off to Stripe.

After payment, Stripe redirects to `/checkout/success?session_id=...`. That page polls `/auth/me` every 1.5s until `subscription_status` flips into the active set (with a 30s soft timeout that still shows a "your account will update shortly" CTA — the webhook is authoritative). `/checkout/cancel` is a graceful return that links back to `/pricing` and `/dashboard`.

Helper hooks for protected client routes:
- `useRequireAuth()` — redirects anon users to `/auth/login?next=<path>`.
- `useRequirePaid()` — additionally redirects free/expired users to `/pricing`.

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for auto-fill |
| `TWOCAPTCHA_API_KEY` | 2Captcha API key |
| `GOOGLE_SHEETS_CREDENTIALS` | Service account JSON for Sheets |
| `GMAIL_CREDENTIALS` | OAuth credentials for Gmail |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |
| `STRIPE_PRICE_ID_STARTER` | Stripe price id for Starter tier |
| `STRIPE_PRICE_ID_PRO` | Stripe price id for Pro tier |
| `STRIPE_PRICE_ID_MAX` | Stripe price id for Max tier |
| `JWT_SECRET` | Secret for JWT tokens |

### Production Environment Variables

When deploying (Railway for the backend, Vercel for the frontend), set
**every variable below** before flipping traffic. Missing values fail
quietly: the app boots, but checkout returns 503 and webhooks return
503 with `Webhook secret not configured`.

**Backend (Railway / Docker)**

| Variable | Where it comes from | Notes |
|----------|---------------------|-------|
| `DATABASE_URL` | Postgres host | Use a connection pooler in prod (e.g. Supabase pgbouncer URL). |
| `JWT_SECRET` | `openssl rand -hex 32` | **Rotate from the default before any real user signs up.** |
| `JWT_ALGORITHM` | leave as `HS256` | |
| `JWT_EXPIRATION_HOURS` | e.g. `24` | |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | choose | Login as this email gets `is_admin=true` and bypasses the paywall. |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API keys | Use a **live** `sk_live_…` key in prod, `sk_test_…` in staging. |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Developers → Webhooks → your endpoint | One per environment — **don't share between live and test**. Endpoint URL is `https://<your-domain>/payments/webhook`. |
| `STRIPE_PRICE_ID_STARTER` | Stripe Dashboard → Products | Recurring monthly price; tier is unbookable if unset. |
| `STRIPE_PRICE_ID_PRO` | same | |
| `STRIPE_PRICE_ID_MAX` | same | |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Used by the auto-fill bot. |
| `TWOCAPTCHA_API_KEY` | 2captcha.com | CAPTCHA solver. |
| `GOOGLE_SHEETS_CREDENTIALS` | GCP service-account JSON, single line | For applications log. |
| `GMAIL_CREDENTIALS` | GCP OAuth client JSON, single line | For email verification codes. |

**Frontend (Vercel)**

| Variable | Notes |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Public URL of the deployed backend, e.g. `https://api.nightshift.app`. Baked in at build time. |

**Stripe webhook endpoint setup (one-time per environment)**

1. Stripe Dashboard → Developers → Webhooks → **Add endpoint**.
2. URL: `https://<backend-domain>/payments/webhook`.
3. Subscribe to: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`.
4. Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
5. Hit "Send test webhook" → expect 200 OK.

### Subscription Tiers

| Tier | Price | Apps/Night | Features |
|------|-------|------------|----------|
| Starter | $19/mo | 3 | Basic auto-fill, LinkedIn/Indeed |
| Pro | $39/mo | 10 | All job boards, custom resume |
| Max | $69/mo | 25 | AI cover letters, custom scheduling |

## Usage

### Manual Commands

```bash
# Run job scraper
python -m backend.scrapers.linkedin

# Test single application
python -m backend.bot.engine --job-id 123 --user-id 1

# Run scheduler manually
python -m backend.services.scheduler --run-now
```

### Scheduler

The scheduler runs automatically:
- **8 PM**: Job scraping
- **10 PM**: First application batch
- **11 PM**: Second application batch

Times are configurable per user.

## Development

### Running Tests

```bash
# Backend tests
cd backend
pip install -r requirements-dev.txt   # one-time: pytest + pytest-asyncio
pytest

# Frontend
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

### Continuous Integration

GitHub Actions runs the same checks on every PR and push to `main` —
see `.github/workflows/ci.yml`. Two parallel jobs:

- **Backend** — installs `requirements.txt` + `requirements-dev.txt`, runs `pytest`.
- **Frontend** — installs deps, runs `next lint`, `tsc --noEmit`, and `next build`.

CI seeds dummy values for `JWT_SECRET`, `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, and the `STRIPE_PRICE_ID_*` vars so config
loads cleanly. Tests inject their own values via `conftest.py`.

### Database Migrations

```bash
cd backend

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Security Notes

- All API routes require JWT authentication
- Passwords are hashed with bcrypt
- Stripe webhooks are verified
- File uploads are validated and sandboxed

## License

MIT
