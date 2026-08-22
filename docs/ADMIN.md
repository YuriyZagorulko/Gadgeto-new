# Gadgeto Admin Application

## Architecture

```
admin/ (Next.js standalone)
    ↓
FastAPI (/api/v1/admin/*)
    ↓
PostgreSQL
```

## Tech Stack

- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- Client-side API calls via fetch/axios

## Authentication

- POST /api/v1/admin/auth/login → access_token
- Token stored in localStorage as `admin_token`
- Passed via Authorization: Bearer header
- Session stored in PostgreSQL `sessions` table with 24h expiry
- Backend validates token hash on each request

## Routes

| Path | Section |
|---|---|
| /login | Auth |
| /dashboard | Overview with real stats |
| /products | Product list + CRUD |
| /categories | Category tree + CRUD |
| /attributes | Attribute + value management |
| /brands | Brand management |
| /suppliers | Supplier info |
| /filters | Category filter management |
| /mappings | Mapping management |
| /imports | Import history |
| /orders | Order list |
| /users | User management |
| /settings | System settings |

## API Endpoints

All under `/api/v1/admin/`:

### Auth
- POST /auth/login
- GET /auth/me

### Products
- GET /products (paginated, searchable, filterable)
- GET /products/{id} (detail with categories, attributes, images)
- PUT /products/{id} (update)
- DELETE /products/{id} (archive)
- POST /products/{id}/attributes (assign attribute)
- DELETE /products/{id}/attributes/{aid} (remove attribute)
- POST /products/{id}/images (add image)
- DELETE /product-images/{id} (remove image)
- POST /products/{id}/tags (add supplier tag)

### Dashboard
- GET /dashboard (real PostgreSQL counts)

## Dashboard Stats

All from actual database:
- Total products: 22,505
- Published: ~15,505
- In stock: ~22,000+
- Categories: 147
- Attributes: 162
- Attribute values: 4,708
- Brands: 44
- Product images: 24,494
- Category filters: 453
