# Environment Variables

Never commit real values. Copy `.env.example` and fill in the values. See the legend
below.

---

## Backend

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL DSN | `postgresql+asyncpg://gadgeto:pass@db:5432/gadgeto` |
| `REDIS_URL` | Redis DSN (cache + broker) | `redis://redis:6379/0` |
| `SECRET_KEY` | session/CSRF signing | (random 32+ bytes) |
| `ENVIRONMENT` | dev/staging/production | `development` |
| `CORS_ORIGINS` | comma-separated frontend origins | `http://localhost:3000` |

## LiqPay

| Variable | Description |
|---|---|
| `LIQPAY_PUBLIC_KEY` | public key (prod) |
| `LIQPAY_PRIVATE_KEY` | private key (prod) |
| `LIQPAY_TEST_MODE` | `true` in staging/tests |
| `LIQPAY_TEST_PUBLIC_KEY` / `LIQPAY_TEST_PRIVATE_KEY` | sandbox credentials |

## Nova Poshta

| Variable | Description |
|---|---|
| `NOVAPOSHTA_API_KEY` | NP API key (never hard-code) |
| `NOVAPOSHTA_API_URL` | service URL (default `https://api.novaposhta.ua/v2.0/json/`) |

## Email

| Variable | Description |
|---|---|
| `SMTP_HOST` / `SMTP_PORT` | SMTP server + port |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP auth |
| `SMTP_FROM` | sender address (`noreply@gadgeto.com.ua`) |
| `E_MAIL_FORCE_SYNC` | `1` in dev to write emails to a log file instead of sending |

## Frontend

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | public API base URL (http://localhost:8000 in dev) |
| `NEXT_PUBLIC_SITE_URL` | canonical site URL (for SEO/canonical) |

## Import / supplier credentials (per-supplier, kept out of code)

| Variable | Description |
|---|---|
| `SUPPLIER_ITLINK_USERNAME` / `SUPPLIER_ITLINK_PASSWORD` | IT-Link |
| `SUPPLIER_ITLINK_PRICE_ID` / `SUPPLIER_ITLINK_CUSTOMER_ID` | IT-Link price-list API |
| `SUPPLIER_DCLINK_LOGIN` / `SUPPLIER_DCLINK_PASSWORD` | DC-Link |

## File/media

| Variable | Description |
|---|---|
| `MEDIA_DIR` | local media storage dir |
| `MEDIA_BASE_URL` | public media URL path |

> All suppliers' credentials are stored only in environment/secret manager —
> never committed (verify with `gitleaks`/pre-commit).