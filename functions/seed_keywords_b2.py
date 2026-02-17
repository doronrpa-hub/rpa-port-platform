"""
Block B2: Seed keyword_index with product/material/industry terms.
One-time script. Run with: python -X utf8 seed_keywords_b2.py [--test]

--test: seed only first 50 keywords (test batch)
(no flag): seed all keywords
"""
import sys
import os
from datetime import datetime, timezone

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

try:
    app = firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(r"C:\Users\doron\sa-key.json")
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Curated keyword list ──
# Format: (keyword_en, keyword_he, heading_4digit, description)
# Only clear, unambiguous mappings. Heading = 4-digit HS level.
# Removed: container, drum, bag, tube (ambiguous across chapters)

KEYWORDS = [
    # ── PACKAGING (clear heading) ──
    ("pallet", "משטח", "4415", "wooden pallets and pallet collars"),
    ("wooden crate", "ארגז עץ", "4415", "wooden crates and boxes for transport"),
    ("carton", "קרטון", "4819", "cartons, boxes of paper or paperboard"),
    ("cardboard box", "קופסת קרטון", "4819", "cardboard boxes and cases"),
    ("sack", "שק", "6305", "sacks and bags for packing, of textile"),
    ("glass bottle", "בקבוק זכוכית", "7010", "glass bottles, flasks, jars"),
    ("steel drum", "חבית פלדה", "7310", "tanks, drums, cans of iron or steel"),
    ("steel tank", "מיכל פלדה", "7310", "tanks and vessels of iron or steel"),
    ("aluminum can", "פחית אלומיניום", "7612", "aluminum casks, drums, cans"),
    ("IBC", "מכל ביניים", "7310", "intermediate bulk containers, steel"),
    ("plastic crate", "ארגז פלסטיק", "3923", "plastic boxes, crates, cases for packing"),
    ("plastic bottle", "בקבוק פלסטיק", "3923", "plastic bottles, flasks for packing"),
    ("plastic tray", "מגש פלסטיק", "3923", "plastic trays for packing"),
    ("shrink wrap", "כיווץ", "3920", "plastic shrink film, sheets"),
    ("stretch film", "סרט נמתח", "3920", "self-adhesive stretch film of plastics"),
    ("foam packaging", "קצף אריזה", "3921", "cellular plastic sheets for packaging"),
    ("label", "תווית", "4821", "paper labels of all kinds"),
    ("strapping", "סרט קשירה", "7217", "steel strapping wire"),

    # ── MATERIALS (clear chapter, not ambiguous) ──
    ("stainless steel", "פלדת אל-חלד", "7218", "stainless steel semi-finished products"),
    ("aluminum sheet", "יריעת אלומיניום", "7606", "aluminum plates, sheets"),
    ("aluminum profile", "פרופיל אלומיניום", "7604", "aluminum bars, rods, profiles"),
    ("copper wire", "חוט נחושת", "7408", "copper wire"),
    ("copper pipe", "צינור נחושת", "7411", "copper tubes and pipes"),
    ("zinc", "אבץ", "7901", "unwrought zinc"),
    ("tin", "בדיל", "8001", "unwrought tin"),
    ("lead", "עופרת", "7801", "unwrought lead"),
    ("nickel", "ניקל", "7502", "unwrought nickel"),
    ("brass", "פליז", "7403", "copper-zinc alloys (brass)"),
    ("carbon fiber", "סיבי פחמן", "6815", "carbon fibers and articles thereof"),
    ("rubber sheet", "יריעת גומי", "4008", "vulcanized rubber plates and sheets"),
    ("rubber hose", "צינור גומי", "4009", "tubes and pipes of vulcanized rubber"),
    ("plywood", "דיקט", "4412", "plywood and veneered panels"),
    ("MDF", "אם-די-אף", "4411", "medium density fiberboard"),
    ("chipboard", "סיבית", "4410", "particle board of wood"),
    ("glass sheet", "יריעת זכוכית", "7005", "float glass and polished glass"),
    ("tempered glass", "זכוכית מחוסמת", "7007", "safety glass, tempered"),
    ("ceramic tile", "אריח קרמי", "6908", "glazed ceramic tiles"),
    ("marble", "שיש", "6802", "worked marble and stone"),
    ("granite", "גרניט", "6802", "worked granite"),
    ("concrete block", "בלוק בטון", "6810", "articles of cement or concrete"),

    # ── MECHANICAL COMPONENTS (clear heading) ──
    ("valve", "שסתום", "8481", "taps, cocks, valves for pipes"),
    ("pump", "משאבה", "8413", "pumps for liquids"),
    ("electric motor", "מנוע חשמלי", "8501", "electric motors"),
    ("generator", "גנרטור", "8502", "electric generating sets"),
    ("compressor", "מדחס", "8414", "air or gas compressors"),
    ("fan", "מאוורר", "8414", "fans and blowers"),
    ("bearing", "מיסב", "8482", "ball or roller bearings"),
    ("bolt", "בורג", "7318", "bolts, screws, nuts, washers of iron/steel"),
    ("nut", "אום", "7318", "nuts of iron or steel"),
    ("screw", "הברגה", "7318", "screws of iron or steel"),
    ("washer", "שייבה", "7318", "washers of iron or steel"),
    ("spring", "קפיץ", "7320", "springs of iron or steel"),
    ("gear", "גלגל שיניים", "8483", "gears, gearing, ball screws"),
    ("shaft", "ציר", "8483", "transmission shafts and cranks"),
    ("gasket", "אטם", "8484", "gaskets and joints of metal sheeting"),
    ("seal", "איטום", "8484", "mechanical seals"),
    ("pipe fitting", "אבזר צנרת", "7307", "tube or pipe fittings of iron/steel"),
    ("steel pipe", "צינור פלדה", "7304", "seamless tubes and pipes of steel"),
    ("welded pipe", "צינור מרותך", "7306", "welded tubes and pipes of steel"),
    ("chain", "שרשרת", "7315", "chain and parts thereof of iron/steel"),
    ("wire rope", "כבל פלדה", "7312", "stranded wire and ropes of iron/steel"),
    ("conveyor belt", "סרט מסוע", "4010", "conveyor belts of vulcanized rubber"),
    ("filter", "מסנן", "8421", "centrifuges and filtering machinery"),
    ("nozzle", "זרבובית", "8424", "spray nozzles and similar appliances"),
    ("crane", "מנוף", "8426", "cranes, derricks, hoists"),
    ("forklift", "מלגזה", "8427", "fork-lift trucks"),

    # ── ELECTRICAL COMPONENTS (clear heading) ──
    ("electric cable", "כבל חשמלי", "8544", "insulated wire, cable"),
    ("connector", "מחבר", "8536", "electrical connectors and plugs"),
    ("switch", "מתג", "8536", "electrical switches"),
    ("relay", "ממסר", "8536", "electrical relays"),
    ("transformer", "שנאי", "8504", "electrical transformers"),
    ("capacitor", "קבל", "8532", "electrical capacitors"),
    ("resistor", "נגד", "8533", "electrical resistors"),
    ("circuit breaker", "מפסק זרם", "8536", "circuit breakers"),
    ("battery", "סוללה", "8506", "primary batteries"),
    ("rechargeable battery", "סוללה נטענת", "8507", "electric accumulators"),
    ("LED", "לד", "8541", "light-emitting diodes"),
    ("sensor", "חיישן", "9025", "temperature and pressure sensors"),
    ("thermostat", "תרמוסטט", "9032", "automatic regulating instruments"),
    ("solar panel", "פאנל סולארי", "8541", "photovoltaic cells and panels"),

    # ── CONSUMER GOODS (clear heading) ──
    ("laptop", "מחשב נייד", "8471", "portable digital computers"),
    ("computer", "מחשב", "8471", "automatic data processing machines"),
    ("printer", "מדפסת", "8443", "printing machinery"),
    ("furniture", "רהיט", "9403", "other furniture and parts"),
    ("office chair", "כיסא משרדי", "9401", "seats and chairs"),
    ("mattress", "מזרן", "9404", "mattress supports and mattresses"),
    ("toy", "צעצוע", "9503", "toys, models, puzzles"),
    ("perfume", "בושם", "3303", "perfumes and toilet waters"),
    ("cosmetics", "קוסמטיקה", "3304", "beauty and makeup preparations"),
    ("shampoo", "שמפו", "3305", "preparations for use on hair"),
    ("soap", "סבון", "3401", "soap and organic surface-active products"),
    ("detergent", "חומר ניקוי", "3402", "organic surface-active agents"),
    ("paint", "צבע", "3208", "paints and varnishes in non-aqueous medium"),
    ("adhesive", "דבק", "3506", "prepared glues and adhesives"),
    ("lubricant", "חומר סיכה", "2710", "petroleum oils and lubricants"),
    ("sunscreen", "קרם הגנה", "3304", "sunscreen preparations"),

    # ── TEXTILES (clear heading) ──
    ("woven fabric", "בד ארוג", "5407", "woven fabrics of synthetic filament"),
    ("knitted fabric", "בד סרוג", "6006", "knitted or crocheted fabrics"),
    ("cotton fabric", "בד כותנה", "5208", "woven fabrics of cotton"),
    ("nonwoven", "לא ארוג", "5603", "nonwovens"),
    ("men shirt", "חולצת גברים", "6205", "men's shirts"),
    ("women dress", "שמלה", "6204", "women's dresses"),
    ("men trousers", "מכנסי גברים", "6203", "men's trousers"),
    ("shoes", "נעליים", "6403", "footwear with leather uppers"),
    ("sports shoes", "נעלי ספורט", "6404", "footwear with textile uppers"),
    ("gloves", "כפפות", "6116", "knitted gloves"),
    ("socks", "גרביים", "6115", "hosiery, knitted"),

    # ── FOOD & AGRICULTURE (clear heading) ──
    ("olive oil", "שמן זית", "1509", "olive oil"),
    ("sunflower oil", "שמן חמנייה", "1512", "sunflower-seed oil"),
    ("sugar", "סוכר", "1701", "cane or beet sugar"),
    ("chocolate", "שוקולד", "1806", "chocolate and cocoa preparations"),
    ("coffee", "קפה", "0901", "coffee"),
    ("tea", "תה", "0902", "tea"),
    ("rice", "אורז", "1006", "rice"),
    ("pasta", "פסטה", "1902", "pasta"),
    ("biscuit", "ביסקוויט", "1905", "bread, pastry, biscuits"),
    ("juice", "מיץ", "2009", "fruit and vegetable juices"),
    ("wine", "יין", "2204", "wine of fresh grapes"),
    ("beer", "בירה", "2203", "beer made from malt"),
    ("mineral water", "מים מינרליים", "2201", "waters including mineral"),
    ("animal feed", "מזון בעלי חיים", "2309", "preparations for animal feeding"),
    ("fertilizer", "דשן", "3105", "mineral or chemical fertilizers"),
    ("pesticide", "חומר הדברה", "3808", "insecticides, herbicides"),
    ("seeds", "זרעים", "1209", "seeds for sowing"),

    # ── PHARMA & MEDICAL (clear heading) ──
    ("medicine", "תרופה", "3004", "medicaments in measured doses"),
    ("bandage", "תחבושת", "3005", "wadding, bandages, dressings"),
    ("syringe", "מזרק", "9018", "syringes, needles, catheters"),
    ("surgical instrument", "מכשיר כירורגי", "9018", "instruments for medical use"),
    ("wheelchair", "כיסא גלגלים", "8713", "carriages for disabled persons"),
    ("hearing aid", "מכשיר שמיעה", "9021", "hearing aids"),
    ("vitamins", "ויטמינים", "2936", "provitamins and vitamins"),
    ("supplements", "תוספי תזונה", "2106", "food preparations not elsewhere specified"),

    # ── INDUSTRY TERMS (use-case, clear heading) ──
    ("food grade", "תקן מזון", "3923", "food-grade packaging of plastics"),
    ("hydraulic", "הידראולי", "8412", "hydraulic power engines and motors"),
    ("pneumatic", "פנאומטי", "8412", "pneumatic power engines"),
    ("welding", "ריתוך", "8515", "electric welding machines"),
    ("cutting tool", "כלי חיתוך", "8207", "interchangeable tools for machine tools"),
    ("drill bit", "מקדח", "8207", "drilling tools"),
    ("grinding wheel", "אבן השחזה", "6804", "millstones and grinding wheels"),
    ("hand tool", "כלי עבודה", "8205", "hand tools not elsewhere specified"),
    ("measuring instrument", "מכשיר מדידה", "9031", "measuring or checking instruments"),

    # ── JEWELRY & WATCHES (clear heading) ──
    ("gold jewelry", "תכשיט זהב", "7113", "articles of jewelry of precious metal"),
    ("silver jewelry", "תכשיט כסף", "7113", "articles of jewelry of precious metal"),
    ("watch", "שעון יד", "9101", "wrist-watches with case of precious metal"),
    ("clock", "שעון קיר", "9105", "other clocks"),

    # ── VEHICLES & PARTS (clear heading) ──
    ("tire", "צמיג", "4011", "new pneumatic tires of rubber"),
    ("brake pad", "רפידת בלם", "6813", "brake linings and pads"),
    ("spark plug", "מצת", "8511", "spark plugs"),
    ("car battery", "מצבר רכב", "8507", "lead-acid accumulators"),
    ("headlight", "פנס ראשי", "8512", "electrical lighting for vehicles"),
    ("windshield", "שמשה קדמית", "7007", "safety glass for vehicles"),
    ("shock absorber", "בולם זעזועים", "8708", "parts and accessories of motor vehicles"),
    ("air filter", "מסנן אוויר", "8421", "filtering machinery"),
    ("oil filter", "מסנן שמן", "8421", "filtering machinery"),
    ("radiator", "רדיאטור", "8708", "parts and accessories of motor vehicles"),
    ("exhaust pipe", "צינור פליטה", "8708", "exhaust pipes for motor vehicles"),

    # ── BUILDING & CONSTRUCTION (clear heading) ──
    ("steel beam", "קורת פלדה", "7216", "angles, shapes, sections of iron/steel"),
    ("steel rebar", "ברזל בניין", "7214", "bars and rods of iron/steel"),
    ("steel wire", "חוט פלדה", "7217", "wire of iron or non-alloy steel"),
    ("roof tile", "רעף", "6905", "roofing tiles of ceramics"),
    ("sanitary ware", "כלים סניטריים", "6910", "ceramic sinks, baths, toilets"),
    ("faucet", "ברז", "8481", "taps and cocks for sanitary ware"),
    ("door lock", "מנעול", "8301", "padlocks and locks of base metal"),
    ("hinge", "ציר דלת", "8302", "hinges and mountings of base metal"),
    ("insulation", "בידוד", "6806", "mineral wools and thermal insulation"),
    ("PVC pipe", "צינור PVC", "3917", "tubes, pipes of plastics"),
    ("electric wire", "חוט חשמל", "8544", "insulated wire and cable"),
    ("light fixture", "גוף תאורה", "9405", "lamps and lighting fittings"),
    ("air conditioner", "מזגן", "8415", "air conditioning machines"),
    ("water heater", "דוד חימום", "8419", "water heaters, non-electric"),
    ("elevator", "מעלית", "8428", "lifting and handling machinery"),
]

# ─────────────────────────────────────────────────────────
NOW = datetime.now(timezone.utc).isoformat()


def safe_doc_id(text):
    """Create Firestore-safe document ID from keyword."""
    return text.lower().strip().replace(" ", "_").replace("/", "_")[:100]


def seed_batch(keywords, dry_run=False):
    """Seed a batch of keywords into keyword_index."""
    batch = db.batch()
    count = 0
    skipped = 0

    for kw_en, kw_he, heading, desc in keywords:
        # Create entries for both English and Hebrew
        for kw in [kw_en, kw_he]:
            doc_id = safe_doc_id(kw)
            ref = db.collection("keyword_index").document(doc_id)

            # Check if exists
            existing = ref.get()
            if existing.exists:
                d = existing.to_dict()
                codes = d.get("codes", [])
                # Check if this heading is already mapped
                has_heading = any(
                    c.get("hs_code", "").startswith(heading) for c in codes
                )
                if has_heading:
                    skipped += 1
                    continue
                # Append to existing
                codes.append({
                    "hs_code": heading,
                    "weight": 3,
                    "source": "b2_seed",
                    "description": desc,
                })
                if not dry_run:
                    batch.update(ref, {
                        "codes": codes,
                        "count": len(codes),
                        "updated_at": NOW,
                    })
            else:
                # New entry
                doc = {
                    "keyword": kw,
                    "keyword_en": kw_en,
                    "keyword_he": kw_he,
                    "codes": [{
                        "hs_code": heading,
                        "weight": 3,
                        "source": "b2_seed",
                        "description": desc,
                    }],
                    "count": 1,
                    "built_at": NOW,
                    "enriched": False,
                }
                if not dry_run:
                    batch.set(ref, doc)

            count += 1
            # Firestore batch limit is 500
            if count % 400 == 0 and not dry_run:
                batch.commit()
                batch = db.batch()
                print(f"  Committed batch ({count} so far)")

    if not dry_run and count % 400 != 0:
        batch.commit()

    return count, skipped


if __name__ == "__main__":
    test_mode = "--test" in sys.argv

    if test_mode:
        subset = KEYWORDS[:25]  # 25 entries = 50 keywords (en+he)
        print(f"TEST MODE: Seeding {len(subset)} entries ({len(subset)*2} keywords)")
    else:
        subset = KEYWORDS
        print(f"FULL MODE: Seeding {len(subset)} entries ({len(subset)*2} keywords)")

    count, skipped = seed_batch(subset)
    print(f"\nDone: {count} keywords written, {skipped} skipped (already had heading)")
    print(f"Total entries in list: {len(KEYWORDS)} ({len(KEYWORDS)*2} keywords incl. en+he)")
