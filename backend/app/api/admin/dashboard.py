"""Admin dashboard API - real PostgreSQL data."""
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


def _count(cur, sql):
    cur.execute(sql)
    return cur.fetchone()["count"]


@router.get("/dashboard/stats")
async def stats(user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        products = {
            "total": _count(cur, "SELECT count(*) FROM products"),
            "active": _count(cur, "SELECT count(*) FROM products WHERE status='PUBLISHED' AND is_active=true"),
            "without_images": _count(cur, "SELECT count(*) FROM products p WHERE NOT EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id=p.id)"),
            "without_price": _count(cur, "SELECT count(*) FROM products WHERE price IS NULL OR price=0"),
            "out_of_stock": _count(cur, "SELECT count(*) FROM products WHERE stock_status='out_of_stock'"),
        }
        catalog = {
            "categories": _count(cur, "SELECT count(*) FROM categories"),
            "brands": _count(cur, "SELECT count(*) FROM brands"),
            "attributes": _count(cur, "SELECT count(*) FROM attributes"),
        }
        orders = {
            "total": _count(cur, "SELECT count(*) FROM orders"),
            "pending": _count(cur, "SELECT count(*) FROM orders WHERE status='PENDING'"),
            "processing": _count(cur, "SELECT count(*) FROM orders WHERE status='PROCESSING'"),
            "completed": _count(cur, "SELECT count(*) FROM orders WHERE status IN ('SHIPPED','DELIVERED')"),
            "cancelled": _count(cur, "SELECT count(*) FROM orders WHERE status='CANCELLED'"),
        }
        imports = {
            "total": _count(cur, "SELECT count(*) FROM import_jobs"),
            "running": _count(cur, "SELECT count(*) FROM import_jobs WHERE status IN ('QUEUED','RUNNING')"),
            "failed": _count(cur, "SELECT count(*) FROM import_jobs WHERE status='FAILED'"),
            "stale": _count(cur, "SELECT count(*) FROM import_jobs WHERE status='STALE'"),
            "cancelled": _count(cur, "SELECT count(*) FROM import_jobs WHERE status='CANCELLED'"),
        }

        cur.execute("""SELECT number, buyer_name, email, total_amount, status,
                       payment_status, created_at FROM orders
                       ORDER BY created_at DESC LIMIT 8""")
        recent_orders = cur.fetchall()

        cur.execute("""SELECT j.id, j.status, j.import_type, j.started_at, j.finished_at,
                       s.name AS supplier_name
                       FROM import_jobs j LEFT JOIN suppliers s ON s.id=j.supplier_id
                       ORDER BY j.id DESC LIMIT 5""")
        recent_imports = cur.fetchall()

        cur.execute("SELECT COALESCE(sum(total_amount),0) AS revenue FROM orders "
                    "WHERE status IN ('PAID','SHIPPED','DELIVERED')")
        revenue = cur.fetchone()["revenue"]

        return {"products": products, "catalog": catalog, "orders": orders,
                "imports": imports, "revenue": revenue,
                "recent_orders": recent_orders, "recent_imports": recent_imports}
    finally:
        conn.close()

