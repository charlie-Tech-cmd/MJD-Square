# MJD Square

Business management for MJD Square, a Nigerian retail and wholesale business. The repository is a modular monolith: a React/Vite application calls a versioned FastAPI API, and PostgreSQL is the authoritative datastore.

## What is implemented

The initial foundation includes:

- React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook Form, and Zod.
- FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, and OpenAPI documentation.
- Owner bootstrap, Argon2 password hashing, database-backed expiring sessions, HttpOnly session cookies, CSRF validation, login throttling, password changes, and backend-enforced permissions.
- Owner-managed staff accounts with least-privilege defaults and immediate account deactivation/session revocation.
- Business profile settings for NGN, Africa/Lagos, and manually recorded payment methods.
- Audit entries for authentication, account, and settings changes.
- A responsive MJD Square workspace shell, sign-in screen, dashboard setup state, account security, staff, and business settings screens.

Sales, inventory, customer/supplier records, receipts, reports, reminders, and offline synchronization are not implemented yet. Dashboard figures are intentionally omitted until authoritative business records exist. No payment gateway or provider credentials are part of this launch foundation.

## Local development

Requirements for the no-Docker local setup: Python 3.12+, Node.js 20.19+ (or 22.12+), and npm. Local development defaults to an on-disk SQLite database. PostgreSQL 15+ is recommended for production and is available through the optional Docker Compose setup.

1. No `.env` file is required for the local SQLite setup. The API defaults to `backend/data/mjd_square.db` and creates the data directory automatically. To configure it explicitly from the `backend/` directory, copy `.env.example` to the repository root `.env`; its SQLite URL is relative to the backend working directory.
2. Create and activate a backend virtual environment, then install and migrate:

   ```sh
   cd backend
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e ".[dev]"
   alembic upgrade head
   python -m app.cli create-admin --email owner@example.com --name "Business Owner"
   uvicorn app.main:app --reload
   ```

   The command securely prompts for the initial owner's password; passwords must be 12–128 characters. Only the first owner can be created through this bootstrap command.

   The API starts at `http://localhost:8000`. Leave it running. In a separate terminal:

   ```sh
   cd frontend
   npm ci
   npm run dev
   ```

   Open `http://localhost:5173`. Vite proxies `/api` and `/health` to FastAPI on port 8000. If the API is stopped, the app explains that the backend/database is unavailable and provides a retry action.

SQLite is intended for a single local development instance, not concurrent production traffic. The production configuration rejects SQLite and requires PostgreSQL plus secure cookies.

FastAPI's interactive API documentation is available at `http://localhost:8000/docs`; liveness and database readiness checks are at `/health/live` and `/health/ready`.

## Docker Compose

For a disposable local PostgreSQL database and development servers:

```sh
docker compose up --build
docker compose exec backend python -m app.cli create-admin --email owner@example.com --name "Business Owner"
```

Open `http://localhost:5173`. Compose's database credentials are local-development defaults only. Replace them and use managed secrets, TLS, secure cookies, and restricted network access in any deployed environment. Database data is stored in the `postgres-data` volume.

## Database and recovery

Apply migrations from `backend/` with `alembic upgrade head`; review the migration before applying it to a production database. The committed migration history starts with authentication, permissions, business settings, and audit records.

For a local PostgreSQL backup and restore, use PostgreSQL's standard tools:

```sh
pg_dump --format=custom --file=mjd-square.backup "$DATABASE_URL"
pg_restore --clean --if-exists --dbname="$DATABASE_URL" mjd-square.backup
```

Protect backups as sensitive financial data, encrypt them at rest and in transit, restrict access, and test restoration against a separate database before relying on them. These commands are operational guidance, not an automated production backup service.

## Verification

From `backend/`:

```sh
pytest
ruff check .
alembic upgrade head
```

From `frontend/`:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

The backend tests use isolated SQLite databases for fast unit/API coverage. PostgreSQL migrations and CI use PostgreSQL; SQLite is not the production datastore.

## Roadmap

1. **Foundation (implemented):** authentication, RBAC, business settings, shared UI, CI.
2. **Business records:** products, customers, suppliers, units, opening balances, and auditable stock movements.
3. **Transactions:** sales, invoices, payment entries and allocations, purchases, supplier balances, expenses, returns, and corrections.
4. **Operations and reporting:** receipts, statements, reminders, reports, exports, and complete financial audit workflows.
5. **Offline operation:** PWA, carefully scoped IndexedDB storage, idempotent synchronization, and conflict handling.
6. **Production readiness:** security review, performance checks, migration and backup restoration tests, deployment, and onboarding.
7. **Planned future OPay integration:** only after account eligibility and official provider capabilities are confirmed. It is not a launch dependency; manual cash, POS, and transfer recording remain the fallback.

## Security notes

- Never commit `.env`, production data, or provider credentials.
- Use HTTPS and set `COOKIE_SECURE=true` in production.
- The frontend does not connect directly to PostgreSQL.
- Staff permissions are enforced by the API, not only by navigation visibility.
- Manual payment methods record staff-entered information and do not claim independent bank/provider verification.
- Completed financial records will require reversal or adjustment workflows; deleting transactions is not part of the design.
