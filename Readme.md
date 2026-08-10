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

- **Timezone**: `work_start` and `work_end` are stored as bare `TimeField` values interpreted in `CLINIC_TIMEZONE`
  (default: `Africa/Nairobi`). When generating slots, the service converts clinic local times to UTC using `zoneinfo`.
  All API responses return UTC ISO 8601 datetimes — client applications are responsible for converting to the user's
  local timezone for display. A multi-location clinic would need a timezone field per `Doctor` rather than a single
  global setting.
- **Working hour changes**: When a doctor's working hours change, any active appointment that no longer falls within the
  updated schedule is cancelled automatically and marked with the update reason. This is currently applied to active
  bookings that still fit the future booking window.

- **Day-wide cancellation**: The service supports cancelling all active appointments for a given day by doctor/admin
  action, but this is still handled through the service layer rather than a dedicated public endpoint.
- **Password reset**: Out of scope. Requires email infrastructure. Noted as a V2 concern.
- **`date` parameter on availability**: Means the shift start date, not the calendar date. A night-shift doctor's July
  13 availability returns slots from `2026-07-13 22:00Z` to `2026-07-14 05:30Z`.
- **Creating a new doctor**: While I don't think doctors should be self-registering, we could have an endpoint to create
  them only that it would be a separate admin-only operation.
- Doctors should have specialisations. You can't just book any doctor e.g. you shouldn't book a cardiologist if you want
  an oncologist. They won't help you.
- We do not account for breaks e.g. lunch break instead we only track work_start, work_end, and is_available.
- Actually known bug: theoretically, a doctor's shift could start at 8:03 and in that case we'd generate slots like 08:
  03, 08:33, 09:03 ... The booking code would then reject because it's not on :00 or :30. We've simplified the code to
  assume work starts exactly at the top of the hour or at 30 minues into the hour.

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

The API is available at `http://localhost:8000`. Interactive API docs at `http://localhost:8000`

### Running Test

```bash
uv run pytest
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

The API is available at `http://localhost:8000`. Source code is mounted as a volume — changes reload automatically.

---

## API Overview

### Authentication

All endpoints except `POST /api/auth/register/` and `POST /api/auth/login/` require a JWT access token:

```txt
Authorization: Bearer <access_token>
```

### Endpoints

| Method  | Endpoint                                          | Auth                 | Description                                                                                                                |
|---------|---------------------------------------------------|----------------------|----------------------------------------------------------------------------------------------------------------------------|
| `POST`  | `/api/auth/register/`                             | None                 | Register as a patient. Returns token pair immediately.                                                                     |
| `POST`  | `/api/auth/login/`                                | None                 | Login. Returns access + refresh tokens.                                                                                    |
| `POST`  | `/api/auth/token/refresh/`                        | None                 | Get a new access token using a refresh token.                                                                              |
| `POST`  | `/api/auth/logout/`                               | Required             | Blacklist the refresh token.                                                                                               |
| `GET`   | `/api/auth/me/`                                   | Required             | Get current user profile.                                                                                                  |
| `PATCH` | `/api/auth/me/`                                   | Required             | Update profile (first name, last name, email).                                                                             |
| `GET`   | `/api/doctors/`                                   | Required             | List all available doctors.                                                                                                |
| `GET`   | `/api/doctors/{id}/`                              | Required             | Get a single doctor.                                                                                                       |
| `GET`   | `/api/doctors/{id}/availability/?date=YYYY-MM-DD` | Required             | Available 30-minute slots for a doctor on a given date (UTC).                                                              |
| `GET`   | `/api/appointments/`                              | Authenticated        | List appointments visible to the current user. Doctors see their own appointments; patients see their own; admins see all. |
| `POST`  | `/api/appointments/`                              | Patient only         | Book an appointment.                                                                                                       |
| `PATCH` | `/api/appointments/{id}/cancel/`                  | Patient/doctor/admin | Cancel an appointment with a reason. Patients can cancel their own; doctors can cancel their own; admins can cancel any.   |
| `PATCH` | `/api/appointments/{id}/reschedule/`              | Patient only         | Move to a new slot. Only the patient who owns the booking can reschedule it.                                               |
| `GET`   | `/api/patients/{id}/appointments/`                | Owner only           | Upcoming active appointments sorted by date.                                                                               |
| `GET`   | `/`                                               | None                 | Interactive Swagger UI.                                                                                                    |

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

- This workflow works on a PR, when opened and when the PR is updated.
- It runs the AI-generated review workflow on the PR.
- The workflow takes advantage of the qodo github plugin and comments "/review" on the PR which triggers the review bot.
- The review bot will then review the PR and provide feedback on what can be improved or potential bugs.
- Mine is to review the feedback and evaluate whether the suggested changes are necessary.

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

# AI Reflection

## 1. How I Used AI Across the Four Sections

### Section 1 — Design

I used AI primarily to brainstorm and reason during the design phase. With AI, I explored edge cases and
compared possible approaches, particularly around:

* Overnight shifts and time boundaries
* Appointment rescheduling and race conditions
* Whether appointment slots should be computed dynamically or stored
* Timezone handling
* Database constraints and their implications for the appointment lifecycle

I provided the requirements and proposed the models and business rules, while using AI to challenge those
decisions and explore alternative approaches. The final design decisions were mine and were based on the project's
requirements and trade-offs.

### Section 2 — Implementation

I used AI during implementation, particularly for generating boilerplate and translating my design into
Django code.

For example, I designed the database models, relationships, and constraints and then used AI to generate the initial
Django model implementations. I reviewed the generated code against my intended design and modified or rejected
suggestions where they did not fit the requirements.

Some examples of issues I identified during review included:

* AI initially used `timezone.utc`, which is not a Django attribute; the implementation needed to use `datetime.UTC`.
* A shared `AuthRateThrottle` scope caused the login and registration endpoints to share the same rate-limit counter,
  which was not the intended behaviour.
* An initial implementation of the custom JWT view bypassed the configured `TOKEN_OBTAIN_SERIALIZER`, resulting in the
  custom `role` claim not being added to the token.

AI also generated the initial test suite. I reviewed the tests and used them as part of validating the implementation,
but I recognise that I relied more heavily on AI for test generation than for the architectural and business-logic
decisions. I therefore treated passing tests as evidence of validation rather than as proof that the implementation was
correct.

### Section 3 — Deployment

I used AI to generate the initial GitHub Actions workflows, including the workflow for deploying the application to
Render and the CodeQL scanning workflow.

During the deployment work, AI also generated several additional deployment-related files, including a `Procfile`,
`render.yaml`, and `build.sh`. I did not simply accept these files. I checked the Render documentation and found that
the deployment workflow could be considerably simpler by using a Render Deploy Hook.

I therefore chose to use the documented `RENDER_DEPLOY_HOOK_URL` approach instead of introducing deployment
configuration that was not required for this project.

For example, the deployment workflow ultimately used the documented approach of triggering the Render deployment
directly:

```yaml
steps:
  - name: Trigger Render deployment
    env:
      RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}
    run: |
      response=$(curl --fail --silent --show-error "$RENDER_DEPLOY_HOOK_URL")
      echo "$response"
```

This was a useful example of where AI-generated output was more complicated than necessary. Rather than assuming that
generated configuration was required, I verified the deployment requirements against the platform's documentation and
chose the simpler solution.

I also investigated CodeQL after encountering it in another project and asked AI whether it could be incorporated into a
Django project. AI generated the initial workflow, but when the workflow failed, it was unable to identify the
underlying cause from the available information.

I therefore investigated the failure independently and discovered that the issue was related to the repository's CodeQL
availability/configuration. This reinforced the importance of understanding generated configuration and being able to
troubleshoot it independently rather than relying on AI to diagnose every problem.

### Section 4 — Reflection

I wrote this section independently.

---

## 2. An Example Where AI Improved the Work

One useful example was handling the race condition during appointment rescheduling.

I prompted AI with the following problem:

> "We need to handle the reschedule race condition — what happens if the new slot is taken by the time the request is
> processed?"

AI suggested using a single `transaction.atomic()` block and locking the relevant rows with `select_for_update()` so
that the current appointment and target slot could be handled atomically.

The important part of this interaction was not simply generating the code, but using AI to reason through what could
happen when two requests attempted to modify the same appointment slot concurrently.

The resulting implementation ensures that the original appointment is not released until the new slot has been
successfully secured. The database constraint provides an additional layer of protection, with an `IntegrityError`
causing the transaction to roll back if the uniqueness constraint is violated.

This helped me reason more explicitly about the difference between handling the normal application flow and protecting
the system against concurrent requests.

---

## 3. An Example Where AI Output Was Wrong or Incomplete

One significant example involved the custom JWT authentication flow.

The initial implementation generated by AI delegated to `TokenObtainPairView.as_view()` by calling:

```python
view(request._request)
```

This had two problems. First, it relied on the private `_request` attribute. More importantly, the delegation bypassed
the custom `TOKEN_OBTAIN_SERIALIZER` configuration, meaning that the custom `role` claim was not being added to the JWT
as intended.

I identified the problem by tracing how the configured serializer was actually used and comparing that with the
generated implementation.

The fix was straightforward: I subclassed `TokenObtainPairView` and explicitly configured it to use
`CustomTokenObtainPairSerializer`, which is responsible for adding the `role` claim.

This was a good example of why generated code needs to be understood and reviewed rather than accepted simply because it
appears to follow the framework's conventions.

---

## 4. Decisions I Made Without AI

### Render Deployment Approach

One deployment decision I made independently was how the application would be deployed to Render.

Although AI generated several deployment-related files, including a `Procfile`, `render.yaml`, and `build.sh`, I did not
consider these files necessary simply because they had been generated. I checked the Render documentation and found that
the deployment could be triggered directly from GitHub Actions using a Render Deploy Hook through the
`RENDER_DEPLOY_HOOK_URL` secret.

I chose this approach because it was simpler and aligned with the documented deployment mechanism for the project. This
avoided introducing additional configuration and files that were not required to achieve the desired deployment
workflow.

This was a good example of using AI for generating an initial solution while independently verifying whether the
proposed solution was actually appropriate for the platform and project requirements.

### Custom User Model

I decided how the project's custom user model should be implemented.

AI initially suggested using `AbstractBaseUser`, explaining that it provides greater flexibility for heavily customised
authentication models. Based on my previous experience with Django, I determined that this project did not require that
level of customisation.

The requirement was primarily to use email as the unique authentication identifier while retaining Django's built-in
authentication functionality. I therefore chose `AbstractUser` instead, which provided the required customisation while
keeping the implementation simpler.

### Avoiding Unnecessary Defensive Programming

I also rejected several instances where AI proposed additional defensive programming that I considered unnecessary for
the project's requirements.

My approach was to avoid adding complexity merely to handle hypothetical failure modes. Where there was no meaningful
recovery strategy, I preferred to keep the implementation simple and allow genuine programming errors to surface rather
than masking them with broad exception handling or unnecessary fallback behaviour.

The principle I followed was that defensive programming should address a realistic failure mode and provide a useful
recovery or error-handling strategy.

### Conditional Unique Constraint

One important database decision I made was to use a conditional unique constraint rather than a full unique constraint
for appointments.

The constraint is effectively:

```text
UNIQUE (doctor, slot_time) WHERE status = 'active'
```

rather than:

```text
UNIQUE (doctor, slot_time)
```

This means that cancelled appointments do not prevent the same doctor and time slot from being booked again.

A full unique constraint would have prevented this and therefore conflicted with the required cancellation and rebooking
behaviour.

This decision came from reasoning through the appointment lifecycle and the business requirements rather than from an AI
recommendation.

---

## 5. Overall Reflection

Using AI significantly accelerated the implementation of the project, particularly for boilerplate code, test generation,
and configuration. However, I found that its usefulness depended heavily on how it was used.

I did not treat AI-generated output as authoritative. I provided the requirements and design decisions, used AI to
explore alternatives and generate implementation code, and then reviewed the resulting code against the intended
behaviour.

The most valuable part of the process was often identifying where AI was **wrong, overly complex, or making assumptions
that did not apply to the project**. This required understanding the framework, the business requirements, and the
consequences of the implementation rather than simply checking whether the generated code looked reasonable.

The project reinforced my view that AI is most useful as an engineering copilot: it can significantly reduce the time
spent on repetitive implementation work and help explore solutions, but the developer still needs to own the
architecture, make the trade-offs, verify the output, and take responsibility for the final system.
