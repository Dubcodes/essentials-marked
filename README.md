# Essentials Marked

Essentials Marked is a focused, browser-based daily-care recording system for early-childhood classrooms. It supports fast care entries, room-console attribution, parent daily records and a small operational admin surface. It deliberately does not replace enrolment administration, learning stories, chat, payroll or emergency systems.

## Architecture

- **Web:** React + TypeScript + Vite single-page interface, served by Nginx.
- **API:** FastAPI + SQLAlchemy 2 with tenant-scoped records and Alembic migration.
- **Data:** PostgreSQL 16 with a persistent Docker volume; media volume is reserved for validated uploads.
- **Deployment:** Three services in `docker-compose.yml`: `web`, `api`, and `db`. Nginx serves same-origin `/api` requests, so cookies are not exposed to cross-origin browser scripts.

## Quick start

```sh
copy .env.example .env
docker compose up --build
```

Open `http://localhost:8088`. Development-only seeded credentials:

- Admin: `admin@demo.local` / `ChangeMe123!`
- Parent: `demo-parent` / `123456`
- Sample staff PINs: Sarah `1234`, Michael `2345`, Aroha `3456`

Set a unique `SECRET_KEY`, database password and `COOKIE_SECURE=true` behind HTTPS before any real deployment. Set `DEMO_SEED=false` for a production database. Portainer can deploy the same compose file after setting environment values.

## Workflows included

- Secure classroom pairing tokens: 60-second expiry, single use, visual challenge and remote device revocation.
- Persistent room-console state: room and selected staff are distinct; ordinary events have quick touch forms.
- Nappy/toilet, food, sunscreen, sleep start/end/check, medicine, incident, staff note and supply event APIs.
- Multiple-child entry, present-child selection, actual attendance and temporary room visits.
- Performed-by and recorded-by staff attribution. Admin correction creates a separate audit row instead of overwriting history; finalised medicine/incident records reject bulk-style attribution corrections.
- Parent sign-in, many-to-many child access, chronological daily timeline, operational note submission and access-controlled CSV export.
- IndexedDB write queue in the classroom UI. New ordinary events receive a browser UUID, persist locally when offline, retry on reconnection, and use server-side idempotency keys.

## Operations and backup

Back up the PostgreSQL volume and `media_data` volume together. For a compose deployment, operators can run `docker compose exec db pg_dump -U essentials essentials_marked > essentials-marked.sql` from a trusted host, then test restoring into a separate database. Never store backups in publicly readable locations.

## Security notes

Credentials and staff PINs use Argon2 hashes. Sessions are HttpOnly, SameSite cookies and device sessions can be revoked. API queries scope objects to the authenticated centre; parent child IDs are checked against the parent-child relation. Login attempts have basic per-process rate limiting. Production still needs HTTPS, a persistent/distributed rate limiter, secret management, database backups, CSP tuning, upload routes with image validation, and an independent privacy/compliance assessment.

## Development and test

```sh
cd backend && python -m pytest
cd frontend && npm install && npm run build
docker compose up --build
```

The test suite covers parent object access, high-consequence PIN enforcement and idempotent retry. The first demo uses fictional names only.

## Project layout

`backend/` contains the FastAPI application, models, migration and tests. `frontend/` contains the tablet, parent and admin SPA. `docs/compliance/NZ-ECE-COMPLIANCE.md` contains the NZ guidance review and its source links.

## Known first-version limitations

This is a strong operational demo foundation, not a legal-compliance certification. The current UI exposes the common teacher workflow and core data paths, but full incident/medication authority capture, signature canvas and revision acknowledgement, image uploads/import wizard, configurable retention administration, exhaustive admin CRUD, service-worker cache, and production-grade shared rate limiting remain the highest-priority additions before live-centre use. Validate workflow speed on actual tablets with educators before trialling it.
