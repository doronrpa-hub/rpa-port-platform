# HANDOFF: tariff_tree.py — Full XML Tariff Tree Extractor

## What Was Built

**`functions/lib/tariff_tree.py`** (~553 lines) — An isolated, in-memory tariff tree
reconstructed from two XML files in `data_c3/extracted/`:

- `CustomsItem.xml` (12.6 MB) — 18,032 import tree nodes with parent-child links
- `CustomsItemDetailsHistory.xml` (42.9 MB) — Hebrew + English descriptions

The tree covers all 9 hierarchy levels: Section (L1) > Chapter (L2) > Heading (L3) >
Subheading (L4-L5) > Israeli tariff item (L6-L9).

### Stats
- 18,032 import nodes parsed (BookType=1)
- 17,721 (98.3%) have descriptions from XML
- 311 (1.7%) still missing — fillable from Firestore `tariff` collection when `db` is provided
- 22 sections, 99 chapters, 1,266 headings
- Tree loads in ~5 seconds, cached as singleton after first call

## Two Public Functions

### `get_subtree(code_or_id, db=None) -> dict or None`

Returns the full subtree from a node downward, with recursive children.

Accepts:
- HS code: `"8431"`, `"84.31"`, `"8431490000"`, `"84.31.4900"`
- Section: `"XVI"`
- Chapter: `"84"`
- Node ID (int): `25900`

Returns dict: `{fc, hs, level, desc_he, desc_en, children: [...]}`

### `search_tree(query, db=None) -> list`

Searches Hebrew and English descriptions. Returns up to 50 matches, each with
full path from Section root down to the matching node.

Supports Hebrew prefix stripping (מ,ב,ל,ה,ו,כ,ש,וה,של).

Returns list of: `{fc, hs, level, desc_he, desc_en, path: [...], match_field}`

## Feature Flag

```python
# functions/lib/classification_agents.py, line 175
USE_TARIFF_TREE = False  # Flip to True to test tariff tree module
```

Currently **OFF**. Not wired to anything yet. Exists for future integration.
When False — all existing behavior unchanged, nothing breaks.

## Files

| File | Action | Lines |
|------|--------|-------|
| `functions/lib/tariff_tree.py` | NEW | ~553 |
| `functions/tests/test_tariff_tree.py` | NEW | ~203 |
| `functions/lib/classification_agents.py` | MODIFIED | +1 line (flag) |

## Test Results

- 18 new tariff tree tests — all passing
- 2,370 existing tests — all passing, zero regressions
- Total: 2,388 passed, 0 failed

## What the Next Step Is

1. **Wire the flag**: When `USE_TARIFF_TREE = True`, classification should use
   `get_subtree()` and `search_tree()` instead of flat Firestore `tariff` lookups.
   Key integration points:
   - `broker_engine.py` — replace `_search_tariff_db()` with tree navigation
   - `tool_executors.py` — `_search_tariff()` and `_verify_in_tariff_db()` could
     use tree lookups for hierarchical context
   - `elimination_engine.py` — tree structure enables proper GIR rule walking

2. **Extract duty rates**: The XML archive also contains `Tariff_0-6.xml`,
   `TariffDetailsHistory_0-52.xml`, and `ComputationMethodData_0-91.xml` which
   hold the actual duty rates, purchase tax, and computation formulas. These can
   be joined to the tree via `CustomsItemID`. Currently NOT extracted.

3. **Extract supplement rate tables**: Pages 3124-5540 of the PDF (2,416 pages)
   contain per-HS-code preferential rates under FTA supplements. These are the
   biggest data gap — the system can classify but cannot compute what you'll pay.

4. **Firestore gap-fill**: Call `load_tariff_tree(db=firestore_client)` to fill
   the 311 nodes missing descriptions from the existing `tariff` collection.
