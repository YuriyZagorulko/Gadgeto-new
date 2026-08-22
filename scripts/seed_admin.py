#!/usr/bin/env python3
"""Seed admin user for the admin panel."""
import psycopg2

DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"
conn = psycopg2.connect(DB)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT count(*) FROM users WHERE email = 'admin@gadgeto.com.ua'")
if cur.fetchone()[0] > 0:
    print("Admin already exists")
else:
    from passlib.hash import bcrypt
    pwd = bcrypt.hash("admin123")
    cur.execute("""
        INSERT INTO users (email, password_hash, full_name, role, status, created_at, updated_at)
        VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE', NOW(), NOW())
    """, ("admin@gadgeto.com.ua", pwd, "Gadgeto Admin"))
    print("Admin created: admin@gadgeto.com.ua / admin123")

cur.execute("SELECT id, email, role FROM users WHERE role IN ('ADMIN','STAFF')")
for r in cur.fetchall():
    print(f"  [{r[2]}] {r[1]} (id={r[0]})")
conn.close()
