# Development Guide

## Quick Start

Start the development environment with hot reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
## How Hot Reload Works

### Backend (FastAPI + Uvicorn)

- The backend container runs `uvicorn --reload`.
- When you edit any Python file in `backend/app/`, uvicorn detects the change and reloads.
- The host `./backend/app/` directory is bind-mounted into the container at `/app/app/`.
- The host `./migrations/` directory is bind-mounted into the container at `/app/migrations/`.
- Changes are reflected within 1–2 seconds.

### Frontend (Next.js)

- The frontend container runs `npm run dev`.
- Next.js watches the `src/` directory for changes.
- The host `./frontend/` directory is bind-mounted into the container at `/app/`.
- Changes are reflected within 1–3 seconds (Next.js fast refresh).
- `node_modules` lives in a named Docker volume (`frontend_node_modules`) to avoid platform conflicts.

### Admin (Next.js)

- Same architecture as Frontend.
## Start vs Stop vs Restart

### First start (build + up)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This builds the dev images and starts the containers.

### After stopping (up again — no rebuild)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Restart a single service

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart admin
```

### View logs

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=50 -f backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=50 -f frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=50 -f admin
```
- `node_modules` lives in a named Docker volume (`admin_node_modules`).
- Host port 3001 maps to container port 3000.
```

## What Requires Rebuilding

| Change | Action Required |
|---|---|
| **Source code** (`*.py`, `*.tsx`, `*.ts`, `*.css`) | ✅ **Nothing.** Hot reload handles it automatically. |
| **package.json** (frontend/admin) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npm install` or rebuild: `docker compose -f docker-compose.yml -f docker-compose.dev.yml build frontend` |
| **requirements.txt** (backend) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml build backend` |
| **Dockerfile.dev** changes | `docker compose -f docker-compose.yml -f docker-compose.dev.yml build <service>` |
| **docker-compose.yml / docker-compose.dev.yml** changes | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` |
This starts all three services with live code reloading.

### URLs

| Service    | URL                          |
|------------|------------------------------|
| Frontend   | http://localhost:3000        |
| Admin      | http://localhost:3001        |
| Backend    | http://localhost:8000        |
| API Docs   | http://localhost:8000/docs   |

## Architecture

### PostgreSQL

- PostgreSQL runs on the **host** machine, not inside Docker.
- The development containers connect to `host.docker.internal:5432`.
- The database is named `gadgeto` and contains the real catalog.
- **No destructive operations** are performed on startup.
- The existing 22,505 products, 147 categories, and all related data remain intact.

### Network

- All three services communicate via the internal Docker network.
- Frontend calls backend via `http://backend:8000` (Docker DNS).
- Admin calls backend via `http://backend:8000` (Docker DNS).
- Backend CORS allows requests from `http://localhost:3000` and `http://localhost:3001`.

### Volume Layout

```
frontend:
  ./frontend/  →  /app/          (bind mount — source code)
  named volume → /app/node_modules (persistent, not on host)

admin:
  ./admin/  →  /app/            (bind mount — source code)
  named volume → /app/node_modules (persistent, not on host)

backend:
### Frontend/Admin — npm

When `package.json` changes, reinstall dependencies:

```bash
# Option 1: Install inside running container
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec frontend npm install

# Option 2: Rebuild the dev image (includes npm ci)
docker compose -f docker-compose.yml -f docker-compose.dev.yml build frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d frontend
```

### Backend — pip

When `requirements.txt` changes, rebuild the image:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d backend
## Production vs Development

| Aspect | Production | Development |
|---|---|---|
| Build command | `docker compose build` | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` |
| Frontend mode | `node server.js` (standalone) | `npm run dev` (hot reload) |
| Admin mode | `node server.js` (standalone) | `npm run dev` (hot reload) |
| Backend mode | `uvicorn` (no reload) | `uvicorn --reload` |
| Source mounts | ❌ Code baked into image | ✅ Bind-mounted |
| node_modules | ❌ Inside image | ✅ Named volume |
| Performance | 🚀 Optimized production | 🔄 Fast iteration |
```
  ./backend/app/  →  /app/app/   (bind mount — Python source)
  ./migrations/  →  /app/migrations/ (bind mount — Alembic)
```
### Stop Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```
## Troubleshooting

### "node_modules not found" or dependency errors

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npm install
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm admin npm install
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend admin
```

### Backend not reloading

Check logs:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=50 backend
```

Verify `--reload` flag is present in the startup message.

### "Port already in use"

Stop other instances:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

### Database connection refused

Verify PostgreSQL is running on the host:
```bash
pg_isready -h localhost -p 5432
```

### Container exits immediately on start

Check logs for startup errors:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs <service>
```

### Hot reload not detecting file changes

On some Docker configurations, filesystem events may not propagate correctly.
The default file-watching should work on Linux. If changes are not detected,
Next.js has a fallback polling mechanism that can be enabled by adding
`--watch-poll` to the dev command or setting `CHOKIDAR_USEPOLLING=1`.
This is not recommended unless you observe the issue. It causes higher CPU usage.