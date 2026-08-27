# Mapping Audit Report — Phase 1-9 Complete Analysis

Generated: 2026-08-27 18:30 EEST
Backup: `/home/yuri/Desktop/my/projects/Gadgeto-new/backup_mapping_analysis.dump`

---

## Database Backup

**Backup created and verified:**
- Format: PostgreSQL custom (pg_dump -Fc -Z 9)
- Path: `/home/yuri/Desktop/my/projects/Gadgeto-new/backup_mapping_analysis.dump`
- Size: 37 MB compressed
- Verification: `pg_restore -l` shows 616 TOC entries, valid archive
- DB version: 16.15

**No mutations have been performed.** All analysis was read-only.

---

## 1. Inconsistent Value Mappings (68 total)

### Group Summary

| Parent Attribute | Target Attribute (wrong) | Count |
|---|---|---|
| Частота ядра, МГц (id=325) | Частота ядра (id=288) | 68 |

### Classification

| Classification | Count |
|---|---:|
| SAFE_REASSIGN | **0** |
| SAFE_CREATE | **23** |
| MANUAL_REVIEW | **45** |

**Why 0 SAFE_REASSIGN?** No supplier value among the 68 has an exact string match among canonical values under the correct parent attribute (Частота ядра, МГц, id=325). The 8 existing canonical values under id=325 are:
- '2160 - 2580', '2452-2588', '2497 - 2595', '2557-2587', '2602'
- 'Boost Clock: 2482 MHz; Extreme Performance: 2497 MHz'
- 'Boost Clock: 2527 MHz; Extreme Performance: 2535 MHz'
- 'Boost Clock: 2542 MHz; Extreme Performance: 2557 MHz'

None of the 68 supplier values match these exactly.
### 23 SAFE_CREATE Proposals

These are simple numeric frequencies/ranges that clearly belong under "Частота ядра, МГц" (id=325). Each would need a new `attribute_values` record created before reassignment.

| Mapping ID | Supplier Value | Product Usage | Proposed Canonical AV |
|---|---|---|---|
| 15802 | 1477 | 1 | AV='1477' under attr id=325 |
| 15804 | 2280 - 2497 | 1 | AV='2280 - 2497' under attr id=325 |
| 15805 | 2280 - 2512 | 1 | AV='2280 - 2512' under attr id=325 |
| 15806 | 2280 - 2535 | 0 | AV='2280 - 2535' under attr id=325 |
| 15807 | 2407 - 2550 | 0 | AV='2407 - 2550' under attr id=325 |
| 15808 | 2407 - 2573 | 0 | AV='2407 - 2573' under attr id=325 |
| 15809 | 2407 - 2602 | 1 | AV='2407 - 2602' under attr id=325 |
| 15810 | 2407 - 2632 | 0 | AV='2407 - 2632' under attr id=325 |
| 15811 | 2407 - 2655 | 0 | AV='2407 - 2655' under attr id=325 |
| 15813 | 2482 - 2497 | 0 | AV='2482 - 2497' under attr id=325 |
| 15814 | 2497 | 1 | AV='2497' under attr id=325 |
| 15815 | 2497 - 2512 | 0 | AV='2497 - 2512' under attr id=325 |
| 15816 | 2497 - 2550 | 1 | AV='2497 - 2550' under attr id=325 |
| 15818 | 2512 - 2587 | 0 | AV='2512 - 2587' under attr id=325 |
| 15819 | 2512 - 2625 | 0 | AV='2512 - 2625' under attr id=325 |
| 15820 | 2550 | 0 | AV='2550' under attr id=325 |
| 15822 | 2572 - 2587 | 1 | AV='2572 - 2587' under attr id=325 |
| 15823 | 2572 - 2617 | 0 | AV='2572 - 2617' under attr id=325 |
| 15824 | 2572 - 2632 | 1 | AV='2572 - 2632' under attr id=325 |
| 15826 | 2617 | 0 | AV='2617' under attr id=325 |
| 15827 | 2617 - 2670 | 0 | AV='2617 - 2670' under attr id=325 |
| 15828 | 2617-2805 | 0 | AV='2617-2805' under attr id=325 |
| 15829 | 2780 - 3320 | 1 | AV='2780 - 3320' under attr id=325 |

**Total product usage across SAFE_CREATE proposals: 9 products affected**
**Canonical values to create: 23**

### 45 MANUAL_REVIEW Items

These contain compound descriptions, OC mode details, or non-standard formats requiring human judgment:

| Category | Count | Examples |
|---|---|---|
| Boost Clock compound values | 15 | 'Boost Clock: 2602 MHz; Extreme Performance: 2617 MHz' |
| Base Clock + Boost Clock | 6 | 'Base Clock: 2295 MHz/Boost Clock: 2617 MHz' |
| OC Mode values | 16 | 'OC Mode - 1537 MHz, Default Mode – Boost Clock : 1507 MHz' |
| Game Clock values | 4 | 'Game: 2250 MHz/Boost: 2655 MHz' |
| Silent Mode values | 3 | 'Silent Mode – Boost Clock : 2790 MHz/Game Clock: 2220 MHz' |
| Немає даних | 1 | No-data placeholder |

**Total product usage across MANUAL_REVIEW: 18 products**

**Recommendation:** An administrator should review compound values to decide whether they should be:
- Stored as-is under Частота ядра, МГц (new canonical values)
- Simplified to represent only the core/boost frequency
- Categorized differently
---

## 2. Orphan Value Mappings (152 total)

### Classification

| Subcategory | Count | Classification |
|---|---:|---|
| Parent missing | 27 | **SAFE_LINK** (all 27) |
| Parent inactive | 125 | **MANUAL_REVIEW** (125) |

### 2.1 Parent Missing — SAFE_LINK (27)

**Supplier Attribute:** `Технології заряджання` (global, SA#11469, supplier_id=NULL)

**Situation:** The global supplier attribute exists and has 27 `supplier_attribute_values` with their corresponding `attribute_value_mappings`. However, there is NO `attribute_mapping` record (parent) for SA#11469. This means the MappingResolver skips all values from this attribute entirely.

**Resolution: Create a single `attribute_mapping` record:**
- `supplier_attribute_id` = 11469
- `attribute_id` = 191 (Технології заряджання)
- `is_active` = true
- `category_id` = NULL (global)

**Validation:** All 27 existing value mappings already point to valid AVs under attribute id=191. The exact canonical values already exist. No value changes needed.

**Product usage:** Unknown — currently all products with this attribute are completely skipped during import. After linking, they will resolve correctly.

### 2.2 Parent Inactive — MANUAL_REVIEW (125)

These belong to two global supplier attributes whose `attribute_mapping` is inactive and has no internal attribute target:

| AM ID | Supplier Attribute | Target | Active | Child VMs | Product Usage |
|---|---|---|---|---|---|
| 3350 | Довжина (SA#11126) | NULL | false | 61 | 1375 |
| 3381 | Бюджет PoE (SA#11391) | NULL | false | 64 | 0 |

**Why inactive?** These mappings were created during initial import with no internal attribute target (attribute_id IS NULL). Likely intentionally set to "Не імпортувати".

**Recommendation:**
- AM#3350 (Довжина, 61 values, 1375 product usage): Significant product impact. Administrator should decide.
- AM#3381 (Бюджет PoE, 64 values, 0 product usage): No product impact.
---

## 3. Ambiguous Global Attribute Mappings (160 total)

### Classification: All 160 are **MANUAL_REVIEW**

All 160 ambiguous global mappings are legitimate use of the same attribute across multiple categories. No conflicting semantics were detected.

**Key attributes:**

| Attribute | Categories | Assessment |
|---|---|---|
| Вага (id=354) | 43 | Normal — weight applies to many categories |
| Розміри (id=355) | 13 | Normal — dimensions are cross-category |
| Підтримка Bluetooth (id=347) | 16 | Normal — BT is cross-category |
| Об'єм вбудованої пам'яті (id=345) | 4 | Normal — storage for phones/tablets/laptops |
| Об'єм пам'яті відеокарти (id=344) | 4 | Normal — VRAM for computer-like items |

**No automatic changes recommended.** If a specific supplier attribute maps to different internal attributes by category, category-specific mappings should be created. No such conflicts were found.

---

## 4. Unassigned Attribute Mappings (21 total in 7 groups)

### Classification: All 21 are **MANUAL_REVIEW**

| Attribute | Mappings | Product Usage | Supplier Names |
|---|---|---|---|
| Бренд (id=353) | 6 | 0 | brand, Brand, BRAND, Бренд, Бренди, Виробник |
| Кількість (id=167) | 8 | 0 | Кількість, Кількість SIP акаунтів, Кількість розеток, etc. |
| ECC (id=328) | 2 | 0 | Перевірка і/та корекція помилок (ECC) |
| Підтримка RAID (id=351) | 1 | 0 | Підтримка RAID |
| Форм-фактор (id=172) | 2 | 0 | Форм-фактор, Формфактор |
| Час відгуку матриці (id=357) | 1 | 0 | Час відгуку матриці |
| Яскравість дисплея (id=358) | 1 | 0 | Яскравість дисплея |

**All have 0 product usage** because they have no category assignment. Products can't use attributes that aren't assigned to any category.

**Notes:**
- **Бренд** may be a historical artifact — brand should go through `products.brand_id`
- **Кількість** is highly generic; each variant should be category-specific
- **ECC, RAID, Форм-фактор, Час відгуку, Яскравість** need category assignments

---

## 5. Database Integrity

### Before/After Counts (unchanged — no mutations performed)

| Table | Count | Status |
|---|---|---|
| products | 14,519 | ✅ Unchanged |
| product_attributes | 185,566 | ✅ Unchanged |
| attributes | 201 | ✅ Unchanged |
| attribute_values | 7,860 | ✅ Unchanged |
| category_attributes | 708 | ✅ Unchanged |
| category_attribute_values | 7,577 | ✅ Unchanged |
| attribute_mappings | 1,150 | ✅ Unchanged |
| attribute_value_mappings | 8,142 | ✅ Unchanged |
| category_mappings | 203 | ✅ Unchanged |
| category_filters | 452 | ✅ Unchanged |
| channel_category_mappings | 155 | ✅ Unchanged |
| channel_attribute_mappings | 93 | ✅ Unchanged |
| channel_value_mappings | 502 | ✅ Unchanged |

---

## 6. Product Data Safety

- ProductAttributes modified: **0**
- Product data modified: **0**
- value_text modified: **0**

---

## 7. Channel Safety

- ChannelCategoryMappings modified: **0**
- ChannelAttributeMappings modified: **0**
- ChannelValueMappings modified: **0**

---

## 8. Backup Confirmation

- **Path:** `/home/yuri/Desktop/my/projects/Gadgeto-new/backup_mapping_analysis.dump`
- **Format:** pg_dump custom (Fc), Z=9 compression
- **Size:** 37 MB
- **Verified:** `pg_restore -l` confirms 616 TOC entries

---

## 9. Summary of Recommended Actions

| Category | Total | Resolvable Now | Needs Admin |
|---|---:|---:|---:|
| Inconsistent Values | 68 | 23 (SAFE_CREATE proposals) | 45 |
| Orphans | 152 | 27 (SAFE_LINK) | 125 |
| Ambiguous Global | 160 | 0 | 160 |
| Unassigned | 21 | 0 | 21 |
| **Total** | **401** | **50** | **351** |

### Can Be Done Immediately (SAFE_LINK):
1. **Create attribute_mapping for Технології заряджання (SA#11469 → attr 191)** — resolves 27 orphans immediately.

### Proposed for Admin Approval (SAFE_CREATE):
2. **Create 23 canonical values under Частота ядра, МГц (id=325)** — simple numeric frequencies, then reassign value mappings (~9 products affected).

### Requires Admin Decision (MANUAL_REVIEW):
3. **45 compound frequency values** — keep as-is, simplify, or categorize differently
4. **125 inactive orphans** — decide on Довжина (1375 products) and Бюджет PoE (0 products)
5. **160 ambiguous global mappings** — confirm global assignment
6. **21 unassigned mappings** — assign to appropriate categories

---

## 10. Key Findings

1. **No SAFE_REASSIGN cases** — none of the 68 supplier values match existing canonical values under the correct parent attribute
2. **27 orphans trivially fixable** — missing parent `attribute_mapping` only; values already correct
3. **No product data changes needed** — all fixes are in the mapping layer
4. **MappingResolver works correctly** — no bugs found; precedence is correct
5. **Backup verified** — safe to proceed with mutations after admin approval