"""
Live test: Verification Engine against production Firestore.

Run: python test_verification_live.py

Tests 3 products with known expected outcomes:
1. Steel storage box (HS 7326.9000, origin China) — expects ANTIDUMPING warning
2. Rubber medical gloves (HS 4015.1900, has_standards) — expects STANDARD flag
3. Laptop (HS 8471.3000, EU origin) — expects FTA info flag + good bilingual match
"""

import os
import sys
import json

# Add functions dir to path
sys.path.insert(0, os.path.dirname(__file__))

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firestore
sa_path = os.path.join(os.path.expanduser("~"), "sa-key.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

from lib.verification_engine import run_verification_engine, build_verification_flags_html, _reset_caches


def test_steel_box():
    """Test 1: Steel storage box from China — expect ANTIDUMPING warning."""
    print("\n" + "=" * 70)
    print("TEST 1: Steel storage box (HS 7326.9000, origin China)")
    print("=" * 70)

    _reset_caches()
    classifications = [{
        "hs_code": "7326.9000",
        "item": "steel storage box for industrial use, foldable",
        "official_description_he": "פריטים אחרים, מפלדה או מברזל",
        "official_description_en": "Other articles of iron or steel",
        "confidence": 0.82,
        "origin_country": "China",
    }]

    # Mock FIO data for the HS code
    fio = {
        "7326.9000": {
            "authorities_summary": ["משרד הכלכלה"],
            "has_standards": False,
        }
    }

    result = run_verification_engine(db, classifications, free_import_results=fio)

    hs_result = result.get("7326.9000", {})
    phase4 = hs_result.get("phase4", {})
    phase5 = hs_result.get("phase5", {})
    flags = hs_result.get("flags", [])

    print(f"\n  Phase 4: bilingual_match={phase4.get('bilingual_match')}")
    print(f"           HE score={phase4.get('he_match_score')}, EN score={phase4.get('en_match_score')}")
    print(f"  Phase 5: verified={phase5.get('verified')}, adj={phase5.get('confidence_adjustment')}")
    print(f"           directives={len(phase5.get('directives_found', []))}")
    print(f"  Flags ({len(flags)}):")
    for f in flags:
        print(f"    [{f['severity']}] {f['type']}: {f['message_en']}")

    # Verify expectations
    ad_flags = [f for f in flags if f["type"] == "ANTIDUMPING"]
    assert len(ad_flags) >= 1, "Expected ANTIDUMPING flag for ch.73 from China"
    print("\n  ✅ PASS: ANTIDUMPING flag present")

    # Check HTML rendering
    enriched = {"ve_flags": flags, "ve_phase4": phase4}
    html = build_verification_flags_html(enriched)
    assert html and len(html) > 50, "Expected non-empty HTML"
    print(f"  ✅ PASS: HTML rendered ({len(html)} chars)")

    return True


def test_rubber_gloves():
    """Test 2: Rubber medical gloves — expect STANDARD flag."""
    print("\n" + "=" * 70)
    print("TEST 2: Rubber medical gloves (HS 4015.1900, has_standards)")
    print("=" * 70)

    _reset_caches()
    classifications = [{
        "hs_code": "4015.1900",
        "item": "rubber medical examination gloves, non-sterile",
        "official_description_he": "כפפות מגומי וולקני",
        "official_description_en": "Gloves of vulcanized rubber",
        "confidence": 0.90,
        "origin_country": "Malaysia",
    }]

    fio = {
        "4015.1900": {
            "authorities_summary": ["מכון התקנים"],
            "has_standards": True,
        }
    }

    result = run_verification_engine(db, classifications, free_import_results=fio)

    hs_result = result.get("4015.1900", {})
    flags = hs_result.get("flags", [])

    print(f"\n  Flags ({len(flags)}):")
    for f in flags:
        print(f"    [{f['severity']}] {f['type']}: {f['message_en']}")

    std_flags = [f for f in flags if f["type"] == "STANDARD"]
    assert len(std_flags) >= 1, "Expected STANDARD flag for has_standards=True"
    print("\n  ✅ PASS: STANDARD flag present")

    return True


def test_laptop():
    """Test 3: Laptop from EU — expect FTA info flag + good bilingual match."""
    print("\n" + "=" * 70)
    print("TEST 3: Laptop (HS 8471.3000, EU origin, FTA eligible)")
    print("=" * 70)

    _reset_caches()
    classifications = [{
        "hs_code": "8471.3000",
        "item": "laptop computer portable, Intel Core processor, 16GB RAM",
        "official_description_he": "מכונות עיבוד נתונים אוטומטיות ניידות",
        "official_description_en": "Portable automatic data processing machines",
        "confidence": 0.88,
        "origin_country": "EU",
        "fta": {"eligible": True, "agreement": "EU-Israel Association Agreement"},
    }]

    result = run_verification_engine(db, classifications)

    hs_result = result.get("8471.3000", {})
    phase4 = hs_result.get("phase4", {})
    flags = hs_result.get("flags", [])

    print(f"\n  Phase 4: bilingual_match={phase4.get('bilingual_match')}")
    print(f"           HE score={phase4.get('he_match_score')}, EN score={phase4.get('en_match_score')}")
    print(f"  Flags ({len(flags)}):")
    for f in flags:
        print(f"    [{f['severity']}] {f['type']}: {f['message_en']}")

    fta_flags = [f for f in flags if f["type"] == "FTA"]
    assert len(fta_flags) >= 1, "Expected FTA info flag for EU origin"
    print("\n  ✅ PASS: FTA flag present")

    # Check bilingual match
    assert phase4.get("bilingual_match") is True, "Expected bilingual match for laptop"
    print("  ✅ PASS: Bilingual match confirmed")

    return True


if __name__ == "__main__":
    print("🔍 Verification Engine Live Tests")
    print("=" * 70)

    results = []
    for test_fn in [test_steel_box, test_rubber_gloves, test_laptop]:
        try:
            passed = test_fn()
            results.append(("PASS", test_fn.__name__))
        except AssertionError as e:
            results.append(("FAIL", f"{test_fn.__name__}: {e}"))
        except Exception as e:
            results.append(("ERROR", f"{test_fn.__name__}: {e}"))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for status, name in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {status}: {name}")

    passed = sum(1 for s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n  {passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)
