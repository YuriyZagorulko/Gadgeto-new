# Admin imports API
from fastapi import APIRouter
router = APIRouter()

DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

def db():
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur
