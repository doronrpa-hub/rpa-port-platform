"""
RCB Overnight Brain Explosion — Know Everything By Morning.
=============================================================
8 parallel enrichment streams that mine ALL internal data, call the UK Tariff
API, cross-reference everything, and use Gemini Flash to fill knowledge gaps.

HARD COST CAP: $3.50 per run (enforced by CostTracker).

Streams:
  1. Tariff Deep Mine — fix garbage, extract & index terms from 11,753 items
  2. Email Archive Mine — mine rcb_processed + inbox for products, suppliers
  3. CC Email Learning — expert decisions from CC'd emails (GOLD)
  4. Attachment Text Mine — mine extracted text from inbox attachments
  5. AI Knowledge Fill — Gemini fills open knowledge_gaps
  6. UK Tariff API Sweep — free HTTPS calls, zero AI cost
  7. Cross-Reference Engine — link every HS code to all its data sources
  8. Self-Teach from Patterns — synthesize per-chapter classification rules

Schedule: 20:00 Jerusalem time (well before 02:00 nightly_learn — no conflict).

Session 28 — Assignment 19
R.P.A.PORT LTD - February 2026
"""

import json
import re
import time
import logging
import requests
from datetime import datetime, timezone
from collections import defaultdict

from lib.cost_tracker import CostTracker, call_gemini_tracked

logger = logging.getLogger("rcb.overnight_brain")

# Stream priority (if budget runs low, highest priority streams run first)
STREAM_PRIORITY = [
    (6, "UK API sweep"),           # $0.00 — free API
    (7, "Cross-reference"),        # ~$0.00 — Firestore only
    (3, "CC email learning"),      # ~$0.01 — expert decisions = GOLD
    (8, "Self-teach"),             # ~$0.02 — synthesizes everything
    (1, "Tariff deep mine"),       # ~$0.04 — fixes core data
    (2, "Email archive mine"),     # ~$0.01 — history mining
    (5, "AI knowledge fill"),      # ~$0.02 — fills gaps
    (4, "Attachment mine"),        # ~$0.05 — biggest batch
]


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

_HS_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4,8}(/\d)?$")
_HS_DIGITS_RE = re.compile(r"^\d{4,10}$")


def _validate_hs_format(code):
    """Check if code looks like a valid Israeli HS code."""
    if not code or not isinstance(code, str):
        return False
    clean = code.replace(".", "").replace("/", "").replace(" ", "")
    if not _HS_DIGITS_RE.match(clean):
        return False
    try:
        chapter = int(clean[:2])
        return 1 <= chapter <= 97
    except (ValueError, IndexError):
        return False


def _is_garbage_description(desc):
    """Detect garbage/corrupted tariff descriptions."""
    if not desc or len(desc.strip()) < 3:
        return True
    # Mostly non-printable or very short
    printable = sum(1 for c in desc if c.isprintable())
    if printable < len(desc) * 0.5:
        return True
    # Mostly digits or punctuation
    alpha = sum(1 for c in desc if c.isalpha())
    if alpha < 3:
        return True
    return False


def _extract_hebrew_terms(text):
    """Extract meaningful Hebrew terms from a description."""
    if not text:
        return []
    # Hebrew letter range: \u0590-\u05FF
    words = re.findall(r"[\u0590-\u05FF]{2,}", text)
    # Filter stop words and very short words
    stop = {"של", "את", "או", "לא", "על", "עם", "כל", "אם", "גם", "כי", "זה", "הם", "היא", "הוא", "מן"}
    return [w for w in words if len(w) >= 2 and w not in stop]


def _extract_english_terms(text):
    """Extract meaningful English terms from a description."""
    if not text:
        return []
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {"the", "and", "for", "not", "with", "from", "that", "this", "are", "was",
            "other", "than", "but", "all", "any", "each", "into", "more", "such",
            "including", "excluding", "whether", "being", "having", "which", "their",
            "been", "used", "made", "see", "also", "note", "chapter", "heading",
            "subheading", "parts", "thereof", "hereof"}
    return list(set(w for w in words if w not in stop))[:20]


def _safe_doc_id(text):
    """Create a safe Firestore document ID from text."""
    safe = re.sub(r"[^a-zA-Z0-9\u0590-\u05FF_-]", "_", str(text)[:80])
    return safe.strip("_")[:100] or "unknown"


def _chunk_list(lst, size):
    """Split a list into chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def _convert_il_to_uk_code(il_code):
    """Convert Israeli HS code to UK 10-digit format for API lookup."""
    clean = il_code.replace(".", "").replace("/", "").replace(" ", "")
    # Pad to 10 digits (UK commodity codes are 10 digits)
    return clean.ljust(10, "0")[:10]


# ═══════════════════════════════════════════════════════════════
#  STREAM 1: TARIFF DEEP MINE
# ═══════════════════════════════════════════════════════════════

def stream_1_tariff_deep_mine(db, gemini_key, tracker):
    """
    Mine 11,753 tariff items. Fix garbage descriptions. Index every term.
    Mostly FREE (text parsing), ~$0.04 for Gemini garbage fixes.
    """
    print("  [Stream 1] Tariff deep mine starting...")
    stats = {"processed": 0, "garbage_found": 0, "garbage_fixed": 0,
             "terms_indexed": 0, "errors": 0}

    try:
        all_items = list(db.collection("tariff").stream())
        tracker.record_firestore_ops(reads=len(all_items))
    except Exception as e:
        logger.error(f"Stream 1: Failed to read tariff: {e}")
        return stats

    garbage_batch = []

    for item in all_items:
        if tracker.is_over_budget:
            break

        data = item.to_dict()
        stats["processed"] += 1
        hs_code = data.get("hs_code", "")

        desc_he = data.get("description_he", "") or data.get("title_he", "") or ""
        desc_en = data.get("description_en", "") or data.get("title_en", "") or ""

        # Check for garbage descriptions
        if _is_garbage_description(desc_he) and hs_code:
            stats["garbage_found"] += 1
            garbage_batch.append({
                "id": item.id,
                "hs_code": hs_code,
                "desc": desc_he[:200],
            })

            # Batch fix with Gemini every 50 garbage entries
            if len(garbage_batch) >= 50:
                fixed = _fix_garbage_batch(db, gemini_key, tracker, garbage_batch)
                stats["garbage_fixed"] += fixed
                garbage_batch = []
            continue

        # Extract and index terms (FREE — no AI)
        terms_he = _extract_hebrew_terms(desc_he)
        terms_en = _extract_english_terms(desc_en)
        all_terms = terms_he + terms_en

        if all_terms and hs_code:
            chapter = hs_code.replace(".", "").replace("/", "")[:2]
            for term in all_terms[:15]:  # Max 15 terms per item
                doc_id = _safe_doc_id(term)
                try:
                    ref = db.collection("keyword_index").document(doc_id)
                    existing = ref.get()
                    if existing.exists:
                        existing_data = existing.to_dict()
                        codes = existing_data.get("codes", [])
                        # Don't duplicate
                        if not any(c.get("hs_code") == hs_code for c in codes):
                            codes.append({
                                "hs_code": hs_code,
                                "weight": 1,
                                "source": "tariff_deep_mine",
                                "description": desc_he[:100],
                            })
                            ref.update({
                                "codes": codes,
                                "count": len(codes),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            })
                    else:
                        ref.set({
                            "keyword": term,
                            "codes": [{
                                "hs_code": hs_code,
                                "weight": 1,
                                "source": "tariff_deep_mine",
                                "description": desc_he[:100],
                            }],
                            "count": 1,
                            "built_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                    stats["terms_indexed"] += 1
                except Exception:
                    stats["errors"] += 1

            tracker.record_firestore_ops(writes=min(len(all_terms), 15))

    # Process remaining garbage batch
    if garbage_batch and not tracker.is_over_budget:
        fixed = _fix_garbage_batch(db, gemini_key, tracker, garbage_batch)
        stats["garbage_fixed"] += fixed

    print(f"  [Stream 1] Done: {stats['processed']} items, "
          f"{stats['garbage_found']} garbage ({stats['garbage_fixed']} fixed), "
          f"{stats['terms_indexed']} terms indexed")
    return stats


def _fix_garbage_batch(db, gemini_key, tracker, batch):
    """Use Gemini to fix a batch of corrupted tariff descriptions."""
    if not batch or tracker.is_over_budget:
        return 0

    prompt = (
        "Fix these corrupted Israeli tariff descriptions. "
        "For each, return the correct Hebrew description based on the HS code.\n"
        f"{json.dumps(batch, ensure_ascii=False)}\n"
        'Respond with JSON array: [{"id": "...", "fixed_description": "..."}]'
    )

    result = call_gemini_tracked(gemini_key, prompt, tracker, max_tokens=2000)

    if not result or not isinstance(result, list):
        return 0

    fixed = 0
    for fix in result:
        fix_id = fix.get("id")
        fix_desc = fix.get("fixed_description", "")
        if fix_id and fix_desc:
            try:
                db.collection("tariff").document(fix_id).update({
                    "description_he": fix_desc,
                    "description_fixed_by": "overnight_brain_gemini",
                    "fixed_at": datetime.now(timezone.utc).isoformat(),
                })
                fixed += 1
            except Exception as e:
                logger.warning(f"Failed to fix tariff {fix_id}: {e}")
    tracker.record_firestore_ops(writes=fixed)
    return fixed


# ═══════════════════════════════════════════════════════════════
#  STREAM 2: EMAIL ARCHIVE MINE
# ═══════════════════════════════════════════════════════════════

def stream_2_email_archive_mine(db, gemini_key, tracker):
    """
    Mine ALL processed emails for products, suppliers, patterns.
    Cost: ~$0.01 (batch 50 emails per Gemini call).
    """
    print("  [Stream 2] Email archive mine starting...")
    stats = {"emails_processed": 0, "suppliers_found": 0,
             "keywords_added": 0, "errors": 0}

    # Read from rcb_processed (has subject, from) and inbox (has body, attachments)
    try:
        processed = list(db.collection("rcb_processed").stream())
        tracker.record_firestore_ops(reads=len(processed))
    except Exception as e:
        logger.error(f"Stream 2: Failed to read rcb_processed: {e}")
        return stats

    # Also read rcb_classifications for HS codes assigned
    try:
        classifications = list(db.collection("rcb_classifications").stream())
        tracker.record_firestore_ops(reads=len(classifications))
    except Exception:
        classifications = []

    # Build lookup: subject -> classification data
    cls_by_subject = {}
    for cls in classifications:
        cls_data = cls.to_dict()
        subj = cls_data.get("subject", "")
        if subj:
            cls_by_subject[subj] = cls_data

    # Batch process emails
    email_texts = []
    for doc in processed:
        data = doc.to_dict()
        email_texts.append({
            "id": doc.id,
            "from": data.get("from", ""),
            "subject": data.get("subject", ""),
            "type": data.get("type", ""),
            "hs_code": cls_by_subject.get(data.get("subject", ""), {}).get("hs_code", ""),
        })

    for batch in _chunk_list(email_texts, 50):
        if tracker.is_over_budget:
            break

        result = call_gemini_tracked(
            gemini_key,
            f"""Extract from each email entry:
- supplier_name: company name (not person)
- supplier_domain: email domain
- product_keywords: up to 10 Hebrew + English keywords
- email_intent: classification_request|tracking|question|information|cc_observation
- client_product_category: electronics, textiles, food, chemicals, etc.

Emails:
{json.dumps(batch, ensure_ascii=False)}

JSON array, one per email, matching by id.""",
            tracker,
            max_tokens=2000,
        )

        if not result or not isinstance(result, list):
            continue

        for r in result:
            stats["emails_processed"] += 1
            supplier = r.get("supplier_name", "")
            domain = r.get("supplier_domain", "")
            keywords = r.get("product_keywords", [])
            category = r.get("client_product_category", "")

            # Update supplier_index
            if supplier:
                try:
                    sup_id = _safe_doc_id(supplier.lower())
                    sup_ref = db.collection("supplier_index").document(sup_id)
                    sup_doc = sup_ref.get()
                    if sup_doc.exists:
                        sup_data = sup_doc.to_dict()
                        sup_data.setdefault("products", {})
                        if category:
                            sup_data["products"][category] = {
                                "count": sup_data["products"].get(category, {}).get("count", 0) + 1,
                                "last_seen": datetime.now(timezone.utc).isoformat(),
                            }
                        sup_ref.update({
                            "products": sup_data["products"],
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        sup_ref.set({
                            "supplier_name": supplier,
                            "domain": domain,
                            "products": {category: {"count": 1}} if category else {},
                            "codes": [],
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                    stats["suppliers_found"] += 1
                except Exception:
                    stats["errors"] += 1

            # Add product keywords to keyword_index
            hs_code = r.get("hs_code") or batch[0].get("hs_code", "") if batch else ""
            for kw in keywords[:10]:
                try:
                    kw_id = _safe_doc_id(kw.lower())
                    kw_ref = db.collection("keyword_index").document(kw_id)
                    kw_doc = kw_ref.get()
                    if kw_doc.exists:
                        kw_data = kw_doc.to_dict()
                        codes = kw_data.get("codes", [])
                        if hs_code and not any(c.get("hs_code") == hs_code for c in codes):
                            codes.append({
                                "hs_code": hs_code,
                                "weight": 1,
                                "source": "email_archive_mine",
                                "description": r.get("supplier_name", ""),
                            })
                            kw_ref.update({"codes": codes, "count": len(codes),
                                           "updated_at": datetime.now(timezone.utc).isoformat()})
                    else:
                        entry = {
                            "keyword": kw,
                            "codes": [],
                            "count": 0,
                            "built_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        if hs_code:
                            entry["codes"].append({
                                "hs_code": hs_code,
                                "weight": 1,
                                "source": "email_archive_mine",
                            })
                            entry["count"] = 1
                        kw_ref.set(entry)
                    stats["keywords_added"] += 1
                except Exception:
                    stats["errors"] += 1

        tracker.record_firestore_ops(writes=stats["suppliers_found"] + stats["keywords_added"])

    print(f"  [Stream 2] Done: {stats['emails_processed']} emails, "
          f"{stats['suppliers_found']} suppliers, {stats['keywords_added']} keywords")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 3: CC EMAIL DEEP LEARNING
# ═══════════════════════════════════════════════════════════════

def stream_3_cc_email_learning(db, gemini_key, tracker):
    """
    CC emails are GOLD — Doron's actual expert decisions.
    Mine for classification decisions, corrections, reasoning, terminology.
    Cost: ~$0.01
    """
    print("  [Stream 3] CC email learning starting...")
    stats = {"cc_emails": 0, "patterns_learned": 0, "corrections_learned": 0,
             "terms_added": 0, "errors": 0}

    # CC emails are stored in rcb_processed with type "cc_observation"
    try:
        cc_docs = list(
            db.collection("rcb_processed")
            .where("type", "==", "cc_observation")
            .stream()
        )
        tracker.record_firestore_ops(reads=len(cc_docs))
    except Exception as e:
        logger.error(f"Stream 3: Failed to read CC emails: {e}")
        return stats

    if not cc_docs:
        print("  [Stream 3] No CC emails found")
        return stats

    # Batch process
    cc_texts = []
    for doc in cc_docs:
        data = doc.to_dict()
        cc_texts.append({
            "id": doc.id,
            "from": data.get("from", ""),
            "subject": data.get("subject", ""),
        })

    for batch in _chunk_list(cc_texts, 30):
        if tracker.is_over_budget:
            break

        result = call_gemini_tracked(
            gemini_key,
            f"""These are CC'd emails from a customs brokerage team (Doron, Rina, Galina at R.P.A.PORT).
Extract from each:
- is_classification_decision: boolean (assigns HS code to product?)
- hs_code_assigned: string
- product_classified: string
- is_correction: boolean (corrects a previous classification?)
- original_code: string (if correction)
- corrected_code: string (if correction)
- correction_reason: string
- expert_reasoning: string (WHY this classification?)
- new_terms: list of customs/product terms in Hebrew
- email_intent: classification|correction|question|tracking|other

Emails:
{json.dumps(batch, ensure_ascii=False)}

JSON array.""",
            tracker,
            max_tokens=2000,
        )

        if not result or not isinstance(result, list):
            continue

        now = datetime.now(timezone.utc).isoformat()

        for r in result:
            stats["cc_emails"] += 1

            # Store classification decisions as learned patterns
            if r.get("is_classification_decision") and r.get("hs_code_assigned"):
                try:
                    db.collection("learned_patterns").add({
                        "source": "cc_email_expert",
                        "product": r.get("product_classified", ""),
                        "hs_code": r["hs_code_assigned"],
                        "reasoning": r.get("expert_reasoning", ""),
                        "confidence": "high",
                        "learned_at": now,
                    })
                    stats["patterns_learned"] += 1
                except Exception:
                    stats["errors"] += 1

            # Store corrections
            if r.get("is_correction") and r.get("corrected_code"):
                try:
                    db.collection("learned_corrections").add({
                        "original_code": r.get("original_code", ""),
                        "corrected_code": r["corrected_code"],
                        "product": r.get("product_classified", ""),
                        "reason": r.get("correction_reason", ""),
                        "source": "cc_email_correction",
                        "learned_at": now,
                    })
                    stats["corrections_learned"] += 1
                except Exception:
                    stats["errors"] += 1

            # Add new terms to keyword_index
            for term in r.get("new_terms", [])[:10]:
                try:
                    t_id = _safe_doc_id(term)
                    t_ref = db.collection("keyword_index").document(t_id)
                    if not t_ref.get().exists:
                        hs = r.get("hs_code_assigned", "")
                        t_ref.set({
                            "keyword": term,
                            "codes": [{"hs_code": hs, "weight": 3, "source": "cc_expert"}] if hs else [],
                            "count": 1 if hs else 0,
                            "built_at": now,
                            "updated_at": now,
                        })
                        stats["terms_added"] += 1
                except Exception:
                    stats["errors"] += 1

        tracker.record_firestore_ops(
            writes=stats["patterns_learned"] + stats["corrections_learned"] + stats["terms_added"]
        )

    print(f"  [Stream 3] Done: {stats['cc_emails']} CC emails, "
          f"{stats['patterns_learned']} patterns, {stats['corrections_learned']} corrections")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 4: ATTACHMENT TEXT MINE
# ═══════════════════════════════════════════════════════════════

def stream_4_attachment_mine(db, gemini_key, tracker):
    """
    Mine extracted text from inbox attachment entries.
    Extract: document type, products, materials, HS codes on documents.
    Cost: ~$0.05 (biggest batch).
    """
    print("  [Stream 4] Attachment text mine starting...")
    stats = {"docs_scanned": 0, "products_found": 0, "materials_found": 0,
             "hs_codes_found": 0, "errors": 0}

    # Inbox docs have extracted text from attachments
    try:
        inbox_docs = list(db.collection("inbox").stream())
        tracker.record_firestore_ops(reads=len(inbox_docs))
    except Exception as e:
        logger.error(f"Stream 4: Failed to read inbox: {e}")
        return stats

    # Filter to docs with substantial extracted text
    processable = []
    for doc in inbox_docs:
        data = doc.to_dict()
        # Attachments may have extracted_text
        attachments = data.get("attachments", [])
        body = data.get("body", "")
        # Combine available text
        text = body or ""
        for att in attachments:
            text += " " + (att.get("extracted_text", "") or "")
        text = text.strip()

        if len(text) > 100:
            processable.append({
                "id": doc.id,
                "text": text[:1500],
                "subject": data.get("subject", ""),
                "from": data.get("from", ""),
            })

    print(f"  [Stream 4] {len(processable)} docs with text > 100 chars")

    for batch in _chunk_list(processable, 30):
        if tracker.is_over_budget:
            break

        result = call_gemini_tracked(
            gemini_key,
            f"""Texts from customs/logistics document attachments. For each extract:
- document_type: invoice|packing_list|bill_of_lading|awb|certificate_of_origin|eur1|msds|brochure|other
- products: list of {{name, description}}
- materials: list of material compositions
- hs_codes_on_document: any HS/tariff codes printed on document
- country_of_origin: string
- supplier_manufacturer: string
- key_terms: 5-10 terms for search (Hebrew and English)

Documents:
{json.dumps(batch, ensure_ascii=False)}

JSON array. If no useful data: {{"id":"...","skip":true}}""",
            tracker,
            max_tokens=2000,
        )

        if not result or not isinstance(result, list):
            continue

        now = datetime.now(timezone.utc).isoformat()

        for r in result:
            if r.get("skip"):
                continue
            stats["docs_scanned"] += 1

            # Index products
            for product in r.get("products", []):
                name = product.get("name", "")
                if name:
                    try:
                        p_id = _safe_doc_id(name.lower())
                        p_ref = db.collection("product_index").document(p_id)
                        p_doc = p_ref.get()
                        if not p_doc.exists:
                            p_ref.set({
                                "product_name": name,
                                "description": product.get("description", ""),
                                "hs_code": "",
                                "confidence": 0,
                                "usage_count": 1,
                                "materials": r.get("materials", []),
                                "source": "attachment_mine",
                                "updated_at": now,
                            })
                        else:
                            p_ref.update({
                                "usage_count": (p_doc.to_dict().get("usage_count", 0) or 0) + 1,
                                "updated_at": now,
                            })
                        stats["products_found"] += 1
                    except Exception:
                        stats["errors"] += 1

            # Index materials
            for material in r.get("materials", []):
                if material:
                    try:
                        m_id = _safe_doc_id(str(material).lower())
                        m_ref = db.collection("keyword_index").document(m_id)
                        if not m_ref.get().exists:
                            m_ref.set({
                                "keyword": str(material),
                                "codes": [],
                                "count": 0,
                                "built_at": now,
                                "updated_at": now,
                            })
                        stats["materials_found"] += 1
                    except Exception:
                        stats["errors"] += 1

            # Track HS codes found on documents
            for code in r.get("hs_codes_on_document", []):
                if _validate_hs_format(str(code)):
                    stats["hs_codes_found"] += 1

            # Update supplier
            supplier = r.get("supplier_manufacturer", "")
            if supplier:
                try:
                    s_id = _safe_doc_id(supplier.lower())
                    s_ref = db.collection("supplier_index").document(s_id)
                    if not s_ref.get().exists:
                        s_ref.set({
                            "supplier_name": supplier,
                            "country": r.get("country_of_origin", ""),
                            "codes": [],
                            "products": {},
                            "updated_at": now,
                        })
                except Exception:
                    stats["errors"] += 1

        tracker.record_firestore_ops(
            writes=stats["products_found"] + stats["materials_found"]
        )

    print(f"  [Stream 4] Done: {stats['docs_scanned']} docs, "
          f"{stats['products_found']} products, {stats['materials_found']} materials")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 5: AI KNOWLEDGE FILL
# ═══════════════════════════════════════════════════════════════

def stream_5_ai_knowledge_fill(db, gemini_key, tracker):
    """
    Use Gemini training knowledge to fill open gaps.
    Store as ai_knowledge_enrichment (tagged as AI opinion).
    Cost: ~$0.02
    """
    print("  [Stream 5] AI knowledge fill starting...")
    stats = {"gaps_processed": 0, "gaps_filled": 0, "enrichments_added": 0, "errors": 0}

    # Read open knowledge gaps
    try:
        gaps = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "open")
            .limit(100)
            .stream()
        )
        tracker.record_firestore_ops(reads=len(gaps))
    except Exception as e:
        logger.error(f"Stream 5: Failed to read knowledge_gaps: {e}")
        return stats

    # Collect HS codes from gaps
    hs_codes_to_enrich = set()
    gap_docs = []
    for gap_doc in gaps:
        gap = gap_doc.to_dict()
        gap["_doc_id"] = gap_doc.id
        gap_docs.append(gap)
        code = gap.get("hs_code", "")
        if code and _validate_hs_format(code):
            hs_codes_to_enrich.add(code)

    # Also get most classified codes from rcb_classifications
    try:
        recent_cls = list(db.collection("rcb_classifications").limit(200).stream())
        tracker.record_firestore_ops(reads=len(recent_cls))
        for cls in recent_cls:
            code = cls.to_dict().get("hs_code", "")
            if code and _validate_hs_format(code):
                hs_codes_to_enrich.add(code)
    except Exception:
        pass

    print(f"  [Stream 5] {len(hs_codes_to_enrich)} HS codes to enrich")

    # Check which already have AI enrichments
    try:
        existing = set()
        for doc in db.collection("ai_knowledge_enrichments").stream():
            existing.add(doc.to_dict().get("hs_code", ""))
        tracker.record_firestore_ops(reads=len(existing))
        hs_codes_to_enrich -= existing
    except Exception:
        pass

    # Enrich in batches
    now = datetime.now(timezone.utc).isoformat()
    for batch in _chunk_list(list(hs_codes_to_enrich), 10):
        if tracker.is_over_budget:
            break

        # Look up existing descriptions
        codes_info = []
        for code in batch:
            clean = code.replace(".", "").replace("/", "")
            desc = ""
            try:
                items = list(
                    db.collection("tariff")
                    .where("hs_code", "==", code)
                    .limit(1)
                    .stream()
                )
                if items:
                    desc = items[0].to_dict().get("description_he", "")
            except Exception:
                pass
            codes_info.append({"code": code, "description": desc})
            tracker.record_firestore_ops(reads=1)

        result = call_gemini_tracked(
            gemini_key,
            f"""Senior Israeli customs broker analysis. For each HS code provide:
- classification_rules: which rules determine this classification
- alternative_codes: 2-3 codes that could be confused, why they're wrong
- physical_characteristics: what physical properties determine this
- edge_cases: known disputes or ambiguities
- key_terms_he: 5-10 Hebrew terms
- key_terms_en: 5-10 English terms

Codes:
{json.dumps(codes_info, ensure_ascii=False)}

JSON array.""",
            tracker,
            max_tokens=3000,
        )

        if not result or not isinstance(result, list):
            continue

        for r in result:
            code = r.get("code", "")
            if not code:
                continue
            stats["gaps_processed"] += 1

            try:
                db.collection("ai_knowledge_enrichments").add({
                    "hs_code": code,
                    "source": "gemini_flash_knowledge",
                    "generated_at": now,
                    "data": r,
                    "confidence": "ai_generated",
                })
                stats["enrichments_added"] += 1

                # Add terms to keyword_index
                for term in r.get("key_terms_he", []) + r.get("key_terms_en", []):
                    try:
                        t_id = _safe_doc_id(term)
                        t_ref = db.collection("keyword_index").document(t_id)
                        if not t_ref.get().exists:
                            t_ref.set({
                                "keyword": term,
                                "codes": [{"hs_code": code, "weight": 1, "source": "ai_enrichment"}],
                                "count": 1,
                                "built_at": now,
                                "updated_at": now,
                            })
                    except Exception:
                        pass

                # Fill matching gaps
                for gap in gap_docs:
                    if gap.get("hs_code") == code:
                        try:
                            db.collection("knowledge_gaps").document(gap["_doc_id"]).update({
                                "status": "filled_by_ai",
                                "filled_at": now,
                            })
                            stats["gaps_filled"] += 1
                        except Exception:
                            pass

            except Exception:
                stats["errors"] += 1

        tracker.record_firestore_ops(writes=stats["enrichments_added"] * 3)

    print(f"  [Stream 5] Done: {stats['gaps_processed']} codes processed, "
          f"{stats['enrichments_added']} enrichments, {stats['gaps_filled']} gaps filled")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 6: UK TARIFF API SWEEP
# ═══════════════════════════════════════════════════════════════

def stream_6_uk_tariff_sweep(db, tracker):
    """
    UK Trade Tariff API — free, no key needed, works over HTTPS.
    Fetch English descriptions + chapter notes for every HS code.
    Rate limit: 2 req/sec. Cost: $0.00 (only Firestore writes).
    """
    print("  [Stream 6] UK Tariff API sweep starting...")
    stats = {"fetched": 0, "not_found": 0, "errors": 0, "already_cached": 0}

    # Collect all HS codes from tariff collection
    all_codes = set()
    try:
        items = list(db.collection("tariff").stream())
        tracker.record_firestore_ops(reads=len(items))
        for item in items:
            code = item.to_dict().get("hs_code", "")
            if _validate_hs_format(code):
                all_codes.add(code)
    except Exception as e:
        logger.error(f"Stream 6: Failed to read tariff: {e}")
        return stats

    # Also collect codes from classifications
    try:
        cls_docs = list(db.collection("rcb_classifications").stream())
        tracker.record_firestore_ops(reads=len(cls_docs))
        for doc in cls_docs:
            code = doc.to_dict().get("hs_code", "")
            if code and _validate_hs_format(code):
                all_codes.add(code)
    except Exception:
        pass

    # Check existing UK tariff cache
    existing_codes = set()
    try:
        uk_docs = list(db.collection("tariff_uk").stream())
        tracker.record_firestore_ops(reads=len(uk_docs))
        for doc in uk_docs:
            existing_codes.add(doc.to_dict().get("il_code", ""))
    except Exception:
        pass

    codes_to_fetch = all_codes - existing_codes
    stats["already_cached"] = len(existing_codes)
    print(f"  [Stream 6] {len(codes_to_fetch)} codes to fetch ({len(existing_codes)} cached)")

    # Limit to avoid timeout — max 200 per run
    codes_to_fetch = list(codes_to_fetch)[:200]

    for code in codes_to_fetch:
        if tracker.is_over_budget:
            break

        uk_code = _convert_il_to_uk_code(code)

        try:
            response = requests.get(
                f"https://www.trade-tariff.service.gov.uk/api/v2/commodities/{uk_code}",
                timeout=10,
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                attrs = data.get("data", {}).get("attributes", {})

                uk_entry = {
                    "uk_code": uk_code,
                    "il_code": code,
                    "description": attrs.get("description", ""),
                    "formatted_description": attrs.get("formatted_description", ""),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

                # Extract ancestors (tree path)
                included = data.get("included", [])
                ancestors = []
                for inc in included:
                    if inc.get("type") in ("heading", "chapter", "commodity"):
                        ancestors.append({
                            "type": inc["type"],
                            "id": inc.get("id", ""),
                            "description": inc.get("attributes", {}).get("description", ""),
                        })
                uk_entry["ancestors"] = ancestors

                # Extract footnotes
                footnotes = []
                for inc in included:
                    if inc.get("type") == "footnote":
                        footnotes.append(inc.get("attributes", {}).get("description", ""))
                uk_entry["footnotes"] = footnotes

                db.collection("tariff_uk").document(uk_code).set(uk_entry)
                tracker.record_firestore_ops(writes=1)

                # Index English terms from description
                en_terms = _extract_english_terms(uk_entry["description"])
                for term in en_terms[:10]:
                    try:
                        t_id = _safe_doc_id(term)
                        t_ref = db.collection("keyword_index").document(t_id)
                        t_doc = t_ref.get()
                        if t_doc.exists:
                            t_data = t_doc.to_dict()
                            codes = t_data.get("codes", [])
                            if not any(c.get("hs_code") == code for c in codes):
                                codes.append({
                                    "hs_code": code,
                                    "weight": 1,
                                    "source": "uk_tariff",
                                    "description": uk_entry["description"][:100],
                                })
                                t_ref.update({"codes": codes, "count": len(codes),
                                              "updated_at": datetime.now(timezone.utc).isoformat()})
                        else:
                            t_ref.set({
                                "keyword": term,
                                "codes": [{"hs_code": code, "weight": 1, "source": "uk_tariff",
                                           "description": uk_entry["description"][:100]}],
                                "count": 1,
                                "built_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            })
                    except Exception:
                        pass
                tracker.record_firestore_ops(writes=min(len(en_terms), 10))
                stats["fetched"] += 1

            elif response.status_code == 404:
                db.collection("tariff_uk").document(uk_code).set({
                    "uk_code": uk_code,
                    "il_code": code,
                    "status": "not_found_in_uk",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
                tracker.record_firestore_ops(writes=1)
                stats["not_found"] += 1

            else:
                stats["errors"] += 1

            # Rate limit: 2/sec
            time.sleep(0.5)

        except requests.Timeout:
            stats["errors"] += 1
            time.sleep(2)
        except Exception as e:
            logger.warning(f"UK tariff fetch error for {code}: {e}")
            stats["errors"] += 1
            time.sleep(1)

    print(f"  [Stream 6] Done: {stats['fetched']} fetched, "
          f"{stats['not_found']} not found, {stats['errors']} errors")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 7: CROSS-REFERENCE ENGINE
# ═══════════════════════════════════════════════════════════════

def stream_7_cross_reference(db, tracker):
    """
    For each HS code: link to chapter notes, UK data, emails, patterns,
    corrections, AI enrichments. Calculate knowledge_completeness score.
    Cost: ~$0.00 (Firestore only).
    """
    print("  [Stream 7] Cross-reference engine starting...")
    stats = {"codes_processed": 0, "avg_completeness": 0, "errors": 0}

    # Get all HS codes from tariff + classifications
    all_codes = set()
    try:
        items = list(db.collection("tariff").stream())
        tracker.record_firestore_ops(reads=len(items))
        for item in items:
            code = item.to_dict().get("hs_code", "")
            if _validate_hs_format(code):
                all_codes.add(code)
    except Exception:
        pass

    try:
        cls_docs = list(db.collection("rcb_classifications").stream())
        tracker.record_firestore_ops(reads=len(cls_docs))
        for doc in cls_docs:
            code = doc.to_dict().get("hs_code", "")
            if code and _validate_hs_format(code):
                all_codes.add(code)
    except Exception:
        pass

    # Pre-load collections for fast lookup (avoid N+1 queries)
    chapter_notes_set = set()
    try:
        for doc in db.collection("chapter_notes").stream():
            chapter_notes_set.add(doc.id)
        tracker.record_firestore_ops(reads=len(chapter_notes_set))
    except Exception:
        pass

    uk_codes_set = set()
    try:
        for doc in db.collection("tariff_uk").stream():
            data = doc.to_dict()
            if data.get("status") != "not_found_in_uk":
                uk_codes_set.add(data.get("il_code", ""))
        tracker.record_firestore_ops(reads=len(uk_codes_set))
    except Exception:
        pass

    ai_enriched_set = set()
    try:
        for doc in db.collection("ai_knowledge_enrichments").stream():
            ai_enriched_set.add(doc.to_dict().get("hs_code", ""))
        tracker.record_firestore_ops(reads=len(ai_enriched_set))
    except Exception:
        pass

    patterns_by_code = defaultdict(int)
    try:
        for doc in db.collection("learned_patterns").stream():
            code = doc.to_dict().get("hs_code", "")
            if code:
                patterns_by_code[code] += 1
        tracker.record_firestore_ops(reads=sum(patterns_by_code.values()))
    except Exception:
        pass

    corrections_by_code = defaultdict(int)
    try:
        for doc in db.collection("learned_corrections").stream():
            code = doc.to_dict().get("corrected_code", "")
            if code:
                corrections_by_code[code] += 1
        tracker.record_firestore_ops(reads=sum(corrections_by_code.values()))
    except Exception:
        pass

    # Process each code — limit to avoid timeout
    completeness_scores = []
    now = datetime.now(timezone.utc).isoformat()

    for code in list(all_codes)[:500]:
        if tracker.is_over_budget:
            break

        clean = code.replace(".", "").replace("/", "").replace(" ", "")
        chapter = clean[:2].zfill(2)

        has_chapter_note = f"chapter_{chapter}" in chapter_notes_set
        has_uk = code in uk_codes_set
        has_ai = code in ai_enriched_set
        has_patterns = patterns_by_code.get(code, 0) > 0
        has_corrections = corrections_by_code.get(code, 0) > 0

        total_sources = sum([
            has_chapter_note, has_uk, has_ai, has_patterns,
        ])
        completeness = round(total_sources / 4 * 100)
        completeness_scores.append(completeness)

        crossref = {
            "hs_code": code,
            "chapter": chapter,
            "has_chapter_note": has_chapter_note,
            "has_uk_tariff": has_uk,
            "has_ai_enrichment": has_ai,
            "learned_pattern_count": patterns_by_code.get(code, 0),
            "correction_count": corrections_by_code.get(code, 0),
            "knowledge_completeness": completeness,
            "updated_at": now,
        }

        try:
            doc_id = clean[:10]
            db.collection("hs_code_crossref").document(doc_id).set(crossref)
            tracker.record_firestore_ops(writes=1)
            stats["codes_processed"] += 1
        except Exception:
            stats["errors"] += 1

    if completeness_scores:
        stats["avg_completeness"] = round(sum(completeness_scores) / len(completeness_scores), 1)

    print(f"  [Stream 7] Done: {stats['codes_processed']} codes, "
          f"avg completeness {stats['avg_completeness']}%")
    return stats


# ═══════════════════════════════════════════════════════════════
#  STREAM 8: SELF-TEACH FROM PATTERNS
# ═══════════════════════════════════════════════════════════════

def stream_8_self_teach(db, gemini_key, tracker):
    """
    Analyze learned_patterns + learned_corrections -> generate per-chapter:
    classification rules, common mistakes, decision keywords, exclusion keywords.
    Cost: ~$0.02
    """
    print("  [Stream 8] Self-teach from patterns starting...")
    stats = {"chapters_taught": 0, "rules_generated": 0, "errors": 0}

    # Read all patterns and corrections
    try:
        patterns = list(db.collection("learned_patterns").stream())
        corrections = list(db.collection("learned_corrections").stream())
        tracker.record_firestore_ops(reads=len(patterns) + len(corrections))
    except Exception as e:
        logger.error(f"Stream 8: Failed to read patterns/corrections: {e}")
        return stats

    # Group by chapter
    chapter_patterns = defaultdict(list)
    for doc in patterns:
        data = doc.to_dict()
        code = data.get("hs_code", "")
        if code:
            clean = code.replace(".", "").replace("/", "")
            chapter = clean[:2].zfill(2)
            chapter_patterns[chapter].append(data)

    correction_data = []
    for doc in corrections:
        correction_data.append(doc.to_dict())

    now = datetime.now(timezone.utc).isoformat()

    for chapter, pats in chapter_patterns.items():
        if len(pats) < 3 or tracker.is_over_budget:
            continue

        chapter_corrections = [
            c for c in correction_data
            if c.get("corrected_code", "").replace(".", "").replace("/", "")[:2] == chapter
        ]

        result = call_gemini_tracked(
            gemini_key,
            f"""Expert Israeli customs classifier — Chapter {chapter} analysis.

Products classified here:
{json.dumps([{"product": p.get("product", ""), "code": p.get("hs_code", ""), "reasoning": p.get("reasoning", "")} for p in pats[:20]], ensure_ascii=False)}

Corrections made:
{json.dumps([{"product": c.get("product", ""), "wrong": c.get("original_code", ""), "right": c.get("corrected_code", ""), "reason": c.get("reason", "")} for c in chapter_corrections[:10]], ensure_ascii=False)}

Generate JSON:
- classification_rules: 3-5 rules for this chapter (Hebrew)
- common_mistakes: misclassification errors to watch for
- decision_keywords: Hebrew/English keywords that indicate this chapter
- exclusion_keywords: keywords that indicate NOT this chapter
- typical_products: product types in this chapter""",
            tracker,
            max_tokens=1500,
        )

        if not result or not isinstance(result, dict):
            continue

        try:
            db.collection("chapter_classification_rules").document(f"chapter_{chapter}").set({
                "chapter": chapter,
                "rules": result.get("classification_rules", []),
                "common_mistakes": result.get("common_mistakes", []),
                "decision_keywords": result.get("decision_keywords", []),
                "exclusion_keywords": result.get("exclusion_keywords", []),
                "typical_products": result.get("typical_products", []),
                "generated_from_patterns": len(pats),
                "generated_from_corrections": len(chapter_corrections),
                "generated_at": now,
                "source": "self_taught",
            })
            stats["chapters_taught"] += 1
            stats["rules_generated"] += len(result.get("classification_rules", []))

            # Add decision keywords to keyword_index
            for kw in result.get("decision_keywords", []):
                try:
                    k_id = _safe_doc_id(str(kw))
                    k_ref = db.collection("keyword_index").document(k_id)
                    if not k_ref.get().exists:
                        k_ref.set({
                            "keyword": str(kw),
                            "codes": [],
                            "count": 0,
                            "built_at": now,
                            "updated_at": now,
                        })
                except Exception:
                    pass

            tracker.record_firestore_ops(writes=1 + len(result.get("decision_keywords", [])))
        except Exception:
            stats["errors"] += 1

    print(f"  [Stream 8] Done: {stats['chapters_taught']} chapters, "
          f"{stats['rules_generated']} rules generated")
    return stats


# ═══════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_overnight_brain(db, get_secret_func):
    """
    Master orchestrator. HARD CAP: $3.50.
    Runs all 8 enrichment streams in priority order.
    """
    tracker = CostTracker()
    t0 = time.time()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 60)
    print("  OVERNIGHT BRAIN EXPLOSION")
    print(f"  Time: {now_str} UTC")
    print(f"  Budget: ${tracker.BUDGET_LIMIT} (hard cap)")
    print("=" * 60)

    # Get Gemini API key
    gemini_key = None
    try:
        gemini_key = get_secret_func("GEMINI_API_KEY")
    except Exception as e:
        logger.error(f"Failed to get GEMINI_API_KEY: {e}")

    all_stats = {}

    # ── Phase A: FREE first (UK API sweep) ──
    print("\n--- Phase A: Free API sweep ---")
    try:
        all_stats["stream_6_uk_tariff"] = stream_6_uk_tariff_sweep(db, tracker)
    except Exception as e:
        logger.error(f"Stream 6 error: {e}")
        all_stats["stream_6_uk_tariff"] = {"error": str(e)}
    print(f"  Budget after Phase A: ${tracker.total_spent:.4f}")

    # ── Phase B: High-value AI streams ──
    print("\n--- Phase B: High-value AI streams ---")
    try:
        all_stats["stream_3_cc_learning"] = stream_3_cc_email_learning(db, gemini_key, tracker)
    except Exception as e:
        logger.error(f"Stream 3 error: {e}")
        all_stats["stream_3_cc_learning"] = {"error": str(e)}

    if not tracker.is_over_budget:
        try:
            all_stats["stream_1_tariff_mine"] = stream_1_tariff_deep_mine(db, gemini_key, tracker)
        except Exception as e:
            logger.error(f"Stream 1 error: {e}")
            all_stats["stream_1_tariff_mine"] = {"error": str(e)}

    if not tracker.is_over_budget:
        try:
            all_stats["stream_2_email_mine"] = stream_2_email_archive_mine(db, gemini_key, tracker)
        except Exception as e:
            logger.error(f"Stream 2 error: {e}")
            all_stats["stream_2_email_mine"] = {"error": str(e)}

    print(f"  Budget after Phase B: ${tracker.total_spent:.4f}")

    # ── Phase C: Bulk processing (skip if tight) ──
    if not tracker.is_over_budget:
        print("\n--- Phase C: Bulk processing ---")
        try:
            all_stats["stream_4_attachments"] = stream_4_attachment_mine(db, gemini_key, tracker)
        except Exception as e:
            logger.error(f"Stream 4 error: {e}")
            all_stats["stream_4_attachments"] = {"error": str(e)}

        if not tracker.is_over_budget:
            try:
                all_stats["stream_5_ai_fill"] = stream_5_ai_knowledge_fill(db, gemini_key, tracker)
            except Exception as e:
                logger.error(f"Stream 5 error: {e}")
                all_stats["stream_5_ai_fill"] = {"error": str(e)}

        print(f"  Budget after Phase C: ${tracker.total_spent:.4f}")

    # ── Phase D: Cross-reference (Firestore only) ──
    if not tracker.is_over_budget:
        print("\n--- Phase D: Cross-reference ---")
        try:
            all_stats["stream_7_crossref"] = stream_7_cross_reference(db, tracker)
        except Exception as e:
            logger.error(f"Stream 7 error: {e}")
            all_stats["stream_7_crossref"] = {"error": str(e)}

    # ── Phase E: Self-teach ──
    if not tracker.is_over_budget:
        print("\n--- Phase E: Self-teach ---")
        try:
            all_stats["stream_8_self_teach"] = stream_8_self_teach(db, gemini_key, tracker)
        except Exception as e:
            logger.error(f"Stream 8 error: {e}")
            all_stats["stream_8_self_teach"] = {"error": str(e)}

    # ── Final audit ──
    print("\n--- Final Knowledge Audit ---")
    audit = _final_knowledge_audit(db, tracker)
    cost_summary = tracker.summary()
    total_time = round(time.time() - t0, 1)

    # Save enrichment report
    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": total_time,
        "cost": cost_summary,
        "audit": audit,
        "stream_stats": all_stats,
    }

    try:
        doc_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        db.collection("enrichment_reports").document(doc_id).set(report)
    except Exception as e:
        logger.error(f"Failed to save enrichment report: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("  OVERNIGHT BRAIN EXPLOSION — COMPLETE")
    print(f"  Duration: {total_time}s")
    print(f"  Cost: ${cost_summary['total_spent']:.4f} / ${tracker.BUDGET_LIMIT}")
    print(f"  AI calls: {cost_summary['gemini_calls']}")
    print(f"  Firestore: {cost_summary['firestore_reads']} reads, {cost_summary['firestore_writes']} writes")
    print(f"  Budget stopped: {cost_summary['stopped_by_budget']}")

    if audit:
        print("\n  Knowledge Audit:")
        for key, val in audit.items():
            print(f"    {key}: {val}")

    print("=" * 60)

    return report


def _final_knowledge_audit(db, tracker):
    """Count key collections for the final audit report."""
    audit = {}

    collections_to_count = [
        "tariff", "keyword_index", "product_index", "supplier_index",
        "learned_patterns", "learned_corrections", "tariff_uk",
        "ai_knowledge_enrichments", "chapter_classification_rules",
        "hs_code_crossref", "brain_index",
    ]

    for coll_name in collections_to_count:
        try:
            count = len(list(db.collection(coll_name).limit(10000).stream()))
            audit[coll_name] = count
            tracker.record_firestore_ops(reads=count)
        except Exception:
            audit[coll_name] = "error"

    # Count knowledge gaps by status
    try:
        open_gaps = len(list(
            db.collection("knowledge_gaps")
            .where("status", "==", "open")
            .stream()
        ))
        audit["knowledge_gaps_open"] = open_gaps
    except Exception:
        audit["knowledge_gaps_open"] = "error"

    try:
        filled_gaps = len(list(
            db.collection("knowledge_gaps")
            .where("status", "in", ["filled", "filled_by_ai"])
            .stream()
        ))
        audit["knowledge_gaps_filled"] = filled_gaps
    except Exception:
        audit["knowledge_gaps_filled"] = "error"

    return audit
