# Admin Decision Sheet — 7 Remaining Mapping Decisions

**Status:** READ-ONLY — no changes have been made.
**Your decisions below will determine how the last 22 mapping items are resolved.**

---

## Decision A — GPU Clock "Немає даних"
**Mapping:** VM#15877

| Detail | Value |
|--------|-------|
| Supplier value | `Немає даних` |
| Current target | AV#4310 under attr 288 (wrong parent) |
| Proposed | Create `Немає даних` as canonical under attr 325 (Частота ядра, МГц) |
| Product impact | 1 GPU without frequency data |
| Precedent | Exists as canonical value under **54 other attributes** |

**Decision:** Create it under attr 325? **YES** (54 precedents) / NO (leave manual)

**Recommendation: YES** — Standard no-data placeholder pattern.

---

## Decision B — Бренд (Brand) — 6 mappings
**AM IDs:** 3395, 3042, 3045, 3044, 3046, 3043
**Attribute:** Бренд (id=353)

| Detail | Value |
|--------|-------|
| Supplier names | Бренд, Виробник, Бренди, brand, Brand, BRAND |
| Products WITH brand_id | **396** of 14,519 |
| Products WITHOUT brand | **14,123** |
| Existing brand mechanism | `products.brand_id` FK, but 97% empty |
| Сумісний бренд attr | 183 exists for "compatible brand" — different concept |

**Options:**
1. **Assign attr 353 to categories** — Let supplier imports fill brand data. Complements existing brand_id.
2. **Leave unassigned** — 14,123 products remain without brand.
3. **Merge into brand_id system** — Not directly possible (code change needed).

**Decision:** Option 1 / Option 2 / Option 3

**Recommendation: OPTION 1** — All 6 names mean "manufacturer brand", not "compatible brand". Fills the branding gap for 97% of products.
---

## Decision C — ECC (Error Checking) — 2 mappings
**AM IDs:** 2686, 2687
**Attribute:** Перевірка та корекція помилок (ECC) (id=328)

| Detail | Value |
|--------|-------|
| Supplier values | `Є` (Yes), `Немає` (No) — boolean ECC |
| Attribute values | AV#6060 `Є`, AV#6059 `Немає` — already exist |
| Current categories | **None** — no category_attributes record |
| Product usage | 0 (no category = unusable) |
| Candidate categories | Оперативна пам'ять (28), SSD (6), Сервери (78), Жорсткі диски (17), Контролери (23) |

**Decision:** Check all applicable:
- ☐ Оперативна пам'ять (28) — RAM ECC is primary use case
- ☐ SSD-накопичувачі (6) — Some SSDs have ECC
- ☐ Сервери (78) — Server-class components
- ☐ None (leave unassigned)

**Recommendation:** At minimum Оперативна пам'ять + Сервери.

---

## Decision D — RAID Support — 1 mapping
**AM ID:** 2753
**Attribute:** Підтримка RAID (id=351)

| Detail | Value |
|--------|-------|
| Supplier values | None (no value mappings exist) |
| Attribute values | None (attribute_values table empty for 351) |
| Current categories | None |
| Candidate categories | Контролери (23), PCI (24), Сервери (78), SSD (6) |

**Note:** Placeholder only — needs RAID level values created first.

**Options:**
1. **Leave for now** — Needs value definition first
2. **Create values + assign** — Define RAID levels first
3. **Delete mapping** — Remove if permanently unused

**Decision:** Option 1 / 2 / 3

**Recommendation: OPTION 1** — Needs value creation before assignment.
---

## Decision E — Яскравість дисплея vs Яскравість — 1 mapping
**AM ID:** 9182 (dclink-specific)

| Detail | Attr 299 `Яскравість` | Attr 358 `Яскравість дисплея` |
|--------|:---------------------:|:-----------------------------:|
| Categories | Монітори (74), Графічні планшети | **None** |
| Values | 30+ (`220 кд/м2`, `250 кд/м2`, etc.) | **0 values** |
| Product usage | Active | None |

**The problem:** dclink's `Яскравість дисплея` maps to attr 358, but attr 299 already covers display brightness in the same categories. These are semantically identical — display brightness in cd/m².

**Options:**
1. **MERGE** — Reassign dclink value mappings from attr 358 → attr 299. Deactivate attr 358.
2. **KEEP SEPARATE** — Assign attr 358 to Монітори. Create separate values.

**Decision:** Option 1 (MERGE) / Option 2 (KEEP)

**Recommendation: OPTION 1 (MERGE)** — Identical semantics, eliminating a dead duplicate.

---

## Decision F — Кількість (Quantity) — 8 mappings
**Attribute:** Кількість (id=167) — currently no category assignment

### How it works
Keep all 8 mappings global (category_id=NULL). Just assign attr 167 to categories via `category_attributes`. The MappingResolver handles this automatically.

| # | AM ID | Supplier Name | Semantic Meaning | Proposed Categories |
|:-:|:-----:|:--------------|:-----------------|:--------------------|
| 1 | 2531 | Кількість | Generic quantity | ALL categories |
| 2 | 2533 | Кількість SIP акаунтів | SIP account count | IP-телефони |
| 3 | 2579 | Кількість розеток | Power socket count | Розетки, подовжувачі |
| 4 | 2581 | Кількість смуг | Network lane count | Мережеве обладнання |
| 5 | 2582 | Кількість у комплекті | Bundle/pack qty | Multi-pack categories |
| 6 | 2583 | Кількість у коробці, шт | Box qty | Wholesale categories |
| 7 | 2584 | Кількість у наборі | Kit qty | Kit categories |
| 8 | 2585 | Кількість у ящику, шт | Case/lot qty | Wholesale categories |

**Decision:** Which approach?
1. Assign attr 167 to **ALL** categories — simplest, quantity is universal
2. Assign to **SELECTED** categories — pick from the table above
3. **Leave unassigned** — keep all 8 mappings unused

---

## Decision G — Форм-фактор (Form Factor) — 2 mappings
**AM IDs:** 2954 (`Форм-фактор`), 2963 (`Формфактор`)
**Attribute:** Форм-фактор (id=172)

### The problem: 47 values, 5 different semantics

| Concept | Example Values | Should map to |
|:--------|:--------------|:--------------|
| Motherboard size | ATX, MicroATX, Mini-ITX, E-ATX | Specialized attr 267 (Форм-фактор материнської плати) |
| Drive size | 2.5", 3.5", M.2 2230, M.2 2280, mSATA | Specialized attr 360 (Форм-фактор накопичувача) |
| Memory module | DIMM, SO-DIMM, UDIMM | Specialized attr 361 (Форм-фактор пам'яті) |
| PSU size | SFX, SFX-L, PS2 | Specialized attr 362 (Форм-фактор блока живлення) |
| Device type | настільний, портативний, стійковий, моноблок | Generic attr 172 OR specialized attr 363 (Форм-фактор корпусу) |

The system already has **6 specialized form factor attributes** (360, 361, 362, 363, 364, 267). Assigning all 47 values to a single generic attr 172 would mix ATX (motherboards) with DIMM (RAM) in the same dropdown — semantically incorrect.

**Options:**
1. **Redistribute to specialized attrs** — Remap supplier values to correct specialized attributes. Semantically correct but requires more work.
2. **Assign generic to limited categories** — Only assign attr 172 to categories where its values are unambiguous (e.g., Корпуси only).
3. **Leave unassigned** — Don't resolve now.

**Decision:** Option 1 / Option 2 / Option 3

**Recommendation: OPTION 1** — The 47 values must be split across specialized attributes for correct semantics.

---

## Summary — Quick Reference

| # | Decision | Recommendation | Your Choice |
|:-:|:---------|:--------------|:-----------:|
| A | GPU "Немає даних" under attr 325 | **YES** (54 precedents) | ☐ |
| B | Бренд (attr 353) category assignment | **OPTION 1** — Assign to categories | ☐ |
| C | ECC categories | **Оперативна пам'ять + Сервери** | ☐ |
| D | RAID (attr 351) future | **OPTION 1** — Leave for now | ☐ |
| E | Яскравість дисплея merge | **OPTION 1 (MERGE)** → attr 299 | ☐ |
| F | Кількість (attr 167) categories | **OPTION 1** — ALL categories | ☐ |
| G | Форм-фактор (attr 172) | **OPTION 1** — Use specialized attrs | ☐ |

**Once you mark your choices:**
- 44 SAFE_CREATE GPU clock values can be executed (already approved by precedent)
- Category assignments and remapping can be implemented
- 22 remaining mapping items can be fully resolved
**Recommendation: OPTION 1** — Quantity is universal. Simplest correct approach.