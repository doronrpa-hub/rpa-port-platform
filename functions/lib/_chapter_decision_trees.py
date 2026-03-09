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
    r'\bcarp\b|haddock|halibut|\bsole\b|catfish|perch|pike|swordfish|'
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
    r'(?:שיער\s*(?:אדם|חזיר|סוס)|זיפים|שער\s*חזיר|bristle|(?:animal|horse|pig|goat|badger|brush)\s*hair|horsehair|'
    r'pig\s*bristle)',
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

_CH13_LAC = re.compile(r'(?:לכה|\blac\b|shellac)', re.IGNORECASE)
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
    r'bread|loaf|pita|baguette|\brolls?\b|toast|flatbread|naan|ciabatta|'
    r'sourdough|rye\s*bread|white\s*bread|whole\s*wheat\s*bread)',
    re.IGNORECASE
)

_CH19_PASTRY = re.compile(
    r'(?:עוגה|עוגות|מאפה|מאפים|קרואסון|דונאט|בורקס|'
    r'cake|pastry|croissant|donut|doughnut|muffin|cookie|biscuit|'
    r'wafer|\bpie\b|\btart\b|danish|scone|brioche|strudel|baklava|'
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
# CHAPTER 25: Salt; sulphur; earths and stone; plastering materials, lime, cement
# ============================================================================

_CH25_SALT = re.compile(
    r'(?:מלח\s*(?:גולמי|שולחן|תעשייתי|ים)|'
    r'salt|sodium\s*chloride|rock\s*salt|sea\s*salt|table\s*salt|'
    r'brine|salt\s*(?:deicing|de.icing|industrial))',
    re.IGNORECASE
)

_CH25_SULPHUR = re.compile(
    r'(?:גופרית|sulphur|sulfur|sublimed\s*sulph|precipitated\s*sulph)',
    re.IGNORECASE
)

_CH25_SAND_GRAVEL = re.compile(
    r'(?:חול|חצץ|אבן\s*(?:שחיקה|טבעית)|'
    r'sand|gravel|pebble|crushed\s*stone|natural\s*sand|'
    r'silica\s*sand|quartz\s*sand)',
    re.IGNORECASE
)

_CH25_CEMENT = re.compile(
    r'(?:מלט|צמנט|cement|clinker|portland)',
    re.IGNORECASE
)

_CH25_PLASTER = re.compile(
    r'(?:גבס|טיח|plaster|gypsum|anhydrite|stucco)',
    re.IGNORECASE
)

_CH25_LIME = re.compile(
    r'(?:סיד|lime|quicklime|slaked\s*lime|hydraulic\s*lime|calcium\s*oxide|'
    r'calcium\s*hydroxide)',
    re.IGNORECASE
)

_CH25_MARBLE_GRANITE = re.compile(
    r'(?:שיש|גרניט|אבן\s*בנייה|marble|granite|travertine|'
    r'sandstone|slate|basalt|porphyry|monumental\s*stone)',
    re.IGNORECASE
)

_CH25_CLAY = re.compile(
    r'(?:חימר|קאולין|בנטוניט|clay|kaolin|bentonite|'
    r'fireclay|chamotte|andalusite|mullite|dolomite)',
    re.IGNORECASE
)

_CH25_MICA_TALC = re.compile(
    r'(?:טלק|מיקה|אסבסט|mica|talc|asbestos|vermiculite|meerschaum)',
    re.IGNORECASE
)


def _is_chapter_25_candidate(text):
    return bool(
        _CH25_SALT.search(text) or _CH25_SULPHUR.search(text)
        or _CH25_SAND_GRAVEL.search(text) or _CH25_CEMENT.search(text)
        or _CH25_PLASTER.search(text) or _CH25_LIME.search(text)
        or _CH25_MARBLE_GRANITE.search(text) or _CH25_CLAY.search(text)
        or _CH25_MICA_TALC.search(text)
    )


def _decide_chapter_25(product):
    """Chapter 25: Salt; sulphur; earths and stone; plastering materials, lime, cement.

    Headings:
        25.01 — Salt; pure NaCl; sea water
        25.03 — Sulphur (crude/refined)
        25.05 — Natural sands
        25.06 — Quartz; quartzite
        25.15 — Marble, travertine, building stone
        25.16 — Granite, sandstone, porphyry
        25.17 — Pebbles, gravel, broken stone
        25.07 — Kaolin and other kaolinic clays
        25.08 — Other clays, andalusite, mullite, chamotte
        25.20 — Gypsum; anhydrite; plasters
        25.22 — Quicklime, slaked lime, hydraulic lime
        25.23 — Portland cement and similar
        25.25 — Mica
        25.26 — Natural steatite/talc
    """
    text = _product_text(product)
    result = {"chapter": 25, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH25_SALT.search(text):
        result["candidates"].append({"heading": "25.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Salt / sodium chloride / sea water → 25.01.",
            "rule_applied": "GIR 1 — heading 25.01"})
        return result
    if _CH25_SULPHUR.search(text):
        result["candidates"].append({"heading": "25.03", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Sulphur (crude or refined) → 25.03.",
            "rule_applied": "GIR 1 — heading 25.03"})
        return result
    if _CH25_CEMENT.search(text):
        result["candidates"].append({"heading": "25.23", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Portland cement / clinker → 25.23.",
            "rule_applied": "GIR 1 — heading 25.23"})
        return result
    if _CH25_PLASTER.search(text):
        result["candidates"].append({"heading": "25.20", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Gypsum / plaster → 25.20.",
            "rule_applied": "GIR 1 — heading 25.20"})
        return result
    if _CH25_LIME.search(text):
        result["candidates"].append({"heading": "25.22", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Quicklime / slaked lime / hydraulic lime → 25.22.",
            "rule_applied": "GIR 1 — heading 25.22"})
        return result
    if _CH25_CLAY.search(text):
        if re.search(r'(?:קאולין|kaolin)', text, re.IGNORECASE):
            heading, reasoning = "25.07", "Kaolin / kaolinic clay → 25.07."
        else:
            heading, reasoning = "25.08", "Clay / bentonite / fireclay → 25.08."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH25_MARBLE_GRANITE.search(text):
        if re.search(r'(?:שיש|marble|travertine)', text, re.IGNORECASE):
            heading, reasoning = "25.15", "Marble / travertine / building stone → 25.15."
        else:
            heading, reasoning = "25.16", "Granite / sandstone / porphyry → 25.16."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH25_SAND_GRAVEL.search(text):
        if re.search(r'(?:חצץ|gravel|pebble|crushed)', text, re.IGNORECASE):
            heading, reasoning = "25.17", "Pebbles / gravel / crushed stone → 25.17."
        else:
            heading, reasoning = "25.05", "Natural sand → 25.05."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH25_MICA_TALC.search(text):
        if re.search(r'(?:מיקה|mica)', text, re.IGNORECASE):
            heading, reasoning = "25.25", "Mica → 25.25."
        else:
            heading, reasoning = "25.26", "Talc / steatite → 25.26."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "25.30", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Mineral product n.e.s. → 25.30.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of mineral? (salt, sulphur, sand, cement, plaster, lime, clay, marble, granite)")
    return result


# ============================================================================
# CHAPTER 26: Ores, slag and ash
# ============================================================================

_CH26_IRON_ORE = re.compile(
    r'(?:עפרת?\s*ברזל|iron\s*ore|hematite|magnetite|limonite|siderite)',
    re.IGNORECASE
)
_CH26_COPPER_ORE = re.compile(
    r'(?:עפרת?\s*נחושת|copper\s*ore|chalcopyrite|malachite\s*ore)',
    re.IGNORECASE
)
_CH26_ALUMINIUM_ORE = re.compile(
    r'(?:בוקסיט|עפרת?\s*אלומיניום|bauxite|aluminium\s*ore|aluminum\s*ore)',
    re.IGNORECASE
)
_CH26_SLAG_ASH = re.compile(
    r'(?:סיגים|אפר|שלאק|slag|\bash\b|dross|\bscale\b|skimming|fly\s*ash|'
    r'bottom\s*ash|clinker\s*ash)',
    re.IGNORECASE
)
_CH26_OTHER_ORE = re.compile(
    r'(?:עפרה|עפרת|ore|concentrate|manganese\s*ore|chromium\s*ore|'
    r'tungsten\s*ore|nickel\s*ore|cobalt\s*ore|tin\s*ore|zinc\s*ore|'
    r'lead\s*ore|titanium\s*ore|zirconium\s*ore|uranium\s*ore|'
    r'molybdenum|precious\s*metal\s*ore|gold\s*ore|silver\s*ore)',
    re.IGNORECASE
)


def _is_chapter_26_candidate(text):
    return bool(
        _CH26_IRON_ORE.search(text) or _CH26_COPPER_ORE.search(text)
        or _CH26_ALUMINIUM_ORE.search(text) or _CH26_SLAG_ASH.search(text)
        or _CH26_OTHER_ORE.search(text)
    )


def _decide_chapter_26(product):
    """Chapter 26: Ores, slag and ash.

    Headings:
        26.01 — Iron ores and concentrates
        26.03 — Copper ores and concentrates
        26.06 — Aluminium ores (bauxite)
        26.19-26.21 — Slag, ash, residues containing metals
        26.02-26.17 — Other metal ores and concentrates
    """
    text = _product_text(product)
    result = {"chapter": 26, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH26_IRON_ORE.search(text):
        result["candidates"].append({"heading": "26.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Iron ore / hematite / magnetite → 26.01.",
            "rule_applied": "GIR 1 — heading 26.01"})
        return result
    if _CH26_COPPER_ORE.search(text):
        result["candidates"].append({"heading": "26.03", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Copper ore / concentrate → 26.03.",
            "rule_applied": "GIR 1 — heading 26.03"})
        return result
    if _CH26_ALUMINIUM_ORE.search(text):
        result["candidates"].append({"heading": "26.06", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Bauxite / aluminium ore → 26.06.",
            "rule_applied": "GIR 1 — heading 26.06"})
        return result
    if _CH26_SLAG_ASH.search(text):
        result["candidates"].append({"heading": "26.21", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Slag / ash / dross / residues → 26.21.",
            "rule_applied": "GIR 1 — heading 26.21"})
        return result
    if _CH26_OTHER_ORE.search(text):
        result["candidates"].append({"heading": "26.17", "subheading_hint": None,
            "confidence": 0.75, "reasoning": "Other metal ore / concentrate → 26.17 (other ores n.e.s.).",
            "rule_applied": "GIR 1 — heading 26.17"})
        result["questions_needed"].append("Which metal ore? (manganese, chromium, nickel, zinc, lead, tin, etc.)")
        return result

    result["candidates"].append({"heading": "26.21", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Ore/slag/ash type unclear → 26.21.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type of ore or residue? (iron, copper, bauxite, slag, ash)")
    return result


# ============================================================================
# CHAPTER 27: Mineral fuels, mineral oils, bituminous substances; mineral waxes
# ============================================================================

_CH27_COAL = re.compile(
    r'(?:פחם\s*(?:אבן|ביטומני|חום|אנתרציט|קוק)|'
    r'coal|anthracite|bituminous\s*coal|lignite|brown\s*coal|coke|'
    r'briquette\s*(?:of\s*)?coal|peat)',
    re.IGNORECASE
)
_CH27_CRUDE_OIL = re.compile(
    r'(?:נפט\s*גולמי|שמן\s*גולמי|crude\s*(?:oil|petroleum)|'
    r'bituminous\s*oil\s*(?:crude|natural))',
    re.IGNORECASE
)
_CH27_PETROLEUM = re.compile(
    r'(?:בנזין|סולר|דלק|נפט|קרוסין|מזוט|ביטומן|אספלט|'
    r'gasoline|petrol|diesel|kerosene|jet\s*fuel|fuel\s*oil|'
    r'heavy\s*fuel|naphtha|bitumen|asphalt|petroleum\s*(?:jelly|wax)|'
    r'vaseline|paraffin\s*(?:wax|oil)|lubricating\s*oil|white\s*oil)',
    re.IGNORECASE
)
_CH27_GAS = re.compile(
    r'(?:גז\s*(?:טבעי|נוזלי|LPG|LNG)|'
    r'natural\s*gas|LPG|LNG|liquefied\s*(?:petroleum|natural)\s*gas|'
    r'propane|butane|methane)',
    re.IGNORECASE
)
_CH27_TAR = re.compile(
    r'(?:זפת|tar|pitch|creosote|coal\s*tar)',
    re.IGNORECASE
)
_CH27_ELECTRICITY = re.compile(
    r'(?:חשמל|electrical\s*energy|electricity)',
    re.IGNORECASE
)


def _is_chapter_27_candidate(text):
    return bool(
        _CH27_COAL.search(text) or _CH27_CRUDE_OIL.search(text)
        or _CH27_PETROLEUM.search(text) or _CH27_GAS.search(text)
        or _CH27_TAR.search(text) or _CH27_ELECTRICITY.search(text)
    )


def _decide_chapter_27(product):
    """Chapter 27: Mineral fuels, oils, waxes, bituminous substances.

    Headings:
        27.01 — Coal; briquettes of coal
        27.02 — Lignite
        27.04 — Coke and semi-coke of coal/lignite/peat
        27.09 — Petroleum oils, crude
        27.10 — Petroleum oils (not crude); preparations ≥70% petroleum
        27.11 — Petroleum gases (LPG, LNG, natural gas, propane, butane)
        27.12 — Petroleum jelly, paraffin wax, mineral wax
        27.13 — Petroleum coke, petroleum bitumen
        27.15 — Bituminous mixtures (asphalt)
        27.16 — Electrical energy
    """
    text = _product_text(product)
    result = {"chapter": 27, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH27_CRUDE_OIL.search(text):
        result["candidates"].append({"heading": "27.09", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Crude petroleum oil → 27.09.",
            "rule_applied": "GIR 1 — heading 27.09"})
        return result
    if _CH27_GAS.search(text):
        result["candidates"].append({"heading": "27.11", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Petroleum/natural gas (LPG/LNG/propane/butane) → 27.11.",
            "rule_applied": "GIR 1 — heading 27.11"})
        return result
    if _CH27_COAL.search(text):
        if re.search(r'(?:קוק|coke)', text, re.IGNORECASE):
            heading, reasoning = "27.04", "Coke / semi-coke → 27.04."
        elif re.search(r'(?:לגניט|lignite|brown\s*coal)', text, re.IGNORECASE):
            heading, reasoning = "27.02", "Lignite / brown coal → 27.02."
        else:
            heading, reasoning = "27.01", "Coal / anthracite / bituminous coal → 27.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH27_ELECTRICITY.search(text):
        result["candidates"].append({"heading": "27.16", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Electrical energy → 27.16.",
            "rule_applied": "GIR 1 — heading 27.16"})
        return result
    if _CH27_TAR.search(text):
        result["candidates"].append({"heading": "27.06", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Tar / pitch / creosote → 27.06.",
            "rule_applied": "GIR 1 — heading 27.06"})
        return result
    if _CH27_PETROLEUM.search(text):
        if re.search(r'(?:ביטומן|אספלט|bitumen|asphalt)', text, re.IGNORECASE):
            heading, reasoning = "27.15", "Bitumen / asphalt → 27.15."
        elif re.search(r'(?:וזלין|פרפין|petroleum\s*jelly|paraffin\s*wax|vaseline)', text, re.IGNORECASE):
            heading, reasoning = "27.12", "Petroleum jelly / paraffin wax → 27.12."
        else:
            heading, reasoning = "27.10", "Petroleum products (gasoline/diesel/kerosene/fuel oil) → 27.10."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "27.10", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Mineral fuel type unclear → 27.10.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of mineral fuel? (coal, crude oil, gasoline/diesel, LPG/gas, bitumen, wax)")
    return result


# ============================================================================
# CHAPTER 28: Inorganic chemicals; compounds of precious/rare-earth metals
# ============================================================================

_CH28_ACID = re.compile(
    r'(?:חומצה\s*(?:גפרתנית|מלחית|חנקתית|זרחנית|פלואורית|בורית)|'
    r'(?:hydrochloric|sulphuric|sulfuric|nitric|phosphoric|hydrofluoric|'
    r'boric|hydrobromic|hydrogen\s*peroxide)\s*acid|H2SO4|HCl|HNO3|H3PO4|H2O2)',
    re.IGNORECASE
)
_CH28_BASE = re.compile(
    r'(?:נתרן\s*הידרוקסיד|אשלגן\s*הידרוקסיד|'
    r'sodium\s*hydroxide|potassium\s*hydroxide|caustic\s*(?:soda|potash)|'
    r'NaOH|KOH|calcium\s*hydroxide|ammonia|ammonium\s*hydroxide)',
    re.IGNORECASE
)
_CH28_OXIDE = re.compile(
    r'(?:תחמוצת|אוקסיד|oxide|zinc\s*oxide|titanium\s*dioxide|'
    r'aluminium\s*oxide|aluminum\s*oxide|silicon\s*dioxide|'
    r'iron\s*oxide|TiO2|ZnO|Al2O3|SiO2)',
    re.IGNORECASE
)
_CH28_HALOGEN = re.compile(
    r'(?:כלור|ברום|יוד|פלואור|chlorine|bromine|iodine|fluorine)',
    re.IGNORECASE
)
_CH28_SALT_INORGANIC = re.compile(
    r'(?:סודיום\s*(?:כלוריד|קרבונט|ביקרבונט|סולפט|ניטרט|פוספט)|'
    r'sodium\s*(?:carbonate|bicarbonate|sulphate|sulfate|nitrate|phosphate)|'
    r'potassium\s*(?:chloride|carbonate|nitrate|permanganate)|'
    r'calcium\s*(?:carbonate|chloride|phosphate|sulphate|sulfate)|'
    r'barium\s*(?:sulphate|sulfate)|magnesium\s*(?:oxide|sulphate|sulfate|chloride))',
    re.IGNORECASE
)
_CH28_RARE_EARTH = re.compile(
    r'(?:אדמות\s*נדירות|rare\s*earth|lanthanide|cerium|lanthanum|'
    r'neodymium|yttrium|scandium)',
    re.IGNORECASE
)
_CH28_GENERAL = re.compile(
    r'(?:כימיקל\s*(?:אי.?אורגני|אנאורגני)|inorganic\s*chemical|'
    r'chemical\s*(?:compound|reagent|element)|'
    r'carbon\s*(?:black|dioxide)|CO2|activated\s*carbon|silicon)',
    re.IGNORECASE
)


def _is_chapter_28_candidate(text):
    return bool(
        _CH28_ACID.search(text) or _CH28_BASE.search(text)
        or _CH28_OXIDE.search(text) or _CH28_HALOGEN.search(text)
        or _CH28_SALT_INORGANIC.search(text) or _CH28_RARE_EARTH.search(text)
        or _CH28_GENERAL.search(text)
    )


def _decide_chapter_28(product):
    """Chapter 28: Inorganic chemicals.

    Headings:
        28.01 — Fluorine, chlorine, bromine, iodine
        28.06-28.11 — Inorganic acids (HCl, H2SO4, HNO3, H3PO4, etc.)
        28.12-28.15 — Halides, sulphides
        28.16-28.21 — Hydroxides, oxides (NaOH, KOH, ZnO, TiO2, Al2O3)
        28.33-28.42 — Sulphates, nitrates, phosphates, carbonates, cyanides
        28.43-28.46 — Compounds of precious/rare-earth metals; isotopes
        28.47-28.53 — Other inorganic compounds, H2O2, carbides, etc.
    """
    text = _product_text(product)
    result = {"chapter": 28, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH28_HALOGEN.search(text):
        result["candidates"].append({"heading": "28.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Halogen element (F/Cl/Br/I) → 28.01.",
            "rule_applied": "GIR 1 — heading 28.01"})
        return result
    if _CH28_ACID.search(text):
        if re.search(r'(?:H2O2|hydrogen\s*peroxide)', text, re.IGNORECASE):
            heading, reasoning = "28.47", "Hydrogen peroxide → 28.47."
        else:
            heading, reasoning = "28.06", "Inorganic acid → 28.06 (or appropriate acid heading)."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH28_BASE.search(text):
        result["candidates"].append({"heading": "28.15", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Hydroxide / caustic (NaOH/KOH/ammonia) → 28.15.",
            "rule_applied": "GIR 1 — heading 28.15"})
        return result
    if _CH28_OXIDE.search(text):
        result["candidates"].append({"heading": "28.18", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Metal oxide (ZnO/TiO2/Al2O3) → 28.18.",
            "rule_applied": "GIR 1 — heading 28.18"})
        return result
    if _CH28_SALT_INORGANIC.search(text):
        result["candidates"].append({"heading": "28.36", "subheading_hint": None,
            "confidence": 0.75, "reasoning": "Inorganic salt (carbonate/sulphate/nitrate/phosphate) → 28.36.",
            "rule_applied": "GIR 1 — heading 28.36"})
        result["questions_needed"].append("Which salt? (carbonate, sulphate, nitrate, phosphate, chloride)")
        return result
    if _CH28_RARE_EARTH.search(text):
        result["candidates"].append({"heading": "28.46", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Rare earth compounds → 28.46.",
            "rule_applied": "GIR 1 — heading 28.46"})
        return result
    if _CH28_GENERAL.search(text):
        result["candidates"].append({"heading": "28.53", "subheading_hint": None,
            "confidence": 0.65, "reasoning": "Inorganic chemical compound n.e.s. → 28.53.",
            "rule_applied": "GIR 1 — heading 28.53"})
        return result

    result["candidates"].append({"heading": "28.53", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Inorganic chemical, type unclear → 28.53.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of inorganic chemical? (acid, base/alkali, oxide, halogen, salt, rare earth)")
    return result


# ============================================================================
# CHAPTER 29: Organic chemicals
# ============================================================================

_CH29_HYDROCARBON = re.compile(
    r'(?:פחמימן|hydrocarbon|benzene|toluene|xylene|styrene|'
    r'\bethylene\b|\bpropylene\b|butadiene|cyclohexane|naphthalene|'
    r'acetylene|methane)',
    re.IGNORECASE
)
_CH29_ALCOHOL = re.compile(
    r'(?:אלכוהול\s*(?:מתילי|אתילי|איזופרופילי)|'
    r'methanol|ethanol|isopropanol|propanol|butanol|'
    r'glycerol|glycerin|sorbitol|mannitol|ethylene\s*glycol|'
    r'propylene\s*glycol)',
    re.IGNORECASE
)
_CH29_ACID_ORGANIC = re.compile(
    r'(?:חומצה\s*(?:אצטית|ציטרית|לקטית|אוקסלית|טרטרית)|'
    r'acetic\s*acid|citric\s*acid|lactic\s*acid|oxalic\s*acid|'
    r'tartaric\s*acid|formic\s*acid|propionic\s*acid|'
    r'stearic\s*acid|oleic\s*acid|benzoic\s*acid|'
    r'salicylic\s*acid|ascorbic\s*acid)',
    re.IGNORECASE
)
_CH29_ESTER = re.compile(
    r'(?:אסתר|ester|acetate|phthalate|acrylate|methacrylate)',
    re.IGNORECASE
)
_CH29_AMINE = re.compile(
    r'(?:אמין|amine|aniline|melamine|hexamethylene)',
    re.IGNORECASE
)
_CH29_KETONE_ALDEHYDE = re.compile(
    r'(?:קטון|אלדהיד|acetone|ketone|aldehyde|formaldehyde|'
    r'acetaldehyde|cyclohexanone|MEK|methyl\s*ethyl\s*ketone)',
    re.IGNORECASE
)
_CH29_VITAMIN = re.compile(
    r'(?:ויטמין|vitamin\s*[A-K]|provitamin|ascorbic)',
    re.IGNORECASE
)
_CH29_HORMONE = re.compile(
    r'(?:הורמון|hormone|steroid|cortisone|insulin|testosterone|'
    r'estrogen|progesterone)',
    re.IGNORECASE
)
_CH29_SUGAR_CHEM = re.compile(
    r'(?:סוכר\s*(?:כימי|טהור)|chemically\s*pure\s*sugar|'
    r'sucrose\s*(?:pure|analytical)|fructose\s*(?:pure|analytical))',
    re.IGNORECASE
)
_CH29_GENERAL = re.compile(
    r'(?:כימיקל\s*אורגני|organic\s*chemical|organic\s*compound)',
    re.IGNORECASE
)


def _is_chapter_29_candidate(text):
    return bool(
        _CH29_HYDROCARBON.search(text) or _CH29_ALCOHOL.search(text)
        or _CH29_ACID_ORGANIC.search(text) or _CH29_ESTER.search(text)
        or _CH29_AMINE.search(text) or _CH29_KETONE_ALDEHYDE.search(text)
        or _CH29_VITAMIN.search(text) or _CH29_HORMONE.search(text)
        or _CH29_GENERAL.search(text)
    )


def _decide_chapter_29(product):
    """Chapter 29: Organic chemicals.

    Headings:
        29.01-29.04 — Hydrocarbons (acyclic, cyclic, halogenated, sulfonated)
        29.05 — Acyclic alcohols (methanol, ethanol, glycerol)
        29.06 — Cyclic alcohols (menthol, cyclohexanol)
        29.12-29.14 — Aldehydes, ketones, quinones
        29.15-29.18 — Carboxylic acids and derivatives
        29.21-29.29 — Nitrogen-function compounds (amines, amides)
        29.36 — Provitamins and vitamins
        29.37 — Hormones and steroids
        29.40 — Chemically pure sugars (other than sucrose/etc. of Ch.17)
    """
    text = _product_text(product)
    result = {"chapter": 29, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH29_VITAMIN.search(text):
        result["candidates"].append({"heading": "29.36", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Vitamin / provitamin → 29.36.",
            "rule_applied": "GIR 1 — heading 29.36"})
        return result
    if _CH29_HORMONE.search(text):
        result["candidates"].append({"heading": "29.37", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Hormone / steroid → 29.37.",
            "rule_applied": "GIR 1 — heading 29.37"})
        return result
    if _CH29_HYDROCARBON.search(text):
        result["candidates"].append({"heading": "29.02", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Hydrocarbon (benzene/toluene/ethylene/etc.) → 29.02.",
            "rule_applied": "GIR 1 — heading 29.02"})
        return result
    if _CH29_ALCOHOL.search(text):
        result["candidates"].append({"heading": "29.05", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Alcohol (methanol/ethanol/glycerol/glycol) → 29.05.",
            "rule_applied": "GIR 1 — heading 29.05"})
        return result
    if _CH29_KETONE_ALDEHYDE.search(text):
        if re.search(r'(?:אלדהיד|aldehyde|formaldehyde)', text, re.IGNORECASE):
            heading, reasoning = "29.12", "Aldehyde → 29.12."
        else:
            heading, reasoning = "29.14", "Ketone (acetone/MEK) → 29.14."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH29_ACID_ORGANIC.search(text):
        result["candidates"].append({"heading": "29.15", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Organic / carboxylic acid → 29.15.",
            "rule_applied": "GIR 1 — heading 29.15"})
        return result
    if _CH29_ESTER.search(text):
        result["candidates"].append({"heading": "29.15", "subheading_hint": None,
            "confidence": 0.75, "reasoning": "Ester / acetate / acrylate → 29.15.",
            "rule_applied": "GIR 1 — heading 29.15"})
        return result
    if _CH29_AMINE.search(text):
        result["candidates"].append({"heading": "29.21", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Amine / aniline / melamine → 29.21.",
            "rule_applied": "GIR 1 — heading 29.21"})
        return result
    if _CH29_SUGAR_CHEM.search(text):
        result["candidates"].append({"heading": "29.40", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Chemically pure sugar → 29.40.",
            "rule_applied": "GIR 1 — heading 29.40"})
        return result

    result["candidates"].append({"heading": "29.42", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Organic chemical compound n.e.s. → 29.42.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of organic chemical? (hydrocarbon, alcohol, acid, ester, amine, vitamin, hormone)")
    return result


# ============================================================================
# CHAPTER 30: Pharmaceutical products
# ============================================================================

_CH30_TABLET_CAPSULE = re.compile(
    r'(?:טבליה|טבליות|כמוסה|כמוסות|כדור|כדורים|'
    r'tablet|capsule|pill|caplet|lozenge|dragee)',
    re.IGNORECASE
)
_CH30_INJECTION = re.compile(
    r'(?:זריקה|אמפולה|עירוי|injection|ampoule|ampule|'
    r'syringe|infusion|injectable|IV\s*bag|vial)',
    re.IGNORECASE
)
_CH30_CREAM_OINTMENT = re.compile(
    r'(?:משחה\s*רפואית|ג\'ל\s*רפואי|קרם\s*רפואי|'
    r'ointment|pharmaceutical\s*(?:cream|gel)|topical\s*(?:cream|gel)|'
    r'dermal\s*(?:cream|patch)|transdermal\s*patch)',
    re.IGNORECASE
)
_CH30_SYRUP = re.compile(
    r'(?:סירופ\s*(?:רפואי|שיעול)|'
    r'(?:cough|pharmaceutical|medicinal)\s*syrup|'
    r'oral\s*(?:solution|suspension|liquid))',
    re.IGNORECASE
)
_CH30_VACCINE = re.compile(
    r'(?:חיסון|חיסונים|vaccine|immunological|serum|antiserum|'
    r'toxoid|toxin|antitoxin)',
    re.IGNORECASE
)
_CH30_BANDAGE_MEDICAL = re.compile(
    r'(?:תחבושת\s*(?:רפואית|ספוגית)|פלסטר\s*רפואי|גבס\s*רפואי|'
    r'(?:adhesive|surgical)\s*bandage|(?:medical|surgical)\s*dressing|'
    r'first\s*aid\s*(?:bandage|kit)|sticking\s*plaster|catgut|'
    r'suture|blood\s*grouping\s*reagent)',
    re.IGNORECASE
)
_CH30_VETERINARY = re.compile(
    r'(?:וטרינר|לבע"ח|veterinary|for\s*(?:animal|livestock)\s*use)',
    re.IGNORECASE
)
_CH30_PHARMA_GENERAL = re.compile(
    r'(?:תרופה|תרופות|רפואי|רפואה|'
    r'pharmaceutical|medicament|medication|medicine|drug\s*(?:product)?|'
    r'dosage\s*form|API\s*(?:active\s*pharmaceutical))',
    re.IGNORECASE
)


def _is_chapter_30_candidate(text):
    return bool(
        _CH30_TABLET_CAPSULE.search(text) or _CH30_INJECTION.search(text)
        or _CH30_VACCINE.search(text) or _CH30_PHARMA_GENERAL.search(text)
        or _CH30_BANDAGE_MEDICAL.search(text) or _CH30_CREAM_OINTMENT.search(text)
        or _CH30_SYRUP.search(text)
    )


def _decide_chapter_30(product):
    """Chapter 30: Pharmaceutical products.

    Headings:
        30.01 — Glands/organs; extracts thereof; heparin
        30.02 — Human/animal blood; antisera; vaccines; toxins; cultures
        30.03 — Medicaments (not in dosage form or packed for retail)
        30.04 — Medicaments (in dosage form or packed for retail)
        30.05 — Wadding, gauze, bandages, surgical dressings
        30.06 — Pharmaceutical goods (sutures, blood reagents, first aid, etc.)
    """
    text = _product_text(product)
    result = {"chapter": 30, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH30_VACCINE.search(text):
        result["candidates"].append({"heading": "30.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Vaccine / serum / immunological product → 30.02.",
            "rule_applied": "GIR 1 — heading 30.02"})
        return result
    if _CH30_BANDAGE_MEDICAL.search(text):
        result["candidates"].append({"heading": "30.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Surgical bandage / dressing / plaster → 30.05.",
            "rule_applied": "GIR 1 — heading 30.05"})
        return result
    # Dosage forms → 30.04
    if (_CH30_TABLET_CAPSULE.search(text) or _CH30_INJECTION.search(text)
            or _CH30_CREAM_OINTMENT.search(text) or _CH30_SYRUP.search(text)):
        conf = 0.85
        form_desc = "dosage form"
        if _CH30_TABLET_CAPSULE.search(text):
            form_desc = "tablets/capsules"
        elif _CH30_INJECTION.search(text):
            form_desc = "injection/ampoule"
        elif _CH30_SYRUP.search(text):
            form_desc = "oral syrup/solution"
        elif _CH30_CREAM_OINTMENT.search(text):
            form_desc = "ointment/cream/patch"
        reasoning = f"Medicament in {form_desc} → 30.04."
        if _CH30_VETERINARY.search(text):
            reasoning += " (veterinary)"
        result["candidates"].append({"heading": "30.04", "subheading_hint": None,
            "confidence": conf, "reasoning": reasoning,
            "rule_applied": "GIR 1 — heading 30.04"})
        return result

    if _CH30_PHARMA_GENERAL.search(text):
        result["candidates"].append({"heading": "30.04", "subheading_hint": None,
            "confidence": 0.70, "reasoning": "Pharmaceutical product, form unclear → 30.04 (most common).",
            "rule_applied": "GIR 1 — heading 30.04"})
        result["questions_needed"].append(
            "What form? (tablet/capsule, injection, syrup, cream/ointment, vaccine, bandage)")
        return result

    result["candidates"].append({"heading": "30.04", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Pharmaceutical product → 30.04.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What pharmaceutical form and purpose?")
    return result


# ============================================================================
# CHAPTER 31: Fertilizers
# ============================================================================

_CH31_NITROGEN = re.compile(
    r'(?:דשן\s*(?:חנקני|אוריאה)|'
    r'urea|ammonium\s*(?:nitrate|sulphate|sulfate)|'
    r'nitrogenous\s*fertilizer|nitrogen\s*fertilizer|'
    r'sodium\s*nitrate\s*(?:fertilizer|natural)|'
    r'calcium\s*(?:ammonium\s*nitrate|cyanamide))',
    re.IGNORECASE
)
_CH31_PHOSPHATE = re.compile(
    r'(?:דשן\s*(?:זרחני|סופרפוספט)|'
    r'superphosphate|phosphatic\s*fertilizer|phosphate\s*fertilizer|'
    r'Thomas\s*slag|basic\s*slag|dicalcium\s*phosphate|'
    r'ground\s*phosphate)',
    re.IGNORECASE
)
_CH31_POTASSIC = re.compile(
    r'(?:דשן\s*(?:אשלגני|פוטסיום)|'
    r'potassic\s*fertilizer|potash\s*fertilizer|'
    r'potassium\s*chloride\s*fertilizer|muriate\s*of\s*potash|'
    r'potassium\s*sulphate\s*fertilizer)',
    re.IGNORECASE
)
_CH31_NPK = re.compile(
    r'(?:NPK|דשן\s*(?:מורכב|משולב)|compound\s*fertilizer|'
    r'complex\s*fertilizer|mixed\s*fertilizer|'
    r'(?:nitrogen|phosph|potass).*(?:nitrogen|phosph|potass))',
    re.IGNORECASE
)
_CH31_GUANO = re.compile(
    r'(?:גואנו|guano|animal\s*fertilizer|manure)',
    re.IGNORECASE
)
_CH31_GENERAL = re.compile(
    r'(?:דשן|fertilizer|fertiliser|plant\s*(?:food|nutrient))',
    re.IGNORECASE
)


def _is_chapter_31_candidate(text):
    return bool(
        _CH31_NITROGEN.search(text) or _CH31_PHOSPHATE.search(text)
        or _CH31_POTASSIC.search(text) or _CH31_NPK.search(text)
        or _CH31_GUANO.search(text) or _CH31_GENERAL.search(text)
    )


def _decide_chapter_31(product):
    """Chapter 31: Fertilizers.

    Headings:
        31.01 — Animal/vegetable fertilizers (guano, manure)
        31.02 — Mineral or chemical, nitrogenous (urea, ammonium nitrate)
        31.03 — Mineral or chemical, phosphatic (superphosphate)
        31.04 — Mineral or chemical, potassic (muriate of potash)
        31.05 — Compound/complex fertilizers; other fertilizers; NPK
    """
    text = _product_text(product)
    result = {"chapter": 31, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH31_NPK.search(text):
        result["candidates"].append({"heading": "31.05", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Compound/NPK fertilizer → 31.05.",
            "rule_applied": "GIR 1 — heading 31.05"})
        return result
    if _CH31_NITROGEN.search(text):
        result["candidates"].append({"heading": "31.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Nitrogenous fertilizer (urea/ammonium nitrate) → 31.02.",
            "rule_applied": "GIR 1 — heading 31.02"})
        return result
    if _CH31_PHOSPHATE.search(text):
        result["candidates"].append({"heading": "31.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Phosphatic fertilizer (superphosphate) → 31.03.",
            "rule_applied": "GIR 1 — heading 31.03"})
        return result
    if _CH31_POTASSIC.search(text):
        result["candidates"].append({"heading": "31.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Potassic fertilizer (muriate of potash) → 31.04.",
            "rule_applied": "GIR 1 — heading 31.04"})
        return result
    if _CH31_GUANO.search(text):
        result["candidates"].append({"heading": "31.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Animal/vegetable fertilizer (guano/manure) → 31.01.",
            "rule_applied": "GIR 1 — heading 31.01"})
        return result

    result["candidates"].append({"heading": "31.05", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Fertilizer type unclear → 31.05.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of fertilizer? (nitrogenous/urea, phosphatic, potassic, NPK compound, organic/guano)")
    return result


# ============================================================================
# CHAPTER 32: Tanning/dyeing extracts; dyes; pigments; paints; varnishes; inks
# ============================================================================

_CH32_TANNING = re.compile(
    r'(?:עפץ|חומר\s*עיבוד\s*עור|tanning\s*(?:extract|agent|substance)|'
    r'quebracho|wattle|tannin|synthetic\s*tanning)',
    re.IGNORECASE
)
_CH32_DYE = re.compile(
    r'(?:צבע\s*(?:סינתטי|אורגני|ריאקטיבי)|'
    r'(?:synthetic|organic|reactive|acid|disperse|vat|direct)\s*dye|'
    r'dyestuff|colorant|pigment\s*(?:dye|organic)|'
    r'fluorescent\s*(?:brightener|whitener)|optical\s*brightener)',
    re.IGNORECASE
)
_CH32_PIGMENT = re.compile(
    r'(?:פיגמנט|pigment|colour\s*(?:lake|preparation)|'
    r'titanium\s*dioxide\s*pigment|iron\s*oxide\s*pigment|'
    r'carbon\s*black\s*pigment|zinc\s*(?:oxide|chromate)\s*pigment)',
    re.IGNORECASE
)
_CH32_PAINT = re.compile(
    r'(?:צבע\s*(?:קיר|שמן|אקריל|לטקס|תרסיס|ים)|'
    r'paint|enamel|lacquer|distemper|varnish|'
    r'(?:acrylic|latex|oil|water)\s*(?:based\s*)?paint|'
    r'anti.?fouling|anti.?corrosive\s*paint|primer|undercoat|putty|'
    r'wood\s*(?:stain|filler))',
    re.IGNORECASE
)
_CH32_INK = re.compile(
    r'(?:דיו|ink|printing\s*ink|writing\s*ink|stamp\s*pad\s*ink)',
    re.IGNORECASE
)
_CH32_ARTISTS = re.compile(
    r'(?:צבע\s*(?:אמנים|שמן\s*אמנים)|'
    r'artist.?s?\s*(?:colour|color|paint)|water.?colour|oil\s*(?:colour|color)|'
    r'poster\s*(?:colour|paint)|tempera)',
    re.IGNORECASE
)


def _is_chapter_32_candidate(text):
    return bool(
        _CH32_TANNING.search(text) or _CH32_DYE.search(text)
        or _CH32_PIGMENT.search(text) or _CH32_PAINT.search(text)
        or _CH32_INK.search(text) or _CH32_ARTISTS.search(text)
    )


def _decide_chapter_32(product):
    """Chapter 32: Tanning/dyeing; dyes; pigments; paints; varnishes; inks; putty.

    Headings:
        32.01-32.02 — Tanning extracts; tanning substances
        32.04 — Synthetic organic colouring matter (dyes)
        32.06 — Colour preparations; pigments; colour lakes
        32.08-32.10 — Paints, varnishes, enamels (dissolved in non-aqueous / aqueous)
        32.12 — Pigments in non-aqueous media (stamping foils, dyes for retail)
        32.13 — Artists' colours
        32.15 — Printing ink, writing ink, drawing ink
    """
    text = _product_text(product)
    result = {"chapter": 32, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH32_TANNING.search(text):
        result["candidates"].append({"heading": "32.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Tanning extract / tanning agent → 32.01.",
            "rule_applied": "GIR 1 — heading 32.01"})
        return result
    if _CH32_INK.search(text):
        result["candidates"].append({"heading": "32.15", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Printing / writing / drawing ink → 32.15.",
            "rule_applied": "GIR 1 — heading 32.15"})
        return result
    if _CH32_ARTISTS.search(text):
        result["candidates"].append({"heading": "32.13", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Artists' colours / watercolour / tempera → 32.13.",
            "rule_applied": "GIR 1 — heading 32.13"})
        return result
    if _CH32_DYE.search(text):
        result["candidates"].append({"heading": "32.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Synthetic dye / dyestuff / colorant → 32.04.",
            "rule_applied": "GIR 1 — heading 32.04"})
        return result
    if _CH32_PIGMENT.search(text):
        result["candidates"].append({"heading": "32.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Pigment / colour preparation / colour lake → 32.06.",
            "rule_applied": "GIR 1 — heading 32.06"})
        return result
    if _CH32_PAINT.search(text):
        result["candidates"].append({"heading": "32.09", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Paint / varnish / lacquer / enamel / primer → 32.09.",
            "rule_applied": "GIR 1 — heading 32.09"})
        return result

    result["candidates"].append({"heading": "32.12", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Tanning/dyeing/paint product n.e.s. → 32.12.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type of product? (tanning agent, dye, pigment, paint/varnish, ink, artists' colours)")
    return result


# ============================================================================
# CHAPTER 33: Essential oils, resinoids; perfumery, cosmetic, toiletry preparations
# ============================================================================

_CH33_ESSENTIAL_OIL = re.compile(
    r'(?:שמן\s*(?:אתרי|אתרים)|'
    r'essential\s*oil|resinoid|oleoresin|'
    r'(?:lavender|peppermint|eucalyptus|tea\s*tree|rose|lemon)\s*oil)',
    re.IGNORECASE
)
_CH33_PERFUME = re.compile(
    r'(?:בושם|בשמים|מי\s*(?:בושם|טואלט)|'
    r'perfume|parfum|eau\s*de\s*(?:toilette|parfum|cologne)|'
    r'cologne|fragrance|aftershave)',
    re.IGNORECASE
)
_CH33_CREAM_LOTION = re.compile(
    r'(?:קרם\s*(?:פנים|ידיים|גוף|עור|לחות|שיזוף|הגנה)|'
    r'(?:skin|face|hand|body|moisturizing|sunscreen|sun\s*protection)\s*cream|'
    r'lotion|body\s*(?:lotion|milk|butter)|sunblock|SPF)',
    re.IGNORECASE
)
_CH33_SHAMPOO = re.compile(
    r'(?:שמפו|מרכך|conditioner|shampoo|hair\s*(?:conditioner|rinse|mask|treatment|serum))',
    re.IGNORECASE
)
_CH33_TOOTHPASTE = re.compile(
    r'(?:משחת?\s*שיניים|שטיפת?\s*פה|'
    r'toothpaste|dentifrice|mouthwash|mouth\s*rinse|dental\s*(?:floss|preparation))',
    re.IGNORECASE
)
_CH33_DEODORANT = re.compile(
    r'(?:דאודורנט|אנטיפרספירנט|deodorant|antiperspirant)',
    re.IGNORECASE
)
_CH33_MAKEUP = re.compile(
    r'(?:איפור|שפתון|לק|מסקרה|אייליינר|פודרה|סומק|'
    r'(?:lip|eye)\s*(?:stick|liner|shadow|pencil|gloss)|'
    r'mascara|foundation|blush|rouge|powder\s*(?:compact|face)|'
    r'nail\s*(?:polish|varnish|lacquer)|makeup|cosmetic\s*(?:set|kit))',
    re.IGNORECASE
)
_CH33_SHAVING = re.compile(
    r'(?:קרם\s*גילוח|סבון\s*גילוח|shaving\s*(?:cream|foam|gel|soap)|'
    r'pre.?shave|after.?shave\s*(?:balm|lotion))',
    re.IGNORECASE
)


def _is_chapter_33_candidate(text):
    return bool(
        _CH33_ESSENTIAL_OIL.search(text) or _CH33_PERFUME.search(text)
        or _CH33_CREAM_LOTION.search(text) or _CH33_SHAMPOO.search(text)
        or _CH33_TOOTHPASTE.search(text) or _CH33_DEODORANT.search(text)
        or _CH33_MAKEUP.search(text) or _CH33_SHAVING.search(text)
    )


def _decide_chapter_33(product):
    """Chapter 33: Essential oils; perfumery, cosmetic, toiletry preparations.

    Headings:
        33.01 — Essential oils; resinoids; extracted oleoresins
        33.02 — Mixtures of odoriferous substances (for food/beverage industry)
        33.03 — Perfumes and toilet waters
        33.04 — Beauty/make-up/skin-care preparations; sunscreen; manicure/pedicure
        33.05 — Hair preparations (shampoo, conditioner, hair spray, dyes)
        33.06 — Oral/dental hygiene (toothpaste, mouthwash, dental floss)
        33.07 — Shaving, deodorant, bath, depilatory, room perfuming preparations
    """
    text = _product_text(product)
    result = {"chapter": 33, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH33_ESSENTIAL_OIL.search(text):
        result["candidates"].append({"heading": "33.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Essential oil / resinoid / oleoresin → 33.01.",
            "rule_applied": "GIR 1 — heading 33.01"})
        return result
    if _CH33_PERFUME.search(text):
        result["candidates"].append({"heading": "33.03", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Perfume / eau de toilette / cologne → 33.03.",
            "rule_applied": "GIR 1 — heading 33.03"})
        return result
    if _CH33_TOOTHPASTE.search(text):
        result["candidates"].append({"heading": "33.06", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Toothpaste / mouthwash / dental prep → 33.06.",
            "rule_applied": "GIR 1 — heading 33.06"})
        return result
    if _CH33_SHAMPOO.search(text):
        result["candidates"].append({"heading": "33.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Shampoo / hair conditioner / hair treatment → 33.05.",
            "rule_applied": "GIR 1 — heading 33.05"})
        return result
    if _CH33_DEODORANT.search(text) or _CH33_SHAVING.search(text):
        result["candidates"].append({"heading": "33.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Deodorant / shaving prep / bath prep → 33.07.",
            "rule_applied": "GIR 1 — heading 33.07"})
        return result
    if _CH33_MAKEUP.search(text) or _CH33_CREAM_LOTION.search(text):
        result["candidates"].append({"heading": "33.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Cosmetic / skin-care / makeup / sunscreen → 33.04.",
            "rule_applied": "GIR 1 — heading 33.04"})
        return result

    result["candidates"].append({"heading": "33.04", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Cosmetic/toiletry product n.e.s. → 33.04.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type? (essential oil, perfume, skin cream, shampoo, toothpaste, deodorant, makeup)")
    return result


# ============================================================================
# CHAPTER 34: Soap, washing preparations, lubricating preparations, waxes, candles
# ============================================================================

_CH34_SOAP = re.compile(
    r'(?:סבון|soap\s*(?:bar|liquid|flake)?)',
    re.IGNORECASE
)
_CH34_DETERGENT = re.compile(
    r'(?:חומר\s*(?:ניקוי|כביסה|שטיפה)|דטרגנט|אבקת\s*כביסה|מרכך\s*כביסה|'
    r'detergent|washing\s*(?:powder|liquid|agent)|laundry\s*(?:powder|liquid|detergent)|'
    r'dish\s*(?:soap|liquid|detergent)|fabric\s*(?:softener|conditioner)|'
    r'surfactant|surface.?active\s*(?:agent|preparation))',
    re.IGNORECASE
)
_CH34_POLISH = re.compile(
    r'(?:משחת?\s*(?:נעליים|רצפה|רהיטים)|'
    r'polish|shoe\s*(?:cream|polish)|floor\s*polish|furniture\s*polish|'
    r'scouring\s*(?:paste|powder|cream))',
    re.IGNORECASE
)
_CH34_WAX = re.compile(
    r'(?:שעווה\s*(?:מלאכותית|סינתטית)|'
    r'artificial\s*wax|prepared\s*wax|wax\s*(?:polish|preparation)|'
    r'modelling\s*(?:paste|clay|wax))',
    re.IGNORECASE
)
_CH34_CANDLE = re.compile(
    r'(?:נר|נרות|candle|taper|night.?light)',
    re.IGNORECASE
)


def _is_chapter_34_candidate(text):
    return bool(
        _CH34_SOAP.search(text) or _CH34_DETERGENT.search(text)
        or _CH34_POLISH.search(text) or _CH34_WAX.search(text)
        or _CH34_CANDLE.search(text)
    )


def _decide_chapter_34(product):
    """Chapter 34: Soap, organic surface-active agents, washing preparations, waxes, candles.

    Headings:
        34.01 — Soap; organic surface-active products in bars/flakes for soap use
        34.02 — Organic surface-active agents; washing/cleaning preparations; detergents
        34.04 — Artificial waxes and prepared waxes
        34.05 — Polishes, creams (shoe, furniture, floor, car)
        34.06 — Candles, tapers, and the like
    """
    text = _product_text(product)
    result = {"chapter": 34, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH34_CANDLE.search(text):
        result["candidates"].append({"heading": "34.06", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Candle / taper → 34.06.",
            "rule_applied": "GIR 1 — heading 34.06"})
        return result
    if _CH34_DETERGENT.search(text):
        result["candidates"].append({"heading": "34.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Detergent / washing preparation / surfactant → 34.02.",
            "rule_applied": "GIR 1 — heading 34.02"})
        return result
    if _CH34_POLISH.search(text):
        result["candidates"].append({"heading": "34.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Polish (shoe/floor/furniture/scouring) → 34.05.",
            "rule_applied": "GIR 1 — heading 34.05"})
        return result
    if _CH34_WAX.search(text):
        result["candidates"].append({"heading": "34.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Artificial/prepared wax → 34.04.",
            "rule_applied": "GIR 1 — heading 34.04"})
        return result
    if _CH34_SOAP.search(text):
        result["candidates"].append({"heading": "34.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Soap (bar/liquid/flake) → 34.01.",
            "rule_applied": "GIR 1 — heading 34.01"})
        return result

    result["candidates"].append({"heading": "34.02", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Soap/detergent product unclear → 34.02.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type? (soap bar, detergent, polish, wax, candle)")
    return result


# ============================================================================
# CHAPTER 35: Albuminoidal substances; modified starches; glues; enzymes
# ============================================================================

_CH35_CASEIN = re.compile(
    r'(?:קזאין|אלבומין|casein|caseinates|albumin|gelatin|gelatine|'
    r'peptone|dextrin|isinglass)',
    re.IGNORECASE
)
_CH35_STARCH_MODIFIED = re.compile(
    r'(?:עמילן\s*(?:שונה|מותאם)|'
    r'modified\s*starch|esterified\s*starch|etherified\s*starch|'
    r'pregelatinised\s*starch)',
    re.IGNORECASE
)
_CH35_GLUE = re.compile(
    r'(?:דבק|glue|adhesive|prepared\s*glue|animal\s*glue|'
    r'casein\s*glue|starch\s*(?:glue|paste)|'
    r'rubber\s*cement|contact\s*(?:adhesive|cement))',
    re.IGNORECASE
)
_CH35_ENZYME = re.compile(
    r'(?:אנזים|enzyme|rennet|pepsin|lipase|protease|amylase|'
    r'cellulase|lactase)',
    re.IGNORECASE
)


def _is_chapter_35_candidate(text):
    return bool(
        _CH35_CASEIN.search(text) or _CH35_STARCH_MODIFIED.search(text)
        or _CH35_GLUE.search(text) or _CH35_ENZYME.search(text)
    )


def _decide_chapter_35(product):
    """Chapter 35: Albuminoidal substances; modified starches; glues; enzymes.

    Headings:
        35.01 — Casein, caseinates, casein glues; albumins
        35.02 — Albumins, albuminates; other albumin derivatives
        35.03 — Gelatin; isinglass; other glues of animal origin
        35.04 — Peptones; other protein substances; hide powder
        35.05 — Dextrins; modified starches; starch-based glues
        35.06 — Prepared glues n.e.s.; adhesives; products for use as glues
        35.07 — Enzymes; prepared enzymes n.e.s.
    """
    text = _product_text(product)
    result = {"chapter": 35, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH35_ENZYME.search(text):
        result["candidates"].append({"heading": "35.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Enzyme (rennet/pepsin/lipase/protease) → 35.07.",
            "rule_applied": "GIR 1 — heading 35.07"})
        return result
    if _CH35_GLUE.search(text):
        result["candidates"].append({"heading": "35.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Prepared glue / adhesive → 35.06.",
            "rule_applied": "GIR 1 — heading 35.06"})
        return result
    if _CH35_STARCH_MODIFIED.search(text):
        result["candidates"].append({"heading": "35.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Modified starch / dextrin → 35.05.",
            "rule_applied": "GIR 1 — heading 35.05"})
        return result
    if _CH35_CASEIN.search(text):
        if re.search(r'(?:ג\'לטין|gelatin|gelatine|isinglass)', text, re.IGNORECASE):
            heading, reasoning = "35.03", "Gelatin / isinglass → 35.03."
        else:
            heading, reasoning = "35.01", "Casein / albumin → 35.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "35.06", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Albuminoidal/glue/enzyme product n.e.s. → 35.06.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type? (casein/albumin, gelatin, modified starch, glue/adhesive, enzyme)")
    return result


# ============================================================================
# CHAPTER 36: Explosives; pyrotechnic products; matches; pyrophoric alloys
# ============================================================================

_CH36_EXPLOSIVE = re.compile(
    r'(?:חומר\s*נפץ|חומרי\s*נפץ|TNT|דינמיט|'
    r'explosive|dynamite|TNT|detonator|blasting\s*cap|'
    r'detonating\s*(?:fuse|cord)|propellant\s*powder|'
    r'gun\s*powder|smokeless\s*powder)',
    re.IGNORECASE
)
_CH36_FIREWORK = re.compile(
    r'(?:זיקוקין|זיקוקי\s*דינור|אבוקה|'
    r'firework|firecracker|pyrotechnic|signal\s*(?:flare|rocket)|'
    r'distress\s*signal|rain\s*rocket|fog\s*signal)',
    re.IGNORECASE
)
_CH36_MATCH = re.compile(
    r'(?:גפרור|גפרורים|match|safety\s*match|strike\s*anywhere)',
    re.IGNORECASE
)
_CH36_FERRO_CERIUM = re.compile(
    r'(?:אבן\s*(?:צור|מצית)|ferro.?cerium|pyrophoric\s*alloy|'
    r'lighter\s*flint)',
    re.IGNORECASE
)


def _is_chapter_36_candidate(text):
    return bool(
        _CH36_EXPLOSIVE.search(text) or _CH36_FIREWORK.search(text)
        or _CH36_MATCH.search(text) or _CH36_FERRO_CERIUM.search(text)
    )


def _decide_chapter_36(product):
    """Chapter 36: Explosives; pyrotechnic products; matches; pyrophoric alloys.

    Headings:
        36.01 — Propellant powders
        36.02 — Prepared explosives (dynamite, TNT, etc.)
        36.03 — Detonating/safety fuses; detonators; electric detonators; igniters
        36.04 — Fireworks, signalling flares, rain rockets, fog signals, etc.
        36.05 — Matches
        36.06 — Ferro-cerium and other pyrophoric alloys; lighter flints
    """
    text = _product_text(product)
    result = {"chapter": 36, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH36_MATCH.search(text):
        result["candidates"].append({"heading": "36.05", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Matches / safety matches → 36.05.",
            "rule_applied": "GIR 1 — heading 36.05"})
        return result
    if _CH36_FIREWORK.search(text):
        result["candidates"].append({"heading": "36.04", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Fireworks / pyrotechnics / signal flares → 36.04.",
            "rule_applied": "GIR 1 — heading 36.04"})
        return result
    if _CH36_FERRO_CERIUM.search(text):
        result["candidates"].append({"heading": "36.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Ferro-cerium / pyrophoric alloy / lighter flint → 36.06.",
            "rule_applied": "GIR 1 — heading 36.06"})
        return result
    if _CH36_EXPLOSIVE.search(text):
        if re.search(r'(?:detonator|fuse|igniter|blasting\s*cap)', text, re.IGNORECASE):
            heading, reasoning = "36.03", "Detonator / fuse / igniter → 36.03."
        elif re.search(r'(?:propellant|gun\s*powder|smokeless)', text, re.IGNORECASE):
            heading, reasoning = "36.01", "Propellant powder → 36.01."
        else:
            heading, reasoning = "36.02", "Prepared explosive (dynamite/TNT) → 36.02."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "36.02", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Explosive/pyrotechnic product n.e.s. → 36.02.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type? (explosive, firework, match, detonator, propellant)")
    return result


# ============================================================================
# CHAPTER 37: Photographic or cinematographic goods
# ============================================================================

_CH37_FILM = re.compile(
    r'(?:סרט\s*(?:צילום|צילומי|קולנוע|רנטגן)|'
    r'photographic\s*(?:film|plate)|x.?ray\s*film|'
    r'cinematographic\s*film|instant\s*print\s*film|'
    r'microfilm|microfiche)',
    re.IGNORECASE
)
_CH37_PAPER = re.compile(
    r'(?:נייר\s*(?:צילום|פוטו)|'
    r'photographic\s*paper|sensitized\s*(?:paper|textile)|'
    r'photo\s*paper)',
    re.IGNORECASE
)
_CH37_CHEMICAL_PHOTO = re.compile(
    r'(?:תכשיר\s*צילום|chemical\s*(?:for\s*)?photograph|'
    r'developer|fixer|photographic\s*(?:chemical|reagent)|'
    r'toner\s*(?:photographic|cartridge)|unmixed\s*product\s*(?:for\s*)?photograph)',
    re.IGNORECASE
)


def _is_chapter_37_candidate(text):
    return bool(
        _CH37_FILM.search(text) or _CH37_PAPER.search(text)
        or _CH37_CHEMICAL_PHOTO.search(text)
    )


def _decide_chapter_37(product):
    """Chapter 37: Photographic or cinematographic goods.

    Headings:
        37.01 — Photographic plates and film in flat form, sensitised, unexposed
        37.02 — Photographic film in rolls, sensitised, unexposed
        37.03 — Photographic paper/textiles, sensitised, unexposed
        37.04 — Photographic plates, film, paper, exposed but not developed
        37.05 — Photographic plates and film, exposed and developed (excl. cinema film)
        37.06 — Cinematographic film, exposed and developed
        37.07 — Chemical preparations for photographic uses
    """
    text = _product_text(product)
    result = {"chapter": 37, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH37_CHEMICAL_PHOTO.search(text):
        result["candidates"].append({"heading": "37.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Photographic chemical (developer/fixer/toner) → 37.07.",
            "rule_applied": "GIR 1 — heading 37.07"})
        return result
    if _CH37_PAPER.search(text):
        result["candidates"].append({"heading": "37.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Photographic paper / sensitised paper → 37.03.",
            "rule_applied": "GIR 1 — heading 37.03"})
        return result
    if _CH37_FILM.search(text):
        if re.search(r'(?:roll|רול)', text, re.IGNORECASE):
            heading, reasoning = "37.02", "Photographic film in rolls → 37.02."
        elif re.search(r'(?:קולנוע|cinematographic|cinema)', text, re.IGNORECASE):
            heading, reasoning = "37.06", "Cinematographic film → 37.06."
        else:
            heading, reasoning = "37.01", "Photographic plate/film in flat form → 37.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "37.07", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Photographic product n.e.s. → 37.07.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type? (film, paper, chemicals/developer)")
    return result


# ============================================================================
# CHAPTER 38: Miscellaneous chemical products
# ============================================================================

_CH38_INSECTICIDE = re.compile(
    r'(?:חומר\s*(?:הדברה|קוטל\s*(?:חרקים|עשבים|פטריות|מזיקים))|'
    r'insecticide|pesticide|herbicide|fungicide|rodenticide|'
    r'disinsecting|weed\s*killer|bug\s*spray|ant\s*killer|'
    r'mosquito\s*(?:repellent|coil)|plant\s*growth\s*regulator)',
    re.IGNORECASE
)
_CH38_DISINFECTANT = re.compile(
    r'(?:חומר\s*(?:חיטוי|דזינפקציה)|'
    r'disinfectant|sanitizer|sanitiser|sterilising|germicide|'
    r'bactericide|antiseptic\s*(?:solution|product))',
    re.IGNORECASE
)
_CH38_ANTIFREEZE = re.compile(
    r'(?:נוזל\s*(?:קירור|נגד\s*קפיאה)|'
    r'antifreeze|anti.?freeze|de.?icing\s*(?:fluid|preparation)|'
    r'coolant\s*(?:fluid|liquid))',
    re.IGNORECASE
)
_CH38_BIODIESEL = re.compile(
    r'(?:ביודיזל|bio.?diesel|bio.?ethanol|bio.?fuel|'
    r'fatty\s*acid\s*methyl\s*ester|FAME)',
    re.IGNORECASE
)
_CH38_DIAGNOSTIC = re.compile(
    r'(?:ריאגנט\s*(?:אבחון|מעבדה)|'
    r'diagnostic\s*(?:reagent|kit|test)|laboratory\s*reagent|'
    r'certified\s*reference\s*material)',
    re.IGNORECASE
)
_CH38_FLUX = re.compile(
    r'(?:שטף\s*(?:הלחמה|ריתוך)|flux|soldering\s*flux|welding\s*flux|'
    r'pickling\s*(?:preparation|paste)|electroplating\s*preparation)',
    re.IGNORECASE
)
_CH38_ACTIVATED_CARBON = re.compile(
    r'(?:פחם\s*פעיל|activated\s*(?:carbon|charcoal)|'
    r'activated\s*natural\s*mineral|activated\s*earth)',
    re.IGNORECASE
)
_CH38_GENERAL_CHEMICAL = re.compile(
    r'(?:תכשיר\s*כימי|chemical\s*(?:preparation|product)\s*n\.?e\.?s|'
    r'residual\s*(?:product|lye)|industrial\s*(?:fatty\s*acid|tall\s*oil))',
    re.IGNORECASE
)


def _is_chapter_38_candidate(text):
    return bool(
        _CH38_INSECTICIDE.search(text) or _CH38_DISINFECTANT.search(text)
        or _CH38_ANTIFREEZE.search(text) or _CH38_BIODIESEL.search(text)
        or _CH38_DIAGNOSTIC.search(text) or _CH38_FLUX.search(text)
        or _CH38_ACTIVATED_CARBON.search(text) or _CH38_GENERAL_CHEMICAL.search(text)
    )


def _decide_chapter_38(product):
    """Chapter 38: Miscellaneous chemical products.

    Headings:
        38.02 — Activated carbon; activated natural mineral products
        38.08 — Insecticides, rodenticides, herbicides, fungicides, disinfectants
        38.09 — Finishing agents, dye carriers, pickling preparations
        38.10 — Metal pickling/soldering/welding/electroplating preparations
        38.20 — Anti-freezing preparations; de-icing fluids
        38.21 — Culture media for micro-organisms; diagnostic/laboratory reagents
        38.22 — Composite diagnostic/laboratory reagents (excl. Ch.30)
        38.24 — Prepared binders for foundry moulds; chemical products n.e.s.
        38.26 — Biodiesel (FAME and blends thereof)
    """
    text = _product_text(product)
    result = {"chapter": 38, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH38_INSECTICIDE.search(text):
        result["candidates"].append({"heading": "38.08", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Insecticide / herbicide / fungicide / pesticide → 38.08.",
            "rule_applied": "GIR 1 — heading 38.08"})
        return result
    if _CH38_DISINFECTANT.search(text):
        result["candidates"].append({"heading": "38.08", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Disinfectant / sanitizer / germicide → 38.08.",
            "rule_applied": "GIR 1 — heading 38.08"})
        return result
    if _CH38_ANTIFREEZE.search(text):
        result["candidates"].append({"heading": "38.20", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Antifreeze / de-icing fluid / coolant → 38.20.",
            "rule_applied": "GIR 1 — heading 38.20"})
        return result
    if _CH38_BIODIESEL.search(text):
        result["candidates"].append({"heading": "38.26", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Biodiesel / FAME / biofuel → 38.26.",
            "rule_applied": "GIR 1 — heading 38.26"})
        return result
    if _CH38_DIAGNOSTIC.search(text):
        result["candidates"].append({"heading": "38.22", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Diagnostic reagent / laboratory reagent / test kit → 38.22.",
            "rule_applied": "GIR 1 — heading 38.22"})
        return result
    if _CH38_ACTIVATED_CARBON.search(text):
        result["candidates"].append({"heading": "38.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Activated carbon / charcoal / activated earth → 38.02.",
            "rule_applied": "GIR 1 — heading 38.02"})
        return result
    if _CH38_FLUX.search(text):
        result["candidates"].append({"heading": "38.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Soldering/welding flux / pickling preparation → 38.10.",
            "rule_applied": "GIR 1 — heading 38.10"})
        return result

    result["candidates"].append({"heading": "38.24", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Miscellaneous chemical product n.e.s. → 38.24.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append(
        "What type? (insecticide, disinfectant, antifreeze, biodiesel, diagnostic reagent, activated carbon)")
    return result


# ============================================================================
# CHAPTER 39: Plastics and articles thereof
# ============================================================================

_CH39_PE = re.compile(
    r'(?:פוליאתילן|polyethylene|PE[\s\-]?(?:HD|LD|LLD|UHM)|HDPE|LDPE|LLDPE|UHMWPE)',
    re.IGNORECASE
)
_CH39_PP = re.compile(
    r'(?:פוליפרופילן|polypropylene|PP\b)',
    re.IGNORECASE
)
_CH39_PVC = re.compile(
    r'(?:פי\.?וי\.?סי|PVC|polyvinyl\s*chloride|vinyl\s*chloride)',
    re.IGNORECASE
)
_CH39_PET = re.compile(
    r'(?:פוליאסטר|\bPET\b|polyethylene\s*terephthalate|\bPETE\b)',
    re.IGNORECASE
)
_CH39_PS = re.compile(
    r'(?:פוליסטירן|polystyrene|styrofoam|styrene|EPS|XPS)',
    re.IGNORECASE
)
_CH39_PU = re.compile(
    r'(?:פוליאורתן|polyurethane|PU\b|PUR\b)',
    re.IGNORECASE
)
_CH39_PRIMARY = re.compile(
    r'(?:גרגיר|גרנול|אבקה|פתיתי|שרף|בצורה\s*ראשונית|'
    r'granule|pellet|resin|powder|flake|primary\s*form|in\s*primary|'
    r'raw\s*material|virgin|compound\b)',
    re.IGNORECASE
)
_CH39_PLATE_FILM = re.compile(
    r'(?:לוח|יריע|סרט|פילם|גיליון|רדיד|'
    r'plate|sheet|film|foil|strip|laminate|membrane|'
    r'self.adhesive|cellular)',
    re.IGNORECASE
)
_CH39_TUBE = re.compile(
    r'(?:צינור|שפופרת|tube|pipe|hose|conduit|fitting|'
    r'אביזר\s*צנרת|pipe\s*fitting|elbow|tee\b|coupling|valve)',
    re.IGNORECASE
)
_CH39_ARTICLES = re.compile(
    r'(?:מיכל|בקבוק|שקית|ארגז|מכסה|פקק|כלי\s*שולחן|'
    r'container|bottle|bag|sack|box|cap|lid|closure|'
    r'tableware|kitchenware|sanitary|bath|tank|barrel|'
    r'carboy|jerry\s*can|packing|crate)',
    re.IGNORECASE
)
_CH39_PLASTIC_GENERAL = re.compile(
    r'(?:פלסטיק|פולימר|ניילון|אקריליק|סיליקון|פוליקרבונט|'
    r'plastic|polymer|resin\b|nylon|acrylic|silicone|polycarbonate|'
    r'polyamide|ABS\b|polyacetal|epoxy\b|alkyd|phenolic|melamine|'
    r'amino\s*resin|polyurethane|polyester\s*(?:resin|film|sheet)|'
    r'polylactic|polyoxymethylene|polyimide)',
    re.IGNORECASE
)


def _is_chapter_39_candidate(text):
    return bool(
        _CH39_PE.search(text) or _CH39_PP.search(text) or _CH39_PVC.search(text)
        or _CH39_PET.search(text) or _CH39_PS.search(text) or _CH39_PU.search(text)
        or _CH39_PLASTIC_GENERAL.search(text)
    )


def _decide_chapter_39(product):
    """Chapter 39: Plastics and articles thereof.

    Key decision: polymer type → form (primary/plate-film/tube/articles).
    Headings:
        39.01-39.14 — Polymers in primary forms
        39.15 — Waste, parings, scrap
        39.16 — Monofilament; rods, sticks, profiles
        39.17 — Tubes, pipes, hoses and fittings
        39.18 — Floor coverings
        39.19 — Self-adhesive plates/sheets/film/tape
        39.20 — Other plates/sheets/film/foil (non-cellular, not reinforced)
        39.21 — Other plates/sheets/film/foil (cellular or combined)
        39.22 — Baths, showers, sinks, WC seats (sanitary ware)
        39.23 — Articles for conveyance/packing (containers, bottles, bags)
        39.24 — Tableware, kitchenware, household articles
        39.25 — Builders' ware (tanks, doors, windows, shutters)
        39.26 — Other articles of plastics
    """
    text = _product_text(product)
    result = {"chapter": 39, "candidates": [], "redirect": None, "questions_needed": []}

    # Step 1: Detect form — articles override polymer-type routing
    if _CH39_TUBE.search(text):
        result["candidates"].append({"heading": "39.17", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Plastic tube / pipe / hose / fitting → 39.17.",
            "rule_applied": "GIR 1 — heading 39.17"})
        return result
    if re.search(r'(?:אמבט|כיור|אסלה|מקלחת|bath|shower|sink|WC|lavatory|bidet|sanitary)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "39.22", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Plastic sanitary ware (bath/sink/WC) → 39.22.",
            "rule_applied": "GIR 1 — heading 39.22"})
        return result
    if _CH39_ARTICLES.search(text):
        if re.search(r'(?:בקבוק|שקית|מיכל|bottle|bag|sack|container|packing|barrel|jerry|carboy|crate)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "39.23", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Plastic packing article (bottle/bag/container) → 39.23.",
                "rule_applied": "GIR 1 — heading 39.23"})
        elif re.search(r'(?:כלי\s*שולחן|tableware|kitchenware|cup|plate|bowl|tray)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "39.24", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Plastic tableware / kitchenware → 39.24.",
                "rule_applied": "GIR 1 — heading 39.24"})
        else:
            result["candidates"].append({"heading": "39.26", "subheading_hint": None,
                "confidence": 0.70, "reasoning": "Other plastic article → 39.26.",
                "rule_applied": "GIR 1 — heading 39.26"})
        return result

    # Step 2: Plates/sheets/film
    if _CH39_PLATE_FILM.search(text):
        if re.search(r'(?:self.adhesive|דביק)', text, re.IGNORECASE):
            heading = "39.19"
        elif re.search(r'(?:cellular|קצף|foam)', text, re.IGNORECASE):
            heading = "39.21"
        else:
            heading = "39.20"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Plastic plate/sheet/film → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # Step 3: Primary forms — route by polymer type
    if _CH39_PRIMARY.search(text) or not _CH39_ARTICLES.search(text):
        if _CH39_PE.search(text):
            heading = "39.01"
            reasoning = "Polyethylene in primary forms → 39.01."
        elif _CH39_PP.search(text):
            heading = "39.02"
            reasoning = "Polypropylene in primary forms → 39.02."
        elif _CH39_PVC.search(text):
            heading = "39.04"
            reasoning = "PVC / vinyl chloride polymer in primary forms → 39.04."
        elif _CH39_PS.search(text):
            heading = "39.03"
            reasoning = "Polystyrene in primary forms → 39.03."
        elif _CH39_PET.search(text):
            heading = "39.07"
            reasoning = "PET / polyester in primary forms → 39.07."
        elif _CH39_PU.search(text):
            heading = "39.09"
            reasoning = "Polyurethane in primary forms → 39.09."
        else:
            heading = "39.11"
            reasoning = "Other polymer in primary forms → 39.11."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "39.26", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Plastic article n.e.s. → 39.26.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What form? (granules/pellets, sheet/film, tube/pipe, bottle/bag, tableware)")
    return result


# ============================================================================
# CHAPTER 40: Rubber and articles thereof
# ============================================================================

_CH40_NATURAL = re.compile(
    r'(?:גומי\s*טבעי|לטקס\s*טבעי|natural\s*rubber|latex\s*natural|'
    r'hevea|caoutchouc|balata|gutta.percha|guayule|chicle)',
    re.IGNORECASE
)
_CH40_SYNTHETIC = re.compile(
    r'(?:גומי\s*סינתטי|סינתטי|synthetic\s*rubber|SBR|NBR|EPDM|'
    r'chloroprene|neoprene|butadiene|isoprene|nitrile\s*rubber|'
    r'butyl\s*rubber|silicone\s*rubber)',
    re.IGNORECASE
)
_CH40_TYRE = re.compile(
    r'(?:צמיג|טייר|tyre|tire|pneumatic|radial\s*tyre|retreaded)',
    re.IGNORECASE
)
_CH40_TUBE = re.compile(
    r'(?:פנימית|inner\s*tube|tube\s*for\s*tyre|tube\s*for\s*tire)',
    re.IGNORECASE
)
_CH40_BELT = re.compile(
    r'(?:רצועת?\s*הינע|conveyor\s*belt|transmission\s*belt|V.belt|'
    r'synchronous\s*belt|timing\s*belt|fan\s*belt)',
    re.IGNORECASE
)
_CH40_HOSE = re.compile(
    r'(?:צינור\s*גומי|צינור\s*גמיש|rubber\s*hose|flexible\s*hose|'
    r'hydraulic\s*hose|reinforced\s*hose)',
    re.IGNORECASE
)
_CH40_GLOVE = re.compile(
    r'(?:כפפ|rubber\s*glove|latex\s*glove|nitrile\s*glove|'
    r'surgical\s*glove|examination\s*glove|disposable\s*glove)',
    re.IGNORECASE
)
_CH40_RUBBER_GENERAL = re.compile(
    r'(?:גומי|rubber|vulcani[sz]ed|elastomer|gasket|seal|washer|'
    r'O.ring|grommet|bumper|buffer|mat\s*rubber)',
    re.IGNORECASE
)


def _is_chapter_40_candidate(text):
    return bool(
        _CH40_NATURAL.search(text) or _CH40_SYNTHETIC.search(text)
        or _CH40_TYRE.search(text) or _CH40_RUBBER_GENERAL.search(text)
    )


def _decide_chapter_40(product):
    """Chapter 40: Rubber and articles thereof.

    Key decision: natural vs synthetic → form (raw/vulcanised/articles).
    Headings:
        40.01 — Natural rubber latex
        40.02 — Synthetic rubber and factice
        40.05 — Compounded rubber, unvulcanised
        40.06 — Other forms of unvulcanised rubber (rods, tubes, profiles)
        40.07 — Vulcanised rubber thread and cord
        40.08 — Plates, sheets, strip of vulcanised rubber
        40.09 — Tubes, pipes, hoses of vulcanised rubber
        40.10 — Conveyor/transmission belts of vulcanised rubber
        40.11 — New pneumatic tyres
        40.12 — Retreaded/used tyres; solid/cushion tyres; tyre flaps
        40.13 — Inner tubes
        40.14 — Hygienic/pharmaceutical articles (teats, gloves, etc.)
        40.15 — Articles of apparel (gloves, aprons)
        40.16 — Other articles of vulcanised rubber
        40.17 — Hard rubber (ebonite) articles
    """
    text = _product_text(product)
    result = {"chapter": 40, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH40_TYRE.search(text):
        if re.search(r'(?:retreaded|משופדר|used|solid|cushion|flap)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "40.12", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Retreaded/used/solid tyre or flap → 40.12.",
                "rule_applied": "GIR 1 — heading 40.12"})
        else:
            result["candidates"].append({"heading": "40.11", "subheading_hint": None,
                "confidence": 0.90, "reasoning": "New pneumatic tyre → 40.11.",
                "rule_applied": "GIR 1 — heading 40.11"})
        return result
    if _CH40_TUBE.search(text):
        result["candidates"].append({"heading": "40.13", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Inner tube for tyre → 40.13.",
            "rule_applied": "GIR 1 — heading 40.13"})
        return result
    if _CH40_GLOVE.search(text):
        if re.search(r'(?:surgical|medical|examination|חד\s*פעמי|disposable|nitrile\s*glove|latex\s*glove)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "40.15", "subheading_hint": "4015.19",
                "confidence": 0.85, "reasoning": "Rubber/latex/nitrile gloves → 40.15.",
                "rule_applied": "GIR 1 — heading 40.15"})
        else:
            result["candidates"].append({"heading": "40.15", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Rubber gloves → 40.15.",
                "rule_applied": "GIR 1 — heading 40.15"})
        return result
    if _CH40_BELT.search(text):
        result["candidates"].append({"heading": "40.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Conveyor / transmission belt → 40.10.",
            "rule_applied": "GIR 1 — heading 40.10"})
        return result
    if _CH40_HOSE.search(text):
        result["candidates"].append({"heading": "40.09", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Rubber hose / flexible tube → 40.09.",
            "rule_applied": "GIR 1 — heading 40.09"})
        return result
    # Raw rubber
    if _CH40_NATURAL.search(text):
        result["candidates"].append({"heading": "40.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Natural rubber / latex → 40.01.",
            "rule_applied": "GIR 1 — heading 40.01"})
        return result
    if _CH40_SYNTHETIC.search(text):
        result["candidates"].append({"heading": "40.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Synthetic rubber → 40.02.",
            "rule_applied": "GIR 1 — heading 40.02"})
        return result

    # Fallback: vulcanised article
    result["candidates"].append({"heading": "40.16", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Rubber article n.e.s. → 40.16.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type? (tyre, glove, belt, hose, raw rubber, gasket/seal)")
    return result


# ============================================================================
# CHAPTER 41: Raw hides and skins (other than furskins) and leather
# ============================================================================

_CH41_RAW = re.compile(
    r'(?:עור\s*גולמי|עור\s*ירוק|שלח|raw\s*hide|raw\s*skin|'
    r'green\s*hide|salted\s*hide|dried\s*hide|pickled\s*hide|'
    r'fresh\s*hide|limed\s*hide)',
    re.IGNORECASE
)
_CH41_WET_BLUE = re.compile(
    r'(?:ווט\s*בלו|wet.blue|chrome.tanned\s*(?:wet|semi)|'
    r'wet.white|pre.tanned)',
    re.IGNORECASE
)
_CH41_CRUST = re.compile(
    r'(?:קראסט|crust\s*leather|crust\s*hide|tanned\s*(?:not|un)\s*finish|'
    r're.tanned|vegetable.tanned\s*crust)',
    re.IGNORECASE
)
_CH41_FINISHED = re.compile(
    r'(?:עור\s*מעובד|עור\s*גמור|finished\s*leather|full.grain|'
    r'split\s*leather|patent\s*leather|chamois|parchment\s*leather|'
    r'nubuck|suede|composition\s*leather|reconstituted)',
    re.IGNORECASE
)
_CH41_BOVINE = re.compile(
    r'(?:בקר|שור|פרה|עגל|buffalo|bovine|cattle|cow|calf|bull|ox|'
    r'buffalo\s*hide|kip)',
    re.IGNORECASE
)
_CH41_SHEEP = re.compile(
    r'(?:כבש|עז|sheep|lamb|goat|kid|ovine|caprine)',
    re.IGNORECASE
)
_CH41_REPTILE = re.compile(
    r'(?:זוחל|תנין|נחש|reptile|crocodile|alligator|snake|lizard|python)',
    re.IGNORECASE
)
_CH41_LEATHER_GENERAL = re.compile(
    r'(?:עור(?:\s|$)|leather|hide|skin|pelt|tanned|tanning)',
    re.IGNORECASE
)


def _is_chapter_41_candidate(text):
    return bool(
        _CH41_RAW.search(text) or _CH41_WET_BLUE.search(text)
        or _CH41_CRUST.search(text) or _CH41_FINISHED.search(text)
        or _CH41_LEATHER_GENERAL.search(text)
    )


def _decide_chapter_41(product):
    """Chapter 41: Raw hides and skins (other than furskins) and leather.

    Key decision: species + tanning state.
    Headings:
        41.01 — Raw hides/skins of bovine/equine (fresh/salted/dried/limed/pickled)
        41.02 — Raw skins of sheep/lambs
        41.03 — Raw hides/skins of other animals
        41.04 — Tanned/crust hides of bovine/equine (no hair, not further prepared)
        41.05 — Tanned/crust skins of sheep/lamb
        41.06 — Tanned/crust hides of other animals
        41.07 — Leather further prepared (bovine/equine) — finished
        41.12 — Leather further prepared (sheep/lamb) — finished
        41.13 — Leather further prepared (other animals) — finished
        41.14 — Chamois leather; patent leather; laminated leather; metallised leather
        41.15 — Composition leather (reconstituted)
    """
    text = _product_text(product)
    result = {"chapter": 41, "candidates": [], "redirect": None, "questions_needed": []}

    is_bovine = bool(_CH41_BOVINE.search(text))
    is_sheep = bool(_CH41_SHEEP.search(text))
    is_reptile = bool(_CH41_REPTILE.search(text))

    # Composition/reconstituted leather
    if re.search(r'(?:composition|reconstituted|שחזור)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "41.15", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Composition / reconstituted leather → 41.15.",
            "rule_applied": "GIR 1 — heading 41.15"})
        return result
    # Chamois / patent
    if re.search(r'(?:chamois|patent\s*leather|metallised|laminated\s*leather)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "41.14", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Chamois / patent / metallised leather → 41.14.",
            "rule_applied": "GIR 1 — heading 41.14"})
        return result

    # Raw hides
    if _CH41_RAW.search(text):
        if is_bovine:
            heading = "41.01"
        elif is_sheep:
            heading = "41.02"
        else:
            heading = "41.03"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": f"Raw hide/skin → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # Wet-blue / crust (tanned, not finished)
    if _CH41_WET_BLUE.search(text) or _CH41_CRUST.search(text):
        if is_bovine:
            heading = "41.04"
        elif is_sheep:
            heading = "41.05"
        else:
            heading = "41.06"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": f"Tanned/crust leather → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # Finished leather
    if _CH41_FINISHED.search(text) or _CH41_LEATHER_GENERAL.search(text):
        if is_bovine:
            heading = "41.07"
        elif is_sheep:
            heading = "41.12"
        elif is_reptile:
            heading = "41.13"
        else:
            heading = "41.07"  # default to bovine
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.75, "reasoning": f"Finished leather → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        if not is_bovine and not is_sheep and not is_reptile:
            result["questions_needed"].append("What animal species? (bovine, sheep/goat, reptile, other)")
        return result

    result["candidates"].append({"heading": "41.07", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Leather type unclear → 41.07 (bovine default).",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Species? Tanning state? (raw, wet-blue, crust, finished)")
    return result


# ============================================================================
# CHAPTER 42: Articles of leather; saddlery; travel goods; handbags
# ============================================================================

_CH42_SADDLERY = re.compile(
    r'(?:אוכף|רתם|רסן|saddlery|harness|saddle|bridle|stirrup|'
    r'horse\s*tack|equestrian)',
    re.IGNORECASE
)
_CH42_HANDBAG = re.compile(
    r'(?:תיק\s*(?:יד|נשים|אופנה)|ארנק|handbag|purse|wallet|'
    r'billfold|card\s*case|clutch\s*bag|tote\s*bag|shoulder\s*bag)',
    re.IGNORECASE
)
_CH42_TRAVEL = re.compile(
    r'(?:מזוודה|תיק\s*נסיעות|תיק\s*גב|trunk|suitcase|travel\s*bag|'
    r'vanity\s*case|attache|briefcase|backpack|rucksack|knapsack|'
    r'school\s*bag|duffel)',
    re.IGNORECASE
)
_CH42_BELT = re.compile(
    r'(?:חגורה|belt(?!\s*(?:conveyor|transmission|V[\s\-]|timing|fan)))',
    re.IGNORECASE
)
_CH42_GLOVE = re.compile(
    r'(?:כפפ.*עור|leather\s*glove|driving\s*glove|dress\s*glove)',
    re.IGNORECASE
)
_CH42_LEATHER_ARTICLE = re.compile(
    r'(?:תיק|ארנק|חגורה|כפפ|מזוודה|leather\s*(?:article|good|case|cover|pouch|strap)|'
    r'leatherware|watch\s*(?:band|strap))',
    re.IGNORECASE
)


def _is_chapter_42_candidate(text):
    return bool(
        _CH42_SADDLERY.search(text) or _CH42_HANDBAG.search(text)
        or _CH42_TRAVEL.search(text) or _CH42_BELT.search(text)
        or _CH42_GLOVE.search(text) or _CH42_LEATHER_ARTICLE.search(text)
    )


def _decide_chapter_42(product):
    """Chapter 42: Articles of leather; saddlery and harness; travel goods; handbags.

    Headings:
        42.01 — Saddlery and harness for animals
        42.02 — Trunks, suitcases, vanity cases, briefcases, school bags, spectacle cases
        42.03 — Articles of apparel and clothing accessories of leather (belts, gloves)
        42.05 — Other articles of leather or composition leather
        42.06 — Articles of gut, goldbeater's skin, bladders, tendons
    """
    text = _product_text(product)
    result = {"chapter": 42, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH42_SADDLERY.search(text):
        result["candidates"].append({"heading": "42.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Saddlery / harness / equestrian gear → 42.01.",
            "rule_applied": "GIR 1 — heading 42.01"})
        return result
    if _CH42_TRAVEL.search(text) or _CH42_HANDBAG.search(text):
        result["candidates"].append({"heading": "42.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Handbag / wallet / suitcase / travel bag → 42.02.",
            "rule_applied": "GIR 1 — heading 42.02"})
        return result
    if _CH42_BELT.search(text) or _CH42_GLOVE.search(text):
        result["candidates"].append({"heading": "42.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Leather belt / glove / clothing accessory → 42.03.",
            "rule_applied": "GIR 1 — heading 42.03"})
        return result

    result["candidates"].append({"heading": "42.05", "subheading_hint": None,
        "confidence": 0.70, "reasoning": "Other leather article → 42.05.",
        "rule_applied": "GIR 1 — heading 42.05"})
    return result


# ============================================================================
# CHAPTER 43: Furskins and artificial fur; manufactures thereof
# ============================================================================

_CH43_RAW_FUR = re.compile(
    r'(?:פרווה\s*גולמי|פרווה\s*גלם|raw\s*furskin|undressed\s*fur|'
    r'mink\s*(?:raw|pelt)|fox\s*(?:raw|pelt)|chinchilla\s*pelt|sable\s*pelt|'
    r'rabbit\s*(?:skin|pelt)|karakul|astrakhan\s*pelt)',
    re.IGNORECASE
)
_CH43_DRESSED_FUR = re.compile(
    r'(?:פרווה\s*מעובד|dressed\s*furskin|tanned\s*fur|dyed\s*fur|'
    r'bleached\s*fur|dressed\s*mink|dressed\s*fox)',
    re.IGNORECASE
)
_CH43_FUR_ARTICLE = re.compile(
    r'(?:מעיל\s*פרווה|פרווה|fur\s*coat|fur\s*jacket|fur\s*trim|'
    r'fur\s*hat|fur\s*collar|fur\s*garment|fur\s*article|'
    r'artificial\s*fur|faux\s*fur|fake\s*fur|imitation\s*fur)',
    re.IGNORECASE
)


def _is_chapter_43_candidate(text):
    return bool(
        _CH43_RAW_FUR.search(text) or _CH43_DRESSED_FUR.search(text)
        or _CH43_FUR_ARTICLE.search(text)
    )


def _decide_chapter_43(product):
    """Chapter 43: Furskins and artificial fur; manufactures thereof.

    Headings:
        43.01 — Raw furskins (mink, lamb, fox, etc.) including heads/tails/pieces
        43.02 — Tanned/dressed furskins (assembled or not)
        43.03 — Articles of apparel, accessories, and other articles of furskin
        43.04 — Artificial fur and articles thereof
    """
    text = _product_text(product)
    result = {"chapter": 43, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:artificial|faux|fake|imitation|מלאכותי)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "43.04", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Artificial / faux fur → 43.04.",
            "rule_applied": "GIR 1 — heading 43.04"})
        return result
    if _CH43_RAW_FUR.search(text):
        result["candidates"].append({"heading": "43.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Raw furskin / undressed pelt → 43.01.",
            "rule_applied": "GIR 1 — heading 43.01"})
        return result
    if _CH43_DRESSED_FUR.search(text):
        result["candidates"].append({"heading": "43.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Dressed / tanned furskin → 43.02.",
            "rule_applied": "GIR 1 — heading 43.02"})
        return result

    # Fur articles (coat, trim, etc.)
    result["candidates"].append({"heading": "43.03", "subheading_hint": None,
        "confidence": 0.80, "reasoning": "Fur garment / article of furskin → 43.03.",
        "rule_applied": "GIR 1 — heading 43.03"})
    return result


# ============================================================================
# CHAPTER 44: Wood and articles of wood; wood charcoal
# ============================================================================

_CH44_LOG = re.compile(
    r'(?:בול\s*עץ|גזע|כריתה|log|round\s*wood|rough\s*wood|'
    r'fuel\s*wood|firewood|wood\s*chips|sawdust|wood\s*waste|'
    r'wood\s*charcoal|פחם\s*עצים)',
    re.IGNORECASE
)
_CH44_SAWN = re.compile(
    r'(?:עץ\s*מנוסר|נסורת|קורה|sawn\s*wood|lumber|timber|'
    r'planed|tongued|grooved|board|plank|beam|joist|scantling)',
    re.IGNORECASE
)
_CH44_PLYWOOD = re.compile(
    r'(?:דיקט|פלייווד|למינציה|plywood|laminated\s*wood|'
    r'veneered\s*panel|veneer\s*sheet|blockboard)',
    re.IGNORECASE
)
_CH44_FIBREBOARD = re.compile(
    r'(?:סיבית|MDF|HDF|fibreboard|fiberboard|hardboard|'
    r'medium\s*density|high\s*density\s*fibre)',
    re.IGNORECASE
)
_CH44_PARTICLEBOARD = re.compile(
    r'(?:שבבית|OSB|particle\s*board|chipboard|oriented\s*strand|'
    r'waferboard|flaxboard)',
    re.IGNORECASE
)
_CH44_DOOR_WINDOW = re.compile(
    r'(?:דלת\s*עץ|חלון\s*עץ|משקוף|wooden\s*door|wooden\s*window|'
    r'door\s*frame|window\s*frame|shutter)',
    re.IGNORECASE
)
_CH44_FLOORING = re.compile(
    r'(?:רצפה|פרקט|parquet|flooring|floor\s*panel|laminate\s*floor)',
    re.IGNORECASE
)
_CH44_FURNITURE_PARTS = re.compile(
    r'(?:חלקי\s*רהיט|wooden\s*furniture\s*part|table\s*top\s*wood|'
    r'wooden\s*leg|wooden\s*shelf)',
    re.IGNORECASE
)
_CH44_WOOD_GENERAL = re.compile(
    r'(?:עץ|עצי|wooden|wood|timber|lumber|carpentry|joinery|'
    r'marquetry|packing\s*case\s*wood|pallet\s*wood|cask|barrel\s*wood|'
    r'wood\s*frame|moulding|dowel)',
    re.IGNORECASE
)


def _is_chapter_44_candidate(text):
    return bool(
        _CH44_LOG.search(text) or _CH44_SAWN.search(text)
        or _CH44_PLYWOOD.search(text) or _CH44_FIBREBOARD.search(text)
        or _CH44_PARTICLEBOARD.search(text) or _CH44_WOOD_GENERAL.search(text)
    )


def _decide_chapter_44(product):
    """Chapter 44: Wood and articles of wood; wood charcoal.

    Headings:
        44.01 — Fuel wood; wood chips; sawdust
        44.02 — Wood charcoal
        44.03 — Wood in the rough (logs)
        44.07 — Wood sawn/chipped lengthwise (lumber)
        44.08 — Veneer sheets
        44.09 — Wood continuously shaped (tongued, grooved, moulded)
        44.10 — Particle board / OSB
        44.11 — Fibreboard (MDF, HDF, hardboard)
        44.12 — Plywood, veneered panels, laminated wood
        44.18 — Builders' joinery (windows, doors, parquet)
        44.19 — Tableware and kitchenware of wood
        44.20 — Wood marquetry; caskets; statuettes
        44.21 — Other articles of wood (hangers, tools, spools, pallets)
    """
    text = _product_text(product)
    result = {"chapter": 44, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:פחם\s*עצים|wood\s*charcoal|charcoal)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "44.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Wood charcoal → 44.02.",
            "rule_applied": "GIR 1 — heading 44.02"})
        return result
    if _CH44_FIBREBOARD.search(text):
        result["candidates"].append({"heading": "44.11", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Fibreboard / MDF / HDF → 44.11.",
            "rule_applied": "GIR 1 — heading 44.11"})
        return result
    if _CH44_PARTICLEBOARD.search(text):
        result["candidates"].append({"heading": "44.10", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Particleboard / OSB / chipboard → 44.10.",
            "rule_applied": "GIR 1 — heading 44.10"})
        return result
    if _CH44_PLYWOOD.search(text):
        result["candidates"].append({"heading": "44.12", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Plywood / veneered panel / laminated wood → 44.12.",
            "rule_applied": "GIR 1 — heading 44.12"})
        return result
    if _CH44_DOOR_WINDOW.search(text) or _CH44_FLOORING.search(text):
        result["candidates"].append({"heading": "44.18", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Builders' joinery (door/window/parquet) → 44.18.",
            "rule_applied": "GIR 1 — heading 44.18"})
        return result
    if _CH44_LOG.search(text):
        if re.search(r'(?:fuel\s*wood|firewood|chips|sawdust|waste|נסורת)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "44.01", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Fuel wood / chips / sawdust / waste → 44.01.",
                "rule_applied": "GIR 1 — heading 44.01"})
        else:
            result["candidates"].append({"heading": "44.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Wood in the rough / logs → 44.03.",
                "rule_applied": "GIR 1 — heading 44.03"})
        return result
    if _CH44_SAWN.search(text):
        result["candidates"].append({"heading": "44.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Sawn wood / lumber / timber → 44.07.",
            "rule_applied": "GIR 1 — heading 44.07"})
        return result
    if _CH44_FURNITURE_PARTS.search(text):
        result["redirect"] = {"chapter": 94, "reason": "Wooden furniture parts → Chapter 94 (furniture).",
            "rule_applied": "Section IX Note / GIR 1"}
        return result

    result["candidates"].append({"heading": "44.21", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Other article of wood → 44.21.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What form? (log, sawn, plywood, MDF, door/window, flooring)")
    return result


# ============================================================================
# CHAPTER 45: Cork and articles of cork
# ============================================================================

_CH45_NATURAL = re.compile(
    r'(?:שעם\s*(?:טבעי|גולמי)|natural\s*cork|raw\s*cork|cork\s*bark|'
    r'cork\s*waste|cork\s*granule|crushed\s*cork)',
    re.IGNORECASE
)
_CH45_STOPPER = re.compile(
    r'(?:פקק\s*שעם|cork\s*stopper|cork\s*plug|wine\s*cork|bottle\s*cork)',
    re.IGNORECASE
)
_CH45_ARTICLE = re.compile(
    r'(?:שעם|cork|agglomerated\s*cork|cork\s*tile|cork\s*sheet|'
    r'cork\s*board|cork\s*roll|cork\s*disc|cork\s*gasket|'
    r'cork\s*mat|cork\s*panel|cork\s*floor)',
    re.IGNORECASE
)


def _is_chapter_45_candidate(text):
    return bool(_CH45_ARTICLE.search(text))


def _decide_chapter_45(product):
    """Chapter 45: Cork and articles of cork.

    Headings:
        45.01 — Natural cork, raw or simply prepared; waste cork; crushed/granulated/ground cork
        45.02 — Natural cork, debacked or roughly squared; blocks/plates/sheets/strip
        45.03 — Articles of natural cork
        45.04 — Agglomerated cork and articles thereof (tiles, stoppers, gaskets, discs)
    """
    text = _product_text(product)
    result = {"chapter": 45, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH45_STOPPER.search(text):
        # Natural cork stoppers → 45.03; agglomerated stoppers → 45.04
        if re.search(r'(?:agglomerat|לחוץ)', text, re.IGNORECASE):
            heading, reasoning = "45.04", "Agglomerated cork stopper → 45.04."
        else:
            heading, reasoning = "45.03", "Natural cork stopper / plug → 45.03."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH45_NATURAL.search(text):
        if re.search(r'(?:waste|granul|crushed|ground|פסולת)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "45.01", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Cork waste / granulated / crushed cork → 45.01.",
                "rule_applied": "GIR 1 — heading 45.01"})
        else:
            result["candidates"].append({"heading": "45.01", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Natural cork raw / bark → 45.01.",
                "rule_applied": "GIR 1 — heading 45.01"})
        return result
    if re.search(r'(?:agglomerat|לחוץ|tile|sheet|board|panel|floor|disc|gasket)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "45.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Agglomerated cork article (tile/sheet/board) → 45.04.",
            "rule_applied": "GIR 1 — heading 45.04"})
        return result

    result["candidates"].append({"heading": "45.03", "subheading_hint": None,
        "confidence": 0.70, "reasoning": "Cork article → 45.03.",
        "rule_applied": "GIR 1"})
    return result


# ============================================================================
# CHAPTER 46: Manufactures of straw, esparto or other plaiting materials;
#              basketware and wickerwork
# ============================================================================

_CH46_PLAIT_MAT = re.compile(
    r'(?:קש|קליע|ערב|במבוק|ראטן|נצרי|'
    r'straw|esparto|raffia|bamboo|rattan|wicker|willow|'
    r'cane|reed|rush|osier|palm\s*leaf|plait)',
    re.IGNORECASE
)
_CH46_BASKET = re.compile(
    r'(?:סל|basket|hamper|wickerwork|basketware|'
    r'woven\s*(?:mat|seat|panel))',
    re.IGNORECASE
)


def _is_chapter_46_candidate(text):
    return bool(_CH46_PLAIT_MAT.search(text) or _CH46_BASKET.search(text))


def _decide_chapter_46(product):
    """Chapter 46: Manufactures of straw, esparto or other plaiting materials.

    Headings:
        46.01 — Plaits and similar products of plaiting materials (bound in parallel strands)
        46.02 — Basketwork, wickerwork, and other articles made from plaiting materials
    """
    text = _product_text(product)
    result = {"chapter": 46, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH46_BASKET.search(text):
        result["candidates"].append({"heading": "46.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Basket / wickerwork / plaited article → 46.02.",
            "rule_applied": "GIR 1 — heading 46.02"})
        return result
    # Raw plaiting materials / plaits
    result["candidates"].append({"heading": "46.01", "subheading_hint": None,
        "confidence": 0.80, "reasoning": "Plaiting material / plait / braid → 46.01.",
        "rule_applied": "GIR 1 — heading 46.01"})
    return result


# ============================================================================
# CHAPTER 47: Pulp of wood or of other fibrous cellulosic material
# ============================================================================

_CH47_MECHANICAL = re.compile(
    r'(?:עיסת\s*עץ\s*מכנית|mechanical\s*(?:wood\s*)?pulp|'
    r'groundwood|thermo.?mechanical|TMP|CTMP)',
    re.IGNORECASE
)
_CH47_CHEMICAL = re.compile(
    r'(?:עיסה\s*כימית|chemical\s*(?:wood\s*)?pulp|'
    r'sulphate|sulfate|kraft\s*pulp|sulphite|sulfite|'
    r'soda\s*pulp|bleached\s*pulp|unbleached\s*pulp)',
    re.IGNORECASE
)
_CH47_DISSOLVING = re.compile(
    r'(?:עיסת?\s*המסה|dissolving\s*(?:grade\s*)?pulp|'
    r'viscose\s*pulp|alpha.cellulose)',
    re.IGNORECASE
)
_CH47_RECOVERED = re.compile(
    r'(?:נייר\s*ממוחזר|waste\s*paper|recovered\s*paper|'
    r'paper\s*scrap|recycled\s*paper\s*pulp|wastepaper)',
    re.IGNORECASE
)
_CH47_PULP_GENERAL = re.compile(
    r'(?:עיסת?\s*(?:עץ|נייר|תאית)|cellulose\s*pulp|wood\s*pulp|'
    r'paper\s*pulp|pulp\s*(?:of\s*wood|board|sheet))',
    re.IGNORECASE
)


def _is_chapter_47_candidate(text):
    return bool(
        _CH47_MECHANICAL.search(text) or _CH47_CHEMICAL.search(text)
        or _CH47_DISSOLVING.search(text) or _CH47_RECOVERED.search(text)
        or _CH47_PULP_GENERAL.search(text)
    )


def _decide_chapter_47(product):
    """Chapter 47: Pulp of wood or of other fibrous cellulosic material.

    Headings:
        47.01 — Mechanical wood pulp
        47.02 — Chemical wood pulp, dissolving grades
        47.03 — Chemical wood pulp, soda or sulphate (kraft), not dissolving
        47.04 — Chemical wood pulp, sulphite, not dissolving
        47.05 — Wood pulp obtained by combination of mechanical and chemical processes
        47.06 — Pulps of fibres derived from recovered paper/paperboard or other
        47.07 — Recovered (waste and scrap) paper or paperboard
    """
    text = _product_text(product)
    result = {"chapter": 47, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH47_DISSOLVING.search(text):
        result["candidates"].append({"heading": "47.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Dissolving grade chemical pulp → 47.02.",
            "rule_applied": "GIR 1 — heading 47.02"})
        return result
    if _CH47_RECOVERED.search(text):
        result["candidates"].append({"heading": "47.07", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Waste / recovered / recycled paper → 47.07.",
            "rule_applied": "GIR 1 — heading 47.07"})
        return result
    if _CH47_CHEMICAL.search(text):
        if re.search(r'(?:sulphite|sulfite)', text, re.IGNORECASE):
            heading, reasoning = "47.04", "Chemical wood pulp, sulphite → 47.04."
        else:
            heading, reasoning = "47.03", "Chemical wood pulp, kraft/sulphate/soda → 47.03."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning, "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH47_MECHANICAL.search(text):
        result["candidates"].append({"heading": "47.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Mechanical wood pulp / groundwood / TMP → 47.01.",
            "rule_applied": "GIR 1 — heading 47.01"})
        return result

    result["candidates"].append({"heading": "47.06", "subheading_hint": None,
        "confidence": 0.65, "reasoning": "Wood/cellulose pulp type unclear → 47.06 (other pulps).",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Pulp type? (mechanical, chemical kraft, chemical sulphite, dissolving, recovered)")
    return result


# ============================================================================
# CHAPTER 48: Paper and paperboard; articles of paper pulp/paper/paperboard
# ============================================================================

_CH48_NEWSPRINT = re.compile(
    r'(?:נייר\s*עיתון|newsprint)',
    re.IGNORECASE
)
_CH48_KRAFT = re.compile(
    r'(?:קראפט|kraft\s*(?:paper|liner|board|sack)|'
    r'uncoated\s*kraft|test\s*liner|linerboard)',
    re.IGNORECASE
)
_CH48_TISSUE = re.compile(
    r'(?:טישו|נייר\s*טואלט|מגבת\s*נייר|מפית|'
    r'tissue|toilet\s*paper|paper\s*towel|napkin|'
    r'facial\s*tissue|kitchen\s*roll|crepe\s*paper)',
    re.IGNORECASE
)
_CH48_COATED = re.compile(
    r'(?:נייר\s*מצופה|coated\s*paper|art\s*paper|'
    r'glossy\s*paper|matt\s*paper|clay.coated|kaolin.coated|'
    r'lightweight\s*coated|LWC)',
    re.IGNORECASE
)
_CH48_CARTON = re.compile(
    r'(?:קרטון|גלי|carton|cardboard|corrugated|'
    r'paperboard|box\s*board|folding\s*box|container\s*board|'
    r'fluting)',
    re.IGNORECASE
)
_CH48_WALLPAPER = re.compile(
    r'(?:טפט|wallpaper|wall\s*paper|wall\s*covering\s*paper)',
    re.IGNORECASE
)
_CH48_PAPER_GENERAL = re.compile(
    r'(?:נייר|paper(?!weight)|stationery|envelope|'
    r'filter\s*paper|carbon\s*paper|wax\s*paper|'
    r'parchment\s*paper|greaseproof|tracing\s*paper|'
    r'cigarette\s*paper|label\s*paper|copy\s*paper|'
    r'writing\s*paper|printing\s*paper)',
    re.IGNORECASE
)


def _is_chapter_48_candidate(text):
    return bool(
        _CH48_NEWSPRINT.search(text) or _CH48_KRAFT.search(text)
        or _CH48_TISSUE.search(text) or _CH48_COATED.search(text)
        or _CH48_CARTON.search(text) or _CH48_WALLPAPER.search(text)
        or _CH48_PAPER_GENERAL.search(text)
    )


def _decide_chapter_48(product):
    """Chapter 48: Paper and paperboard; articles of paper pulp, paper, or paperboard.

    Headings:
        48.01 — Newsprint
        48.04 — Uncoated kraft paper and paperboard
        48.05 — Other uncoated paper and paperboard
        48.06 — Vegetable parchment, greaseproof, tracing, glassine
        48.08 — Corrugated paper/paperboard (with or without flat surface sheets)
        48.09 — Carbon paper, self-copy paper
        48.10 — Paper/paperboard coated with kaolin/inorganic substances
        48.11 — Paper/paperboard coated/impregnated/covered (excl. 48.03/48.09/48.10)
        48.13 — Cigarette paper
        48.14 — Wallpaper and similar wall coverings
        48.17 — Envelopes, letter cards, boxes of paper stationery
        48.18 — Toilet paper, tissues, towels, napkins, tablecloths
        48.19 — Cartons, boxes, cases, bags of paper/paperboard
        48.20 — Registers, notebooks, diaries, binders
        48.21 — Paper labels; bobbins/spools/cops; paper pulp articles
        48.23 — Other paper/paperboard cut to size; articles of paper n.e.s.
    """
    text = _product_text(product)
    result = {"chapter": 48, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH48_NEWSPRINT.search(text):
        result["candidates"].append({"heading": "48.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Newsprint → 48.01.",
            "rule_applied": "GIR 1 — heading 48.01"})
        return result
    if _CH48_TISSUE.search(text):
        result["candidates"].append({"heading": "48.18", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Toilet paper / tissue / paper towel / napkin → 48.18.",
            "rule_applied": "GIR 1 — heading 48.18"})
        return result
    if _CH48_WALLPAPER.search(text):
        result["candidates"].append({"heading": "48.14", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Wallpaper / wall covering paper → 48.14.",
            "rule_applied": "GIR 1 — heading 48.14"})
        return result
    if _CH48_CARTON.search(text):
        if re.search(r'(?:corrugated|גלי|fluting)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "48.08", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Corrugated paper / paperboard → 48.08.",
                "rule_applied": "GIR 1 — heading 48.08"})
        else:
            result["candidates"].append({"heading": "48.19", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Carton / box / case of paperboard → 48.19.",
                "rule_applied": "GIR 1 — heading 48.19"})
        return result
    if _CH48_KRAFT.search(text):
        result["candidates"].append({"heading": "48.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Kraft paper / kraft liner / sack kraft → 48.04.",
            "rule_applied": "GIR 1 — heading 48.04"})
        return result
    if _CH48_COATED.search(text):
        result["candidates"].append({"heading": "48.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Coated paper / art paper / clay-coated → 48.10.",
            "rule_applied": "GIR 1 — heading 48.10"})
        return result

    # Generic paper
    if re.search(r'(?:envelope|מעטפ)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "48.17", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Envelope / letter card / stationery → 48.17.",
            "rule_applied": "GIR 1 — heading 48.17"})
        return result
    if re.search(r'(?:filter\s*paper|carbon\s*paper)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "48.23", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Filter paper / carbon paper → 48.23.",
            "rule_applied": "GIR 1 — heading 48.23"})
        return result

    result["candidates"].append({"heading": "48.23", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Paper/paperboard article n.e.s. → 48.23.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What type? (newsprint, kraft, tissue, coated, carton, wallpaper)")
    return result


# ============================================================================
# CHAPTER 49: Printed books, newspapers, pictures; other products of printing
# ============================================================================

_CH49_BOOK = re.compile(
    r'(?:ספר|חוברת|book|brochure|pamphlet|booklet|leaflet|'
    r'encyclop|dictionar|atlas|manual|textbook)',
    re.IGNORECASE
)
_CH49_NEWSPAPER = re.compile(
    r'(?:עיתון|newspaper|journal|periodical|magazine)',
    re.IGNORECASE
)
_CH49_MAP = re.compile(
    r'(?:מפה|map|chart|globe|hydrographic|topographic|'
    r'wall\s*map|nautical\s*chart)',
    re.IGNORECASE
)
_CH49_POSTCARD = re.compile(
    r'(?:גלויה|גלוית|postcard|greeting\s*card|picture\s*card|'
    r'illustrated\s*card)',
    re.IGNORECASE
)
_CH49_CALENDAR = re.compile(
    r'(?:לוח\s*שנה|יומן|calendar|diary|planner)',
    re.IGNORECASE
)
_CH49_LABEL = re.compile(
    r'(?:תווית|מדבקה|label|sticker|transfer|decal|decalcomania)',
    re.IGNORECASE
)
_CH49_PRINTED = re.compile(
    r'(?:דפוס|הדפס|מודפס|printed|\bprint\b|poster|picture|'
    r'\bphotographs?\b|plan|drawing|\bstamp\b|banknote)',
    re.IGNORECASE
)


def _is_chapter_49_candidate(text):
    return bool(
        _CH49_BOOK.search(text) or _CH49_NEWSPAPER.search(text)
        or _CH49_MAP.search(text) or _CH49_POSTCARD.search(text)
        or _CH49_CALENDAR.search(text) or _CH49_LABEL.search(text)
        or _CH49_PRINTED.search(text)
    )


def _decide_chapter_49(product):
    """Chapter 49: Printed books, newspapers, pictures and other printing products.

    Headings:
        49.01 — Printed books, brochures, leaflets
        49.02 — Newspapers, journals, periodicals
        49.03 — Children's picture/drawing/colouring books
        49.05 — Maps and hydrographic/similar charts (printed)
        49.07 — Unused postage/revenue stamps; banknotes; cheque forms
        49.08 — Transfers (decalcomanias)
        49.09 — Printed/illustrated postcards; printed greeting cards
        49.10 — Calendars (printed)
        49.11 — Other printed matter (pictures, photographs, plans, posters, labels)
    """
    text = _product_text(product)
    result = {"chapter": 49, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH49_BOOK.search(text):
        if re.search(r'(?:children|colouring|coloring|ילד|צביעה)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "49.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Children's picture/colouring book → 49.03.",
                "rule_applied": "GIR 1 — heading 49.03"})
        else:
            result["candidates"].append({"heading": "49.01", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Printed book / brochure / pamphlet → 49.01.",
                "rule_applied": "GIR 1 — heading 49.01"})
        return result
    if _CH49_NEWSPAPER.search(text):
        result["candidates"].append({"heading": "49.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Newspaper / journal / periodical → 49.02.",
            "rule_applied": "GIR 1 — heading 49.02"})
        return result
    if _CH49_MAP.search(text):
        result["candidates"].append({"heading": "49.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Map / chart / globe → 49.05.",
            "rule_applied": "GIR 1 — heading 49.05"})
        return result
    if _CH49_POSTCARD.search(text):
        result["candidates"].append({"heading": "49.09", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Postcard / greeting card → 49.09.",
            "rule_applied": "GIR 1 — heading 49.09"})
        return result
    if _CH49_CALENDAR.search(text):
        result["candidates"].append({"heading": "49.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Calendar / diary → 49.10.",
            "rule_applied": "GIR 1 — heading 49.10"})
        return result
    if _CH49_LABEL.search(text):
        result["candidates"].append({"heading": "49.11", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Label / sticker / transfer → 49.11.",
            "rule_applied": "GIR 1 — heading 49.11"})
        return result

    result["candidates"].append({"heading": "49.11", "subheading_hint": None,
        "confidence": 0.65, "reasoning": "Other printed matter → 49.11.",
        "rule_applied": "GIR 1"})
    return result


# ============================================================================
# CHAPTER 50: Silk
# ============================================================================

_CH50_RAW_SILK = re.compile(
    r'(?:משי\s*גולמי|גולם\s*משי|raw\s*silk|silk\s*worm|cocoon|'
    r'silk\s*waste|noil|thrown\s*silk)',
    re.IGNORECASE
)
_CH50_YARN = re.compile(
    r'(?:חוט\s*משי|silk\s*yarn|spun\s*silk|silk\s*thread)',
    re.IGNORECASE
)
_CH50_FABRIC = re.compile(
    r'(?:בד\s*משי|אריג\s*משי|silk\s*fabric|woven\s*silk|silk\s*cloth|'
    r'silk\s*textile|silk\s*satin|silk\s*chiffon|silk\s*taffeta|'
    r'silk\s*organza|silk\s*crepe)',
    re.IGNORECASE
)
_CH50_SILK_GENERAL = re.compile(
    r'(?:משי|silk)',
    re.IGNORECASE
)


def _is_chapter_50_candidate(text):
    return bool(_CH50_SILK_GENERAL.search(text))


def _decide_chapter_50(product):
    """Chapter 50: Silk.

    Headings:
        50.01 — Silk-worm cocoons suitable for reeling
        50.02 — Raw silk (not thrown)
        50.03 — Silk waste (including cocoons unsuitable for reeling, yarn waste, noils)
        50.04 — Silk yarn (not put up for retail sale)
        50.05 — Yarn spun from silk waste (not put up for retail sale)
        50.06 — Silk yarn and spun yarn put up for retail sale; silk-worm gut
        50.07 — Woven fabrics of silk or silk waste
    """
    text = _product_text(product)
    result = {"chapter": 50, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:cocoon|גולם)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "50.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Silk-worm cocoons → 50.01.",
            "rule_applied": "GIR 1 — heading 50.01"})
        return result
    if _CH50_FABRIC.search(text):
        result["candidates"].append({"heading": "50.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Woven fabric of silk → 50.07.",
            "rule_applied": "GIR 1 — heading 50.07"})
        return result
    if _CH50_YARN.search(text):
        result["candidates"].append({"heading": "50.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Silk yarn → 50.04.",
            "rule_applied": "GIR 1 — heading 50.04"})
        return result
    if _CH50_RAW_SILK.search(text):
        if re.search(r'(?:waste|noil|פסולת)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "50.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Silk waste / noils → 50.03.",
                "rule_applied": "GIR 1 — heading 50.03"})
        else:
            result["candidates"].append({"heading": "50.02", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Raw silk (not thrown) → 50.02.",
                "rule_applied": "GIR 1 — heading 50.02"})
        return result

    result["candidates"].append({"heading": "50.07", "subheading_hint": None,
        "confidence": 0.65, "reasoning": "Silk product → 50.07 (woven fabric default).",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What form? (raw silk, yarn, woven fabric)")
    return result


# ============================================================================
# CHAPTER 51: Wool, fine or coarse animal hair; horsehair yarn and woven fabric
# ============================================================================

_CH51_RAW_WOOL = re.compile(
    r'(?:צמר\s*(?:גולמי|גזוז|רחוץ)|greasy\s*wool|shorn\s*wool|'
    r'raw\s*wool|scoured\s*wool|wool\s*grease|lanolin|'
    r'fine\s*animal\s*hair|coarse\s*animal\s*hair|'
    r'cashmere|angora|mohair|alpaca|camel\s*hair|vicuna)',
    re.IGNORECASE
)
_CH51_TOPS = re.compile(
    r'(?:סרוק|טופס|wool\s*tops|combed\s*wool|carded\s*wool|'
    r'wool\s*noils|carbonised|wool\s*waste)',
    re.IGNORECASE
)
_CH51_YARN = re.compile(
    r'(?:חוט\s*צמר|yarn\s*of\s*(?:wool|fine\s*animal|coarse\s*animal)|'
    r'worsted\s*yarn|woollen\s*yarn|wool\s*yarn)',
    re.IGNORECASE
)
_CH51_FABRIC = re.compile(
    r'(?:בד\s*צמר|אריג\s*צמר|woven\s*(?:fabric|cloth)\s*of\s*(?:wool|fine\s*animal)|'
    r'wool\s*fabric|tweed|flannel\s*wool|worsted\s*fabric)',
    re.IGNORECASE
)
_CH51_WOOL_GENERAL = re.compile(
    r'(?:צמר|wool|worsted|woollen|mohair|cashmere|alpaca|angora)',
    re.IGNORECASE
)


def _is_chapter_51_candidate(text):
    return bool(_CH51_WOOL_GENERAL.search(text))


def _decide_chapter_51(product):
    """Chapter 51: Wool, fine or coarse animal hair; horsehair yarn and woven fabric.

    Headings:
        51.01 — Wool, not carded or combed
        51.02 — Fine animal hair (cashmere, angora, alpaca, camel), not carded/combed
        51.03 — Waste of wool or fine/coarse animal hair (noils, yarn waste)
        51.04 — Garnetted stock of wool or fine/coarse animal hair
        51.05 — Wool and fine animal hair, carded or combed (tops)
        51.06 — Yarn of carded wool (not for retail)
        51.07 — Yarn of combed wool (not for retail)
        51.08 — Yarn of fine animal hair (not for retail)
        51.09 — Yarn of wool/fine animal hair for retail sale
        51.10 — Yarn of coarse animal hair or of horsehair
        51.11 — Woven fabrics of carded wool or fine animal hair
        51.12 — Woven fabrics of combed wool or fine animal hair
        51.13 — Woven fabrics of coarse animal hair or horsehair
    """
    text = _product_text(product)
    result = {"chapter": 51, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH51_FABRIC.search(text):
        if re.search(r'(?:combed|worsted|סרוק)', text, re.IGNORECASE):
            heading = "51.12"
        else:
            heading = "51.11"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Woven fabric of wool → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH51_YARN.search(text):
        result["candidates"].append({"heading": "51.07", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Yarn of wool → 51.07.",
            "rule_applied": "GIR 1 — heading 51.07"})
        return result
    if _CH51_TOPS.search(text):
        result["candidates"].append({"heading": "51.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Wool tops / carded / combed wool → 51.05.",
            "rule_applied": "GIR 1 — heading 51.05"})
        return result
    if _CH51_RAW_WOOL.search(text):
        if re.search(r'(?:cashmere|angora|mohair|alpaca|camel|vicuna|קשמיר)', text, re.IGNORECASE):
            heading, reasoning = "51.02", "Fine animal hair (cashmere/angora/alpaca) → 51.02."
        elif re.search(r'(?:waste|noil|פסולת)', text, re.IGNORECASE):
            heading, reasoning = "51.03", "Wool waste / noils → 51.03."
        else:
            heading, reasoning = "51.01", "Raw wool, not carded/combed → 51.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "51.12", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Wool product type unclear → 51.12.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What form? (raw wool, tops/combed, yarn, woven fabric)")
    return result


# ============================================================================
# CHAPTER 52: Cotton
# ============================================================================

_CH52_RAW = re.compile(
    r'(?:כותנה\s*(?:גולמי|גלם)|raw\s*cotton|cotton\s*(?:not\s*carded|linter)|'
    r'cotton\s*waste|ginned\s*cotton|unginned|seed\s*cotton)',
    re.IGNORECASE
)
_CH52_YARN = re.compile(
    r'(?:חוט\s*כותנה|cotton\s*yarn|cotton\s*thread|'
    r'sewing\s*thread\s*cotton|carded\s*cotton\s*yarn|'
    r'combed\s*cotton\s*yarn)',
    re.IGNORECASE
)
_CH52_FABRIC = re.compile(
    r'(?:בד\s*כותנה|אריג\s*כותנה|woven\s*(?:fabric|cloth)\s*(?:of\s*)?cotton|'
    r'cotton\s*fabric|denim|canvas\s*cotton|poplin|'
    r'cotton\s*gauze|muslin|cotton\s*twill)',
    re.IGNORECASE
)
_CH52_COTTON_GENERAL = re.compile(
    r'(?:כותנה|cotton|denim)',
    re.IGNORECASE
)


def _is_chapter_52_candidate(text):
    return bool(_CH52_COTTON_GENERAL.search(text))


def _decide_chapter_52(product):
    """Chapter 52: Cotton.

    Headings:
        52.01 — Cotton, not carded or combed
        52.02 — Cotton waste (including yarn waste and garnetted stock)
        52.03 — Cotton, carded or combed
        52.04 — Cotton sewing thread
        52.05 — Cotton yarn (not sewing thread), not for retail (≥85% cotton)
        52.06 — Cotton yarn (not sewing thread), not for retail (<85% cotton)
        52.07 — Cotton yarn for retail sale
        52.08 — Woven cotton fabrics (≥85% cotton, ≤200 g/m²)
        52.09 — Woven cotton fabrics (≥85% cotton, >200 g/m²)
        52.10 — Woven cotton fabrics (<85% cotton, mixed with man-made fibres, ≤200 g/m²)
        52.11 — Woven cotton fabrics (<85% cotton, mixed with man-made fibres, >200 g/m²)
        52.12 — Other woven cotton fabrics
    """
    text = _product_text(product)
    result = {"chapter": 52, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH52_FABRIC.search(text):
        if re.search(r'(?:denim|ג\'ינס)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "52.09", "subheading_hint": "5209.42",
                "confidence": 0.85, "reasoning": "Denim fabric (≥85% cotton, >200 g/m²) → 52.09.",
                "rule_applied": "GIR 1 — heading 52.09"})
        else:
            result["candidates"].append({"heading": "52.08", "subheading_hint": None,
                "confidence": 0.75, "reasoning": "Woven cotton fabric → 52.08 (≥85%, ≤200 g/m² default).",
                "rule_applied": "GIR 1 — heading 52.08"})
            result["questions_needed"].append("Cotton content ≥85%? Fabric weight ≤200 g/m² or >200?")
        return result
    if _CH52_YARN.search(text):
        if re.search(r'(?:sewing|תפירה)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "52.04", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Cotton sewing thread → 52.04.",
                "rule_applied": "GIR 1 — heading 52.04"})
        else:
            result["candidates"].append({"heading": "52.05", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Cotton yarn (not sewing thread) → 52.05.",
                "rule_applied": "GIR 1 — heading 52.05"})
        return result
    if _CH52_RAW.search(text):
        if re.search(r'(?:waste|פסולת|linter)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "52.02", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Cotton waste / linters → 52.02.",
                "rule_applied": "GIR 1 — heading 52.02"})
        else:
            result["candidates"].append({"heading": "52.01", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Raw cotton, not carded/combed → 52.01.",
                "rule_applied": "GIR 1 — heading 52.01"})
        return result

    result["candidates"].append({"heading": "52.08", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Cotton product type unclear → 52.08.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What form? (raw, yarn, woven fabric)")
    return result


# ============================================================================
# CHAPTER 53: Other vegetable textile fibres; paper yarn and woven fabrics
# ============================================================================

_CH53_FLAX = re.compile(
    r'(?:פשתן|flax|linen)',
    re.IGNORECASE
)
_CH53_JUTE = re.compile(
    r'(?:יוטה|jute|kenaf)',
    re.IGNORECASE
)
_CH53_SISAL = re.compile(
    r'(?:סיסל|sisal|agave|henequen)',
    re.IGNORECASE
)
_CH53_HEMP = re.compile(
    r'(?:קנבוס|hemp|true\s*hemp|cannabis\s*sativa\s*fibre)',
    re.IGNORECASE
)
_CH53_COIR = re.compile(
    r'(?:קויר|סיבי\s*קוקוס|coir|coconut\s*fibre)',
    re.IGNORECASE
)
_CH53_VEG_FIBRE = re.compile(
    r'(?:פשתן|יוטה|סיסל|קנבוס|קויר|ramie|abaca|manila\s*hemp|'
    r'flax|jute|sisal|hemp|coir|vegetable\s*(?:textile\s*)?fibre)',
    re.IGNORECASE
)


def _is_chapter_53_candidate(text):
    return bool(_CH53_VEG_FIBRE.search(text))


def _decide_chapter_53(product):
    """Chapter 53: Other vegetable textile fibres; paper yarn and woven fabrics of paper yarn.

    Headings:
        53.01 — Flax, raw or processed (not spun); flax tow and waste
        53.02 — True hemp, raw or processed (not spun)
        53.03 — Jute and other bast fibres, raw or processed (not spun)
        53.05 — Coconut (coir), abaca, ramie and other vegetable fibres
        53.06 — Flax yarn
        53.07 — Yarn of jute or other bast fibres
        53.08 — Yarn of other vegetable textile fibres; paper yarn
        53.09 — Woven fabrics of flax
        53.10 — Woven fabrics of jute or other bast fibres
        53.11 — Woven fabrics of other vegetable textile fibres and paper yarn
    """
    text = _product_text(product)
    result = {"chapter": 53, "candidates": [], "redirect": None, "questions_needed": []}

    is_woven = bool(re.search(r'(?:בד|אריג|woven|fabric|cloth)', text, re.IGNORECASE))
    is_yarn = bool(re.search(r'(?:חוט|yarn|thread|spun)', text, re.IGNORECASE))

    if _CH53_FLAX.search(text):
        if is_woven:
            heading, reasoning = "53.09", "Woven fabric of flax/linen → 53.09."
        elif is_yarn:
            heading, reasoning = "53.06", "Flax/linen yarn → 53.06."
        else:
            heading, reasoning = "53.01", "Raw/processed flax → 53.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH53_JUTE.search(text):
        if is_woven:
            heading, reasoning = "53.10", "Woven fabric of jute → 53.10."
        elif is_yarn:
            heading, reasoning = "53.07", "Jute yarn → 53.07."
        else:
            heading, reasoning = "53.03", "Raw/processed jute → 53.03."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH53_HEMP.search(text):
        if is_woven:
            heading, reasoning = "53.11", "Woven fabric of hemp → 53.11."
        elif is_yarn:
            heading, reasoning = "53.08", "Hemp yarn → 53.08."
        else:
            heading, reasoning = "53.02", "Raw/processed hemp → 53.02."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH53_SISAL.search(text) or _CH53_COIR.search(text):
        if is_woven:
            heading, reasoning = "53.11", "Woven fabric of sisal/coir/other veg fibre → 53.11."
        elif is_yarn:
            heading, reasoning = "53.08", "Sisal/coir yarn → 53.08."
        else:
            heading, reasoning = "53.05", "Sisal/coir/other vegetable fibre → 53.05."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "53.11", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Other vegetable textile fibre → 53.11.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("What fibre? (flax, jute, sisal, hemp, coir)")
    return result


# ============================================================================
# CHAPTER 54: Man-made filaments; strip of man-made textile materials
# ============================================================================

_CH54_POLYESTER_FIL = re.compile(
    r'(?:פוליאסטר\s*(?:פילמנט|חוט)|polyester\s*(?:filament|yarn|thread|fibre)|'
    r'PET\s*(?:yarn|filament|fibre))',
    re.IGNORECASE
)
_CH54_NYLON_FIL = re.compile(
    r'(?:ניילון\s*(?:פילמנט|חוט)|nylon\s*(?:filament|yarn|thread)|'
    r'polyamide\s*(?:filament|yarn)|PA\s*6|PA\s*66)',
    re.IGNORECASE
)
_CH54_ACRYLIC_FIL = re.compile(
    r'(?:אקריליק\s*(?:פילמנט|חוט)|acrylic\s*(?:filament|yarn)|'
    r'modacrylic\s*(?:filament|yarn))',
    re.IGNORECASE
)
_CH54_FILAMENT_FABRIC = re.compile(
    r'(?:בד\s*(?:פוליאסטר|ניילון|סינתטי)|'
    r'woven\s*fabric.*(?:synthetic|filament|polyester|nylon|polyamide)|'
    r'(?:polyester|nylon|polyamide)\s*(?:fabric|cloth|woven)|'
    r'taffeta|organza\s*(?:polyester|nylon))',
    re.IGNORECASE
)
_CH54_FILAMENT_GENERAL = re.compile(
    r'(?:פילמנט\s*סינתטי|synthetic\s*filament|man.made\s*filament|'
    r'artificial\s*filament|viscose\s*filament|rayon\s*filament|'
    r'acetate\s*filament|cuprammonium|lyocell\s*filament)',
    re.IGNORECASE
)


def _is_chapter_54_candidate(text):
    return bool(
        _CH54_POLYESTER_FIL.search(text) or _CH54_NYLON_FIL.search(text)
        or _CH54_ACRYLIC_FIL.search(text) or _CH54_FILAMENT_FABRIC.search(text)
        or _CH54_FILAMENT_GENERAL.search(text)
    )


def _decide_chapter_54(product):
    """Chapter 54: Man-made filaments; strip and the like of man-made textile materials.

    Key: synthetic vs artificial (regenerated); filament yarn vs woven fabric.
    Headings:
        54.01 — Sewing thread of man-made filaments
        54.02 — Synthetic filament yarn (nylon, polyester, etc.) not for retail
        54.03 — Artificial filament yarn (viscose, acetate) not for retail
        54.04 — Synthetic monofilament (≥67 dtex); strip of synthetic
        54.05 — Artificial monofilament; strip of artificial
        54.06 — Man-made filament yarn for retail sale
        54.07 — Woven fabrics of synthetic filament yarn
        54.08 — Woven fabrics of artificial filament yarn
    """
    text = _product_text(product)
    result = {"chapter": 54, "candidates": [], "redirect": None, "questions_needed": []}

    is_artificial = bool(re.search(r'(?:viscose|rayon|acetate|cuprammonium|lyocell|ויסקוזה|ריון)', text, re.IGNORECASE))

    if _CH54_FILAMENT_FABRIC.search(text):
        if is_artificial:
            heading, reasoning = "54.08", "Woven fabric of artificial filament yarn → 54.08."
        else:
            heading, reasoning = "54.07", "Woven fabric of synthetic filament yarn → 54.07."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if re.search(r'(?:sewing|תפירה)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "54.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Sewing thread of man-made filament → 54.01.",
            "rule_applied": "GIR 1 — heading 54.01"})
        return result
    if _CH54_NYLON_FIL.search(text) or _CH54_POLYESTER_FIL.search(text) or _CH54_ACRYLIC_FIL.search(text):
        result["candidates"].append({"heading": "54.02", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Synthetic filament yarn (polyester/nylon/acrylic) → 54.02.",
            "rule_applied": "GIR 1 — heading 54.02"})
        return result
    if is_artificial:
        result["candidates"].append({"heading": "54.03", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Artificial filament yarn (viscose/rayon/acetate) → 54.03.",
            "rule_applied": "GIR 1 — heading 54.03"})
        return result

    result["candidates"].append({"heading": "54.02", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Man-made filament type unclear → 54.02.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Synthetic (polyester/nylon) or artificial (viscose/rayon)? Yarn or fabric?")
    return result


# ============================================================================
# CHAPTER 55: Man-made staple fibres
# ============================================================================

_CH55_POLYESTER_STAPLE = re.compile(
    r'(?:סיבי?\s*פוליאסטר|polyester\s*staple|polyester\s*(?:fibre|fiber)\s*(?:staple)?|'
    r'PET\s*staple|PSF\b|polyester\s*tow)',
    re.IGNORECASE
)
_CH55_VISCOSE_STAPLE = re.compile(
    r'(?:סיבי?\s*ויסקוזה|viscose\s*(?:staple|fibre|fiber)|'
    r'viscose\s*rayon\s*(?:staple|fibre)|VSF\b|modal\s*fibre|'
    r'lyocell\s*(?:staple|fibre))',
    re.IGNORECASE
)
_CH55_ACRYLIC_STAPLE = re.compile(
    r'(?:סיבי?\s*אקריליק|acrylic\s*(?:staple|fibre|fiber)|'
    r'modacrylic\s*(?:staple|fibre))',
    re.IGNORECASE
)
_CH55_NYLON_STAPLE = re.compile(
    r'(?:סיבי?\s*ניילון|nylon\s*(?:staple|fibre|fiber)|'
    r'polyamide\s*(?:staple|fibre))',
    re.IGNORECASE
)
_CH55_STAPLE_YARN = re.compile(
    r'(?:חוט\s*(?:סיבי|סינתטי|אקריליק|ויסקוזה)|'
    r'yarn\s*of\s*(?:synthetic|artificial|man.made)\s*staple|'
    r'(?:synthetic|artificial)\s*staple\s*(?:fibre\s*)?yarn|'
    r'staple\s*fibre\s*yarn)',
    re.IGNORECASE
)
_CH55_STAPLE_FABRIC = re.compile(
    r'(?:בד\s*(?:סיבי|סינתטי\s*סטייפל)|'
    r'woven\s*fabric.*(?:synthetic|artificial)\s*staple|'
    r'(?:synthetic|artificial)\s*staple\s*(?:fibre\s*)?(?:fabric|woven)|'
    r'staple\s*fibre\s*(?:fabric|woven))',
    re.IGNORECASE
)
_CH55_STAPLE_GENERAL = re.compile(
    r'(?:סיבי?\s*(?:סינתטי|מלאכותי)|staple\s*fibre|man.made\s*staple|'
    r'synthetic\s*(?:staple|fibre|fiber)|artificial\s*(?:staple|fibre|fiber))',
    re.IGNORECASE
)


def _is_chapter_55_candidate(text):
    return bool(
        _CH55_POLYESTER_STAPLE.search(text) or _CH55_VISCOSE_STAPLE.search(text)
        or _CH55_ACRYLIC_STAPLE.search(text) or _CH55_NYLON_STAPLE.search(text)
        or _CH55_STAPLE_YARN.search(text) or _CH55_STAPLE_FABRIC.search(text)
        or _CH55_STAPLE_GENERAL.search(text)
    )


def _decide_chapter_55(product):
    """Chapter 55: Man-made staple fibres.

    Key: synthetic vs artificial + form (staple/tow → yarn → fabric).
    Headings:
        55.01 — Synthetic filament tow
        55.02 — Artificial filament tow
        55.03 — Synthetic staple fibres, not carded/combed/otherwise processed
        55.04 — Artificial staple fibres, not carded/combed
        55.05 — Waste of man-made fibres
        55.06 — Synthetic staple fibres, carded/combed/otherwise processed
        55.07 — Artificial staple fibres, carded/combed
        55.08 — Sewing thread of man-made staple fibres
        55.09 — Yarn of synthetic staple fibres (not for retail)
        55.10 — Yarn of artificial staple fibres (not for retail)
        55.11 — Yarn of man-made staple fibres for retail sale
        55.12 — Woven fabrics of synthetic staple fibres (≥85%)
        55.13 — Woven of synthetic staple (<85%, mixed with cotton, ≤170 g/m²)
        55.14 — Woven of synthetic staple (<85%, mixed with cotton, >170 g/m²)
        55.15 — Other woven fabrics of synthetic staple fibres
        55.16 — Woven fabrics of artificial staple fibres
    """
    text = _product_text(product)
    result = {"chapter": 55, "candidates": [], "redirect": None, "questions_needed": []}

    is_artificial = bool(re.search(r'(?:viscose|rayon|modal|lyocell|ויסקוזה|ריון)', text, re.IGNORECASE))

    # Fabric
    if _CH55_STAPLE_FABRIC.search(text) or re.search(r'(?:woven|fabric|cloth|בד|אריג)', text, re.IGNORECASE):
        if is_artificial or _CH55_VISCOSE_STAPLE.search(text):
            heading, reasoning = "55.16", "Woven fabric of artificial staple fibre → 55.16."
        else:
            heading, reasoning = "55.12", "Woven fabric of synthetic staple fibre → 55.12."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    # Yarn
    if _CH55_STAPLE_YARN.search(text) or re.search(r'(?:yarn|חוט)', text, re.IGNORECASE):
        if re.search(r'(?:sewing|תפירה)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "55.08", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Sewing thread of man-made staple → 55.08.",
                "rule_applied": "GIR 1 — heading 55.08"})
        elif is_artificial or _CH55_VISCOSE_STAPLE.search(text):
            result["candidates"].append({"heading": "55.10", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Yarn of artificial staple fibre → 55.10.",
                "rule_applied": "GIR 1 — heading 55.10"})
        else:
            result["candidates"].append({"heading": "55.09", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Yarn of synthetic staple fibre → 55.09.",
                "rule_applied": "GIR 1 — heading 55.09"})
        return result
    # Waste
    if re.search(r'(?:waste|פסולת|scrap)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "55.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Waste of man-made fibres → 55.05.",
            "rule_applied": "GIR 1 — heading 55.05"})
        return result
    # Tow
    if re.search(r'(?:tow\b|טאו)', text, re.IGNORECASE):
        if is_artificial:
            heading, reasoning = "55.02", "Artificial filament tow → 55.02."
        else:
            heading, reasoning = "55.01", "Synthetic filament tow → 55.01."
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": reasoning,
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    # Raw staple fibres
    if _CH55_POLYESTER_STAPLE.search(text) or _CH55_ACRYLIC_STAPLE.search(text) or _CH55_NYLON_STAPLE.search(text):
        result["candidates"].append({"heading": "55.03", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Synthetic staple fibre → 55.03.",
            "rule_applied": "GIR 1 — heading 55.03"})
        return result
    if _CH55_VISCOSE_STAPLE.search(text):
        result["candidates"].append({"heading": "55.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Artificial staple fibre (viscose/modal/lyocell) → 55.04.",
            "rule_applied": "GIR 1 — heading 55.04"})
        return result

    result["candidates"].append({"heading": "55.03", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Man-made staple fibre type unclear → 55.03.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Synthetic or artificial? What form? (staple fibre, yarn, woven fabric)")
    return result


# ============================================================================
# CHAPTER 56: Wadding, felt and nonwovens; special yarns; twine, cordage, ropes
# ============================================================================

_CH56_WADDING = re.compile(
    r'(?:ליבוד|צמר\s*גפן\s*טכני|wadding|batting|padding\s*(?:material|fibre)|'
    r'quilted\s*wadding|absorbent\s*wadding)',
    re.IGNORECASE
)
_CH56_FELT = re.compile(
    r'(?:לבד|felt(?:ed)?|needle.?felt|pressed\s*felt|felt\s*sheet|felt\s*roll)',
    re.IGNORECASE
)
_CH56_NONWOVEN = re.compile(
    r'(?:לא.?ארוג|non.?woven|spunbond|meltblown|spunlace|'
    r'needle.?punch(?:ed)?|hydro.?entangled|geotextile)',
    re.IGNORECASE
)
_CH56_TWINE = re.compile(
    r'(?:חבל|חוט\s*קשירה|שזור|twine|cordage|rope|cable|'
    r'binder\s*twine|baler\s*twine|string|net(?:ting)?)',
    re.IGNORECASE
)
_CH56_SPECIAL_YARN = re.compile(
    r'(?:חוט\s*(?:מיוחד|מתכתי|גומי)|metallized\s*yarn|'
    r'gimped\s*yarn|chenille\s*yarn|loop\s*wale\s*yarn|'
    r'rubber\s*thread\s*textile|elastic\s*yarn\s*textile)',
    re.IGNORECASE
)
_CH56_GENERAL = re.compile(
    r'(?:wadding|felt|non.?woven|twine|cordage|rope|netting)',
    re.IGNORECASE
)


def _is_chapter_56_candidate(text):
    return bool(
        _CH56_WADDING.search(text) or _CH56_FELT.search(text)
        or _CH56_NONWOVEN.search(text) or _CH56_TWINE.search(text)
        or _CH56_SPECIAL_YARN.search(text)
    )


def _decide_chapter_56(product):
    """Chapter 56: Wadding, felt, nonwovens; special yarns; twine, cordage, ropes.

    Headings:
        56.01 — Wadding and articles thereof; textile fibres ≤5mm (flock)
        56.02 — Felt, whether or not impregnated/coated/covered/laminated
        56.03 — Nonwovens, whether or not impregnated/coated/covered/laminated
        56.04 — Rubber thread/cord textile covered; textile yarn metallized/gimped
        56.05 — Metallized yarn (gimped with metal strip/powder/thread)
        56.06 — Gimped yarn; chenille yarn; loop wale yarn
        56.07 — Twine, cordage, ropes, cables
        56.08 — Knotted netting; made up fishing nets; other made up nets
        56.09 — Articles of yarn, strip, twine, cordage, rope, cables n.e.s.
    """
    text = _product_text(product)
    result = {"chapter": 56, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH56_NONWOVEN.search(text):
        result["candidates"].append({"heading": "56.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Nonwoven fabric (spunbond/meltblown/needlepunch) → 56.03.",
            "rule_applied": "GIR 1 — heading 56.03"})
        return result
    if _CH56_FELT.search(text):
        result["candidates"].append({"heading": "56.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Felt / needle-felt fabric → 56.02.",
            "rule_applied": "GIR 1 — heading 56.02"})
        return result
    if _CH56_WADDING.search(text):
        result["candidates"].append({"heading": "56.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Wadding / batting / padding material → 56.01.",
            "rule_applied": "GIR 1 — heading 56.01"})
        return result
    if _CH56_TWINE.search(text):
        if re.search(r'(?:net(?:ting)?|רשת)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "56.08", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Knotted netting / fishing net → 56.08.",
                "rule_applied": "GIR 1 — heading 56.08"})
        else:
            result["candidates"].append({"heading": "56.07", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Twine / cordage / rope / cable → 56.07.",
                "rule_applied": "GIR 1 — heading 56.07"})
        return result
    if _CH56_SPECIAL_YARN.search(text):
        if re.search(r'(?:metalliz|מתכתי|metal\s*strip)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "56.05", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Metallized yarn → 56.05.",
                "rule_applied": "GIR 1 — heading 56.05"})
        else:
            result["candidates"].append({"heading": "56.04", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Rubber thread textile-covered / special yarn → 56.04.",
                "rule_applied": "GIR 1 — heading 56.04"})
        return result

    result["candidates"].append({"heading": "56.03", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Wadding/felt/nonwoven type unclear → 56.03.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Wadding, felt, nonwoven, twine/rope, or special yarn?")
    return result


# ============================================================================
# CHAPTER 57: Carpets and other textile floor coverings
# ============================================================================

_CH57_KNOTTED = re.compile(
    r'(?:שטיח\s*(?:קשור|יד)|hand.?knotted|hand.?made\s*carpet|'
    r'oriental\s*carpet|persian\s*(?:carpet|rug)|kilim|kelim)',
    re.IGNORECASE
)
_CH57_WOVEN = re.compile(
    r'(?:שטיח\s*ארוג|woven\s*carpet|woven\s*rug|'
    r'Axminster|Wilton|jacquard\s*carpet)',
    re.IGNORECASE
)
_CH57_TUFTED = re.compile(
    r'(?:שטיח\s*(?:רקום|טאפט)|tufted\s*carpet|tufted\s*rug|'
    r'tufted\s*floor\s*covering)',
    re.IGNORECASE
)
_CH57_CARPET_GENERAL = re.compile(
    r'(?:שטיח|מרבד|ריצוף\s*טקסטיל|carpet|rug|'
    r'floor\s*covering\s*(?:textile|fabric)|mat\s*(?:textile|woven|tufted)|'
    r'runner\s*(?:carpet|rug)|door\s*mat\s*textile)',
    re.IGNORECASE
)


def _is_chapter_57_candidate(text):
    return bool(
        _CH57_KNOTTED.search(text) or _CH57_WOVEN.search(text)
        or _CH57_TUFTED.search(text) or _CH57_CARPET_GENERAL.search(text)
    )


def _decide_chapter_57(product):
    """Chapter 57: Carpets and other textile floor coverings.

    Headings:
        57.01 — Carpets, hand-knotted or hand-inserted
        57.02 — Carpets, woven (Kelem, Schumacks, Karamanie, etc.)
        57.03 — Carpets, tufted
        57.04 — Carpets, felt (not tufted/flocked)
        57.05 — Other carpets and textile floor coverings
    """
    text = _product_text(product)
    result = {"chapter": 57, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH57_KNOTTED.search(text):
        result["candidates"].append({"heading": "57.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Hand-knotted / hand-made carpet → 57.01.",
            "rule_applied": "GIR 1 — heading 57.01"})
        return result
    if _CH57_TUFTED.search(text):
        result["candidates"].append({"heading": "57.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Tufted carpet / rug → 57.03.",
            "rule_applied": "GIR 1 — heading 57.03"})
        return result
    if _CH57_WOVEN.search(text):
        result["candidates"].append({"heading": "57.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Woven carpet (Axminster/Wilton/Jacquard) → 57.02.",
            "rule_applied": "GIR 1 — heading 57.02"})
        return result
    if re.search(r'(?:felt|לבד)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "57.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Felt carpet / floor covering → 57.04.",
            "rule_applied": "GIR 1 — heading 57.04"})
        return result

    result["candidates"].append({"heading": "57.05", "subheading_hint": None,
        "confidence": 0.70, "reasoning": "Textile floor covering type unclear → 57.05.",
        "rule_applied": "GIR 1 — heading 57.05"})
    result["questions_needed"].append("Knotted, woven, tufted, or felt carpet?")
    return result


# ============================================================================
# CHAPTER 58: Special woven fabrics; tufted textile fabrics; lace; tapestries
# ============================================================================

_CH58_PILE = re.compile(
    r'(?:בד\s*(?:קטיפה|שניל)|pile\s*fabric|velvet|velour|plush|'
    r'corduroy|chenille\s*fabric|terry\s*(?:fabric|towelling))',
    re.IGNORECASE
)
_CH58_LACE = re.compile(
    r'(?:תחרה|lace|bobbin\s*lace|needle\s*lace|machine\s*lace|'
    r'tulle|crochet\s*lace)',
    re.IGNORECASE
)
_CH58_EMBROIDERY = re.compile(
    r'(?:רקמה|embroidery|embroidered\s*fabric|broderie)',
    re.IGNORECASE
)
_CH58_RIBBON = re.compile(
    r'(?:סרט\s*(?:ארוג|טקסטיל)|narrow\s*woven\s*fabric|ribbon|'
    r'label|badge\s*(?:woven|embroidered)|webbing)',
    re.IGNORECASE
)
_CH58_TAPESTRY = re.compile(
    r'(?:שטיחון\s*קיר|tapestry|tapestries|Gobelins|Aubusson)',
    re.IGNORECASE
)
_CH58_GENERAL = re.compile(
    r'(?:pile\s*fabric|velvet|velour|lace|tulle|embroidery|'
    r'ribbon|tapestry|chenille|terry|corduroy)',
    re.IGNORECASE
)


def _is_chapter_58_candidate(text):
    return bool(
        _CH58_PILE.search(text) or _CH58_LACE.search(text)
        or _CH58_EMBROIDERY.search(text) or _CH58_RIBBON.search(text)
        or _CH58_TAPESTRY.search(text)
    )


def _decide_chapter_58(product):
    """Chapter 58: Special woven fabrics; tufted fabrics; lace; tapestries; trimmings.

    Headings:
        58.01 — Woven pile fabrics and chenille fabrics (excl. 57.02, 58.06)
        58.02 — Terry towelling and similar woven terry fabrics; tufted textile fabrics
        58.03 — Gauze (other than narrow fabrics of 58.06)
        58.04 — Tulles and other net fabrics (not woven/knitted/crocheted); lace
        58.05 — Hand-woven tapestries (Gobelins, Aubusson, etc.)
        58.06 — Narrow woven fabrics; ribbons; labels; badges
        58.07 — Labels, badges, similar articles of textiles, not embroidered, in the piece
        58.08 — Braids in the piece; ornamental trimmings; tassels; pompons
        58.09 — Woven fabrics of metal thread (for apparel/furnishing/similar)
        58.10 — Embroidery in the piece, in strips or in motifs
        58.11 — Quilted textile products in the piece
    """
    text = _product_text(product)
    result = {"chapter": 58, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH58_EMBROIDERY.search(text):
        result["candidates"].append({"heading": "58.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Embroidery / embroidered fabric → 58.10.",
            "rule_applied": "GIR 1 — heading 58.10"})
        return result
    if _CH58_LACE.search(text):
        result["candidates"].append({"heading": "58.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Lace / tulle / net fabric → 58.04.",
            "rule_applied": "GIR 1 — heading 58.04"})
        return result
    if _CH58_TAPESTRY.search(text):
        result["candidates"].append({"heading": "58.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Hand-woven tapestry → 58.05.",
            "rule_applied": "GIR 1 — heading 58.05"})
        return result
    if _CH58_RIBBON.search(text):
        result["candidates"].append({"heading": "58.06", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Narrow woven fabric / ribbon / label / badge → 58.06.",
            "rule_applied": "GIR 1 — heading 58.06"})
        return result
    if re.search(r'(?:terry|מגבת|towelling)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "58.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Terry towelling / tufted textile fabric → 58.02.",
            "rule_applied": "GIR 1 — heading 58.02"})
        return result
    if _CH58_PILE.search(text):
        result["candidates"].append({"heading": "58.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Woven pile / velvet / chenille fabric → 58.01.",
            "rule_applied": "GIR 1 — heading 58.01"})
        return result

    result["candidates"].append({"heading": "58.01", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Special woven fabric type unclear → 58.01.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Pile/velvet, lace, embroidery, ribbon, or terry?")
    return result


# ============================================================================
# CHAPTER 59: Impregnated, coated, covered or laminated textile fabrics
# ============================================================================

_CH59_COATED = re.compile(
    r'(?:בד\s*(?:מצופה|ספוג|מלאמין)|coated\s*(?:textile|fabric)|'
    r'impregnated\s*(?:textile|fabric)|laminated\s*(?:textile|fabric)|'
    r'rubberized\s*(?:textile|fabric)|PVC\s*coated\s*fabric|'
    r'PU\s*coated\s*fabric)',
    re.IGNORECASE
)
_CH59_TARPAULIN = re.compile(
    r'(?:ברזנט|tarpaulin|tarp|awning|tent\s*fabric|'
    r'sail(?:cloth)?|camping\s*good\s*textile)',
    re.IGNORECASE
)
_CH59_CONVEYOR = re.compile(
    r'(?:רצועת\s*(?:הנעה|העברה)|conveyor\s*belt|transmission\s*belt|'
    r'belting\s*(?:fabric|textile))',
    re.IGNORECASE
)
_CH59_TYRE_CORD = re.compile(
    r'(?:כבל\s*צמיג|tyre\s*cord\s*fabric|tire\s*cord|'
    r'cord\s*fabric\s*(?:nylon|polyester|rayon)\s*(?:tyre|tire))',
    re.IGNORECASE
)
_CH59_HOSE = re.compile(
    r'(?:צינור\s*טקסטיל|textile\s*hose|hose\s*pipe\s*textile|'
    r'fire\s*hose|garden\s*hose\s*textile)',
    re.IGNORECASE
)
_CH59_GENERAL = re.compile(
    r'(?:coated\s*fabric|impregnated\s*fabric|laminated\s*fabric|'
    r'tarpaulin|conveyor\s*belt|tyre\s*cord|textile\s*hose|'
    r'rubberized\s*fabric|linoleum)',
    re.IGNORECASE
)


def _is_chapter_59_candidate(text):
    return bool(
        _CH59_COATED.search(text) or _CH59_TARPAULIN.search(text)
        or _CH59_CONVEYOR.search(text) or _CH59_TYRE_CORD.search(text)
        or _CH59_HOSE.search(text)
    )


def _decide_chapter_59(product):
    """Chapter 59: Impregnated, coated, covered or laminated textile fabrics; textile articles for industrial use.

    Headings:
        59.01 — Textile fabrics coated with gum (for bookbinding/tracing/stiffening/etc.)
        59.02 — Tyre cord fabric of high-tenacity nylon/polyester/viscose rayon
        59.03 — Textile fabrics impregnated/coated/covered/laminated with plastics
        59.04 — Linoleum; floor coverings on textile base
        59.05 — Textile wall coverings
        59.06 — Rubberized textile fabrics
        59.07 — Other impregnated/coated/covered textile fabrics; painted canvas
        59.08 — Textile wicks; gas mantles; textile hosepiping
        59.09 — Textile hosepiping and similar tubing
        59.10 — Transmission/conveyor belts of textile material
        59.11 — Textile products for technical uses (specified in Note 7)
    """
    text = _product_text(product)
    result = {"chapter": 59, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH59_TYRE_CORD.search(text):
        result["candidates"].append({"heading": "59.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Tyre cord fabric (high-tenacity yarn) → 59.02.",
            "rule_applied": "GIR 1 — heading 59.02"})
        return result
    if _CH59_CONVEYOR.search(text):
        result["candidates"].append({"heading": "59.10", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Transmission / conveyor belt of textile → 59.10.",
            "rule_applied": "GIR 1 — heading 59.10"})
        return result
    if _CH59_HOSE.search(text):
        result["candidates"].append({"heading": "59.09", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Textile hosepiping / tubing → 59.09.",
            "rule_applied": "GIR 1 — heading 59.09"})
        return result
    if _CH59_TARPAULIN.search(text):
        result["candidates"].append({"heading": "59.07", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Tarpaulin / awning / tent fabric → 59.07.",
            "rule_applied": "GIR 1 — heading 59.07"})
        return result
    if re.search(r'(?:linoleum|לינוליאום|floor\s*covering)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "59.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Linoleum / textile-base floor covering → 59.04.",
            "rule_applied": "GIR 1 — heading 59.04"})
        return result
    if _CH59_COATED.search(text):
        if re.search(r'(?:rubber|גומי)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "59.06", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Rubberized textile fabric → 59.06.",
                "rule_applied": "GIR 1 — heading 59.06"})
        else:
            result["candidates"].append({"heading": "59.03", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Textile fabric coated/impregnated with plastics → 59.03.",
                "rule_applied": "GIR 1 — heading 59.03"})
        return result

    result["candidates"].append({"heading": "59.03", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Coated/impregnated textile type unclear → 59.03.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Tyre cord, conveyor belt, tarpaulin, hose, or coated/impregnated fabric?")
    return result


# ============================================================================
# CHAPTER 60: Knitted or crocheted fabrics
# ============================================================================

_CH60_PILE_KNIT = re.compile(
    r'(?:סריג\s*(?:קטיפה|פלאש)|knitted\s*pile|knit\s*velour|'
    r'knit\s*velvet|knit\s*plush|terry\s*knit)',
    re.IGNORECASE
)
_CH60_WARP_KNIT = re.compile(
    r'(?:סריג\s*שתי|warp.?knit|raschel|tricot\s*(?:fabric|knit)|'
    r'rachel\s*(?:fabric|knit))',
    re.IGNORECASE
)
_CH60_WEFT_KNIT = re.compile(
    r'(?:סריג\s*ערב|weft.?knit|circular\s*knit|jersey\s*(?:fabric|knit)|'
    r'interlock\s*(?:fabric|knit)|rib\s*knit|pique\s*knit|'
    r'single\s*jersey|double\s*jersey|fleece\s*(?:fabric|knit))',
    re.IGNORECASE
)
_CH60_KNIT_GENERAL = re.compile(
    r'(?:סריג|בד\s*סרוג|knitted\s*fabric|crocheted\s*fabric|'
    r'knit\s*fabric|jersey|interlock|fleece\s*fabric)',
    re.IGNORECASE
)


def _is_chapter_60_candidate(text):
    return bool(
        _CH60_PILE_KNIT.search(text) or _CH60_WARP_KNIT.search(text)
        or _CH60_WEFT_KNIT.search(text) or _CH60_KNIT_GENERAL.search(text)
    )


def _decide_chapter_60(product):
    """Chapter 60: Knitted or crocheted fabrics (not made up).

    Headings:
        60.01 — Pile fabrics (including long pile and terry), knitted/crocheted
        60.02 — Knitted/crocheted fabrics of width ≤30cm, ≥5% elastomeric/rubber
        60.03 — Knitted/crocheted fabrics of width ≤30cm (other than 60.01/60.02)
        60.04 — Knitted/crocheted fabrics of width >30cm, ≥5% elastomeric/rubber
        60.05 — Warp knit fabrics (including Raschel lace), other than 60.01-60.04
        60.06 — Other knitted/crocheted fabrics
    """
    text = _product_text(product)
    result = {"chapter": 60, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH60_PILE_KNIT.search(text):
        result["candidates"].append({"heading": "60.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Knitted pile / velour / terry knit fabric → 60.01.",
            "rule_applied": "GIR 1 — heading 60.01"})
        return result
    if _CH60_WARP_KNIT.search(text):
        result["candidates"].append({"heading": "60.05", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Warp-knit fabric (Raschel/tricot) → 60.05.",
            "rule_applied": "GIR 1 — heading 60.05"})
        return result
    if _CH60_WEFT_KNIT.search(text):
        result["candidates"].append({"heading": "60.06", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Weft-knit / circular knit / jersey / interlock fabric → 60.06.",
            "rule_applied": "GIR 1 — heading 60.06"})
        return result

    result["candidates"].append({"heading": "60.06", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Knitted/crocheted fabric type unclear → 60.06.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Warp-knit or weft-knit? Pile/terry? Width ≤30cm or >30cm?")
    return result


# ============================================================================
# CHAPTER 61: Articles of apparel, knitted or crocheted
# ============================================================================

_CH61_COAT = re.compile(
    r'(?:מעיל\s*סרוג|knitted?\s*(?:overcoat|coat|jacket|anorak|parka|windbreaker)|'
    r'knit\s*(?:jacket|blazer)|cardigan)',
    re.IGNORECASE
)
_CH61_SUIT = re.compile(
    r'(?:חליפה\s*סרוגה|knitted?\s*(?:suit|ensemble)|'
    r'knit\s*suit)',
    re.IGNORECASE
)
_CH61_TSHIRT = re.compile(
    r'(?:חולצת?\s*(?:טי|T)|\bT.?shirt|tee.?shirt|singlet|tank\s*top|vest\s*(?:knit|jersey))',
    re.IGNORECASE
)
_CH61_SWEATER = re.compile(
    r'(?:סוודר|פולאובר|pullover|sweater|sweatshirt|hoodie|'
    r'jumper|jersey\s*(?:garment|top)|knit\s*top)',
    re.IGNORECASE
)
_CH61_TROUSERS = re.compile(
    r'(?:מכנסיים?\s*סרוג|knitted?\s*(?:trousers|pants|shorts|leggings|joggers)|'
    r'knit\s*(?:trousers|pants|shorts)|sweatpants)',
    re.IGNORECASE
)
_CH61_DRESS = re.compile(
    r'(?:שמלה\s*סרוגה|knitted?\s*(?:dress|skirt)|knit\s*(?:dress|skirt))',
    re.IGNORECASE
)
_CH61_UNDERWEAR = re.compile(
    r'(?:תחתונים?\s*סרוג|הלבשה\s*תחתונה|underwear\s*knit|underpants\s*knit|'
    r'briefs?\s*knit|panties?\s*knit|bra\s*knit|nightdress\s*knit|pyjama\s*knit|'
    r'nightwear\s*knit|dressing\s*gown\s*knit|bathrobe\s*knit)',
    re.IGNORECASE
)
_CH61_HOSIERY = re.compile(
    r'(?:גרביים|גרביונים|גרב|hosiery|stockings?|tights|pantyhose|socks?)',
    re.IGNORECASE
)
_CH61_BABY = re.compile(
    r'(?:תינוק|baby|infant|babies\s*(?:garment|clothing|wear))',
    re.IGNORECASE
)
_CH61_KNIT_GARMENT = re.compile(
    r'(?:בגד\s*סרוג|ביגוד\s*סרוג|knitted?\s*(?:garment|apparel|clothing|wear)|'
    r'T.?shirt|sweater|pullover|cardigan|hoodie|leggings|joggers|'
    r'sweatshirt|sweatpants|tracksuit|knit\s*(?:top|dress|skirt|blouse))',
    re.IGNORECASE
)


def _is_chapter_61_candidate(text):
    return bool(
        _CH61_TSHIRT.search(text) or _CH61_SWEATER.search(text)
        or _CH61_HOSIERY.search(text) or _CH61_KNIT_GARMENT.search(text)
        or _CH61_UNDERWEAR.search(text) or _CH61_COAT.search(text)
    )


def _decide_chapter_61(product):
    """Chapter 61: Articles of apparel and clothing accessories, knitted or crocheted.

    Headings:
        61.01 — Men's/boys' overcoats, jackets, anoraks (knitted)
        61.02 — Women's/girls' overcoats, jackets, anoraks (knitted)
        61.03 — Men's/boys' suits, ensembles, trousers, shorts (knitted)
        61.04 — Women's/girls' suits, dresses, skirts, trousers (knitted)
        61.05 — Men's/boys' shirts (knitted)
        61.06 — Women's/girls' blouses, shirts (knitted)
        61.07 — Men's/boys' underpants, briefs, nightshirts, pyjamas, robes (knitted)
        61.08 — Women's/girls' slips, briefs, nightdresses, pyjamas, robes (knitted)
        61.09 — T-shirts, singlets, tank tops (knitted)
        61.10 — Jerseys, pullovers, cardigans, waistcoats (knitted)
        61.11 — Babies' garments (knitted)
        61.12 — Track suits, ski suits, swimwear (knitted)
        61.13 — Garments of fabric of 59.03, 59.06, 59.07 (knitted)
        61.14 — Other garments (knitted)
        61.15 — Hosiery (stockings, tights, socks) (knitted)
        61.16 — Gloves, mittens (knitted)
        61.17 — Other clothing accessories; parts of garments (knitted)
    """
    text = _product_text(product)
    result = {"chapter": 61, "candidates": [], "redirect": None, "questions_needed": []}

    is_men = bool(re.search(r'(?:גבר|men|boy|male|man\b)', text, re.IGNORECASE))
    is_women = bool(re.search(r'(?:נש|אשה|women|girl|female|ladies)', text, re.IGNORECASE))

    if _CH61_HOSIERY.search(text):
        result["candidates"].append({"heading": "61.15", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Hosiery / stockings / socks (knitted) → 61.15.",
            "rule_applied": "GIR 1 — heading 61.15"})
        return result
    if _CH61_TSHIRT.search(text):
        result["candidates"].append({"heading": "61.09", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "T-shirt / singlet / tank top (knitted) → 61.09.",
            "rule_applied": "GIR 1 — heading 61.09"})
        return result
    if _CH61_SWEATER.search(text):
        result["candidates"].append({"heading": "61.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Sweater / pullover / cardigan / hoodie (knitted) → 61.10.",
            "rule_applied": "GIR 1 — heading 61.10"})
        return result
    if _CH61_BABY.search(text):
        result["candidates"].append({"heading": "61.11", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Babies' garment (knitted) → 61.11.",
            "rule_applied": "GIR 1 — heading 61.11"})
        return result
    if _CH61_UNDERWEAR.search(text):
        heading = "61.07" if is_men else "61.08"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Underwear/nightwear (knitted) → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH61_COAT.search(text):
        heading = "61.01" if is_men else "61.02"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Coat/jacket (knitted) → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH61_DRESS.search(text):
        result["candidates"].append({"heading": "61.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Dress / skirt (knitted) → 61.04.",
            "rule_applied": "GIR 1 — heading 61.04"})
        return result
    if _CH61_TROUSERS.search(text):
        heading = "61.03" if is_men else "61.04"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Trousers/shorts (knitted) → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if re.search(r'(?:glove|mitten|כפפ)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "61.16", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Knitted gloves / mittens → 61.16.",
            "rule_applied": "GIR 1 — heading 61.16"})
        return result
    if re.search(r'(?:tracksuit|track\s*suit|ski\s*suit|swimwear|swimsuit|swim\s*trunk)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "61.12", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Track suit / ski suit / swimwear (knitted) → 61.12.",
            "rule_applied": "GIR 1 — heading 61.12"})
        return result

    result["candidates"].append({"heading": "61.14", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Knitted garment type unclear → 61.14.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("T-shirt, sweater, coat, trousers, dress, underwear, or hosiery? Men's or women's?")
    return result


# ============================================================================
# CHAPTER 62: Articles of apparel, not knitted or crocheted (woven)
# ============================================================================

_CH62_COAT = re.compile(
    r'(?:מעיל(?!\s*סרוג)|overcoat|trench\s*coat|raincoat|'
    r'woven\s*(?:coat|jacket|anorak|parka|windbreaker|blazer))',
    re.IGNORECASE
)
_CH62_SUIT = re.compile(
    r'(?:חליפה(?!\s*סרוגה)|woven\s*suit|business\s*suit|formal\s*suit|ensemble)',
    re.IGNORECASE
)
_CH62_SHIRT = re.compile(
    r'(?:חולצה\s*מכופתרת|woven\s*shirt|dress\s*shirt|button.?(?:down|up)\s*shirt|'
    r'blouse|men.?s?\s*shirt)',
    re.IGNORECASE
)
_CH62_TROUSERS = re.compile(
    r'(?:מכנסיים?(?!\s*סרוג)|woven\s*(?:trousers|pants|shorts)|'
    r'jeans|denim\s*(?:trousers|pants)|chinos|cargo\s*pants)',
    re.IGNORECASE
)
_CH62_DRESS = re.compile(
    r'(?:שמלה(?!\s*סרוגה)|woven\s*(?:dress|skirt)|skirt)',
    re.IGNORECASE
)
_CH62_WORKWEAR = re.compile(
    r'(?:בגד\s*עבודה|workwear|work\s*(?:clothing|garment)|industrial\s*garment|'
    r'overall|coverall|boiler\s*suit|uniform)',
    re.IGNORECASE
)
_CH62_UNDERWEAR = re.compile(
    r'(?:תחתונים?(?!\s*סרוג)|woven\s*(?:underwear|underpants|briefs|panties)|'
    r'woven\s*(?:nightdress|pyjama|nightwear|bathrobe)|'
    r'handkerchief|pocket\s*square)',
    re.IGNORECASE
)
_CH62_WOVEN_GARMENT = re.compile(
    r'(?:בגד(?!\s*סרוג)|ביגוד(?!\s*סרוג)|woven\s*(?:garment|apparel|clothing)|'
    r'shirt|blouse|trousers|pants|jeans|dress|skirt|suit|jacket|coat|'
    r'overall|coverall|uniform|workwear)',
    re.IGNORECASE
)


def _is_chapter_62_candidate(text):
    return bool(
        _CH62_SHIRT.search(text) or _CH62_TROUSERS.search(text)
        or _CH62_COAT.search(text) or _CH62_WOVEN_GARMENT.search(text)
        or _CH62_WORKWEAR.search(text) or _CH62_DRESS.search(text)
    )


def _decide_chapter_62(product):
    """Chapter 62: Articles of apparel and clothing accessories, not knitted or crocheted.

    Headings:
        62.01 — Men's/boys' overcoats, cloaks, anoraks, wind-jackets
        62.02 — Women's/girls' overcoats, cloaks, anoraks, wind-jackets
        62.03 — Men's/boys' suits, ensembles, trousers, shorts
        62.04 — Women's/girls' suits, dresses, skirts, trousers
        62.05 — Men's/boys' shirts
        62.06 — Women's/girls' blouses, shirts
        62.07 — Men's/boys' singlets, underpants, briefs, nightshirts, pyjamas, robes
        62.08 — Women's/girls' singlets, slips, briefs, nightdresses, pyjamas, robes
        62.09 — Babies' garments
        62.10 — Garments of fabric of 56.02, 56.03, 59.03, 59.06, 59.07
        62.11 — Track suits, ski suits, swimwear; other garments
        62.12 — Brassieres, girdles, corsets, braces, suspenders, garters
        62.13 — Handkerchiefs
        62.14 — Shawls, scarves, mufflers, mantillas, veils
        62.15 — Ties, bow ties, cravats
        62.16 — Gloves, mittens
        62.17 — Other clothing accessories; parts of garments
    """
    text = _product_text(product)
    result = {"chapter": 62, "candidates": [], "redirect": None, "questions_needed": []}

    is_men = bool(re.search(r'(?:גבר|men|boy|male|man\b)', text, re.IGNORECASE))

    if re.search(r'(?:baby|infant|תינוק)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.09", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Babies' woven garment → 62.09.",
            "rule_applied": "GIR 1 — heading 62.09"})
        return result
    if re.search(r'(?:handkerchief|pocket\s*square|ממחטה)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.13", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Handkerchief → 62.13.",
            "rule_applied": "GIR 1 — heading 62.13"})
        return result
    if re.search(r'(?:tie\b|bow\s*tie|cravat|עניבה)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.15", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Tie / bow tie / cravat → 62.15.",
            "rule_applied": "GIR 1 — heading 62.15"})
        return result
    if re.search(r'(?:shawl|scarf|muffler|veil|צעיף|רעלה)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.14", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Shawl / scarf / veil → 62.14.",
            "rule_applied": "GIR 1 — heading 62.14"})
        return result
    if re.search(r'(?:brassiere|bra\b|girdle|corset|חזיי?ה)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.12", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Brassiere / girdle / corset → 62.12.",
            "rule_applied": "GIR 1 — heading 62.12"})
        return result
    if re.search(r'(?:glove|mitten|כפפ)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "62.16", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Woven gloves / mittens → 62.16.",
            "rule_applied": "GIR 1 — heading 62.16"})
        return result
    if _CH62_WORKWEAR.search(text):
        result["candidates"].append({"heading": "62.11", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Workwear / overall / coverall / uniform → 62.11.",
            "rule_applied": "GIR 1 — heading 62.11"})
        return result
    if _CH62_COAT.search(text):
        heading = "62.01" if is_men else "62.02"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Overcoat / jacket (woven) → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH62_SHIRT.search(text):
        heading = "62.05" if is_men else "62.06"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Shirt / blouse (woven) → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH62_DRESS.search(text):
        result["candidates"].append({"heading": "62.04", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Dress / skirt (woven) → 62.04.",
            "rule_applied": "GIR 1 — heading 62.04"})
        return result
    if _CH62_TROUSERS.search(text):
        heading = "62.03" if is_men else "62.04"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Trousers / pants / jeans → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH62_SUIT.search(text):
        heading = "62.03" if is_men else "62.04"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Suit / ensemble → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "62.11", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Woven garment type unclear → 62.11.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Coat, suit, shirt, trousers, dress, workwear? Men's or women's?")
    return result


# ============================================================================
# CHAPTER 63: Other made up textile articles; sets; worn clothing; rags
# ============================================================================

_CH63_BLANKET = re.compile(
    r'(?:שמיכה|כירבולית|blanket|travelling\s*rug|bed\s*spread|'
    r'quilt|duvet|comforter|eiderdown)',
    re.IGNORECASE
)
_CH63_BEDLINEN = re.compile(
    r'(?:מצעים?|סדין|ציפה|ציפית|bed\s*linen|bed\s*sheet|'
    r'pillow\s*case|duvet\s*cover|fitted\s*sheet|flat\s*sheet)',
    re.IGNORECASE
)
_CH63_CURTAIN = re.compile(
    r'(?:וילון|curtain|drape|blind\s*(?:textile|fabric)|'
    r'valance|bed\s*valance|interior\s*blind)',
    re.IGNORECASE
)
_CH63_TABLE_LINEN = re.compile(
    r'(?:מפת?\s*שולחן|table\s*(?:linen|cloth)|(?:cloth|linen|textile)\s*napkin|serviette|'
    r'toilet\s*linen|kitchen\s*linen|dish\s*cloth|tea\s*towel)',
    re.IGNORECASE
)
_CH63_BAG = re.compile(
    r'(?:שק|שקית\s*טקסטיל|sack|bag\s*(?:textile|woven|jute|polypropylene)|'
    r'FIBC|bulk\s*bag|big\s*bag|jumbo\s*bag)',
    re.IGNORECASE
)
_CH63_WORN = re.compile(
    r'(?:בגדים?\s*(?:משומש|יד\s*שנייה)|worn\s*clothing|used\s*clothing|'
    r'second.?hand\s*clothing|\brags?\b|wiping\s*cloth|cleaning\s*cloth)',
    re.IGNORECASE
)
_CH63_GENERAL = re.compile(
    r'(?:blanket|bed\s*linen|curtain|table\s*cloth|sack|bag\s*textile|'
    r'worn\s*clothing|rag|towel|dishcloth|tarpaulin\s*textile)',
    re.IGNORECASE
)


def _is_chapter_63_candidate(text):
    return bool(
        _CH63_BLANKET.search(text) or _CH63_BEDLINEN.search(text)
        or _CH63_CURTAIN.search(text) or _CH63_TABLE_LINEN.search(text)
        or _CH63_BAG.search(text) or _CH63_WORN.search(text)
    )


def _decide_chapter_63(product):
    """Chapter 63: Other made up textile articles; sets; worn clothing and worn textile articles; rags.

    Headings:
        63.01 — Blankets and travelling rugs
        63.02 — Bed linen, table linen, toilet linen, kitchen linen
        63.03 — Curtains, drapes, interior blinds, bed valances
        63.04 — Other furnishing articles (bedspreads, cushions, pouffes)
        63.05 — Sacks and bags for packing goods
        63.06 — Tarpaulins, awnings, tents; sails; camping goods
        63.07 — Other made up articles (floor cloths, dish cloths, dusters, life jackets)
        63.08 — Sets of woven fabric + yarn for making rugs/tapestries/etc.
        63.09 — Worn clothing and other worn textile articles
        63.10 — Used or new rags, scrap twine, cordage, rope
    """
    text = _product_text(product)
    result = {"chapter": 63, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH63_WORN.search(text):
        if re.search(r'(?:rag|wiping|cleaning\s*cloth|סמרטוט)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "63.10", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Rags / wiping cloths / scrap textiles → 63.10.",
                "rule_applied": "GIR 1 — heading 63.10"})
        else:
            result["candidates"].append({"heading": "63.09", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Worn / second-hand clothing → 63.09.",
                "rule_applied": "GIR 1 — heading 63.09"})
        return result
    if _CH63_BLANKET.search(text):
        result["candidates"].append({"heading": "63.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Blanket / quilt / duvet / comforter → 63.01.",
            "rule_applied": "GIR 1 — heading 63.01"})
        return result
    if _CH63_BEDLINEN.search(text):
        result["candidates"].append({"heading": "63.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Bed linen / sheets / pillow case → 63.02.",
            "rule_applied": "GIR 1 — heading 63.02"})
        return result
    if _CH63_TABLE_LINEN.search(text):
        result["candidates"].append({"heading": "63.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Table linen / napkin / kitchen linen → 63.02.",
            "rule_applied": "GIR 1 — heading 63.02"})
        return result
    if _CH63_CURTAIN.search(text):
        result["candidates"].append({"heading": "63.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Curtain / drape / blind → 63.03.",
            "rule_applied": "GIR 1 — heading 63.03"})
        return result
    if _CH63_BAG.search(text):
        result["candidates"].append({"heading": "63.05", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Textile sack / bag for packing → 63.05.",
            "rule_applied": "GIR 1 — heading 63.05"})
        return result

    result["candidates"].append({"heading": "63.07", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Made up textile article type unclear → 63.07.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Blanket, bed linen, curtain, bag, worn clothing, or rags?")
    return result


# ============================================================================
# CHAPTER 64: Footwear, gaiters and the like; parts of such articles
# ============================================================================

_CH64_LEATHER_UPPER = re.compile(
    r'(?:נעל\s*עור|leather\s*(?:shoe|boot|upper)|upper\s*(?:of\s*)?leather|'
    r'leather\s*(?:footwear|sandal|loafer|oxford|derby|brogue))',
    re.IGNORECASE
)
_CH64_RUBBER_UPPER = re.compile(
    r'(?:נעל\s*גומי|rubber\s*(?:shoe|boot|footwear)|wellington|'
    r'galosh|gumboot|waterproof\s*(?:boot|shoe))',
    re.IGNORECASE
)
_CH64_TEXTILE_UPPER = re.compile(
    r'(?:נעל\s*(?:בד|טקסטיל)|textile\s*(?:shoe|upper|footwear)|'
    r'canvas\s*(?:shoe|sneaker)|espadrille|cloth\s*shoe)',
    re.IGNORECASE
)
_CH64_SPORTS = re.compile(
    r'(?:נעל\s*ספורט|sports?\s*(?:shoe|footwear)|sneaker|trainer|'
    r'athletic\s*shoe|running\s*shoe|tennis\s*shoe|basketball\s*shoe|'
    r'football\s*boot|ski\s*boot|hiking\s*boot)',
    re.IGNORECASE
)
_CH64_FOOTWEAR_GENERAL = re.compile(
    r'(?:נעל|מגף|סנדל|shoe|boot|footwear|sandal|slipper|'
    r'sneaker|trainer|loafer|pump|\bheel\b|moccasin|clog|'
    r'flip.?flop|insole|outsole|\bsole\b)',
    re.IGNORECASE
)


def _is_chapter_64_candidate(text):
    return bool(
        _CH64_LEATHER_UPPER.search(text) or _CH64_RUBBER_UPPER.search(text)
        or _CH64_TEXTILE_UPPER.search(text) or _CH64_SPORTS.search(text)
        or _CH64_FOOTWEAR_GENERAL.search(text)
    )


def _decide_chapter_64(product):
    """Chapter 64: Footwear, gaiters and the like; parts of such articles.

    Headings:
        64.01 — Waterproof footwear with outer soles and uppers of rubber/plastics
        64.02 — Other footwear with outer soles and uppers of rubber/plastics
        64.03 — Footwear with outer soles of rubber/plastics/leather, uppers of leather
        64.04 — Footwear with outer soles of rubber/plastics/leather, uppers of textile
        64.05 — Other footwear
        64.06 — Parts of footwear; removable insoles, heel cushions; gaiters, leggings
    """
    text = _product_text(product)
    result = {"chapter": 64, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:insole|outsole|heel\s*(?:cushion|pad)|gaiter|legging\s*leather|sole\s*(?:part|component))', text, re.IGNORECASE):
        result["candidates"].append({"heading": "64.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Footwear parts / insoles / gaiters → 64.06.",
            "rule_applied": "GIR 1 — heading 64.06"})
        return result
    if re.search(r'(?:waterproof|water.?tight|wellington|galosh|gumboot)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "64.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Waterproof footwear (rubber/plastic upper+sole) → 64.01.",
            "rule_applied": "GIR 1 — heading 64.01"})
        return result
    if _CH64_LEATHER_UPPER.search(text):
        result["candidates"].append({"heading": "64.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Footwear with leather upper → 64.03.",
            "rule_applied": "GIR 1 — heading 64.03"})
        return result
    if _CH64_TEXTILE_UPPER.search(text):
        result["candidates"].append({"heading": "64.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Footwear with textile upper → 64.04.",
            "rule_applied": "GIR 1 — heading 64.04"})
        return result
    if _CH64_RUBBER_UPPER.search(text) or _CH64_SPORTS.search(text):
        result["candidates"].append({"heading": "64.02", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Footwear with rubber/plastic upper (sports/casual) → 64.02.",
            "rule_applied": "GIR 1 — heading 64.02"})
        return result

    result["candidates"].append({"heading": "64.05", "subheading_hint": None,
        "confidence": 0.60, "reasoning": "Footwear upper material unclear → 64.05.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Upper material: leather, rubber/plastic, or textile? Waterproof?")
    return result


# ============================================================================
# CHAPTER 65: Headgear and parts thereof
# ============================================================================

_CH65_HAT_BODY = re.compile(
    r'(?:גולם\s*כובע|hat\s*(?:body|form|blank|shape)|felt\s*(?:hood|cone)|'
    r'hat\s*braid|plait\s*(?:for\s*)?hat)',
    re.IGNORECASE
)
_CH65_HELMET = re.compile(
    r'(?:קסדה|helmet|safety\s*helmet|hard\s*hat|crash\s*helmet|'
    r'motorcycle\s*helmet|bicycle\s*helmet|protective\s*headgear)',
    re.IGNORECASE
)
_CH65_HEADGEAR_GENERAL = re.compile(
    r'(?:כובע|כיפה|מצנפת|hat|cap|beret|bonnet|headgear|headwear|'
    r'baseball\s*cap|sun\s*hat|straw\s*hat|felt\s*hat|panama|fedora|'
    r'turban|visor|peak\s*cap|beanie|skull\s*cap)',
    re.IGNORECASE
)


def _is_chapter_65_candidate(text):
    return bool(
        _CH65_HELMET.search(text) or _CH65_HEADGEAR_GENERAL.search(text)
        or _CH65_HAT_BODY.search(text)
    )


def _decide_chapter_65(product):
    """Chapter 65: Headgear and parts thereof.

    Headings:
        65.01 — Hat-forms, hat bodies and hoods of felt; plateaux and manchons of felt
        65.02 — Hat-shapes, plaited or made by assembling strips of any material
        65.03 — Felt hats and other felt headgear (from 65.01 bodies)
        65.04 — Hats and other headgear, plaited or made by assembling strips
        65.05 — Hats and other headgear, knitted/crocheted, or from lace/felt/textile in the piece
        65.06 — Other headgear (whether or not lined or trimmed)
        65.07 — Head-bands, linings, covers, foundations, frames, peaks, chin straps
    """
    text = _product_text(product)
    result = {"chapter": 65, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:head.?band|lining\s*hat|chin\s*strap|peak\s*(?:for\s*)?hat|hat\s*frame)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "65.07", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Headgear parts / accessories → 65.07.",
            "rule_applied": "GIR 1 — heading 65.07"})
        return result
    if _CH65_HELMET.search(text):
        result["candidates"].append({"heading": "65.06", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Safety / protective helmet → 65.06.",
            "rule_applied": "GIR 1 — heading 65.06"})
        return result
    if _CH65_HAT_BODY.search(text):
        if re.search(r'(?:plait|braid|strip|straw)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "65.02", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Hat-shape of plaited/strip material → 65.02.",
                "rule_applied": "GIR 1 — heading 65.02"})
        else:
            result["candidates"].append({"heading": "65.01", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Hat body / hood of felt → 65.01.",
                "rule_applied": "GIR 1 — heading 65.01"})
        return result
    if re.search(r'(?:felt\s*hat|כובע\s*לבד)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "65.03", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Felt hat / headgear → 65.03.",
            "rule_applied": "GIR 1 — heading 65.03"})
        return result
    if re.search(r'(?:straw\s*hat|panama|plaited\s*hat)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "65.04", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Plaited / straw hat → 65.04.",
            "rule_applied": "GIR 1 — heading 65.04"})
        return result
    if re.search(r'(?:knit|crochet|lace|textile|fabric|beanie)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "65.05", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Knitted/crocheted/textile headgear → 65.05.",
            "rule_applied": "GIR 1 — heading 65.05"})
        return result

    result["candidates"].append({"heading": "65.06", "subheading_hint": None,
        "confidence": 0.65, "reasoning": "Headgear type/material unclear → 65.06.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Hat, cap, helmet, beret? Material: felt, straw, textile, plastic?")
    return result


# ============================================================================
# CHAPTER 66: Umbrellas, sun umbrellas, walking sticks, seat-sticks, whips
# ============================================================================

_CH66_UMBRELLA = re.compile(
    r'(?:מטריה|שמשייה|umbrella|parasol|sun\s*umbrella|'
    r'garden\s*umbrella|beach\s*umbrella|golf\s*umbrella)',
    re.IGNORECASE
)
_CH66_WALKING_STICK = re.compile(
    r'(?:מקל\s*הליכה|walking\s*stick|cane|seat.?stick|'
    r'swagger\s*stick|crop|riding\s*crop|whip)',
    re.IGNORECASE
)
_CH66_GENERAL = re.compile(
    r'(?:umbrella|parasol|walking\s*stick|cane|whip|crop)',
    re.IGNORECASE
)


def _is_chapter_66_candidate(text):
    return bool(
        _CH66_UMBRELLA.search(text) or _CH66_WALKING_STICK.search(text)
    )


def _decide_chapter_66(product):
    """Chapter 66: Umbrellas, sun umbrellas, walking-sticks, seat-sticks, whips, riding-crops and parts thereof.

    Headings:
        66.01 — Umbrellas and sun umbrellas (including garden umbrellas)
        66.02 — Walking-sticks, seat-sticks, whips, riding-crops and the like
        66.03 — Parts, trimmings and accessories of 66.01 or 66.02
    """
    text = _product_text(product)
    result = {"chapter": 66, "candidates": [], "redirect": None, "questions_needed": []}

    if re.search(r'(?:part|trim|accessori|frame|handle|rib|runner|ferrule|tip)\s*(?:of\s*)?(?:umbrella|walking|stick)', text, re.IGNORECASE):
        result["candidates"].append({"heading": "66.03", "subheading_hint": None,
            "confidence": 0.80, "reasoning": "Parts/trimmings of umbrella or walking stick → 66.03.",
            "rule_applied": "GIR 1 — heading 66.03"})
        return result
    if _CH66_UMBRELLA.search(text):
        result["candidates"].append({"heading": "66.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Umbrella / parasol / sun umbrella → 66.01.",
            "rule_applied": "GIR 1 — heading 66.01"})
        return result
    if _CH66_WALKING_STICK.search(text):
        result["candidates"].append({"heading": "66.02", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Walking stick / cane / whip / riding crop → 66.02.",
            "rule_applied": "GIR 1 — heading 66.02"})
        return result

    result["candidates"].append({"heading": "66.01", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Umbrella/stick type unclear → 66.01.",
        "rule_applied": "GIR 1"})
    return result


# ============================================================================
# CHAPTER 67: Prepared feathers; artificial flowers; articles of human hair
# ============================================================================

_CH67_FEATHER = re.compile(
    r'(?:נוצה|feather|down\s*(?:filling|stuff)|plumage|quill)',
    re.IGNORECASE
)
_CH67_ARTIFICIAL_FLOWER = re.compile(
    r'(?:פרח\s*(?:מלאכותי|פלסטיק|בד)|artificial\s*(?:flower|plant|foliage|fruit|grass)|'
    r'silk\s*flower|plastic\s*flower|fake\s*(?:flower|plant))',
    re.IGNORECASE
)
_CH67_HUMAN_HAIR = re.compile(
    r'(?:שיער\s*(?:אדם|תותב)|פאה|human\s*hair|wig|toupee|hairpiece|false\s*beard)',
    re.IGNORECASE
)
_CH67_GENERAL = re.compile(
    r'(?:feather|down\s*filling|artificial\s*flower|fake\s*plant|wig|toupee|hairpiece)',
    re.IGNORECASE
)


def _is_chapter_67_candidate(text):
    return bool(
        _CH67_FEATHER.search(text) or _CH67_ARTIFICIAL_FLOWER.search(text)
        or _CH67_HUMAN_HAIR.search(text)
    )


def _decide_chapter_67(product):
    """Chapter 67: Prepared feathers and down; artificial flowers; articles of human hair.

    Headings:
        67.01 — Skins and other parts of birds with feathers/down; feathers; articles thereof
        67.02 — Artificial flowers, foliage, fruit; articles thereof
        67.03 — Human hair, dressed/thinned/bleached; wool/animal hair prepared for wig-making
        67.04 — Wigs, false beards, eyebrows, eyelashes, switches and the like
    """
    text = _product_text(product)
    result = {"chapter": 67, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH67_HUMAN_HAIR.search(text):
        if re.search(r'(?:wig|toupee|hairpiece|false|switch|פאה|תותב)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "67.04", "subheading_hint": None,
                "confidence": 0.90, "reasoning": "Wig / toupee / hairpiece / false beard → 67.04.",
                "rule_applied": "GIR 1 — heading 67.04"})
        else:
            result["candidates"].append({"heading": "67.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Human hair dressed / prepared for wig-making → 67.03.",
                "rule_applied": "GIR 1 — heading 67.03"})
        return result
    if _CH67_ARTIFICIAL_FLOWER.search(text):
        result["candidates"].append({"heading": "67.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Artificial flower / plant / foliage → 67.02.",
            "rule_applied": "GIR 1 — heading 67.02"})
        return result
    if _CH67_FEATHER.search(text):
        result["candidates"].append({"heading": "67.01", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Prepared feathers / down / bird skins → 67.01.",
            "rule_applied": "GIR 1 — heading 67.01"})
        return result

    result["candidates"].append({"heading": "67.02", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Feather/artificial flower/hair type unclear → 67.02.",
        "rule_applied": "GIR 1"})
    return result


# ============================================================================
# CHAPTER 68: Articles of stone, plaster, cement, asbestos, mica or similar
# ============================================================================

_CH68_STONE = re.compile(
    r'(?:אבן\s*(?:בנייה|חיפוי|ריצוף|שיש)|stone\s*(?:tile|slab|paving|block|kerb|flagstone)|'
    r'marble\s*(?:tile|slab|block|article)|granite\s*(?:tile|slab|block)|'
    r'slate\s*(?:tile|slab)|worked\s*stone|monumental\s*stone)',
    re.IGNORECASE
)
_CH68_CEMENT = re.compile(
    r'(?:מלט|בטון\s*(?:מוצר|אריח|בלוק|צינור)|cement\s*(?:product|tile|block|pipe|board)|'
    r'concrete\s*(?:product|tile|block|pipe|slab|beam|pole)|'
    r'fibre.?cement|asbestos.?cement)',
    re.IGNORECASE
)
_CH68_PLASTER = re.compile(
    r'(?:גבס\s*(?:מוצר|לוח|בלוק)|plaster\s*(?:product|board|block|article)|'
    r'gypsum\s*(?:board|panel|block)|drywall|plasterboard)',
    re.IGNORECASE
)
_CH68_INSULATION = re.compile(
    r'(?:בידוד\s*(?:תרמי|אקוסטי)|insulation\s*(?:mineral|rock|glass)\s*wool|'
    r'mineral\s*wool|rock\s*wool|glass\s*wool\s*(?:insulation|board|mat)|'
    r'slag\s*wool|vermiculite\s*(?:expanded|product)|perlite\s*(?:expanded|product))',
    re.IGNORECASE
)
_CH68_FRICTION = re.compile(
    r'(?:חומר\s*חיכוך|friction\s*(?:material|lining|pad)|brake\s*(?:lining|pad)|'
    r'clutch\s*(?:lining|facing))',
    re.IGNORECASE
)
_CH68_MILLSTONE = re.compile(
    r'(?:אבן\s*(?:ריחיים|השחזה|שחיקה)|millstone|grindstone|grinding\s*wheel|'
    r'abrasive\s*(?:wheel|disc|stone)|sharpening\s*stone|whetstone)',
    re.IGNORECASE
)
_CH68_GENERAL = re.compile(
    r'(?:stone\s*article|marble\s*article|granite\s*article|cement\s*article|'
    r'concrete\s*article|plaster\s*board|insulation\s*wool|friction\s*material|'
    r'grindstone|millstone|asbestos|mica)',
    re.IGNORECASE
)


def _is_chapter_68_candidate(text):
    return bool(
        _CH68_STONE.search(text) or _CH68_CEMENT.search(text)
        or _CH68_PLASTER.search(text) or _CH68_INSULATION.search(text)
        or _CH68_FRICTION.search(text) or _CH68_MILLSTONE.search(text)
    )


def _decide_chapter_68(product):
    """Chapter 68: Articles of stone, plaster, cement, asbestos, mica or similar materials.

    Headings:
        68.01 — Setts, curbstones, flagstones of natural stone
        68.02 — Worked monumental/building stone and articles thereof; mosaic cubes
        68.03 — Worked slate and articles thereof
        68.04 — Millstones, grindstones, grinding wheels, polishing stones
        68.05 — Abrasive powder/grain on textile/paper/paperboard base
        68.06 — Slag wool, rock wool, mineral wools; exfoliated vermiculite, expanded clays
        68.07 — Articles of asphalt or similar material (roofing, damp-proofing)
        68.08 — Panels/boards/tiles of vegetable fibre/straw/shavings bonded with cement/plaster
        68.09 — Articles of plaster or compositions based on plaster
        68.10 — Articles of cement, concrete or artificial stone
        68.11 — Articles of asbestos-cement, cellulose fibre-cement or the like
        68.12 — Fabricated asbestos fibres; mixtures with asbestos; articles thereof
        68.13 — Friction material and articles thereof (brake linings, pads)
        68.14 — Worked mica and articles of mica (sheets, strips)
        68.15 — Articles of stone or other mineral substances n.e.s.
    """
    text = _product_text(product)
    result = {"chapter": 68, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH68_MILLSTONE.search(text):
        result["candidates"].append({"heading": "68.04", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Millstone / grindstone / abrasive wheel → 68.04.",
            "rule_applied": "GIR 1 — heading 68.04"})
        return result
    if _CH68_FRICTION.search(text):
        result["candidates"].append({"heading": "68.13", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Friction material / brake lining / pad → 68.13.",
            "rule_applied": "GIR 1 — heading 68.13"})
        return result
    if _CH68_INSULATION.search(text):
        result["candidates"].append({"heading": "68.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Mineral/rock/glass wool insulation → 68.06.",
            "rule_applied": "GIR 1 — heading 68.06"})
        return result
    if _CH68_PLASTER.search(text):
        result["candidates"].append({"heading": "68.09", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Plaster / gypsum board / drywall → 68.09.",
            "rule_applied": "GIR 1 — heading 68.09"})
        return result
    if _CH68_CEMENT.search(text):
        if re.search(r'(?:asbestos|fibre.?cement|cellulose.?cement)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "68.11", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Asbestos-cement / fibre-cement article → 68.11.",
                "rule_applied": "GIR 1 — heading 68.11"})
        else:
            result["candidates"].append({"heading": "68.10", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Cement / concrete article → 68.10.",
                "rule_applied": "GIR 1 — heading 68.10"})
        return result
    if _CH68_STONE.search(text):
        if re.search(r'(?:sett|curb|kerb|flagstone|paving)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "68.01", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Stone setts / curbstones / flagstones → 68.01.",
                "rule_applied": "GIR 1 — heading 68.01"})
        elif re.search(r'(?:slate|צפחה)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "68.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Worked slate / slate article → 68.03.",
                "rule_applied": "GIR 1 — heading 68.03"})
        else:
            result["candidates"].append({"heading": "68.02", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Worked stone (marble/granite) article → 68.02.",
                "rule_applied": "GIR 1 — heading 68.02"})
        return result

    result["candidates"].append({"heading": "68.15", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Stone/cement/plaster article type unclear → 68.15.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Stone, cement, plaster, insulation, friction material, or millstone?")
    return result


# ============================================================================
# CHAPTER 69: Ceramic products
# ============================================================================

_CH69_REFRACTORY = re.compile(
    r'(?:עמיד\s*אש|refractory|fire.?brick|fire.?clay|'
    r'alumina\s*(?:brick|refractory)|silica\s*(?:brick|refractory)|'
    r'magnesia\s*(?:brick|refractory)|retort|crucible|muffle|'
    r'saggar|kiln\s*furniture)',
    re.IGNORECASE
)
_CH69_TILE = re.compile(
    r'(?:אריח\s*(?:קרמיקה|ריצוף|חיפוי)|ceramic\s*tile|floor\s*tile|wall\s*tile|'
    r'porcelain\s*tile|glazed\s*tile|unglazed\s*tile|mosaic\s*(?:tile|cube))',
    re.IGNORECASE
)
_CH69_BRICK = re.compile(
    r'(?:לבנה|brick\s*(?:ceramic|building)|building\s*brick|roofing\s*tile|'
    r'ceramic\s*(?:pipe|conduit|tube)|chimney\s*(?:liner|pot))',
    re.IGNORECASE
)
_CH69_SANITARY = re.compile(
    r'(?:כלי\s*סניטרי|sanitary\s*ware|toilet\s*(?:bowl|seat|cistern)|wash\s*basin|bidet|bath\s*(?:tub)?|'
    r'sink\s*(?:ceramic|porcelain)|lavatory|urinal)',
    re.IGNORECASE
)
_CH69_TABLEWARE = re.compile(
    r'(?:כלי\s*(?:חרסינה|פורצלן|קרמיקה)|'
    r'(?:tableware|kitchenware|dinnerware)\s*(?:ceramic|porcelain|china)?|'
    r'(?:ceramic|porcelain|china)\s*(?:tableware|kitchenware|dinnerware|plate|cup|bowl|mug|vase|figurine)|'
    r'(?:plate|cup|bowl|mug|vase|figurine)\s*(?:ceramic|porcelain|china)|'
    r'ornamental\s*(?:ceramic|porcelain|china))',
    re.IGNORECASE
)
_CH69_GENERAL = re.compile(
    r'(?:ceramic|porcelain|china|earthenware|stoneware|terracotta|'
    r'refractory|fire.?brick|sanitary\s*ware)',
    re.IGNORECASE
)


def _is_chapter_69_candidate(text):
    return bool(
        _CH69_REFRACTORY.search(text) or _CH69_TILE.search(text)
        or _CH69_BRICK.search(text) or _CH69_SANITARY.search(text)
        or _CH69_TABLEWARE.search(text) or _CH69_GENERAL.search(text)
    )


def _decide_chapter_69(product):
    """Chapter 69: Ceramic products.

    Headings:
        69.01 — Bricks, blocks, tiles of siliceous fossil meals or earths
        69.02 — Refractory bricks, blocks, tiles (other than siliceous)
        69.03 — Other refractory ceramic goods (retorts, crucibles, muffles, nozzles)
        69.04 — Ceramic building bricks, flooring blocks, support/filler tiles
        69.05 — Roofing tiles, chimney-pots, cowls, chimney liners, ornamental ceramics
        69.06 — Ceramic pipes, conduits, guttering and pipe fittings
        69.07 — Unglazed ceramic flags and paving, hearth or wall tiles; mosaic cubes
        69.08 — Glazed ceramic flags and paving, hearth or wall tiles; mosaic cubes
        69.09 — Ceramic wares for laboratory, chemical or other technical uses
        69.10 — Ceramic sinks, wash basins, baths, bidets, toilets (sanitary ware)
        69.11 — Tableware, kitchenware of porcelain or china
        69.12 — Ceramic tableware, kitchenware (other than porcelain)
        69.13 — Statuettes, ornamental ceramic articles
        69.14 — Other ceramic articles
    """
    text = _product_text(product)
    result = {"chapter": 69, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH69_REFRACTORY.search(text):
        if re.search(r'(?:retort|crucible|muffle|nozzle|saggar|kiln\s*furniture)', text, re.IGNORECASE):
            heading = "69.03"
        else:
            heading = "69.02"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.85, "reasoning": f"Refractory ceramic → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result
    if _CH69_SANITARY.search(text):
        result["candidates"].append({"heading": "69.10", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Ceramic sanitary ware (toilet/basin/bath) → 69.10.",
            "rule_applied": "GIR 1 — heading 69.10"})
        return result
    if _CH69_TILE.search(text):
        if re.search(r'(?:glazed|מזוגג)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "69.08", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Glazed ceramic tile → 69.08.",
                "rule_applied": "GIR 1 — heading 69.08"})
        else:
            result["candidates"].append({"heading": "69.07", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Ceramic floor/wall tile → 69.07.",
                "rule_applied": "GIR 1 — heading 69.07"})
        return result
    if _CH69_TABLEWARE.search(text):
        if re.search(r'(?:porcelain|china|פורצלן|חרסינה)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "69.11", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Porcelain/china tableware → 69.11.",
                "rule_applied": "GIR 1 — heading 69.11"})
        elif re.search(r'(?:figurine|statuette|ornament|פסלון|קישוט)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "69.13", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Ceramic ornamental figurine/statuette → 69.13.",
                "rule_applied": "GIR 1 — heading 69.13"})
        else:
            result["candidates"].append({"heading": "69.12", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Ceramic tableware (not porcelain) → 69.12.",
                "rule_applied": "GIR 1 — heading 69.12"})
        return result
    if _CH69_BRICK.search(text):
        if re.search(r'(?:roofing|chimney|גג)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "69.05", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Roofing tile / chimney pot → 69.05.",
                "rule_applied": "GIR 1 — heading 69.05"})
        elif re.search(r'(?:pipe|conduit|gutter|צינור)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "69.06", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Ceramic pipe / conduit → 69.06.",
                "rule_applied": "GIR 1 — heading 69.06"})
        else:
            result["candidates"].append({"heading": "69.04", "subheading_hint": None,
                "confidence": 0.80, "reasoning": "Ceramic building brick / block → 69.04.",
                "rule_applied": "GIR 1 — heading 69.04"})
        return result

    result["candidates"].append({"heading": "69.14", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Ceramic product type unclear → 69.14.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Refractory, tile, brick, sanitary ware, tableware, or ornamental?")
    return result


# ============================================================================
# CHAPTER 70: Glass and glassware
# ============================================================================

_CH70_SHEET = re.compile(
    r'(?:זכוכית\s*(?:שטוחה|לוח|גיליון)|flat\s*glass|sheet\s*glass|plate\s*glass|'
    r'float\s*glass|drawn\s*glass|rolled\s*glass|cast\s*glass)',
    re.IGNORECASE
)
_CH70_SAFETY = re.compile(
    r'(?:זכוכית\s*(?:בטיחות|מחוסמת|למינציה)|safety\s*glass|tempered\s*glass|'
    r'toughened\s*glass|laminated\s*glass|windscreen|windshield)',
    re.IGNORECASE
)
_CH70_MIRROR = re.compile(
    r'(?:מראה|mirror|looking.?glass|rear.?view\s*mirror)',
    re.IGNORECASE
)
_CH70_BOTTLE = re.compile(
    r'(?:בקבוק\s*זכוכית|צנצנת\s*זכוכית|glass\s*(?:bottle|jar|flask|ampoule|vial)|'
    r'carboy|demijohn)',
    re.IGNORECASE
)
_CH70_FIBRE = re.compile(
    r'(?:סיבי?\s*זכוכית|glass\s*fibre|fiberglass|fibreglass|'
    r'glass\s*wool|glass\s*mat|glass\s*roving|chopped\s*strand)',
    re.IGNORECASE
)
_CH70_GLASSWARE = re.compile(
    r'(?:כלי\s*זכוכית|glassware|drinking\s*glass|tumbler|goblet|'
    r'wine\s*glass|glass\s*(?:cup|mug|bowl|plate|dish|vase)|crystal(?:ware)?)',
    re.IGNORECASE
)
_CH70_GENERAL = re.compile(
    r'(?:זכוכית|glass|glassware|mirror|fiberglass|fibreglass)',
    re.IGNORECASE
)


def _is_chapter_70_candidate(text):
    return bool(
        _CH70_SHEET.search(text) or _CH70_SAFETY.search(text)
        or _CH70_MIRROR.search(text) or _CH70_BOTTLE.search(text)
        or _CH70_FIBRE.search(text) or _CH70_GLASSWARE.search(text)
        or _CH70_GENERAL.search(text)
    )


def _decide_chapter_70(product):
    """Chapter 70: Glass and glassware.

    Headings:
        70.01 — Cullet and other waste/scrap of glass; glass in the mass
        70.02 — Glass in balls (not microspheres), rods, tubes, unworked
        70.03 — Cast glass and rolled glass, in sheets
        70.04 — Drawn glass and blown glass, in sheets
        70.05 — Float glass and surface ground/polished glass, in sheets
        70.06 — Glass of 70.03-70.05, bent/edge-worked/engraved/drilled/enamelled
        70.07 — Safety glass (tempered or laminated)
        70.08 — Multiple-walled insulating units of glass
        70.09 — Glass mirrors (framed or unframed, rear-view mirrors)
        70.10 — Carboys, bottles, jars, pots, ampoules, of glass (for packing)
        70.11 — Glass envelopes for electric lamps, cathode-ray tubes
        70.12 — Glass inners for vacuum flasks or other vacuum vessels
        70.13 — Glassware for table, kitchen, toilet, office, indoor decoration
        70.14 — Signalling glassware and optical elements (not optically worked)
        70.15 — Clock or watch glasses; glasses for non-corrective spectacles
        70.16 — Paving blocks, tiles, bricks of pressed/moulded glass; glass cubes for mosaics
        70.17 — Laboratory/hygienic/pharmaceutical glassware
        70.18 — Glass beads, imitation pearls, imitation precious stones, glass eyes
        70.19 — Glass fibres (including glass wool) and articles thereof
        70.20 — Other articles of glass
    """
    text = _product_text(product)
    result = {"chapter": 70, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH70_FIBRE.search(text):
        result["candidates"].append({"heading": "70.19", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Glass fibre / fiberglass / glass wool → 70.19.",
            "rule_applied": "GIR 1 — heading 70.19"})
        return result
    if _CH70_SAFETY.search(text):
        result["candidates"].append({"heading": "70.07", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Safety glass (tempered/laminated) → 70.07.",
            "rule_applied": "GIR 1 — heading 70.07"})
        return result
    if _CH70_MIRROR.search(text):
        result["candidates"].append({"heading": "70.09", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Glass mirror → 70.09.",
            "rule_applied": "GIR 1 — heading 70.09"})
        return result
    if _CH70_BOTTLE.search(text):
        result["candidates"].append({"heading": "70.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Glass bottle / jar / ampoule → 70.10.",
            "rule_applied": "GIR 1 — heading 70.10"})
        return result
    if _CH70_GLASSWARE.search(text):
        result["candidates"].append({"heading": "70.13", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Glassware for table / kitchen / decoration → 70.13.",
            "rule_applied": "GIR 1 — heading 70.13"})
        return result
    if _CH70_SHEET.search(text):
        if re.search(r'(?:float|surface\s*ground|polished)', text, re.IGNORECASE):
            heading = "70.05"
        elif re.search(r'(?:drawn|blown)', text, re.IGNORECASE):
            heading = "70.04"
        else:
            heading = "70.03"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Sheet glass → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    result["candidates"].append({"heading": "70.20", "subheading_hint": None,
        "confidence": 0.55, "reasoning": "Glass product type unclear → 70.20.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Sheet/flat, safety, mirror, bottle, fibre, or glassware?")
    return result


# ============================================================================
# CHAPTER 71: Natural/cultured pearls, precious stones, precious metals, jewellery, coins
# ============================================================================

_CH71_DIAMOND = re.compile(
    r'(?:יהלום|diamond|brilliant\s*cut|rough\s*diamond|industrial\s*diamond)',
    re.IGNORECASE
)
_CH71_GEMSTONE = re.compile(
    r'(?:אבן\s*(?:חן|יקרה)|gemstone|precious\s*stone|semi.?precious|'
    r'ruby|sapphire|emerald|opal|topaz|garnet|amethyst|'
    r'aquamarine|tourmaline|jade|lapis\s*lazuli)',
    re.IGNORECASE
)
_CH71_PEARL = re.compile(
    r'(?:פנינה|pearl|cultured\s*pearl|natural\s*pearl)',
    re.IGNORECASE
)
_CH71_GOLD = re.compile(
    r'(?:זהב|gold|unwrought\s*gold|gold\s*(?:bar|ingot|powder|coin|bullion))',
    re.IGNORECASE
)
_CH71_SILVER = re.compile(
    r'(?:כסף(?!\s*(?:כיס|ון))|silver|unwrought\s*silver|silver\s*(?:bar|ingot|powder|coin|bullion))',
    re.IGNORECASE
)
_CH71_PLATINUM = re.compile(
    r'(?:פלטינה|platinum|palladium|rhodium|iridium|osmium|ruthenium)',
    re.IGNORECASE
)
_CH71_JEWELLERY = re.compile(
    r'(?:תכשיט|jewellery|jewelry|necklace|bracelet|ring\s*(?:gold|silver|precious)|'
    r'earring|pendant|brooch|charm|bangle|choker|cufflink)',
    re.IGNORECASE
)
_CH71_COIN = re.compile(
    r'(?:מטבע|coin|numismatic|gold\s*coin|silver\s*coin|commemorative\s*coin)',
    re.IGNORECASE
)
_CH71_GENERAL = re.compile(
    r'(?:diamond|gemstone|pearl|gold|silver|platinum|jewellery|jewelry|coin)',
    re.IGNORECASE
)


def _is_chapter_71_candidate(text):
    return bool(
        _CH71_DIAMOND.search(text) or _CH71_GEMSTONE.search(text)
        or _CH71_PEARL.search(text) or _CH71_GOLD.search(text)
        or _CH71_SILVER.search(text) or _CH71_PLATINUM.search(text)
        or _CH71_JEWELLERY.search(text) or _CH71_COIN.search(text)
    )


def _decide_chapter_71(product):
    """Chapter 71: Natural/cultured pearls, precious/semi-precious stones, precious metals, jewellery, coins.

    Headings:
        71.01 — Natural/cultured pearls
        71.02 — Diamonds
        71.03 — Precious stones (other than diamonds) and semi-precious stones
        71.04 — Synthetic/reconstructed precious or semi-precious stones
        71.05 — Dust and powder of natural/synthetic precious stones
        71.06 — Silver (unwrought, semi-manufactured, in powder form)
        71.07 — Base metals clad with silver
        71.08 — Gold (unwrought, semi-manufactured, in powder form)
        71.09 — Base metals or silver clad with gold
        71.10 — Platinum (unwrought, semi-manufactured, in powder form)
        71.11 — Base metals, silver or gold clad with platinum
        71.12 — Waste and scrap of precious metal or metal clad with precious metal
        71.13 — Articles of jewellery of precious metal or clad
        71.14 — Articles of goldsmiths'/silversmiths' wares
        71.15 — Other articles of precious metal or clad
        71.16 — Articles of natural/cultured pearls, precious/semi-precious stones
        71.17 — Imitation jewellery
        71.18 — Coin
    """
    text = _product_text(product)
    result = {"chapter": 71, "candidates": [], "redirect": None, "questions_needed": []}

    if _CH71_COIN.search(text):
        result["candidates"].append({"heading": "71.18", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Coin (gold/silver/commemorative) → 71.18.",
            "rule_applied": "GIR 1 — heading 71.18"})
        return result
    if _CH71_JEWELLERY.search(text):
        if re.search(r'(?:imitation|costume|fashion\s*jewel|חיקוי)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "71.17", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Imitation / costume jewellery → 71.17.",
                "rule_applied": "GIR 1 — heading 71.17"})
        else:
            result["candidates"].append({"heading": "71.13", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Jewellery of precious metal → 71.13.",
                "rule_applied": "GIR 1 — heading 71.13"})
        return result
    if _CH71_DIAMOND.search(text):
        result["candidates"].append({"heading": "71.02", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Diamond (rough/cut/industrial) → 71.02.",
            "rule_applied": "GIR 1 — heading 71.02"})
        return result
    if _CH71_PEARL.search(text):
        result["candidates"].append({"heading": "71.01", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Natural / cultured pearl → 71.01.",
            "rule_applied": "GIR 1 — heading 71.01"})
        return result
    if _CH71_GEMSTONE.search(text):
        if re.search(r'(?:synthetic|reconstructed|lab.?(?:grown|created)|סינתטי)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "71.04", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Synthetic / reconstructed precious stone → 71.04.",
                "rule_applied": "GIR 1 — heading 71.04"})
        else:
            result["candidates"].append({"heading": "71.03", "subheading_hint": None,
                "confidence": 0.85, "reasoning": "Precious / semi-precious stone → 71.03.",
                "rule_applied": "GIR 1 — heading 71.03"})
        return result
    if _CH71_GOLD.search(text):
        result["candidates"].append({"heading": "71.08", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Gold (unwrought/semi-manufactured/powder) → 71.08.",
            "rule_applied": "GIR 1 — heading 71.08"})
        return result
    if _CH71_SILVER.search(text):
        result["candidates"].append({"heading": "71.06", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Silver (unwrought/semi-manufactured/powder) → 71.06.",
            "rule_applied": "GIR 1 — heading 71.06"})
        return result
    if _CH71_PLATINUM.search(text):
        result["candidates"].append({"heading": "71.10", "subheading_hint": None,
            "confidence": 0.85, "reasoning": "Platinum group metal → 71.10.",
            "rule_applied": "GIR 1 — heading 71.10"})
        return result

    result["candidates"].append({"heading": "71.13", "subheading_hint": None,
        "confidence": 0.50, "reasoning": "Precious metal / stone type unclear → 71.13.",
        "rule_applied": "GIR 1"})
    result["questions_needed"].append("Diamond, gemstone, pearl, gold, silver, platinum, jewellery, or coin?")
    return result


# ============================================================================
# CHAPTER 72: Iron and steel
# ============================================================================

_CH72_PIG_IRON = re.compile(
    r'(?:ברזל\s*(?:גולמי|יצוק)|pig\s*iron|cast\s*iron\s*(?:ingot|block)|'
    r'spiegeleisen|ferro.?alloy|ferro.?manganese|ferro.?silicon|'
    r'ferro.?chromium|ferro.?nickel)',
    re.IGNORECASE
)
_CH72_STAINLESS = re.compile(
    r'(?:פלדת?\s*(?:אל.?חלד|נירוסטה)|stainless\s*steel|inox|AISI\s*3[01]\d|'
    r'(?:304|316|321|430|201)\s*(?:stainless|steel)|18.?8\s*steel|'
    r'austenitic\s*steel|ferritic\s*steel|martensitic\s*steel)',
    re.IGNORECASE
)
_CH72_ALLOY = re.compile(
    r'(?:פלדת?\s*(?:סגסוגת|מיוחדת)|alloy\s*steel|high\s*speed\s*steel|'
    r'tool\s*steel|silicon.?electrical\s*steel|bearing\s*steel|'
    r'HSLA|high\s*strength\s*low\s*alloy)',
    re.IGNORECASE
)
_CH72_FLAT = re.compile(
    r'(?:פח|גיליון\s*(?:פלדה|ברזל)|flat.?rolled|steel\s*(?:sheet|plate|strip|coil)|'
    r'hot.?rolled\s*(?:coil|sheet|plate)|cold.?rolled\s*(?:coil|sheet|strip)|'
    r'galvanized\s*(?:sheet|coil|steel)|tinplate|tin\s*plate|'
    r'electrolytic\s*tinplate|tin\s*free\s*steel)',
    re.IGNORECASE
)
_CH72_BAR_ROD = re.compile(
    r'(?:מוט\s*(?:פלדה|ברזל)|bar\s*(?:steel|iron)|rod\s*(?:steel|iron)|'
    r'wire\s*rod|rebar|reinforcing\s*(?:bar|steel)|round\s*bar|'
    r'deformed\s*bar|bright\s*bar)',
    re.IGNORECASE
)
_CH72_WIRE = re.compile(
    r'(?:חוט\s*(?:פלדה|ברזל)|steel\s*wire|iron\s*wire|'
    r'wire\s*(?:of\s*)?(?:iron|steel)|barbed\s*wire|'
    r'galvanized\s*wire|spring\s*wire|piano\s*wire)',
    re.IGNORECASE
)
_CH72_ANGLE = re.compile(
    r'(?:פרופיל\s*(?:פלדה|ברזל)|angle\s*(?:iron|steel)|'
    r'shape\s*(?:iron|steel)|section\s*(?:iron|steel)|'
    r'(?:H|I|U|L|T).?beam|channel\s*(?:iron|steel)|'
    r'structural\s*(?:steel|section))',
    re.IGNORECASE
)
_CH72_TUBE = re.compile(
    r'(?:צינור\s*(?:פלדה|ברזל)|steel\s*(?:tube|pipe)|iron\s*(?:tube|pipe)|'
    r'seamless\s*(?:tube|pipe)|welded\s*(?:tube|pipe)|'
    r'line\s*pipe|casing\s*(?:pipe|tube)|tubing\s*(?:steel|iron))',
    re.IGNORECASE
)
_CH72_INGOT = re.compile(
    r'(?:אינגוט\s*פלדה|steel\s*(?:ingot|billet|bloom|slab)|'
    r'semi.?finished\s*(?:steel|iron)|continuously\s*cast)',
    re.IGNORECASE
)
_CH72_WASTE = re.compile(
    r'(?:גרוטאות?\s*(?:פלדה|ברזל)|scrap\s*(?:iron|steel)|waste\s*(?:iron|steel)|'
    r'remelting\s*(?:scrap|ingot)|iron\s*scrap|steel\s*scrap)',
    re.IGNORECASE
)
_CH72_GENERAL = re.compile(
    r'(?:פלדה|ברזל|steel|iron|stainless|ferro)',
    re.IGNORECASE
)


def _is_chapter_72_candidate(text):
    return bool(
        _CH72_PIG_IRON.search(text) or _CH72_STAINLESS.search(text)
        or _CH72_ALLOY.search(text) or _CH72_FLAT.search(text)
        or _CH72_BAR_ROD.search(text) or _CH72_WIRE.search(text)
        or _CH72_ANGLE.search(text) or _CH72_TUBE.search(text)
        or _CH72_GENERAL.search(text)
    )


def _decide_chapter_72(product):
    """Chapter 72: Iron and steel.

    Key structure: Form first (flat/bar/wire/tube/angle), then alloy type (non-alloy/stainless/other alloy).
    Headings:
        72.01 — Pig iron and spiegeleisen
        72.02 — Ferro-alloys
        72.03 — Ferrous products from direct reduction of iron ore (sponge iron)
        72.04 — Ferrous waste and scrap; remelting scrap ingots
        72.05 — Granules and powders of pig iron, spiegeleisen, iron or steel
        72.06 — Iron and non-alloy steel ingots/billets/blooms/slabs
        72.07 — Semi-finished products of iron or non-alloy steel
        72.08-72.12 — Flat-rolled non-alloy steel (hot/cold/coated/tinplate)
        72.13-72.17 — Bars, rods, angles, shapes, sections of non-alloy steel
        72.18-72.23 — Stainless steel (semi-finished/flat/bar/wire/angle)
        72.24-72.29 — Other alloy steel (semi-finished/flat/bar/wire/angle)
    """
    text = _product_text(product)
    result = {"chapter": 72, "candidates": [], "redirect": None, "questions_needed": []}

    is_stainless = bool(_CH72_STAINLESS.search(text))
    is_alloy = bool(_CH72_ALLOY.search(text))

    if _CH72_PIG_IRON.search(text):
        if re.search(r'(?:ferro.?alloy|ferro.?manganese|ferro.?silicon|ferro.?chrom|ferro.?nickel)', text, re.IGNORECASE):
            result["candidates"].append({"heading": "72.02", "subheading_hint": None,
                "confidence": 0.90, "reasoning": "Ferro-alloy → 72.02.",
                "rule_applied": "GIR 1 — heading 72.02"})
        else:
            result["candidates"].append({"heading": "72.01", "subheading_hint": None,
                "confidence": 0.90, "reasoning": "Pig iron / spiegeleisen → 72.01.",
                "rule_applied": "GIR 1 — heading 72.01"})
        return result
    if _CH72_WASTE.search(text):
        result["candidates"].append({"heading": "72.04", "subheading_hint": None,
            "confidence": 0.90, "reasoning": "Iron/steel waste, scrap, remelting ingots → 72.04.",
            "rule_applied": "GIR 1 — heading 72.04"})
        return result

    # WIRE (check before flat — "galvanized wire" should not match flat)
    if _CH72_WIRE.search(text):
        if is_stainless:
            heading = "72.23"
        elif is_alloy:
            heading = "72.29"
        else:
            heading = "72.17"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Steel wire → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # BARS and RODS (check before flat — "rebar" should not match flat)
    if _CH72_BAR_ROD.search(text):
        if is_stainless:
            heading = "72.22"
        elif is_alloy:
            heading = "72.28"
        else:
            if re.search(r'(?:hot.?roll|rebar|reinforc|deformed)', text, re.IGNORECASE):
                heading = "72.13"
            else:
                heading = "72.15"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Steel bars/rods → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # FLAT-ROLLED products
    if _CH72_FLAT.search(text):
        if is_stainless:
            if re.search(r'(?:hot.?roll)', text, re.IGNORECASE):
                heading = "72.19"
            else:
                heading = "72.20"
        elif is_alloy:
            if re.search(r'(?:hot.?roll)', text, re.IGNORECASE):
                heading = "72.25"
            else:
                heading = "72.26"
        else:
            if re.search(r'(?:tinplate|tin\s*plate|tin\s*free)', text, re.IGNORECASE):
                heading = "72.10"
            elif re.search(r'(?:galvaniz|coat|clad|plat)', text, re.IGNORECASE):
                heading = "72.10"
            elif re.search(r'(?:cold.?roll)', text, re.IGNORECASE):
                heading = "72.09"
            else:
                heading = "72.08"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Flat-rolled steel product → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # ANGLES, SHAPES, SECTIONS
    if _CH72_ANGLE.search(text):
        if is_stainless:
            heading = "72.22"
        elif is_alloy:
            heading = "72.28"
        else:
            heading = "72.16"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Steel angles/shapes/sections → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # SEMI-FINISHED (ingots/billets/blooms/slabs)
    if _CH72_INGOT.search(text):
        if is_stainless:
            heading = "72.18"
        elif is_alloy:
            heading = "72.24"
        else:
            heading = "72.07"
        result["candidates"].append({"heading": heading, "subheading_hint": None,
            "confidence": 0.80, "reasoning": f"Semi-finished steel → {heading}.",
            "rule_applied": f"GIR 1 — heading {heading}"})
        return result

    # Generic stainless/alloy/non-alloy
    if is_stainless:
        result["candidates"].append({"heading": "72.18", "subheading_hint": None,
            "confidence": 0.60, "reasoning": "Stainless steel form unclear → 72.18.",
            "rule_applied": "GIR 1"})
    elif is_alloy:
        result["candidates"].append({"heading": "72.24", "subheading_hint": None,
            "confidence": 0.60, "reasoning": "Alloy steel form unclear → 72.24.",
            "rule_applied": "GIR 1"})
    else:
        result["candidates"].append({"heading": "72.06", "subheading_hint": None,
            "confidence": 0.55, "reasoning": "Iron/steel form unclear → 72.06.",
            "rule_applied": "GIR 1"})
    result["questions_needed"].append("Form: flat/sheet, bar/rod, wire, angle/section, tube/pipe? Stainless, alloy, or non-alloy?")
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
    25: _decide_chapter_25,
    26: _decide_chapter_26,
    27: _decide_chapter_27,
    28: _decide_chapter_28,
    29: _decide_chapter_29,
    30: _decide_chapter_30,
    31: _decide_chapter_31,
    32: _decide_chapter_32,
    33: _decide_chapter_33,
    34: _decide_chapter_34,
    35: _decide_chapter_35,
    36: _decide_chapter_36,
    37: _decide_chapter_37,
    38: _decide_chapter_38,
    39: _decide_chapter_39,
    40: _decide_chapter_40,
    41: _decide_chapter_41,
    42: _decide_chapter_42,
    43: _decide_chapter_43,
    44: _decide_chapter_44,
    45: _decide_chapter_45,
    46: _decide_chapter_46,
    47: _decide_chapter_47,
    48: _decide_chapter_48,
    49: _decide_chapter_49,
    50: _decide_chapter_50,
    51: _decide_chapter_51,
    52: _decide_chapter_52,
    53: _decide_chapter_53,
    54: _decide_chapter_54,
    55: _decide_chapter_55,
    56: _decide_chapter_56,
    57: _decide_chapter_57,
    58: _decide_chapter_58,
    59: _decide_chapter_59,
    60: _decide_chapter_60,
    61: _decide_chapter_61,
    62: _decide_chapter_62,
    63: _decide_chapter_63,
    64: _decide_chapter_64,
    65: _decide_chapter_65,
    66: _decide_chapter_66,
    67: _decide_chapter_67,
    68: _decide_chapter_68,
    69: _decide_chapter_69,
    70: _decide_chapter_70,
    71: _decide_chapter_71,
    72: _decide_chapter_72,
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
# Priority: finished goods before raw materials to prevent substring collisions.
# Food/agri (1-24) → finished textiles/apparel (56-65) → stone/ceramic (66-72)
# → leather/wood/paper (41-49) → plastics/rubber (39-40) → chemicals (28-38)
# → raw textiles (50-55) → minerals (25-27).
_CHAPTER_DETECT_ORDER = [
    # --- Food / agriculture (very specific names, low false-positive) ---
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
    # --- Wigs/feathers (ch.67) before textiles (lace wig ≠ lace fabric) ---
    (67, _is_chapter_67_candidate, _decide_chapter_67),
    # --- Finished textiles / apparel / footwear (before raw materials) ---
    (64, _is_chapter_64_candidate, _decide_chapter_64),
    (65, _is_chapter_65_candidate, _decide_chapter_65),
    (61, _is_chapter_61_candidate, _decide_chapter_61),
    (62, _is_chapter_62_candidate, _decide_chapter_62),
    (63, _is_chapter_63_candidate, _decide_chapter_63),
    (57, _is_chapter_57_candidate, _decide_chapter_57),
    (58, _is_chapter_58_candidate, _decide_chapter_58),
    (59, _is_chapter_59_candidate, _decide_chapter_59),
    (60, _is_chapter_60_candidate, _decide_chapter_60),
    (56, _is_chapter_56_candidate, _decide_chapter_56),
    # --- Minerals / ores (before metals — "iron ore" is ch.26 not ch.72) ---
    (25, _is_chapter_25_candidate, _decide_chapter_25),
    (26, _is_chapter_26_candidate, _decide_chapter_26),
    (27, _is_chapter_27_candidate, _decide_chapter_27),
    # --- Stone / ceramic / glass / metals ---
    (66, _is_chapter_66_candidate, _decide_chapter_66),
    (68, _is_chapter_68_candidate, _decide_chapter_68),
    (69, _is_chapter_69_candidate, _decide_chapter_69),
    (70, _is_chapter_70_candidate, _decide_chapter_70),
    (71, _is_chapter_71_candidate, _decide_chapter_71),
    (72, _is_chapter_72_candidate, _decide_chapter_72),
    # --- Leather / wood / paper (finished articles) ---
    (41, _is_chapter_41_candidate, _decide_chapter_41),
    (42, _is_chapter_42_candidate, _decide_chapter_42),
    (43, _is_chapter_43_candidate, _decide_chapter_43),
    (44, _is_chapter_44_candidate, _decide_chapter_44),
    (45, _is_chapter_45_candidate, _decide_chapter_45),
    (46, _is_chapter_46_candidate, _decide_chapter_46),
    (47, _is_chapter_47_candidate, _decide_chapter_47),
    (48, _is_chapter_48_candidate, _decide_chapter_48),
    (49, _is_chapter_49_candidate, _decide_chapter_49),
    # --- Chemicals (paints ch.32 before plastics ch.39 — acrylic paint ≠ acrylic plastic) ---
    (28, _is_chapter_28_candidate, _decide_chapter_28),
    (29, _is_chapter_29_candidate, _decide_chapter_29),
    (30, _is_chapter_30_candidate, _decide_chapter_30),
    (31, _is_chapter_31_candidate, _decide_chapter_31),
    (32, _is_chapter_32_candidate, _decide_chapter_32),
    (33, _is_chapter_33_candidate, _decide_chapter_33),
    (34, _is_chapter_34_candidate, _decide_chapter_34),
    (35, _is_chapter_35_candidate, _decide_chapter_35),
    (36, _is_chapter_36_candidate, _decide_chapter_36),
    (37, _is_chapter_37_candidate, _decide_chapter_37),
    (38, _is_chapter_38_candidate, _decide_chapter_38),
    # --- Plastics / rubber (after paints/chemicals) ---
    (39, _is_chapter_39_candidate, _decide_chapter_39),
    (40, _is_chapter_40_candidate, _decide_chapter_40),
    # --- Raw textiles (after finished textiles and chemicals) ---
    (50, _is_chapter_50_candidate, _decide_chapter_50),
    (51, _is_chapter_51_candidate, _decide_chapter_51),
    (52, _is_chapter_52_candidate, _decide_chapter_52),
    (53, _is_chapter_53_candidate, _decide_chapter_53),
    (54, _is_chapter_54_candidate, _decide_chapter_54),
    (55, _is_chapter_55_candidate, _decide_chapter_55),
]


def available_chapters():
    """Return list of chapter numbers that have decision trees."""
    return sorted(_CHAPTER_TREES.keys())
