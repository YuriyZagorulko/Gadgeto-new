# Mapping Execution Plan — 50 Resolvable Items

Generated: 2026-08-27 19:00 EEST
Backup: `/home/yuri/Desktop/my/projects/Gadgeto-new/backup_mapping_analysis.dump`

> **NO DATABASE MUTATIONS WERE PERFORMED.**
> This document describes operations that are safe to execute in a transaction.
> They have been verified against the live database but not yet applied.

---

## 1. Executive Summary

This plan covers **50 mapping issues** identified as resolvable without semantic interpretation:

| # | Category | Count | Operation | Risk |
|---|----------|------:|-----------|------|
| 1 | SAFE_LINK (orphans) | 27 | Create 1 `attribute_mapping` record | None |
| 2 | SAFE_CREATE (inconsistent) | 23 | Create 23 `attribute_values` + reassign 23 `attribute_value_mappings` | None |

**If applied:** 401 outstanding issues → **351**.
**If rolled back:** zero data loss — all operations are reversible.

---

## 2. SAFE_LINK — 27 Orphan Value Mappings

### 2.1 Verification Summary

All checks passed:

| # | Check | Result |
|---|-------|--------|
| 1 | SA#11469 exists | ✅ name='Технології заряджання', supplier_id=NULL, is_removed=false |
| 2 | Internal attribute id=191 exists | ✅ name='Технології заряджання' |
| 3 | Exactly 27 affected ValueMappings | ✅ Count verified |
| 4 | All belong to SA#11469 | ✅ All 27 have supplier_attribute_id=11469 |
| 5 | All target AVs belong to attr 191 | ✅ All 27 have attribute_id=191 |
| 6 | All 27 AVs exist | ✅ None are NULL |
| 7 | No conflicting parent AM | ✅ No `attribute_mapping` for SA#11469 exists |
| 8 | No unique constraint violation | ✅ `uq_attribute_mappings_supplier_attribute` is UNIQUE on supplier_attribute_id; no existing mapping |
| 9 | Resolvable after creation | ✅ MappingResolver loads active mapping; all 27 value mappings already correct |
| 10 | No ProductAttributes need changes | ✅ |

### 2.2 Affected Records (27 orphan value mappings)

```
VM#12522: 'Fast Charge'                          → AV#1918='Fast Charge'
VM#12523: 'PD'                                   → AV#1922='PD'
VM#12524: 'PD 2.0'                               → AV#1923='PD 2.0'
VM#12525: 'PD 3.0'                               → AV#1928='PD 3.0'
VM#12526: 'PD 3.0, PPS'                          → AV#1933='PD 3.0, PPS'
VM#12527: 'PD 3.0, QC 3.0'                       → AV#1921='PD 3.0, QC 3.0'
VM#12528: 'PD 3.0, QC 3.0, AFC, FCP, SCP'        → AV#5780= ...
VM#12529: 'PD 3.0, QC 3.0, AFC, FCP, SFC'        → AV#5781= ...
VM#12530: 'PD 3.0, QC 3.0, FCP, AFC'             → AV#5782= ...
VM#12531: 'PD 3.0, QC 3.0, PPS'                  → AV#5783= ...
VM#12532: 'PD 3.0, QC 4.0'                       → AV#1935='PD 3.0, QC 4.0'
VM#12533: 'PD 3.0, QC 4.0, AFC, FCP'             → AV#5784= ...
VM#12534: 'PD 3.0, QC 4.0, AFC, FCP, PPS'        → AV#5785= ...
VM#12535: 'PD 3.0, QC 4.0, AFC, SFC, SCP, FCP, VOOC' → AV#5786= ...
VM#12536: 'PD 3.1'                               → AV#1936='PD 3.1'
VM#12537: 'PD, PowerIQ'                          → AV#1932='PD, PowerIQ'
VM#12538: 'PD, PowerIQ, PPS'                     → AV#1941='PD, PowerIQ, PPS'
VM#12539: 'PD, QC'                               → AV#5787='PD, QC'
VM#12540: 'PD, QC 3.0'                           → AV#1920='PD, QC 3.0'
VM#12541: 'PD, QC 4.0'                           → AV#1942='PD, QC 4.0'
VM#12542: 'PD, QC, PPS'                          → AV#5788='PD, QC, PPS'
VM#12543: 'PowerIQ'                              → AV#1931='PowerIQ'
VM#12544: 'PowerIQ 3.0'                          → AV#1937='PowerIQ 3.0'
VM#12545: 'QC 3.0'                               → AV#1917='QC 3.0'
VM#12546: 'QC 3.0, FCP, AFC'                     → AV#5789= ...
VM#12547: 'QC 4.0'                               → AV#1926='QC 4.0'
VM#12548: 'Qi'                                   → AV#1919='Qi'
```

### 2.3 Exact Operation

```sql
-- Create the single missing parent attribute mapping
INSERT INTO attribute_mappings
    (supplier_attribute_id, attribute_id, is_active,
     created_by_user_id, created_at, updated_at)
VALUES
    (11469, 191, TRUE, NULL, NOW(), NOW());
```

**No value mappings need updating.** All 27 existing `attribute_value_mappings`
already point to valid `attribute_values` under attribute_id=191.

---

## 3. SAFE_CREATE — 23 Inconsistent Value Mappings

### 3.1 Context

- **Supplier attribute:** `Частота ядра` (global, SA#10548, supplier_id=NULL)
- **Parent AM:** AM#9180 → attribute_id=325 (`Частота ядра, МГц`), cat_id=14 (Відеокарти), active=true
- **Current (wrong) target:** attribute id=288 (`Частота ядра`)
- **Correct target:** attribute id=325 (`Частота ядра, МГц`)
- All 23 current AVs are under the wrong parent attribute
### 3.2 Verification Summary

All checks passed for all 23 proposals:

| # | Check | Result |
|---|-------|--------|
| 1 | Parent AM#9180 exists, active | ✅ SA#10548→attr 325, active=true, cat_id=14 |
| 2 | Target attr 325 exists | ✅ name='Частота ядра, МГц' |
| 3 | Proposed value NOT already under attr 325 | ✅ All 23 values absent |
| 4 | No duplicate under attr 325 | ✅ UNIQUE(attribute_id, value) satisfied |
| 5 | No normalized duplicate | ✅ Trim/case check passed |
| 6 | Current mapping IS cross-attribute | ✅ All 23 inconsistent (attr 288 vs 325) |
| 7 | No FK/unique violation | ✅ Only (attr_id, value) is unique; slug has no constraint |
| 8 | No semantic reinterpretation | ✅ Simple numeric frequencies/ranges |
| 9 | No ProductAttributes need changes | ✅ |

### 3.3 Classification: All 23 → SAFE_CREATE

### 3.4 Affected Records

| VM ID | Supplier Value | Old AV | Usage | Slug |
|:-----:|----------------|:------:|:-----:|:----:|
| 15802 | 1477 | 4313 | 1 | 1477 |
| 15804 | 2280 - 2497 | 4319 | 1 | 2280-2497 |
| 15805 | 2280 - 2512 | 4340 | 1 | 2280-2512 |
| 15806 | 2280 - 2535 | 4318 | 0 | 2280-2535 |
| 15807 | 2407 - 2550 | 4352 | 0 | 2407-2550 |
| 15808 | 2407 - 2573 | 4323 | 0 | 2407-2573 |
| 15809 | 2407 - 2602 | 4339 | 1 | 2407-2602 |
| 15810 | 2407 - 2632 | 4322 | 0 | 2407-2632 |
| 15811 | 2407 - 2655 | 4348 | 0 | 2407-2655 |
| 15813 | 2482 - 2497 | 4347 | 0 | 2482-2497 |
| 15814 | 2497 | 4344 | 1 | 2497 |
| 15815 | 2497 - 2512 | 4354 | 0 | 2497-2512 |
| 15816 | 2497 - 2550 | 4334 | 1 | 2497-2550 |
| 15818 | 2512 - 2587 | 4351 | 0 | 2512-2587 |
| 15819 | 2512 - 2625 | 4350 | 0 | 2512-2625 |
| 15820 | 2550 | 4329 | 0 | 2550 |
| 15822 | 2572 - 2587 | 4357 | 1 | 2572-2587 |
| 15823 | 2572 - 2617 | 4330 | 0 | 2572-2617 |
| 15824 | 2572 - 2632 | 4335 | 1 | 2572-2632 |
| 15826 | 2617 | 6431 | 0 | 2617 |
| 15827 | 2617 - 2670 | 4345 | 0 | 2617-2670 |
| 15828 | 2617-2805 | 4341 | 0 | 2617-2805 |
| 15829 | 2780 - 3320 | 4332 | 1 | 2780-3320 |

### 3.5 STEP 1: Insert 23 new AVs

```sql
INSERT INTO attribute_values (attribute_id, value, slug, sort, is_active, created_at, updated_at)
VALUES
(325, '1477',        '1477',        0, TRUE, NOW(), NOW()),
(325, '2280 - 2497', '2280-2497',   0, TRUE, NOW(), NOW()),
(325, '2280 - 2512', '2280-2512',   0, TRUE, NOW(), NOW()),
(325, '2280 - 2535', '2280-2535',   0, TRUE, NOW(), NOW()),
(325, '2407 - 2550', '2407-2550',   0, TRUE, NOW(), NOW()),
(325, '2407 - 2573', '2407-2573',   0, TRUE, NOW(), NOW()),
(325, '2407 - 2602', '2407-2602',   0, TRUE, NOW(), NOW()),
(325, '2407 - 2632', '2407-2632',   0, TRUE, NOW(), NOW()),
(325, '2407 - 2655', '2407-2655',   0, TRUE, NOW(), NOW()),
(325, '2482 - 2497', '2482-2497',   0, TRUE, NOW(), NOW()),
(325, '2497',        '2497',        0, TRUE, NOW(), NOW()),
(325, '2497 - 2512', '2497-2512',   0, TRUE, NOW(), NOW()),
(325, '2497 - 2550', '2497-2550',   0, TRUE, NOW(), NOW()),
(325, '2512 - 2587', '2512-2587',   0, TRUE, NOW(), NOW()),
(325, '2512 - 2625', '2512-2625',   0, TRUE, NOW(), NOW()),
(325, '2550',        '2550',        0, TRUE, NOW(), NOW()),
(325, '2572 - 2587', '2572-2587',   0, TRUE, NOW(), NOW()),
(325, '2572 - 2617', '2572-2617',   0, TRUE, NOW(), NOW()),
(325, '2572 - 2632', '2572-2632',   0, TRUE, NOW(), NOW()),
(325, '2617',        '2617',        0, TRUE, NOW(), NOW()),
(325, '2617 - 2670', '2617-2670',   0, TRUE, NOW(), NOW()),
(325, '2617-2805',   '2617-2805',   0, TRUE, NOW(), NOW()),
(325, '2780 - 3320', '2780-3320',   0, TRUE, NOW(), NOW())
RETURNING id, value;
```

### 3.6 STEP 2: Reassign 23 VMs

```sql
-- Use RETURNING IDs from STEP 1.
UPDATE attribute_value_mappings SET attribute_value_id = <id>, updated_at = NOW() WHERE id = 15802;
UPDATE attribute_value_mappings SET attribute_value_id = <id>, updated_at = NOW() WHERE id = 15804;
-- ... (one per VM, mapping 15802-15829)
UPDATE attribute_value_mappings SET attribute_value_id = <id>, updated_at = NOW() WHERE id = 15829;
```

---
## 4. Pre-Flight Checks

```sql
-- 4.1 Verify parent AM#9180 (expected: attr=325, active=true)
SELECT id, attribute_id, is_active FROM attribute_mappings WHERE id = 9180;

-- 4.2 Count orphans before (expected: 152)
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
WHERE am.id IS NULL OR am.is_active = false;

-- 4.3 Count inconsistent before (expected: 68)
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
JOIN attribute_values av ON av.id = m.attribute_value_id
WHERE am.is_active = true AND av.attribute_id != am.attribute_id;

-- 4.4 No existing AM for SA#11469 (expected: empty)
SELECT id FROM attribute_mappings WHERE supplier_attribute_id = 11469;

-- 4.5 Proposed values absent from attr 325 (expected: empty)
SELECT value FROM attribute_values WHERE attribute_id = 325
AND value IN ('1477','2280 - 2497','2280 - 2512','2280 - 2535',
  '2407 - 2550','2407 - 2573','2407 - 2602','2407 - 2632','2407 - 2655',
  '2482 - 2497','2497','2497 - 2512','2497 - 2550',
  '2512 - 2587','2512 - 2625','2550',
  '2572 - 2587','2572 - 2617','2572 - 2632','2617',
  '2617 - 2670','2617-2805','2780 - 3320');

-- 4.6 All 23 are still inconsistent (expected: empty)
SELECT m.id FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
JOIN attribute_values av ON av.id = m.attribute_value_id
WHERE m.id IN (15802,15804,15805,15806,15807,15808,15809,15810,15811,
  15813,15814,15815,15816,15818,15819,15820,
  15822,15823,15824,15826,15827,15828,15829)
  AND av.attribute_id = am.attribute_id;

-- 4.7 Channel mappings for attrs 191,325 (expected: 0)
SELECT count(*) FROM channel_attribute_mappings
WHERE internal_attribute_id IN (191, 325);

-- 4.8 ProductAttributes count (expected: 185566)
SELECT count(*) FROM product_attributes;
```

## 5. Post-Flight Integrity Checks

```sql
-- 5.1 Orphans: 125 (was 152)
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
WHERE am.id IS NULL OR am.is_active = false;

-- 5.2 Inconsistent: 45 (was 68)
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
JOIN attribute_values av ON av.id = m.attribute_value_id
WHERE am.is_active = true AND av.attribute_id != am.attribute_id;

-- 5.3 AttributeMappings: 1151 (was 1150)
SELECT count(*) FROM attribute_mappings;

-- 5.4 AttributeValues: 7883 (was 7860)
SELECT count(*) FROM attribute_values;

-- 5.5 ValueMappings: 8142 (unchanged)
SELECT count(*) FROM attribute_value_mappings;

-- 5.6 ProductAttributes: 185566 (unchanged)
SELECT count(*) FROM product_attributes;

-- 5.7 NULL attribute_value_id: 0
SELECT count(*) FROM attribute_value_mappings WHERE attribute_value_id IS NULL;

-- 5.8 Invalid AV refs: 0
SELECT count(*) FROM attribute_value_mappings m
WHERE m.attribute_value_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM attribute_values av WHERE av.id = m.attribute_value_id);

-- 5.9 Duplicate canonical values: 0
SELECT attribute_id, value, count(*) FROM attribute_values
GROUP BY attribute_id, value HAVING count(*) > 1;

-- 5.10 Channel mappings unchanged (155, 93, 502)
SELECT 'channel_cat', count(*) FROM channel_category_mappings
UNION ALL SELECT 'channel_attr', count(*) FROM channel_attribute_mappings
UNION ALL SELECT 'channel_val', count(*) FROM channel_value_mappings;

-- 5.11 New parent mapping exists
SELECT id, attribute_id, is_active FROM attribute_mappings WHERE supplier_attribute_id = 11469;

-- 5.12 Sample VM resolves correctly
SELECT m.id, sav.supplier_value, am.attribute_id AS correct_attr,
       m.attribute_value_id, av.value, av.attribute_id AS av_attr
FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
JOIN attribute_values av ON av.id = m.attribute_value_id
WHERE m.id = 15814;
-- Expected: correct_attr=325, av_attr=325, av.value='2497'
```
## 6. Expected Before/After Counts

| Metric | Before | After | Delta |
|--------|-------:|------:|:-----:|
| attribute_mappings | 1,150 | **1,151** | +1 |
| attribute_values | 7,860 | **7,883** | +23 |
| attribute_value_mappings | 8,142 | 8,142 | 0 |
| orphans | 152 | **125** | -27 |
| inconsistent | 68 | **45** | -23 |
| products | 14,519 | 14,519 | 0 |
| product_attributes | 185,566 | 185,566 | 0 |
| channel_cat_mappings | 155 | 155 | 0 |
| channel_attr_mappings | 93 | 93 | 0 |
| channel_value_mappings | 502 | 502 | 0 |

## 7. Items Excluded (351 Untouched)

| Category | Count | Reason |
|----------|------:|--------|
| Inconsistent — MANUAL_REVIEW | 45 | Compound Boost/OC/Game Clock values requiring human interpretation |
| Orphans — parent inactive | 125 | Довжина + Бюджет PoE need admin decision |
| Ambiguous global mappings | 160 | Legitimate cross-category; no conflicts |
| Unassigned mappings | 21 | Need category assignments |
| **Total excluded** | **351** | |

## 8. Safety Assessment

| Concern | Status |
|---------|--------|
| ProductAttributes need modification? | **NO** |
| Canonical values need deletion? | **NO** — only INSERT |
| Existing values need merging? | **NO** — all 23 are genuinely new |
| Channel/Rozetka mappings need changes? | **NO** — attrs 191,325 have 0 channel mappings |
| Semantic remapping required? | **NO** — simple parent-link + exact-value ops |
| Single transaction? | **YES** — all DML, no DDL |
| Rollback possible? | **YES** — ROLLBACK returns to exact pre-op state |
| Backup available? | **YES** — `backup_mapping_analysis.dump` |

## 9. Transaction Structure

```
BEGIN;
  -- Pre-flight checks (4.1-4.8) → ROLLBACK if any fail
  INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active, ...)
    VALUES (11469, 191, TRUE, ...);                        -- SAFE_LINK
  INSERT INTO attribute_values (attribute_id, value, slug, ...) VALUES ...;  -- SAFE_CREATE step 1
  UPDATE attribute_value_mappings SET attribute_value_id = <new_id> ... ;    -- SAFE_CREATE step 2
  -- Post-flight checks (5.1-5.12) → ROLLBACK if any fail
COMMIT;
```

Alternative: use existing `PUT /api/admin/mappings/review/values/bulk-reassign`.

## 10. Final Verdict

- **27 SAFE_LINK**: Create 1 AM (SA#11469 → attr 191) → all orphans resolved
- **23 SAFE_CREATE**: Create 23 AVs under attr 325 → reassign 23 VMs → all resolved
- **After:** 401 → 351 outstanding items (manual review only)
- **Risk:** Minimal. Product/channel data unaffected. Full rollback possible.

> **NO DATABASE MUTATIONS WERE PERFORMED.**
