"""
RCB Librarian Index - Document Indexing & Inventory
Session 12: Scan, index, and catalog all Firestore collections

Provides functions to discover all collections, index their documents
into a master `librarian_index` collection, and maintain the inventory.
"""

from datetime import datetime, timezone
from .librarian_tags import auto_tag_document, COLLECTION_DEFAULT_TAGS

# ═══════════════════════════════════════════
#  KNOWN COLLECTIONS & FIELD MAPPINGS
# ═══════════════════════════════════════════

# Every collection we expect in Firestore, with its searchable text fields
COLLECTION_FIELDS = {
    "tariff_chapters": {
        "title_fields": ["title", "title_he", "title_en", "description_he", "description_en"],
        "keyword_fields": ["code", "hs_code", "chapter"],
        "hs_fields": ["code", "hs_code"],
        "doc_type": "record",
    },
    "tariff": {
        "title_fields": ["description_he", "description_en"],
        "keyword_fields": ["hs_code", "chapter"],
        "hs_fields": ["hs_code"],
        "doc_type": "record",
    },
    "hs_code_index": {
        "title_fields": ["description", "description_he", "description_en"],
        "keyword_fields": ["code", "hs_code"],
        "hs_fields": ["code", "hs_code"],
        "doc_type": "record",
    },
    "ministry_index": {
        "title_fields": ["ministry", "description"],
        "keyword_fields": ["ministry"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "regulatory": {
        "title_fields": ["title", "content", "description"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "regulatory_approvals": {
        "title_fields": ["description", "type"],
        "keyword_fields": ["ministry", "type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "regulatory_certificates": {
        "title_fields": ["name", "description"],
        "keyword_fields": ["ministry", "type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "classification_rules": {
        "title_fields": ["he", "en", "rule"],
        "keyword_fields": ["source"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "classification_knowledge": {
        "title_fields": ["content", "title", "rule"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "procedures": {
        "title_fields": ["name", "content", "title"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "knowledge": {
        "title_fields": ["title", "content"],
        "keyword_fields": ["source", "type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "knowledge_base": {
        "title_fields": ["title", "content"],
        "keyword_fields": ["source", "type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "legal_references": {
        "title_fields": ["title", "content"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "legal_documents": {
        "title_fields": ["title", "content", "name"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "xml_documents": {
        "title_fields": ["title_he", "file_name"],
        "keyword_fields": ["category", "subcategory", "source"],
        "hs_fields": [],
        "doc_type": "document",
    },
    "licensing_knowledge": {
        "title_fields": ["content", "title"],
        "keyword_fields": ["type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "classifications": {
        "title_fields": ["description", "item"],
        "keyword_fields": ["hs_code"],
        "hs_fields": ["hs_code"],
        "doc_type": "record",
    },
    "declarations": {
        "title_fields": ["description", "item"],
        "keyword_fields": ["hs_code"],
        "hs_fields": ["hs_code"],
        "doc_type": "record",
    },
    "rcb_classifications": {
        "title_fields": ["subject"],
        "keyword_fields": [],
        "hs_fields": [],
        "doc_type": "record",
    },
    "fta_agreements": {
        "title_fields": ["name", "title", "description"],
        "keyword_fields": ["country", "countries"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "documents": {
        "title_fields": ["name", "title", "description"],
        "keyword_fields": ["type", "file_type"],
        "hs_fields": [],
        "doc_type": "document",
    },
    # Session 27: New collections from Assignments 8-9
    "product_index": {
        "title_fields": ["product_name", "description", "description_he"],
        "keyword_fields": ["hs_code", "category"],
        "hs_fields": ["hs_code"],
        "doc_type": "record",
    },
    "supplier_index": {
        "title_fields": ["name", "company", "email"],
        "keyword_fields": ["country", "type"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "chapter_notes": {
        "title_fields": ["chapter_title_he", "chapter_description_he", "heading_summary"],
        "keyword_fields": ["chapter_number", "keywords"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "keyword_index": {
        "title_fields": ["keyword", "keyword_he"],
        "keyword_fields": ["keyword", "keyword_he"],
        "hs_fields": ["hs_codes"],
        "doc_type": "record",
    },
    "cross_check_log": {
        "title_fields": ["item_description", "summary"],
        "keyword_fields": ["tier", "hs_code"],
        "hs_fields": ["hs_code"],
        "doc_type": "record",
    },
    # Session 27 Assignment 14C: Data pipeline collections
    "classification_directives": {
        "title_fields": ["title", "summary", "full_text"],
        "keyword_fields": ["directive_id", "key_terms"],
        "hs_fields": ["hs_codes_mentioned"],
        "doc_type": "document",
    },
    "pre_rulings": {
        "title_fields": ["product_description", "product_description_en", "reasoning_summary"],
        "keyword_fields": ["ruling_id", "key_terms"],
        "hs_fields": ["hs_code_assigned"],
        "doc_type": "document",
    },
    "customs_decisions": {
        "title_fields": ["product_description", "reasoning_summary"],
        "keyword_fields": ["decision_id", "key_terms"],
        "hs_fields": ["hs_code", "hs_codes_discussed"],
        "doc_type": "document",
    },
    "court_precedents": {
        "title_fields": ["case_name", "ruling_summary"],
        "keyword_fields": ["case_id", "key_terms"],
        "hs_fields": ["hs_codes_discussed"],
        "doc_type": "document",
    },
    "customs_ordinance": {
        "title_fields": ["title", "summary"],
        "keyword_fields": ["section_number", "key_terms"],
        "hs_fields": [],
        "doc_type": "document",
    },
    "customs_procedures": {
        "title_fields": ["title", "summary"],
        "keyword_fields": ["procedure_type", "key_terms"],
        "hs_fields": ["applicable_codes"],
        "doc_type": "document",
    },
    "tariff_uk": {
        "title_fields": ["description"],
        "keyword_fields": ["uk_code", "key_terms"],
        "hs_fields": ["uk_code"],
        "doc_type": "record",
    },
    "tariff_usa": {
        "title_fields": ["description"],
        "keyword_fields": ["hts_code", "key_terms"],
        "hs_fields": ["hts_code"],
        "doc_type": "record",
    },
    "tariff_eu": {
        "title_fields": ["description"],
        "keyword_fields": ["taric_code", "key_terms"],
        "hs_fields": ["taric_code"],
        "doc_type": "record",
    },
    "cbp_rulings": {
        "title_fields": ["product_description", "ruling_summary"],
        "keyword_fields": ["ruling_id", "key_terms"],
        "hs_fields": ["hts_code"],
        "doc_type": "document",
    },
    "bti_decisions": {
        "title_fields": ["product_description", "summary"],
        "keyword_fields": ["bti_reference", "key_terms"],
        "hs_fields": ["taric_code"],
        "doc_type": "document",
    },
    # Shipping knowledge collections (added by shipping_knowledge.py)
    "shipping_lines": {
        "title_fields": ["name", "country"],
        "keyword_fields": ["scac", "bol_prefixes", "container_prefixes", "email_domains",
                          "israel_company_codes", "israel_kav_codes"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "fiata_documents": {
        "title_fields": ["name", "description"],
        "keyword_fields": ["code", "key_fields"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "tracker_deals": {
        "title_fields": ["bol_number", "vessel_name", "shipping_line"],
        "keyword_fields": ["bol_number", "containers", "manifest_number",
                          "direction", "status", "port"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "tracker_container_status": {
        "title_fields": ["container_id", "current_step"],
        "keyword_fields": ["container_id", "deal_id", "current_step",
                          "ocean_step", "ocean_sources"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "tracker_timeline": {
        "title_fields": ["event_type", "source"],
        "keyword_fields": ["deal_id", "event_type", "source"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "port_schedules": {
        "title_fields": ["vessel_name", "shipping_line"],
        "keyword_fields": ["port_code", "vessel_name", "shipping_line",
                          "voyage", "schedule_key", "source"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "daily_port_report": {
        "title_fields": ["port_name_en", "port_name_he"],
        "keyword_fields": ["port_code", "report_date"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Tool #33: Route ETA cache — driving time from pickup to port (24h TTL)
    # Source: OpenRouteService / OSRM
    "route_cache": {
        "title_fields": ["origin_address", "port_code"],
        "keyword_fields": ["route_summary", "provider"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tariff structure: sections, chapters, additions, PDF URLs
    # Source: israeli_customs_tariff_structure.xml
    "tariff_structure": {
        "title_fields": ["name_he", "name_en"],
        "keyword_fields": ["type", "section", "chapters"],
        "hs_fields": [],
        "doc_type": "reference",
    },
    # Block C3: צו יבוא חופשי — Free Import Order regulatory requirements
    # Source: data.gov.il FIO dataset (28,899 records, 6,121 HS codes)
    "free_import_order": {
        "title_fields": ["goods_description"],
        "keyword_fields": ["authorities_summary", "appendices", "confirmation_types"],
        "hs_fields": ["hs_code", "hs_10"],
        "doc_type": "regulatory",
    },
    # Block C4: צו יצוא חופשי — Free Export Order regulatory requirements
    # Source: data.gov.il (1,704 records, 979 HS codes)
    "free_export_order": {
        "title_fields": ["goods_description"],
        "keyword_fields": ["authorities_summary", "appendices", "confirmation_types"],
        "hs_fields": ["hs_code", "hs_10"],
        "doc_type": "regulatory",
    },
    # Block C8: Legal knowledge — Customs Ordinance chapters, reforms, customs agents law
    # Source: legal_documents/pkudat_mechess + reference docs
    "legal_knowledge": {
        "title_fields": ["title_he", "title_en", "reform_name_he", "law_name_he", "text"],
        "keyword_fields": ["type", "chapter_number", "sections_mentioned"],
        "hs_fields": [],
        "doc_type": "legal",
    },
    # Block C5: צו מסגרת — Framework Order (legal definitions, FTA rules, additions)
    # Source: knowledge doc (PDF text) + AdditionRulesDetailsHistory.xml
    "framework_order": {
        "title_fields": ["term", "title", "country_en", "country_he", "clause_text"],
        "keyword_fields": ["type", "country_code", "rule_type", "addition_id"],
        "hs_fields": [],
        "doc_type": "legal",
    },
    # Email Intent: questions_log — Q+A pairs, cache, hit tracking
    "questions_log": {
        "title_fields": ["question_text"],
        "keyword_fields": ["intent", "from_email", "detection_method", "compose_model"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Email Intent: system_instructions — Admin directives that persist across emails
    "system_instructions": {
        "title_fields": ["instruction"],
        "keyword_fields": ["scope", "created_by"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Block D8: Elimination engine audit trail — full elimination steps per run
    "elimination_log": {
        "title_fields": ["product_description"],
        "keyword_fields": ["survivors", "eliminated"],
        "hs_fields": ["survivors"],
        "doc_type": "record",
    },
    # Core pipeline marker — processed email records
    "rcb_processed": {
        "title_fields": ["subject"],
        "keyword_fields": ["from_email", "classification_type", "status"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Operational logging — RCB system logs
    "rcb_logs": {
        "title_fields": ["message", "action"],
        "keyword_fields": ["level", "source"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # C2: Section-level notes from tariff (distinct from chapter_notes)
    "section_notes": {
        "title_fields": ["section_title_he", "section_title_en", "notes_he"],
        "keyword_fields": ["section_number", "keywords"],
        "hs_fields": [],
        "doc_type": "reference",
    },
    # Shipping agents — customs/clearing agent profiles (distinct from shipping_lines)
    "shipping_agents": {
        "title_fields": ["name", "company"],
        "keyword_fields": ["agent_code", "port"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Tool #14: Wikipedia lookup cache — product/material knowledge (30-day TTL)
    # Source: Wikipedia REST API (free, no key)
    "wikipedia_cache": {
        "title_fields": ["query"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #15: Wikidata structured facts cache (60-day TTL)
    "wikidata_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #16: Country data cache (90-day TTL)
    "country_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #17: Exchange rates cache (6-hour TTL)
    "currency_rates": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #18: UN Comtrade trade data cache (30-day TTL)
    "comtrade_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #19: Open Food Facts product cache (30-day TTL)
    "food_products_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #20: FDA drug/device cache (30-day TTL)
    "fda_products_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #21: Bank of Israel official exchange rates (6-hour TTL)
    "boi_rates": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #22: NIH PubChem chemical compound cache (90-day TTL)
    "pubchem_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #23: EU TARIC tariff cross-reference cache (30-day TTL)
    "eu_taric_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #24: US HTS cross-reference cache (30-day TTL)
    "usitc_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #25: Israeli CBS trade statistics cache (30-day TTL, overnight only)
    "cbs_trade_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #26: GS1 barcode product lookup cache (60-day TTL)
    "barcode_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #27: WCO explanatory notes cache (180-day TTL)
    "wco_notes_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #28: UNCTAD country GSP/development status cache (90-day TTL)
    "unctad_country_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #29: Open Beauty Facts cosmetics cache (30-day TTL)
    "beauty_products_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #30: CrossRef academic papers cache (90-day TTL, overnight only)
    "crossref_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #31: OpenSanctions screening cache (24-hour TTL)
    "sanctions_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Tool #32: Israel VAT/purchase tax rates cache (7-day TTL)
    "israel_tax_cache": {
        "title_fields": ["cache_key"],
        "keyword_fields": ["cache_key"],
        "hs_fields": [],
        "doc_type": "cache",
    },
    # Session 40c: Image pattern cache — avoids repeat AI vision calls (180-day TTL)
    "image_patterns": {
        "title_fields": ["final_hs_code"],
        "keyword_fields": ["image_hash"],
        "hs_fields": ["final_hs_code"],
        "doc_type": "cache",
    },
    # Session 44-PARALLEL: Regression alerts from overnight guard
    "regression_alerts": {
        "title_fields": ["product"],
        "keyword_fields": ["old_hs_code", "new_hs_code"],
        "hs_fields": ["old_hs_code", "new_hs_code"],
        "doc_type": "alert",
    },
    # Session 46: Deal Identity Graph — unified identifier linking
    # Links B/L, AWB, container, invoice, PO, file number, seped to a single deal
    "deal_identity_graph": {
        "title_fields": ["client_name"],
        "keyword_fields": ["bl_numbers", "container_numbers", "awb_numbers",
                          "booking_refs", "invoice_numbers", "file_number",
                          "seped_number", "job_order_number"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Session 46: Learned identifier patterns — overnight brain refines from cc@ emails
    "learned_identifier_patterns": {
        "title_fields": ["field", "regex"],
        "keyword_fields": ["field", "source", "client_name"],
        "hs_fields": [],
        "doc_type": "record",
    },
    # Session 45: Email quality gate log
    "email_quality_log": {
        "title_fields": ["subject"],
        "keyword_fields": ["recipient", "deal_id", "alert_type", "reason"],
        "hs_fields": [],
        "doc_type": "record",
    },
    "classification_attempts": {
        "title_fields": ["subject"],
        "keyword_fields": ["thread_key", "msg_id"],
        "hs_fields": ["hs_codes"],
        "doc_type": "record",
    },
}

# Document type by file extension
DOC_TYPE_MAP = {
    ".pdf": "PDF",
    ".xlsx": "Excel",
    ".xls": "Excel",
    ".docx": "Word",
    ".doc": "Word",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".png": "Image",
    ".txt": "Text",
    ".csv": "Data",
    ".eml": "Email",
    ".msg": "Email",
}


# ═══════════════════════════════════════════
#  INVENTORY / SCANNING
# ═══════════════════════════════════════════

def scan_all_collections(db):
    """
    Scan all known Firestore collections and count documents.

    Args:
        db: Firestore client

    Returns:
        Dict[str, int] - Collection name → document count
    """
    print("  📚 LIBRARIAN INDEX: Scanning all collections...")
    inventory = {}

    for coll_name in COLLECTION_FIELDS:
        try:
            count = 0
            for _ in db.collection(coll_name).limit(5000).stream():
                count += 1
            inventory[coll_name] = count
            if count > 0:
                print(f"    📁 {coll_name}: {count} documents")
        except Exception as e:
            inventory[coll_name] = -1
            print(f"    ❌ {coll_name}: error - {e}")

    total = sum(v for v in inventory.values() if v > 0)
    print(f"  📚 Total: {total} documents across {len([v for v in inventory.values() if v > 0])} collections")
    return inventory


def index_collection(db, collection_name, batch_size=100):
    """
    Index all documents from a single collection into librarian_index.

    Args:
        db: Firestore client
        collection_name: str - Collection to index
        batch_size: int - Firestore batch write size

    Returns:
        int - Number of documents indexed
    """
    field_config = COLLECTION_FIELDS.get(collection_name)
    if not field_config:
        print(f"    ⚠️ Unknown collection: {collection_name} - using generic config")
        field_config = {
            "title_fields": ["title", "name", "content", "description"],
            "keyword_fields": [],
            "hs_fields": [],
            "doc_type": "record",
        }

    print(f"  📚 Indexing {collection_name}...")
    count = 0
    batch = db.batch()
    batch_count = 0

    try:
        docs = db.collection(collection_name).stream()

        for doc in docs:
            data = doc.to_dict()
            index_entry = _build_index_entry(doc.id, collection_name, data, field_config)

            # Write to librarian_index
            index_id = f"{collection_name}__{doc.id}"
            ref = db.collection("librarian_index").document(index_id)
            batch.set(ref, index_entry, merge=True)
            batch_count += 1
            count += 1

            # Commit in batches
            if batch_count >= batch_size:
                batch.commit()
                batch = db.batch()
                batch_count = 0

        # Commit remaining
        if batch_count > 0:
            batch.commit()

        print(f"    ✅ Indexed {count} documents from {collection_name}")
        return count

    except Exception as e:
        print(f"    ❌ Error indexing {collection_name}: {e}")
        return count


def rebuild_index(db):
    """
    Full rebuild of the librarian_index from all known collections.

    Args:
        db: Firestore client

    Returns:
        Dict with stats: {total_indexed, per_collection, duration_sec}
    """
    import time
    start = time.time()

    print("  📚 LIBRARIAN INDEX: Full rebuild starting...")
    stats = {"total_indexed": 0, "per_collection": {}}

    for coll_name in COLLECTION_FIELDS:
        indexed = index_collection(db, coll_name)
        stats["per_collection"][coll_name] = indexed
        stats["total_indexed"] += indexed

    stats["duration_sec"] = round(time.time() - start, 2)

    # Save rebuild stats
    try:
        db.collection("librarian_enrichment_log").document("last_rebuild").set({
            "type": "full_rebuild",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
        })
    except Exception:
        pass

    print(f"  📚 Rebuild complete: {stats['total_indexed']} docs in {stats['duration_sec']}s")
    return stats


def index_single_document(db, collection_name, doc_id, data):
    """
    Index or re-index a single document (used after updates).

    Args:
        db: Firestore client
        collection_name: str
        doc_id: str
        data: dict - Document data

    Returns:
        bool - Success
    """
    field_config = COLLECTION_FIELDS.get(collection_name, {
        "title_fields": ["title", "name", "content", "description"],
        "keyword_fields": [],
        "hs_fields": [],
        "doc_type": "record",
    })

    try:
        index_entry = _build_index_entry(doc_id, collection_name, data, field_config)
        index_id = f"{collection_name}__{doc_id}"
        db.collection("librarian_index").document(index_id).set(index_entry, merge=True)
        return True
    except Exception as e:
        print(f"    ❌ Error indexing {collection_name}/{doc_id}: {e}")
        return False


def remove_from_index(db, collection_name, doc_id):
    """Remove a document from the index."""
    try:
        index_id = f"{collection_name}__{doc_id}"
        db.collection("librarian_index").document(index_id).delete()
        return True
    except Exception as e:
        print(f"    ❌ Error removing {index_id}: {e}")
        return False


# ═══════════════════════════════════════════
#  INVENTORY STATS
# ═══════════════════════════════════════════

def get_inventory_stats(db):
    """
    Get comprehensive inventory statistics.

    Returns:
        Dict with collection counts, tag distribution, index health
    """
    stats = {
        "collections": {},
        "total_documents": 0,
        "total_indexed": 0,
        "index_coverage": 0.0,
        "by_doc_type": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Count source collections
    for coll_name in COLLECTION_FIELDS:
        try:
            count = 0
            for _ in db.collection(coll_name).limit(5000).stream():
                count += 1
            stats["collections"][coll_name] = count
            stats["total_documents"] += count
        except Exception:
            stats["collections"][coll_name] = -1

    # Count index entries
    try:
        for doc in db.collection("librarian_index").stream():
            stats["total_indexed"] += 1
            data = doc.to_dict()
            doc_type = data.get("document_type", "unknown")
            stats["by_doc_type"][doc_type] = stats["by_doc_type"].get(doc_type, 0) + 1
    except Exception:
        pass

    if stats["total_documents"] > 0:
        stats["index_coverage"] = round(
            stats["total_indexed"] / stats["total_documents"] * 100, 1
        )

    return stats


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _build_index_entry(doc_id, collection_name, data, field_config):
    """Build an index entry for a document."""
    now = datetime.now(timezone.utc).isoformat()

    # Extract title from priority fields
    title = ""
    for field in field_config["title_fields"]:
        val = data.get(field, "")
        if isinstance(val, str) and val.strip():
            title = val.strip()[:200]
            break

    # Extract keywords (Hebrew + English)
    keywords_he = []
    keywords_en = []
    for field in field_config["title_fields"] + field_config["keyword_fields"]:
        val = data.get(field, "")
        if isinstance(val, str) and val.strip():
            words = val.lower().replace(",", " ").replace(".", " ").split()
            for w in words:
                if len(w) > 2:
                    # Basic Hebrew detection
                    if any("\u0590" <= c <= "\u05FF" for c in w):
                        if w not in keywords_he:
                            keywords_he.append(w)
                    else:
                        if w not in keywords_en:
                            keywords_en.append(w)

    # Extract HS codes
    hs_codes = []
    for field in field_config.get("hs_fields", []):
        val = data.get(field, "")
        if val:
            code = str(val).replace(".", "").replace("/", "").replace(" ", "")
            if code and len(code) >= 4:
                hs_codes.append(code)

    # Extract ministry
    ministries = []
    ministry = data.get("ministry", "")
    if ministry:
        ministries.append(ministry)

    # Extract countries
    countries = []
    for field in ["country", "countries", "country_of_origin", "origin"]:
        val = data.get(field)
        if isinstance(val, str) and val:
            countries.append(val)
        elif isinstance(val, list):
            countries.extend(val)

    # Auto-tag
    tags = auto_tag_document(data, collection_name)

    # Build description
    description = ""
    for field in field_config["title_fields"]:
        val = data.get(field, "")
        if isinstance(val, str) and val.strip() and val.strip() != title:
            description = val.strip()[:300]
            break

    return {
        "id": f"{collection_name}__{doc_id}",
        "original_doc_id": doc_id,
        "collection": collection_name,
        "document_type": field_config.get("doc_type", "record"),
        "title": title,
        "description": description,
        "tags": tags,
        "keywords_he": keywords_he[:30],
        "keywords_en": keywords_en[:30],
        "hs_codes": list(set(hs_codes)),
        "ministries": list(set(ministries)),
        "countries": list(set(countries)),
        "created_at": data.get("created_at", now),
        "updated_at": now,
        "last_accessed": now,
        "access_count": 0,
        "confidence_score": 0.8 if title else 0.5,
        "source_url": data.get("source_url", data.get("url", "")),
        "file_path": data.get("file_path", data.get("path", "")),
        "parent_id": data.get("parent_id"),
        "children_ids": data.get("children_ids", []),
    }
