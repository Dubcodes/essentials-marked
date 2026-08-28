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
- IndexedDB outbox and draft-store foundation. Only offline/network failures and 502/503/504 ordinary event failures are queued; 401/403/409/422 operations are not queued.

## Run locally

Use Node 22 for the supported frontend toolchain and Docker Desktop with Linux containers.

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

## Validation

```sh
cd backend && python -m pytest -q -p no:cacheprovider
cd frontend && npm ci && npm run build
docker compose up --build
```

`package-lock.json` is committed and the Docker web image uses `npm ci` for deterministic installs.

## Backups and retention

Back up PostgreSQL and the `media_data` volume together; back up deployment configuration/secrets separately. Example: `docker compose exec db pg_dump -U essentials essentials_marked > essentials-marked.sql`. Test restoration to a separate database. Parent viewing history is configurable and separate from internal record retention; this build does not automatically delete regulated records.

## Important limitations before live-centre use

The domain APIs are a foundation, not a completed regulatory product. The UI does not yet expose the complete medication authority/receipt/return, incident body-map/signature/notification, import, media-upload or comprehensive admin CRUD flows. Offline ordinary events are queued, but medication and incident finalisation intentionally do not queue because a PIN cannot safely be stored. Run hands-on teacher tablet sessions, conduct an independent privacy/compliance review, complete backup/recovery testing and verify current licensing requirements before any live trial.

See [NZ ECE implementation matrix](docs/compliance/NZ-ECE-COMPLIANCE.md) for sources, implementation status and limitations.
