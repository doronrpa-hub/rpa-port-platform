"""
Live elimination engine test — runs against production Firestore.

Tests 3 product scenarios with manually-crafted candidates to verify
that the deterministic elimination pipeline works correctly with real data.

Run: cd functions && python -X utf8 test_elimination_live.py

No AI keys needed — D6/D7 gracefully degrade to no-op.
"""
import sys
import os

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"
sys.path.insert(0, os.path.dirname(__file__))

import firebase_admin
from firebase_admin import credentials, firestore

try:
    app = firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(r"C:\Users\doron\sa-key.json")
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

from lib.elimination_engine import eliminate, make_product_info

# ════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════

def make_candidate(hs_code, confidence=50, description="", description_en="", source="test"):
    """Build a minimal HSCandidate dict."""
    return {
        "hs_code": hs_code,
        "section": "",
        "chapter": "",
        "heading": "",
        "subheading": "",
        "confidence": confidence,
        "source": source,
        "description": description,
        "description_en": description_en,
        "duty_rate": "",
        "alive": True,
        "elimination_reason": "",
        "eliminated_at_level": "",
    }


def print_result(title, result, expected_chapter=None):
    """Pretty-print an elimination result."""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  TEST: {title}")
    print(sep)

    print(f"\n  Input:     {result['input_count']} candidates")
    print(f"  Survivors: {result['survivor_count']}")
    print(f"  Steps:     {len(result['steps'])}")
    print(f"  Sections:  {sorted(result.get('sections_checked', []))}")
    print(f"  Chapters:  {sorted(result.get('chapters_checked', []))}")
    print(f"  Needs AI:  {result['needs_ai']}")
    print(f"  Needs Q:   {result['needs_questions']}")

    # ── Steps trace ──
    print(f"\n  {'─' * 66}")
    print(f"  ELIMINATION TRACE ({len(result['steps'])} steps)")
    print(f"  {'─' * 66}")
    for i, step in enumerate(result['steps'], 1):
        action_icon = {"eliminate": "✘", "keep": "✓", "boost": "⬆"}.get(step['action'], "?")
        print(f"  {i:2d}. [{step['level']:<18s}] {action_icon} {step['rule_type']}")
        print(f"      {step['candidates_before']}→{step['candidates_after']} candidates"
              f"  | Eliminated: {step['eliminated_codes'] or '—'}")
        if step.get('reasoning'):
            reason = step['reasoning'][:120]
            print(f"      {reason}")
        print()

    # ── Survivors ──
    print(f"  {'─' * 66}")
    print(f"  SURVIVORS ({result['survivor_count']})")
    print(f"  {'─' * 66}")
    for s in result['survivors']:
        ch = s.get('chapter', '?')
        mark = " ◄ EXPECTED" if expected_chapter and ch == expected_chapter else ""
        desc = s.get('description', '') or s.get('description_en', '')
        print(f"  ✓ {s['hs_code']:<14s} ch.{ch:<4s} conf={s['confidence']:3d}  "
              f"{desc[:60]}{mark}")

    # ── Eliminated ──
    if result['eliminated']:
        print(f"\n  {'─' * 66}")
        print(f"  ELIMINATED ({len(result['eliminated'])})")
        print(f"  {'─' * 66}")
        for e in result['eliminated']:
            desc = e.get('description', '') or e.get('description_en', '')
            print(f"  ✘ {e['hs_code']:<14s} ch.{e.get('chapter','?'):<4s} "
                  f"@ {e.get('eliminated_at_level','?'):<18s} "
                  f"{e.get('elimination_reason','')[:50]}")

    # ── Challenges (D7) ──
    if result.get('challenges'):
        print(f"\n  {'─' * 66}")
        print(f"  DEVIL'S ADVOCATE ({len(result['challenges'])} challenges)")
        print(f"  {'─' * 66}")
        for ch in result['challenges']:
            print(f"  ⚡ {ch}")

    # ── Verdict ──
    survivor_chapters = {s.get('chapter') for s in result['survivors']}
    if expected_chapter:
        if expected_chapter in survivor_chapters:
            print(f"\n  ✅ PASS — chapter {expected_chapter} survived")
        else:
            print(f"\n  ❌ FAIL — chapter {expected_chapter} was eliminated!")
            print(f"     Survivor chapters: {sorted(survivor_chapters)}")
    print()


# ════════════════════════════════════════════════════════
#  TEST 1: Steel storage boxes → chapter 73
# ════════════════════════════════════════════════════════

def test_steel_storage_boxes():
    product = make_product_info({
        "description": "Steel storage boxes, open top, foldable, for industrial use",
        "description_he": "קופסאות אחסון מפלדה, פתוחות מלמעלה, מתקפלות, לשימוש תעשייתי",
        "material": "steel",
        "form": "box, foldable, open top",
        "use": "industrial storage",
        "origin_country": "China",
    })

    candidates = [
        make_candidate("7326.9000", 60,
                       description="מוצרים אחרים של ברזל או פלדה",
                       description_en="Other articles of iron or steel"),
        make_candidate("8310.0000", 40,
                       description="שלטים, לוחיות שם, לוחיות כתובת ודומיהם, ספרות, אותיות וסמלים אחרים, של מתכת פשוטה",
                       description_en="Sign-plates, name-plates, address-plates and similar of base metal"),
        make_candidate("7310.1000", 45,
                       description="מיכלים, חביות, פחים, קופסאות וכלי קיבול דומים",
                       description_en="Tanks, casks, drums, cans, boxes and similar containers"),
        make_candidate("9403.2000", 30,
                       description="רהיטים אחרים של מתכת",
                       description_en="Other metal furniture"),
        make_candidate("4415.1000", 20,
                       description="ארגזים, תיבות, כלובים, חביות וכלי קיבול דומים, של עץ",
                       description_en="Cases, boxes, crates, drums of wood"),
    ]

    result = eliminate(db, product, candidates)
    print_result("Steel storage boxes → expect ch.73 (not ch.83)", result, expected_chapter="73")
    return result


# ════════════════════════════════════════════════════════
#  TEST 2: Rubber gloves for medical use → chapter 40
# ════════════════════════════════════════════════════════

def test_rubber_gloves_medical():
    product = make_product_info({
        "description": "Disposable rubber examination gloves for medical use, non-sterile, latex",
        "description_he": "כפפות בדיקה חד פעמיות מגומי לשימוש רפואי, לא סטריליות, לטקס",
        "material": "rubber, latex, natural rubber",
        "form": "gloves, disposable",
        "use": "medical examination",
        "origin_country": "Malaysia",
    })

    candidates = [
        make_candidate("4015.1900", 65,
                       description="כפפות, כפפות חלקיות ומוצרי יד, מגומי וולקני",
                       description_en="Gloves, mittens and mitts, of vulcanized rubber"),
        make_candidate("6116.1000", 40,
                       description="כפפות, כפפות חלקיות ומוצרי יד, סרוגים",
                       description_en="Gloves, mittens and mitts, knitted or crocheted"),
        make_candidate("3926.2000", 35,
                       description="פריטי לבוש ואביזריהם, מפלסטיק",
                       description_en="Articles of apparel and clothing accessories, of plastics"),
        make_candidate("9018.3900", 30,
                       description="מכשירים ומתקנים לרפואה, לכירורגיה",
                       description_en="Instruments and appliances used in medical, surgical"),
        make_candidate("6216.0000", 25,
                       description="כפפות, כפפות חלקיות ומוצרי יד",
                       description_en="Gloves, mittens and mitts"),
    ]

    result = eliminate(db, product, candidates)
    print_result("Rubber gloves (medical) → expect ch.40 (rubber)", result, expected_chapter="40")
    return result


# ════════════════════════════════════════════════════════
#  TEST 3: Lithium-ion battery for EV → chapter 85
# ════════════════════════════════════════════════════════

def test_lithium_battery_ev():
    product = make_product_info({
        "description": "Lithium-ion battery pack for electric vehicle, 400V, 75kWh capacity",
        "description_he": "מארז סוללות ליתיום-יון לרכב חשמלי, 400 וולט, קיבולת 75 קילוואט שעה",
        "material": "lithium-ion, lithium",
        "form": "battery pack, module",
        "use": "electric vehicle power, automotive",
        "origin_country": "South Korea",
    })

    candidates = [
        make_candidate("8507.6000", 70,
                       description="מצברים חשמליים ליתיום-יון",
                       description_en="Lithium-ion electric accumulators"),
        make_candidate("8703.8000", 40,
                       description="כלי רכב מנועיים אחרים, חשמליים",
                       description_en="Other motor vehicles, electric"),
        make_candidate("8501.3200", 30,
                       description="מנועים חשמליים ומחוללים",
                       description_en="Electric motors and generators"),
        make_candidate("8541.4000", 25,
                       description="התקנים מוליכים למחצה רגישים לאור",
                       description_en="Photosensitive semiconductor devices"),
        make_candidate("8708.9900", 35,
                       description="חלקים ואביזרים לכלי רכב מנועיים",
                       description_en="Parts and accessories of motor vehicles"),
    ]

    result = eliminate(db, product, candidates)
    print_result("Li-ion battery (EV) → expect ch.85 (electrical)", result, expected_chapter="85")
    return result


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🔬 Elimination Engine — Live Firestore Test")
    print("=" * 70)
    print(f"  Firestore project: rpa-port-customs")
    print(f"  AI keys: None (deterministic only — D6/D7 will no-op)")
    print()

    results = {}
    results['steel'] = test_steel_storage_boxes()
    results['gloves'] = test_rubber_gloves_medical()
    results['battery'] = test_lithium_battery_ev()

    # ── Summary ──
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for name, r in results.items():
        surv_codes = [s['hs_code'] for s in r['survivors']]
        surv_chs = sorted({s.get('chapter', '?') for s in r['survivors']})
        print(f"  {name:<10s}: {r['input_count']}→{r['survivor_count']} survivors  "
              f"chs={surv_chs}  codes={surv_codes}")

    # Check specific expectations
    all_pass = True

    # Test 1: ch.73 should survive, ch.83 should not
    steel_survivor_chs = {s.get('chapter') for s in results['steel']['survivors']}
    if '73' not in steel_survivor_chs:
        print("\n  ❌ FAIL: Steel boxes — ch.73 eliminated")
        all_pass = False

    # Test 2: ch.40 should survive
    gloves_survivor_chs = {s.get('chapter') for s in results['gloves']['survivors']}
    if '40' not in gloves_survivor_chs:
        print("\n  ❌ FAIL: Rubber gloves — ch.40 eliminated")
        all_pass = False

    # Test 3: ch.85 should survive
    battery_survivor_chs = {s.get('chapter') for s in results['battery']['survivors']}
    if '85' not in battery_survivor_chs:
        print("\n  ❌ FAIL: Li-ion battery — ch.85 eliminated")
        all_pass = False

    if all_pass:
        print("\n  ✅ ALL TESTS PASSED — correct chapters survived in all 3 tests")
    else:
        print("\n  ⚠️  SOME TESTS FAILED — see above")

    print()
