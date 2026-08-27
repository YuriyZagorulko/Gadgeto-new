# Final Semantic Review — 66 Remaining Mapping Items

Generated: 2026-08-27 20:15 EEST

> READ-ONLY ANALYSIS — No database mutations were performed.

---

## Executive Summary

| Category | Total | SAFE_CREATE | CATEGORY_SPECIFIC | MANUAL_REVIEW |
|:---------|:-----:|:-----------:|:-----------------:|:-------------:|
| Inconsistent GPU clock values | 45 | 44 | 0 | 1 |
| Unassigned attributes | 21 | 0 | 9 | 12 |
| **TOTAL** | **66** | **44** | **9** | **13** |

---

## Section A — 45 Inconsistent GPU Clock Values

### Context

All 45 belong to:
- **Supplier attribute:** `Частота ядра` (SA#10548, global)
- **Parent mapping:** AM#9180 → Attribute 325 `Частота ядра, МГц` (cat: Відеокарти)
- **Current target:** Attribute 288 `Частота ядра` (wrong)
- **All affected products:** Відеокарти (id=14)

### Key Finding

**Attribute 325 already contains 3 compound values** with full mode descriptions:
- AV#4706: `Boost Clock: 2482 MHz; Extreme Performance: 2497 MHz`
- AV#4703: `Boost Clock: 2527 MHz; Extreme Performance: 2535 MHz`
- AV#4701: `Boost Clock: 2542 MHz; Extreme Performance: 2557 MHz`

These 3 values (created during initial migration) prove the canonical model supports compound frequency descriptions with mode labels. The remaining 45 values are semantically identical.

### Classification: 44 SAFE_CREATE + 1 MANUAL_REVIEW

44 should be created as canonical values under Attribute 325 following the existing precedent. The 1 MANUAL_REVIEW is `Немає даних` — admin must confirm no-data for GPU clock.
### Decision Matrix — 45 GPU Clock Values

| # | VM ID | Supplier Value | Usage | Action | Reason |
|:-:|:-----:|----------------|:-----:|:------:|--------|
| 1 | 15830 | Base 2295/Boost 2617 MHz | 1 | SAFE_CREATE | Same as AV#4706 pattern |
| 2 | 15831 | Base 2295/Boost 2700 MHz | 2 | SAFE_CREATE | Follows precedent |
| 3 | 15835 | Boost 2520/Game 2070 MHz | 0 | SAFE_CREATE | Follows precedent |
| 4 | 15838 | Boost 2602; Extreme 2617 MHz | 2 | SAFE_CREATE | Same as AV#4706 |
| 5 | 15839 | Boost 2632; Extreme 2647 MHz | 1 | SAFE_CREATE | Same as AV#4703 |
| 6 | 15840 | Boost 2677; OC 2707 MHz | 0 | SAFE_CREATE | Follows precedent |
| 7 | 15841 | Boost 2920; Game 2340 | 1 | SAFE_CREATE | Follows precedent |
| 8 | 15832 | Boost 2970/Game 2400 MHz | 0 | SAFE_CREATE | Follows precedent |
| 9 | 15842 | Boost 2970; Game 2400 MHz | 0 | SAFE_CREATE | Follows precedent |
| 10 | 15843 | Boost 3010/Game 2400 MHz | 0 | SAFE_CREATE | Follows precedent |
| 11 | 15844 | Boost 3010; Game 2460 MHz | 0 | SAFE_CREATE | Follows precedent |
| 12 | 15845 | Boost 3060; Game 2520 MHz | 0 | SAFE_CREATE | Follows precedent |
| 13 | 15846 | Boost 3130/Game 2530 MHz | 0 | SAFE_CREATE | Follows precedent |
| 14 | 15847 | Boost 3230/Game 2620 MHz | 0 | SAFE_CREATE | Follows precedent |
| 15 | 15833 | Boost 3290/Game 2700 MHz | 0 | SAFE_CREATE | Follows precedent |
| 16 | 15848 | Boost 3310/Game 2620 MHz | 1 | SAFE_CREATE | Follows precedent |
| 17 | 15849 | Game 2250/Boost 2655 MHz | 0 | SAFE_CREATE | Follows precedent |
| 18 | 15850 | Graphics 2295/Boost 2452 MHz | 0 | SAFE_CREATE | Follows precedent |
| 19 | 15851 | Graphics 2295/Boost 2482 MHz | 0 | SAFE_CREATE | Follows precedent |
| 20 | 15852 | Graphics 2295/Boost 2617 MHz | 1 | SAFE_CREATE | Follows precedent |
| 21 | 15853 | Graphics 2317/Boost 2572 MHz | 2 | SAFE_CREATE | Follows precedent |
| 22 | 15854 | Graphics 2325/Boost 2512 MHz | 0 | SAFE_CREATE | Follows precedent |
| 23 | 15855 | Graphics 2325/Boost 2542 MHz | 0 | SAFE_CREATE | Follows precedent |
| 24 | 15856 | OC 1537, Default Boost 1507 MHz | 1 | SAFE_CREATE | Follows precedent |
| 25 | 15857 | OC 2527, Default Boost 2497 MHz | 0 | SAFE_CREATE | Follows precedent |
| 26 | 15858 | OC 2565, Default Boost 2535 MHz | 1 | SAFE_CREATE | Follows precedent |
| 27 | 15859 | OC 2572, Default Boost 2542 MHz | 1 | SAFE_CREATE | Follows precedent |
| 28 | 15860 | OC 2610, Default Boost 2580 MHz | 0 | SAFE_CREATE | Follows precedent |
| 29 | 15861 | OC 2632, Default Boost 2602 MHz | 1 | SAFE_CREATE | Follows precedent |
| 30 | 15862 | OC 2647, Default Boost 2617 MHz | 1 | SAFE_CREATE | Follows precedent |
| 31-44 | 15863-15876 | Various OC/Game/Silent combos | 0-1 | SAFE_CREATE | All follow precedent |
| 45 | 15877 | Немає даних | 1 | MANUAL_REVIEW | Confirm no-data placeholder |

---

## Section B — 21 Unassigned Attribute Mappings

### Decision Matrix

| # | Attribute | Maps | Recommendation | Action | Reason |
|:-:|:----------|:----:|:--------------|:------:|--------|
| 1-6 | Бренд (353) | 6 | Assign categories, keep global | CATEGORY_SPECIFIC | 14,123/14,519 products lack brand_id. Supplement approach. |
| 7 | Кількість generic | 1 | Assign to multiple categories | CATEGORY_SPECIFIC | Generic quantity belongs everywhere |
| 8 | Кількість SIP акаунтів | 1 | IP-телефони category | CATEGORY_SPECIFIC | SIP accounts are phone-specific |
| 9 | Кількість розеток | 1 | Розетки/подовжувачі | CATEGORY_SPECIFIC | Socket count for power strips |
| 10 | Кількість смуг | 1 | Мережеве обладнання | CATEGORY_SPECIFIC | Network lane count |
| 11 | Кількість у комплекті | 1 | Various (multi-pack) | CATEGORY_SPECIFIC | Bundle/pack quantity |
| 12 | Кількість у коробці шт | 1 | Wholesale categories | CATEGORY_SPECIFIC | Box quantity |
| 13 | Кількість у наборі | 1 | Kit categories | CATEGORY_SPECIFIC | Kit quantity |
| 14 | Кількість у ящику шт | 1 | Wholesale categories | CATEGORY_SPECIFIC | Case quantity |
| 15-16 | ECC (328) | 2 | Assign to memory/storage | MANUAL_REVIEW | Admin chooses categories (RAM, SSD, etc.) |
| 17 | RAID (351) | 1 | Assign to storage/controllers | MANUAL_REVIEW | Admin chooses categories |
| 18-19 | Форм-фактор (172) | 2 | Make category-specific | CATEGORY_SPECIFIC | ATX (motherboard), 2.5" (drives), DIMM (RAM) differ |
| 20 | Час відгуку матриці (357) | 1 | Add CategoryAttribute(74,357) | CATEGORY_SPECIFIC | Not currently in Монітори; should be added |
| 21 | Яскравість дисплея (358) | 1 | Merge/redirect to 299 | MANUAL_REVIEW | Attr 299 (Яскравість) already in Монітори and Графічні планшети |

### How to Make Кількість Category-Specific

Keep the mapping global (category_id=NULL) on all 8 attribute_mappings. Instead, assign Attribute 167 to all relevant categories via `category_attributes`. The MappingResolver loads mappings for any category that has the attribute — so this approach works without changing the supplier mapping layer.

---

## Section C — Summary by Action

| Action | Count | Description |
|:-------|:-----:|:------------|
| SAFE_CREATE | 44 | Create canonical AVs under attr 325 for compound GPU clock descriptions (following precedent) |
| CATEGORY_SPECIFIC | 9 | Assign attributes to appropriate categories |
| MANUAL_REVIEW | 13 | Admin decisions needed |
| **TOTAL** | **66** | |

---

## Section D — Database Safety

| Concern | SAFE_CREATE | CATEGORY_SPECIFIC |
|:--------|:-----------:|:-----------------:|
| ProductAttributes modified? | NO | NO |
| Products modified? | NO | NO |
| Canonical AVs modified? | YES (create 44) | NO |
| ValueMappings modified? | YES (reassign 44) | NO |
| CategoryAttributes modified? | NO | YES (add relations) |
| Channel/Rozetka modified? | NO | NO |

---

## Section E — Final Verdict

| Metric | Value |
|:-------|:------|
| Total reviewed | 66 |
| Automatically resolvable (SAFE_CREATE) | **44** |
| Requires admin confirmation | **22** (9 cat assign + 13 manual) |
| Administrator decisions needed | **~7** (category assignments + merge decisions) |

**Can all 66 be safely resolved automatically?** No — 44 can, 9 need admin category confirmation, 13 need admin judgment.

**Smallest manual workload:** ~7 administrator decisions.

**Next execution phase:** Execute 44 SAFE_CREATE, then present 22 items for admin decisions.

> **NO DATABASE MUTATIONS WERE PERFORMED.**
