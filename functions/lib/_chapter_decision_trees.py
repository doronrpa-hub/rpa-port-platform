"""Chapter Decision Trees — Deterministic chapter routing for customs classification.

Each chapter that has a decision tree gets a `_decide_chapter_XX(product)` function.
The public entry point is `decide_chapter(product)` which detects the relevant
chapter and dispatches to the right tree.

Session 98 — proof of concept with Chapter 03 (Fish, Crustaceans, Molluscs).

Product dict expected keys (from Layer 0 / _identify_items_with_ai):
    name, physical, essence, function,
    transformation_stage, processing_state, dominant_material_pct
"""

import re

# ============================================================================
# CHAPTER 03: Fish, crustaceans, molluscs, other aquatic invertebrates
# ============================================================================

# --- Creature type detection (bilingual) ---

_FISH_WORDS = re.compile(
    r'(?:דג|דגים|סלמון|טונה|נילוס|דניס|בורי|קוד|בקלה|סרדין|מקרל|אנשובי|'
    r'קרפיון|הליבוט|סול|טראוט|הרינג|פורל|אמנון|לוקוס|מוסר|'
    r'salmon|tuna|cod|tilapia|trout|bass|mackerel|sardine|herring|anchovy|'
    r'carp|haddock|halibut|sole|catfish|perch|pike|swordfish|'
    r'fish|fillet|פילה|נתח)',
    re.IGNORECASE
)

_CRUSTACEAN_WORDS = re.compile(
    r'(?:חסילון|שרימפס|שריימפ|סרטן|לובסטר|סרטנים|'
    r'langoustine|crayfish|crawfish|shrimp|prawn|lobster|crab|'
    r'crustacean|norway.lobster|scampi)',
    re.IGNORECASE
)

_MOLLUSC_WORDS = re.compile(
    r'(?:קלמרי|תמנון|צדפה|חילזון\s*ים|אבלון|סקאלופ|'
    r'squid|octopus|mussel|oyster|clam|scallop|snail|abalone|'
    r'cuttlefish|mollusc|mollusk|calamari)',
    re.IGNORECASE
)

_OTHER_INVERT_WORDS = re.compile(
    r'(?:קיפוד\s*ים|מדוזה|sea\s*urchin|sea\s*cucumber|jellyfish|'
    r'aquatic\s*invertebrate)',
    re.IGNORECASE
)

_FLOUR_MEAL_WORDS = re.compile(
    r'(?:קמח\s*דגים|fish\s*flour|fish\s*meal|fish\s*pellet|'
    r'crustacean\s*flour|crustacean\s*meal)',
    re.IGNORECASE
)

# --- Crustacean species sub-routing ---

_LOBSTER_LANGOUSTINE = re.compile(
    r'(?:חסילון|לובסטר|langoustine|lobster|rock\s*lobster|'
    r'norway\s*lobster|scampi|crayfish|crawfish)',
    re.IGNORECASE
)

_SHRIMP_PRAWN = re.compile(
    r'(?:שרימפס|שריימפ|חיסרון|shrimp|prawn)',
    re.IGNORECASE
)

_CRAB = re.compile(
    r'(?:סרטן|סרטנים|crab)',
    re.IGNORECASE
)

# --- Processing state detection from product text ---

_COMPOUND_SIGNALS = re.compile(
    r'(?:מצופה|פירורי\s*לחם|ממולא|ברוטב|במרינדה|מתובל|'
    r'breaded|coated|battered|stuffed|in\s*sauce|marinated|seasoned|'
    r'tempura|panko|crumb)',
    re.IGNORECASE
)

_FILLET_SIGNALS = re.compile(
    r'(?:פילה|נתח|fillet|steak|portion|loin|chunk)',
    re.IGNORECASE
)

_PEELED_SIGNALS = re.compile(
    r'(?:מקולף|קלוף|peeled|shelled|shell.?off|meat\s*only|tail\s*meat)',
    re.IGNORECASE
)


def _detect_creature_type(text):
    """Detect aquatic creature type from combined product text.

    Returns: 'fish', 'crustacean', 'mollusc', 'other_invertebrate',
             'flour_meal', or 'unknown'.
    """
    if _FLOUR_MEAL_WORDS.search(text):
        return "flour_meal"
    if _CRUSTACEAN_WORDS.search(text):
        return "crustacean"
    if _MOLLUSC_WORDS.search(text):
        return "mollusc"
    if _OTHER_INVERT_WORDS.search(text):
        return "other_invertebrate"
    if _FISH_WORDS.search(text):
        return "fish"
    return "unknown"


def _detect_crustacean_species(text):
    """Detect crustacean species for 03.06 sub-routing.

    Returns: 'lobster_langoustine', 'shrimp_prawn', 'crab', or 'other'.
    """
    if _LOBSTER_LANGOUSTINE.search(text):
        return "lobster_langoustine"
    if _SHRIMP_PRAWN.search(text):
        return "shrimp_prawn"
    if _CRAB.search(text):
        return "crab"
    return "other"


def _get_processing_state(product):
    """Get processing state from product, with text-based override.

    The AI-assigned processing_state is primary, but if the product name
    contains compound signals (breaded, sauced), override to 'compound'.
    """
    text = _product_text(product)
    # Compound signals override everything — breaded fish is NOT just "frozen"
    if _COMPOUND_SIGNALS.search(text):
        return "compound"
    return (product.get("processing_state") or "").strip().lower()


def _product_text(product):
    """Combine all text fields for regex matching."""
    parts = [
        product.get("name", ""),
        product.get("essence", ""),
        product.get("physical", ""),
        product.get("function", ""),
    ]
    # Handle physical as dict (from AI) or string (from fallback)
    phys = product.get("physical", "")
    if isinstance(phys, dict):
        parts.append(phys.get("material", ""))
        parts.append(phys.get("form", ""))
    return " ".join(str(p) for p in parts)


def _is_fillet(product):
    """Check if product is a fish fillet/steak/portion (not whole)."""
    return bool(_FILLET_SIGNALS.search(_product_text(product)))


def _is_peeled(product):
    """Check if crustacean is peeled/shelled."""
    return bool(_PEELED_SIGNALS.search(_product_text(product)))


# ============================================================================
# CHAPTER 03 DECISION TREE
# ============================================================================

def _decide_chapter_03(product):
    """Chapter 03 decision tree: Fish, crustaceans, molluscs, aquatic invertebrates.

    Returns:
        {
            "chapter": 3,
            "candidates": [{heading, subheading_hint, confidence, reasoning, rule_applied}],
            "redirect": None or {"chapter": int, "reason": str, "rule_applied": str},
            "questions_needed": [],
        }
    """
    text = _product_text(product)
    state = _get_processing_state(product)
    creature = _detect_creature_type(text)

    result = {
        "chapter": 3,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # ── STEP 0: CHAPTER GATE — Should this be in Chapter 03 at all? ──

    # Gate 0a: Compound (breaded/sauced/marinated) → ALWAYS redirect Ch.16
    if state == "compound":
        result["redirect"] = {
            "chapter": 16,
            "reason": (
                f"processing_state='compound' — product is prepared with added "
                f"ingredients (breaded/sauced/marinated/coated). Chapter 03 Note "
                f"excludes prepared or preserved products beyond the states listed "
                f"(live/fresh/chilled/frozen/dried/salted/smoked/cooked-in-shell). "
                f"→ Chapter 16 (preparations of fish/crustaceans)."
            ),
            "rule_applied": "Chapter 03 exclusion note + GIR 1",
        }
        return result

    # Gate 0b: Preserved (canned, vacuum-packed) → redirect Ch.16
    # UNLESS the preservation is just salting/brining/drying/smoking (those stay Ch.03)
    if state == "preserved":
        result["redirect"] = {
            "chapter": 16,
            "reason": (
                "processing_state='preserved' — canned/vacuum-packed/chemically "
                "preserved beyond Chapter 03 allowed states. "
                "→ Chapter 16 (preparations of fish/crustaceans)."
            ),
            "rule_applied": "Chapter 03 exclusion note + GIR 1",
        }
        return result

    # Gate 0c: Cooked non-crustacean → redirect Ch.16
    # Only crustaceans cooked IN SHELL stay in 03.06
    if state == "cooked" and creature != "crustacean":
        result["redirect"] = {
            "chapter": 16,
            "reason": (
                f"processing_state='cooked' for {creature}. Only crustaceans "
                f"cooked in shell stay in Chapter 03 (heading 03.06). "
                f"Cooked fish/molluscs → Chapter 16."
            ),
            "rule_applied": "Chapter 03 heading 03.06 note — cooked in shell only for crustaceans",
        }
        return result

    # Gate 0d: Cooked crustacean — needs clarification: in shell?
    if state == "cooked" and creature == "crustacean":
        # If text says "in shell" or "בקליפה", keep in 03.06
        in_shell = bool(re.search(r'(?:בקליפה|in\s*shell|shell.?on)', text, re.IGNORECASE))
        if not in_shell:
            result["questions_needed"].append(
                "Was the crustacean cooked in its shell (בקליפה)? "
                "If yes → 03.06. If peeled after cooking → possibly Chapter 16."
            )
            # Still provide 03.06 as tentative candidate
            result["candidates"].append({
                "heading": "03.06",
                "subheading_hint": None,
                "confidence": 0.60,
                "reasoning": (
                    f"Cooked crustacean — stays in 03.06 IF cooked in shell. "
                    f"Clarification needed."
                ),
                "rule_applied": "Chapter 03 heading 03.06 — cooked in shell provision",
            })
            return result
        # If in shell confirmed, fall through to Step 3 (crustacean routing)

    # ── STEP 1: CREATURE TYPE ROUTING ──

    if creature == "fish":
        return _route_fish(product, state, result)
    elif creature == "crustacean":
        return _route_crustacean(product, state, result)
    elif creature == "mollusc":
        result["candidates"].append({
            "heading": "03.07",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": f"Mollusc detected. State: {state}. → 03.07.",
            "rule_applied": "GIR 1 — heading 03.07 'Molluscs'",
        })
        return result
    elif creature == "other_invertebrate":
        result["candidates"].append({
            "heading": "03.08",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": f"Aquatic invertebrate (not crustacean/mollusc). → 03.08.",
            "rule_applied": "GIR 1 — heading 03.08",
        })
        return result
    elif creature == "flour_meal":
        result["candidates"].append({
            "heading": "03.09",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Fish/crustacean flour, meal, or pellets. → 03.09.",
            "rule_applied": "GIR 1 — heading 03.09",
        })
        return result
    else:
        # Unknown creature — provide all possible headings
        for h in ["03.01", "03.02", "03.03", "03.04", "03.05",
                   "03.06", "03.07", "03.08", "03.09"]:
            result["candidates"].append({
                "heading": h,
                "subheading_hint": None,
                "confidence": 0.20,
                "reasoning": "Unknown aquatic product type.",
                "rule_applied": "GIR 1",
            })
        result["questions_needed"].append(
            "What type of aquatic animal/product is this? "
            "(fish, crustacean, mollusc, other invertebrate, flour/meal)"
        )
        return result


def _route_fish(product, state, result):
    """Route fish products to headings 03.01-03.05.

    Key decision: fillet → 03.04 regardless of state.
    Then: live → 03.01, fresh/chilled → 03.02, frozen → 03.03,
          dried/salted/smoked → 03.05.
    """
    is_fil = _is_fillet(product)

    # 03.01: Live fish
    if state == "live":
        result["candidates"].append({
            "heading": "03.01",
            "subheading_hint": None,
            "confidence": 0.95,
            "reasoning": "Live fish → 03.01.",
            "rule_applied": "GIR 1 — heading 03.01 'Live fish'",
        })
        return result

    # 03.04: Fish fillets (fresh, chilled, or frozen)
    if is_fil:
        sub = None
        conf = 0.90
        if state in ("fresh", "chilled"):
            reasoning = "Fish fillet, fresh/chilled → 03.04 (fresh/chilled fillets)."
        elif state == "frozen":
            reasoning = "Fish fillet, frozen → 03.04 (frozen fillets)."
        else:
            reasoning = f"Fish fillet, state={state} → 03.04."
            conf = 0.80
        result["candidates"].append({
            "heading": "03.04",
            "subheading_hint": sub,
            "confidence": conf,
            "reasoning": reasoning,
            "rule_applied": "GIR 1 — heading 03.04 'Fish fillets and other fish meat'",
        })
        return result

    # 03.05: Dried, salted, smoked fish
    if state in ("dried", "salted", "smoked"):
        result["candidates"].append({
            "heading": "03.05",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Fish, {state} → 03.05.",
            "rule_applied": "GIR 1 — heading 03.05 'Fish, dried, salted, smoked'",
        })
        return result

    # 03.02: Fresh or chilled fish (whole, not fillet)
    if state in ("fresh", "chilled"):
        result["candidates"].append({
            "heading": "03.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Whole fish, {state} → 03.02.",
            "rule_applied": "GIR 1 — heading 03.02 'Fish, fresh or chilled'",
        })
        return result

    # 03.03: Frozen fish (whole, not fillet)
    if state == "frozen":
        result["candidates"].append({
            "heading": "03.03",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Whole fish, frozen → 03.03.",
            "rule_applied": "GIR 1 — heading 03.03 'Frozen fish'",
        })
        return result

    # Unknown state — provide candidates with question
    result["candidates"].extend([
        {"heading": "03.02", "subheading_hint": None, "confidence": 0.40,
         "reasoning": "Fish — state unknown, could be fresh/chilled.",
         "rule_applied": "GIR 1"},
        {"heading": "03.03", "subheading_hint": None, "confidence": 0.40,
         "reasoning": "Fish — state unknown, could be frozen.",
         "rule_applied": "GIR 1"},
        {"heading": "03.05", "subheading_hint": None, "confidence": 0.30,
         "reasoning": "Fish — state unknown, could be dried/salted/smoked.",
         "rule_applied": "GIR 1"},
    ])
    result["questions_needed"].append(
        "What is the preservation state of the fish? "
        "(fresh/chilled/frozen/dried/salted/smoked)"
    )
    return result


def _route_crustacean(product, state, result):
    """Route crustacean products within heading 03.06.

    Sub-routing depends on species (lobster/shrimp/crab/other) and state.
    """
    text = _product_text(product)
    species = _detect_crustacean_species(text)
    peeled = _is_peeled(product)

    # 03.06 subheading structure:
    # 0306.11 - Rock lobster/langoustine, live
    # 0306.12 - Lobsters, live
    # 0306.14 - Crabs, live
    # 0306.15 - Norway lobsters, live
    # 0306.16 - Cold-water shrimps/prawns (frozen, not live)
    # 0306.17 - Other shrimps/prawns (frozen, not live)
    # 0306.19 - Other crustaceans (live, incl flour/meal/pellets)
    # 0306.31-39 - Not frozen (fresh/chilled/dried/salted/smoked/cooked-in-shell)

    # Live crustaceans
    if state == "live":
        sub_map = {
            "lobster_langoustine": ("0306.11", "Live langoustine/rock lobster → 0306.11."),
            "shrimp_prawn": ("0306.19", "Live shrimp/prawn → 0306.19 (other live crustaceans)."),
            "crab": ("0306.14", "Live crab → 0306.14."),
            "other": ("0306.19", "Live crustacean (other) → 0306.19."),
        }
        sub, reasoning = sub_map.get(species, ("0306.19", "Live crustacean → 0306.19."))
        result["candidates"].append({
            "heading": "03.06",
            "subheading_hint": sub,
            "confidence": 0.90,
            "reasoning": reasoning,
            "rule_applied": "GIR 1 — heading 03.06 + subheading text",
        })
        return result

    # Frozen crustaceans (0306.11-0306.19 block for frozen)
    if state == "frozen":
        if species == "lobster_langoustine":
            if peeled:
                # Peeled frozen langoustine → 0306.17 "other shrimps and prawns"
                # Actually for langoustine this is typically under 0306.15 or similar
                # but Israeli tariff groups peeled frozen under "other frozen"
                sub = "0306.17"
                reasoning = (
                    "Frozen peeled langoustine meat → 0306.17 (other frozen crustaceans). "
                    "Peeled = no longer 'in shell', classified under 'other' subheading."
                )
            else:
                sub = "0306.11"
                reasoning = "Frozen rock lobster/langoustine (in shell) → 0306.11."
        elif species == "shrimp_prawn":
            sub = "0306.17"
            reasoning = "Frozen shrimp/prawn → 0306.17."
        elif species == "crab":
            sub = "0306.14"
            reasoning = "Frozen crab → 0306.14."
        else:
            sub = "0306.19"
            reasoning = "Frozen crustacean (other) → 0306.19."

        result["candidates"].append({
            "heading": "03.06",
            "subheading_hint": sub,
            "confidence": 0.85,
            "reasoning": reasoning,
            "rule_applied": "GIR 1 — heading 03.06 + subheading for frozen crustaceans",
        })
        return result

    # Not frozen, not live: fresh/chilled/dried/salted/smoked/cooked-in-shell
    # These go to 0306.31-0306.39 block
    if state in ("fresh", "chilled", "dried", "salted", "smoked", "cooked"):
        if species == "lobster_langoustine":
            sub = "0306.31"
            reasoning = f"Langoustine/rock lobster, {state} (not frozen) → 0306.31."
        elif species == "shrimp_prawn":
            sub = "0306.36"
            reasoning = f"Shrimp/prawn, {state} (not frozen) → 0306.36."
        elif species == "crab":
            sub = "0306.33"
            reasoning = f"Crab, {state} (not frozen) → 0306.33."
        else:
            sub = "0306.39"
            reasoning = f"Crustacean (other), {state} (not frozen) → 0306.39."

        result["candidates"].append({
            "heading": "03.06",
            "subheading_hint": sub,
            "confidence": 0.85,
            "reasoning": reasoning,
            "rule_applied": "GIR 1 — heading 03.06 + subheading for non-frozen crustaceans",
        })
        return result

    # Unknown state
    result["candidates"].append({
        "heading": "03.06",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": f"Crustacean ({species}), state unknown → 03.06.",
        "rule_applied": "GIR 1 — heading 03.06",
    })
    result["questions_needed"].append(
        "What is the state of the crustacean? "
        "(live/fresh/chilled/frozen/dried/salted/smoked/cooked-in-shell)"
    )
    return result


# ============================================================================
# CHAPTER 01: Live animals
# ============================================================================

_CH01_BOVINE = re.compile(
    r'(?:בקר|פרה|שור|עגל|פר|בופלו|'
    r'cattle|cow|bull|calf|calves|bovine|buffalo|bison|ox|oxen|steer|heifer|beef|veal)',
    re.IGNORECASE
)

_CH01_SWINE = re.compile(
    r'(?:חזיר|pig|swine|hog|pork|piglet|boar|sow)',
    re.IGNORECASE
)

_CH01_OVINE_CAPRINE = re.compile(
    r'(?:כבש|כבשה|עז|גדי|sheep|lamb|goat|kid|ovine|caprine|ewe|ram|mutton)',
    re.IGNORECASE
)

_CH01_POULTRY = re.compile(
    r'(?:עוף|תרנגול|ברווז|אווז|הודו|שליו|'
    r'chicken|hen|rooster|duck|goose|turkey|guinea\s*fowl|poultry|'
    r'quail|pheasant|pigeon|ostrich)',
    re.IGNORECASE
)

_CH01_HORSE = re.compile(
    r'(?:סוס|חמור|פרד|horse|donkey|ass|mule|hinny|equine)',
    re.IGNORECASE
)

_CH01_LIVE_ANIMAL = re.compile(
    r'(?:חי|חיה|live|living|alive|בעל\s*חיים|animal)',
    re.IGNORECASE
)

# Chapter 01 exclusions — redirect signals
_CH01_MEAT_SIGNALS = re.compile(
    r'(?:בשר|נתח|שוק|כנף|חזה|קרביים|'
    r'meat|carcass|cut|breast|thigh|wing|offal|giblet|butchered|slaughtered)',
    re.IGNORECASE
)


def _detect_ch01_species(text):
    """Detect animal species for Chapter 01 routing."""
    if _CH01_HORSE.search(text):
        return "horse"
    if _CH01_BOVINE.search(text):
        return "bovine"
    if _CH01_SWINE.search(text):
        return "swine"
    if _CH01_OVINE_CAPRINE.search(text):
        return "ovine_caprine"
    if _CH01_POULTRY.search(text):
        return "poultry"
    return "other"


def _is_chapter_01_candidate(text):
    """Check if product text suggests Chapter 01 (live animals)."""
    return bool(_CH01_LIVE_ANIMAL.search(text) and (
        _CH01_BOVINE.search(text) or _CH01_SWINE.search(text)
        or _CH01_OVINE_CAPRINE.search(text) or _CH01_POULTRY.search(text)
        or _CH01_HORSE.search(text)
    ))


def _decide_chapter_01(product):
    """Chapter 01 decision tree: Live animals.

    Headings:
        01.01 — Live horses, asses, mules, hinnies
        01.02 — Live bovine animals
        01.03 — Live swine
        01.04 — Live sheep and goats
        01.05 — Live poultry
        01.06 — Other live animals
    """
    text = _product_text(product)
    state = _get_processing_state(product)
    species = _detect_ch01_species(text)

    result = {
        "chapter": 1,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # Gate: Not live → redirect to Chapter 02 (meat) or 05 (animal products)
    if state in ("slaughtered", "butchered", "frozen", "chilled", "fresh"):
        if _CH01_MEAT_SIGNALS.search(text):
            result["redirect"] = {
                "chapter": 2,
                "reason": (
                    f"Animal is not live (state={state}), meat signals detected. "
                    f"Chapter 01 covers LIVE animals only. → Chapter 02 (meat)."
                ),
                "rule_applied": "Chapter 01 scope — live animals only",
            }
            return result

    if state and state not in ("live", ""):
        # Non-live, non-meat — could be animal products
        result["redirect"] = {
            "chapter": 5,
            "reason": (
                f"Animal product state={state}, not live. "
                f"Chapter 01 covers LIVE animals only. → Chapter 05 (other animal products)."
            ),
            "rule_applied": "Chapter 01 scope — live animals only",
        }
        return result

    # Species routing
    heading_map = {
        "horse": ("01.01", "Live horses, asses, mules, hinnies → 01.01."),
        "bovine": ("01.02", "Live bovine animals → 01.02."),
        "swine": ("01.03", "Live swine → 01.03."),
        "ovine_caprine": ("01.04", "Live sheep and goats → 01.04."),
        "poultry": ("01.05", "Live poultry → 01.05."),
        "other": ("01.06", "Other live animals → 01.06."),
    }

    heading, reasoning = heading_map.get(species, ("01.06", "Other live animals → 01.06."))
    result["candidates"].append({
        "heading": heading,
        "subheading_hint": None,
        "confidence": 0.90,
        "reasoning": reasoning,
        "rule_applied": f"GIR 1 — heading {heading}",
    })
    return result


# ============================================================================
# CHAPTER 02: Meat and edible offal
# ============================================================================

_CH02_OFFAL = re.compile(
    r'(?:קרביים|כבד|לב|כליות|לשון|זנב|'
    r'offal|liver|heart|kidney|tongue|tail|gizzard|giblet)',
    re.IGNORECASE
)

_CH02_MINCED = re.compile(
    r'(?:טחון|קצוץ|minced|ground|mince)',
    re.IGNORECASE
)

_CH02_CUT = re.compile(
    r'(?:נתח|חזה|שוק|כנף|צלע|סטייק|אנטריקוט|'
    r'cut|breast|thigh|leg|wing|rib|steak|chop|loin|shoulder|'
    r'drumstick|tenderloin|fillet|boneless)',
    re.IGNORECASE
)

# States that stay in Ch.02 (Note 1(a): fresh, chilled, frozen, salted, in brine, dried, smoked)
_CH02_ALLOWED_STATES = {"fresh", "chilled", "frozen", "salted", "dried", "smoked", "live", ""}

# Compound/prepared signals → redirect to Ch.16
_CH02_PREPARED = re.compile(
    r'(?:מבושל|מטוגן|צלוי|מעובד|נקניק|קבב|המבורגר|שניצל|'
    r'cooked|fried|roasted|processed|sausage|kebab|hamburger|schnitzel|'
    r'cured|pâté|pate|terrine|canned|preserved|ready.to.eat)',
    re.IGNORECASE
)


def _detect_ch02_species(text):
    """Detect meat species for Chapter 02 heading routing."""
    if _CH01_BOVINE.search(text):
        return "bovine"
    if _CH01_SWINE.search(text):
        return "swine"
    if _CH01_OVINE_CAPRINE.search(text):
        return "ovine_caprine"
    if _CH01_POULTRY.search(text):
        return "poultry"
    if _CH01_HORSE.search(text):
        return "horse"
    return "other"


def _is_chapter_02_candidate(text):
    """Check if product text suggests Chapter 02 (meat)."""
    return bool(_CH01_MEAT_SIGNALS.search(text) and (
        _CH01_BOVINE.search(text) or _CH01_SWINE.search(text)
        or _CH01_OVINE_CAPRINE.search(text) or _CH01_POULTRY.search(text)
        or _CH01_HORSE.search(text)
    ))


def _decide_chapter_02(product):
    """Chapter 02 decision tree: Meat and edible meat offal.

    Headings:
        02.01 — Meat of bovine animals, fresh or chilled
        02.02 — Meat of bovine animals, frozen
        02.03 — Meat of swine, fresh, chilled or frozen
        02.04 — Meat of sheep or goats, fresh, chilled or frozen
        02.05 — Meat of horses/asses/mules/hinnies, fresh, chilled or frozen
        02.06 — Edible offal of bovine, swine, sheep, goats, horses etc., fresh/chilled/frozen
        02.07 — Meat and edible offal of poultry, fresh, chilled or frozen
        02.08 — Other meat and edible meat offal, fresh, chilled or frozen
        02.09 — Pig fat / poultry fat, not rendered, fresh/chilled/frozen/salted/dried/smoked
        02.10 — Meat and edible offal, salted, in brine, dried or smoked
    """
    text = _product_text(product)
    state = _get_processing_state(product)
    species = _detect_ch02_species(text)

    result = {
        "chapter": 2,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # Gate: Compound/prepared → redirect Ch.16
    if state == "compound" or _CH02_PREPARED.search(text):
        result["redirect"] = {
            "chapter": 16,
            "reason": (
                "Meat is prepared/processed beyond Ch.02 allowed states "
                "(fresh/chilled/frozen/salted/dried/smoked). "
                "Cooked, cured, sausage, canned → Chapter 16."
            ),
            "rule_applied": "Chapter 02 Note 1(a) exclusion + GIR 1",
        }
        return result

    # Gate: Live animal → redirect Ch.01
    if state == "live":
        result["redirect"] = {
            "chapter": 1,
            "reason": "Live animal, not meat. → Chapter 01 (live animals).",
            "rule_applied": "Chapter 02 scope — slaughtered/dressed meat only",
        }
        return result

    is_offal = bool(_CH02_OFFAL.search(text))

    # 02.10: Salted/dried/smoked meat (any species)
    if state in ("salted", "dried", "smoked"):
        result["candidates"].append({
            "heading": "02.10",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Meat ({species}), {state} → 02.10.",
            "rule_applied": "GIR 1 — heading 02.10 'Meat, salted, dried or smoked'",
        })
        return result

    # Poultry — heading 02.07 covers meat AND offal, fresh/chilled/frozen
    if species == "poultry":
        result["candidates"].append({
            "heading": "02.07",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Poultry meat/offal, {state or 'fresh/chilled/frozen'} → 02.07.",
            "rule_applied": "GIR 1 — heading 02.07 'Poultry meat and offal'",
        })
        return result

    # Offal (non-poultry) → 02.06
    if is_offal:
        result["candidates"].append({
            "heading": "02.06",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Edible offal ({species}), {state or 'fresh/chilled/frozen'} → 02.06.",
            "rule_applied": "GIR 1 — heading 02.06 'Edible offal'",
        })
        return result

    # Species + state routing for non-offal, non-poultry meat
    if species == "bovine":
        if state in ("fresh", "chilled", ""):
            heading = "02.01"
            reasoning = f"Bovine meat, {state or 'fresh/chilled'} → 02.01."
        elif state == "frozen":
            heading = "02.02"
            reasoning = "Bovine meat, frozen → 02.02."
        else:
            heading = "02.01"
            reasoning = f"Bovine meat, state={state} → 02.01 (default fresh/chilled)."
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    if species == "swine":
        result["candidates"].append({
            "heading": "02.03",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Swine meat, {state or 'fresh/chilled/frozen'} → 02.03.",
            "rule_applied": "GIR 1 — heading 02.03",
        })
        return result

    if species == "ovine_caprine":
        result["candidates"].append({
            "heading": "02.04",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Sheep/goat meat, {state or 'fresh/chilled/frozen'} → 02.04.",
            "rule_applied": "GIR 1 — heading 02.04",
        })
        return result

    if species == "horse":
        result["candidates"].append({
            "heading": "02.05",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": f"Horse/ass/mule meat, {state or 'fresh/chilled/frozen'} → 02.05.",
            "rule_applied": "GIR 1 — heading 02.05",
        })
        return result

    # Other/unknown species (rabbit, frog legs, game, etc.)
    result["candidates"].append({
        "heading": "02.08",
        "subheading_hint": None,
        "confidence": 0.80,
        "reasoning": f"Other meat ({species}), {state or 'fresh/chilled/frozen'} → 02.08.",
        "rule_applied": "GIR 1 — heading 02.08 'Other meat'",
    })
    return result


# ============================================================================
# CHAPTER 04: Dairy produce; birds' eggs; natural honey; edible animal products
# ============================================================================

_CH04_MILK = re.compile(
    r'(?:חלב|cream|milk|שמנת|קרם\s*חלב|'
    r'skim\s*milk|whole\s*milk|buttermilk|whey|מי\s*גבינה)',
    re.IGNORECASE
)

_CH04_CHEESE = re.compile(
    r'(?:גבינה|גבינות|cheese|curd|cottage|mozzarella|cheddar|gouda|'
    r'parmesan|feta|brie|camembert|ricotta|mascarpone|גאודה|פרמזן|צהובה|לבנה)',
    re.IGNORECASE
)

_CH04_YOGURT = re.compile(
    r'(?:יוגורט|קפיר|לבן|yogurt|yoghurt|kefir|fermented\s*milk|'
    r'acidophilus|leben)',
    re.IGNORECASE
)

_CH04_BUTTER = re.compile(
    r'(?:חמאה|butter|ghee|סמנה|dairy\s*spread)',
    re.IGNORECASE
)

_CH04_EGGS = re.compile(
    r'(?:ביצה|ביצים|egg|eggs|yolk|חלמון|חלבון\s*ביצה|albumen)',
    re.IGNORECASE
)

_CH04_HONEY = re.compile(
    r'(?:דבש|honey|דבש\s*טבעי|natural\s*honey)',
    re.IGNORECASE
)

_CH04_OTHER_ANIMAL = re.compile(
    r'(?:ג\'לי\s*רויאל|royal\s*jelly|propolis|פרופוליס|'
    r'edible\s*animal\s*product|insect|turtle\s*egg|bird.s?\s*nest)',
    re.IGNORECASE
)

# Prepared dairy → redirect Ch.21 (food preparations) or Ch.19 (bakery)
_CH04_PREPARED = re.compile(
    r'(?:גלידה|ice\s*cream|pudding|פודינג|'
    r'flavored\s*milk|chocolate\s*milk|fruit\s*yogurt|'
    r'processed\s*cheese\s*spread)',
    re.IGNORECASE
)


def _detect_ch04_product_type(text):
    """Detect dairy product type for Chapter 04 heading routing."""
    if _CH04_CHEESE.search(text):
        return "cheese"
    if _CH04_YOGURT.search(text):
        return "yogurt"
    if _CH04_BUTTER.search(text):
        return "butter"
    if _CH04_EGGS.search(text):
        return "eggs"
    if _CH04_HONEY.search(text):
        return "honey"
    if _CH04_OTHER_ANIMAL.search(text):
        return "other_animal"
    if _CH04_MILK.search(text):
        return "milk"
    return "unknown"


def _is_chapter_04_candidate(text):
    """Check if product text suggests Chapter 04 (dairy/eggs/honey)."""
    return bool(
        _CH04_MILK.search(text) or _CH04_CHEESE.search(text)
        or _CH04_YOGURT.search(text) or _CH04_BUTTER.search(text)
        or _CH04_EGGS.search(text) or _CH04_HONEY.search(text)
        or _CH04_OTHER_ANIMAL.search(text)
    )


def _decide_chapter_04(product):
    """Chapter 04 decision tree: Dairy, eggs, honey, other animal products.

    Headings:
        04.01 — Milk and cream, not concentrated, not sweetened
        04.02 — Milk and cream, concentrated or sweetened
        04.03 — Buttermilk, yogurt, kefir, fermented milk
        04.04 — Whey; products of natural milk constituents
        04.05 — Butter and other fats derived from milk; dairy spreads
        04.06 — Cheese and curd
        04.07 — Birds' eggs, in shell, fresh/preserved/cooked
        04.08 — Birds' eggs, not in shell, yolks
        04.09 — Natural honey
        04.10 — Edible products of animal origin, not elsewhere specified
    """
    text = _product_text(product)
    state = _get_processing_state(product)
    prod_type = _detect_ch04_product_type(text)

    result = {
        "chapter": 4,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # Gate: Ice cream → Ch.21
    if _CH04_PREPARED.search(text):
        result["redirect"] = {
            "chapter": 21,
            "reason": (
                "Prepared dairy product (ice cream/flavored/chocolate milk/pudding). "
                "Chapter 04 covers raw/basic dairy. Preparations → Chapter 21."
            ),
            "rule_applied": "Chapter 04 exclusion note + GIR 1",
        }
        return result

    # Product type routing
    if prod_type == "milk":
        # Check for concentrated/sweetened
        concentrated = bool(re.search(
            r'(?:מרוכז|אבקה|powder|condensed|concentrated|evaporated|sweetened|ממותק)',
            text, re.IGNORECASE
        ))
        if concentrated:
            heading = "04.02"
            reasoning = "Milk/cream, concentrated or sweetened → 04.02."
        else:
            heading = "04.01"
            reasoning = "Milk/cream, not concentrated, not sweetened → 04.01."
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    if prod_type == "yogurt":
        result["candidates"].append({
            "heading": "04.03",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Yogurt/kefir/fermented milk → 04.03.",
            "rule_applied": "GIR 1 — heading 04.03",
        })
        return result

    if prod_type == "butter":
        result["candidates"].append({
            "heading": "04.05",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Butter/ghee/dairy fat → 04.05.",
            "rule_applied": "GIR 1 — heading 04.05",
        })
        return result

    if prod_type == "cheese":
        result["candidates"].append({
            "heading": "04.06",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cheese/curd → 04.06.",
            "rule_applied": "GIR 1 — heading 04.06",
        })
        return result

    if prod_type == "eggs":
        in_shell = bool(re.search(
            r'(?:בקליפה|in\s*shell|shell|whole\s*egg|fresh\s*egg)',
            text, re.IGNORECASE
        ))
        if in_shell or "yolk" not in text.lower() and "חלמון" not in text:
            heading = "04.07"
            reasoning = "Birds' eggs, in shell → 04.07."
        else:
            heading = "04.08"
            reasoning = "Birds' eggs, not in shell / yolks → 04.08."
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    if prod_type == "honey":
        result["candidates"].append({
            "heading": "04.09",
            "subheading_hint": None,
            "confidence": 0.95,
            "reasoning": "Natural honey → 04.09.",
            "rule_applied": "GIR 1 — heading 04.09",
        })
        return result

    if prod_type == "other_animal":
        result["candidates"].append({
            "heading": "04.10",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Edible animal product n.e.s. (royal jelly, propolis, etc.) → 04.10.",
            "rule_applied": "GIR 1 — heading 04.10",
        })
        return result

    # Unknown dairy product
    result["candidates"].extend([
        {"heading": "04.01", "subheading_hint": None, "confidence": 0.25,
         "reasoning": "Unknown dairy — could be milk.", "rule_applied": "GIR 1"},
        {"heading": "04.06", "subheading_hint": None, "confidence": 0.25,
         "reasoning": "Unknown dairy — could be cheese.", "rule_applied": "GIR 1"},
    ])
    result["questions_needed"].append(
        "What type of dairy/animal product is this? "
        "(milk, cream, cheese, yogurt, butter, eggs, honey, other)"
    )
    return result


# ============================================================================
# CHAPTER 05: Products of animal origin, not elsewhere specified or included
# ============================================================================

_CH05_HAIR_BRISTLE = re.compile(
    r'(?:שיער|זיפים|שער\s*חזיר|bristle|hair|horsehair|'
    r'badger\s*hair|brush\s*hair|pig\s*bristle)',
    re.IGNORECASE
)

_CH05_BONE_HORN = re.compile(
    r'(?:עצם|עצמות|קרן|קרניים|חומר\s*קרני|'
    r'bone|horn|antler|hoof|coral|ivory|tortoiseshell|'
    r'ossein|bone\s*meal|bone\s*powder)',
    re.IGNORECASE
)

_CH05_FEATHER_DOWN = re.compile(
    r'(?:נוצה|נוצות|פוך|feather|down|plume|quill)',
    re.IGNORECASE
)

_CH05_SKIN_HIDE = re.compile(
    r'(?:עור\s*גולמי|עורות|raw\s*hide|raw\s*skin|untanned)',
    re.IGNORECASE
)

_CH05_GUTS = re.compile(
    r'(?:מעיים|קיבה|bladder|gut|maw|stomach|intestine|'
    r'rennet|casings|natural\s*casing)',
    re.IGNORECASE
)

_CH05_SEMEN_EMBRYO = re.compile(
    r'(?:זרע|עוברים|semen|embryo|ova|hatching)',
    re.IGNORECASE
)

_CH05_AMBERGRIS = re.compile(
    r'(?:ענבר|ambergris|civet|musk|castoreum|cantharides|bile)',
    re.IGNORECASE
)

_CH05_BLOOD = re.compile(
    r'(?:דם|blood|dried\s*blood|blood\s*meal)',
    re.IGNORECASE
)


def _detect_ch05_product_type(text):
    """Detect product type for Chapter 05 routing."""
    if _CH05_HAIR_BRISTLE.search(text):
        return "hair_bristle"
    if _CH05_FEATHER_DOWN.search(text):
        return "feather_down"
    if _CH05_BONE_HORN.search(text):
        return "bone_horn"
    if _CH05_GUTS.search(text):
        return "guts"
    if _CH05_SEMEN_EMBRYO.search(text):
        return "semen_embryo"
    if _CH05_AMBERGRIS.search(text):
        return "ambergris"
    if _CH05_BLOOD.search(text):
        return "blood"
    if _CH05_SKIN_HIDE.search(text):
        return "skin_hide"
    return "other"


def _is_chapter_05_candidate(text):
    """Check if product text suggests Chapter 05 (other animal products)."""
    return bool(
        _CH05_HAIR_BRISTLE.search(text) or _CH05_BONE_HORN.search(text)
        or _CH05_FEATHER_DOWN.search(text) or _CH05_GUTS.search(text)
        or _CH05_SEMEN_EMBRYO.search(text) or _CH05_AMBERGRIS.search(text)
        or _CH05_BLOOD.search(text) or _CH05_SKIN_HIDE.search(text)
    )


def _decide_chapter_05(product):
    """Chapter 05 decision tree: Products of animal origin, n.e.s.

    Headings:
        05.01 — Human hair; animal hair waste
        05.02 — Pigs'/hogs' bristles; badger/brush hair; hair waste
        05.04 — Guts, bladders, stomachs of animals (not fish)
        05.05 — Skins/parts of birds with feathers; feathers; down
        05.06 — Bones, horn-cores; horn, antler, hooves, coral, etc.
        05.07 — Ivory, tortoiseshell, whalebone, horns, antlers
        05.08 — Coral, shells; cuttlebone, sepia
        05.09 — Natural sponges of animal origin
        05.10 — Ambergris, castoreum, civet, musk; bile; animal substances for pharma
        05.11 — Animal products n.e.s.; dead animals (unfit for human consumption)
    """
    text = _product_text(product)
    prod_type = _detect_ch05_product_type(text)

    result = {
        "chapter": 5,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    type_to_heading = {
        "hair_bristle": ("05.02", "Pig bristles / brush hair → 05.02."),
        "feather_down": ("05.05", "Feathers / down → 05.05."),
        "bone_horn": ("05.06", "Bones / horn / antler / hooves → 05.06."),
        "guts": ("05.04", "Guts / bladders / stomachs / casings → 05.04."),
        "semen_embryo": ("05.11", "Animal semen / embryos → 05.11."),
        "ambergris": ("05.10", "Ambergris / musk / bile / animal pharma substances → 05.10."),
        "blood": ("05.11", "Animal blood → 05.11."),
        "skin_hide": ("05.11", "Raw hides/skins — may redirect to Ch.41 (tanning). Tentative → 05.11."),
    }

    if prod_type in type_to_heading:
        heading, reasoning = type_to_heading[prod_type]
        conf = 0.85
        if prod_type == "skin_hide":
            conf = 0.60
            result["questions_needed"].append(
                "Is this raw hide for tanning/leather (→ Ch.41) or for other purposes (→ Ch.05)?"
            )
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": conf,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    # Other/unknown → 05.11
    result["candidates"].append({
        "heading": "05.11",
        "subheading_hint": None,
        "confidence": 0.70,
        "reasoning": "Animal product n.e.s. → 05.11.",
        "rule_applied": "GIR 1 — heading 05.11",
    })
    result["questions_needed"].append(
        "What type of animal product is this? "
        "(hair/bristle, feathers/down, bones/horns, guts/casings, blood, semen/embryos, other)"
    )
    return result


# ============================================================================
# CHAPTER 06: Live trees, plants; bulbs, roots; cut flowers, ornamental foliage
# ============================================================================

_CH06_BULB_RHIZOME = re.compile(
    r'(?:פקעת|שורש|בצל\s*נוי|bulb|tuber|rhizome|root\s*stock|corm|crown)',
    re.IGNORECASE
)

_CH06_TREE_SHRUB = re.compile(
    r'(?:עץ|שתיל|שיח|נטיעה|tree|shrub|plant|seedling|sapling|'
    r'vine|rose\s*bush|grafted|rootstock)',
    re.IGNORECASE
)

_CH06_CUT_FLOWER = re.compile(
    r'(?:פרח|פרחים|זר|ורד|שושן|ציפורן|סחלב|'
    r'flower|bouquet|rose|lily|carnation|orchid|tulip|'
    r'chrysanthemum|gerbera|sunflower|cut\s*flower)',
    re.IGNORECASE
)

_CH06_FOLIAGE = re.compile(
    r'(?:עלווה|ענף\s*נוי|עלים\s*נוי|foliage|greenery|leaves\s*ornamental|'
    r'fern|moss|lichen|decorative\s*branch)',
    re.IGNORECASE
)

_CH06_DRIED_PRESERVED = re.compile(
    r'(?:מיובש|משומר|מלאכותי|צבוע|dyed|dried|preserved|'
    r'bleached|impregnated|artificial)',
    re.IGNORECASE
)


def _is_chapter_06_candidate(text):
    return bool(
        _CH06_BULB_RHIZOME.search(text) or _CH06_TREE_SHRUB.search(text)
        or _CH06_CUT_FLOWER.search(text) or _CH06_FOLIAGE.search(text)
    )


def _decide_chapter_06(product):
    """Chapter 06: Live trees, plants; bulbs; cut flowers; ornamental foliage.

    06.01 — Bulbs, tubers, tuberous roots, corms, crowns, rhizomes
    06.02 — Other live plants; mushroom spawn
    06.03 — Cut flowers and flower buds (fresh, dried, dyed, bleached)
    06.04 — Foliage, branches, grasses (fresh, dried, dyed, bleached)
    """
    text = _product_text(product)
    state = _get_processing_state(product)

    result = {"chapter": 6, "candidates": [], "redirect": None, "questions_needed": []}

    # Dried/preserved cut flowers → still Ch.06 (06.03 covers dried/dyed)
    # Artificial flowers → redirect Ch.67
    if re.search(r'(?:מלאכותי|artificial|plastic\s*flower|silk\s*flower)', text, re.IGNORECASE):
        result["redirect"] = {
            "chapter": 67,
            "reason": "Artificial/plastic flowers → Chapter 67 (prepared feathers, artificial flowers).",
            "rule_applied": "Chapter 06 exclusion — artificial flowers",
        }
        return result

    if _CH06_BULB_RHIZOME.search(text):
        result["candidates"].append({
            "heading": "06.01", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Bulbs, tubers, rhizomes, corms → 06.01.",
            "rule_applied": "GIR 1 — heading 06.01",
        })
        return result

    if _CH06_CUT_FLOWER.search(text):
        result["candidates"].append({
            "heading": "06.03", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Cut flowers/flower buds → 06.03.",
            "rule_applied": "GIR 1 — heading 06.03",
        })
        return result

    if _CH06_FOLIAGE.search(text):
        result["candidates"].append({
            "heading": "06.04", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Foliage, branches, grasses for ornamental use → 06.04.",
            "rule_applied": "GIR 1 — heading 06.04",
        })
        return result

    if _CH06_TREE_SHRUB.search(text):
        result["candidates"].append({
            "heading": "06.02", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Live plants, trees, shrubs, seedlings → 06.02.",
            "rule_applied": "GIR 1 — heading 06.02",
        })
        return result

    result["candidates"].append({
        "heading": "06.02", "subheading_hint": None, "confidence": 0.60,
        "reasoning": "Live plant product — default → 06.02.",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of plant product? (bulb/tuber, live tree/shrub, cut flowers, foliage)"
    )
    return result


# ============================================================================
# CHAPTER 07: Edible vegetables and certain roots and tubers
# ============================================================================

_CH07_POTATO = re.compile(
    r'(?:תפוח\s*אדמה|תפו"א|potato|potatoes)', re.IGNORECASE
)
_CH07_TOMATO = re.compile(
    r'(?:עגבנייה|עגבניות|tomato|tomatoes)', re.IGNORECASE
)
_CH07_ONION_GARLIC = re.compile(
    r'(?:בצל|שום|כרישה|onion|garlic|leek|shallot|scallion)', re.IGNORECASE
)
_CH07_LEGUME = re.compile(
    r'(?:שעועית|אפונה|עדשים|חומוס|pea|bean|lentil|chickpea|'
    r'broad\s*bean|kidney\s*bean|lima\s*bean|soybean|soya)', re.IGNORECASE
)
_CH07_BRASSICA = re.compile(
    r'(?:כרוב|ברוקולי|כרובית|cabbage|broccoli|cauliflower|'
    r'kale|brussels\s*sprout|kohlrabi)', re.IGNORECASE
)
_CH07_LETTUCE = re.compile(
    r'(?:חסה|עולש|lettuce|chicory|endive|spinach|תרד)', re.IGNORECASE
)
_CH07_CARROT = re.compile(
    r'(?:גזר|סלק|לפת|צנון|carrot|beet|turnip|radish|celeriac|parsnip)',
    re.IGNORECASE
)
_CH07_CUCUMBER = re.compile(
    r'(?:מלפפון|דלעת|קישוא|cucumber|gherkin|pumpkin|squash|zucchini|courgette)',
    re.IGNORECASE
)
_CH07_MUSHROOM = re.compile(
    r'(?:פטריות|כמהין|mushroom|truffle|shiitake|champignon)', re.IGNORECASE
)
_CH07_PEPPER = re.compile(
    r'(?:פלפל|capsicum|pepper|chili|chilli|paprika|jalapeño)', re.IGNORECASE
)
_CH07_VEGETABLE_GENERIC = re.compile(
    r'(?:ירק|ירקות|vegetable|veg|fresh\s*produce|אספרגוס|ארטישוק|'
    r'asparagus|artichoke|celery|סלרי|olive|זית|corn|תירס|sweet\s*corn)',
    re.IGNORECASE
)

_CH07_FROZEN = re.compile(r'(?:קפוא|frozen)', re.IGNORECASE)
_CH07_DRIED = re.compile(r'(?:מיובש|יבש|dried|dehydrated)', re.IGNORECASE)
_CH07_PRESERVED = re.compile(
    r'(?:כבוש|משומר|חמוץ|pickled|preserved|vinegar|brine|canned|tinned)',
    re.IGNORECASE
)


def _is_chapter_07_candidate(text):
    return bool(
        _CH07_POTATO.search(text) or _CH07_TOMATO.search(text)
        or _CH07_ONION_GARLIC.search(text) or _CH07_LEGUME.search(text)
        or _CH07_BRASSICA.search(text) or _CH07_LETTUCE.search(text)
        or _CH07_CARROT.search(text) or _CH07_CUCUMBER.search(text)
        or _CH07_MUSHROOM.search(text) or _CH07_PEPPER.search(text)
        or _CH07_VEGETABLE_GENERIC.search(text)
    )


def _decide_chapter_07(product):
    """Chapter 07: Edible vegetables, roots, tubers.

    07.01 — Potatoes, fresh or chilled
    07.02 — Tomatoes, fresh or chilled
    07.03 — Onions, shallots, garlic, leeks (fresh or chilled)
    07.04 — Cabbages, cauliflowers, broccoli, kale (fresh or chilled)
    07.05 — Lettuce, chicory (fresh or chilled)
    07.06 — Carrots, turnips, beetroot, radishes, celeriac (fresh or chilled)
    07.07 — Cucumbers, gherkins (fresh or chilled)
    07.08 — Leguminous vegetables (fresh or chilled)
    07.09 — Other vegetables (fresh or chilled)
    07.10 — Vegetables (frozen)
    07.11 — Vegetables provisionally preserved
    07.12 — Dried vegetables
    07.13 — Dried leguminous vegetables (shelled)
    07.14 — Manioc, arrowroot, sweet potatoes, similar starchy roots
    """
    text = _product_text(product)
    state = _get_processing_state(product)

    result = {"chapter": 7, "candidates": [], "redirect": None, "questions_needed": []}

    # Gate: Preserved (pickled/canned/vinegar) → redirect Ch.20
    if state == "compound" or _CH07_PRESERVED.search(text):
        result["redirect"] = {
            "chapter": 20,
            "reason": "Preserved/pickled/canned vegetables → Chapter 20 (preparations of vegetables).",
            "rule_applied": "Chapter 07 exclusion note + GIR 1",
        }
        return result

    # Frozen vegetables → 07.10
    if state == "frozen" or _CH07_FROZEN.search(text):
        result["candidates"].append({
            "heading": "07.10", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Frozen vegetables → 07.10.",
            "rule_applied": "GIR 1 — heading 07.10",
        })
        return result

    # Dried vegetables
    if state == "dried" or _CH07_DRIED.search(text):
        if _CH07_LEGUME.search(text):
            result["candidates"].append({
                "heading": "07.13", "subheading_hint": None, "confidence": 0.90,
                "reasoning": "Dried leguminous vegetables → 07.13.",
                "rule_applied": "GIR 1 — heading 07.13",
            })
        else:
            result["candidates"].append({
                "heading": "07.12", "subheading_hint": None, "confidence": 0.85,
                "reasoning": "Dried vegetables → 07.12.",
                "rule_applied": "GIR 1 — heading 07.12",
            })
        return result

    # Fresh/chilled: route by vegetable type
    veg_map = [
        (_CH07_POTATO, "07.01", "Potatoes → 07.01."),
        (_CH07_TOMATO, "07.02", "Tomatoes → 07.02."),
        (_CH07_ONION_GARLIC, "07.03", "Onions/garlic/leeks → 07.03."),
        (_CH07_BRASSICA, "07.04", "Cabbages/broccoli/cauliflower → 07.04."),
        (_CH07_LETTUCE, "07.05", "Lettuce/chicory/spinach → 07.05."),
        (_CH07_CARROT, "07.06", "Carrots/beets/turnips → 07.06."),
        (_CH07_CUCUMBER, "07.07", "Cucumbers/gherkins/squash → 07.07."),
        (_CH07_LEGUME, "07.08", "Fresh leguminous vegetables → 07.08."),
        (_CH07_MUSHROOM, "07.09", "Mushrooms/truffles → 07.09."),
        (_CH07_PEPPER, "07.09", "Peppers/capsicum → 07.09."),
    ]

    for pattern, heading, reasoning in veg_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.90,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    # Generic vegetable
    result["candidates"].append({
        "heading": "07.09", "subheading_hint": None, "confidence": 0.70,
        "reasoning": "Other fresh/chilled vegetables → 07.09.",
        "rule_applied": "GIR 1 — heading 07.09",
    })
    return result


# ============================================================================
# CHAPTER 08: Edible fruit and nuts; peel of citrus fruit or melons
# ============================================================================

_CH08_CITRUS = re.compile(
    r'(?:הדר|תפוז|לימון|אשכולית|מנדרינה|קלמנטינה|'
    r'citrus|orange|lemon|lime|grapefruit|mandarin|clementine|tangerine|pomelo)',
    re.IGNORECASE
)
_CH08_BANANA = re.compile(r'(?:בננה|banana|plantain)', re.IGNORECASE)
_CH08_DATE_FIG = re.compile(
    r'(?:תמר|תאנה|אננס|אבוקדו|מנגו|גויאבה|'
    r'date|fig|pineapple|avocado|mango|guava|papaya|passion\s*fruit)',
    re.IGNORECASE
)
_CH08_GRAPE = re.compile(r'(?:ענב|ענבים|grape|raisin|sultana|currant)', re.IGNORECASE)
_CH08_MELON = re.compile(
    r'(?:אבטיח|מלון|melon|watermelon|cantaloupe)', re.IGNORECASE
)
_CH08_APPLE_PEAR = re.compile(
    r'(?:תפוח|אגס|חבוש|apple|pear|quince)', re.IGNORECASE
)
_CH08_STONE_FRUIT = re.compile(
    r'(?:אפרסק|שזיף|דובדבן|משמש|נקטרינה|'
    r'peach|plum|cherry|apricot|nectarine|prune)', re.IGNORECASE
)
_CH08_BERRY = re.compile(
    r'(?:תות|פטל|אוכמנית|דומדמנית|חמוציות|'
    r'strawberry|raspberry|blueberry|blackberry|cranberry|'
    r'gooseberry|kiwi|berry)', re.IGNORECASE
)
_CH08_NUT = re.compile(
    r'(?:אגוז|שקד|פיסטוק|קשיו|לוז|פקאן|מקדמיה|ערמון|בוטן|'
    r'nut|almond|pistachio|cashew|hazelnut|walnut|pecan|macadamia|'
    r'chestnut|peanut|coconut|קוקוס)', re.IGNORECASE
)
_CH08_FRUIT_GENERIC = re.compile(
    r'(?:פרי|פירות|fruit|רימון|pomegranate|persimmon|אפרסמון|lychee|ליצ\'י)',
    re.IGNORECASE
)


def _is_chapter_08_candidate(text):
    return bool(
        _CH08_CITRUS.search(text) or _CH08_BANANA.search(text)
        or _CH08_DATE_FIG.search(text) or _CH08_GRAPE.search(text)
        or _CH08_MELON.search(text) or _CH08_APPLE_PEAR.search(text)
        or _CH08_STONE_FRUIT.search(text) or _CH08_BERRY.search(text)
        or _CH08_NUT.search(text) or _CH08_FRUIT_GENERIC.search(text)
    )


def _decide_chapter_08(product):
    """Chapter 08: Edible fruit and nuts; peel of citrus/melons.

    08.01 — Coconuts, brazil nuts, cashew nuts
    08.02 — Other nuts (almonds, hazelnuts, walnuts, chestnuts, pistachios, etc.)
    08.03 — Bananas, plantains
    08.04 — Dates, figs, pineapples, avocados, guavas, mangoes
    08.05 — Citrus fruit
    08.06 — Grapes
    08.07 — Melons, watermelons, papayas
    08.08 — Apples, pears, quinces
    08.09 — Apricots, cherries, peaches, plums, nectarines
    08.10 — Other fruit (strawberries, raspberries, kiwi, etc.)
    08.11 — Fruit and nuts, frozen
    08.12 — Fruit and nuts, provisionally preserved
    08.13 — Dried fruit (other than 08.01-08.06)
    08.14 — Peel of citrus fruit or melons
    """
    text = _product_text(product)
    state = _get_processing_state(product)

    result = {"chapter": 8, "candidates": [], "redirect": None, "questions_needed": []}

    # Gate: Preserved/prepared (jam, juice, canned) → Ch.20
    if state == "compound" or re.search(
        r'(?:ריבה|מיץ|שימורים|jam|juice|canned|preserved|marmalade|compote)',
        text, re.IGNORECASE
    ):
        result["redirect"] = {
            "chapter": 20,
            "reason": "Prepared/preserved fruit (jam, juice, canned) → Chapter 20.",
            "rule_applied": "Chapter 08 exclusion note + GIR 1",
        }
        return result

    # Frozen fruit/nuts → 08.11
    if state == "frozen":
        result["candidates"].append({
            "heading": "08.11", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Frozen fruit/nuts → 08.11.",
            "rule_applied": "GIR 1 — heading 08.11",
        })
        return result

    # Dried fruit → 08.13 (unless specific dried fruit in 08.01-08.06)
    if state == "dried":
        if _CH08_GRAPE.search(text):
            result["candidates"].append({
                "heading": "08.06", "subheading_hint": None, "confidence": 0.90,
                "reasoning": "Dried grapes (raisins/sultanas) → 08.06.",
                "rule_applied": "GIR 1 — heading 08.06 covers dried grapes",
            })
        elif _CH08_DATE_FIG.search(text):
            result["candidates"].append({
                "heading": "08.04", "subheading_hint": None, "confidence": 0.90,
                "reasoning": "Dried dates/figs → 08.04.",
                "rule_applied": "GIR 1 — heading 08.04 covers dried dates/figs",
            })
        else:
            result["candidates"].append({
                "heading": "08.13", "subheading_hint": None, "confidence": 0.85,
                "reasoning": "Dried fruit → 08.13.",
                "rule_applied": "GIR 1 — heading 08.13",
            })
        return result

    # Fresh/chilled: route by fruit type
    fruit_map = [
        (_CH08_NUT, "08.02", "Nuts (almonds, walnuts, pistachios, etc.) → 08.02."),
        (_CH08_BANANA, "08.03", "Bananas/plantains → 08.03."),
        (_CH08_DATE_FIG, "08.04", "Dates/figs/pineapples/avocados/mangoes → 08.04."),
        (_CH08_CITRUS, "08.05", "Citrus fruit → 08.05."),
        (_CH08_GRAPE, "08.06", "Grapes → 08.06."),
        (_CH08_MELON, "08.07", "Melons/watermelons → 08.07."),
        (_CH08_APPLE_PEAR, "08.08", "Apples/pears/quinces → 08.08."),
        (_CH08_STONE_FRUIT, "08.09", "Stone fruit (peach/cherry/plum/apricot) → 08.09."),
        (_CH08_BERRY, "08.10", "Berries/kiwi/other fruit → 08.10."),
    ]

    for pattern, heading, reasoning in fruit_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.90,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    result["candidates"].append({
        "heading": "08.10", "subheading_hint": None, "confidence": 0.65,
        "reasoning": "Other fruit → 08.10.",
        "rule_applied": "GIR 1 — heading 08.10",
    })
    return result


# ============================================================================
# CHAPTER 09: Coffee, tea, maté and spices
# ============================================================================

_CH09_COFFEE = re.compile(
    r'(?:קפה|coffee|espresso|arabica|robusta)', re.IGNORECASE
)
_CH09_TEA = re.compile(
    r'(?:תה|tea|green\s*tea|black\s*tea|oolong|matcha|maté|yerba)', re.IGNORECASE
)
_CH09_PEPPER_SPICE = re.compile(
    r'(?:פלפל\s*שחור|פלפל\s*לבן|pepper\s*(?:black|white)|peppercorn)', re.IGNORECASE
)
_CH09_VANILLA = re.compile(r'(?:וניל|vanilla)', re.IGNORECASE)
_CH09_CINNAMON = re.compile(r'(?:קינמון|cinnamon|cassia)', re.IGNORECASE)
_CH09_CLOVE = re.compile(r'(?:ציפורן|clove)', re.IGNORECASE)
_CH09_NUTMEG = re.compile(
    r'(?:אגוז\s*מוסקט|cardamom|הל|nutmeg|mace|cardamom)', re.IGNORECASE
)
_CH09_GINGER = re.compile(
    r'(?:ג\'ינג\'ר|זנגביל|כורכום|ginger|turmeric|saffron|זעפרן|thyme|'
    r'bay\s*lea|oregano|cumin|כמון|coriander|כוסברה|spice|תבלין|תבלינים)',
    re.IGNORECASE
)

_CH09_ROASTED = re.compile(r'(?:קלוי|roasted|roast)', re.IGNORECASE)
_CH09_GROUND = re.compile(r'(?:טחון|ground|powder|crushed)', re.IGNORECASE)
_CH09_EXTRACT = re.compile(
    r'(?:תמצית|מיצוי|extract|instant|soluble|concentrate)', re.IGNORECASE
)


def _is_chapter_09_candidate(text):
    return bool(
        _CH09_COFFEE.search(text) or _CH09_TEA.search(text)
        or _CH09_PEPPER_SPICE.search(text) or _CH09_VANILLA.search(text)
        or _CH09_CINNAMON.search(text) or _CH09_CLOVE.search(text)
        or _CH09_NUTMEG.search(text) or _CH09_GINGER.search(text)
    )


def _decide_chapter_09(product):
    """Chapter 09: Coffee, tea, maté, spices.

    09.01 — Coffee (green/roasted/decaf); husks; substitutes containing coffee
    09.02 — Tea
    09.03 — Maté
    09.04 — Pepper (black/white/long); capsicum/pimenta (dried/crushed/ground)
    09.05 — Vanilla
    09.06 — Cinnamon, cassia
    09.07 — Cloves
    09.08 — Nutmeg, mace, cardamoms
    09.09 — Anise, star anise, fennel, coriander, cumin, caraway, juniper
    09.10 — Ginger, saffron, turmeric, thyme, bay leaves, curry, other spices
    """
    text = _product_text(product)

    result = {"chapter": 9, "candidates": [], "redirect": None, "questions_needed": []}

    # Gate: Instant coffee extracts → Ch.21 if mixed preparations
    # Pure instant coffee stays 09.01; coffee-based beverages → Ch.21
    if _CH09_EXTRACT.search(text) and re.search(
        r'(?:משקה|תערובת|beverage|drink|mix|blend\s*with)', text, re.IGNORECASE
    ):
        result["redirect"] = {
            "chapter": 21,
            "reason": "Coffee/tea beverage mix/blend → Chapter 21 (food preparations).",
            "rule_applied": "Chapter 09 exclusion — mixed preparations",
        }
        return result

    spice_map = [
        (_CH09_COFFEE, "09.01", "Coffee → 09.01."),
        (_CH09_TEA, "09.02", "Tea → 09.02."),
        (_CH09_PEPPER_SPICE, "09.04", "Pepper (black/white) → 09.04."),
        (_CH09_VANILLA, "09.05", "Vanilla → 09.05."),
        (_CH09_CINNAMON, "09.06", "Cinnamon/cassia → 09.06."),
        (_CH09_CLOVE, "09.07", "Cloves → 09.07."),
        (_CH09_NUTMEG, "09.08", "Nutmeg/mace/cardamom → 09.08."),
        (_CH09_GINGER, "09.10", "Ginger/saffron/turmeric/other spices → 09.10."),
    ]

    for pattern, heading, reasoning in spice_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.90,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    result["candidates"].append({
        "heading": "09.10", "subheading_hint": None, "confidence": 0.65,
        "reasoning": "Other spice → 09.10.",
        "rule_applied": "GIR 1 — heading 09.10",
    })
    return result


# ============================================================================
# CHAPTER 10: Cereals
# ============================================================================

_CH10_WHEAT = re.compile(
    r'(?:חיטה|כוסמין|wheat|spelt|meslin|durum)', re.IGNORECASE
)
_CH10_RYE = re.compile(r'(?:שיפון|rye)', re.IGNORECASE)
_CH10_BARLEY = re.compile(r'(?:שעורה|barley)', re.IGNORECASE)
_CH10_OAT = re.compile(r'(?:שיבולת\s*שועל|oat|oats)', re.IGNORECASE)
_CH10_CORN = re.compile(r'(?:תירס|corn|maize)', re.IGNORECASE)
_CH10_RICE = re.compile(r'(?:אורז|rice|paddy|basmati|jasmine)', re.IGNORECASE)
_CH10_SORGHUM = re.compile(r'(?:דורה|sorghum|grain\s*sorghum)', re.IGNORECASE)
_CH10_BUCKWHEAT = re.compile(
    r'(?:כוסמת|דוחן|quinoa|קינואה|buckwheat|millet|canary\s*seed|triticale)',
    re.IGNORECASE
)
_CH10_CEREAL_GENERIC = re.compile(
    r'(?:דגן|דגנים|cereal|grain|whole\s*grain)', re.IGNORECASE
)


def _is_chapter_10_candidate(text):
    return bool(
        _CH10_WHEAT.search(text) or _CH10_RYE.search(text)
        or _CH10_BARLEY.search(text) or _CH10_OAT.search(text)
        or _CH10_CORN.search(text) or _CH10_RICE.search(text)
        or _CH10_SORGHUM.search(text) or _CH10_BUCKWHEAT.search(text)
        or _CH10_CEREAL_GENERIC.search(text)
    )


def _decide_chapter_10(product):
    """Chapter 10: Cereals.

    10.01 — Wheat and meslin
    10.02 — Rye
    10.03 — Barley
    10.04 — Oats
    10.05 — Maize (corn)
    10.06 — Rice
    10.07 — Grain sorghum
    10.08 — Buckwheat, millet, canary seed, other cereals
    """
    text = _product_text(product)
    state = _get_processing_state(product)

    result = {"chapter": 10, "candidates": [], "redirect": None, "questions_needed": []}

    # Gate: Milled/flour → redirect Ch.11
    if re.search(r'(?:קמח|סולת|flour|semolina|meal|groat|flake)', text, re.IGNORECASE):
        result["redirect"] = {
            "chapter": 11,
            "reason": "Milled cereal product (flour/semolina/groats/flakes) → Chapter 11.",
            "rule_applied": "Chapter 10 scope — unmilled grain only",
        }
        return result

    grain_map = [
        (_CH10_WHEAT, "10.01", "Wheat/meslin → 10.01."),
        (_CH10_RYE, "10.02", "Rye → 10.02."),
        (_CH10_BARLEY, "10.03", "Barley → 10.03."),
        (_CH10_OAT, "10.04", "Oats → 10.04."),
        (_CH10_CORN, "10.05", "Maize (corn) → 10.05."),
        (_CH10_RICE, "10.06", "Rice → 10.06."),
        (_CH10_SORGHUM, "10.07", "Grain sorghum → 10.07."),
        (_CH10_BUCKWHEAT, "10.08", "Buckwheat/millet/quinoa/other cereals → 10.08."),
    ]

    for pattern, heading, reasoning in grain_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.90,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    result["candidates"].append({
        "heading": "10.08", "subheading_hint": None, "confidence": 0.65,
        "reasoning": "Other cereal grain → 10.08.",
        "rule_applied": "GIR 1 — heading 10.08",
    })
    return result


# ============================================================================
# CHAPTER 11: Products of the milling industry; malt; starches; inulin; wheat gluten
# ============================================================================

_CH11_WHEAT_FLOUR = re.compile(
    r'(?:קמח\s*חיטה|wheat\s*flour|meslin\s*flour)', re.IGNORECASE
)
_CH11_CEREAL_FLOUR = re.compile(
    r'(?:קמח\s*(?:תירס|אורז|שיבולת|שעורה|שיפון)|'
    r'(?:corn|rice|oat|barley|rye)\s*flour|cereal\s*flour)', re.IGNORECASE
)
_CH11_GROATS = re.compile(
    r'(?:גריסים|גרעינים|סולת|groat|meal|pellet|semolina|kibbled|'
    r'rolled\s*(?:oat|grain)|flake)', re.IGNORECASE
)
_CH11_STARCH = re.compile(
    r'(?:עמילן|starch|corn\s*starch|potato\s*starch|tapioca|inulin)', re.IGNORECASE
)
_CH11_MALT = re.compile(r'(?:לתת|malt|malted)', re.IGNORECASE)
_CH11_GLUTEN = re.compile(r'(?:גלוטן|gluten|wheat\s*gluten)', re.IGNORECASE)


def _is_chapter_11_candidate(text):
    return bool(
        _CH11_WHEAT_FLOUR.search(text) or _CH11_CEREAL_FLOUR.search(text)
        or _CH11_GROATS.search(text) or _CH11_STARCH.search(text)
        or _CH11_MALT.search(text) or _CH11_GLUTEN.search(text)
    )


def _decide_chapter_11(product):
    """Chapter 11: Milling products; malt; starches; inulin; wheat gluten.

    11.01 — Wheat or meslin flour
    11.02 — Cereal flours (other than wheat/meslin)
    11.03 — Cereal groats, meal, pellets
    11.04 — Cereal grains otherwise worked (rolled, flaked, pearled, kibbled)
    11.05 — Flour, meal, powder, flakes of potatoes
    11.06 — Flour/meal of dried leguminous vegetables, sago, manioc
    11.07 — Malt
    11.08 — Starches; inulin
    11.09 — Wheat gluten
    """
    text = _product_text(product)

    result = {"chapter": 11, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH11_WHEAT_FLOUR.search(text):
        result["candidates"].append({
            "heading": "11.01", "subheading_hint": None, "confidence": 0.95,
            "reasoning": "Wheat/meslin flour → 11.01.",
            "rule_applied": "GIR 1 — heading 11.01",
        })
        return result

    if _CH11_GLUTEN.search(text):
        result["candidates"].append({
            "heading": "11.09", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Wheat gluten → 11.09.",
            "rule_applied": "GIR 1 — heading 11.09",
        })
        return result

    if _CH11_MALT.search(text):
        result["candidates"].append({
            "heading": "11.07", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Malt → 11.07.",
            "rule_applied": "GIR 1 — heading 11.07",
        })
        return result

    if _CH11_STARCH.search(text):
        result["candidates"].append({
            "heading": "11.08", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Starch/inulin → 11.08.",
            "rule_applied": "GIR 1 — heading 11.08",
        })
        return result

    if _CH11_CEREAL_FLOUR.search(text):
        result["candidates"].append({
            "heading": "11.02", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Cereal flour (non-wheat) → 11.02.",
            "rule_applied": "GIR 1 — heading 11.02",
        })
        return result

    if _CH11_GROATS.search(text):
        result["candidates"].append({
            "heading": "11.03", "subheading_hint": None, "confidence": 0.80,
            "reasoning": "Cereal groats/meal/pellets/semolina → 11.03.",
            "rule_applied": "GIR 1 — heading 11.03",
        })
        return result

    result["candidates"].append({
        "heading": "11.01", "subheading_hint": None, "confidence": 0.50,
        "reasoning": "Milling product — default → 11.01.",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of milling product? (wheat flour, cereal flour, starch, malt, gluten, groats)"
    )
    return result


# ============================================================================
# CHAPTER 12: Oil seeds; oleaginous fruits; industrial/medicinal plants; straw/fodder
# ============================================================================

_CH12_SOYBEAN = re.compile(r'(?:סויה|soybean|soya\s*bean)', re.IGNORECASE)
_CH12_GROUNDNUT = re.compile(
    r'(?:בוטנים|groundnut|peanut|arachis)', re.IGNORECASE
)
_CH12_SUNFLOWER = re.compile(
    r'(?:חמנייה|sunflower\s*seed|safflower|rapeseed|canola|colza)',
    re.IGNORECASE
)
_CH12_SESAME = re.compile(r'(?:שומשום|sesame)', re.IGNORECASE)
_CH12_LINSEED = re.compile(
    r'(?:פשתן|linseed|flax\s*seed|hemp\s*seed|castor\s*bean|'
    r'cotton\s*seed|poppy\s*seed)', re.IGNORECASE
)
_CH12_MEDICINAL = re.compile(
    r'(?:צמח\s*מרפא|עשב\s*תיבול|medicinal\s*plant|herbal|hop|כשות|'
    r'liquorice|ליקריץ|ginseng|ג\'ינסנג|pyrethrum)', re.IGNORECASE
)
_CH12_SEAWEED = re.compile(r'(?:אצה|אצות|seaweed|algae|kelp)', re.IGNORECASE)
_CH12_STRAW_FODDER = re.compile(
    r'(?:קש|מספוא|תחמיץ|straw|fodder|hay|silage|beet\s*pulp|'
    r'bagasse|animal\s*feed)', re.IGNORECASE
)
_CH12_OIL_SEED_GENERIC = re.compile(
    r'(?:זרע\s*שמן|גרעין|oil\s*seed|seed|kernel)', re.IGNORECASE
)


def _is_chapter_12_candidate(text):
    return bool(
        _CH12_SOYBEAN.search(text) or _CH12_GROUNDNUT.search(text)
        or _CH12_SUNFLOWER.search(text) or _CH12_SESAME.search(text)
        or _CH12_LINSEED.search(text) or _CH12_MEDICINAL.search(text)
        or _CH12_SEAWEED.search(text) or _CH12_STRAW_FODDER.search(text)
    )


def _decide_chapter_12(product):
    """Chapter 12: Oil seeds; oleaginous fruits; miscellaneous grains/seeds/fruit;
    industrial/medicinal plants; straw and fodder.

    12.01 — Soya beans
    12.02 — Groundnuts (peanuts)
    12.03 — Copra
    12.04 — Linseed, rapeseed, sunflower, other oil seeds
    12.05 — [deleted]
    12.06 — Sunflower seeds, safflower seeds
    12.07 — Other oil seeds (sesame, mustard, poppy, cotton, castor, etc.)
    12.08 — Flours/meals of oil seeds (except mustard)
    12.09 — Seeds, fruit, spores for sowing
    12.10 — Hops (cones, powder, lupulin, extract)
    12.11 — Plants for pharmacy, perfumery, insecticides
    12.12 — Locust beans, seaweed, sugar beet/cane
    12.13 — Cereal straw/husks (unprepared)
    12.14 — Swedes, mangolds, fodder roots; hay, lucerne, clover, fodder
    """
    text = _product_text(product)

    result = {"chapter": 12, "candidates": [], "redirect": None, "questions_needed": []}

    # Gate: Oil (extracted) → redirect Ch.15
    if re.search(r'(?:שמן\s*(?:סויה|חמנייה|שומשום|זית)|'
                 r'(?:soybean|sunflower|sesame|olive)\s*oil|'
                 r'vegetable\s*oil|crude\s*oil)', text, re.IGNORECASE):
        result["redirect"] = {
            "chapter": 15,
            "reason": "Extracted vegetable oil → Chapter 15 (fats and oils).",
            "rule_applied": "Chapter 12 scope — seeds/plants, not extracted oil",
        }
        return result

    seed_map = [
        (_CH12_SOYBEAN, "12.01", "Soya beans → 12.01."),
        (_CH12_GROUNDNUT, "12.02", "Groundnuts (peanuts) → 12.02."),
        (_CH12_SUNFLOWER, "12.06", "Sunflower/safflower/rapeseed seeds → 12.06."),
        (_CH12_SESAME, "12.07", "Sesame seeds → 12.07."),
        (_CH12_LINSEED, "12.04", "Linseed/flaxseed/other oil seeds → 12.04."),
        (_CH12_MEDICINAL, "12.11", "Medicinal/herbal plants → 12.11."),
        (_CH12_SEAWEED, "12.12", "Seaweed/algae → 12.12."),
        (_CH12_STRAW_FODDER, "12.14", "Straw/fodder/hay/silage → 12.14."),
    ]

    for pattern, heading, reasoning in seed_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.85,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    result["candidates"].append({
        "heading": "12.07", "subheading_hint": None, "confidence": 0.60,
        "reasoning": "Other oil seeds/plants → 12.07.",
        "rule_applied": "GIR 1 — heading 12.07",
    })
    result["questions_needed"].append(
        "What type of seed/plant? (soybean, peanut, sunflower, sesame, medicinal, seaweed, fodder)"
    )
    return result


# ============================================================================
# CHAPTER 13: Lac; gums, resins and other vegetable saps and extracts
# ============================================================================

_CH13_LAC = re.compile(r'(?:לכה|lac|shellac)', re.IGNORECASE)
_CH13_GUM_ARABIC = re.compile(
    r'(?:גומי\s*ערבי|gum\s*arabic|acacia\s*gum|tragacanth|karaya)', re.IGNORECASE
)
_CH13_NATURAL_GUM = re.compile(
    r'(?:גומי|שרף|resin|gum|oleoresin|balsam|natural\s*gum)', re.IGNORECASE
)
_CH13_PECTIN = re.compile(r'(?:פקטין|pectin|pectinate)', re.IGNORECASE)
_CH13_PLANT_EXTRACT = re.compile(
    r'(?:תמצית\s*צמח|מיץ\s*צמח|plant\s*extract|vegetable\s*sap|'
    r'aloe|opium|licorice\s*extract|henna|pyrethrum\s*extract)', re.IGNORECASE
)
_CH13_AGAR = re.compile(r'(?:אגר|agar|carrageenan|mucilage)', re.IGNORECASE)


def _is_chapter_13_candidate(text):
    return bool(
        _CH13_LAC.search(text) or _CH13_GUM_ARABIC.search(text)
        or _CH13_NATURAL_GUM.search(text) or _CH13_PECTIN.search(text)
        or _CH13_PLANT_EXTRACT.search(text) or _CH13_AGAR.search(text)
    )


def _decide_chapter_13(product):
    """Chapter 13: Lac; gums, resins; vegetable saps and extracts.

    13.01 — Lac; natural gums, resins, gum-resins, oleoresins
    13.02 — Vegetable saps/extracts; pectic substances; agar-agar; mucilages
    """
    text = _product_text(product)

    result = {"chapter": 13, "candidates": [], "redirect": None, "questions_needed": []}

    # 13.01: Lac, natural gums, resins
    if _CH13_LAC.search(text) or _CH13_GUM_ARABIC.search(text) or _CH13_NATURAL_GUM.search(text):
        result["candidates"].append({
            "heading": "13.01", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Lac/natural gum/resin/oleoresin → 13.01.",
            "rule_applied": "GIR 1 — heading 13.01",
        })
        return result

    # 13.02: Vegetable extracts, pectin, agar
    if _CH13_PECTIN.search(text) or _CH13_PLANT_EXTRACT.search(text) or _CH13_AGAR.search(text):
        result["candidates"].append({
            "heading": "13.02", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Vegetable extract/pectin/agar-agar → 13.02.",
            "rule_applied": "GIR 1 — heading 13.02",
        })
        return result

    result["candidates"].append({
        "heading": "13.01", "subheading_hint": None, "confidence": 0.55,
        "reasoning": "Gum/resin/extract product → 13.01 (default).",
        "rule_applied": "GIR 1",
    })
    return result


# ============================================================================
# CHAPTER 14: Vegetable plaiting materials; vegetable products n.e.s.
# ============================================================================

_CH14_BAMBOO = re.compile(r'(?:במבוק|bamboo)', re.IGNORECASE)
_CH14_RATTAN = re.compile(r'(?:רטן|rattan|wicker|osier|willow)', re.IGNORECASE)
_CH14_PLAITING = re.compile(
    r'(?:קליעה|plaiting|straw\s*plait|raffia|reed|rush|palm\s*leaf)',
    re.IGNORECASE
)
_CH14_VEGETABLE_PRODUCT = re.compile(
    r'(?:קפוק|kapok|vegetable\s*hair|crin|coir|piassava|istle|'
    r'broom\s*corn|cotton\s*linter)', re.IGNORECASE
)


def _is_chapter_14_candidate(text):
    return bool(
        _CH14_BAMBOO.search(text) or _CH14_RATTAN.search(text)
        or _CH14_PLAITING.search(text) or _CH14_VEGETABLE_PRODUCT.search(text)
    )


def _decide_chapter_14(product):
    """Chapter 14: Vegetable plaiting materials; vegetable products n.e.s.

    14.01 — Vegetable materials for plaiting (bamboo, rattan, reeds, rushes, etc.)
    14.04 — Vegetable products n.e.s. (cotton linters, kapok, vegetable hair, etc.)
    """
    text = _product_text(product)

    result = {"chapter": 14, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH14_BAMBOO.search(text) or _CH14_RATTAN.search(text) or _CH14_PLAITING.search(text):
        result["candidates"].append({
            "heading": "14.01", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Vegetable plaiting material (bamboo/rattan/reed) → 14.01.",
            "rule_applied": "GIR 1 — heading 14.01",
        })
        return result

    if _CH14_VEGETABLE_PRODUCT.search(text):
        result["candidates"].append({
            "heading": "14.04", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Vegetable product n.e.s. (kapok, coir, etc.) → 14.04.",
            "rule_applied": "GIR 1 — heading 14.04",
        })
        return result

    result["candidates"].append({
        "heading": "14.01", "subheading_hint": None, "confidence": 0.55,
        "reasoning": "Vegetable plaiting/product → 14.01 (default).",
        "rule_applied": "GIR 1",
    })
    return result


# ============================================================================
# CHAPTER 15: Animal or vegetable fats and oils; prepared edible fats; waxes
# ============================================================================

_CH15_ANIMAL_FAT = re.compile(
    r'(?:שומן\s*(?:חזיר|בקר|עוף|דגים)|חֵלֶב|'
    r'lard|tallow|animal\s*fat|fish\s*oil|cod\s*liver\s*oil|'
    r'pig\s*fat|poultry\s*fat|whale\s*oil)', re.IGNORECASE
)
_CH15_OLIVE_OIL = re.compile(
    r'(?:שמן\s*זית|olive\s*oil|virgin\s*olive)', re.IGNORECASE
)
_CH15_PALM_OIL = re.compile(
    r'(?:שמן\s*דקל|palm\s*oil|palm\s*kernel|coconut\s*oil|'
    r'copra\s*oil|babassu\s*oil)', re.IGNORECASE
)
_CH15_SOYBEAN_OIL = re.compile(
    r'(?:שמן\s*סויה|soybean\s*oil|soya\s*oil)', re.IGNORECASE
)
_CH15_SUNFLOWER_OIL = re.compile(
    r'(?:שמן\s*חמנייה|שמן\s*שומשום|sunflower\s*oil|safflower\s*oil|'
    r'sesame\s*oil|cotton[\s-]?seed\s*oil|rapeseed\s*oil|canola\s*oil)',
    re.IGNORECASE
)
_CH15_VEG_OIL_GENERIC = re.compile(
    r'(?:שמן\s*צמחי|vegetable\s*oil|cooking\s*oil|edible\s*oil|'
    r'corn\s*oil|rice\s*bran\s*oil|linseed\s*oil)',
    re.IGNORECASE
)
_CH15_MARGARINE = re.compile(
    r'(?:מרגרינה|margarine|shortening|edible\s*fat\s*spread)', re.IGNORECASE
)
_CH15_WAX = re.compile(
    r'(?:שעווה|שעוות\s*דבורים|wax|beeswax|paraffin\s*wax|'
    r'carnauba\s*wax|spermaceti)', re.IGNORECASE
)
_CH15_HYDROGENATED = re.compile(
    r'(?:מוקשה|hydrogenated|interesterified|re-esterified|hardened)', re.IGNORECASE
)
_CH15_REFINED = re.compile(
    r'(?:מזוקק|refined|bleached|deodorized|winterized)', re.IGNORECASE
)
_CH15_CRUDE = re.compile(r'(?:גולמי|crude|unrefined|virgin)', re.IGNORECASE)


def _is_chapter_15_candidate(text):
    return bool(
        _CH15_ANIMAL_FAT.search(text) or _CH15_OLIVE_OIL.search(text)
        or _CH15_PALM_OIL.search(text) or _CH15_SOYBEAN_OIL.search(text)
        or _CH15_SUNFLOWER_OIL.search(text) or _CH15_VEG_OIL_GENERIC.search(text)
        or _CH15_MARGARINE.search(text) or _CH15_WAX.search(text)
    )


def _decide_chapter_15(product):
    """Chapter 15: Animal/vegetable fats and oils; prepared edible fats; waxes.

    15.01 — Pig fat (lard), poultry fat (rendered)
    15.02 — Fats of bovine, sheep, goat (rendered)
    15.03 — Lard stearin, lard oil, oleostearin, oleo-oil, tallow oil
    15.04 — Fats/oils of fish or marine mammals
    15.05 — Wool grease, lanolin
    15.06 — Other animal fats and oils
    15.07 — Soybean oil
    15.08 — Groundnut oil
    15.09 — Olive oil (virgin)
    15.10 — Other olive oil; blends with virgin olive
    15.11 — Palm oil
    15.12 — Sunflower/safflower/cottonseed oil
    15.13 — Coconut/palm kernel/babassu oil
    15.14 — Rapeseed/canola/mustard oil
    15.15 — Other fixed vegetable fats/oils (linseed, corn, sesame, etc.)
    15.16 — Animal/vegetable fats, hydrogenated/interesterified
    15.17 — Margarine; edible mixtures of fats
    15.18 — Animal/vegetable fats chemically modified (oxidized, dehydrated)
    15.21 — Vegetable waxes, beeswax, spermaceti
    15.22 — Degras; residues of fatty substance treatment
    """
    text = _product_text(product)

    result = {"chapter": 15, "candidates": [], "redirect": None, "questions_needed": []}

    # Wax → 15.21
    if _CH15_WAX.search(text):
        result["candidates"].append({
            "heading": "15.21", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Wax (beeswax/vegetable wax) → 15.21.",
            "rule_applied": "GIR 1 — heading 15.21",
        })
        return result

    # Margarine/edible fat spreads → 15.17
    if _CH15_MARGARINE.search(text):
        result["candidates"].append({
            "heading": "15.17", "subheading_hint": None, "confidence": 0.90,
            "reasoning": "Margarine/edible fat spread → 15.17.",
            "rule_applied": "GIR 1 — heading 15.17",
        })
        return result

    # Hydrogenated → 15.16
    if _CH15_HYDROGENATED.search(text):
        result["candidates"].append({
            "heading": "15.16", "subheading_hint": None, "confidence": 0.85,
            "reasoning": "Hydrogenated/interesterified fat or oil → 15.16.",
            "rule_applied": "GIR 1 — heading 15.16",
        })
        return result

    # Specific oils
    oil_map = [
        (_CH15_ANIMAL_FAT, "15.01", "Animal fat (lard/tallow/fish oil) → 15.01/15.02/15.04."),
        (_CH15_OLIVE_OIL, "15.09", "Olive oil → 15.09."),
        (_CH15_SOYBEAN_OIL, "15.07", "Soybean oil → 15.07."),
        (_CH15_PALM_OIL, "15.11", "Palm oil → 15.11."),
        (_CH15_SUNFLOWER_OIL, "15.12", "Sunflower/safflower/sesame/cottonseed oil → 15.12."),
    ]

    for pattern, heading, reasoning in oil_map:
        if pattern.search(text):
            result["candidates"].append({
                "heading": heading, "subheading_hint": None, "confidence": 0.85,
                "reasoning": reasoning,
                "rule_applied": f"GIR 1 — heading {heading}",
            })
            return result

    # Generic vegetable oil → 15.15
    if _CH15_VEG_OIL_GENERIC.search(text):
        result["candidates"].append({
            "heading": "15.15", "subheading_hint": None, "confidence": 0.75,
            "reasoning": "Other vegetable oil → 15.15.",
            "rule_applied": "GIR 1 — heading 15.15",
        })
        return result

    result["candidates"].append({
        "heading": "15.15", "subheading_hint": None, "confidence": 0.55,
        "reasoning": "Fat/oil product → 15.15 (default).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of fat/oil? (animal fat, olive oil, palm oil, soybean oil, margarine, wax)"
    )
    return result


# ============================================================================
# PUBLIC API — dispatches to the right chapter tree
# ============================================================================

# Registry of chapter decision trees
_CHAPTER_TREES = {
    1: _decide_chapter_01,
    2: _decide_chapter_02,
    3: _decide_chapter_03,
    4: _decide_chapter_04,
    5: _decide_chapter_05,
    6: _decide_chapter_06,
    7: _decide_chapter_07,
    8: _decide_chapter_08,
    9: _decide_chapter_09,
    10: _decide_chapter_10,
    11: _decide_chapter_11,
    12: _decide_chapter_12,
    13: _decide_chapter_13,
    14: _decide_chapter_14,
    15: _decide_chapter_15,
}


def decide_chapter(product):
    """Route a product through chapter-specific decision tree if one exists.

    Args:
        product: dict from Layer 0 with name, physical, essence, function,
                 transformation_stage, processing_state, dominant_material_pct.

    Returns:
        Decision tree result dict, or None if no tree matches.
        Result: {chapter, candidates, redirect, questions_needed}
    """
    text = _product_text(product)

    # Check each chapter's candidate detection in order
    for ch_num, detect_fn, tree_fn in _CHAPTER_DETECT_ORDER:
        if detect_fn(text):
            return tree_fn(product)

    return None


def _is_chapter_03_candidate(text):
    """Check if product text suggests Chapter 03 (fish/seafood)."""
    return bool(
        _FISH_WORDS.search(text)
        or _CRUSTACEAN_WORDS.search(text)
        or _MOLLUSC_WORDS.search(text)
        or _OTHER_INVERT_WORDS.search(text)
        or _FLOUR_MEAL_WORDS.search(text)
    )


# Ordered detection list — checked sequentially, first match wins.
# More specific chapters checked before generic ones.
_CHAPTER_DETECT_ORDER = [
    (1, _is_chapter_01_candidate, _decide_chapter_01),
    (2, _is_chapter_02_candidate, _decide_chapter_02),
    (3, _is_chapter_03_candidate, _decide_chapter_03),
    (4, _is_chapter_04_candidate, _decide_chapter_04),
    (5, _is_chapter_05_candidate, _decide_chapter_05),
    (6, _is_chapter_06_candidate, _decide_chapter_06),
    (7, _is_chapter_07_candidate, _decide_chapter_07),
    (8, _is_chapter_08_candidate, _decide_chapter_08),
    (9, _is_chapter_09_candidate, _decide_chapter_09),
    (10, _is_chapter_10_candidate, _decide_chapter_10),
    (11, _is_chapter_11_candidate, _decide_chapter_11),
    (12, _is_chapter_12_candidate, _decide_chapter_12),
    (13, _is_chapter_13_candidate, _decide_chapter_13),
    (14, _is_chapter_14_candidate, _decide_chapter_14),
    (15, _is_chapter_15_candidate, _decide_chapter_15),
]


def available_chapters():
    """Return list of chapter numbers that have decision trees."""
    return sorted(_CHAPTER_TREES.keys())
