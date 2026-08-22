# Deployment — Docker & Coolify

Status: **recommended architecture** (to be finalized during implementation).
Coolify is available at `http://192.168.1.107:8000/` (staging on the same host).

---

## 1. Container topology (proposed)

```
Coolify (192.168.1.107:8000)
├── gadgeto-frontend (Next.js)         → public port 3000 (proxy / nginx)
├── gadgeto-backend (FastAPI + uvicorn)→ public port 8000 (proxy /api /admin)
├── gadgeto-worker (Celery worker)     → internal only
├── gadgeto-redis (Redis)              → internal only
└── gadgeto-db (PostgreSQL 16)         → internal only (+ volume for data)
```

- **Frontend** talks to the backend via `NEXT_PUBLIC_API_URL` (internal network URL
  in production: `http://gadgeto-backend:8000`).
- **Worker** uses the same image as the backend + a `celery -A app.core.celery_app worker`
  command, so one Dockerfile serves two roles.
- Reverse proxy (Coolify's built-in Caddy/nginx) terminates TLS; the app itself
  doesn't need TLS termination logic.

## 2. Docker-Compose (local dev)

Services in `docker-compose.yml`: `db` (postgres), `redis`, `backend`, `worker`,
`frontend`. Healthchecks for db/redis (depends_on condition), volume mounts for
`pgdata`, `redis-data`, `media/`. Env from `.env`.

## 3. Release process

1. `alembic upgrade head` runs as a backend start-step (entrypoint) — idempotent,
   release-gated in CI.
2. Backend image tags: git sha; coolify redeploys the three services.
3. Frontend build: `npm run build` (SSG/`output: 'standalone'`).

## 4. Coolify specifics

- Create a **separate project** "Gadgeto Staging" with the app shown above.
- Use the repo URL; environment variables per service (see `ENVIRONMENT.md`);
  never commit real secrets.
- Persistent volumes attached to db/redis/media (Coolify managed volumes).
- The production domain (`gadgeto.com.ua`) is NOT pointed to the new deployment
  until cutover approval (Phase 10).

## 5. Backups & recovery

- DB: `pg_dump -Fc` nightly (scripts/backup_db.sh) → rotate 14 days; also before
  every migration run.
- Media: tar of `media/` volume.
- Recovery: restore the latest dump into a fresh container; run `alembic upgrade
  head`; smoke-test; update `url_aliases` if needed.
- Legacy rollback: WordPress remains untouched; DNS can be flipped back in minutes.

## 6. Environment once running

- `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, media paths, admin user bootstrap:
  create first admin via CLI/`scripts/create_admin.py`.