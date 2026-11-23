# MJD Square

Business management for MJD Square, a Nigerian retail and wholesale business. The repository is a modular monolith: a React/Vite application calls a versioned FastAPI API, and PostgreSQL is the authoritative datastore.

## Current implementation status

The repository contains a working local application and the core transaction slice of an operational MVP. It is not yet a complete implementation of the master blueprint or production-validated. Payment-gateway integration is planned for a later phase and is explicitly outside the MVP.

- React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook Form, and Zod.
- FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, and OpenAPI documentation.
- Owner bootstrap, Argon2 password hashing, database-backed expiring sessions, HttpOnly session cookies, CSRF validation, login throttling, password changes, and backend-enforced permissions.
- Owner-managed staff accounts with least-privilege defaults and immediate account deactivation/session revocation.
- Business profile settings for NGN, Africa/Lagos, and manually recorded payment methods.
- Audit entries for authentication, account, and settings changes.
- Customer and supplier records, documented opening balances, product categories, units and unit conversions, retail/wholesale prices and quantity tiers.
- Product inventory balances with reasoned, append-only opening, adjustment, damaged-stock, sale, and purchase movements.
- Completed retail and wholesale sales with invoice snapshots, applicable price tiers, atomic stock reduction, and protection against negative stock.
- Supplier purchases with stock increases, purchase-cost updates, supplier references, and atomic inventory movements.
- Manual, append-only payments against one sale/purchase invoice or a customer/supplier account balance, including partial payments and outstanding balances. Payment methods come from business settings; payments have no independent verification status or provider verification.
- Standalone manual payment receipts with saved history, print/save-as-PDF output, and a prepared WhatsApp message. These are separate from invoices and do not affect invoice balances or financial reports.
- Invoice due dates default to the sale date and can be changed when recording the sale. Customers can opt in to automatic WhatsApp payment receipts; provider acceptance and webhook-confirmed send/delivery/read/failure are recorded separately from payment status. Customer payment reminders still let staff prepare WhatsApp text and record follow-up activity manually.
- Owner-only transaction history over the audit trail, including transaction, account, inventory, authentication, and settings events.
- Manually recorded expenses, date-range totals, customer/supplier outstanding balances, low-stock counts, CSV summary exports, and browser-printable sales invoices.
- A report-permission-gated dashboard with 7-day, 30-day, and year-to-date sales totals and trends, payment totals, current receivables/payables, invoice-linked overdue aging, top products, recent audited activity, low-stock count, and inventory value at current recorded cost.
- A responsive MJD Square workspace shell, sign-in screen, dashboard, account security, staff, business settings, customer, supplier, inventory, sales, purchases, expenses, reports, payment reminders, and transaction history screens.

## Blueprint reconciliation

Status below is measured against the supplied master development prompt, not just against whether a screen or database table exists. “Partial” means a useful subset works, while important required behavior remains.

| Blueprint area | Status | Implemented | Not yet implemented |
|---|---|---|---|
| Product identity and visual design (§2) | Partial | MJD Square branding, responsive light UI, navy/teal styling, SVG favicon. | Full brand/document system, richer accessible transaction states, realistic isolated demo data. |
| Architecture and infrastructure (§3) | Partial | React/TypeScript and FastAPI modular monolith, migrations, CI, local SQLite and PostgreSQL configuration. | Production deployment, managed secrets/HTTPS, automated backups and restore evidence, structured monitoring, background job system, server-generated PDFs, PWA. |
| Accounts and permissions (§4) | Partial | Owner/staff accounts, server-enforced permissions, password hashing, expiring sessions, CSRF, login throttling, password change/reset flow. | SMTP delivery is not configured by default; credit/discount approvals, reversal controls, and all blueprint-specific permission distinctions are not complete. |
| Navigation and search (§5) | Partial | Responsive permission-filtered navigation for implemented pages, including reminders and owner-only transaction history. | Dedicated invoice/payment pages, document-branding settings, and global search. |
| Dashboard (§6) | Partial | Date-filtered financial cards and sales trend; current customer/supplier balances; invoice-linked overdue aging; top products; recent audited activity; low-stock count; estimated inventory value at current recorded product cost. Dashboard metrics require report permission. | Debt aging does not allocate account payments to invoices; no payment trend, recent payment list, due-date forecast, or inventory valuation accounting method. Current-cost stock value is an estimate, not FIFO or audited valuation. |
| Products and inventory (§7) | Partial | Products, SKU/barcode, categories, units/conversions, costs/prices/tiers, suppliers, stock balances/history, low-stock indicator, audited adjustments, atomic sale/purchase stock movement with nonnegative-stock checks. | Product images, returns/supplier returns, stocktaking/discrepancy reports, inventory valuation, multi-location support. PostgreSQL concurrency behavior needs dedicated validation. |
| Sales and invoices (§8) | Partial | Completed retail/wholesale sales, price tiers, immutable line-price snapshots, invoice number, editable due date (defaults to sale date), manual initial/partial payments, printable invoice, stock deduction. | Draft/approval and credit policy/limits, discounts/taxes, multiple methods or allocations per invoice, customer deposits, returns/refunds, cancellation/reversal/correction. |
| Customer accounts (§9) | Partial | Customer records, documented opening balances, invoice/account payments, aggregate outstanding balance. | Customer ledger/profile totals, overdue amounts, unallocated deposits, per-customer payment/invoice history, returns/reminders, period statements and reconciliation UI. |
| Supplier accounts (§10) | Partial | Supplier records, purchase invoices, stock intake, invoice/account payments, aggregate payable balance. | Due dates/aging, supplier statements/history, returns/adjustments, reconciliation UI. Account payments are not allocated to a specific purchase invoice. |
| Payment recording (§11, supplied excerpt) | Partial | Manual payment methods, invoice/account-linked payment entries, amount, auto-recorded timestamp, reference, notes, and recording user. | Explicit verification states, user-specified transaction time, receiving/paying account and evidence fields, multi-invoice allocation, and full reconciliation workflows. No gateway is needed for this version; manual records still need explicit lifecycle/verification handling. |
| Payment reminders (§12) | Partial | Due-date based customer reminder queue, overdue/upcoming summaries, staff-reviewed WhatsApp message preparation, and append-only manually recorded reminder/follow-up activity. Opt-in payment receipts can be sent through Meta WhatsApp Cloud API and delivery callbacks are tracked separately. | Configurable reminder rules and scheduled delivery. WhatsApp receipt delivery is not proof of settlement. |
| Later blueprint areas | Not assessed from attachment | The shared prompt snapshot ends partway through §11. | The rest of the master prompt was not included in the provided attachment, so no completeness claim is made for it. |

This implementation can demonstrate normal sales, purchases, basic payments, expenses, stock effects, and summary reports with local test data. It is not safe to treat as the complete blueprint or as production financial software. Financial records have no complete reversal/correction lifecycle; use test data until that and the operational controls are implemented and accepted. Offline synchronization and payment-gateway integration are not part of this MVP slice.

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
In local development, payment receipts are stored privately under `backend/data/payment-receipts/` by default, so uploads work without an S3 account. Keep this directory in local backups as needed; production requires the private S3-compatible storage described below.

FastAPI's interactive API documentation is available at `http://localhost:8000/docs`; liveness and database readiness checks are at `/health/live` and `/health/ready`.

## Docker Compose

For a disposable local PostgreSQL database and development servers:

```sh
docker compose up --build
docker compose exec backend python -m app.cli create-admin --email owner@example.com --name "Business Owner"
```

Open `http://localhost:5173`. Compose's database credentials are local-development defaults only. Replace them and use managed secrets, TLS, secure cookies, and restricted network access in any deployed environment. Database data is stored in the `postgres-data` volume.

## Vercel hosting

The Vercel configuration uses two projects connected to this repository so the static frontend and Python API can each use their native Vercel runtime:

1. Create an API project named `mjd-square-api` with **Root Directory** `backend`. Vercel detects the FastAPI entrypoint from `backend/pyproject.toml`.
2. Assign `mjd-square-api.vercel.app` as the API project's stable domain. The frontend rewrite in `frontend/vercel.json` targets this domain; if it is unavailable, assign another stable API domain and update both rewrite destinations to match.
3. Create a frontend project with **Root Directory** `frontend`. Vercel detects Vite, builds with `npm run build`, and serves the SPA. Its rewrites proxy `/api/*` and `/health/*` to the API while keeping browser requests same-origin for session and CSRF cookies.
4. Configure the API project's Production environment variables:
   - `APP_ENV=production`
   - `DATABASE_URL` with a managed PostgreSQL URL (use the provider's pooled connection string where available; do not use SQLite)
   - `COOKIE_SECURE=true`
   - `OWNER_SETUP_TOKEN` set to a unique random value of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and keep it in the provider's secret environment settings. Give it to the business owner through a separate trusted channel; never put it in a URL or source control.
   - `CORS_ORIGINS` and `FRONTEND_URL` set to the frontend's exact HTTPS production origin
   - `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_USERNAME` (Brevo SMTP login), `SMTP_PASSWORD` (the full Brevo SMTP key, not an API key), `SMTP_USE_STARTTLS=true`, and `MAIL_FROM` (a verified sender address) for password recovery email. Keep all credentials in the hosting provider's secret environment settings, not in source control.
   - `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` for a **private** S3-compatible bucket; `S3_ENDPOINT_URL` is optional for compatible providers. Grant the API credentials access only to the receipt bucket, and keep public access/block-public-access enabled.

   For Backblaze B2, the equivalent supported environment names are `B2_REGION`, `B2_BUCKET`, `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, and `B2_S3_ENDPOINT_URL`. Create a private B2 bucket, create an application key restricted to that bucket, and set the endpoint to the bucket's S3-compatible endpoint, for example `https://s3.eu-central-003.backblazeb2.com`. Use the B2 region value (not a friendly bucket name) for `B2_REGION`, keep bucket public access disabled, and do not expose the application key in browser code or source control.
5. Before serving traffic, apply migrations to the managed database with `alembic upgrade head` from `backend/`, using a trusted environment that has the production database URL and never committing credentials. Then open the production frontend at `/setup` and create the initial owner account using the setup token. Setup becomes unavailable after the first owner is created; rotate `OWNER_SETUP_TOKEN` to a new random value afterward. As an alternative, create the owner from a trusted environment with `python -m app.cli create-admin`; the UI setup is also disabled automatically once that owner exists.

The database, SMTP account, private object-storage bucket, and Vercel environment variables must be provisioned by the operator; deployments do not create or migrate a production database automatically. Receipt uploads accept PDF, JPEG, PNG, and WebP files up to 10 MiB. Receipt objects are retained in private storage and downloaded through a short-lived signed URL after staff permission checks. Include the bucket in your backup, retention, and recovery plan; deleting a payment record does not delete its evidence. Configure a separate staging database and matching frontend/API projects before enabling Preview deployments, otherwise previews can use the production API rewrite. Verify `/health/ready`, sign-in, password recovery, uploads and authorized downloads, and a test transaction after deployment. A Vercel deployment scaffold is not a substitute for backup/restore drills, financial control acceptance, or production monitoring.

## Database and recovery

Apply migrations from `backend/` with `alembic upgrade head`; review the migration before applying it to a production database. The committed migration history starts with authentication, permissions, business settings, and audit records.

For a local PostgreSQL backup and restore, use PostgreSQL's standard tools:

```sh
pg_dump --format=custom --file=mjd-square.backup "$DATABASE_URL"
pg_restore --clean --if-exists --dbname="$DATABASE_URL" mjd-square.backup
```

Protect backups as sensitive financial data, encrypt them at rest and in transit, restrict access, and test restoration against a separate database before relying on them. These commands are operational guidance, not an automated production backup service.

## WhatsApp payment receipts

Customers must explicitly agree to receipt messages and have a WhatsApp number on their record. Changing their number clears consent. When a customer payment is recorded, the API attempts a receipt using Meta's WhatsApp Cloud API; payment recording does not depend on WhatsApp being available. A receipt status of `accepted` means Meta accepted the request, while `sent`, `delivered`, `read`, and `failed` are updated by webhook callbacks. None of these statuses verifies bank settlement.

Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` (a currently supported, pinned Meta Graph API version), and `WHATSAPP_RECEIPT_TEMPLATE` to enable sending. The named template must be approved by Meta in the language selected by `WHATSAPP_RECEIPT_TEMPLATE_LANGUAGE`. Its body must contain eleven text placeholders, in order: recipient name, business name, payment direction ("payment received by MJD Square from you" or "payment made by MJD Square to you"), receipt number, invoice/account reference, amount and currency, payment method, payment reference, local date/time, remaining balance and currency, and the manual-record-not-bank-confirmation disclaimer. Customers and suppliers must separately opt in on their records; changing the WhatsApp number clears consent. Supplier notices are sent only for supplier payments, not when recording supplier invoices. Configure `WHATSAPP_APP_SECRET` and `WHATSAPP_WEBHOOK_VERIFY_TOKEN` together and set the Meta webhook URL to `https://<api-host>/webhooks/whatsapp`, subscribing to message status updates. Keep these values in hosting-provider secrets, not source control. Apply `alembic upgrade head` before deploying this feature.

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

The work follows the staged blueprint. The payment gateway is a future integration phase and is not required for the first release.

1. **Foundation (partially implemented):** repository, database configuration, authentication, core RBAC, business settings, shared UI, CI, and tests are present. Production infrastructure, search, PWA, monitoring, automated backup, and other blueprint items remain.
2. **Business records (partially implemented):** product/customer/supplier setup, units and price tiers, opening balances, and audited stock movements are available. Inventory valuation, returns, and stocktaking are not.
3. **Core transaction MVP (partially implemented):** completed retail/wholesale sales and invoices, manual payments against one invoice or account balance, purchases, supplier balances, expenses, period summaries, and transaction-driven inventory changes. Approval policies, due dates, returns/refunds, reversal/correction workflows, and multi-invoice allocation remain.
4. **Receipts, reminders, and reports (partially implemented):** browser-printable sales invoices, outstanding-balance/period reports, CSV summary exports, a permission-gated financial dashboard, and opt-in WhatsApp payment receipts with separately tracked delivery status are available. PDF documents, statements, allocated payment history, configurable overdue alerts, and some audit-history workflows remain.
5. **Offline operation (not implemented):** PWA installation, carefully scoped IndexedDB storage, idempotent synchronization, visible sync state, and conflict handling.
6. **Production readiness (not complete):** security and performance reviews, PostgreSQL deployment validation, backup restoration tests, user acceptance, deployment, data migration, and staff onboarding.
7. **Future payment-gateway integration (OPay planned):** confirm business-account eligibility and official provider capabilities first; then implement and test secure server-side events, reconciliation, and audit handling. The integration must not block launch, and manual cash, POS, and transfer recording remain the fallback.

Do not treat an opening balance as a historical invoice, or a manual payment entry as independently verified by a bank or provider. Sales and purchases now create inventory movements; all future stock-affecting actions must preserve that ledger relationship.

## Security notes

- Never commit `.env`, production data, or provider credentials.
- Use HTTPS and set `COOKIE_SECURE=true` in production.
- The frontend does not connect directly to PostgreSQL.
- Staff permissions are enforced by the API, not only by navigation visibility.
- Manual payment methods record staff-entered information and do not claim independent bank/provider verification.
- Payment-gateway integration is not active. Do not configure or expose payment-provider credentials until the future integration phase is approved and official provider requirements are verified. WhatsApp credentials are separate and only used for opted-in payment receipt messages.
- Completed financial records will require reversal or adjustment workflows; deleting transactions is not part of the design.
