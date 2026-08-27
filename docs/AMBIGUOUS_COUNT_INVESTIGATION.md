# Investigation Report: Ambiguous Global Count Change (160 → 161)

## Summary

| Metric | Before | After | Delta |
|--------|-------:|------:|:-----:|
| ambiguous_global | 160 | 161 | **+1** |

The +1 increase is **EXPECTED** and **LEGITIMATE**.

---

## Root Cause

**AttributeMapping #9183** (created by the 50 approved operations) qualifies as "ambiguous global" by the exact same SQL logic used by all review API endpoints.

### Details

| Property | Value |
|----------|-------|
| AM ID | **9183** |
| Supplier Attribute | SA#11469 `Технології заряджання` (global, supplier_id=NULL) |
| Internal Attribute | id=191 `Технології заряджання` |
| category_id | NULL (global mapping) |
| is_active | true |

### Why It's Ambiguous

The review SQL classifies a mapping as ambiguous when:
```
m.category_id IS NULL
AND m.attribute_id IS NOT NULL
AND m.is_active = true
AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1
```

Attribute 191 (`Технології заряджання`) appears in **2 categories**:
- Зарядні пристрої (Charging devices)
- Повербанки (Power banks)

Therefore AM#9183 meets all criteria for being counted as ambiguous global.

### Pre-Existing State

Before the 50 operations, there was already **1 global mapping** for attribute 191:
- **AM#2868**: SA#10463 `Стандарти швидкого заряджання` → Attribute 191

AM#2868 was already counted as ambiguous (included in the 160 pre-execution count).

After execution, **2 global mappings** point to attribute 191:
- AM#2868 (pre-existing)
- AM#9183 (newly created)

Both are correctly counted as ambiguous (161 = 160 pre-existing + 1 new).

---

## Verification: Pre-Execution Count Reconstruction

```sql
-- Count excluding AM#9183 (reconstructs pre-execution state)
SELECT count(*) FROM attribute_mappings m
JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
WHERE m.category_id IS NULL
  AND m.attribute_id IS NOT NULL
  AND m.is_active = true
  AND m.id != 9183
  AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1;
-- Result: 160 ✅
```

```sql
-- Count including AM#9183 (current state)
SELECT count(*) FROM attribute_mappings m
JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
WHERE m.category_id IS NULL
  AND m.attribute_id IS NOT NULL
  AND m.is_active = true
  AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1;
-- Result: 161 ✅
```

---

## API Consistency Check

All three review endpoints use **identical SQL logic** for counting ambiguous global mappings:

| Endpoint | SQL for ambiguous_count | Count |
|----------|------------------------|:-----:|
| `GET /mappings/review/summary` (line 285-293) | `SELECT count(*) ... WHERE ... (SELECT count(DISTINCT ...) > 1)` | **161** ✅ |
| `GET /mappings/review/groups` (line 874-882) | Same SQL | **161** ✅ |
| `GET /mappings/review/attributes` (line 356-362) | Same filter logic | **161** ✅ |

No inconsistency detected.

---

## Other Review Counts (Verified Against API SQL)

| Metric | Expected | Actual | Delta Explanation | Status |
|--------|---------:|-------:|:-----------------:|:------:|
| inconsistent | 45 | 45 | 68 - 23 = 45 ✅ | PASS |
| orphans_total | 125 | 125 | 152 - 27 = 125 ✅ | PASS |
| orphans_parent_missing | 0 | 0 | Was 27, now fully resolved | PASS |
| orphans_parent_inactive | 125 | 125 | Unchanged (not in scope) | PASS |
| ambiguous_global | 160 | 161 | +1 due to new AM#9183 | **EXPECTED** |
| unassigned_mappings | 21 | 21 | Unchanged | PASS |
| unassigned_attrs | 7 | 7 | Unchanged | PASS |

---

## Baseline Integrity (Unchanged Items)

| Table | Count | Status |
|-------|:-----:|--------|
| attribute_mappings | 1,151 | ✅ (+1 from AM#9183) |
| attribute_value_mappings | 8,142 | ✅ unchanged |
| product_attributes | 185,566 | ✅ unchanged |
| products | 14,519 | ✅ unchanged |
| channel_category_mappings | 155 | ✅ unchanged |
| channel_attribute_mappings | 93 | ✅ unchanged |
| channel_value_mappings | 502 | ✅ unchanged |

---

## Classification

The +1 ambiguous global change is:

**A. EXPECTED AND LEGITIMATE** ✅

- AM#9183 was intentionally created as a global (category_id=NULL) mapping
- Attribute 191 validly belongs to 2 categories
- The ambiguous count correctly reflects this

**Not a bug** — the mapping review system is working as designed. The ambiguous global review list exists specifically to help administrators identify global mappings that may need category-specific scoping.

---

## Final Verdict

**EXPECTED CHANGE** ✅

The ambiguous_global count increased from 160 to 161 because the newly created AttributeMapping #9183 (SA#11469 `Технології заряджання` → Attribute 191 `Технології заряджання`) correctly qualifies as ambiguous — its target attribute appears in 2 categories (Зарядні пристрої, Повербанки).

This is not a bug. The review system correctly identified the new mapping for potential category-specific scoping if the administrator determines it's needed. The administrator can now decide whether to:
- Keep AM#9183 as global (appropriate if "Технології заряджання" semantics are consistent across both categories)
- Convert it to category-specific mappings if different values apply per category

**No further investigation or action required.**