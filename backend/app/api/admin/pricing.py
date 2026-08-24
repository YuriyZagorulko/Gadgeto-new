"""
Pricing configuration API — markup rules, USD rate, preview calculator.
"""
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB
from app.imports.pricing_service import (
    get_usd_rate, set_usd_rate, _load_rules, calculate_price,
    find_markup_multiplier,
)

router = APIRouter()


def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class MarkupRuleCreate(BaseModel):
    supplier_code: str = "*"
    category_id: Optional[int] = None
    price_threshold: int
    multiplier: float
    is_active: bool = True


class MarkupRuleUpdate(BaseModel):
    price_threshold: Optional[int] = None
    multiplier: Optional[float] = None
    is_active: Optional[bool] = None
    category_id: Optional[int] = None


class UsdRateUpdate(BaseModel):
    rate: float


class PricePreviewRequest(BaseModel):
    price: float
    currency: str = "UAH"
    supplier_code: str = "*"
    category_id: Optional[int] = None


@router.get("/pricing/config")
async def get_config(user: dict = Depends(require_admin)):
    """Return the full pricing configuration."""
    rules = _load_rules()
    usd_rate = get_usd_rate()
    return {"usd_rate": usd_rate, "rules": rules}


@router.put("/pricing/usd-rate")
async def update_usd_rate(body: UsdRateUpdate, user: dict = Depends(require_admin)):
    """Update the USD->UAH exchange rate."""
    if body.rate <= 0:
        raise HTTPException(status_code=422, detail="\u041a\u0443\u0440\u0441 \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0431\u0456\u043b\u044c\u0448\u0435 0")
    set_usd_rate(body.rate)
    return {"ok": True, "usd_rate": body.rate}


@router.post("/pricing/rules")
async def create_rule(rule: MarkupRuleCreate, user: dict = Depends(require_admin)):
    if rule.multiplier < 1.0:
        raise HTTPException(status_code=422, detail="\u041d\u0430\u0446\u0456\u043d\u043a\u0430 \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 >= 1.0")
    if rule.price_threshold <= 0:
        raise HTTPException(status_code=422, detail="\u041f\u043e\u0440\u0456\u0433 \u0446\u0456\u043d\u0438 \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 > 0")
    conn, cur = db()
    try:
        cur.execute(
            """INSERT INTO markup_rules (supplier_code, category_id, price_threshold,
               multiplier, sort_order, is_active, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW()) RETURNING id""",
            (rule.supplier_code, rule.category_id, rule.price_threshold,
             rule.multiplier, rule.price_threshold, rule.is_active),
        )
        rid = cur.fetchone()["id"]
        return {"ok": True, "id": rid}
    finally:
        conn.close()


@router.put("/pricing/rules/{rule_id}")
async def update_rule(rule_id: int, body: MarkupRuleUpdate,
                      user: dict = Depends(require_admin)):
    sets, params = [], []
    if body.price_threshold is not None:
        sets.append("price_threshold = %s"); params.append(body.price_threshold)
        sets.append("sort_order = %s"); params.append(body.price_threshold)
    if body.multiplier is not None:
        if body.multiplier < 1.0:
            raise HTTPException(status_code=422, detail="\u041d\u0430\u0446\u0456\u043d\u043a\u0430 \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 >= 1.0")
        sets.append("multiplier = %s"); params.append(body.multiplier)
    if body.is_active is not None:
        sets.append("is_active = %s"); params.append(body.is_active)
    if body.category_id is not None:
        sets.append("category_id = %s"); params.append(body.category_id)
    if not sets:
        return {"ok": True, "id": rule_id}
    sets.append("updated_at = NOW()")
    params.append(rule_id)
    conn, cur = db()
    try:
        cur.execute(f"UPDATE markup_rules SET {', '.join(sets)} WHERE id = %s", params)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="\u041f\u0440\u0430\u0432\u0438\u043b\u043e \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")
        return {"ok": True, "id": rule_id}
    finally:
        conn.close()


@router.delete("/pricing/rules/{rule_id}")
async def delete_rule(rule_id: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("DELETE FROM markup_rules WHERE id = %s", (rule_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="\u041f\u0440\u0430\u0432\u0438\u043b\u043e \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")
        return {"ok": True, "deleted": rule_id}
    finally:
        conn.close()


@router.post("/pricing/preview")
async def price_preview(body: PricePreviewRequest,
                        user: dict = Depends(require_admin)):
    """Calculate the final price with current configuration (preview)."""
    price_uah = None
    price_usd = None
    if body.currency.upper() == "UAH":
        price_uah = body.price
    elif body.currency.upper() == "USD":
        price_usd = body.price
    else:
        raise HTTPException(status_code=422, detail="\u041d\u0435\u0432\u0456\u0440\u043d\u0430 \u0432\u0430\u043b\u044e\u0442\u0430")

    usd_rate = get_usd_rate()
    category_ids = [body.category_id] if body.category_id else None

    final_kopecks = calculate_price(
        price_uah=price_uah,
        price_usd=price_usd,
        usd_rate=usd_rate,
        supplier_code=body.supplier_code,
        category_ids=category_ids,
    )

    if price_uah and price_uah > 0:
        base_uah = price_uah
    elif price_usd and price_usd > 0:
        base_uah = price_usd * usd_rate
    else:
        base_uah = 0.0

    multiplier = find_markup_multiplier(
        base_price_uah=base_uah,
        supplier_code=body.supplier_code,
        category_ids=category_ids,
    )

    return {
        "source_price": body.price,
        "source_currency": body.currency.upper(),
        "usd_rate": usd_rate if body.currency.upper() == "USD" else None,
        "base_price_uah": round(base_uah, 2),
        "multiplier": multiplier,
        "markup_percent": round((multiplier - 1) * 100),
        "final_price_uah": round(base_uah * multiplier, 2),
        "final_price_kopecks": final_kopecks,
    }
