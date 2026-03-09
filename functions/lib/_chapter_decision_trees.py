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
# CHAPTER 16: Preparations of meat, fish, crustaceans, molluscs
# ============================================================================

_CH16_SAUSAGE = re.compile(
    r'(?:נקניק|נקניקי|סלמי|פפרוני|מורטדלה|קבנוס|'
    r'sausage|salami|pepperoni|mortadella|chorizo|frankfurter|hot\s*dog|'
    r'bratwurst|bologna|wiener|kielbasa)',
    re.IGNORECASE
)

_CH16_MEAT_EXTRACT = re.compile(
    r'(?:תמצית\s*בשר|מרק\s*בשר|meat\s*extract|meat\s*juice|bouillon|'
    r'broth\s*concentrate)',
    re.IGNORECASE
)

_CH16_PREPARED_MEAT = re.compile(
    r'(?:שימורי?\s*בשר|בשר\s*משומר|נתחי\s*בשר\s*מבושל|קורנד?\s*ביף|'
    r'canned\s*meat|corned\s*beef|pâté|pate|tinned\s*meat|'
    r'prepared\s*meat|preserved\s*meat|cooked\s*ham|luncheon\s*meat|spam)',
    re.IGNORECASE
)

_CH16_PREPARED_FISH = re.compile(
    r'(?:שימורי?\s*דג|דג\s*משומר|טונה\s*בשמן|סרדין\s*בשמן|'
    r'canned\s*fish|canned\s*tuna|canned\s*salmon|canned\s*sardine|'
    r'prepared\s*fish|preserved\s*fish|fish\s*stick|fish\s*finger|surimi|'
    r'fish\s*paste|fish\s*ball|gefilte\s*fish)',
    re.IGNORECASE
)

_CH16_PREPARED_CRUSTACEAN = re.compile(
    r'(?:שימורי?\s*(?:שרימפס|סרטן|לובסטר)|'
    r'canned\s*(?:shrimp|crab|lobster)|prepared\s*(?:shrimp|crab|lobster|crustacean)|'
    r'shrimp\s*paste|crab\s*paste)',
    re.IGNORECASE
)

_CH16_CAVIAR = re.compile(
    r'(?:קוויאר|ביצי\s*דג|caviar|roe|fish\s*eggs)',
    re.IGNORECASE
)


def _detect_ch16_product_type(text):
    """Detect product type for Chapter 16 routing."""
    if _CH16_CAVIAR.search(text):
        return "caviar"
    if _CH16_SAUSAGE.search(text):
        return "sausage"
    if _CH16_MEAT_EXTRACT.search(text):
        return "meat_extract"
    if _CH16_PREPARED_CRUSTACEAN.search(text):
        return "prepared_crustacean"
    if _CH16_PREPARED_FISH.search(text):
        return "prepared_fish"
    if _CH16_PREPARED_MEAT.search(text):
        return "prepared_meat"
    # Check general fish/meat signals for fallback
    if _FISH_WORDS.search(text) or _CRUSTACEAN_WORDS.search(text) or _MOLLUSC_WORDS.search(text):
        return "prepared_fish"
    if _CH01_BOVINE.search(text) or _CH01_SWINE.search(text) or _CH01_POULTRY.search(text):
        return "prepared_meat"
    return "unknown"


def _is_chapter_16_candidate(text):
    """Check if product text suggests Chapter 16 (preparations of meat/fish)."""
    return bool(
        _CH16_SAUSAGE.search(text)
        or _CH16_MEAT_EXTRACT.search(text)
        or _CH16_PREPARED_MEAT.search(text)
        or _CH16_PREPARED_FISH.search(text)
        or _CH16_PREPARED_CRUSTACEAN.search(text)
        or _CH16_CAVIAR.search(text)
        or _COMPOUND_SIGNALS.search(text) and (
            _FISH_WORDS.search(text) or _CRUSTACEAN_WORDS.search(text)
            or _CH01_BOVINE.search(text) or _CH01_SWINE.search(text)
            or _CH01_POULTRY.search(text)
        )
    )


def _decide_chapter_16(product):
    """Chapter 16 decision tree: Preparations of meat, fish, crustaceans, molluscs.

    Headings:
        16.01 — Sausages and similar; food preparations based thereon
        16.02 — Other prepared or preserved meat, offal, blood
        16.03 — Extracts and juices of meat, fish, crustaceans
        16.04 — Prepared or preserved fish; caviar and caviar substitutes
        16.05 — Crustaceans, molluscs etc. prepared or preserved
    """
    text = _product_text(product)
    prod_type = _detect_ch16_product_type(text)

    result = {
        "chapter": 16,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    type_to_heading = {
        "sausage": ("16.01", "Sausage/similar products → 16.01."),
        "prepared_meat": ("16.02", "Prepared/preserved meat → 16.02."),
        "meat_extract": ("16.03", "Meat/fish extract or juice → 16.03."),
        "prepared_fish": ("16.04", "Prepared/preserved fish → 16.04."),
        "caviar": ("16.04", "Caviar/fish roe → 16.04."),
        "prepared_crustacean": ("16.05", "Prepared/preserved crustacean/mollusc → 16.05."),
    }

    if prod_type in type_to_heading:
        heading, reasoning = type_to_heading[prod_type]
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    # Unknown
    result["candidates"].append({
        "heading": "16.02",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Prepared meat/fish product type unknown → 16.02 (catch-all prepared meat).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of preparation? (sausage, canned meat, canned fish, caviar, prepared crustacean)"
    )
    return result


# ============================================================================
# CHAPTER 17: Sugars and sugar confectionery
# ============================================================================

_CH17_CANE_BEET = re.compile(
    r'(?:סוכר\s*(?:קנה|סלק|לבן|גולמי|חום)|'
    r'cane\s*sugar|beet\s*sugar|raw\s*sugar|refined\s*sugar|white\s*sugar|'
    r'brown\s*sugar|granulated\s*sugar|icing\s*sugar|caster\s*sugar|sucrose)',
    re.IGNORECASE
)

_CH17_MOLASSES = re.compile(
    r'(?:מולסה|דבש\s*(?:קנה|סלק)|treacle|molasses|'
    r'sugar\s*syrup\s*(?:colouring|coloring))',
    re.IGNORECASE
)

_CH17_MAPLE_GLUCOSE = re.compile(
    r'(?:מייפל|גלוקוז|פרוקטוז|לקטוז|מלטוז|'
    r'maple\s*(?:syrup|sugar)|glucose|fructose|lactose|maltose|'
    r'dextrose|invert\s*sugar|isoglucose|sugar\s*syrup)',
    re.IGNORECASE
)

_CH17_CANDY = re.compile(
    r'(?:סוכריה|סוכריות|ממתק|ממתקים|טופי|מרשמלו|גומי\s*דובים|מסטיק\s*סוכר|'
    r'candy|candies|confectionery|sweet|toffee|caramel|fudge|nougat|'
    r'marshmallow|gummy|jelly\s*bean|lollipop|bonbon|pastille|'
    r'sugar\s*coated|dragee|chewing\s*gum\s*(?:sugar|not)|halva|halwa|halvah)',
    re.IGNORECASE
)

_CH17_CHOCOLATE = re.compile(
    r'(?:שוקולד|chocolate|cocoa\s*(?:preparation|drink))',
    re.IGNORECASE
)


def _is_chapter_17_candidate(text):
    """Check if product text suggests Chapter 17 (sugars/confectionery)."""
    return bool(
        _CH17_CANE_BEET.search(text)
        or _CH17_MOLASSES.search(text)
        or _CH17_MAPLE_GLUCOSE.search(text)
        or _CH17_CANDY.search(text)
    )


def _decide_chapter_17(product):
    """Chapter 17 decision tree: Sugars and sugar confectionery.

    Headings:
        17.01 — Cane or beet sugar (solid)
        17.02 — Other sugars (lactose, maple, glucose, fructose, etc.)
        17.03 — Molasses
        17.04 — Sugar confectionery (not containing cocoa)
    """
    text = _product_text(product)

    result = {
        "chapter": 17,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # Gate: Chocolate confectionery → Chapter 18
    if _CH17_CHOCOLATE.search(text):
        result["redirect"] = {
            "chapter": 18,
            "reason": "Contains chocolate/cocoa — sugar confectionery with cocoa → Chapter 18.",
            "rule_applied": "Chapter 17 Note: excludes confectionery containing cocoa (→ 18.06)",
        }
        return result

    if _CH17_CANDY.search(text):
        result["candidates"].append({
            "heading": "17.04",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Sugar confectionery (not containing cocoa) → 17.04.",
            "rule_applied": "GIR 1 — heading 17.04",
        })
        return result

    if _CH17_MOLASSES.search(text):
        result["candidates"].append({
            "heading": "17.03",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Molasses from sugar extraction → 17.03.",
            "rule_applied": "GIR 1 — heading 17.03",
        })
        return result

    if _CH17_MAPLE_GLUCOSE.search(text):
        result["candidates"].append({
            "heading": "17.02",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Other sugars (glucose/fructose/lactose/maple) → 17.02.",
            "rule_applied": "GIR 1 — heading 17.02",
        })
        return result

    if _CH17_CANE_BEET.search(text):
        result["candidates"].append({
            "heading": "17.01",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cane or beet sugar in solid form → 17.01.",
            "rule_applied": "GIR 1 — heading 17.01",
        })
        return result

    # Unknown sugar product
    result["candidates"].append({
        "heading": "17.01",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Sugar product, type unclear → 17.01 (default).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of sugar product? (cane/beet sugar, glucose/fructose, molasses, confectionery)"
    )
    return result


# ============================================================================
# CHAPTER 18: Cocoa and cocoa preparations
# ============================================================================

_CH18_COCOA_BEAN = re.compile(
    r'(?:פולי?\s*קקאו|cocoa\s*bean|cacao\s*bean|raw\s*cocoa)',
    re.IGNORECASE
)

_CH18_COCOA_SHELL = re.compile(
    r'(?:קליפת?\s*קקאו|cocoa\s*(?:shell|husk|skin|waste))',
    re.IGNORECASE
)

_CH18_COCOA_PASTE = re.compile(
    r'(?:משחת?\s*קקאו|ליקור\s*קקאו|cocoa\s*(?:paste|liquor|mass)|'
    r'chocolate\s*liquor)',
    re.IGNORECASE
)

_CH18_COCOA_BUTTER = re.compile(
    r'(?:חמאת?\s*קקאו|שומן\s*קקאו|cocoa\s*butter|cocoa\s*fat|'
    r'cocoa\s*oil)',
    re.IGNORECASE
)

_CH18_COCOA_POWDER = re.compile(
    r'(?:אבקת?\s*קקאו|cocoa\s*powder)',
    re.IGNORECASE
)

_CH18_CHOCOLATE = re.compile(
    r'(?:שוקולד|טבלת?\s*שוקולד|פרלין|'
    r'chocolate|praline|chocolate\s*bar|couverture|'
    r'chocolate\s*spread|chocolate\s*chip)',
    re.IGNORECASE
)

_CH18_COCOA_GENERAL = re.compile(
    r'(?:קקאו|cocoa|cacao)',
    re.IGNORECASE
)


def _is_chapter_18_candidate(text):
    """Check if product text suggests Chapter 18 (cocoa/chocolate)."""
    return bool(
        _CH18_COCOA_GENERAL.search(text)
        or _CH18_CHOCOLATE.search(text)
    )


def _decide_chapter_18(product):
    """Chapter 18 decision tree: Cocoa and cocoa preparations.

    Headings:
        18.01 — Cocoa beans, whole or broken, raw or roasted
        18.02 — Cocoa shells, husks, skins, waste
        18.03 — Cocoa paste, defatted or not
        18.04 — Cocoa butter, fat, oil
        18.05 — Cocoa powder (unsweetened)
        18.06 — Chocolate and other food preparations containing cocoa
    """
    text = _product_text(product)

    result = {
        "chapter": 18,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH18_COCOA_BEAN.search(text):
        result["candidates"].append({
            "heading": "18.01",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cocoa beans, whole or broken → 18.01.",
            "rule_applied": "GIR 1 — heading 18.01",
        })
        return result

    if _CH18_COCOA_SHELL.search(text):
        result["candidates"].append({
            "heading": "18.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cocoa shells/husks/waste → 18.02.",
            "rule_applied": "GIR 1 — heading 18.02",
        })
        return result

    if _CH18_COCOA_PASTE.search(text):
        result["candidates"].append({
            "heading": "18.03",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Cocoa paste/liquor → 18.03.",
            "rule_applied": "GIR 1 — heading 18.03",
        })
        return result

    if _CH18_COCOA_BUTTER.search(text):
        result["candidates"].append({
            "heading": "18.04",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cocoa butter/fat/oil → 18.04.",
            "rule_applied": "GIR 1 — heading 18.04",
        })
        return result

    if _CH18_COCOA_POWDER.search(text):
        result["candidates"].append({
            "heading": "18.05",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Cocoa powder (unsweetened) → 18.05.",
            "rule_applied": "GIR 1 — heading 18.05",
        })
        return result

    if _CH18_CHOCOLATE.search(text):
        result["candidates"].append({
            "heading": "18.06",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Chocolate/food preparation containing cocoa → 18.06.",
            "rule_applied": "GIR 1 — heading 18.06",
        })
        return result

    # General cocoa reference — need more info
    result["candidates"].append({
        "heading": "18.06",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Cocoa product, form unclear → 18.06 (most common).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What form is the cocoa product? (beans, shells, paste, butter, powder, chocolate)"
    )
    return result


# ============================================================================
# CHAPTER 19: Preparations of cereals, flour, starch, or milk; pastrycooks' products
# ============================================================================

_CH19_PASTA = re.compile(
    r'(?:פסטה|אטריות|ספגטי|מקרוני|לזניה|רביולי|ניוקי|'
    r'pasta|spaghetti|macaroni|noodle|lasagna|ravioli|tortellini|'
    r'gnocchi|vermicelli|fettuccine|penne|fusilli|couscous)',
    re.IGNORECASE
)

_CH19_BREAD = re.compile(
    r'(?:לחם|חלה|פיתה|באגט|לחמניה|טוסט|'
    r'bread|loaf|pita|baguette|roll|toast|flatbread|naan|ciabatta|'
    r'sourdough|rye\s*bread|white\s*bread|whole\s*wheat\s*bread)',
    re.IGNORECASE
)

_CH19_PASTRY = re.compile(
    r'(?:עוגה|עוגות|מאפה|מאפים|קרואסון|דונאט|בורקס|'
    r'cake|pastry|croissant|donut|doughnut|muffin|cookie|biscuit|'
    r'wafer|pie|tart|danish|scone|brioche|strudel|baklava|'
    r'puff\s*pastry|phyllo|filo)',
    re.IGNORECASE
)

_CH19_BREAKFAST_CEREAL = re.compile(
    r'(?:קורנפלקס|דגני\s*בוקר|גרנולה|מוזלי|שיבולת\s*שועל|'
    r'cornflakes|corn\s*flakes|breakfast\s*cereal|granola|muesli|'
    r'oat\s*flakes|puffed\s*rice|cereal\s*bar|ready.to.eat\s*cereal)',
    re.IGNORECASE
)

_CH19_PIZZA = re.compile(
    r'(?:פיצה|pizza|quiche|calzone)',
    re.IGNORECASE
)

_CH19_INFANT_FOOD = re.compile(
    r'(?:מזון\s*תינוקות|דייסת?\s*תינוקות|baby\s*food|infant\s*(?:food|cereal)|'
    r'follow.on\s*formula)',
    re.IGNORECASE
)

_CH19_MALT_EXTRACT = re.compile(
    r'(?:תמצית\s*לתת|malt\s*extract|malt\s*preparation)',
    re.IGNORECASE
)


def _is_chapter_19_candidate(text):
    """Check if product text suggests Chapter 19 (cereal/flour preparations)."""
    return bool(
        _CH19_PASTA.search(text) or _CH19_BREAD.search(text)
        or _CH19_PASTRY.search(text) or _CH19_BREAKFAST_CEREAL.search(text)
        or _CH19_PIZZA.search(text) or _CH19_INFANT_FOOD.search(text)
        or _CH19_MALT_EXTRACT.search(text)
    )


def _decide_chapter_19(product):
    """Chapter 19 decision tree: Preparations of cereals, flour, starch, or milk.

    Headings:
        19.01 — Malt extract; food preparations of flour/starch/malt extract (infant food etc.)
        19.02 — Pasta (uncooked, cooked, stuffed, couscous)
        19.04 — Prepared foods from cereals (cornflakes, muesli, puffed rice, etc.)
        19.05 — Bread, pastry, cakes, biscuits, pizza, wafers, etc.
    """
    text = _product_text(product)

    result = {
        "chapter": 19,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH19_PASTA.search(text):
        result["candidates"].append({
            "heading": "19.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Pasta/noodles/couscous → 19.02.",
            "rule_applied": "GIR 1 — heading 19.02",
        })
        return result

    if _CH19_BREAKFAST_CEREAL.search(text):
        result["candidates"].append({
            "heading": "19.04",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Breakfast cereal/granola/oat flakes → 19.04.",
            "rule_applied": "GIR 1 — heading 19.04",
        })
        return result

    if _CH19_INFANT_FOOD.search(text) or _CH19_MALT_EXTRACT.search(text):
        result["candidates"].append({
            "heading": "19.01",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Malt extract / infant food preparation → 19.01.",
            "rule_applied": "GIR 1 — heading 19.01",
        })
        return result

    if _CH19_BREAD.search(text) or _CH19_PASTRY.search(text) or _CH19_PIZZA.search(text):
        result["candidates"].append({
            "heading": "19.05",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Bread/pastry/cake/biscuit/pizza/wafer → 19.05.",
            "rule_applied": "GIR 1 — heading 19.05",
        })
        return result

    # Unknown cereal preparation
    result["candidates"].append({
        "heading": "19.05",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Cereal/flour preparation, type unclear → 19.05 (default).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of cereal/flour preparation? (pasta, bread, pastry, breakfast cereal, infant food)"
    )
    return result


# ============================================================================
# CHAPTER 20: Preparations of vegetables, fruit, nuts, or other parts of plants
# ============================================================================

_CH20_TOMATO_PREP = re.compile(
    r'(?:רסק\s*עגבני|רוטב\s*עגבני|קטשופ|'
    r'tomato\s*(?:paste|puree|purée|sauce|ketchup|concentrate)|ketchup)',
    re.IGNORECASE
)

_CH20_JUICE = re.compile(
    r'(?:מיץ\s*(?:תפוחים|תפוזים|ענבים|אשכולית|לימון|גזר|רימונים|פירות)|'
    r'(?:apple|orange|grape|grapefruit|lemon|pineapple|tomato|mango|'
    r'cranberry|pomegranate|guava|fruit)\s*juice|'
    r'juice\s*(?:concentrate|not\s*fermented))',
    re.IGNORECASE
)

_CH20_JAM = re.compile(
    r'(?:ריבה|ריבת|מרמלדה|ג\'לי\s*פירות|'
    r'jam|marmalade|jelly\s*(?:fruit|preserve)|fruit\s*(?:preserve|spread|butter))',
    re.IGNORECASE
)

_CH20_PICKLED = re.compile(
    r'(?:כבוש|כבושים|חמוצים|מלפפון\s*חמוץ|זית\s*(?:כבוש|מרינד)|'
    r'pickle|pickled|gherkin|olive\s*(?:in\s*brine|pickled|marinated)|'
    r'sauerkraut|kimchi|caper)',
    re.IGNORECASE
)

_CH20_FROZEN_VEG = re.compile(
    r'(?:ירקות\s*(?:קפואים|מוקפאים)|פירות\s*(?:קפואים|מוקפאים)|'
    r'frozen\s*(?:vegetables|fruit|berries|peas|corn|spinach|mixed\s*veg))',
    re.IGNORECASE
)

_CH20_CANNED_VEG = re.compile(
    r'(?:שימורי?\s*(?:ירקות|פירות|תירס|אפונה|שעועית)|'
    r'canned\s*(?:vegetables|fruit|corn|peas|beans|peach|pear|pineapple|'
    r'mushroom|asparagus|artichoke)|tinned\s*(?:vegetables|fruit))',
    re.IGNORECASE
)

_CH20_NUT_PREP = re.compile(
    r'(?:חמאת?\s*(?:בוטנים|שקדים)|'
    r'peanut\s*butter|almond\s*butter|nut\s*butter|nut\s*paste|'
    r'roasted\s*(?:peanuts|cashews|almonds|nuts)\s*(?:salted|flavored|flavoured)?)',
    re.IGNORECASE
)


def _is_chapter_20_candidate(text):
    """Check if product text suggests Chapter 20 (veg/fruit preparations)."""
    return bool(
        _CH20_TOMATO_PREP.search(text) or _CH20_JUICE.search(text)
        or _CH20_JAM.search(text) or _CH20_PICKLED.search(text)
        or _CH20_FROZEN_VEG.search(text) or _CH20_CANNED_VEG.search(text)
        or _CH20_NUT_PREP.search(text)
    )


def _decide_chapter_20(product):
    """Chapter 20 decision tree: Preparations of vegetables, fruit, nuts.

    Headings:
        20.01 — Vegetables, fruit, nuts prepared by vinegar/acetic acid
        20.02 — Tomatoes prepared or preserved (not by vinegar)
        20.03 — Mushrooms, truffles prepared or preserved
        20.04 — Other vegetables prepared or preserved (frozen)
        20.05 — Other vegetables prepared or preserved (not frozen)
        20.06 — Vegetables, fruit, nuts preserved by sugar (glacé)
        20.07 — Jams, jellies, marmalades, purées, pastes
        20.08 — Fruit, nuts otherwise prepared or preserved (peanut butter, etc.)
        20.09 — Fruit/vegetable juices, unfermented, no added spirits
    """
    text = _product_text(product)

    result = {
        "chapter": 20,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH20_JUICE.search(text):
        result["candidates"].append({
            "heading": "20.09",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Fruit/vegetable juice (unfermented) → 20.09.",
            "rule_applied": "GIR 1 — heading 20.09",
        })
        return result

    if _CH20_TOMATO_PREP.search(text):
        result["candidates"].append({
            "heading": "20.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Tomato paste/puree/sauce/ketchup → 20.02.",
            "rule_applied": "GIR 1 — heading 20.02",
        })
        return result

    if _CH20_JAM.search(text):
        result["candidates"].append({
            "heading": "20.07",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Jam/marmalade/fruit jelly/fruit purée → 20.07.",
            "rule_applied": "GIR 1 — heading 20.07",
        })
        return result

    if _CH20_PICKLED.search(text):
        result["candidates"].append({
            "heading": "20.01",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Vegetables/fruit pickled or preserved by vinegar → 20.01.",
            "rule_applied": "GIR 1 — heading 20.01",
        })
        return result

    if _CH20_NUT_PREP.search(text):
        result["candidates"].append({
            "heading": "20.08",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Fruit/nuts otherwise prepared (peanut butter, roasted nuts) → 20.08.",
            "rule_applied": "GIR 1 — heading 20.08",
        })
        return result

    if _CH20_FROZEN_VEG.search(text):
        result["candidates"].append({
            "heading": "20.04",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Frozen vegetables/fruit prepared or preserved → 20.04.",
            "rule_applied": "GIR 1 — heading 20.04",
        })
        return result

    if _CH20_CANNED_VEG.search(text):
        result["candidates"].append({
            "heading": "20.05",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Canned/preserved vegetables (not frozen) → 20.05.",
            "rule_applied": "GIR 1 — heading 20.05",
        })
        return result

    # Unknown
    result["candidates"].append({
        "heading": "20.05",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Vegetable/fruit preparation, type unclear → 20.05.",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of veg/fruit preparation? (juice, tomato paste, jam, pickled, canned, frozen, nut butter)"
    )
    return result


# ============================================================================
# CHAPTER 21: Miscellaneous edible preparations
# ============================================================================

_CH21_SOUP_BROTH = re.compile(
    r'(?:מרק|ציר|soup|broth|stock\s*cube|bouillon\s*cube)',
    re.IGNORECASE
)

_CH21_SAUCE_CONDIMENT = re.compile(
    r'(?:רוטב|חרדל|מיונז|טחינה|חומוס|סויה|'
    r'sauce|mustard|mayonnaise|tahini|hummus|soy\s*sauce|'
    r'worcestershire|barbecue\s*sauce|hot\s*sauce|vinaigrette|'
    r'salad\s*dressing|condiment)',
    re.IGNORECASE
)

_CH21_ICE_CREAM = re.compile(
    r'(?:גלידה|סורבה|שרבט\s*(?:קפוא|קרח)|'
    r'ice\s*cream|gelato|sorbet|frozen\s*(?:yogurt|dessert)|sherbet)',
    re.IGNORECASE
)

_CH21_YEAST = re.compile(
    r'(?:שמרים|שמר|yeast|baking\s*powder|baking\s*soda)',
    re.IGNORECASE
)

_CH21_PROTEIN_CONCENTRATE = re.compile(
    r'(?:חלבון\s*(?:סויה|אפונה|מי\s*גבינה)|'
    r'(?:soy|pea|whey)\s*protein\s*(?:concentrate|isolate)|'
    r'textured\s*(?:vegetable|soy)\s*protein|TVP)',
    re.IGNORECASE
)

_CH21_INSTANT_BEV = re.compile(
    r'(?:קפה\s*(?:נמס|מיידי)|קקאו\s*(?:נמס|מיידי)|'
    r'instant\s*(?:coffee|cocoa|tea)|coffee\s*(?:mix|substitute)|'
    r'chicory\s*(?:roasted|extract))',
    re.IGNORECASE
)

_CH21_FOOD_PREP_NES = re.compile(
    r'(?:תוסף\s*(?:מזון|תזונה)|אבקת\s*(?:מזון|שייק)|'
    r'food\s*(?:supplement|preparation)|meal\s*replacement|'
    r'nutritional\s*(?:supplement|drink|shake))',
    re.IGNORECASE
)


def _is_chapter_21_candidate(text):
    """Check if product text suggests Chapter 21 (misc food preparations)."""
    return bool(
        _CH21_SOUP_BROTH.search(text) or _CH21_SAUCE_CONDIMENT.search(text)
        or _CH21_ICE_CREAM.search(text) or _CH21_YEAST.search(text)
        or _CH21_INSTANT_BEV.search(text) or _CH21_FOOD_PREP_NES.search(text)
        or _CH21_PROTEIN_CONCENTRATE.search(text)
    )


def _decide_chapter_21(product):
    """Chapter 21 decision tree: Miscellaneous edible preparations.

    Headings:
        21.01 — Extracts of coffee/tea/maté; chicory; concentrates
        21.02 — Yeasts; baking powders
        21.03 — Sauces, condiments, mustard, ketchup (prepared)
        21.04 — Soups, broths, preparations therefor
        21.05 — Ice cream and other edible ice
        21.06 — Food preparations n.e.s. (protein concentrates, supplements, etc.)
    """
    text = _product_text(product)

    result = {
        "chapter": 21,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH21_ICE_CREAM.search(text):
        result["candidates"].append({
            "heading": "21.05",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Ice cream/gelato/sorbet/frozen dessert → 21.05.",
            "rule_applied": "GIR 1 — heading 21.05",
        })
        return result

    if _CH21_INSTANT_BEV.search(text):
        result["candidates"].append({
            "heading": "21.01",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Instant coffee/cocoa/tea/chicory → 21.01.",
            "rule_applied": "GIR 1 — heading 21.01",
        })
        return result

    if _CH21_YEAST.search(text):
        result["candidates"].append({
            "heading": "21.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Yeast/baking powder → 21.02.",
            "rule_applied": "GIR 1 — heading 21.02",
        })
        return result

    if _CH21_SAUCE_CONDIMENT.search(text):
        result["candidates"].append({
            "heading": "21.03",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Sauce/condiment/mustard/mayonnaise → 21.03.",
            "rule_applied": "GIR 1 — heading 21.03",
        })
        return result

    if _CH21_SOUP_BROTH.search(text):
        result["candidates"].append({
            "heading": "21.04",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Soup/broth/stock/bouillon → 21.04.",
            "rule_applied": "GIR 1 — heading 21.04",
        })
        return result

    if _CH21_PROTEIN_CONCENTRATE.search(text) or _CH21_FOOD_PREP_NES.search(text):
        result["candidates"].append({
            "heading": "21.06",
            "subheading_hint": None,
            "confidence": 0.80,
            "reasoning": "Food preparation n.e.s. / protein concentrate / supplement → 21.06.",
            "rule_applied": "GIR 1 — heading 21.06",
        })
        return result

    # Unknown
    result["candidates"].append({
        "heading": "21.06",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Miscellaneous food preparation, type unclear → 21.06.",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of food preparation? (sauce, soup, ice cream, yeast, instant coffee, supplement)"
    )
    return result


# ============================================================================
# CHAPTER 22: Beverages, spirits, and vinegar
# ============================================================================

_CH22_WATER = re.compile(
    r'(?:מים\s*(?:מינרליים|מוגזים|שתייה)|'
    r'mineral\s*water|sparkling\s*water|drinking\s*water|'
    r'spring\s*water|soda\s*water|tonic\s*water)',
    re.IGNORECASE
)

_CH22_SOFT_DRINK = re.compile(
    r'(?:משקה\s*(?:קל|מוגז|ממותק)|'
    r'soft\s*drink|carbonated\s*(?:drink|beverage)|cola|'
    r'lemonade|energy\s*drink|sports\s*drink)',
    re.IGNORECASE
)

_CH22_BEER = re.compile(
    r'(?:בירה|beer|ale|lager|stout|porter|malt\s*beer)',
    re.IGNORECASE
)

_CH22_WINE = re.compile(
    r'(?:יין|wine|champagne|prosecco|cava|vermouth|'
    r'grape\s*must|port\s*wine|sherry|marsala)',
    re.IGNORECASE
)

_CH22_CIDER = re.compile(
    r'(?:סיידר|מיד|perry|cider|mead)',
    re.IGNORECASE
)

_CH22_SPIRITS = re.compile(
    r'(?:וודקה|וויסקי|ג\'ין|רום|טקילה|ברנדי|קוניאק|ליקר|ערק|עראק|'
    r'vodka|whisky|whiskey|gin|rum|tequila|brandy|cognac|liqueur|'
    r'arak|ouzo|grappa|absinthe|mezcal|sambuca|schnapps|'
    r'spirit|distilled|ethyl\s*alcohol)',
    re.IGNORECASE
)

_CH22_VINEGAR = re.compile(
    r'(?:חומץ|vinegar|acetic\s*acid\s*(?:for\s*food|edible))',
    re.IGNORECASE
)

_CH22_FERMENTED = re.compile(
    r'(?:מותסס|fermented|kombucha|kefir\s*drink|kvass)',
    re.IGNORECASE
)


def _is_chapter_22_candidate(text):
    """Check if product text suggests Chapter 22 (beverages/spirits/vinegar)."""
    return bool(
        _CH22_WATER.search(text) or _CH22_SOFT_DRINK.search(text)
        or _CH22_BEER.search(text) or _CH22_WINE.search(text)
        or _CH22_SPIRITS.search(text) or _CH22_VINEGAR.search(text)
        or _CH22_CIDER.search(text) or _CH22_FERMENTED.search(text)
    )


def _decide_chapter_22(product):
    """Chapter 22 decision tree: Beverages, spirits, and vinegar.

    Headings:
        22.01 — Waters (mineral, aerated, flavored)
        22.02 — Sweetened/flavored waters; non-alcoholic beverages (excl. juices 20.09)
        22.03 — Beer made from malt
        22.04 — Wine of fresh grapes; grape must
        22.05 — Vermouth and other wine of fresh grapes flavored
        22.06 — Other fermented beverages (cider, perry, mead, sake)
        22.07 — Undenatured ethyl alcohol ≥80%; denatured ethyl alcohol
        22.08 — Undenatured ethyl alcohol <80%; spirits, liqueurs
        22.09 — Vinegar and substitutes
    """
    text = _product_text(product)

    result = {
        "chapter": 22,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    # Gate: Fruit/veg juice (unfermented, no alcohol) → Ch.20
    if _CH20_JUICE.search(text) and not _CH22_SPIRITS.search(text):
        result["redirect"] = {
            "chapter": 20,
            "reason": "Unfermented fruit/vegetable juice without added spirits → Chapter 20 (heading 20.09).",
            "rule_applied": "Chapter 22 exclusion — juices of 20.09 excluded",
        }
        return result

    if _CH22_VINEGAR.search(text):
        result["candidates"].append({
            "heading": "22.09",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Vinegar → 22.09.",
            "rule_applied": "GIR 1 — heading 22.09",
        })
        return result

    if _CH22_SPIRITS.search(text):
        result["candidates"].append({
            "heading": "22.08",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Spirits/distilled alcoholic beverage/liqueur → 22.08.",
            "rule_applied": "GIR 1 — heading 22.08",
        })
        return result

    if _CH22_WINE.search(text):
        # Vermouth check
        if re.search(r'(?:ורמוט|vermouth)', text, re.IGNORECASE):
            result["candidates"].append({
                "heading": "22.05",
                "subheading_hint": None,
                "confidence": 0.85,
                "reasoning": "Vermouth / flavored wine → 22.05.",
                "rule_applied": "GIR 1 — heading 22.05",
            })
        else:
            result["candidates"].append({
                "heading": "22.04",
                "subheading_hint": None,
                "confidence": 0.85,
                "reasoning": "Wine of fresh grapes / grape must → 22.04.",
                "rule_applied": "GIR 1 — heading 22.04",
            })
        return result

    if _CH22_BEER.search(text):
        result["candidates"].append({
            "heading": "22.03",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Beer made from malt → 22.03.",
            "rule_applied": "GIR 1 — heading 22.03",
        })
        return result

    if _CH22_CIDER.search(text) or _CH22_FERMENTED.search(text):
        result["candidates"].append({
            "heading": "22.06",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Fermented beverage (cider/perry/mead/kombucha/sake) → 22.06.",
            "rule_applied": "GIR 1 — heading 22.06",
        })
        return result

    if _CH22_SOFT_DRINK.search(text):
        result["candidates"].append({
            "heading": "22.02",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Non-alcoholic sweetened/flavored beverage → 22.02.",
            "rule_applied": "GIR 1 — heading 22.02",
        })
        return result

    if _CH22_WATER.search(text):
        result["candidates"].append({
            "heading": "22.01",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Mineral/sparkling/drinking water → 22.01.",
            "rule_applied": "GIR 1 — heading 22.01",
        })
        return result

    # Unknown beverage
    result["candidates"].append({
        "heading": "22.02",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Beverage type unclear → 22.02 (non-alcoholic beverages catch-all).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of beverage? (water, soft drink, beer, wine, spirits, vinegar, fermented)"
    )
    return result


# ============================================================================
# CHAPTER 23: Residues from food industries; prepared animal feed
# ============================================================================

_CH23_BRAN = re.compile(
    r'(?:סובין|סובין\s*(?:חיטה|תירס|אורז|שעורה)|'
    r'bran|sharps|middlings|screenings|'
    r'residue\s*(?:of\s*)?(?:cereal|milling|sifting))',
    re.IGNORECASE
)

_CH23_OILCAKE = re.compile(
    r'(?:פסולת\s*(?:סויה|חמניות|כותנה|קנולה|דקלים)|עוגת\s*שמן|'
    r'oilcake|oil.?cake|soybean\s*meal|soya\s*meal|sunflower\s*meal|'
    r'rapeseed\s*meal|cottonseed\s*meal|palm\s*kernel\s*meal|'
    r'expeller|extraction\s*residue)',
    re.IGNORECASE
)

_CH23_BEET_PULP = re.compile(
    r'(?:פסולת\s*(?:סלק|סוכר|בירה|יקב|זיקוק)|'
    r'beet\s*pulp|bagasse|brew(?:ing|er)\s*(?:waste|grain|spent)|'
    r'distiller\s*(?:grain|dregs|waste)|wine\s*lees)',
    re.IGNORECASE
)

_CH23_PET_FOOD = re.compile(
    r'(?:מזון\s*(?:כלבים|חתולים|ציפורים|דגים)|אוכל\s*(?:כלבים|חתולים)|'
    r'pet\s*food|dog\s*food|cat\s*food|bird\s*(?:feed|food|seed)|'
    r'fish\s*feed|aquarium\s*food)',
    re.IGNORECASE
)

_CH23_ANIMAL_FEED = re.compile(
    r'(?:מספוא|מזון\s*(?:בעלי\s*חיים|בהמות|עופות)|תערובת\s*מזון|'
    r'animal\s*feed|cattle\s*feed|poultry\s*feed|livestock\s*feed|'
    r'compound\s*feed|feed\s*(?:mix|supplement|premix|additive)|'
    r'fodder|silage|hay\s*(?:pellet|cube))',
    re.IGNORECASE
)

_CH23_FISH_MEAL = re.compile(
    r'(?:קמח\s*(?:בשר|עצם|דם|דגים)|'
    r'meat\s*meal|bone\s*meal|blood\s*meal|fish\s*meal|'
    r'meat.?and.?bone\s*meal|MBM|feather\s*meal)',
    re.IGNORECASE
)


def _is_chapter_23_candidate(text):
    """Check if product text suggests Chapter 23 (food residues/animal feed)."""
    return bool(
        _CH23_BRAN.search(text) or _CH23_OILCAKE.search(text)
        or _CH23_BEET_PULP.search(text) or _CH23_PET_FOOD.search(text)
        or _CH23_ANIMAL_FEED.search(text) or _CH23_FISH_MEAL.search(text)
    )


def _decide_chapter_23(product):
    """Chapter 23 decision tree: Residues from food industries; animal feed.

    Headings:
        23.01 — Flours/meals/pellets of meat/offal/fish; greaves (cracklings)
        23.02 — Bran, sharps and other residues from cereals/legumes
        23.03 — Residues of starch/sugar/brewing/distilling (beet pulp, spent grain)
        23.04 — Oilcake and other solid residues from vegetable oil extraction (soya, etc.)
        23.05 — Oilcake from groundnuts (peanut)
        23.06 — Oilcake from other vegetable fats/oils
        23.08 — Vegetable materials/waste used in animal feed n.e.s.
        23.09 — Preparations for animal feeding (pet food, compound feed, premixes)
    """
    text = _product_text(product)

    result = {
        "chapter": 23,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH23_PET_FOOD.search(text) or _CH23_ANIMAL_FEED.search(text):
        result["candidates"].append({
            "heading": "23.09",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Pet food / compound animal feed / feed preparation → 23.09.",
            "rule_applied": "GIR 1 — heading 23.09",
        })
        return result

    if _CH23_FISH_MEAL.search(text):
        result["candidates"].append({
            "heading": "23.01",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Meat/bone/blood/fish meal/flour → 23.01.",
            "rule_applied": "GIR 1 — heading 23.01",
        })
        return result

    if _CH23_OILCAKE.search(text):
        # Could be 23.04 (soya), 23.05 (peanut), or 23.06 (other)
        if re.search(r'(?:סויה|soy|soya)', text, re.IGNORECASE):
            heading, reasoning = "23.04", "Soybean oilcake/meal → 23.04."
        elif re.search(r'(?:בוטנים|peanut|groundnut)', text, re.IGNORECASE):
            heading, reasoning = "23.05", "Groundnut/peanut oilcake → 23.05."
        else:
            heading, reasoning = "23.06", "Oilcake from other vegetable oils → 23.06."
        result["candidates"].append({
            "heading": heading,
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}",
        })
        return result

    if _CH23_BEET_PULP.search(text):
        result["candidates"].append({
            "heading": "23.03",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Sugar/brewing/distilling residue (beet pulp, spent grain) → 23.03.",
            "rule_applied": "GIR 1 — heading 23.03",
        })
        return result

    if _CH23_BRAN.search(text):
        result["candidates"].append({
            "heading": "23.02",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Bran/sharps/cereal milling residue → 23.02.",
            "rule_applied": "GIR 1 — heading 23.02",
        })
        return result

    # Unknown residue
    result["candidates"].append({
        "heading": "23.09",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Food industry residue/animal feed, type unclear → 23.09.",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What type of product? (bran, oilcake, beet pulp, pet food, compound feed, meat/fish meal)"
    )
    return result


# ============================================================================
# CHAPTER 24: Tobacco and manufactured tobacco substitutes
# ============================================================================

_CH24_TOBACCO_LEAF = re.compile(
    r'(?:טבק\s*(?:גולמי|עלים|לא\s*מעובד)|עלי\s*טבק|'
    r'tobacco\s*(?:leaf|leaves|unmanufactured|raw|stem|stalk|refuse|waste)|'
    r'unstripped\s*tobacco|flue.cured|burley|oriental\s*tobacco)',
    re.IGNORECASE
)

_CH24_CIGARETTE = re.compile(
    r'(?:סיגריה|סיגריות|cigarette)',
    re.IGNORECASE
)

_CH24_CIGAR = re.compile(
    r'(?:סיגר|סיגרים|cigar|cheroot|cigarillo)',
    re.IGNORECASE
)

_CH24_PIPE_TOBACCO = re.compile(
    r'(?:טבק\s*(?:מקטרת|גלגול|לגלגול)|'
    r'pipe\s*tobacco|smoking\s*tobacco|roll.your.own|'
    r'loose\s*tobacco|shag)',
    re.IGNORECASE
)

_CH24_HEATED_TOBACCO = re.compile(
    r'(?:טבק\s*(?:מחומם|לחימום)|'
    r'heated?\s*tobacco|heat.not.burn|HNB|IQOS\s*(?:stick|heets)|'
    r'tobacco\s*(?:stick|plug)\s*(?:for\s*heating)?)',
    re.IGNORECASE
)

_CH24_SNUFF_CHEW = re.compile(
    r'(?:טבק\s*(?:הרחה|לעיסה)|'
    r'snuff|chewing\s*tobacco|snus|smokeless\s*tobacco|'
    r'tobacco\s*(?:for\s*chewing|for\s*snuffing))',
    re.IGNORECASE
)

_CH24_ECIGARETTE = re.compile(
    r'(?:סיגריה\s*אלקטרונית|ויייפ|'
    r'e.cigarette|electronic\s*cigarette|vape|vaping|'
    r'e.liquid|vape\s*(?:juice|liquid|pod)|nicotine\s*(?:liquid|salt))',
    re.IGNORECASE
)

_CH24_TOBACCO_GENERAL = re.compile(
    r'(?:טבק|tobacco|nicotine)',
    re.IGNORECASE
)


def _is_chapter_24_candidate(text):
    """Check if product text suggests Chapter 24 (tobacco)."""
    return bool(
        _CH24_TOBACCO_GENERAL.search(text)
        or _CH24_CIGARETTE.search(text)
        or _CH24_CIGAR.search(text)
        or _CH24_ECIGARETTE.search(text)
    )


def _decide_chapter_24(product):
    """Chapter 24 decision tree: Tobacco and manufactured tobacco substitutes.

    Headings:
        24.01 — Unmanufactured tobacco; tobacco refuse
        24.02 — Cigars, cheroots, cigarillos; cigarettes
        24.03 — Other manufactured tobacco; "homogenised"/"reconstituted" tobacco;
                 tobacco extracts and essences; heated tobacco products
        24.04 — Products containing tobacco/nicotine for inhalation without combustion (e-cig)
    """
    text = _product_text(product)

    result = {
        "chapter": 24,
        "candidates": [],
        "redirect": None,
        "questions_needed": [],
    }

    if _CH24_CIGARETTE.search(text):
        result["candidates"].append({
            "heading": "24.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cigarettes → 24.02.",
            "rule_applied": "GIR 1 — heading 24.02",
        })
        return result

    if _CH24_CIGAR.search(text):
        result["candidates"].append({
            "heading": "24.02",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Cigars/cheroots/cigarillos → 24.02.",
            "rule_applied": "GIR 1 — heading 24.02",
        })
        return result

    if _CH24_ECIGARETTE.search(text):
        result["candidates"].append({
            "heading": "24.04",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "E-cigarette/vape/nicotine liquid for inhalation without combustion → 24.04.",
            "rule_applied": "GIR 1 — heading 24.04",
        })
        return result

    if _CH24_HEATED_TOBACCO.search(text):
        result["candidates"].append({
            "heading": "24.03",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Heated tobacco product (HNB/IQOS sticks) → 24.03.",
            "rule_applied": "GIR 1 — heading 24.03",
        })
        return result

    if _CH24_PIPE_TOBACCO.search(text) or _CH24_SNUFF_CHEW.search(text):
        result["candidates"].append({
            "heading": "24.03",
            "subheading_hint": None,
            "confidence": 0.85,
            "reasoning": "Pipe/smoking/chewing/snuff tobacco → 24.03.",
            "rule_applied": "GIR 1 — heading 24.03",
        })
        return result

    if _CH24_TOBACCO_LEAF.search(text):
        result["candidates"].append({
            "heading": "24.01",
            "subheading_hint": None,
            "confidence": 0.90,
            "reasoning": "Unmanufactured tobacco leaf/refuse → 24.01.",
            "rule_applied": "GIR 1 — heading 24.01",
        })
        return result

    # General tobacco reference — need more info
    result["candidates"].append({
        "heading": "24.02",
        "subheading_hint": None,
        "confidence": 0.60,
        "reasoning": "Tobacco product, form unclear → 24.02 (cigarettes/cigars most common).",
        "rule_applied": "GIR 1",
    })
    result["questions_needed"].append(
        "What form is the tobacco? (leaf/raw, cigarettes, cigars, pipe tobacco, heated, e-cigarette/vape)"
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
    16: _decide_chapter_16,
    17: _decide_chapter_17,
    18: _decide_chapter_18,
    19: _decide_chapter_19,
    20: _decide_chapter_20,
    21: _decide_chapter_21,
    22: _decide_chapter_22,
    23: _decide_chapter_23,
    24: _decide_chapter_24,
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
    (16, _is_chapter_16_candidate, _decide_chapter_16),
    (17, _is_chapter_17_candidate, _decide_chapter_17),
    (18, _is_chapter_18_candidate, _decide_chapter_18),
    (19, _is_chapter_19_candidate, _decide_chapter_19),
    (20, _is_chapter_20_candidate, _decide_chapter_20),
    (21, _is_chapter_21_candidate, _decide_chapter_21),
    (22, _is_chapter_22_candidate, _decide_chapter_22),
    (23, _is_chapter_23_candidate, _decide_chapter_23),
    (24, _is_chapter_24_candidate, _decide_chapter_24),
]


def available_chapters():
    """Return list of chapter numbers that have decision trees."""
    return sorted(_CHAPTER_TREES.keys())
