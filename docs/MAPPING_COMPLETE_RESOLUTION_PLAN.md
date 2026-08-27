# Complete Mapping Resolution Plan

Generated: 2026-08-27 19:45 EEST

> **NO DATABASE MUTATIONS WERE PERFORMED.**
> This is an analysis and execution-plan generation document.
> A separate explicit execution step must be performed after review and approval.

---

## Executive Summary

### Classification Counts

| Classification | Count |
|---|---:|
| SAFE_LINK | 125 |
| KEEP_GLOBAL | 161 |
| MANUAL_REVIEW | 66 |
| SAFE_REASSIGN | 0 |
| SAFE_CREATE | 0 |
| CATEGORY_SPECIFIC | 0 |
| SAFE_DELETE | 0 |
| **TOTAL** | **352** |

### Breakdown by Category

| Category | Total | Safe | Manual |
|----------|------:|-----:|-------:|
| Inconsistent values | 45 | 0 | 45 |
| Orphan mappings | 125 | 125 | 0 |
| Ambiguous global | 161 | 161 (KEEP) | 0 |
| Unassigned | 21 | 0 | 21 |
| **Total** | **352** | **125** | **66** |

---

## Section A — Inconsistent Value Mappings (45 items)

### Group Summary

All 45 remaining inconsistent mappings share a single parent:

| Parent Attribute | Wrong Target | Count | Reason |
|-----------------|-------------|------:|--------|
| Частота ядра, МГц (id=325) | Частота ядра (id=288) | 45 | Compound values requiring human interpretation |

**Why no SAFE_CREATE?** The 23 simple numeric/range values were already created as AV#8763–8785 and reassigned in the previous execution. What remains are 45 compound descriptions that cannot be resolved automatically.

**Value pattern types:**

| Pattern | Count | Example |
|---------|------:|---------|
| Boost Clock compound | 15 | 'Boost Clock: 2602 MHz; Extreme Performance: 2617 MHz' |
| Base/Boost Clock | 6 | 'Base Clock: 2295 MHz/Boost Clock: 2617 MHz' |
| OC Mode descriptions | 16 | 'OC Mode - 1537 MHz, Default Mode – Boost Clock : 1507 MHz' |
| Game Clock variants | 4 | 'Game: 2250 MHz/Boost: 2655 MHz' |
| Silent Mode | 3 | 'Silent Mode – Boost Clock : 2790 MHz/Game Clock: 2220 MHz' |
| No-data placeholders | 1 | 'Немає даних' |

**All 45 items classified MANUAL_REVIEW.** Administrator must decide whether to create canonical values with full compound text, simplify, or leave unmapped.
---

## Section B — Orphan Value Mappings (125 items)

### Group Summary

| Status | Supplier Attribute | Parent AM | VMs | Product Usage | Matching Attr |
|:-----:|-------------------|:---------:|:---:|:-------------:|:-------------:|
| PARENT_INACTIVE | Довжина (SA#11126) | AM#3350 | 61 | 1,375 | 179 (Довжина) |
| PARENT_INACTIVE | Бюджет PoE (SA#11391) | AM#3381 | 64 | 0 | 281 (Бюджет PoE) |

### Classification: 125 items → **SAFE_LINK**

Both groups can be resolved by updating the existing inactive parent AMs to link to matching internal attributes.

### Resolution for Довжина (61 VMs, 1,375 product usage)

| Item | Value |
|------|-------|
| Supplier Attribute ID | SA#11126 (global) |
| Supplier Attribute Name | Довжина |
| Existing Parent AM | AM#3350 (inactive, attribute_id=NULL) |
| Matching Internal Attribute | id=179 (Довжина) |
| Category Assignment | 13 categories |
| Proposed Operation | UPDATE AM#3350 SET attribute_id=179, is_active=true |

**Validation:** Attribute 179 Довжина assigned to 13 categories matching length measurement semantics.

### Resolution for Бюджет PoE (64 VMs, 0 product usage)

| Item | Value |
|------|-------|
| Supplier Attribute ID | SA#11391 (global) |
| Supplier Attribute Name | Бюджет PoE |
| Existing Parent AM | AM#3381 (inactive, attribute_id=NULL) |
| Matching Internal Attribute | id=281 (Бюджет PoE) |
| Category Assignment | 1 category (Комутатори) |
| Proposed Operation | UPDATE AM#3381 SET attribute_id=281, is_active=true |

---

## Section C — Unassigned Attribute Mappings (21 items, 7 groups)

### Classification: 21 items → **MANUAL_REVIEW**

| Attribute | Mappings | Product Usage | Supplier Names | Notes |
|:---------:|:--------:|:-------------:|----------------|:------|
| Бренд (id=353) | 6 | 0 | brand, Brand, BRAND, Бренд, Бренди, Виробник | May be artifact; brand uses products.brand_id |
| Кількість (id=167) | 8 | 0 | Кількість, Кількість SIP акаунтів, Кількість розеток, etc. | Each variant belongs to different categories |
| ECC (id=328) | 2 | 0 | Перевірка і/та корекція помилок (ECC) | Memory/storage categories |
| Підтримка RAID (id=351) | 1 | 0 | Підтримка RAID | Storage/controller categories |
| Форм-фактор (id=172) | 2 | 0 | Форм-фактор, Формфактор | Category-specific (motherboard vs case) |
| Час відгуку матриці (id=357) | 1 | 0 | Час відгуку матриці | Display/monitor categories |
| Яскравість дисплея (id=358) | 1 | 0 | Яскравість дисплея | Display/monitor categories |

**All 21 have 0 product usage** — no category assignment means products cannot use them. Administrator must decide categories.

---

## Section D — Ambiguous Global Mappings (161 items)

### Classification: 161 items → **KEEP_GLOBAL**

All 161 global mappings target internal attributes that legitimately span multiple categories. **No evidence of conflicting semantics** was found.

**Key examples:**

| Attribute | Categories | Reason |
|:----------|:----------:|--------|
| Вага (id=354) | 43 | Weight is universal |
| Колір (id=168) | 73 | Color is universal |
| Матеріал корпусу (id=169) | 29 | Material applies to many product types |
| Підтримка Bluetooth (id=347) | 16 | Bluetooth is cross-category |
| Об'єм пам'яті (id=193) | 18 | Memory capacity is universal |
| Інтерфейси (id=173) | 26 | Interface connectivity is cross-category |

No supplier attribute name maps to different internal attributes depending on category — the key indicator of genuine ambiguity.

---

## Section E — Proposed Safe Operations

### SAFE_LINK — 2 Parent AM Updates (resolves 125 orphans)

**Operation 1: Link AM#3350 → Attribute 179 (Довжина)**
```sql
UPDATE attribute_mappings
SET attribute_id = 179, is_active = true, updated_at = NOW()
WHERE id = 3350;
```
- Resolves 61 orphan VMs affecting 1,375 products
- Zero channel impact

**Operation 2: Link AM#3381 → Attribute 281 (Бюджет PoE)**
```sql
UPDATE attribute_mappings
SET attribute_id = 281, is_active = true, updated_at = NOW()
WHERE id = 3381;
```
- Resolves 64 orphan VMs affecting 0 products
- Zero channel impact

### Pre-Flight Checks

```sql
SELECT id, name FROM attributes WHERE id IN (179, 281);
-- Expected: Довжина (179), Бюджет PoE (281)

SELECT id, attribute_id, is_active FROM attribute_mappings WHERE id IN (3350, 3381);
-- Expected: both NULL attribute_id, both false is_active

SELECT count(*) FROM channel_attribute_mappings WHERE internal_attribute_id IN (179, 281);
-- Expected: 0
```

### Post-Flight Checks

```sql
-- Orphans: 125 → 0
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
WHERE am.id IS NULL OR am.is_active = false;
-- Expected: 0

-- Inconsistent: unchanged at 45
SELECT count(*) FROM attribute_value_mappings m
JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
JOIN attribute_values av ON av.id = m.attribute_value_id
WHERE am.attribute_id IS NOT NULL AND am.is_active = true
  AND av.attribute_id != am.attribute_id;
-- Expected: 45

-- ProductAttributes unchanged
SELECT count(*) FROM product_attributes;
-- Expected: 185566
```
**Validation:** Attribute 281 Бюджет PoE already exists and is assigned to "Комутатори". Perfect semantic match.
---

## Section F — Expected State After SAFE_LINK

| Metric | Current | After SAFE_LINK |
|--------|:-------:|:---------------:|
| review items | 352 | **232** |
| orphans | 125 | **0** |
| inconsistent | 45 | 45 |
| ambiguous global | 161 | 161 |
| unassigned | 21 | 21 |
| attribute_mappings | 1,151 | 1,151 (updated) |
| product_attributes | 185,566 | 185,566 |

---

## Section G — Machine-Readable Execution Proposal

```json
{
  "safe_link": [
    {
      "am_id": 3350,
      "supplier_attribute": "Довжина",
      "target_attribute_id": 179,
      "affected_vm_count": 61,
      "product_impact": 1375,
      "operation": "UPDATE attribute_mappings SET attribute_id=179, is_active=true WHERE id=3350"
    },
    {
      "am_id": 3381,
      "supplier_attribute": "Бюджет PoE",
      "target_attribute_id": 281,
      "affected_vm_count": 64,
      "product_impact": 0,
      "operation": "UPDATE attribute_mappings SET attribute_id=281, is_active=true WHERE id=3381"
    }
  ],
  "keep_global": [{
    "count": 161,
    "description": "All ambiguous global mappings are legitimate cross-category attributes"
  }],
  "manual_review": [
    {"category": "inconsistent_values", "count": 45,
     "description": "Compound frequency values requiring human decision"},
    {"category": "unassigned_attributes", "count": 21,
     "description": "Attributes needing category assignments"}
  ]
}
```

---

## Section H — Database Integrity (Unchanged)

| Table | Count | Status |
|:------|:-----:|:------:|
| products | 14,519 | ✅ |
| product_attributes | 185,566 | ✅ |
| attributes | 201 | ✅ |
| attribute_values | 7,883 | ✅ |
| attribute_mappings | 1,151 | ✅ |
| value_mappings | 8,142 | ✅ |
| category_attributes | 708 | ✅ |
| category_attribute_values | 7,577 | ✅ |
| category_mappings | 203 | ✅ |
| category_filters | 452 | ✅ |
| channel_category_mappings | 155 | ✅ |
| channel_attribute_mappings | 93 | ✅ |
| channel_value_mappings | 502 | ✅ |

**No database mutations were performed during this analysis.**

---

## Final Verdict

**READY FOR APPROVAL** ✅

- 66 items require manual administrator review (45 inconsistent + 21 unassigned)
- 125 orphan mappings can be resolved via 2 SAFE_LINK operations
- 161 ambiguous global mappings correctly classified as KEEP_GLOBAL
- Zero product data changes required
- Zero channel data changes required

Execution of the 2 SAFE_LINK operations would reduce review items from 352 → 232.

> **NO DATABASE MUTATIONS WERE PERFORMED.**