"""
RCB Smart Librarian - Central Knowledge Manager
Session 12: Enhanced with indexing, tagging, smart search, researcher, and reporting

The Librarian is the CENTRAL BRAIN of the RCB system:
- Knows everything (inventory & indexing)
- Finds anything (smart search & retrieval)
- Keeps learning (researcher & enrichment)
"""

import re
import time
from datetime import datetime, timezone

# ═══════════════════════════════════════════
#  SESSION 27: SEARCH CACHE (TTL-based)
# ═══════════════════════════════════════════

_SEARCH_CACHE = {}          # key -> (timestamp, result)
_CACHE_TTL_SEC = 300        # 5 minutes


def _cache_get(key):
    """Return cached result if within TTL, else None."""
    entry = _SEARCH_CACHE.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL_SEC:
        return entry[1]
    return None


def _cache_set(key, value):
    """Store result in cache with current timestamp."""
    _SEARCH_CACHE[key] = (time.time(), value)


def clear_search_cache():
    """Clear the entire search cache (call between classification runs)."""
    _SEARCH_CACHE.clear()


# ═══════════════════════════════════════════
#  SESSION 11 ORIGINALS (preserved)
# ═══════════════════════════════════════════

def extract_search_keywords(item_description):
    """Extract meaningful keywords from description"""
    stop_words = {'the', 'a', 'an', 'of', 'for', 'and', 'or', 'with', 'to', 'from', 
                  'in', 'on', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                  'את', 'של', 'על', 'עם', 'או', 'גם', 'כי', 'אם', 'לא', 'יש', 'זה'}
    
    words = item_description.lower().replace(',', ' ').replace('.', ' ').split()
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    return keywords[:10]


def search_collection_smart(db, collection_name, keywords, text_fields, max_results=50):
    """Smart search a single collection (with cache + word-boundary matching)."""
    keywords_lower = sorted(set(k.lower() for k in keywords if k))
    cache_key = f"{collection_name}|{'|'.join(keywords_lower)}|{'|'.join(text_fields)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:max_results]

    results = []

    try:
        docs = db.collection(collection_name).limit(500).stream()
        for doc in docs:
            data = doc.to_dict()

            search_text = ""
            for field in text_fields:
                val = data.get(field, "")
                if isinstance(val, str):
                    search_text += " " + val.lower()

            score = 0
            for kw in keywords_lower:
                # Word-boundary match for Latin, substring for Hebrew
                if any("\u0590" <= c <= "\u05FF" for c in kw):
                    if kw in search_text:
                        score += 1
                else:
                    if re.search(r'\b' + re.escape(kw) + r'\b', search_text):
                        score += 1

            if score > 0:
                results.append({
                    "doc_id": doc.id,
                    "score": score,
                    "data": data
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        _cache_set(cache_key, results)
        return results[:max_results]

    except Exception as e:
        print(f"    Error searching {collection_name}: {e}")
        return []


def search_tariff_codes(db, keywords):
    """Search for HS codes in tariff collections.
    Session 27: Searches product_index FIRST (highest signal for repeat items)."""
    results = []

    # Tier 0: product_index — best signal for repeat items (boosted score)
    print("    Searching product_index...")
    products = search_collection_smart(
        db, 'product_index', keywords,
        ['product_name', 'description', 'description_he'],
        max_results=10
    )
    for r in products:
        data = r["data"]
        hs = data.get('hs_code', '')
        if hs:
            results.append({
                "source": "product_index",
                "hs_code": hs,
                "description_he": data.get('description_he', data.get('product_name', '')),
                "description_en": data.get('description', data.get('product_name', '')),
                "chapter": "",
                "duty_rate": "",
                "score": r["score"] + 2  # Boost: learned product = high signal
            })

    print("    Searching tariff_chapters...")
    chapters = search_collection_smart(
        db, 'tariff_chapters', keywords,
        ['description_he', 'description_en', 'title', 'title_he', 'title_en', 'code'],
        max_results=30
    )
    for r in chapters:
        data = r["data"]
        results.append({
            "source": "tariff_chapters",
            "hs_code": data.get('code', data.get('hs_code', '')),
            "description_he": data.get('description_he', data.get('title_he', '')),
            "description_en": data.get('description_en', data.get('title_en', '')),
            "chapter": data.get('chapter', ''),
            "duty_rate": data.get('duty_rate', ''),
            "score": r["score"]
        })
    
    print("    🔍 Searching tariff...")
    tariff = search_collection_smart(
        db, 'tariff', keywords,
        ['description_he', 'description_en', 'hs_code'],
        max_results=20
    )
    for r in tariff:
        data = r["data"]
        results.append({
            "source": "tariff",
            "hs_code": data.get('hs_code', ''),
            "description_he": data.get('description_he', ''),
            "chapter": data.get('chapter', ''),
            "score": r["score"]
        })
    
    print("    🔍 Searching hs_code_index...")
    hs_index = search_collection_smart(
        db, 'hs_code_index', keywords,
        ['description', 'description_he', 'description_en', 'code', 'hs_code'],
        max_results=30
    )
    for r in hs_index:
        data = r["data"]
        results.append({
            "source": "hs_code_index",
            "hs_code": data.get('code', data.get('hs_code', '')),
            "description_he": data.get('description_he', data.get('description', '')),
            "score": r["score"]
        })
    
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:20]


def search_regulations(db, keywords):
    """Search regulatory requirements"""
    results = []
    
    collections = [
        ('ministry_index', ['ministry']),
        ('regulatory', ['title', 'content', 'description']),
        ('regulatory_approvals', ['ministry', 'type', 'description']),
        ('regulatory_certificates', ['name', 'ministry', 'type']),
        ('licensing_knowledge', ['content', 'title'])
    ]
    
    for coll_name, fields in collections:
        print(f"    🔍 Searching {coll_name}...")
        found = search_collection_smart(db, coll_name, keywords, fields, max_results=20)
        for r in found:
            results.append({
                "source": coll_name,
                "data": r["data"],
                "score": r["score"]
            })
    
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:15]


def search_pipeline_sources(db, keywords):
    """Search pipeline-ingested collections (directives, decisions, precedents, foreign tariffs)."""
    results = []

    collections = [
        ('classification_directives', ['title', 'summary', 'key_terms', 'directive_id']),
        ('pre_rulings', ['product_description', 'product_description_en', 'key_terms', 'ruling_id']),
        ('customs_decisions', ['product_description', 'key_terms', 'reasoning_summary']),
        ('court_precedents', ['case_name', 'ruling_summary', 'key_terms']),
        ('customs_ordinance', ['title', 'summary', 'key_terms']),
        ('customs_procedures', ['title', 'summary', 'key_terms']),
        ('cbp_rulings', ['description', 'key_terms']),
        ('bti_decisions', ['description', 'key_terms']),
    ]

    for coll_name, fields in collections:
        try:
            found = search_collection_smart(db, coll_name, keywords, fields, max_results=10)
            for r in found:
                results.append({
                    "source": coll_name,
                    "data": r["data"],
                    "score": r["score"]
                })
        except Exception:
            pass  # Collection may not exist yet

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:15]


def search_procedures_and_rules(db, keywords):
    """Search procedures and classification rules"""
    results = []
    
    print("    🔍 Searching procedures...")
    procs = search_collection_smart(
        db, 'procedures', keywords,
        ['name', 'content', 'title', 'type'],
        max_results=20
    )
    for r in procs:
        results.append({"source": "procedures", "data": r["data"], "score": r["score"]})
    
    print("    🔍 Searching classification_rules...")
    rules = search_collection_smart(
        db, 'classification_rules', keywords + ['סיווג', 'כללי', 'פרשנות'],
        ['he', 'en', 'source', 'rule'],
        max_results=20
    )
    for r in rules:
        results.append({"source": "classification_rules", "data": r["data"], "score": r["score"]})
    
    print("    🔍 Searching classification_knowledge...")
    ck = search_collection_smart(
        db, 'classification_knowledge', keywords,
        ['content', 'title', 'rule', 'description'],
        max_results=20
    )
    for r in ck:
        results.append({"source": "classification_knowledge", "data": r["data"], "score": r["score"]})
    
    return results


def search_knowledge_base(db, keywords):
    """Search general knowledge collections"""
    results = []
    
    collections = [
        ('knowledge', ['title', 'content', 'source']),
        ('knowledge_base', ['title', 'content', 'source']),
        ('legal_references', ['title', 'content']),
        ('legal_documents', ['title', 'content', 'name'])
    ]
    
    for coll_name, fields in collections:
        print(f"    🔍 Searching {coll_name}...")
        found = search_collection_smart(db, coll_name, keywords, fields, max_results=15)
        for r in found:
            results.append({
                "source": coll_name,
                "data": r["data"],
                "score": r["score"]
            })
    
    return results


def search_history(db, keywords):
    """Search previous classifications and declarations"""
    results = []
    
    print("    🔍 Searching classifications history...")
    classes = search_collection_smart(
        db, 'classifications', keywords,
        ['description', 'hs_code', 'item'],
        max_results=20
    )
    for r in classes:
        results.append({"source": "classifications", "data": r["data"], "score": r["score"]})
    
    print("    🔍 Searching declarations...")
    decl = search_collection_smart(
        db, 'declarations', keywords,
        ['description', 'item', 'hs_code'],
        max_results=15
    )
    for r in decl:
        results.append({"source": "declarations", "data": r["data"], "score": r["score"]})
    
    print("    🔍 Searching rcb_classifications...")
    rcb = search_collection_smart(
        db, 'rcb_classifications', keywords,
        ['subject'],
        max_results=10
    )
    for r in rcb:
        results.append({"source": "rcb_classifications", "data": r["data"], "score": r["score"]})
    
    return results


def _dedup_results(results_list, key_func=None):
    """Remove duplicate results. key_func(item) -> unique key string."""
    if not key_func:
        def key_func(item):
            # Default: dedup by hs_code or doc_id or data title
            hs = item.get("hs_code", "")
            if hs:
                return hs
            doc_id = item.get("doc_id", "")
            if doc_id:
                return doc_id
            data = item.get("data", {})
            return data.get("title", "") or str(data)[:80]
    seen = set()
    deduped = []
    for item in results_list:
        k = key_func(item)
        if k and k not in seen:
            seen.add(k)
            deduped.append(item)
    return deduped


def full_knowledge_search(db, query_terms, item_description=""):
    """
    Complete phased search across ALL knowledge.
    Session 27: Added cache, word-boundary matching, dedup, tiered search.
    Phase 1: Extract keywords and search all sources
    Phase 2: If low results, expand with learned knowledge
    """
    print("  📚 LIBRARIAN: Starting comprehensive search...")

    all_terms = query_terms if isinstance(query_terms, list) else [query_terms]
    if item_description:
        all_terms.extend(extract_search_keywords(item_description))

    keywords = list(set([t for t in all_terms if t and len(str(t)) > 2]))[:15]
    print(f"  📚 Keywords: {keywords[:5]}...")

    # Check full-query cache
    fks_cache_key = f"fks|{'|'.join(sorted(keywords))}"
    cached = _cache_get(fks_cache_key)
    if cached is not None:
        print("  📚 LIBRARIAN: Returning cached results")
        return cached

    results = {
        "tariff_codes": [],
        "regulations": [],
        "procedures_rules": [],
        "knowledge": [],
        "history": [],
        "similar_past": [],
        "confidence": "low"
    }

    try:
        # Phase 1: Tiered search — most valuable sources first
        # Tier 1: Product index + tariff (highest signal)
        results["tariff_codes"] = search_tariff_codes(db, keywords)

        # Early stop: if we have 5+ tariff hits, skip low-value sources
        tariff_found = len(results["tariff_codes"])

        # Tier 2: Regulations (always needed for compliance)
        results["regulations"] = search_regulations(db, keywords)

        # Tier 2b: Pipeline sources (directives, decisions, precedents)
        results["pipeline_sources"] = search_pipeline_sources(db, keywords)

        # Tier 3: Rules and knowledge (skip if we already have plenty)
        results["procedures_rules"] = search_procedures_and_rules(db, keywords)
        results["knowledge"] = search_knowledge_base(db, keywords)

        # Tier 4: History (only if we need more signal)
        total_so_far = sum(len(v) for v in results.values() if isinstance(v, list))
        if total_so_far < 15:
            results["history"] = search_history(db, keywords)

        # Phase 2: Search learned knowledge for similar past items
        if item_description:
            try:
                from .librarian_researcher import find_similar_classifications
                results["similar_past"] = find_similar_classifications(
                    db, item_description, limit=5
                )
                if results["similar_past"]:
                    print(f"    📚 Found {len(results['similar_past'])} similar past classifications")
            except ImportError:
                pass

        # Dedup each category
        results["tariff_codes"] = _dedup_results(
            results["tariff_codes"],
            lambda x: x.get("hs_code", "")
        )
        results["regulations"] = _dedup_results(
            results["regulations"],
            lambda x: x.get("data", {}).get("title", "") or x.get("source", "")
        )
        results["pipeline_sources"] = _dedup_results(
            results.get("pipeline_sources", []),
            lambda x: x.get("data", {}).get("title", "") or x.get("data", {}).get("directive_id", "") or x.get("source", "")
        )
        results["history"] = _dedup_results(
            results["history"],
            lambda x: x.get("data", {}).get("hs_code", "") or x.get("data", {}).get("description", "")[:60]
        )

        # Calculate confidence
        total_found = sum(len(v) for v in results.values() if isinstance(v, list))
        tariff_found = len(results["tariff_codes"])
        pipeline_found = len(results.get("pipeline_sources", []))
        similar_found = len(results.get("similar_past", []))

        if tariff_found >= 3 and total_found >= 10:
            results["confidence"] = "high"
        elif pipeline_found >= 2 and tariff_found >= 1:
            results["confidence"] = "high"
        elif tariff_found >= 1 and total_found >= 5:
            results["confidence"] = "medium"
        elif similar_found >= 2:
            results["confidence"] = "medium"
        else:
            results["confidence"] = "low"

        # Cache results
        _cache_set(fks_cache_key, results)

        # Log search for analytics
        _log_search(db, keywords, item_description, total_found, results["confidence"])

        print(f"  📚 LIBRARIAN: Found {total_found} docs, confidence: {results['confidence']}")

    except Exception as e:
        print(f"  Librarian error: {e}")
        import traceback
        traceback.print_exc()

    return results


# ═══════════════════════════════════════════
#  HS CODE FORMATTING & VALIDATION (Session 11)
# ═══════════════════════════════════════════

def get_israeli_hs_format(hs_code):
    """Convert HS code to Israeli format XX.XX.XXXX/XX"""
    code = str(hs_code).replace('.', '').replace(' ', '').replace('/', '')
    code = code.ljust(10, '0')[:10]

    if len(code) >= 8:
        return f"{code[:2]}.{code[2:4]}.{code[4:8]}/{code[8:10]}"
    return hs_code


def normalize_hs_code(hs_code):
    """Normalize HS code to 10 digits for comparison"""
    code = str(hs_code).replace('.', '').replace(' ', '').replace('/', '')
    return code.ljust(10, '0')[:10]


def validate_hs_code(db, hs_code):
    """
    Validate that an HS code exists in the tariff database.
    Returns: dict with {valid, exact_match, suggested_code, description, confidence}
    
    Session 11: Added to prevent agents from generating non-existent codes
    """
    normalized = normalize_hs_code(hs_code)
    chapter = normalized[:2]
    heading = normalized[:4]
    subheading = normalized[:6]
    
    result = {
        "valid": False,
        "exact_match": False,
        "input_code": hs_code,
        "normalized": normalized,
        "suggested_code": None,
        "suggested_description": None,
        "confidence": "none"
    }
    
    try:
        print(f"    🔍 Validating HS code: {get_israeli_hs_format(normalized)}")
        
        exact_matches = []
        partial_matches = []
        
        # Search tariff_chapters for exact match
        chapters_ref = db.collection('tariff_chapters').limit(1000).stream()
        for doc in chapters_ref:
            data = doc.to_dict()
            doc_code = normalize_hs_code(data.get('code', data.get('hs_code', '')))
            
            if doc_code == normalized:
                result["valid"] = True
                result["exact_match"] = True
                result["suggested_code"] = doc_code
                result["suggested_description"] = data.get('description_he', data.get('description_en', ''))
                result["confidence"] = "high"
                print(f"    ✅ Exact match found: {get_israeli_hs_format(doc_code)}")
                return result
            
            if doc_code[:6] == subheading:
                partial_matches.append({
                    "code": doc_code,
                    "description": data.get('description_he', data.get('description_en', '')),
                    "match_level": "subheading"
                })
            elif doc_code[:4] == heading:
                partial_matches.append({
                    "code": doc_code,
                    "description": data.get('description_he', data.get('description_en', '')),
                    "match_level": "heading"
                })
        
        # Check tariff collection
        tariff_ref = db.collection('tariff').limit(500).stream()
        for doc in tariff_ref:
            data = doc.to_dict()
            doc_code = normalize_hs_code(data.get('hs_code', ''))
            
            if doc_code == normalized:
                result["valid"] = True
                result["exact_match"] = True
                result["suggested_code"] = doc_code
                result["suggested_description"] = data.get('description_he', '')
                result["confidence"] = "high"
                print(f"    ✅ Exact match in tariff: {get_israeli_hs_format(doc_code)}")
                return result
            
            if doc_code[:6] == subheading:
                partial_matches.append({
                    "code": doc_code,
                    "description": data.get('description_he', ''),
                    "match_level": "subheading"
                })
        
        # Check hs_code_index
        hs_index_ref = db.collection('hs_code_index').limit(500).stream()
        for doc in hs_index_ref:
            data = doc.to_dict()
            doc_code = normalize_hs_code(data.get('code', data.get('hs_code', '')))
            
            if doc_code == normalized:
                result["valid"] = True
                result["exact_match"] = True
                result["suggested_code"] = doc_code
                result["suggested_description"] = data.get('description_he', data.get('description', ''))
                result["confidence"] = "high"
                print(f"    ✅ Exact match in hs_code_index: {get_israeli_hs_format(doc_code)}")
                return result
        
        # If no exact match, suggest best partial match
        if partial_matches:
            subheading_matches = [m for m in partial_matches if m["match_level"] == "subheading"]
            if subheading_matches:
                best = subheading_matches[0]
                result["valid"] = True
                result["exact_match"] = False
                result["suggested_code"] = best["code"]
                result["suggested_description"] = best["description"]
                result["confidence"] = "medium"
                print(f"    ⚠️ No exact match. Suggested: {get_israeli_hs_format(best['code'])}")
            else:
                best = partial_matches[0]
                result["valid"] = True
                result["exact_match"] = False
                result["suggested_code"] = best["code"]
                result["suggested_description"] = best["description"]
                result["confidence"] = "low"
                print(f"    ⚠️ Partial match only. Suggested: {get_israeli_hs_format(best['code'])}")
        else:
            print(f"    ❌ HS code not found in database: {get_israeli_hs_format(normalized)}")
        
        return result
        
    except Exception as e:
        print(f"    ❌ Error validating HS code: {e}")
        return result


def validate_and_correct_classifications(db, classifications):
    """
    Validate all HS codes in a classification result and correct if needed.
    """
    validated = []
    
    for classification in classifications:
        hs_code = classification.get('hs_code', '')
        if not hs_code:
            validated.append(classification)
            continue
        
        validation = validate_hs_code(db, hs_code)
        
        classification['hs_validated'] = validation['valid']
        classification['hs_exact_match'] = validation['exact_match']
        classification['validation_confidence'] = validation['confidence']
        
        if not validation['exact_match'] and validation['suggested_code']:
            classification['original_hs_code'] = hs_code
            classification['hs_code'] = validation['suggested_code']
            classification['hs_corrected'] = True
            classification['correction_note'] = f"קוד מקורי {get_israeli_hs_format(hs_code)} תוקן ל-{get_israeli_hs_format(validation['suggested_code'])}"
            
            if classification.get('confidence') == 'גבוהה':
                classification['confidence'] = 'בינונית'
        
        if not validation['valid']:
            classification['hs_warning'] = f"⚠️ קוד HS לא נמצא במאגר: {get_israeli_hs_format(hs_code)}"
            classification['confidence'] = 'נמוכה'
        
        validated.append(classification)
    
    return validated


def build_classification_context(librarian_results):
    """Build context string for classification agent"""
    context = []
    
    # Tariff codes (most important)
    if librarian_results.get("tariff_codes"):
        context.append("=== קודי תעריף מכס רלוונטיים ===")
        for t in librarian_results["tariff_codes"][:10]:
            hs = get_israeli_hs_format(t.get("hs_code", ""))
            desc = t.get("description_he") or t.get("description_en", "")
            context.append(f"קוד: {hs}")
            context.append(f"תיאור: {desc}")
            if t.get("duty_rate"):
                context.append(f"מכס: {t['duty_rate']}")
            context.append(f"(ציון התאמה: {t.get('score', 0)})")
            context.append("")
    
    # Similar past classifications (Session 12 - NEW)
    if librarian_results.get("similar_past"):
        context.append("\n=== סיווגים דומים מהעבר ===")
        for s in librarian_results["similar_past"][:5]:
            hs = get_israeli_hs_format(s.get("hs_code", ""))
            desc = s.get("description", "")
            context.append(f"קוד: {hs}")
            context.append(f"תיאור: {desc}")
            context.append(f"(ציון דמיון: {s.get('score', 0)}, שימושים: {s.get('usage_count', 0)})")
            if s.get("is_correction"):
                context.append("⚠️ מבוסס על תיקון - קוד מתוקן!")
            context.append("")
    
    # Regulations
    if librarian_results.get("regulations"):
        context.append("\n=== דרישות רגולטוריות ===")
        for r in librarian_results["regulations"][:8]:
            data = r.get("data", {})
            context.append(f"- מקור: {r.get('source', '')}")
            if data.get("ministry"):
                context.append(f"  משרד: {data['ministry']}")
            context.append("")
    
    # Procedures and rules
    if librarian_results.get("procedures_rules"):
        context.append("\n=== כללי סיווג ונהלים ===")
        for r in librarian_results["procedures_rules"][:5]:
            data = r.get("data", {})
            if data.get("he"):
                context.append(f"- {data['he']}")
            elif data.get("name"):
                context.append(f"- {data['name']}")
            if data.get("source"):
                context.append(f"  מקור: {data['source']}")
    
    # Confidence indicator
    context.append(f"\n=== רמת ודאות הספרייה: {librarian_results.get('confidence', 'unknown')} ===")
    
    return "\n".join(context)


# ═══════════════════════════════════════════
#  SESSION 12: NEW SMART SEARCH FUNCTIONS
# ═══════════════════════════════════════════

def find_by_hs_code(db, hs_code):
    """
    Find ALL information related to a specific HS code.
    Searches across tariff, regulatory, and history collections.

    Args:
        db: Firestore client
        hs_code: str - HS code to search for

    Returns:
        Dict with tariff info, regulations, history, and related docs
    """
    normalized = normalize_hs_code(hs_code)
    chapter = normalized[:2]
    heading = normalized[:4]
    
    print(f"  📚 LIBRARIAN: Finding all info for HS {get_israeli_hs_format(normalized)}...")
    
    result = {
        "hs_code": normalized,
        "formatted": get_israeli_hs_format(normalized),
        "tariff_data": None,
        "regulations": [],
        "history": [],
        "related_codes": [],
        "validation": None,
    }
    
    # 1. Validate the code
    result["validation"] = validate_hs_code(db, hs_code)
    
    # 2. Find tariff data
    keywords = [normalized, heading, chapter, hs_code]
    tariff_results = search_tariff_codes(db, keywords)
    if tariff_results:
        result["tariff_data"] = tariff_results[0]
        result["related_codes"] = tariff_results[1:5]
    
    # 3. Find regulations for this HS code
    result["regulations"] = search_regulations(db, keywords)
    
    # 4. Find history
    result["history"] = search_history(db, keywords)
    
    # 5. Search the index for related documents
    try:
        index_results = db.collection("librarian_index") \
            .where("hs_codes", "array_contains", normalized) \
            .limit(10).stream()
        
        for doc in index_results:
            data = doc.to_dict()
            result["related_codes"].append({
                "source": data.get("collection", "librarian_index"),
                "title": data.get("title", ""),
                "tags": data.get("tags", []),
            })
    except Exception:
        pass
    
    return result


def find_by_ministry(db, ministry):
    """
    Find all regulations, certificates, and requirements for a ministry.

    Args:
        db: Firestore client
        ministry: str - Ministry name (Hebrew or English)

    Returns:
        List of related documents and requirements
    """
    print(f"  📚 LIBRARIAN: Finding all info for ministry: {ministry}...")
    
    keywords = [ministry]
    ministry_lower = ministry.lower()
    
    # Add Hebrew keywords for known ministries
    ministry_keywords = {
        "health": ["בריאות", "health", "רפואי", "medical"],
        "בריאות": ["בריאות", "health", "רפואי", "medical"],
        "economy": ["כלכלה", "economy", "ייבוא", "import"],
        "כלכלה": ["כלכלה", "economy", "ייבוא", "import"],
        "agriculture": ["חקלאות", "agriculture", "צמחי", "plant", "veterinary"],
        "חקלאות": ["חקלאות", "agriculture", "צמחי", "plant"],
        "defense": ["ביטחון", "defense", "דו-שימושי", "dual-use"],
        "ביטחון": ["ביטחון", "defense", "דו-שימושי"],
        "transport": ["תחבורה", "transport", "רכב", "vehicle"],
        "תחבורה": ["תחבורה", "transport", "רכב"],
    }
    
    for key, extra_kw in ministry_keywords.items():
        if key in ministry_lower:
            keywords.extend(extra_kw)
            break
    
    results = search_regulations(db, list(set(keywords)))
    
    # Also search the index
    try:
        index_results = db.collection("librarian_index") \
            .where("ministries", "array_contains", ministry) \
            .limit(20).stream()
        
        for doc in index_results:
            data = doc.to_dict()
            results.append({
                "source": f"librarian_index ({data.get('collection', '')})",
                "data": data,
                "score": 1,
            })
    except Exception:
        pass
    
    return results


def find_by_tags(db, tags):
    """
    Find documents matching ALL specified tags.

    Args:
        db: Firestore client
        tags: List[str] - Tags to match

    Returns:
        List of matching documents
    """
    print(f"  📚 LIBRARIAN: Searching by tags: {tags}...")
    results = []
    
    try:
        # Firestore can only do array_contains for one element
        # So we filter the first tag in query and the rest in Python
        if not tags:
            return []
        
        query = db.collection("librarian_index") \
            .where("tags", "array_contains", tags[0]) \
            .limit(100)
        
        for doc in query.stream():
            data = doc.to_dict()
            doc_tags = set(data.get("tags", []))
            
            # Check all requested tags are present
            if all(t in doc_tags for t in tags):
                results.append({
                    "id": doc.id,
                    "title": data.get("title", ""),
                    "collection": data.get("collection", ""),
                    "tags": data.get("tags", []),
                    "hs_codes": data.get("hs_codes", []),
                    "description": data.get("description", ""),
                })
        
        print(f"    📚 Found {len(results)} documents with tags {tags}")
    except Exception as e:
        print(f"    ❌ Error searching by tags: {e}")
    
    return results


def smart_search(db, query, limit=20):
    """
    Unified smart search — searches the librarian_index first,
    then falls back to collection-level search.
    Session 27: Added cache, dedup, early stopping.

    Args:
        db: Firestore client
        query: str - Search query (Hebrew or English)
        limit: int - Max results

    Returns:
        List of matching documents with scores
    """
    print(f"  📚 LIBRARIAN: Smart search for '{query}'...")

    keywords = extract_search_keywords(query)
    if not keywords:
        keywords = [query]

    # Check cache
    ss_cache_key = f"ss|{'|'.join(sorted(keywords))}|{limit}"
    cached = _cache_get(ss_cache_key)
    if cached is not None:
        return cached

    results = []
    seen_ids = set()

    # 1. Search librarian_index first (fastest, most comprehensive)
    try:
        index_results = search_collection_smart(
            db, "librarian_index", keywords,
            ["title", "description", "keywords_he", "keywords_en"],
            max_results=limit
        )

        for r in index_results:
            data = r["data"]
            doc_key = data.get("id", r["doc_id"])
            if doc_key not in seen_ids:
                seen_ids.add(doc_key)
                results.append({
                    "id": doc_key,
                    "title": data.get("title", ""),
                    "collection": data.get("collection", ""),
                    "tags": data.get("tags", []),
                    "hs_codes": data.get("hs_codes", []),
                    "score": r["score"] * 1.5,  # Boost indexed results
                    "source": "librarian_index",
                })
    except Exception:
        pass

    # 2. Early stop: if index gave enough high-quality results, skip fallback
    if len(results) < limit // 2:
        fallback = full_knowledge_search(db, keywords, query)

        for category in ["tariff_codes", "regulations", "procedures_rules", "knowledge", "history"]:
            for item in fallback.get(category, []):
                item_id = str(item.get("hs_code", item.get("data", {}).get("title", "")))[:50]
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append({
                        "id": item_id,
                        "title": item.get("description_he", "") or str(item.get("data", {}).get("title", "")),
                        "collection": item.get("source", category),
                        "score": item.get("score", 0),
                        "source": "direct_search",
                    })
    
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    final = results[:limit]

    # Cache and log
    _cache_set(ss_cache_key, final)
    _log_search(db, keywords, query, len(final), "smart_search")

    return final


# ═══════════════════════════════════════════
#  SESSION 12: DOCUMENT LOCATION
# ═══════════════════════════════════════════

def get_document_location(db, doc_id):
    """
    Get the exact location of a document (collection + path).

    Args:
        db: Firestore client
        doc_id: str - Document ID (can be index ID or raw doc ID)

    Returns:
        str - Document location description
    """
    # Try librarian_index first
    try:
        index_doc = db.collection("librarian_index").document(doc_id).get()
        if index_doc.exists:
            data = index_doc.to_dict()
            collection = data.get("collection", "")
            original_id = data.get("original_doc_id", "")
            file_path = data.get("file_path", "")
            
            location = f"{collection}/{original_id}"
            if file_path:
                location += f" (file: {file_path})"
            return location
    except Exception:
        pass
    
    # Search across all known collections
    from .librarian_index import COLLECTION_FIELDS
    for coll_name in COLLECTION_FIELDS:
        try:
            doc = db.collection(coll_name).document(doc_id).get()
            if doc.exists:
                return f"{coll_name}/{doc_id}"
        except Exception:
            continue
    
    return f"Document '{doc_id}' not found"


def get_all_locations_for(db, query):
    """
    Find all document locations matching a query.

    Args:
        db: Firestore client
        query: str - Search query

    Returns:
        List[str] - Document location strings
    """
    results = smart_search(db, query, limit=10)
    locations = []
    
    for r in results:
        collection = r.get("collection", "")
        doc_id = r.get("id", "")
        title = r.get("title", "")
        
        loc = f"{collection}/{doc_id}"
        if title:
            loc += f" — {title[:60]}"
        locations.append(loc)
    
    return locations


# ═══════════════════════════════════════════
#  SESSION 12: INVENTORY & INDEXING WRAPPERS
# ═══════════════════════════════════════════

def scan_all_collections(db):
    """Scan all Firestore collections and count documents."""
    from .librarian_index import scan_all_collections as _scan
    return _scan(db)


def rebuild_index(db):
    """Full rebuild of the librarian_index."""
    from .librarian_index import rebuild_index as _rebuild
    return _rebuild(db)


def get_inventory_stats(db):
    """Get comprehensive inventory statistics."""
    from .librarian_index import get_inventory_stats as _stats
    return _stats(db)


# ═══════════════════════════════════════════
#  SESSION 12: RESEARCHER WRAPPERS
# ═══════════════════════════════════════════

def learn_from_classification(db, classification_result):
    """Learn from a completed classification."""
    from .librarian_researcher import learn_from_classification as _learn
    return _learn(db, classification_result)


def check_for_updates(db, source):
    """Check for external source updates."""
    from .librarian_researcher import check_for_updates as _check
    return _check(db, source)


def get_enrichment_status(db):
    """Get enrichment task status."""
    from .librarian_researcher import get_enrichment_status as _status
    return _status(db)


def get_search_analytics(db):
    """Get search analytics."""
    from .librarian_researcher import get_search_analytics as _analytics
    return _analytics(db)


# ═══════════════════════════════════════════
#  SESSION 12: TAGGING WRAPPERS
# ═══════════════════════════════════════════

def auto_tag_document(document, collection_name=None):
    """Auto-tag a document based on content."""
    from .librarian_tags import auto_tag_document as _tag
    return _tag(document, collection_name)


def add_tags(db, doc_id, tags):
    """Add tags to a document."""
    from .librarian_tags import add_tags as _add
    return _add(db, doc_id, tags)


def get_tags_for_hs_code(hs_code):
    """Get appropriate tags for an HS code."""
    from .librarian_tags import get_tags_for_hs_code as _tags
    return _tags(hs_code)


# ═══════════════════════════════════════════
#  BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════

def search_all_knowledge(db, query_terms, item_description=""):
    """Backward compatible wrapper"""
    return full_knowledge_search(db, query_terms, item_description)

def search_extended_knowledge(db, query_terms):
    """Backward compatible wrapper"""
    return full_knowledge_search(db, query_terms, "")


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _log_search(db, keywords, query, results_count, confidence):
    """Log a search for analytics (best-effort, non-blocking)."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        log_id = f"search_{now[:19].replace(':', '-')}"
        db.collection("librarian_search_log").document(log_id).set({
            "query": query[:200] if query else "",
            "keywords": keywords[:10],
            "results_count": results_count,
            "confidence": confidence,
            "timestamp": now,
        })
    except Exception:
        pass  # Never fail on logging
