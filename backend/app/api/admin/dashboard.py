"""Admin dashboard API - real PostgreSQL data."""
from fastapi import APIRouter
import psycopg2, psycopg2.extras

router = APIRouter()
DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

@router.get("/dashboard")
async def dashboard():
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    results = {}
    
    cur.execute("SELECT count(*) FROM products"); results["total_products"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM products WHERE status='PUBLISHED'"); results["published"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM products WHERE is_active=false"); results["inactive"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM products WHERE stock_status='in_stock'"); results["in_stock"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM products WHERE stock_status='out_of_stock'"); results["out_of_stock"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM categories"); results["categories"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM attributes"); results["attributes"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM attribute_values"); results["attribute_values"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM brands"); results["brands"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM product_images"); results["images"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM product_categories"); results["product_categories"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM product_attributes"); results["product_attributes"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM category_filters"); results["category_filters"] = cur.fetchone()["count"]
    cur.execute("SELECT count(*) FROM suppliers"); results["suppliers"] = cur.fetchone()["count"]
    
    # Products without images
    cur.execute("SELECT count(*) FROM products WHERE id NOT IN (SELECT DISTINCT product_id FROM product_images)"); results["no_images"] = cur.fetchone()["count"]
    
    # Products without categories
    cur.execute("SELECT count(*) FROM products WHERE id NOT IN (SELECT DISTINCT product_id FROM product_categories)"); results["no_categories"] = cur.fetchone()["count"]
    
    conn.close()
    return results
