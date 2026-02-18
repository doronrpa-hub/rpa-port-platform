"""
Verification Engine — Block E: Phases 4-6 + Proactive Flagging

Session 34 Block E: Post-classification verification.
- Phase 4: Bilingual verification (HE<>EN description cross-check)
- Phase 5: Post-classification knowledge verification (directives, framework, chapter notes, elimination conflict)
- Phase 6: Regulatory checks — SKIPPED (already done via C3+C4)
- Proactive Flagging: Structured per-item flags (permits, standards, antidumping, FTA, conflicts)

Cost: ~$0.00-0.001 per classification (mostly free Firestore reads + keyword matching).
"""

import re

# ---------------------------------------------------------------------------
# Reuse patterns from elimination_engine.py
# ---------------------------------------------------------------------------

_HE_PREFIX_RE = re.compile(r'^[מבלהוכש]')

_STOP_WORDS = {
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "new",
    "used", "set", "pcs", "piece", "pieces", "item", "items", "type",
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
}

_WORD_SPLIT_RE = re.compile(r'[^\w\u0590-\u05FF]+')

# ---------------------------------------------------------------------------
# Permit authorities — from Free Import Order (C3) authority names
# ---------------------------------------------------------------------------

_PERMIT_AUTHORITIES = {
    "משרד הבריאות", "משרד החקלאות", "משרד התחבורה", "משרד הכלכלה",
    "משרד התקשורת", "משרד האנרגיה", "משרד הפנים", "המשרד להגנת הסביבה",
    "רשות שוק ההון", "רשות התקשוב", "משטרת ישראל", "משרד הביטחון",
    "רשות מקרקעי ישראל", "הרשות לניירות ערך",
    "Ministry of Health", "Ministry of Agriculture", "Ministry of Transport",
    "Ministry of Economy", "Ministry of Communications", "Ministry of Energy",
    "Ministry of Interior", "Ministry of Environmental Protection",
    "Israel Police", "Ministry of Defense",
}

# ---------------------------------------------------------------------------
# Antidumping heuristic — chapters + origins with known measures
# ---------------------------------------------------------------------------

_ANTIDUMPING_CHAPTERS = {"72", "73"}  # Iron and steel
_ANTIDUMPING_ORIGINS = {"cn", "china", "tr", "turkey", "in", "india", "סין", "טורקיה", "הודו"}


# =============================================================================
# KEYWORD EXTRACTION (same logic as elimination_engine.py:210)
# =============================================================================

def _extract_keywords(text, limit=15):
    """Extract meaningful keywords from text. Bilingual (Hebrew + English).
    Hebrew prefix-stripped variants included."""
    if not text:
        return []
    words = _WORD_SPLIT_RE.split(text.lower())
    keywords = [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
    extra = []
    for w in keywords:
        if len(w) > 3 and '\u0590' <= w[0] <= '\u05FF':
            stripped = _HE_PREFIX_RE.sub('', w)
            if stripped and len(stripped) > 2 and stripped != w and stripped not in _STOP_WORDS:
                extra.append(stripped)
    keywords.extend(extra)
    seen = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:limit]


# =============================================================================
# HS UTILITIES
# =============================================================================

def _clean_hs(hs_code):
    """Strip dots/slashes/spaces from HS code string."""
    return str(hs_code).replace(".", "").replace("/", "").replace(" ", "").strip()


def _chapter_from_hs(hs_code):
    """Extract 2-digit zero-padded chapter from HS code."""
    clean = _clean_hs(hs_code)
    if not clean:
        return ""
    return clean[:2].zfill(2)


# =============================================================================
# BILINGUAL KEYWORD OVERLAP SCORER
# =============================================================================

def _score_bilingual(product_desc, official_desc):
    """Score product description keywords against an official description.

    Returns float 0.0-1.0 (Jaccard-like ratio using smaller keyword set).
    Handles Hebrew prefix stripping for better matching.
    """
    if not product_desc or not official_desc:
        return 0.0
    kw_product = set(_extract_keywords(product_desc, limit=20))
    kw_official = set(_extract_keywords(official_desc, limit=30))
    if not kw_product or not kw_official:
        return 0.0
    overlap = kw_product & kw_official
    smaller = min(len(kw_product), len(kw_official))
    return len(overlap) / smaller if smaller > 0 else 0.0


# =============================================================================
# COLLECTION LOADERS (lazy-load, same pattern as tool_executors.py:87)
# =============================================================================

_cached_directives = None
_cached_framework_order = None


def _load_directives(db):
    """Load all classification_directives docs. Cached for module lifetime."""
    global _cached_directives
    if _cached_directives is not None:
        return _cached_directives
    try:
        _cached_directives = [
            (doc.id, doc.to_dict())
            for doc in db.collection("classification_directives").stream()
        ]
    except Exception as e:
        print(f"    [VE] Failed to load directives: {e}")
        _cached_directives = []
    return _cached_directives


def _load_framework_order(db):
    """Load all framework_order docs. Cached for module lifetime."""
    global _cached_framework_order
    if _cached_framework_order is not None:
        return _cached_framework_order
    try:
        _cached_framework_order = [
            (doc.id, doc.to_dict())
            for doc in db.collection("framework_order").stream()
        ]
    except Exception as e:
        print(f"    [VE] Failed to load framework order: {e}")
        _cached_framework_order = []
    return _cached_framework_order


def _reset_caches():
    """Reset module-level caches (for testing)."""
    global _cached_directives, _cached_framework_order
    _cached_directives = None
    _cached_framework_order = None


# =============================================================================
# PHASE 4 — BILINGUAL VERIFICATION
# =============================================================================

def _run_phase4(cls_item, db=None, api_key=None, gemini_key=None):
    """Phase 4: Bilingual verification — cross-check HE and EN descriptions
    against the product description.

    Args:
        cls_item: Classification dict with hs_code, item, official_description_he/en
        db: Firestore client (for UK tariff lookup)
        api_key: Anthropic API key (fallback)
        gemini_key: Gemini API key (for mismatch AI check)

    Returns:
        dict with bilingual_match, he_match_score, en_match_score, etc.
    """
    result = {
        "bilingual_match": True,
        "he_match_score": 0.0,
        "en_match_score": 0.0,
        "mismatch_details": "",
        "ai_consulted": False,
        "en_source": "classification",
    }

    product_desc = cls_item.get("item", "") or cls_item.get("description", "")
    desc_he = cls_item.get("official_description_he", "")
    desc_en = cls_item.get("official_description_en", "")
    hs_code = cls_item.get("hs_code", "")

    if not product_desc:
        return result

    # If EN is empty -> try UK tariff API (free, cached 7 days)
    if not desc_en and hs_code and db:
        try:
            from lib.uk_tariff_integration import lookup_uk_tariff
            uk_data = lookup_uk_tariff(db, hs_code)
            if uk_data and uk_data.get("found"):
                desc_en = uk_data.get("description", "") or uk_data.get("formatted_description", "")
                if desc_en:
                    result["en_source"] = "uk_tariff"
        except Exception:
            pass

    # Score product keywords against HE and EN descriptions
    he_score = _score_bilingual(product_desc, desc_he) if desc_he else 0.0
    en_score = _score_bilingual(product_desc, desc_en) if desc_en else 0.0

    result["he_match_score"] = round(he_score, 3)
    result["en_match_score"] = round(en_score, 3)

    threshold = 0.25

    # If both scores above threshold -> match, no AI needed
    if he_score >= threshold and en_score >= threshold:
        result["bilingual_match"] = True
        return result

    # If we only have one language and it's above threshold -> accept
    if not desc_he and en_score >= threshold:
        result["bilingual_match"] = True
        return result
    if not desc_en and he_score >= threshold:
        result["bilingual_match"] = True
        return result

    # If either score below threshold -> consult AI with minimal prompt
    if gemini_key or api_key:
        try:
            from lib.classification_agents import call_ai
            prompt = (
                f"Product: {product_desc[:200]}\n"
                f"HS Code: {hs_code}\n"
                f"HE description: {desc_he[:200]}\n"
                f"EN description: {desc_en[:200]}\n\n"
                f"Does this product match this HS code description? Answer YES or NO only."
            )
            ai_result = call_ai(
                api_key, gemini_key,
                "You are a customs classification verifier. Answer YES or NO only.",
                prompt, max_tokens=10, tier="fast"
            )
            result["ai_consulted"] = True
            if ai_result and "yes" in ai_result.lower():
                result["bilingual_match"] = True
                return result
            elif ai_result and "no" in ai_result.lower():
                result["bilingual_match"] = False
                result["mismatch_details"] = (
                    f"AI detected mismatch: product '{product_desc[:80]}' "
                    f"vs HS {hs_code} descriptions"
                )
                return result
        except Exception:
            pass

    # Fallback: use best available score
    best_score = max(he_score, en_score)
    result["bilingual_match"] = best_score >= threshold
    if best_score < threshold:
        result["mismatch_details"] = (
            f"Low keyword overlap: HE={he_score:.2f}, EN={en_score:.2f} (threshold={threshold})"
        )
    return result


# =============================================================================
# PHASE 5 — POST-CLASSIFICATION KNOWLEDGE VERIFICATION
# =============================================================================

def _run_phase5(cls_item, db, elimination_results=None):
    """Phase 5: Post-classification knowledge verification.

    Checks classified HS code against:
    1. Classification directives (218 cached docs)
    2. Framework order definitions (85 cached docs)
    3. Chapter exclusion notes (Firestore)
    4. Elimination engine conflict (was this code eliminated?)

    Returns:
        dict with verified, confidence_adjustment, conflicts, etc.
    """
    result = {
        "verified": True,
        "confidence_adjustment": 0.0,
        "conflicts": [],
        "directives_found": [],
        "framework_matches": [],
        "chapter_exclusion_hit": False,
        "elimination_conflict": False,
    }

    hs_code = cls_item.get("hs_code", "")
    product_desc = cls_item.get("item", "") or cls_item.get("description", "")
    if not hs_code:
        return result

    chapter = _chapter_from_hs(hs_code)
    hs_clean = _clean_hs(hs_code)
    adj = 0.0

    # ── 1. Directives check ──
    if db:
        try:
            directives = _load_directives(db)
            for doc_id, data in directives:
                if not data:
                    continue
                primary = _clean_hs(data.get("primary_hs_code", "") or "")
                hs_mentioned = data.get("hs_codes_mentioned", [])
                related = data.get("related_hs_codes", [])
                title = data.get("title", "") or ""

                match = False
                # Check if directive references this HS code
                if primary and hs_clean[:4] == primary[:4]:
                    match = True
                if not match:
                    for h in hs_mentioned + related:
                        h_clean = _clean_hs(str(h))
                        if h_clean and hs_clean[:4] == h_clean[:4]:
                            match = True
                            break

                if match:
                    directive_info = {
                        "directive_id": data.get("directive_id", doc_id),
                        "title": title[:120],
                        "is_active": data.get("is_active", True),
                    }
                    result["directives_found"].append(directive_info)

                    # Check if directive content supports or conflicts
                    content = (data.get("content", "") or "").lower()
                    product_kw = set(_extract_keywords(product_desc, limit=10))
                    content_kw = set(_extract_keywords(content, limit=30))
                    if product_kw and content_kw:
                        overlap = product_kw & content_kw
                        if len(overlap) >= 2:
                            adj += 0.05  # Supporting directive
                        # Check for explicit conflict indicators
                        if any(w in content for w in ["אינו כולל", "לא יסווג", "exclud", "not classif"]):
                            if any(kw in content for kw in product_kw):
                                result["conflicts"].append(
                                    f"Directive {directive_info['directive_id']} may exclude this product"
                                )
                                adj -= 0.10
        except Exception as e:
            print(f"    [VE] Directives check error: {e}")

    # ── 2. Framework definitions check ──
    if db:
        try:
            framework_docs = _load_framework_order(db)
            for doc_id, data in framework_docs:
                if not data:
                    continue
                doc_type = data.get("type", "")
                if doc_type != "definition":
                    continue
                term = (data.get("term", "") or "").lower()
                definition_text = (data.get("definition", "") or data.get("content", "") or "").lower()
                if not term or len(term) < 3:
                    continue
                # Check if the definition's term appears in the product description
                if term in product_desc.lower():
                    result["framework_matches"].append({
                        "term": data.get("term", ""),
                        "doc_id": doc_id,
                    })
                    adj += 0.05
        except Exception as e:
            print(f"    [VE] Framework check error: {e}")

    # ── 3. Chapter exclusion check ──
    if db and chapter:
        try:
            doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
            if doc.exists:
                notes_data = doc.to_dict()
                exclusions = notes_data.get("exclusions", [])
                product_lower = product_desc.lower()
                for excl in exclusions:
                    excl_text = ""
                    if isinstance(excl, str):
                        excl_text = excl.lower()
                    elif isinstance(excl, dict):
                        excl_text = (excl.get("text", "") or excl.get("description", "") or "").lower()
                    if not excl_text:
                        continue
                    # Check if any product keyword appears in exclusion text
                    product_kw = _extract_keywords(product_desc, limit=10)
                    excl_kw = set(_extract_keywords(excl_text, limit=20))
                    overlap = set(product_kw) & excl_kw
                    if len(overlap) >= 2:
                        result["chapter_exclusion_hit"] = True
                        result["conflicts"].append(
                            f"Chapter {chapter} exclusion may apply: {excl_text[:100]}"
                        )
                        adj -= 0.20
                        break  # One exclusion hit is enough
        except Exception as e:
            print(f"    [VE] Chapter exclusion check error: {e}")

    # ── 4. Elimination conflict check ──
    if elimination_results:
        try:
            # elimination_results is keyed by description or hs_code
            for key, elim_data in elimination_results.items():
                if not isinstance(elim_data, dict):
                    continue
                eliminated_codes = []
                for e in elim_data.get("eliminated", []):
                    if isinstance(e, dict):
                        eliminated_codes.append(_clean_hs(e.get("hs_code", "")))
                    elif isinstance(e, str):
                        eliminated_codes.append(_clean_hs(e))

                survivors = []
                for s in elim_data.get("survivors", []):
                    if isinstance(s, dict):
                        survivors.append(_clean_hs(s.get("hs_code", "")))
                    elif isinstance(s, str):
                        survivors.append(_clean_hs(s))

                # Check if Agent 2 chose an eliminated code
                if hs_clean in eliminated_codes and hs_clean not in survivors:
                    result["elimination_conflict"] = True
                    result["verified"] = False
                    result["conflicts"].append(
                        f"CRITICAL: HS {hs_code} was eliminated by the elimination engine but chosen by Agent 2"
                    )
                    adj -= 0.30
                    break
        except Exception as e:
            print(f"    [VE] Elimination conflict check error: {e}")

    # Cap total adjustment to [-0.30, +0.20]
    adj = max(-0.30, min(0.20, adj))
    result["confidence_adjustment"] = round(adj, 2)

    if result["conflicts"]:
        result["verified"] = False

    return result


# =============================================================================
# PROACTIVE FLAGGING
# =============================================================================

def _generate_flags(cls_item, phase4_result=None, phase5_result=None,
                    free_import_results=None):
    """Generate structured flag dicts for a classified item.

    Flag types: PERMIT, STANDARD, FTA, ANTIDUMPING, ELIMINATION_CONFLICT,
                DIRECTIVE, BILINGUAL_MISMATCH

    Returns: list of flag dicts
    """
    flags = []
    hs_code = cls_item.get("hs_code", "")
    chapter = _chapter_from_hs(hs_code)
    origin = (cls_item.get("origin_country", "") or "").lower()

    # ── 1. PERMIT flag — from FIO authorities ──
    if free_import_results and isinstance(free_import_results, dict):
        fio_data = free_import_results.get(hs_code) or free_import_results.get(_clean_hs(hs_code))
        if isinstance(fio_data, dict):
            authorities = fio_data.get("authorities_summary", [])
            if isinstance(authorities, list):
                for auth in authorities:
                    auth_name = auth if isinstance(auth, str) else str(auth)
                    if auth_name in _PERMIT_AUTHORITIES:
                        flags.append({
                            "type": "PERMIT",
                            "severity": "warning",
                            "message_he": f"נדרש אישור: {auth_name}",
                            "message_en": f"Permit required: {auth_name}",
                            "source": "free_import_order",
                        })

    # ── 2. STANDARD flag — from FIO has_standards ──
    if free_import_results and isinstance(free_import_results, dict):
        fio_data = free_import_results.get(hs_code) or free_import_results.get(_clean_hs(hs_code))
        if isinstance(fio_data, dict):
            if fio_data.get("has_standards"):
                flags.append({
                    "type": "STANDARD",
                    "severity": "warning",
                    "message_he": "נדרשת עמידה בתקן ישראלי",
                    "message_en": "Israeli standard compliance required",
                    "source": "free_import_order",
                })

    # ── 3. FTA flag — from cls.fta.eligible ──
    fta_data = cls_item.get("fta")
    if isinstance(fta_data, dict) and fta_data.get("eligible"):
        agreement = fta_data.get("agreement", fta_data.get("agreement_name", "FTA"))
        flags.append({
            "type": "FTA",
            "severity": "info",
            "message_he": f"זכאי להסכם סחר חופשי: {agreement}",
            "message_en": f"Eligible for FTA: {agreement}",
            "source": "fta_agent",
        })

    # ── 4. ANTIDUMPING flag — chapter+origin heuristic ──
    if chapter in _ANTIDUMPING_CHAPTERS and origin:
        if any(ao in origin for ao in _ANTIDUMPING_ORIGINS):
            flags.append({
                "type": "ANTIDUMPING",
                "severity": "warning",
                "message_he": f"ייתכן היטל היצף על פרק {chapter} ממקור {origin}",
                "message_en": f"Possible antidumping duty for chapter {chapter} from {origin}",
                "source": "heuristic",
            })

    # ── 5. ELIMINATION_CONFLICT flag ──
    if phase5_result and phase5_result.get("elimination_conflict"):
        flags.append({
            "type": "ELIMINATION_CONFLICT",
            "severity": "critical",
            "message_he": f"קוד {hs_code} נפסל ע\"י מנוע האלימינציה אך נבחר ע\"י הסוכן",
            "message_en": f"HS {hs_code} was eliminated by the engine but chosen by Agent 2",
            "source": "elimination_engine",
        })

    # ── 6. DIRECTIVE flag ──
    if phase5_result and phase5_result.get("directives_found"):
        for d in phase5_result["directives_found"][:3]:  # Max 3 directive flags
            flags.append({
                "type": "DIRECTIVE",
                "severity": "info",
                "message_he": f"הנחיית סיווג קיימת: {d.get('title', d.get('directive_id', ''))}",
                "message_en": f"Classification directive exists: {d.get('directive_id', '')}",
                "source": "classification_directives",
            })

    # ── 7. BILINGUAL_MISMATCH flag ──
    if phase4_result and not phase4_result.get("bilingual_match", True):
        details = phase4_result.get("mismatch_details", "")
        flags.append({
            "type": "BILINGUAL_MISMATCH",
            "severity": "warning",
            "message_he": "אי-התאמה בין תיאור המוצר לתיאור הרשמי בעברית/אנגלית",
            "message_en": f"Bilingual description mismatch detected. {details}",
            "source": "phase4_verification",
        })

    return flags


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_verification_engine(
    db, classifications, elimination_results=None,
    free_import_results=None, api_key=None, gemini_key=None
):
    """Run the full verification engine (Phase 4 + Phase 5 + Proactive Flagging).

    Called once per pipeline run, after Agent 2 classifies and verification loop validates.

    Args:
        db: Firestore client
        classifications: list of classification dicts from Agent 2 (validated)
        elimination_results: dict from elimination engine (keyed by description)
        free_import_results: dict from free import order lookup (keyed by HS code)
        api_key: Anthropic API key (for Phase 4 AI fallback)
        gemini_key: Gemini API key (for Phase 4 AI check)

    Returns:
        dict keyed by hs_code with phase4, phase5, flags sub-dicts,
        plus a summary key with aggregate stats.
    """
    if not classifications:
        return {"summary": {"total": 0, "verified": 0, "flagged": 0, "conflicts": 0}}

    # Reset module caches for fresh run
    _reset_caches()

    results = {}
    total = 0
    verified_count = 0
    flagged_count = 0
    conflict_count = 0

    for cls_item in classifications:
        if not isinstance(cls_item, dict):
            continue
        hs_code = cls_item.get("hs_code", "")
        if not hs_code:
            continue

        total += 1
        item_result = {}

        # Phase 4: Bilingual verification
        try:
            phase4 = _run_phase4(cls_item, db=db, api_key=api_key, gemini_key=gemini_key)
            item_result["phase4"] = phase4
        except Exception as e:
            print(f"    [VE] Phase 4 error for {hs_code}: {e}")
            item_result["phase4"] = {"bilingual_match": True, "he_match_score": 0, "en_match_score": 0}
            phase4 = item_result["phase4"]

        # Phase 5: Knowledge verification
        try:
            phase5 = _run_phase5(cls_item, db, elimination_results=elimination_results)
            item_result["phase5"] = phase5
        except Exception as e:
            print(f"    [VE] Phase 5 error for {hs_code}: {e}")
            item_result["phase5"] = {"verified": True, "confidence_adjustment": 0, "conflicts": []}
            phase5 = item_result["phase5"]

        # Proactive Flagging
        try:
            flags = _generate_flags(
                cls_item, phase4_result=phase4, phase5_result=phase5,
                free_import_results=free_import_results,
            )
            item_result["flags"] = flags
        except Exception as e:
            print(f"    [VE] Flagging error for {hs_code}: {e}")
            item_result["flags"] = []
            flags = []

        # Apply UK tariff EN confirmation bonus to Phase 5
        if phase4.get("en_source") == "uk_tariff" and phase4.get("bilingual_match"):
            current_adj = phase5.get("confidence_adjustment", 0)
            phase5["confidence_adjustment"] = round(
                max(-0.30, min(0.20, current_adj + 0.05)), 2
            )

        # Aggregate stats
        if phase5.get("verified", True) and phase4.get("bilingual_match", True):
            verified_count += 1
        if flags:
            flagged_count += 1
        if phase5.get("conflicts"):
            conflict_count += len(phase5["conflicts"])

        results[hs_code] = item_result

    results["summary"] = {
        "total": total,
        "verified": verified_count,
        "flagged": flagged_count,
        "conflicts": conflict_count,
    }

    print(f"    🔍 Verification Engine: {total} items — "
          f"{verified_count} verified, {flagged_count} flagged, {conflict_count} conflicts")

    return results


# =============================================================================
# HTML RENDERER — Email-safe verification badges + proactive flags
# =============================================================================

def build_verification_flags_html(enriched_item):
    """Render bilingual verification badge + proactive flags as email-safe HTML.

    Args:
        enriched_item: dict from _enrich_results_for_email() with ve_flags and ve_phase4

    Returns:
        HTML string or empty string if no flags/verification data
    """
    flags = enriched_item.get("ve_flags", [])
    phase4 = enriched_item.get("ve_phase4", {})

    if not flags and not phase4:
        return ""

    # Color scheme matching existing badges in classification_agents.py
    _SEVERITY_STYLES = {
        "info": "background:#dcfce7;border:1px solid #bbf7d0;color:#166534",
        "warning": "background:#fef3c7;border:1px solid #fde68a;color:#92400e",
        "critical": "background:#fee2e2;border:1px solid #fecaca;color:#991b1b",
    }

    html_parts = []

    # Phase 4 bilingual verification badge
    if phase4:
        match = phase4.get("bilingual_match", True)
        he_score = phase4.get("he_match_score", 0)
        en_score = phase4.get("en_match_score", 0)
        if match:
            style = _SEVERITY_STYLES["info"]
            badge_text = f"✓ אימות דו-לשוני עבר (HE:{he_score:.0%} EN:{en_score:.0%})"
        else:
            style = _SEVERITY_STYLES["warning"]
            badge_text = f"⚠ אי-התאמה דו-לשונית (HE:{he_score:.0%} EN:{en_score:.0%})"
        html_parts.append(
            f'<span style="display:inline-block;{style};border-radius:20px;'
            f'padding:3px 10px;margin:2px;font-size:11px">{badge_text}</span>'
        )

    # Proactive flags
    for flag in flags:
        severity = flag.get("severity", "info")
        style = _SEVERITY_STYLES.get(severity, _SEVERITY_STYLES["info"])
        msg = flag.get("message_he", flag.get("message_en", ""))
        flag_type = flag.get("type", "")
        if not msg:
            continue

        # Icon by type
        icon = {
            "PERMIT": "📋",
            "STANDARD": "📏",
            "FTA": "🤝",
            "ANTIDUMPING": "⚖️",
            "ELIMINATION_CONFLICT": "🚨",
            "DIRECTIVE": "📌",
            "BILINGUAL_MISMATCH": "🔤",
        }.get(flag_type, "ℹ️")

        html_parts.append(
            f'<span style="display:inline-block;{style};border-radius:20px;'
            f'padding:3px 10px;margin:2px;font-size:11px">{icon} {msg}</span>'
        )

    if not html_parts:
        return ""

    return (
        '<div style="margin-top:6px;direction:rtl">'
        + "\n".join(html_parts)
        + '</div>'
    )
