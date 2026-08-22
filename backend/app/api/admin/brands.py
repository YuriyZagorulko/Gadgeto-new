# Admin brands API
from fastapi import APIRouter
router = APIRouter()

from app.core.db_connect import get_cursor as _db
# DB connection via app.core.db_connect

def db():
    
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur
