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
- `GET /auth/me` - Get current user

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
- `GET /payments/subscription` - Get subscription status (reads persisted user record)
- `POST /payments/cancel` - Cancel current subscription at period end
- `POST /payments/portal` - Create Stripe Billing Portal session
- `POST /payments/webhook` - Stripe webhook receiver (signature-verified, idempotent)

#### Stripe webhook setup

The webhook endpoint at `/payments/webhook` handles:

| Event | Effect |
|-------|--------|
| `checkout.session.completed` | Optimistically marks user active for the requested tier |
| `customer.subscription.created` / `updated` | Syncs `tier`, `subscription_status`, `current_period_end`, `stripe_subscription_id` from the subscription object |
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
pytest

# Frontend tests
cd frontend
npm test
```

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
# NightShift
# NightShift
