"""
RCB Justification Engine
=========================
Every HS code classification must be backed by a legal justification chain.

A real customs broker's reasoning:
1. "This is a machine -> Chapter 84 (per heading to chapter 84)"
2. "Specifically a computing machine -> Heading 84.71"
3. "It's a complete unit -> 8471.30 (portable, weight < 10kg)"
4. "Not chapter 85 because -> heading to 85 excludes items of 84.71"
5. "No special requirements -> checked FIO appendix 2, no permit needed"

Session 27 — Assignment 11: Intelligent Classification
R.P.A.PORT LTD - February 2026
"""

import json
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("rcb.justification")


# ═══════════════════════════════════════════
#  PART 1: JUSTIFICATION CHAIN
# ═══════════════════════════════════════════

def build_justification_chain(db, hs_code, product_description, classification_reasoning=""):
    """
    Build a legal justification chain for a classification.

    Args:
        db: Firestore client
        hs_code: The classified HS code
        product_description: What the product is
        classification_reasoning: Raw AI reasoning text

    Returns:
        dict with chain, gaps, legal_strength, coverage_pct, confidence_boost
    """
    hs_clean = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""
    heading = hs_clean[:4] if len(hs_clean) >= 4 else ""

    chain = []
    gaps = []
    sources_found = 0
    sources_needed = 0

    # ── STEP 1: Chapter justification ──
    sources_needed += 1
    ch_data = None
    try:
        chapter_doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
        if chapter_doc.exists:
            ch_data = chapter_doc.to_dict()
            preamble = ch_data.get("preamble", "")
            title_he = ch_data.get("chapter_title_he", "")

            chain.append({
                "step": 1,
                "decision": f"Chapter {chapter} — {title_he}",
                "source_type": "heading_to_chapter",
                "source_ref": f"chapter {chapter}",
                "source_text": preamble[:500] if preamble else "heading not found",
                "has_source": bool(preamble),
                "reasoning": f"Product classified to chapter {chapter} based on chapter preamble",
            })
            sources_found += 1 if preamble else 0

            if not preamble:
                gaps.append({
                    "type": "missing_preamble",
                    "chapter": chapter,
                    "description": f"Preamble for chapter {chapter} not found or empty",
                    "priority": "high",
                })
        else:
            chain.append({
                "step": 1,
                "decision": f"Chapter {chapter}",
                "source_type": "heading_to_chapter",
                "source_ref": f"chapter {chapter}",
                "source_text": "Chapter not found in system",
                "has_source": False,
                "reasoning": "Chapter notes not available",
            })
            gaps.append({
                "type": "missing_chapter_notes",
                "chapter": chapter,
                "description": f"Chapter {chapter} notes not in chapter_notes collection",
                "priority": "critical",
            })
    except Exception as e:
        logger.warning(f"Chapter lookup failed: {e}")

    # ── STEP 2: Heading justification ──
    sources_needed += 1
    try:
        heading_docs = list(
            db.collection("tariff")
            .where("heading", "==", heading)
            .limit(5)
            .stream()
        )
        if heading_docs:
            heading_data = heading_docs[0].to_dict()
            chain.append({
                "step": 2,
                "decision": f"Heading {heading[:2]}.{heading[2:4]}",
                "source_type": "tariff",
                "source_ref": f"item {heading[:2]}.{heading[2:4]}",
                "source_text": heading_data.get("description_he", ""),
                "source_text_en": heading_data.get("description_en", ""),
                "has_source": True,
                "reasoning": "Heading matches product description",
            })
            sources_found += 1
        else:
            chain.append({
                "step": 2,
                "decision": f"Heading {heading[:2]}.{heading[2:4]}",
                "source_type": "tariff",
                "source_ref": f"item {heading[:2]}.{heading[2:4]}",
                "source_text": "item not found",
                "has_source": False,
                "reasoning": "Heading not found in tariff DB",
            })
            gaps.append({
                "type": "missing_heading",
                "heading": heading,
                "description": f"Heading {heading} not in tariff collection",
                "priority": "high",
            })
    except Exception as e:
        logger.warning(f"Heading lookup failed: {e}")

    # ── STEP 3: Subheading justification ──
    if len(hs_clean) >= 6:
        sources_needed += 1
        try:
            sub_docs = list(
                db.collection("tariff")
                .where("hs_code", "==", hs_code)
                .limit(3)
                .stream()
            )
            if not sub_docs:
                # Try with formatted code
                from lib.librarian import get_israeli_hs_format
                formatted = get_israeli_hs_format(hs_clean)
                sub_docs = list(
                    db.collection("tariff")
                    .where("hs_code_formatted", "==", formatted)
                    .limit(3)
                    .stream()
                )

            if sub_docs:
                sub_data = sub_docs[0].to_dict()
                chain.append({
                    "step": 3,
                    "decision": f"Subheading {hs_code}",
                    "source_type": "tariff",
                    "source_ref": f"sub-item {hs_code}",
                    "source_text": sub_data.get("description_he", ""),
                    "source_text_en": sub_data.get("description_en", ""),
                    "has_source": True,
                    "duty_rate": sub_data.get("customs_duty", ""),
                    "purchase_tax": sub_data.get("purchase_tax", ""),
                    "reasoning": "Subheading selected based on product specifics",
                })
                sources_found += 1
            else:
                gaps.append({
                    "type": "missing_subheading",
                    "hs_code": hs_code,
                    "description": f"Subheading {hs_code} not in tariff collection",
                    "priority": "medium",
                })
        except Exception as e:
            logger.warning(f"Subheading lookup failed: {e}")

    # ── STEP 4: Check for relevant notes ──
    sources_needed += 1
    if ch_data:
        notes = ch_data.get("notes", [])
        if notes:
            relevant_notes = []
            for note in notes:
                note_str = str(note)
                if heading in note_str or f"{heading[:2]}.{heading[2:4]}" in note_str:
                    relevant_notes.append(note_str)

            if relevant_notes:
                chain.append({
                    "step": 4,
                    "decision": f"Applied {len(relevant_notes)} relevant notes",
                    "source_type": "chapter_notes",
                    "source_ref": f"Notes for chapter {chapter}",
                    "source_text": "\n".join(relevant_notes)[:1000],
                    "has_source": True,
                    "reasoning": f"Found {len(relevant_notes)} notes referencing heading {heading}",
                })
                sources_found += 1
            else:
                chain.append({
                    "step": 4,
                    "decision": "No specific notes found for this heading",
                    "source_type": "chapter_notes",
                    "source_ref": f"Notes for chapter {chapter}",
                    "source_text": f"Checked {len(notes)} notes, none reference heading {heading}",
                    "has_source": True,
                    "reasoning": "No specific notes apply",
                })
                sources_found += 1
        else:
            gaps.append({
                "type": "missing_notes",
                "chapter": chapter,
                "description": f"No notes found for chapter {chapter}",
                "priority": "high",
            })

    # ── STEP 5: Check classification directives ──
    sources_needed += 1
    try:
        directive_docs = list(
            db.collection("classification_directives")
            .where("hs_code", "==", hs_code)
            .limit(3)
            .stream()
        )
        if not directive_docs:
            directive_docs = list(
                db.collection("classification_directives")
                .where("chapter", "==", chapter)
                .limit(3)
                .stream()
            )

        if directive_docs:
            chain.append({
                "step": 5,
                "decision": f"Found {len(directive_docs)} classification directives",
                "source_type": "classification_directive",
                "source_ref": "classification directives",
                "has_source": True,
                "reasoning": "Classification directive found",
            })
            sources_found += 1
        else:
            gaps.append({
                "type": "missing_directive",
                "hs_code": hs_code,
                "chapter": chapter,
                "description": f"No classification directive for {hs_code} or chapter {chapter}",
                "priority": "medium",
                "action": "search customs.gov.il for classification directives",
            })
    except Exception:
        # Collection may not exist yet
        gaps.append({
            "type": "missing_directive",
            "hs_code": hs_code,
            "chapter": chapter,
            "description": f"classification_directives collection not available",
            "priority": "medium",
        })

    # ── STEP 6: Check pre-rulings ──
    sources_needed += 1
    try:
        preruling_docs = list(
            db.collection("pre_rulings")
            .where("hs_code", "==", hs_code)
            .limit(3)
            .stream()
        )
        if preruling_docs:
            chain.append({
                "step": 6,
                "decision": f"Found {len(preruling_docs)} pre-rulings",
                "source_type": "pre_ruling",
                "source_ref": "pre-ruling",
                "has_source": True,
                "reasoning": "Pre-ruling supports this classification",
            })
            sources_found += 1
        else:
            gaps.append({
                "type": "missing_preruling",
                "hs_code": hs_code,
                "description": f"No pre-ruling found for {hs_code}",
                "priority": "low",
                "action": "search pre-ruling database if available",
            })
    except Exception:
        gaps.append({
            "type": "missing_preruling",
            "hs_code": hs_code,
            "description": "pre_rulings collection not available",
            "priority": "low",
        })

    # ── Calculate legal strength ──
    coverage = sources_found / max(sources_needed, 1)

    if coverage >= 0.8:
        legal_strength = "strong"
        confidence_boost = 15
    elif coverage >= 0.5:
        legal_strength = "moderate"
        confidence_boost = 5
    else:
        legal_strength = "weak"
        confidence_boost = -10

    return {
        "chain": chain,
        "gaps": gaps,
        "legal_strength": legal_strength,
        "sources_found": sources_found,
        "sources_needed": sources_needed,
        "coverage_pct": round(coverage * 100),
        "confidence_boost": confidence_boost,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════
#  PART 2: DEVIL'S ADVOCATE (CHALLENGE ENGINE)
# ═══════════════════════════════════════════

def challenge_classification(db, hs_code, product_description, primary_chapter,
                             gemini_key=None, call_gemini_func=None):
    """
    Devil's advocate: try to reclassify to different chapters.
    Uses Gemini Flash (cheapest) to generate alternatives.

    Returns:
        dict with alternatives, challenge_passed, strongest_alternative
    """
    hs_clean = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else str(primary_chapter).zfill(2)

    alternatives = []

    # ── METHOD 1: Check chapter exclusions pointing elsewhere ──
    try:
        chapter_doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
        if chapter_doc.exists:
            ch_data = chapter_doc.to_dict()
            exclusions = ch_data.get("exclusions", [])

            for excl in exclusions:
                excl_str = str(excl)
                ch_refs = re.findall(r'(?:chapter)\s*(\d{1,2})', excl_str, re.IGNORECASE)
                for ref in ch_refs:
                    ref_padded = ref.zfill(2)
                    if ref_padded != chapter:
                        alternatives.append({
                            "chapter": ref_padded,
                            "source": "exclusion_reference",
                            "reason_for": f"Chapter {chapter} exclusion mentions chapter {ref_padded}: {excl_str[:200]}",
                            "reason_against": "",
                            "checked": False,
                        })
    except Exception as e:
        logger.warning(f"Chapter exclusion check failed: {e}")

    # ── METHOD 2: Find chapters with similar headings via tariff search ──
    try:
        from lib.librarian import extract_search_keywords, search_collection_smart
        keywords = extract_search_keywords(product_description)
        if keywords:
            search_results = search_collection_smart(
                db, "tariff", keywords,
                ["description_he", "description_en", "hs_code"],
                max_results=20,
            )
            for result in search_results:
                result_data = result.get("data", {})
                result_chapter = str(result_data.get("chapter", "")).zfill(2)
                if result_chapter and result_chapter != chapter and result_chapter != "00":
                    alternatives.append({
                        "chapter": result_chapter,
                        "heading": result_data.get("heading", ""),
                        "source": "tariff_search",
                        "reason_for": f"Tariff search found: {result_data.get('description_he', '')[:200]}",
                        "reason_against": "",
                        "checked": False,
                    })
    except Exception as e:
        logger.warning(f"Tariff search for alternatives failed: {e}")

    # Deduplicate by chapter
    seen_chapters = set()
    unique_alternatives = []
    for alt in alternatives:
        if alt["chapter"] not in seen_chapters:
            seen_chapters.add(alt["chapter"])
            unique_alternatives.append(alt)
    alternatives = unique_alternatives[:5]

    # ── METHOD 3: For each alternative, check WHY NOT ──
    for alt in alternatives:
        alt_chapter = alt["chapter"]
        try:
            alt_doc = db.collection("chapter_notes").document(f"chapter_{alt_chapter}").get()
            if alt_doc.exists:
                alt_data = alt_doc.to_dict()
                alt_exclusions = alt_data.get("exclusions", [])

                for excl in alt_exclusions:
                    excl_str = str(excl)
                    if chapter in excl_str:
                        alt["reason_against"] = f"Chapter {alt_chapter} excludes: {excl_str[:200]}"
                        break

                if not alt["reason_against"]:
                    alt["reason_against"] = (
                        f"Checked chapter {alt_chapter} preamble — "
                        f"no exclusion found, but primary chapter is more specific"
                    )
        except Exception:
            pass
        alt["checked"] = True

    # ── METHOD 4: Use AI for deeper challenge (if strong unresolved alternatives) ──
    strong_alternatives = [a for a in alternatives if a["checked"] and not a["reason_against"]]

    if strong_alternatives and call_gemini_func and gemini_key:
        alt_list = "\n".join(
            [f"- Chapter {a['chapter']}: {a['reason_for'][:100]}" for a in strong_alternatives[:3]]
        )
        challenge_prompt = (
            f"You are a devil's advocate Israeli customs classification expert.\n"
            f"The primary classification is: {hs_code} (Chapter {chapter})\n"
            f"Product: {product_description[:500]}\n\n"
            f"These alternative chapters were found with NO clear exclusion:\n{alt_list}\n\n"
            f"For each alternative, explain briefly in Hebrew:\n"
            f"1. Why it COULD apply\n"
            f"2. Why the primary classification is BETTER\n\n"
            f"Respond as JSON array:\n"
            f'[{{"chapter": "XX", "could_apply": "reason", "primary_better": "reason"}}]'
        )

        try:
            ai_response = call_gemini_func(
                gemini_key,
                "You are an Israeli customs classification expert reviewing alternative classifications.",
                challenge_prompt,
                max_tokens=500,
                model="gemini-2.5-flash",
            )
            if ai_response:
                try:
                    # Extract JSON from response
                    json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
                    if json_match:
                        ai_alts = json.loads(json_match.group())
                        for ai_alt in ai_alts:
                            for alt in alternatives:
                                if alt["chapter"] == str(ai_alt.get("chapter", "")).zfill(2):
                                    alt["ai_reason_for"] = ai_alt.get("could_apply", "")
                                    alt["ai_reason_against"] = ai_alt.get("primary_better", "")
                                    if not alt["reason_against"]:
                                        alt["reason_against"] = ai_alt.get("primary_better", "")
                except (json.JSONDecodeError, ValueError):
                    pass
        except Exception as e:
            logger.warning(f"Challenge AI call failed: {e}")

    # ── Verdict ──
    unresolved = [a for a in alternatives if not a.get("reason_against")]
    challenge_passed = len(unresolved) == 0
    strongest = (
        max(alternatives, key=lambda a: len(a.get("reason_for", "")))
        if alternatives
        else None
    )

    return {
        "alternatives": alternatives,
        "challenge_passed": challenge_passed,
        "unresolved_count": len(unresolved),
        "strongest_alternative": strongest,
        "chapters_checked": len(alternatives),
    }


# ═══════════════════════════════════════════
#  PART 3: GAP DETECTION + STORAGE
# ═══════════════════════════════════════════

def save_knowledge_gaps(db, gaps, email_id=None, hs_code=None):
    """Save detected knowledge gaps for nightly enrichment."""
    if not gaps:
        return

    now = datetime.now(timezone.utc).isoformat()

    for gap in gaps:
        gap_doc = {
            "type": gap.get("type", "unknown"),
            "description": gap.get("description", ""),
            "priority": gap.get("priority", "low"),
            "action": gap.get("action", ""),
            "hs_code": hs_code or gap.get("hs_code", ""),
            "chapter": gap.get("chapter", ""),
            "email_id": email_id or "",
            "detected_at": now,
            "status": "open",
            "filled_at": None,
            "filled_by": None,
        }

        # Deterministic ID so same gap isn't duplicated
        gap_id = f"{gap.get('type', 'unknown')}_{gap.get('chapter', '')}_{gap.get('hs_code', '')}"
        gap_id = gap_id.replace(".", "_").replace("/", "_").replace(" ", "_")

        try:
            existing = db.collection("knowledge_gaps").document(gap_id).get()
            if not existing.exists:
                db.collection("knowledge_gaps").document(gap_id).set(gap_doc)
                logger.info(f"New gap: {gap_id}")
            else:
                # Update seen count
                db.collection("knowledge_gaps").document(gap_id).update({
                    "seen_count": (existing.to_dict().get("seen_count", 0) or 0) + 1,
                    "last_seen": now,
                })
        except Exception as e:
            logger.warning(f"Failed to save gap {gap_id}: {e}")


# ═══════════════════════════════════════════
#  PART 5: PUPIL QUESTIONS (when confused)
# ═══════════════════════════════════════════

def generate_pupil_questions(db, hs_code, product_description, justification, challenge_result):
    """
    When confidence is low and challenge found unresolved alternatives,
    generate specific questions for Doron.

    Returns list of questions with context.
    """
    questions = []

    # From unresolved alternatives
    if challenge_result and challenge_result.get("unresolved_count", 0) > 0:
        for alt in challenge_result.get("alternatives", []):
            if not alt.get("reason_against"):
                questions.append({
                    "question_he": (
                        f"Is this product in chapter {alt['chapter']} "
                        f"({alt.get('reason_for', '')[:100]})?"
                    ),
                    "question_en": f"Could this product belong to chapter {alt['chapter']}?",
                    "context": f"Product: {product_description[:200]}",
                    "primary_hs": hs_code,
                    "alternative_chapter": alt["chapter"],
                    "type": "chapter_dispute",
                })

    # From gaps in justification
    if justification:
        for gap in justification.get("gaps", []):
            if gap.get("priority") in ["critical", "high"]:
                questions.append({
                    "question_he": f"Missing information: {gap.get('description', '')}",
                    "question_en": f"Missing: {gap.get('description', '')}",
                    "context": f"Needed for classification of {hs_code}",
                    "gap_type": gap.get("type", ""),
                    "type": "knowledge_gap",
                })

    # Save questions for daily digest
    if questions:
        now = datetime.now(timezone.utc).isoformat()
        for q in questions:
            q["asked_at"] = now
            q["answered"] = False
            q["answer"] = None
            try:
                db.collection("pupil_questions").add(q)
            except Exception as e:
                logger.warning(f"Failed to save pupil question: {e}")

    return questions
