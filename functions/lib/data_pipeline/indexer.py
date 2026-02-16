"""
Step 4: INDEX — Make structured documents searchable.

After storing a document in its collection, add it to:
1. librarian_index — master searchable index
2. keyword_index — term-to-HS-code mapping

Integrates with existing librarian_index.py infrastructure.

Session 27 — Assignment 14C
"""

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("rcb.pipeline.indexer")


def index_document(db, collection, doc_id, doc):
    """
    Index a structured document for search.

    Adds entries to:
    1. librarian_index — via existing index_single_document()
    2. keyword_index — every key_term maps to HS codes in this document

    Args:
        db: Firestore client
        collection: str — Firestore collection name
        doc_id: str — document ID
        doc: dict — the structured document data

    Returns:
        dict with indexing results
    """
    results = {"librarian_indexed": False, "keywords_indexed": 0, "hs_codes_indexed": 0}

    # 1. Add to librarian_index
    try:
        from lib.librarian_index import index_single_document
        results["librarian_indexed"] = index_single_document(db, collection, doc_id, doc)
    except Exception as e:
        logger.warning(f"Librarian indexing failed for {collection}/{doc_id}: {e}")

    # 2. Add to keyword_index
    key_terms = doc.get("key_terms", [])
    hs_codes = _gather_hs_codes(doc)

    if key_terms and hs_codes:
        for term in key_terms[:20]:
            try:
                _add_to_keyword_index(db, term, hs_codes, collection, doc_id)
                results["keywords_indexed"] += 1
            except Exception as e:
                logger.debug(f"Keyword index error for '{term}': {e}")

    # 3. Add HS code cross-references
    all_hs = _gather_all_hs_mentions(doc)
    for code in all_hs[:20]:
        try:
            _add_hs_code_reference(db, code, collection, doc_id, doc)
            results["hs_codes_indexed"] += 1
        except Exception as e:
            logger.debug(f"HS code index error for '{code}': {e}")

    return results


def _gather_hs_codes(doc):
    """Extract primary HS codes from a structured document."""
    codes = []

    for field in ("hs_code", "hs_code_assigned"):
        val = doc.get(field, "")
        if val:
            codes.append(str(val))

    return codes


def _gather_all_hs_mentions(doc):
    """Gather all HS codes mentioned anywhere in the document."""
    codes = set()

    for field in ("hs_code", "hs_code_assigned", "hs_codes_mentioned",
                  "hs_codes_discussed", "applicable_codes"):
        val = doc.get(field)
        if isinstance(val, str) and val:
            codes.add(val)
        elif isinstance(val, list):
            for item in val:
                if item:
                    codes.add(str(item))

    return list(codes)


def _add_to_keyword_index(db, term, hs_codes, collection, doc_id):
    """
    Add a keyword → HS code mapping to keyword_index.

    Merges with existing entries: if keyword already exists,
    adds new codes or increases weight of existing ones.
    """
    safe_term = re.sub(r'[^\w\u0590-\u05FF]', '_', term.lower().strip())
    if not safe_term or len(safe_term) < 2:
        return

    doc_ref = db.collection("keyword_index").document(safe_term)
    existing = doc_ref.get()

    if existing.exists:
        data = existing.to_dict()
        existing_codes = data.get("codes", [])

        # Merge: increase weight for existing codes, add new ones
        code_map = {c["hs_code"]: c for c in existing_codes}
        for code in hs_codes:
            clean_code = code.replace(".", "").replace("/", "").replace(" ", "")
            if clean_code in code_map:
                code_map[clean_code]["weight"] = code_map[clean_code].get("weight", 1) + 1
            else:
                code_map[clean_code] = {
                    "hs_code": clean_code,
                    "weight": 2,  # Pipeline sources are authoritative
                    "source": collection,
                    "description": f"From {collection}/{doc_id}",
                }

        # Sort by weight, keep top 20
        sorted_codes = sorted(code_map.values(), key=lambda c: c.get("weight", 0), reverse=True)
        doc_ref.update({
            "codes": sorted_codes[:20],
            "count": len(sorted_codes[:20]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Create new entry
        codes_list = []
        for code in hs_codes:
            clean_code = code.replace(".", "").replace("/", "").replace(" ", "")
            codes_list.append({
                "hs_code": clean_code,
                "weight": 2,
                "source": collection,
                "description": f"From {collection}/{doc_id}",
            })

        doc_ref.set({
            "keyword": safe_term,
            "codes": codes_list[:20],
            "count": len(codes_list[:20]),
            "built_at": datetime.now(timezone.utc).isoformat(),
        })


def _add_hs_code_reference(db, hs_code, collection, doc_id, doc):
    """
    Add a reference from an HS code to a source document.
    Stored in hs_code_references collection for reverse lookup.
    """
    clean_code = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    if not clean_code or len(clean_code) < 4:
        return

    ref_id = f"{clean_code}__{collection}__{doc_id}"

    db.collection("hs_code_references").document(ref_id).set({
        "hs_code": clean_code,
        "collection": collection,
        "doc_id": doc_id,
        "source_type": collection,
        "title": (doc.get("title") or doc.get("product_description") or doc.get("summary", ""))[:200],
        "relevance": "direct_mention",
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }, merge=True)
