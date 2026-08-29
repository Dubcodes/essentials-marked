# Essentials Marked

Essentials Marked is a focused browser application for recording daily early-childhood care. It supports classroom tablet operations, a small parent daily record and a centre admin view. It is not an enrolment, learning-story, messaging, payroll or emergency-management system.

## Current foundation

- React 18/Vite 5 front end; FastAPI/SQLAlchemy 2 API; PostgreSQL 16; Nginx same-origin proxy.
- Explicit Alembic schema migration. The earlier prototype database must be reset before this version: development data is disposable.
- Centre-scoped rooms, children, staff, parents, devices, attendance and events.
- Server-side, revocable sliding sessions: device inactivity defaults to seven days, parent to 30 days, admin to 12 hours.
- Bcrypt password/PIN hashes. Staff PINs are transient verification secrets and are stripped from all ordinary domain payloads and local outbox records.
- Fast nappy/toilet, food, sunscreen, staff note, supply, attendance and room-presence event APIs; room selection is sent and validated per operation.
- Explicit sleep-session/check, medicine authority/receipt/administration and incident domain APIs.
- Parent child-scoped timeline/export. Staff-only notes are filtered by the server and never exported.
- IndexedDB outbox and draft-store foundation. Offline/network failures and 502/503/504 ordinary event failures are queued; Food also treats Vite's local proxy 500 during an upstream outage as retryable. 401/403/409/422 operations are not queued.
- Cached last-confirmed emergency roll and a service-worker app shell support read-only emergency accountability after an offline relaunch.
- Teacher workspaces keep the full roster visible, distinguish physical-room eligibility, preserve retries through stable operation IDs, and provide explicit sleep-session reconciliation.
- Admin navigation exposes operational rooms, children, staff, devices/pairing, records, audit, family data requests, centre timezone and branding views.

## Run locally

The reproducible web image is pinned to Node 22. Local frontend checks are supported on Node 22 through 24; this release was also verified on Node 24. Use Docker Desktop with Linux containers for the full stack.

```sh
copy .env.example .env
docker compose up --build
```

Open `http://localhost:8088`. The checked-in example is explicitly **development only** and sets demo seed data:

- Admin: `admin@demo.local` / `ChangeMe123!`
- Parent: `demo-parent` / `123456`
- Staff PINs: Sarah `1234`, Michael `2345`, Aroha `3456`

## Production checklist

Set `APP_ENV=production`, a unique 32+ character `SECRET_KEY`, a non-trivial database password, `COOKIE_SECURE=true`, the exact HTTPS `PUBLIC_ORIGIN`, and `DEMO_SEED=false`. Production startup rejects the default secret, insecure cookies and demo seeding. Terminate HTTPS at a trusted reverse proxy/Cloudflare Tunnel and do not forward untrusted client-IP headers as an identity source.

The API container runs `alembic upgrade head` before starting Uvicorn. PostgreSQL and uploaded media use the named `postgres_data` and `media_data` volumes; treat migration, database backup and media backup as one deployment procedure.

## Validation

```sh
cd backend && python -m pytest -q -p no:cacheprovider
# Optional real PostgreSQL migration/domain probe:
POSTGRES_TEST_URL=postgresql+psycopg://... python -m pytest -q -p no:cacheprovider tests/test_postgres_integration.py
cd frontend && npm ci && npm test && npm run typecheck && npm run build
docker compose config --quiet
docker compose up --build
```

`package-lock.json` is committed and the Docker web image uses `npm ci` for deterministic installs.

### Development-tool audit status

Vite 5.4.21 and Vitest 2.1.9 include the low-risk fixes available on their current release lines. `npm audit` still reports five findings inherited through the Vite/Vitest development servers (three moderate, one high and one critical); the registry currently offers only major-version upgrades to clear them. Those servers are not shipped in the production image—the compiled static assets are served by Nginx—and Vitest is run in one-shot CLI mode without its UI/API server. Major toolchain upgrades are deferred to a dedicated compatibility pass.

## Backups and retention

Back up PostgreSQL and the `media_data` volume together; back up deployment configuration/secrets separately. Example: `docker compose exec db pg_dump -U essentials essentials_marked > essentials-marked.sql`. Test restoration to a separate database. Parent viewing history is configurable and separate from internal record retention; this build does not automatically delete regulated records.

## Important limitations before live-centre use

This remains a trial build, not a completed regulatory product. Medication receipt/administration/return, structured incident drafts, pairing, audit, branding and the core trial administration views are exposed, but enrolment/import, broad media workflows, incident notifications/signatures and comprehensive CRUD remain outside this pass. Offline ordinary events are queued, while medication and incident finalisation intentionally require a live connection because a PIN cannot safely be stored. The PostgreSQL integration test is opt-in and requires a reachable disposable PostgreSQL database; the default SQLite suite does not substitute for running it. Run hands-on teacher tablet sessions, conduct an independent privacy/compliance review, complete backup/recovery testing and verify current licensing requirements before any live trial.

See [NZ ECE implementation matrix](docs/compliance/NZ-ECE-COMPLIANCE.md) for sources, implementation status and limitations.
