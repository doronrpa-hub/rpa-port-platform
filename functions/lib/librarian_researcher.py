"""
RCB Librarian Researcher - Continuous Knowledge Enrichment
Session 12: Constantly searches DB + web, geo-tags Israeli vs foreign

The Researcher:
1. CONSTANTLY scans the database for gaps and keywords to research
2. Searches the web for additional data (Israeli gov sites, WCO, EU, etc.)
3. Marks every piece of data as Israeli source or foreign source
4. Learns from every classification, correction, and email
5. Tracks enrichment history and search analytics

Web Sources (Israeli):
- shaarolami-query.customs.mof.gov.il (תעריפון, החלטות סיווג)
- taxes.gov.il (רשות המסים, נהלים)
- gov.il/* (משרדי ממשלה, תקנות, צווים)
- nevo.co.il (חקיקה, פסיקה)
- takdin.co.il (פסקי דין)

Web Sources (International):
- eur-lex.europa.eu (EU regulations)
- wcoomd.org (WCO HS explanatory notes)
- trade.gov (US trade data)
"""

from datetime import datetime, timezone
from enum import Enum

# ═══════════════════════════════════════════
#  ENRICHMENT TASK DEFINITIONS
# ═══════════════════════════════════════════

class EnrichmentFrequency(str, Enum):
    PER_EMAIL = "per_email"
    CONTINUOUS = "continuous"     # Runs whenever system is idle
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EnrichmentSource(str, Enum):
    # Israeli government sources
    CUSTOMS_GOV = "customs.mof.gov.il"
    TAXES_GOV = "taxes.gov.il"
    ECONOMY_GOV = "economy.gov.il"
    HEALTH_GOV = "health.gov.il"
    AGRICULTURE_GOV = "agriculture.gov.il"
    TRANSPORT_GOV = "transport.gov.il"
    COMMUNICATIONS_GOV = "communications.gov.il"
    ENVIRONMENT_GOV = "environment.gov.il"
    NEVO = "nevo.co.il"
    TAKDIN = "takdin.co.il"
    # International sources
    EUR_LEX = "eur-lex.europa.eu"
    WCO = "wcoomd.org"
    US_TRADE = "trade.gov"
    # Internal sources
    INTERNAL_DB = "internal_database"
    INTERNAL_EMAIL = "internal_email"
    INTERNAL_CLASSIFICATION = "internal_classification"
    INTERNAL_CORRECTION = "internal_correction"


# ═══════════════════════════════════════════
#  WEB SEARCH KEYWORDS BY TOPIC
# ═══════════════════════════════════════════

# Keywords the researcher uses to search the web, grouped by topic
RESEARCH_KEYWORDS = {
    "tariff_updates": {
        "keywords_he": ["עדכון תעריפון מכס", "שינוי שיעורי מכס", "הודעת מכס חדשה", "תעריף מכס ישראל"],
        "keywords_en": ["israel customs tariff update", "israeli duty rate change"],
        "sources": [EnrichmentSource.CUSTOMS_GOV, EnrichmentSource.TAXES_GOV],
        "geo": "israel",
    },
    "classification_decisions": {
        "keywords_he": ["החלטת סיווג מכס", "החלטה מקדמית סיווג", "פרשנות סיווג", "סיווג מכס חדש"],
        "keywords_en": ["israel customs classification decision", "HS classification ruling israel"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "free_import_order": {
        "keywords_he": ["צו יבוא חופשי עדכון", "תוספת צו יבוא חופשי", "שינוי צו יבוא"],
        "keywords_en": ["israel free import order amendment"],
        "sources": [EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "customs_procedures": {
        "keywords_he": ["נוהל מכס חדש", "עדכון נוהל מכס", "הנחיות רשות המכס"],
        "keywords_en": ["israel customs procedure update"],
        "sources": [EnrichmentSource.CUSTOMS_GOV, EnrichmentSource.TAXES_GOV],
        "geo": "israel",
    },
    "ministry_health_procedures": {
        "keywords_he": ["נוהל משרד הבריאות יבוא", "אישור יבוא בריאות", "תקנות בריאות יבוא"],
        "keywords_en": ["israel ministry health import procedure"],
        "sources": [EnrichmentSource.HEALTH_GOV],
        "geo": "israel",
    },
    "ministry_agriculture_procedures": {
        "keywords_he": ["נוהל משרד החקלאות יבוא", "אישור וטרינרי", "אישור צמחים יבוא", "שירות הגנת הצומח"],
        "keywords_en": ["israel agriculture import permit", "phytosanitary israel"],
        "sources": [EnrichmentSource.AGRICULTURE_GOV],
        "geo": "israel",
    },
    "ministry_transport_procedures": {
        "keywords_he": ["נוהל משרד התחבורה יבוא", "אישור יבוא רכב", "תקנות תחבורה"],
        "keywords_en": ["israel transport ministry import vehicle"],
        "sources": [EnrichmentSource.TRANSPORT_GOV],
        "geo": "israel",
    },
    "ministry_communications_procedures": {
        "keywords_he": ["נוהל משרד התקשורת יבוא", "אישור תקשורת", "ציוד אלחוטי יבוא"],
        "keywords_en": ["israel communications ministry import wireless"],
        "sources": [EnrichmentSource.COMMUNICATIONS_GOV],
        "geo": "israel",
    },
    "standards_updates": {
        "keywords_he": ["עדכון תקן ישראלי", "תו תקן חדש", "מכון התקנים עדכון"],
        "keywords_en": ["SII standard update israel", "israeli standard new"],
        "sources": [EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "regulations_updates": {
        "keywords_he": ["תקנות חדשות יבוא", "צו חדש מכס", "עדכון תקנות"],
        "keywords_en": ["israel new import regulations"],
        "sources": [EnrichmentSource.NEVO, EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "court_rulings": {
        "keywords_he": ["פסק דין מכס", "ערר מכס", "ערעור סיווג", "פסיקת מכס"],
        "keywords_en": ["israel customs court ruling", "customs tribunal decision israel"],
        "sources": [EnrichmentSource.NEVO, EnrichmentSource.TAKDIN],
        "geo": "israel",
    },
    "fta_updates": {
        "keywords_he": ["הסכם סחר חופשי ישראל", "עדכון הסכם סחר", "הסכם EUR1"],
        "keywords_en": ["israel free trade agreement update", "israel FTA new"],
        "sources": [EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "export_procedures": {
        "keywords_he": ["נוהל יצוא חופשי", "פיקוח יצוא", "רישיון יצוא", "עדכון יצוא"],
        "keywords_en": ["israel export procedure", "israel export control update"],
        "sources": [EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    # ── Export & Customs Procedures ──
    "export_control_updates": {
        "keywords_he": ["פיקוח יצוא דו-שימושי", "צו יצוא כימי ביולוגי גרעיני", "רישיון יצוא ביטחוני"],
        "keywords_en": ["israel dual-use export control", "israel defense export update"],
        "sources": [EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "export_classification": {
        "keywords_he": ["סיווג טובין ביצוא", "ספר סיווג יצוא", "עדכון סיווג יצוא"],
        "keywords_en": ["israel export classification update"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "rules_of_origin": {
        "keywords_he": ["כללי מקור ישראל", "תעודת מקור EUR1", "יצואן מאושר", "הסכם סחר כללי מקור"],
        "keywords_en": ["israel rules of origin", "EUR1 certificate", "authorized exporter israel"],
        "sources": [EnrichmentSource.CUSTOMS_GOV, EnrichmentSource.ECONOMY_GOV],
        "geo": "israel",
    },
    "ata_carnet": {
        "keywords_he": ["קרנה אטא עדכון", "נוהל קרנה", "פנקס מעבר מכס", "דוגמאות מסחריות קרנה"],
        "keywords_en": ["ATA carnet israel", "carnet procedure update"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "declarants_procedure": {
        "keywords_he": ["נוהל מצהרים עדכון", "מצהר מורשה", "נוהל מצהרים מכס"],
        "keywords_en": ["israel customs declarants procedure"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "customs_release_procedure": {
        "keywords_he": ["נוהל שחרור עדכון", "תהליך שחרור מכס", "מסלול ירוק אדום"],
        "keywords_en": ["israel customs release procedure update"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "customs_valuation": {
        "keywords_he": ["הערכת טובין עדכון", "נוהל הערכה מכס", "הערכה GATT"],
        "keywords_en": ["israel customs valuation update", "WTO valuation"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "bonded_warehouse": {
        "keywords_he": ["מחסן רישוי עדכון", "מחסני ערובה", "אזור סחר חופשי"],
        "keywords_en": ["israel bonded warehouse", "free trade zone israel"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "temporary_import_export": {
        "keywords_he": ["יבוא זמני עדכון", "יצוא זמני", "כניסה זמנית", "יצוא מוחזר פריט 810"],
        "keywords_en": ["israel temporary import", "temporary export", "returned export"],
        "sources": [EnrichmentSource.CUSTOMS_GOV],
        "geo": "israel",
    },
    "wco_updates": {
        "keywords_he": [],
        "keywords_en": ["WCO HS explanatory notes update", "harmonized system amendment",
                         "WCO classification opinion"],
        "sources": [EnrichmentSource.WCO],
        "geo": "international",
    },
    "eu_regulations": {
        "keywords_he": [],
        "keywords_en": ["EU customs regulation update", "EU combined nomenclature change",
                         "european classification ruling"],
        "sources": [EnrichmentSource.EUR_LEX],
        "geo": "eu",
    },
}

# Pre-defined enrichment task configurations
ENRICHMENT_TASKS = {
    "tariff_update": {
        "name": "Tariff Updates",
        "name_he": "עדכון תעריפון",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.DAILY,
        "target_collections": ["tariff_chapters", "tariff"],
        "research_topic": "tariff_updates",
        "geo": "israel",
    },
    "classification_decisions": {
        "name": "Classification Decisions",
        "name_he": "החלטות סיווג",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.DAILY,
        "target_collections": ["classification_knowledge", "classification_rules"],
        "research_topic": "classification_decisions",
        "geo": "israel",
    },
    "free_import_order_update": {
        "name": "Free Import Order Updates",
        "name_he": "עדכון צו יבוא חופשי",
        "source": EnrichmentSource.ECONOMY_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["regulatory", "free_import_orders"],
        "research_topic": "free_import_order",
        "geo": "israel",
    },
    "customs_procedures_update": {
        "name": "Customs Procedures Update",
        "name_he": "עדכון נהלי מכס",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["procedures"],
        "research_topic": "customs_procedures",
        "geo": "israel",
    },
    "ministry_procedures_update": {
        "name": "Ministry Procedures Update",
        "name_he": "עדכון נהלי משרדים",
        "source": EnrichmentSource.HEALTH_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["procedures", "regulatory"],
        "research_topics": [
            "ministry_health_procedures",
            "ministry_agriculture_procedures",
            "ministry_transport_procedures",
            "ministry_communications_procedures",
        ],
        "geo": "israel",
    },
    "regulation_update": {
        "name": "Regulation Updates",
        "name_he": "עדכון תקנות",
        "source": EnrichmentSource.NEVO,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["regulatory", "legal_documents"],
        "research_topic": "regulations_updates",
        "geo": "israel",
    },
    "court_rulings_update": {
        "name": "Court Rulings",
        "name_he": "עדכון פסיקה",
        "source": EnrichmentSource.NEVO,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["legal_references", "court_rulings"],
        "research_topic": "court_rulings",
        "geo": "israel",
    },
    "fta_update": {
        "name": "FTA Updates",
        "name_he": "עדכון הסכמי סחר",
        "source": EnrichmentSource.ECONOMY_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["fta_agreements"],
        "research_topic": "fta_updates",
        "geo": "israel",
    },
    "export_update": {
        "name": "Export Procedures Update",
        "name_he": "עדכון נהלי יצוא",
        "source": EnrichmentSource.ECONOMY_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["procedures", "export_procedures"],
        "research_topic": "export_procedures",
        "geo": "israel",
    },
    "standards_update": {
        "name": "Standards Updates",
        "name_he": "עדכון תקנים",
        "source": EnrichmentSource.ECONOMY_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["regulatory"],
        "research_topic": "standards_updates",
        "geo": "israel",
    },
    "wco_update": {
        "name": "WCO HS Updates",
        "name_he": "עדכון HS בינלאומי",
        "source": EnrichmentSource.WCO,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["classification_knowledge"],
        "research_topic": "wco_updates",
        "geo": "international",
    },
    "eu_regulation_update": {
        "name": "EU Regulation Updates",
        "name_he": "עדכון רגולציה אירופית",
        "source": EnrichmentSource.EUR_LEX,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["classification_knowledge", "regulatory"],
        "research_topic": "eu_regulations",
        "geo": "eu",
    },
    # ── Additional Customs Procedure Tasks ──
    "export_control_update": {
        "name": "Export Control Updates",
        "name_he": "עדכון פיקוח יצוא",
        "source": EnrichmentSource.ECONOMY_GOV,
        "frequency": EnrichmentFrequency.WEEKLY,
        "target_collections": ["procedures", "export_procedures", "legal_documents"],
        "research_topics": ["export_control_updates", "export_classification"],
        "geo": "israel",
    },
    "ata_carnet_update": {
        "name": "ATA Carnet Procedures",
        "name_he": "עדכון נוהל קרנה אט״א",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "ata_carnet_docs"],
        "research_topic": "ata_carnet",
        "geo": "israel",
    },
    "declarants_update": {
        "name": "Declarants Procedure Update",
        "name_he": "עדכון נוהל מצהרים",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "declarants_docs"],
        "research_topic": "declarants_procedure",
        "geo": "israel",
    },
    "customs_release_update": {
        "name": "Release Procedure Update",
        "name_he": "עדכון תהליך שחרור",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "procedures"],
        "research_topic": "customs_release_procedure",
        "geo": "israel",
    },
    "valuation_update": {
        "name": "Valuation Procedure Update",
        "name_he": "עדכון נוהל הערכה",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "procedures"],
        "research_topic": "customs_valuation",
        "geo": "israel",
    },
    "bonded_warehouse_update": {
        "name": "Bonded Warehouse Update",
        "name_he": "עדכון מחסנים רשויים",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "procedures"],
        "research_topic": "bonded_warehouse",
        "geo": "israel",
    },
    "temp_import_export_update": {
        "name": "Temporary Import/Export Update",
        "name_he": "עדכון יבוא/יצוא זמני",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "procedures"],
        "research_topic": "temporary_import_export",
        "geo": "israel",
    },
    "rules_of_origin_update": {
        "name": "Rules of Origin Update",
        "name_he": "עדכון כללי מקור",
        "source": EnrichmentSource.CUSTOMS_GOV,
        "frequency": EnrichmentFrequency.MONTHLY,
        "target_collections": ["customs_handbook", "fta_agreements"],
        "research_topic": "rules_of_origin",
        "geo": "israel",
    },
    "email_learning": {
        "name": "Email Learning",
        "name_he": "למידה מאימיילים",
        "source": EnrichmentSource.INTERNAL_EMAIL,
        "frequency": EnrichmentFrequency.PER_EMAIL,
        "target_collections": ["knowledge_base", "classifications"],
        "geo": "israel",
    },
    "classification_learning": {
        "name": "Classification Learning",
        "name_he": "למידה מסיווגים",
        "source": EnrichmentSource.INTERNAL_CLASSIFICATION,
        "frequency": EnrichmentFrequency.PER_EMAIL,
        "target_collections": ["classification_knowledge", "rcb_classifications"],
        "geo": "israel",
    },
    "correction_learning": {
        "name": "Correction Learning",
        "name_he": "למידה מתיקונים",
        "source": EnrichmentSource.INTERNAL_CORRECTION,
        "frequency": EnrichmentFrequency.PER_EMAIL,
        "target_collections": ["classification_knowledge"],
        "geo": "israel",
    },
    "continuous_db_scan": {
        "name": "Continuous DB Scan",
        "name_he": "סריקת מסד נתונים רציפה",
        "source": EnrichmentSource.INTERNAL_DB,
        "frequency": EnrichmentFrequency.CONTINUOUS,
        "target_collections": ["knowledge_base"],
        "geo": "israel",
    },
}

# ═══════════════════════════════════════════
#  ISRAELI WEB SOURCES REGISTRY
# ═══════════════════════════════════════════

ISRAELI_WEB_SOURCES = {
    "customs_tariff": {
        "url": "https://shaarolami-query.customs.mof.gov.il",
        "name_he": "שער עולמי - תעריפון",
        "content_type": ["tariff", "classification_decision"],
        "geo": "israel",
    },
    "customs_procedures": {
        "url": "https://taxes.gov.il/customs",
        "name_he": "רשות המסים - מכס",
        "content_type": ["procedure_customs", "publication", "circular"],
        "geo": "israel",
    },
    "economy_trade": {
        "url": "https://www.gov.il/he/departments/ministry_of_economy",
        "name_he": "משרד הכלכלה - סחר חוץ",
        "content_type": ["free_import_order", "fta", "regulation"],
        "geo": "israel",
    },
    "health_import": {
        "url": "https://www.gov.il/he/departments/ministry_of_health",
        "name_he": "משרד הבריאות - יבוא",
        "content_type": ["procedure_health", "certificate"],
        "geo": "israel",
    },
    "agriculture_import": {
        "url": "https://www.gov.il/he/departments/ministry_of_agriculture",
        "name_he": "משרד החקלאות - יבוא",
        "content_type": ["procedure_agriculture", "certificate"],
        "geo": "israel",
    },
    "transport_import": {
        "url": "https://www.gov.il/he/departments/ministry_of_transport",
        "name_he": "משרד התחבורה - יבוא",
        "content_type": ["procedure_transport", "certificate"],
        "geo": "israel",
    },
    "communications_import": {
        "url": "https://www.gov.il/he/departments/ministry_of_communications",
        "name_he": "משרד התקשורת - יבוא",
        "content_type": ["procedure_communications", "certificate"],
        "geo": "israel",
    },
    "nevo_legislation": {
        "url": "https://www.nevo.co.il",
        "name_he": "נבו - חקיקה ופסיקה",
        "content_type": ["law", "regulations", "court_ruling", "order"],
        "geo": "israel",
    },
    "standards_institute": {
        "url": "https://www.sii.org.il",
        "name_he": "מכון התקנים הישראלי",
        "content_type": ["certificate", "regulation"],
        "geo": "israel",
    },
}

INTERNATIONAL_WEB_SOURCES = {
    "wco": {
        "url": "https://www.wcoomd.org",
        "name_en": "World Customs Organization",
        "content_type": ["classification", "knowledge"],
        "geo": "international",
    },
    "eur_lex": {
        "url": "https://eur-lex.europa.eu",
        "name_en": "EUR-Lex EU Law",
        "content_type": ["regulation", "classification"],
        "geo": "eu",
    },
    "us_trade": {
        "url": "https://www.trade.gov",
        "name_en": "US Trade",
        "content_type": ["regulation", "knowledge"],
        "geo": "usa",
    },
}


# ═══════════════════════════════════════════
#  CONTINUOUS DB SCANNING
# ═══════════════════════════════════════════

def scan_db_for_research_keywords(db, limit=100):
    """
    Scan the database for items that need more research.
    Looks for:
    - Classifications with low confidence
    - Items with missing ministry requirements
    - HS codes without complete regulatory info
    - Documents tagged 'needs_update'

    Returns:
        List[dict] - Research tasks with keywords to search
    """
    research_tasks = []

    try:
        # 1. Find low-confidence classifications
        print("    🔍 Scanning for low-confidence classifications...")
        docs = db.collection("classification_knowledge").limit(limit).stream()
        for doc in docs:
            data = doc.to_dict()
            confidence = data.get("confidence", "")
            if confidence in ("נמוכה", "low", ""):
                hs_code = data.get("hs_code", "")
                description = data.get("description", "")
                if hs_code or description:
                    research_tasks.append({
                        "type": "verify_classification",
                        "hs_code": hs_code,
                        "description": description[:100],
                        "keywords": [hs_code, description[:50]] if description else [hs_code],
                        "reason": "Low confidence - needs verification",
                        "priority": "high",
                    })

        # 2. Find documents tagged 'needs_update'
        print("    🔍 Scanning for documents needing update...")
        try:
            index_docs = db.collection("librarian_index") \
                .where("tags", "array_contains", "needs_update") \
                .limit(50).stream()
            for doc in index_docs:
                data = doc.to_dict()
                research_tasks.append({
                    "type": "update_document",
                    "doc_id": doc.id,
                    "title": data.get("title", ""),
                    "collection": data.get("collection", ""),
                    "keywords": data.get("keywords_he", [])[:5] + data.get("keywords_en", [])[:5],
                    "reason": "Marked as needs_update",
                    "priority": "medium",
                })
        except Exception:
            pass

        # 3. Find HS codes without regulatory info
        print("    🔍 Scanning for HS codes missing regulatory data...")
        hs_codes_seen = set()
        cls_docs = db.collection("rcb_classifications").limit(100).stream()
        for doc in cls_docs:
            data = doc.to_dict()
            items = data.get("items", data.get("classification_data", []))
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        hs = item.get("hs_code", "")
                        if hs and hs not in hs_codes_seen:
                            hs_codes_seen.add(hs)
                            if not item.get("ministry_requirements"):
                                research_tasks.append({
                                    "type": "find_regulations",
                                    "hs_code": hs,
                                    "description": item.get("description", "")[:100],
                                    "keywords": [hs, "תוספת", "אישור", "רישיון"],
                                    "reason": "Missing ministry requirements for HS code",
                                    "priority": "medium",
                                })

        print(f"    📋 Found {len(research_tasks)} research tasks")

    except Exception as e:
        print(f"    ❌ Error scanning DB for research: {e}")

    return research_tasks


def get_web_search_queries(research_topic):
    """
    Get the search queries for a research topic.
    Returns Hebrew and English keywords plus target sources.

    Args:
        research_topic: str - Key from RESEARCH_KEYWORDS

    Returns:
        dict with keywords_he, keywords_en, sources, geo
    """
    return RESEARCH_KEYWORDS.get(research_topic, {
        "keywords_he": [],
        "keywords_en": [],
        "sources": [],
        "geo": "unknown",
    })


# ═══════════════════════════════════════════
#  GEO-TAGGING
# ═══════════════════════════════════════════

def geo_tag_source(url="", text="", source_name=""):
    """
    Determine if a source is Israeli or foreign and return appropriate tags.

    Args:
        url: str - Source URL
        text: str - Source text content
        source_name: str - Source name

    Returns:
        dict with {geo: str, origin_tag: str, country_tag: str}
    """
    combined = (url + " " + text + " " + source_name).lower()

    # Israeli indicators
    israeli_domains = [".gov.il", ".co.il", ".org.il", "nevo.co.il", "takdin.co.il", "sii.org.il"]
    israeli_text = ["ישראל", "israel", "מכס ישראל", "רשות המסים", "משרד"]

    for domain in israeli_domains:
        if domain in combined:
            return {"geo": "israel", "origin_tag": "source_israeli", "country_tag": "israel"}

    for indicator in israeli_text:
        if indicator in combined:
            return {"geo": "israel", "origin_tag": "source_israeli", "country_tag": "israel"}

    # EU indicators
    eu_indicators = [".europa.eu", "eur-lex", "eu regulation", "european commission"]
    for indicator in eu_indicators:
        if indicator in combined:
            return {"geo": "eu", "origin_tag": "source_foreign", "country_tag": "eu"}

    # US indicators
    us_indicators = [".gov", "trade.gov", "cbp.gov", "us customs"]
    for indicator in us_indicators:
        if indicator in combined and ".gov.il" not in combined:
            return {"geo": "usa", "origin_tag": "source_foreign", "country_tag": "usa"}

    # WCO
    if "wcoomd" in combined or "world customs" in combined:
        return {"geo": "international", "origin_tag": "source_foreign", "country_tag": "wco"}

    # Default
    return {"geo": "unknown", "origin_tag": "source_foreign", "country_tag": "international"}


def enrich_with_geo_tags(document, url="", source_name=""):
    """
    Add geographic origin tags to a document.

    Args:
        document: dict - Document to tag
        url: str - Source URL
        source_name: str - Source name

    Returns:
        dict - Document with added geo tags
    """
    text = " ".join(str(v) for v in document.values() if isinstance(v, str))
    geo_info = geo_tag_source(url=url, text=text, source_name=source_name)

    tags = document.get("tags", [])
    if isinstance(tags, list):
        if geo_info["origin_tag"] and geo_info["origin_tag"] not in tags:
            tags.append(geo_info["origin_tag"])
        if geo_info["country_tag"] and geo_info["country_tag"] not in tags:
            tags.append(geo_info["country_tag"])
        document["tags"] = sorted(list(set(tags)))

    document["geo_origin"] = geo_info["geo"]
    document["source_country"] = geo_info["country_tag"]

    return document


# ═══════════════════════════════════════════
#  LEARNING FROM CLASSIFICATIONS
# ═══════════════════════════════════════════

def learn_from_classification(db, classification_result):
    """
    Extract knowledge from a completed classification and store it.
    Geo-tags as Israeli since these come from Israeli customs processing.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        items = classification_result.get("items") or classification_result.get("classification_data", [])
        subject = classification_result.get("subject", "")
        sender = classification_result.get("sender", "")

        if not items:
            return False

        learned_count = 0
        for item in items:
            if not isinstance(item, dict):
                continue

            hs_code = item.get("hs_code", "")
            description = item.get("description") or item.get("item_description", "")
            if not hs_code or not description:
                continue

            learning_entry = {
                "type": "classification_learning",
                "hs_code": hs_code,
                "description": description,
                "description_lower": description.lower(),
                "confidence": item.get("confidence", ""),
                "source_subject": subject,
                "source_sender": sender,
                "duty_rate": item.get("duty_rate", ""),
                "ministry_requirements": item.get("ministry_requirements", []),
                "notes": item.get("notes", ""),
                "learned_at": now,
                "usage_count": 1,
                "is_correction": False,
                "geo_origin": "israel",
                "tags": ["classification", "source_learned", "source_israeli", "israel"],
            }

            doc_id = f"learn_{hs_code}_{_safe_id(description[:50])}"
            doc_ref = db.collection("classification_knowledge").document(doc_id)

            existing = doc_ref.get()
            if existing.exists:
                ed = existing.to_dict()
                learning_entry["usage_count"] = ed.get("usage_count", 0) + 1
                learning_entry["first_seen"] = ed.get("learned_at", now)

            doc_ref.set(learning_entry, merge=True)
            learned_count += 1

        _log_enrichment(db, "classification_learning", {
            "items_learned": learned_count, "subject": subject, "sender": sender,
        })

        print(f"    📚 Learned from {learned_count} classification items")
        return True

    except Exception as e:
        print(f"    ❌ Error learning from classification: {e}")
        return False


def learn_from_correction(db, original_hs_code, corrected_hs_code,
                          description, correction_reason=""):
    """Learn from a user correction — high-value, prevents repeat mistakes."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        correction_entry = {
            "type": "correction",
            "original_hs_code": original_hs_code,
            "corrected_hs_code": corrected_hs_code,
            "description": description,
            "description_lower": description.lower() if description else "",
            "correction_reason": correction_reason,
            "learned_at": now,
            "is_correction": True,
            "usage_count": 1,
            "geo_origin": "israel",
            "tags": ["classification", "source_learned", "source_israeli"],
        }

        doc_id = f"corr_{original_hs_code}_{corrected_hs_code}_{_safe_id(description[:30])}"
        db.collection("classification_knowledge").document(doc_id).set(
            correction_entry, merge=True
        )

        _log_enrichment(db, "correction_learning", {
            "original": original_hs_code, "corrected": corrected_hs_code,
        })

        print(f"    📚 Learned correction: {original_hs_code} → {corrected_hs_code}")
        return True

    except Exception as e:
        print(f"    ❌ Error learning correction: {e}")
        return False


def learn_from_email(db, email_data):
    """Extract and learn knowledge from a processed email. Geo-tags based on sender."""
    result = {"learned_items": 0, "new_suppliers": 0, "new_products": 0}

    try:
        now = datetime.now(timezone.utc).isoformat()
        sender = email_data.get("sender", "")
        subject = email_data.get("subject", "")

        # Determine geo from sender domain
        sender_geo = geo_tag_source(url=sender, source_name=sender)

        # 1. Learn supplier info
        if sender:
            supplier_id = f"supplier_{_safe_id(sender)}"
            supplier_ref = db.collection("knowledge_base").document(supplier_id)
            existing = supplier_ref.get()

            supplier_data = {
                "type": "supplier",
                "email": sender,
                "last_contact": now,
                "email_count": 1,
                "geo_origin": sender_geo["geo"],
                "tags": ["source_email", sender_geo["origin_tag"]],
            }

            if existing.exists:
                ed = existing.to_dict()
                supplier_data["email_count"] = ed.get("email_count", 0) + 1
                supplier_data["first_contact"] = ed.get("first_contact", now)
            else:
                supplier_data["first_contact"] = now
                result["new_suppliers"] = 1

            supplier_ref.set(supplier_data, merge=True)

        # 2. Learn from extracted items
        extracted = email_data.get("extracted_items", [])
        for item in extracted:
            if isinstance(item, dict) and item.get("description"):
                product_id = f"product_{_safe_id(item['description'][:50])}"
                product_data = {
                    "type": "product",
                    "description": item["description"],
                    "hs_code": item.get("hs_code", ""),
                    "supplier": sender,
                    "first_seen": now,
                    "source_subject": subject,
                    "geo_origin": sender_geo["geo"],
                    "tags": ["source_email", sender_geo["origin_tag"]],
                }
                db.collection("knowledge_base").document(product_id).set(product_data, merge=True)
                result["learned_items"] += 1
                result["new_products"] += 1

        _log_enrichment(db, "email_learning", {
            "sender": sender, "subject": subject,
            "items_learned": result["learned_items"],
            "geo": sender_geo["geo"],
        })

    except Exception as e:
        print(f"    ❌ Error learning from email: {e}")

    return result


def learn_from_web_result(db, web_result, research_topic):
    """
    Store a web research result in the knowledge base with geo-tags.

    Args:
        db: Firestore client
        web_result: dict - {url, title, content, source_name}
        research_topic: str - Topic key from RESEARCH_KEYWORDS

    Returns:
        bool - Success
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        topic_config = RESEARCH_KEYWORDS.get(research_topic, {})
        geo = topic_config.get("geo", "unknown")

        geo_info = geo_tag_source(
            url=web_result.get("url", ""),
            text=web_result.get("content", ""),
            source_name=web_result.get("source_name", ""),
        )

        doc_id = f"web_{research_topic}_{_safe_id(web_result.get('title', 'untitled')[:50])}"

        entry = {
            "type": "web_research",
            "research_topic": research_topic,
            "title": web_result.get("title", ""),
            "content": web_result.get("content", "")[:2000],
            "source_url": web_result.get("url", ""),
            "source_name": web_result.get("source_name", ""),
            "fetched_at": now,
            "geo_origin": geo_info["geo"],
            "tags": [
                "source_web",
                geo_info["origin_tag"],
                geo_info["country_tag"],
                "knowledge",
            ],
        }

        db.collection("knowledge_base").document(doc_id).set(entry, merge=True)

        _log_enrichment(db, "web_research", {
            "topic": research_topic, "url": web_result.get("url", ""),
            "geo": geo_info["geo"],
        })

        return True

    except Exception as e:
        print(f"    ❌ Error storing web result: {e}")
        return False


# ═══════════════════════════════════════════
#  FIND SIMILAR PAST CLASSIFICATIONS
# ═══════════════════════════════════════════

def find_similar_classifications(db, description, limit=5):
    """Find past classifications similar to a given description."""
    results = []
    desc_lower = description.lower()
    desc_words = set(desc_lower.replace(",", " ").replace(".", " ").split())
    desc_words = {w for w in desc_words if len(w) > 2}

    try:
        docs = db.collection("classification_knowledge").limit(500).stream()
        for doc in docs:
            data = doc.to_dict()
            stored_desc = data.get("description_lower", "")
            if not stored_desc:
                stored_desc = data.get("description", "").lower()

            stored_words = set(stored_desc.replace(",", " ").replace(".", " ").split())
            stored_words = {w for w in stored_words if len(w) > 2}

            if not stored_words:
                continue

            overlap = len(desc_words & stored_words)
            if overlap == 0:
                continue

            score = overlap / max(len(desc_words), 1)
            if data.get("is_correction"):
                score *= 1.5
            usage = data.get("usage_count", 1)
            if usage > 3:
                score *= 1.2

            results.append({
                "hs_code": data.get("corrected_hs_code") or data.get("hs_code", ""),
                "description": data.get("description", ""),
                "confidence": data.get("confidence", ""),
                "score": round(score, 3),
                "usage_count": usage,
                "is_correction": data.get("is_correction", False),
                "geo_origin": data.get("geo_origin", "unknown"),
                "source": "classification_knowledge",
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    except Exception as e:
        print(f"    ❌ Error finding similar classifications: {e}")
        return []


# ═══════════════════════════════════════════
#  UPDATE CHECKING & SCHEDULING
# ═══════════════════════════════════════════

def check_for_updates(db, source):
    """Check if any tasks for a source are overdue."""
    pending = []
    try:
        matching_tasks = {
            k: v for k, v in ENRICHMENT_TASKS.items()
            if v["source"] == source or
               (hasattr(v["source"], 'value') and v["source"].value == source)
        }

        for task_key, task_config in matching_tasks.items():
            log_ref = db.collection("librarian_enrichment_log").document(f"last_{task_key}")
            log_doc = log_ref.get()

            should_run = True
            if log_doc.exists:
                last_run = log_doc.to_dict().get("timestamp", "")
                if last_run:
                    should_run = _is_overdue(last_run, task_config["frequency"])

            if should_run:
                pending.append({"task_key": task_key, "task": task_config, "status": "pending"})

    except Exception as e:
        print(f"    ❌ Error checking for updates: {e}")

    return pending


def schedule_enrichment(db, task_key):
    """Mark an enrichment task as scheduled for execution."""
    try:
        if task_key not in ENRICHMENT_TASKS:
            return ""
        now = datetime.now(timezone.utc).isoformat()
        schedule_id = f"sched_{task_key}_{now[:10]}"
        db.collection("librarian_enrichment_log").document(schedule_id).set({
            "task_key": task_key,
            "task_name": ENRICHMENT_TASKS[task_key]["name"],
            "status": "scheduled",
            "scheduled_at": now,
            "geo": ENRICHMENT_TASKS[task_key].get("geo", "israel"),
        })
        return schedule_id
    except Exception as e:
        print(f"    ❌ Error scheduling {task_key}: {e}")
        return ""


def complete_enrichment(db, schedule_id, result_data):
    """Mark an enrichment task as completed with results."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        db.collection("librarian_enrichment_log").document(schedule_id).update({
            "status": "completed", "completed_at": now, "result": result_data,
        })
        return True
    except Exception as e:
        print(f"    ❌ Error completing {schedule_id}: {e}")
        return False


# ═══════════════════════════════════════════
#  STATUS & REPORTING
# ═══════════════════════════════════════════

def get_enrichment_status(db):
    """Get status of all enrichment tasks."""
    status = {
        "tasks": {},
        "total_enrichments": 0,
        "israeli_sources": 0,
        "foreign_sources": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        logs = db.collection("librarian_enrichment_log").limit(200).stream()
        for doc in logs:
            data = doc.to_dict()
            task_key = data.get("task_key", doc.id)
            status["total_enrichments"] += 1

            geo = data.get("geo", "")
            if geo == "israel":
                status["israeli_sources"] += 1
            elif geo in ("eu", "international", "usa"):
                status["foreign_sources"] += 1

            if task_key not in status["tasks"] or \
               data.get("timestamp", "") > status["tasks"][task_key].get("last_run", ""):
                status["tasks"][task_key] = {
                    "name": data.get("task_name", task_key),
                    "last_run": data.get("timestamp") or data.get("completed_at", ""),
                    "status": data.get("status", "unknown"),
                    "geo": geo,
                }

    except Exception as e:
        status["error"] = str(e)

    return status


def get_search_analytics(db, limit=50):
    """Get search analytics from the search log."""
    analytics = {
        "total_searches": 0,
        "top_queries": {},
        "top_hs_codes": {},
        "no_result_queries": [],
    }

    try:
        logs = db.collection("librarian_search_log").limit(limit).stream()
        for doc in logs:
            data = doc.to_dict()
            analytics["total_searches"] += 1
            query = data.get("query", "")
            if query:
                analytics["top_queries"][query] = analytics["top_queries"].get(query, 0) + 1
            hs = data.get("hs_code", "")
            if hs:
                analytics["top_hs_codes"][hs] = analytics["top_hs_codes"].get(hs, 0) + 1
            if data.get("results_count", 0) == 0:
                analytics["no_result_queries"].append(query)

        analytics["top_queries"] = dict(sorted(analytics["top_queries"].items(), key=lambda x: -x[1])[:20])
        analytics["top_hs_codes"] = dict(sorted(analytics["top_hs_codes"].items(), key=lambda x: -x[1])[:20])
    except Exception as e:
        analytics["error"] = str(e)

    return analytics


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _log_enrichment(db, task_type, details):
    """Log an enrichment event."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        log_id = f"{task_type}_{now[:19].replace(':', '-')}"
        db.collection("librarian_enrichment_log").document(log_id).set({
            "task_key": task_type,
            "task_name": task_type.replace("_", " ").title(),
            "timestamp": now,
            "status": "completed",
            "details": details,
            "geo": details.get("geo", "israel") if isinstance(details, dict) else "israel",
        })
    except Exception:
        pass


def _safe_id(text):
    """Create a safe Firestore document ID from text."""
    import re
    safe = re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '_', text.strip())
    return safe[:60].strip('_') or "unknown"


def _is_overdue(last_run_iso, frequency):
    """Check if a task is overdue based on its frequency."""
    try:
        if isinstance(frequency, EnrichmentFrequency):
            frequency = frequency.value
        last_run = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed = (now - last_run).total_seconds()
        thresholds = {
            "per_email": 0,
            "continuous": 300,    # 5 minutes
            "hourly": 3600,
            "daily": 86400,
            "weekly": 604800,
            "monthly": 2592000,
        }
        return elapsed >= thresholds.get(frequency, 86400)
    except Exception:
        return True
