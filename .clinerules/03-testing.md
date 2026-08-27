# Testing & Verification

## 1. After Code Changes

Run these checks in order of practicality:

1. Run appropriate safe tests/checks (unit/integration).
2. Run type checking where applicable.
3. Run linting where applicable.
4. Verify affected endpoints/pages when practical.
5. Check Docker/container health when relevant.
6. Inspect actual results.
7. Fix discovered problems when possible.

## 2. Test Types — Distinguish Clearly

Never conflate different test levels. Always report results accurately:

- **Static inspection** — code review, type checking, linting (no runtime).
- **Unit tests** — isolated function/class tests (pytest).
- **Integration tests** — cross-component tests (API + DB).
- **E2E tests** — full browser-based user flow tests (Playwright).
- **Real external-service tests** — actual API calls to Brevo, LiqPay, Nova Poshta, etc.

## 3. Honest Reporting

- Never claim a test was performed if it was not.
- HTTP `200` alone is not proof that a feature works correctly.
- Never claim completion based only on static inspection or HTTP `200`.

## 4. Backend Testing

The backend test suite uses **pytest** with `pytest-asyncio`.

```bash
cd backend
pytest
```

Test configuration is in `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

Integration tests requiring the database use the project's database infrastructure
(see `docker-compose.yml`).

## 5. Frontend / Admin Testing

TypeScript type checking:

```bash
cd frontend   # or admin
npx tsc --noEmit
```

The project uses Next.js App Router; component tests follow standard React testing
patterns. Playwright is available as an optional dependency in both `admin/` and
`frontend/` for browser-based testing.

## 6. Docker Health Verification

After infrastructure changes, verify:

```bash
docker compose ps
docker compose logs <service>
```

## 7. Migration Verification

After executing a migration, verify:

- Alembic revision matches expected;
- affected schema matches expected;
- application starts and responds;
- relevant tests pass.

## 8. External Service Testing

- For Brevo, LiqPay, Nova Poshta: prefer structural/unit tests over real calls.
- Never use fake credentials in real calls.
- Avoid bulk real-world operations during testing.
- When credentials are unavailable, test the integration structurally and explicitly
  state that real delivery was not verified.
- A single controlled test is the maximum allowed without approval.