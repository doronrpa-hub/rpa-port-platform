"""
Nightly Learning Pipeline — Automated knowledge building.
==========================================================
Reads source collections, builds/enriches derived indexes.
All operations are ADDITIVE — only adds new fields and index entries.

Pipeline (4 steps):
  1. enrich_knowledge — Add extracted fields to knowledge_base & declarations
     (additive only: adds type, hs_codes_extracted, products_extracted, etc.)
  2. knowledge_indexer — Rebuild keyword_index, product_index, supplier_index
     from tariff, classification_knowledge, rcb_classifications, sellers
  3. deep_learn — Mine knowledge_base, declarations, classification_knowledge,
     rcb_classifications → enrich indexes with additional data (additive merge)
  4. read_everything — Build master brain_index from ALL 27 collections

Source collections: READ + additive field enrichment (never overwrites/deletes)
Index collections: WRITE (keyword_index, product_index, supplier_index, brain_index)

Called by rcb_nightly_learn scheduled Cloud Function at 2:00 AM Israel time.
Each step runs independently — if one fails, the rest still run.

No AI calls — pure Firestore reads + text parsing + index writes. $0 cost.
"""

import io
import os
import sys
import time
from datetime import datetime, timezone
from collections import defaultdict

import firebase_admin
from firebase_admin import firestore

# Fix Windows cp1255 encoding — scripts print Unicode (═══, ✅)
# In Cloud Functions this is a no-op (already UTF-8)
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# Firebase init — same guard as the scripts
cred_path = os.path.join(
    os.environ.get("APPDATA", ""),
    "gcloud", "legacy_credentials", "doronrpa@gmail.com", "adc.json"
)
if os.path.exists(cred_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "rpa-port-customs")

if not firebase_admin._apps:
    firebase_admin.initialize_app()


def run_pipeline():
    """
    Run the full nightly learning pipeline.
    All operations are additive — only adds data, never overwrites or deletes.
    Returns dict with results for each step.
    """
    db = firestore.client()
    results = {}
    t0 = time.time()

    print("=" * 60)
    print("  NIGHTLY LEARNING PIPELINE")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("  Mode: ADDITIVE — adds fields and indexes, never overwrites source data")
    print("=" * 60)

    # ── Step 1: Enrich knowledge_base (add extracted fields to source docs) ──
    # Reads: knowledge_base, rcb_classifications, declarations
    # Adds to source docs: type, hs_codes_extracted, products_extracted,
    #   suppliers_extracted, hs_codes_real, hs_code_is_filing (all additive)
    # Merges into: supplier_index, product_index, keyword_index
    print("\n--- Step 1/4: enrich_knowledge (add extracted fields) ---")
    step_t = time.time()
    try:
        # Lazy import to avoid name collision with Cloud Function
        import enrich_knowledge as ek_script
        ek_script.STATS_ONLY = False
        ek_script.run()
        elapsed = round(time.time() - step_t, 1)
        results["enrich_knowledge"] = {"status": "success", "duration_s": elapsed}
        print(f"  Step 1 done in {elapsed}s")
    except Exception as e:
        elapsed = round(time.time() - step_t, 1)
        results["enrich_knowledge"] = {"status": f"error: {e}", "duration_s": elapsed}
        print(f"  Step 1 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ── Step 2: Knowledge indexer (build keyword/product/supplier indexes) ──
    # Reads: tariff (11K), classification_knowledge, rcb_classifications, sellers
    # Writes: keyword_index, product_index, supplier_index
    print("\n--- Step 2/4: knowledge_indexer (build 3 inverted indexes) ---")
    step_t = time.time()
    try:
        import knowledge_indexer as ki_script
        ki_script.DRY_RUN = False
        ki_script.STATS_ONLY = False
        ki_script.run_all()
        elapsed = round(time.time() - step_t, 1)
        results["knowledge_indexer"] = {"status": "success", "duration_s": elapsed}
        print(f"  Step 2 done in {elapsed}s")
    except Exception as e:
        elapsed = round(time.time() - step_t, 1)
        results["knowledge_indexer"] = {"status": f"error: {e}", "duration_s": elapsed}
        print(f"  Step 2 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ── Step 3: Deep learn (mine all docs, enrich indexes with more data) ──
    # Reads: knowledge_base, declarations, classification_knowledge, rcb_classifications
    # Writes: keyword_index (merge), product_index (merge), supplier_index (merge)
    print("\n--- Step 3/4: deep_learn (mine + enrich indexes) ---")
    step_t = time.time()
    try:
        import deep_learn as dl_script
        dl_script.DRY_RUN = False
        dl_script.STATS_ONLY = False
        # Reset module-level state for clean run
        dl_script.mined = {
            "products": {},
            "suppliers": defaultdict(lambda: defaultdict(lambda: {"count": 0, "last_seen": "", "products": []})),
            "keywords": defaultdict(dict),
            "hs_connections": defaultdict(lambda: {"suppliers": set(), "products": set(), "duty_rate": "", "origin_countries": set()}),
            "stats": defaultdict(int),
        }
        dl_script.run()
        elapsed = round(time.time() - step_t, 1)
        results["deep_learn"] = {"status": "success", "duration_s": elapsed}
        print(f"  Step 3 done in {elapsed}s")
    except Exception as e:
        elapsed = round(time.time() - step_t, 1)
        results["deep_learn"] = {"status": f"error: {e}", "duration_s": elapsed}
        print(f"  Step 3 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ── Step 4: Read everything (build master brain_index from 27 collections) ──
    # Reads: ALL 27 knowledge-bearing collections
    # Writes: brain_index
    print("\n--- Step 4/4: read_everything (master brain_index) ---")
    step_t = time.time()
    try:
        import read_everything as re_script
        re_script.STATS_ONLY = False
        # Reset module-level state for clean run
        re_script.brain = defaultdict(lambda: defaultdict(lambda: {"sources": [], "total_weight": 0}))
        re_script.stats = defaultdict(int)
        re_script.run()
        elapsed = round(time.time() - step_t, 1)
        results["read_everything"] = {"status": "success", "duration_s": elapsed}
        print(f"  Step 4 done in {elapsed}s")
    except Exception as e:
        elapsed = round(time.time() - step_t, 1)
        results["read_everything"] = {"status": f"error: {e}", "duration_s": elapsed}
        print(f"  Step 4 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ── Save pipeline results ──
    total_time = round(time.time() - t0, 1)
    all_success = all(
        r.get("status") == "success" for r in results.values()
    )

    summary = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": total_time,
        "all_success": all_success,
        "steps": {
            name: {"status": r["status"], "duration_s": r["duration_s"]}
            for name, r in results.items()
        },
    }

    try:
        db.collection("system_metadata").document("nightly_learn").set(summary)
        print(f"\n  Pipeline metadata saved to system_metadata/nightly_learn")
    except Exception as e:
        print(f"\n  Failed to save pipeline metadata: {e}")

    # ── Final summary ──
    print("\n" + "=" * 60)
    print("  NIGHTLY LEARNING PIPELINE — COMPLETE")
    print(f"  Status: {'ALL SUCCESS' if all_success else 'SOME FAILURES'}")
    for name, r in results.items():
        status = r["status"]
        dur = r["duration_s"]
        icon = "OK" if status == "success" else "FAIL"
        print(f"    [{icon}] {name}: {status} ({dur}s)")
    print(f"  Total time: {total_time}s")
    print("=" * 60)

    return results
