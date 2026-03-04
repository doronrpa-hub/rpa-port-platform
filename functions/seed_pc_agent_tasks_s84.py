"""Session 84: Create PC agent download tasks for WAF-blocked URLs.

Run once: python seed_pc_agent_tasks_s84.py

Creates tasks in Firestore `pc_agent_tasks` collection for:
1. Ports Ordinance (פקודת הנמלים) — Nevo.co.il (WAF-blocked)
2. ATA Carnet procedure — gov.il
3. Direct Delivery procedure — gov.il
4. AEO procedure (גורם כלכלי מאושר) — gov.il
5. EU Reform Q&A page — gov.il
6. EU Directives search tool — gov.il
"""
import os
import sys
from datetime import datetime, timezone

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(__file__))

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
sa_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.path.join(
    os.path.dirname(__file__), "..", "sa-key.json"
)
if not firebase_admin._apps:
    cred = credentials.Certificate(sa_key)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ── FTA agreement tasks: rules of origin, preferential documents, full agreements ──
FTA_TASKS = [
    {
        "task_id": "fta_eu_rules_of_origin",
        "url": "https://www.gov.il/he/pages/eu-isr-fta",
        "source_name": "כללי מקור — הסכם ישראל-EU (פרוטוקול 4)",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_eu_rules_of_origin",
        "content_needed": "Protocol 4 rules of origin, EUR.1 procedures, approved exporter, cumulation with EFTA/Turkey, value tolerances, list rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_efta_rules_of_origin",
        "url": "https://www.gov.il/he/pages/efta-fta",
        "source_name": "כללי מקור — הסכם ישראל-EFTA",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_efta_rules_of_origin",
        "content_needed": "Rules of origin, EUR.1 procedures, cumulation with EU/Turkey, protocol on origin, list rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_uk_rules_of_origin",
        "url": "https://www.gov.il/he/pages/uk-israel-trade-agreement",
        "source_name": "כללי מקור — הסכם ישראל-UK",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_uk_rules_of_origin",
        "content_needed": "Rules of origin, EUR.1 procedures, statement on origin, approved exporter",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_turkey_rules_of_origin",
        "url": "https://www.gov.il/he/pages/free-trade-area-agreement-israel-turkey",
        "source_name": "כללי מקור — הסכם ישראל-טורקיה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_turkey_rules_of_origin",
        "content_needed": "Rules of origin, EUR.1 procedures, pan-Euro-Med cumulation, list rules, direct transport",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_jordan_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/jordan-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-ירדן",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_jordan_rules_of_origin",
        "content_needed": "Rules of origin, EUR.1 procedures, QIZ provisions, origin protocol",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_usa_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/fta-isr-usa",
        "source_name": "כללי מקור — הסכם ישראל-ארה\"ב",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_usa_rules_of_origin",
        "content_needed": "Rules of origin, 35% value-added rule, invoice declaration, substantial transformation",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_canada_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/israel-canada-fta",
        "source_name": "כללי מקור — הסכם ישראל-קנדה (CIFTA)",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_canada_rules_of_origin",
        "content_needed": "CIFTA rules of origin, certificate of origin, goods transfer via USA, specific rules by chapter",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_korea_rules_of_origin",
        "url": "https://www.gov.il/he/pages/il-korea-fta-180521",
        "source_name": "כללי מקור — הסכם ישראל-קוריאה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_korea_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, product-specific rules, chapter 3 protocol",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_uae_rules_of_origin",
        "url": "https://www.gov.il/he/pages/isr-uae-fta",
        "source_name": "כללי מקור — הסכם ישראל-UAE",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_uae_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, value-added thresholds, direct consignment",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_vietnam_rules_of_origin",
        "url": "https://www.gov.il/he/pages/israel-vietnam-fta",
        "source_name": "כללי מקור — הסכם ישראל-וייטנאם",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_vietnam_rules_of_origin",
        "content_needed": "VIFTA rules of origin, certificate of origin, product-specific rules, regional value content",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_ukraine_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/isr-ukraine-fta",
        "source_name": "כללי מקור — הסכם ישראל-אוקראינה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_ukraine_rules_of_origin",
        "content_needed": "Rules of origin, EUR.1 procedures, pan-Euro-Med cumulation, list rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_mexico_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/mexico-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-מקסיקו",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_mexico_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, regional value content, product-specific rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_colombia_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/colombia-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-קולומביה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_colombia_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, value-added thresholds, product-specific rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_panama_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/panama-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-פנמה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_panama_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, product-specific rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_guatemala_rules_of_origin",
        "url": "https://www.gov.il/he/pages/guatemala-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-גואטמלה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_guatemala_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, product-specific rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    {
        "task_id": "fta_mercosur_rules_of_origin",
        "url": "https://www.gov.il/he/departments/policies/mercosur-israel-fta",
        "source_name": "כללי מקור — הסכם ישראל-מרקוסור",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_mercosur_rules_of_origin",
        "content_needed": "Rules of origin, certificate of origin, Mercosur-specific provisions, product-specific rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    # Master FTA index page
    {
        "task_id": "fta_master_index",
        "url": "https://www.gov.il/he/pages/free-trade-area",
        "source_name": "אינדקס הסכמי סחר חופשי — משרד הכלכלה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_master_index",
        "content_needed": "Complete list of all FTA agreements, effective dates, country lists, links to agreement texts",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
    # Bilateral agreements search tool
    {
        "task_id": "fta_search_tool",
        "url": "https://www.gov.il/he/departments/dynamiccollectors/bilateral-agreements-search",
        "source_name": "כלי חיפוש הסכמים דו-צדדיים",
        "target_collection": "legal_knowledge",
        "target_doc_id": "fta_search_tool",
        "content_needed": "Search results for all bilateral trade agreements — full list with HS code coverage",
        "requires_browser": True,
        "priority": "high",
        "task_category": "fta_origin_rules",
    },
]

# ── General tasks: laws, procedures, reforms ──
TASKS = [
    {
        "task_id": "ports_ordinance_nevo",
        "url": "https://www.nevo.co.il/law_html/law00/67952.htm",
        "source_name": "פקודת הנמלים [נוסח חדש], תשל\"א-1971",
        "target_collection": "legal_knowledge",
        "target_doc_id": "ports_ordinance",
        "content_needed": "Full text of Ports Ordinance — all articles, definitions, port authority powers, cargo handling rules",
        "requires_browser": True,
        "priority": "high",
        "task_category": "law_download",
        "notes": "WAF-blocked (403 from direct HTTP). Needs browser. ~50 articles covering port operations.",
    },
    {
        "task_id": "ata_carnet_procedure",
        "url": "https://www.gov.il/he/pages/ata-carnet",
        "source_name": "נוהל פנקס ATA (קרנה)",
        "target_collection": "customs_procedures",
        "target_doc_id": "ata_carnet_procedure",
        "content_needed": "Full ATA Carnet procedure: temporary admission, re-export, CPD Carnet, guarantee",
        "requires_browser": True,
        "priority": "medium",
        "task_category": "procedure_download",
        "notes": "ATA Carnet for temporary admission of goods. Relevant for exhibitions, samples.",
    },
    {
        "task_id": "direct_delivery_procedure",
        "url": "https://www.gov.il/he/pages/direct-delivery-customs",
        "source_name": "נוהל אספקה ישירה (משלוח ישיר)",
        "target_collection": "customs_procedures",
        "target_doc_id": "direct_delivery_procedure",
        "content_needed": "Direct delivery procedure for FTA preferential treatment — when goods ship via third country",
        "requires_browser": True,
        "priority": "medium",
        "task_category": "procedure_download",
        "notes": "Direct shipment/delivery rules for maintaining FTA origin status through third countries.",
    },
    {
        "task_id": "aeo_procedure_govil",
        "url": "https://www.gov.il/he/pages/authorized-economic-operator",
        "source_name": "נוהל גורם כלכלי מאושר (AEO)",
        "target_collection": "customs_procedures",
        "target_doc_id": "aeo_procedure",
        "content_needed": "AEO certification requirements, benefits, application process, customs simplifications",
        "requires_browser": True,
        "priority": "medium",
        "task_category": "procedure_download",
        "notes": "Authorized Economic Operator — simplified customs procedures for certified businesses.",
    },
    {
        "task_id": "eu_reform_qna",
        "url": "https://www.gov.il/he/pages/qna-europe-reform",
        "source_name": "שאלות ותשובות — רפורמת אירופה",
        "target_collection": "legal_knowledge",
        "target_doc_id": "eu_reform_qna",
        "content_needed": "Full Q&A content: all questions and answers about EU reform procedures",
        "requires_browser": True,
        "priority": "medium",
        "task_category": "reform_download",
        "notes": "Supplements the EU reform main page with practical Q&A.",
    },
    {
        "task_id": "eu_directives_search",
        "url": "https://www.gov.il/he/Departments/DynamicCollectors/eu-directives-seach",
        "source_name": "חיפוש דירקטיבות אירופיות",
        "target_collection": "legal_knowledge",
        "target_doc_id": "eu_directives_list",
        "content_needed": "Full list of adopted EU directives with status, effective dates, product categories",
        "requires_browser": True,
        "priority": "high",
        "task_category": "reform_download",
        "notes": "Dynamic search tool — needs browser to render. Contains all 43 directives with status.",
    },
    {
        "task_id": "customs_agents_law_nevo",
        "url": "https://www.nevo.co.il/law_html/law01/255_001.htm",
        "source_name": "חוק סוכני המכס, תשכ\"ה-1964",
        "target_collection": "legal_knowledge",
        "target_doc_id": "customs_agents_law_full",
        "content_needed": "Full text of Customs Agents Law — all articles, licensing requirements, disciplinary procedures",
        "requires_browser": True,
        "priority": "medium",
        "task_category": "law_download",
        "notes": "Currently only have ordinance cross-refs (partial). Need full law text.",
    },
]


def main():
    now = datetime.now(timezone.utc).isoformat()
    created = 0
    skipped = 0

    all_tasks = FTA_TASKS + TASKS
    print(f"Processing {len(all_tasks)} tasks ({len(FTA_TASKS)} FTA + {len(TASKS)} general)...\n")

    for task in all_tasks:
        doc_ref = db.collection("pc_agent_tasks").document(task["task_id"])
        existing = doc_ref.get()
        if existing.exists:
            print(f"  SKIP  {task['task_id']} — already exists")
            skipped += 1
            continue

        doc_ref.set({
            "url": task["url"],
            "source_name": task["source_name"],
            "target_collection": task["target_collection"],
            "target_doc_id": task["target_doc_id"],
            "content_needed": task["content_needed"],
            "requires_browser": task["requires_browser"],
            "priority": task["priority"],
            "task_category": task["task_category"],
            "notes": task.get("notes", ""),
            "status": "pending",
            "created_at": now,
            "created_by": "session_84",
        })
        print(f"  CREATE  {task['task_id']} — {task['source_name']}")
        created += 1

    print(f"\nDone: {created} created, {skipped} skipped")


if __name__ == "__main__":
    main()
