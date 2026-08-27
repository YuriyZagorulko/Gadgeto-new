# E2E Testing Skill

## Overview

Browser-based end-to-end testing for this project uses **Playwright**.

Playwright is available as an optional dependency in both `admin/` and `frontend/`
package manifests. The backend also uses Playwright (headless Chromium) for the
IT-Link supplier OAuth2 download flow.

## Scope

E2E tests validate complete user flows across the full stack:

- Storefront (Next.js at `http://localhost:3000`)
- Admin panel (Next.js at `http://localhost:3001`)
- Backend API (FastAPI at `http://localhost:8000`)
- Database (PostgreSQL)

## Prerequisites

Before running E2E tests, ensure:

1. All services are running:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
   ```
2. Database migrations are applied:
   ```bash
   docker compose exec backend alembic upgrade head
   ```
3. Test data is seeded (if applicable).

## Test Organization

E2E tests should be placed in:

- `frontend/tests/` — storefront user flows
- `admin/tests/` — admin panel flows
- `backend/tests/` — backend integration tests (pytest-based, not browser)

## What to Test

### Authentication flows

- Registration, login, logout
- Email verification
- Password reset
- Admin login with role-based access

### Storefront flows

- Product browsing and search
- Category navigation
- Product detail pages
- Cart operations (add, remove, update quantity)
- Guest checkout
- Account-based checkout

### Admin flows

- Product management (CRUD)
- Category management
- Attribute management
- Mapping management (category, attribute, value)
- Import job management
- Export/Rozetka management

### API verification

- Response status codes
- Response payload structure
- Authentication enforcement
- Authorization checks

## Best Practices

1. **Use test-specific data** — never modify production or development data.
2. **Clean up after tests** — remove created entities, restore state.
3. **Keep tests independent** — each test should not depend on another test's state.
4. **Use fixtures/seeds** — set up known state before each test run.
5. **Capture failures** — take screenshots on failure for debugging.
6. **Tag tests** — mark smoke tests, regression tests, etc.

## Running Tests

### Backend unit/integration tests

```bash
cd backend
pytest
```

### Frontend type checking

```bash
cd frontend   # or admin
npx tsc --noEmit
```

### Playwright E2E tests (when configured)

```bash
cd frontend   # or admin
npx playwright test
```

## Notes

- The project currently does not have a comprehensive Playwright E2E test suite;
  tests exist primarily at the backend pytest level with HTTP client mocking.
- Playwright is also used by the backend's IT-Link downloader for OAuth2
  authentication (not for testing).
- When adding new E2E tests, follow the project's existing patterns and conventions.