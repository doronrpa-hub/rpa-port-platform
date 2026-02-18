"""
Session 47: Seed BELSHINA learning data — teach the system from the BALKI test case.

Seeds 3 collections:
  1. learned_classifications — 13 tire models from JSC BELSHINA price offer
  2. learned_identifier_patterns — belshina.by domain → seller pattern
  3. learned_document_types — price offer / proforma detection phrases

Run: python -X utf8 seed_belshina_learning.py
"""
import sys
import os
from datetime import datetime, timezone

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ──
SA_PATHS = [
    r"C:\Users\User\Downloads\rpa-port-customs-firebase-adminsdk-fbsvc-da5df22d32.json",
    r"C:\Users\doron\sa-key.json",
]

try:
    app = firebase_admin.get_app()
except ValueError:
    sa_path = next((p for p in SA_PATHS if os.path.exists(p)), None)
    if not sa_path:
        print("ERROR: No service account key found")
        sys.exit(1)
    cred = credentials.Certificate(sa_path)
    app = firebase_admin.initialize_app(cred)

db = firestore.client()
now = datetime.now(timezone.utc)

# ── Israeli HS format helper ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from librarian import get_israeli_hs_format

# ═══════════════════════════════════════════════════════════════
#  1. LEARNED CLASSIFICATIONS — BELSHINA tire models
# ═══════════════════════════════════════════════════════════════
# HS 4011.10 — New pneumatic tyres, of rubber, for motor cars
# Full Israeli format computed by get_israeli_hs_format()

BELSHINA_PRODUCTS = [
    # From BALKI price offer — JSC BELSHINA tire models
    {"product": "Belshina Bel-100 155/70R13", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-119 175/70R13", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-171 185/60R14", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-188 195/65R15", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-205 205/55R16", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-207 215/65R16", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-261 175/65R14", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-220 185/65R15", "hs_raw": "4011100000"},
    {"product": "Belshina Bel-247 205/65R15", "hs_raw": "4011100000"},
    {"product": "Belshina ArtMotion 195/65R15", "hs_raw": "4011100000"},
    {"product": "Belshina ArtMotion Snow 185/65R15", "hs_raw": "4011100000"},
    # Truck tyres — HS 4011.20
    {"product": "Belshina Bel-138M 260-508R (9.00R20)", "hs_raw": "4011200000"},
    {"product": "Belshina Bel-146 315/80R22.5", "hs_raw": "4011200000"},
]

print("=" * 60)
print("Seeding learned_classifications — BELSHINA tires")
print("=" * 60)

import hashlib

def make_id(key):
    return hashlib.md5(key.encode()).hexdigest()[:20]

seeded_cls = 0
for item in BELSHINA_PRODUCTS:
    product = item["product"]
    hs_formatted = get_israeli_hs_format(item["hs_raw"])
    product_lower = product.strip().lower()
    doc_id = make_id(f"cls_{product_lower}_{hs_formatted}")

    chapter = item["hs_raw"][:2]  # "40" for rubber
    keywords = [w for w in product_lower.split() if len(w) > 2]

    doc_ref = db.collection("learned_classifications").document(doc_id)
    doc_ref.set({
        "product": product.strip(),
        "product_lower": product_lower,
        "hs_code": hs_formatted,
        "chapter": chapter,
        "keywords": keywords[:50],
        "method": "manual",
        "source": "user",
        "confidence": 1.0,
        "learned_at": now,
        "times_used": 0,
        "tracking_code": "RCB-20260218-BALKI",
        "seller": "JSC BELSHINA",
        "origin_country": "Belarus",
    }, merge=True)
    seeded_cls += 1
    print(f"  ✅ {product} → {hs_formatted}")

print(f"\n  Total: {seeded_cls} classifications seeded\n")

# ═══════════════════════════════════════════════════════════════
#  2. LEARNED IDENTIFIER PATTERNS — belshina.by domain
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("Seeding learned_identifier_patterns — belshina.by")
print("=" * 60)

patterns = [
    {
        "pattern_id": "belshina_seller_domain",
        "field": "seller_domain",
        "regex": r"belshina\.by$",
        "source": "manual",
        "client_name": "JSC BELSHINA",
        "examples": ["belshina@belshina.by", "sales@belshina.by"],
        "hit_count": 1,
        "last_seen": now,
        "seller_website": "belshina.by",
        "seller_country": "Belarus",
        "product_category": "pneumatic tyres (chapter 40)",
    },
    {
        "pattern_id": "belshina_email",
        "field": "sender_email",
        "regex": r"@belshina\.by$",
        "source": "manual",
        "client_name": "JSC BELSHINA",
        "examples": ["belshina@belshina.by"],
        "hit_count": 1,
        "last_seen": now,
        "seller_website": "belshina.by",
    },
]

for pat in patterns:
    doc_id = pat["pattern_id"]
    db.collection("learned_identifier_patterns").document(doc_id).set(pat, merge=True)
    print(f"  ✅ {doc_id}: {pat['regex']}")

print(f"\n  Total: {len(patterns)} patterns seeded\n")

# ═══════════════════════════════════════════════════════════════
#  3. LEARNED DOCUMENT TYPES — price offer detection
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("Seeding learned_document_types — price offer phrases")
print("=" * 60)

doc_types = [
    {
        "doc_type": "price_offer",
        "display_name_he": "הצעת מחיר",
        "display_name_en": "Price Offer / Quotation",
        "detection_phrases_en": [
            "price offer", "price list", "quotation", "quote",
            "proforma", "pro forma", "pro-forma",
            "price proposal", "commercial offer", "offer letter",
        ],
        "detection_phrases_he": [
            "הצעת מחיר", "רשימת מחירים", "הצעה מסחרית",
            "חשבון פרופורמה", "פרופורמה",
        ],
        "treat_as": "invoice",  # Extract items exactly like an invoice
        "extraction_notes": "Number fields map to invoice_number. All line items should be extracted.",
        "examples": [
            "BALKI price offer from JSC BELSHINA",
        ],
        "seeded_at": now,
    },
    {
        "doc_type": "proforma_invoice",
        "display_name_he": "חשבון פרופורמה",
        "display_name_en": "Proforma Invoice",
        "detection_phrases_en": [
            "proforma invoice", "pro forma invoice", "pro-forma invoice",
            "PI No.", "proforma no.",
        ],
        "detection_phrases_he": [
            "חשבון פרופורמה", "פרופורמה",
        ],
        "treat_as": "invoice",
        "extraction_notes": "Identical to commercial invoice. Extract all line items.",
        "examples": [],
        "seeded_at": now,
    },
]

for dt in doc_types:
    doc_id = dt["doc_type"]
    db.collection("learned_document_types").document(doc_id).set(dt, merge=True)
    print(f"  ✅ {doc_id}: {dt['display_name_en']}")

# Metadata
db.collection("learned_document_types").document("_metadata").set({
    "total_types": len(doc_types),
    "seeded_at": now,
    "source": "Session 47 — BALKI/BELSHINA case",
}, merge=True)

print(f"\n  Total: {len(doc_types)} document types seeded\n")

print("=" * 60)
print("BELSHINA learning data seeding complete!")
print("=" * 60)
