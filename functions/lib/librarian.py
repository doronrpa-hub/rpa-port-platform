"""
RCB Smart Librarian - Phased Knowledge Search
Searches intelligently, expands if needed, never misses critical data
"""

def extract_search_keywords(item_description):
    """Extract meaningful keywords from description"""
    # Common words to ignore
    stop_words = {'the', 'a', 'an', 'of', 'for', 'and', 'or', 'with', 'to', 'from', 
                  'in', 'on', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                  'את', 'של', 'על', 'עם', 'או', 'גם', 'כי', 'אם', 'לא', 'יש', 'זה'}
    
    # Split and clean
    words = item_description.lower().replace(',', ' ').replace('.', ' ').split()
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    return keywords[:10]  # Max 10 keywords


def search_collection_smart(db, collection_name, keywords, text_fields, max_results=50):
    """Smart search a single collection"""
    results = []
    keywords_lower = [k.lower() for k in keywords if k]
    
    try:
        docs = db.collection(collection_name).limit(500).stream()
        for doc in docs:
            data = doc.to_dict()
            
            # Build searchable text from specified fields
            search_text = ""
            for field in text_fields:
                val = data.get(field, "")
                if isinstance(val, str):
                    search_text += " " + val.lower()
            
            # Score by keyword matches
            score = 0
            for kw in keywords_lower:
                if kw in search_text:
                    score += 1
            
            if score > 0:
                results.append({
                    "doc_id": doc.id,
                    "score": score,
                    "data": data
                })
        
        # Sort by score, return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
        
    except Exception as e:
        print(f"    ❌ Error searching {collection_name}: {e}")
        return []


def search_tariff_codes(db, keywords):
    """Search for HS codes in tariff collections"""
    results = []
    
    # Search tariff_chapters
    print("    🔍 Searching tariff_chapters...")
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
    
    # Search tariff
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
    
    # Search hs_code_index
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
    
    # Sort all by score
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


def search_procedures_and_rules(db, keywords):
    """Search procedures and classification rules"""
    results = []
    
    # Procedures
    print("    🔍 Searching procedures...")
    procs = search_collection_smart(
        db, 'procedures', keywords,
        ['name', 'content', 'title', 'type'],
        max_results=20
    )
    for r in procs:
        results.append({"source": "procedures", "data": r["data"], "score": r["score"]})
    
    # Classification rules
    print("    🔍 Searching classification_rules...")
    rules = search_collection_smart(
        db, 'classification_rules', keywords + ['סיווג', 'כללי', 'פרשנות'],
        ['he', 'en', 'source', 'rule'],
        max_results=20
    )
    for r in rules:
        results.append({"source": "classification_rules", "data": r["data"], "score": r["score"]})
    
    # Classification knowledge
    print("    🔍 Searching classification_knowledge...")
    ck = search_collection_smart(
        db, 'classification_knowledge', keywords,
        ['content', 'title', 'rule'],
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
    
    # Previous classifications
    print("    🔍 Searching classifications history...")
    classes = search_collection_smart(
        db, 'classifications', keywords,
        ['description', 'hs_code', 'item'],
        max_results=20
    )
    for r in classes:
        results.append({"source": "classifications", "data": r["data"], "score": r["score"]})
    
    # Declarations
    print("    🔍 Searching declarations...")
    decl = search_collection_smart(
        db, 'declarations', keywords,
        ['description', 'item', 'hs_code'],
        max_results=15
    )
    for r in decl:
        results.append({"source": "declarations", "data": r["data"], "score": r["score"]})
    
    # RCB classifications
    print("    🔍 Searching rcb_classifications...")
    rcb = search_collection_smart(
        db, 'rcb_classifications', keywords,
        ['subject'],
        max_results=10
    )
    for r in rcb:
        results.append({"source": "rcb_classifications", "data": r["data"], "score": r["score"]})
    
    return results


def full_knowledge_search(db, query_terms, item_description=""):
    """
    Complete phased search across ALL knowledge
    Phase 1: Extract keywords and search all sources
    Phase 2: If low results, expand keywords
    """
    print("  📚 LIBRARIAN: Starting comprehensive search...")
    
    # Extract keywords
    all_terms = query_terms if isinstance(query_terms, list) else [query_terms]
    if item_description:
        all_terms.extend(extract_search_keywords(item_description))
    
    keywords = list(set([t for t in all_terms if t and len(str(t)) > 2]))[:15]
    print(f"  📚 Keywords: {keywords[:5]}...")
    
    results = {
        "tariff_codes": [],
        "regulations": [],
        "procedures_rules": [],
        "knowledge": [],
        "history": [],
        "confidence": "low"
    }
    
    try:
        # Phase 1: Targeted search
        results["tariff_codes"] = search_tariff_codes(db, keywords)
        results["regulations"] = search_regulations(db, keywords)
        results["procedures_rules"] = search_procedures_and_rules(db, keywords)
        results["knowledge"] = search_knowledge_base(db, keywords)
        results["history"] = search_history(db, keywords)
        
        # Calculate confidence based on results
        total_found = sum(len(v) for v in results.values() if isinstance(v, list))
        tariff_found = len(results["tariff_codes"])
        
        if tariff_found >= 3 and total_found >= 10:
            results["confidence"] = "high"
        elif tariff_found >= 1 and total_found >= 5:
            results["confidence"] = "medium"
        else:
            results["confidence"] = "low"
        
        print(f"  📚 LIBRARIAN: Found {total_found} docs, confidence: {results['confidence']}")
        
    except Exception as e:
        print(f"  ❌ Librarian error: {e}")
        import traceback
        traceback.print_exc()
    
    return results


def get_israeli_hs_format(hs_code):
    """Convert HS code to Israeli format XX.XX.XXXXXX/X"""
    code = str(hs_code).replace('.', '').replace(' ', '').replace('/', '')
    code = code.ljust(10, '0')[:10]
    
    if len(code) >= 8:
        return f"{code[:2]}.{code[2:4]}.{code[4:10]}/{code[9] if len(code) > 9 else '0'}"
    return hs_code


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


# Keep backward compatibility
def search_all_knowledge(db, query_terms, item_description=""):
    """Backward compatible wrapper"""
    return full_knowledge_search(db, query_terms, item_description)

def search_extended_knowledge(db, query_terms):
    """Backward compatible wrapper"""
    return full_knowledge_search(db, query_terms, "")
