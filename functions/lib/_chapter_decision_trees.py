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
# PUBLIC API — dispatches to the right chapter tree
# ============================================================================

# Registry of chapter decision trees
_CHAPTER_TREES = {
    1: _decide_chapter_01,
    2: _decide_chapter_02,
    3: _decide_chapter_03,
    4: _decide_chapter_04,
    5: _decide_chapter_05,
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
    if _is_chapter_01_candidate(text):
        return _decide_chapter_01(product)
    if _is_chapter_02_candidate(text):
        return _decide_chapter_02(product)
    if _is_chapter_03_candidate(text):
        return _decide_chapter_03(product)
    if _is_chapter_04_candidate(text):
        return _decide_chapter_04(product)
    if _is_chapter_05_candidate(text):
        return _decide_chapter_05(product)

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


def available_chapters():
    """Return list of chapter numbers that have decision trees."""
    return sorted(_CHAPTER_TREES.keys())
