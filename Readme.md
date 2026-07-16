# Clinic Booking API

A production-grade REST API for clinic appointment scheduling, built with Django and Django REST Framework.

## Table of Contents

- [System Design](#system-design)
- [Running Locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [API Overview](#api-overview)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [AI Reflection](#ai-reflection)

---

## System Design

### Models

**User** — Extends `AbstractUser`. Email is the login field. Role is either `admin`,`patient` or `doctor`. All users
authenticate via JWT.

**Doctor** — A `OneToOneField` to `User` holding shift data (`work_start`, `work_end`).

**Appointment** — Belongs to a `Doctor` and a `patient` (User). Holds `slot_time` (UTC datetime), `status` (`active` or
`cancelled`), and `cancel_reason`.

### Slot Model

Slots are **computed on the fly** — not stored. Given a doctor and a date, the API generates all 30-minute slots between
`work_start` and `work_end`, then subtracts already-booked slots. This keeps the database simple and avoids stale slot
records.

### Concurrency

Double-booking is prevented at two levels:

1. **`select_for_update()` inside `transaction.atomic()`** — acquires a row-level lock before inserting, so concurrent
   requests are serialised.
2. **Partial unique constraint on `(doctor, slot_time)` where `status=active`** — the database enforces the invariant
   even if application-level locking is bypassed. A cancelled appointment does not block the slot from being rebooked.

### Reschedule Atomicity

When rescheduling, the original slot is only released **after** the new slot is confirmed. If the new slot is already
taken, `IntegrityError` is raised inside the atomic block, the transaction rolls back, and the patient keeps their
original booking. They never lose a slot.

### Key Decisions

| Decision                                      | Reasoning                                                                                                                                                                                      |
|-----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Slots computed, not stored                    | Simpler schema, no stale data, trivially supports working hour changes                                                                                                                         |
| `status` field over `cancelled` boolean       | Extensible — `completed`, `no_show` can be added without a migration                                                                                                                           |
| Doctor created via admin only                 | Doctors are a managed, fixed resource — not self-registering users                                                                                                                             |
| Email as login field                          | Username is maintained internally by `AbstractUser` but never exposed                                                                                                                          |
| All datetimes in UTC                          | `USE_TZ = True` throughout. `TimeField` on `Doctor` is interpreted in `CLINIC_TIMEZONE` and converted to UTC at slot generation time. Clients convert UTC to their local timezone for display. |
| RS256 in production, HS256 in dev             | No RSA keys needed to run locally; asymmetric signing in production allows token verification by external services                                                                             |
| `is_available` separate from `user.is_active` | A doctor can be taken off the booking system without disabling their account and losing historical data                                                                                        |

### Known Simplifications

- **Timezone**: `work_start` and `work_end` are stored as bare `TimeField` values interpreted in `CLINIC_TIMEZONE` (
  default: `Africa/Nairobi`). When generating slots, the service converts clinic local times to UTC using `zoneinfo`.
  All API responses return UTC ISO 8601 datetimes — client applications are responsible for converting to the user's
  local timezone for display. A multi-location clinic would need a timezone field per `Doctor` rather than a single
  global setting.
- **Working hour changes**: Existing bookings outside new working hours are grandfathered. No retroactive cancellation.
- **Doctor cancelling a full day**: Admin operation only in this version — no API endpoint.
- **Password reset**: Out of scope. Requires email infrastructure. Noted as a V2 concern.
- **`date` parameter on availability**: Means the shift start date, not the calendar date. A night-shift doctor's July
  13 availability returns slots from `2026-07-13 22:00Z` to `2026-07-14 05:30Z`.
- **Creating a new doctor**: While I don't think doctors should be self-registering, we could have an endpoint to create
  them only that it would be a separate admin-only operation.

---

## Running Locally

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker (for Postgres)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Pinchez25/clinic-booking.git
cd clinic-booking

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env — set DJANGO_SECRET_KEY to any random string

# 3. Install dependencies
uv sync --group dev

# 4. Install pre-commit hooks
uv run pre-commit install

# 5. Start Postgres
docker compose up -d

# 6. Run migrations
uv run python manage.py migrate

# 7. Create a superuser (to access Django admin and create doctors)
uv run python manage.py createsuperuser

# 8. Start the development server
uv run python manage.py runserver
```

The API is available at `http://localhost:8000`.
Interactive API docs at `http://localhost:8000/api/docs/`.

### Running Tests

```bash
uv run pytest
```

With coverage report:

```bash
uv run pytest --cov --cov-report=term-missing
```

---

## Running with Docker

For a fully containerised environment (web + database):

```bash
# 1. Copy and fill in environment variables
cp .env.example .env

# 2. Build and start all services
docker compose -f docker-compose.dev.yml up --build

# 3. Create a superuser
docker compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
```

The API is available at `http://localhost:8000`.
Source code is mounted as a volume — changes reload automatically.

---

## API Overview

### Authentication

All endpoints except `POST /api/auth/register/` and `POST /api/auth/login/` require a JWT access token:

```
Authorization: Bearer <access_token>
```

### Endpoints

| Method  | Endpoint                                          | Auth         | Description                                                   |
|---------|---------------------------------------------------|--------------|---------------------------------------------------------------|
| `POST`  | `/api/auth/register/`                             | None         | Register as a patient. Returns token pair immediately.        |
| `POST`  | `/api/auth/login/`                                | None         | Login. Returns access + refresh tokens.                       |
| `POST`  | `/api/auth/token/refresh/`                        | None         | Get a new access token using a refresh token.                 |
| `POST`  | `/api/auth/logout/`                               | Required     | Blacklist the refresh token.                                  |
| `GET`   | `/api/auth/me/`                                   | Required     | Get current user profile.                                     |
| `PATCH` | `/api/auth/me/`                                   | Required     | Update profile (first name, last name, email).                |
| `GET`   | `/api/doctors/`                                   | Required     | List all available doctors.                                   |
| `GET`   | `/api/doctors/{id}/`                              | Required     | Get a single doctor.                                          |
| `GET`   | `/api/doctors/{id}/availability/?date=YYYY-MM-DD` | Required     | Available 30-minute slots for a doctor on a given date (UTC). |
| `POST`  | `/api/appointments/`                              | Patient only | Book an appointment.                                          |
| `PATCH` | `/api/appointments/{id}/cancel/`                  | Owner only   | Cancel with a reason.                                         |
| `PATCH` | `/api/appointments/{id}/reschedule/`              | Owner only   | Move to a new slot.                                           |
| `GET`   | `/api/patients/{id}/appointments/`                | Owner only   | Upcoming active appointments sorted by date.                  |
| `GET`   | `/`                                               | None         | Interactive Swagger UI.                                       |

### Generating RSA Keys (Production)

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Set the contents of these files as `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` in your environment. Never commit them.

---

## CI/CD

### Pipeline (`deploy.yml`)

Two jobs in one workflow:

**`ci` job** — runs on every pull request and every push to `main`:

1. Spins up a Postgres service container
2. Installs dependencies with `uv`
3. Runs `ruff check` and `ruff format --check` — lint failures block the pipeline
4. Runs the full test suite with `pytest`

**`deploy` job** — runs only on push to `main`, only if `ci` passes (`needs: ci`):

1. Calls the Render deploy hook via `curl`
2. Render pulls `main`, runs the build commands, performs a zero-downtime swap

### Security Scanning (`codeql.yml`)

CodeQL runs on PRs, pushes to `main`, and every Monday at 06:00 UTC. It scans for Python security vulnerabilities
including SQL injection, path traversal, and insecure deserialization.

### Code Quality Checks (`qodo-ai-review.yml`)

* This workflow works on a PR, when opened and when the PR is updated.
* It runs the AI-generated review workflow on the PR.
* The workflow takes advantage of the qodo github plugin and comments "/review" on the PR which triggers the review bot.
* The review bot will then review the PR and provide feedback on what can be improved or potential bugs.
* Mine is to review the feedback and evaluate whether the suggested changes are necessary.

### Secrets Required

| Secret                   | Where to set                | Description                       |
|--------------------------|-----------------------------|-----------------------------------|
| `RENDER_DEPLOY_HOOK_URL` | GitHub → Settings → Secrets | Deploy hook from Render dashboard |

---

## Deployment

Deployed on **Render** using `render.yaml` for infrastructure-as-code.

- **Public URL**: [https://clinic-booking-tz0o.onrender.com/](https://clinic-booking-tz0o.onrender.com/)
- **CI/CD**:
- **Branch**: Merging a PR into `main` triggers a deployment
- **Database**: Managed Postgres 18 on Render free tier
- **Static files**: Served by WhiteNoise — no CDN required

### Environment Variables on Render

The following must be set manually in the Render dashboard:

| Variable               | Description                                      |
|------------------------|--------------------------------------------------|
| `JWT_PRIVATE_KEY`      | RS256 private key (PEM format, newlines as `\n`) |
| `JWT_PUBLIC_KEY`       | RS256 public key (PEM format, newlines as `\n`)  |
| DJANGO_SETTINGS_MODULE | `clinic_booking.settings.production`             |
| SECRET_KEY             | Any random string                                |
| DATABASE_URL           | Render-provided Postgres connection string       |

---

## Design Decisions & Trade-offs

### Security

- **RS256 over HS256 in production**: Asymmetric signing means a separate service can verify tokens using only the
  public key, without needing the private key. In development, HS256 with `SECRET_KEY` is used to avoid managing RSA
  keys locally.
- **Minimal JWT payload**: Only `user_id` and `role` are in the token. Email, name, and phone are never included — JWT
  payloads are base64-encoded, not encrypted.
- **Refresh token rotation + blacklisting**: Every token refresh issues a new refresh token and invalidates the old one.
  Logout explicitly blacklists the refresh token.
- **Scoped throttling**: Login and register have independent rate limits (`auth_login`, `auth_register`) so they don't
  share a counter.
- **Non-root Docker user**: The production container runs as a `clinic` system user, not root.

### What We Would Add Before Production

- Email verification on registration
- Password reset via email
- Redis-backed token blacklisting (currently uses DB)
- Audit logging for all appointment state changes
- Doctor schedule overrides (holidays, sick days)
- Sentry for error tracking
- Structured JSON logging with request tracing

---

## AI Reflection

### 1. What did I use AI for across the four sections?

**Section 1 (Design)**: Used AI to think through edge cases — overnight shifts, reschedule atomicity, the slot model (
computed vs stored), and timezone handling. AI helped structure the trade-off analysis but the decisions were made
collaboratively.

**Section 2 (Implementation)**: Most of the boilerplate code was generated by AI. For example, all I did was describe
the database models that I had designed for the project and AI generated them for me. Every generated code was reviewed,
questioned, and often corrected. Notable catches during review: `timezone.utc` is not a Django attribute (it's
`datetime.UTC`), a shared `AuthRateThrottle` scope causing login and register to share a rate limit counter etc.

**Section 3 (Deployment)**: Used AI to generate the GitHub Actions workflows. AI generated a lot of files like
`render.yaml`, and Procfile and build.sh which I considered necessary and decided to follow
the simple documented action on render docs on how to deploy using github actions. AI also helped me work on the codeql
scan workflow. I came across codeql on some other project and asked AI if we could use it on a django project. AI
suggested
that we could and it generated the workflow for me. What it did not catch is that codeql only works on public repos
unless
you have a paid plan. I had a hard time finding out why the action was failing and without obvious errors, the AI was no
help.
That is until I found out that the action was failing because the codeql scan was not allowed to run on private repos.

**Section 4 (Reflection)**: Written independently.

### 2. One example where AI improved the work

**Prompt**: *"We need to handle the reschedule race condition — what happens if the new slot is taken by the time the
request is processed?"*

AI suggested wrapping the reschedule in a single `transaction.atomic()` block that locks both the current appointment
row and the target slot row with `select_for_update()`, then updating `slot_time` in place. The `IntegrityError` from
the unique constraint acts as the rollback trigger — the original slot is never released until the new one is confirmed.
This directly addresses the scenario the reviewer's internal notes flag as critical.

### 3. One example where AI output was wrong or incomplete

The initial `CustomTokenObtainPairView` approach delegated to `TokenObtainPairView.as_view()` by calling
`view(request._request)` — accessing a private attribute and bypassing our custom `TOKEN_OBTAIN_SERIALIZER` setting,
meaning the `role` claim was never added to the token. Caught by tracing through what `TOKEN_OBTAIN_SERIALIZER` actually
does and realising the delegation was circumventing it. The fix was actually kinda easy because all I had to to was to
subclass
`TokenObtainPairView` but override its serializer to use the `CustomTokenObtainPairSerializer` which adds the role
claim.

### 4. Decisions made without AI

** I prompted the AI to create a custom user model with email as the default username field. The AI implemented it using
AbstractBaseUser, explaining that it is more flexible for heavily customised authentication models. Based on my prior
experience building Django applications, I chose to use AbstractUser instead because the project only required email
authentication while retaining Django's built-in authentication functionality. This provided a simpler implementation
that better matched the project's requirements.

** Basically everywhere I found the AI to be over-engineering, including too much defensive programming, I decided to
implement it myself. I found that too much defensive programming was a common source of bugs and was a waste of time. It
could hide genuine bugs in the hope that the application should be fault tolerant.

**Using a partial unique constraint over a full unique constraint**: The constraint is
`UNIQUE (doctor, slot_time) WHERE status = 'active'` rather than `UNIQUE (doctor, slot_time)`. This means cancelled
appointments don't block the slot from being rebooked — a business requirement that a full constraint would silently
violate. This decision came from thinking through the cancellation flow, not from an AI suggestion.
