"""
Evidence Types -- Structured Evidence Bundle for Reply Composition
==================================================================
Transforms the loose ContextPackage from context_engine.py into a tagged
EvidenceBundle where every fact has a source_name and source_ref.

Also handles direction-specific enrichment: FIO vs FEO, valuation articles
(import only), approved exporter (export only).

Usage:
    from lib.evidence_types import EvidenceBundle, build_evidence_bundle
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# -----------------------------------------------------------------------
#  DATA STRUCTURES
# -----------------------------------------------------------------------

@dataclass
class EvidencePiece:
    """A single fact with full provenance."""
    fact: str               # The actual text/data
    source_name: str        # "פקודת המכס", "נוהל סיווג #3", "צו יבוא חופשי"
    source_ref: str         # "סעיף 132", "תוספת 2", "פרט 39.23"
    source_type: str        # ordinance, procedure, fio, feo, tariff, fta, directive, framework, web
    confidence: float = 1.0


@dataclass
class EvidenceBundle:
    """Structured evidence from ALL data sources, tagged with provenance."""

    # Direction
    direction: str = "unknown"          # import / export / transit / unknown
    direction_config: dict = field(default_factory=dict)
    direction_confidence: float = 0.0

    # Domain detected by context_engine
    domain: str = "general"

    # Original query
    original_subject: str = ""
    original_body: str = ""
    detected_language: str = "he"

    # Tariff data
    tariff_entries: list = field(default_factory=list)
    # Each: {hs_code, description_he, description_en, duty, purchase_tax, vat, source_ref}

    # Ordinance articles (with full Hebrew text)
    ordinance_articles: list = field(default_factory=list)
    # Each: {article_id, title_he, summary_en, full_text_he, chapter, source_name, source_ref}

    # Procedures
    procedure_refs: list = field(default_factory=list)
    # Each: {procedure_number, name_he, relevant_text, source_name, source_ref}

    # FIO / FEO requirements
    regulatory_requirements: list = field(default_factory=list)
    # Each: {supplement, authority, requirement, standard, hs_code, source_name, source_ref}

    # FTA data
    fta_data: Optional[dict] = None
    # {applicable, country, origin_rules, declaration_type, preferential_rate, source_name, source_ref}

    # Framework order articles
    framework_articles: list = field(default_factory=list)
    # Each: {article_id, title_he, text, source_name, source_ref}

    # Classification directives
    directives: list = field(default_factory=list)
    # Each: {directive_id, title, hs_code, content, source_name, source_ref}

    # Chapter notes
    chapter_notes: list = field(default_factory=list)

    # Discount codes
    discount_codes: list = field(default_factory=list)

    # Valuation data (import only)
    valuation_articles: list = field(default_factory=list)
    # Each: EvidencePiece with ordinance art. 130-133 full text

    # Release data (import only)
    release_articles: list = field(default_factory=list)
    # Each: EvidencePiece with ordinance art. 62-63 + procedure #1

    # Web/Wikipedia results (for general queries)
    web_results: list = field(default_factory=list)
    # Each: {title, text, source_url, source_name}

    # Supplier website results
    supplier_results: list = field(default_factory=list)
    # Each: {url, content, source_name='supplier_website', source_ref}

    # XML document results (EU reform, procedures, etc.)
    xml_results: list = field(default_factory=list)

    # Case plan (from case_reasoning.py)
    case_plan: Optional[Any] = None
    # CasePlan dataclass with legal_category, items_to_classify, discount_group, etc.

    # Chapter 98 data (for personal imports)
    chapter98_entries: list = field(default_factory=list)
    # Each: {hs_code, chapter98_code, desc_he, desc_en, duty, pt, discount_info}

    # Entities extracted from query
    entities: dict = field(default_factory=dict)

    # Audit trail
    search_log: list = field(default_factory=list)
    sources_found: list = field(default_factory=list)     # List of source names actually used
    sources_not_found: list = field(default_factory=list)  # Sources searched but empty

    def has_tariff_data(self):
        return bool(self.tariff_entries)

    def has_regulatory_data(self):
        return bool(self.regulatory_requirements)

    def has_fta_data(self):
        return bool(self.fta_data and self.fta_data.get("applicable"))

    def has_valuation_data(self):
        return bool(self.valuation_articles)

    def has_web_data(self):
        return bool(self.web_results)


# -----------------------------------------------------------------------
#  BUILDER: ContextPackage -> EvidenceBundle
# -----------------------------------------------------------------------

def build_evidence_bundle(context_package, direction_result, db=None, case_plan=None):
    """Transform a ContextPackage into a tagged EvidenceBundle.

    Args:
        context_package: ContextPackage from context_engine.prepare_context_package()
        direction_result: dict from direction_router.detect_direction()
        db: Optional Firestore client (for direction-specific enrichment)
        case_plan: Optional CasePlan from case_reasoning.analyze_case()

    Returns:
        EvidenceBundle with every fact tagged by source
    """
    from lib.direction_router import get_direction_config

    direction = direction_result.get("direction", "unknown")
    dir_config = get_direction_config(direction)

    bundle = EvidenceBundle(
        direction=direction,
        direction_config=dir_config,
        direction_confidence=direction_result.get("confidence", 0.0),
        domain=context_package.domain,
        original_subject=context_package.original_subject,
        original_body=context_package.original_body,
        detected_language=context_package.detected_language,
        entities=context_package.entities,
        search_log=list(context_package.search_log),
    )

    # 1. Tag ordinance articles
    _tag_ordinance_articles(bundle, context_package.ordinance_articles)

    # 2. Tag framework articles
    _tag_framework_articles(bundle, context_package.framework_articles)

    # 3. Tag tariff results
    _tag_tariff_results(bundle, context_package.tariff_results)

    # 4. Tag regulatory results
    _tag_regulatory_results(bundle, context_package.regulatory_results, dir_config)

    # 5. Tag XML results (EU reform, procedures, etc.)
    _tag_xml_results(bundle, context_package.xml_results)

    # 6. Tag web/Wikipedia results
    _tag_web_results(bundle, context_package)

    # 7. Tag other tool results (supplier website, logistics, etc.)
    _tag_other_results(bundle, context_package)

    # 8. Search discount codes if keywords detected
    _tag_discount_codes(bundle)

    # 9. Direction-specific enrichment
    _enrich_by_direction(bundle, dir_config)

    # 10. Case plan enrichment (Chapter 98, directed searches)
    if case_plan:
        bundle.case_plan = case_plan
        _enrich_from_case_plan(bundle, case_plan)

    # 11. Build source audit
    _build_source_audit(bundle)

    return bundle


# -----------------------------------------------------------------------
#  TAGGERS — convert loose ContextPackage data into tagged evidence
# -----------------------------------------------------------------------

def _tag_ordinance_articles(bundle, articles):
    """Tag ordinance articles with provenance."""
    for art in (articles or []):
        source = art.get("source", "ordinance")
        if source == "regulations":
            source_name = art.get("title_he", "תקנות")
        else:
            source_name = "פקודת המכס"
        bundle.ordinance_articles.append({
            "article_id": art.get("article_id", ""),
            "title_he": art.get("title_he", ""),
            "summary_en": art.get("summary_en", ""),
            "full_text_he": art.get("full_text_he", ""),
            "chapter": art.get("chapter", 0),
            "source_name": source_name,
            "source_ref": f"סעיף {art.get('article_id', '')} לפקודת המכס"
                          if source != "regulations"
                          else art.get("title_he", ""),
        })


def _tag_framework_articles(bundle, articles):
    """Tag framework order articles."""
    for art in (articles or []):
        bundle.framework_articles.append({
            "article_id": art.get("article_id", ""),
            "title_he": art.get("title_he", art.get("t", "")),
            "text": art.get("full_text_he", art.get("text", art.get("f", ""))),
            "source_name": "צו מסגרת",
            "source_ref": f"סעיף {art.get('article_id', '')} לצו המסגרת",
        })


def _tag_tariff_results(bundle, results):
    """Tag tariff search results."""
    for entry in (results or []):
        bundle.tariff_entries.append({
            "hs_code": entry.get("hs_code", ""),
            "description_he": entry.get("description_he", entry.get("description", "")),
            "description_en": entry.get("description_en", ""),
            "duty": entry.get("duty", entry.get("customs_rate", "")),
            "purchase_tax": entry.get("purchase_tax", entry.get("pt", "")),
            "vat": entry.get("vat", "18%"),
            "source_name": "תעריף המכס",
            "source_ref": f"פרט {entry.get('hs_code', '')}",
        })


def _tag_regulatory_results(bundle, results, dir_config):
    """Tag regulatory results (FIO/FEO)."""
    decree_name = dir_config.get("decree_name_he", "צו יבוא חופשי")
    for item in (results or []):
        data = item if isinstance(item, dict) else {}
        # Regulatory results from tool_executors come nested in {"data": ...}
        if "data" in data:
            data = data["data"]
        if not data:
            continue

        # Handle requirements list from FIO/FEO
        requirements = data.get("requirements", [])
        for req in requirements:
            bundle.regulatory_requirements.append({
                "supplement": req.get("supplement", req.get("appendix", "")),
                "authority": req.get("authority", req.get("authority_name", "")),
                "requirement": req.get("requirement", req.get("description", "")),
                "standard": req.get("standard", ""),
                "hs_code": data.get("hs_code", req.get("hs_code", "")),
                "source_name": decree_name,
                "source_ref": f"{decree_name}, {req.get('supplement', '')}",
            })

        # If no nested requirements but top-level data
        if not requirements and data.get("authorities_summary"):
            for auth in data.get("authorities_summary", []):
                bundle.regulatory_requirements.append({
                    "supplement": "",
                    "authority": auth if isinstance(auth, str) else str(auth),
                    "requirement": "",
                    "standard": "",
                    "hs_code": data.get("hs_code", ""),
                    "source_name": decree_name,
                    "source_ref": decree_name,
                })


def _tag_xml_results(bundle, results):
    """Tag XML document results."""
    for item in (results or []):
        bundle.xml_results.append({
            "title": item.get("title", ""),
            "content": item.get("content", item.get("text", ""))[:2000],
            "doc_type": item.get("doc_type", ""),
            "source_name": item.get("source_name", item.get("title", "מסמך")),
            "source_ref": item.get("source_ref", item.get("title", "")),
        })


def _tag_web_results(bundle, context_package):
    """Tag Wikipedia and web results."""
    for item in (context_package.wikipedia_results or []):
        bundle.web_results.append({
            "title": item.get("title", ""),
            "text": item.get("extract", item.get("text", ""))[:2000],
            "source_url": item.get("url", item.get("source_url", "")),
            "source_name": f"Wikipedia: {item.get('title', '')}",
        })


def _tag_other_results(bundle, context_package):
    """Tag supplier, logistics, and other tool results."""
    for item in (context_package.other_tool_results or []):
        tool_name = item.get("_tool_name", "")
        if tool_name == "fetch_seller_website":
            bundle.supplier_results.append({
                "url": item.get("url", ""),
                "content": item.get("content", "")[:3000],
                "source_name": "supplier_website",
                "source_ref": item.get("url", ""),
            })
        elif tool_name in ("search_classification_directives",):
            for d in item.get("directives", [item]):
                bundle.directives.append({
                    "directive_id": d.get("directive_id", ""),
                    "title": d.get("title", ""),
                    "hs_code": d.get("primary_hs_code", d.get("hs_code", "")),
                    "content": d.get("content", "")[:2000],
                    "source_name": "הנחיית סיווג",
                    "source_ref": f"הנחיית סיווג {d.get('directive_id', '')}",
                })
        # FTA results
        elif tool_name in ("lookup_fta",):
            if item.get("applicable") or item.get("country"):
                bundle.fta_data = {
                    "applicable": item.get("applicable", False),
                    "country": item.get("country", ""),
                    "origin_rules": item.get("origin_rules", item.get("rules", "")),
                    "declaration_type": item.get("declaration_type", ""),
                    "preferential_rate": item.get("preferential_rate", ""),
                    "source_name": f"הסכם סחר חופשי — {item.get('country', '')}",
                    "source_ref": item.get("agreement_name", ""),
                }


# -----------------------------------------------------------------------
#  DISCOUNT CODES — תושב חוזר / עולה / פטור / הנחה
# -----------------------------------------------------------------------

# Keywords that trigger discount code search (Hebrew customs terms)
_DISCOUNT_KEYWORDS = [
    "תושב חוזר", "עולה", "עולה חדש", "סטודנט חוזר",
    "קוד הנחה", "פטור", "פטור ממכס", "הנחה", "הקלה",
    "חפצים אישיים", "חפצים ביתיים", "כלי עבודה",
    "רכב עולה", "רכב תושב", "משלוח אישי",
    "returning resident", "new immigrant", "oleh", "toshav chozer",
    "discount code", "exemption", "duty free",
]


def _tag_discount_codes(bundle):
    """Search discount codes if the email body contains relevant keywords."""
    text = f"{bundle.original_subject} {bundle.original_body}".lower()
    matched_keywords = [kw for kw in _DISCOUNT_KEYWORDS if kw in text]

    if not matched_keywords:
        return

    try:
        from lib._discount_codes_data import search_discount_codes, get_discount_code
    except ImportError:
        try:
            from _discount_codes_data import search_discount_codes, get_discount_code
        except ImportError:
            return

    seen = set()
    for kw in matched_keywords:
        results = search_discount_codes(kw)
        for item_num, sub_code, desc in results:
            key = (item_num, sub_code or "")
            if key in seen:
                continue
            seen.add(key)

            entry = {
                "item_number": item_num,
                "sub_code": sub_code or "",
                "description_he": desc,
                "source_name": "צו תעריף המכס והפטורים",
                "source_ref": f"פרט {item_num}" + (f" קוד {sub_code}" if sub_code else ""),
                "matched_keyword": kw,
            }
            # Enrich with duty details from sub_code if available
            item_data = get_discount_code(item_num)
            if item_data and sub_code:
                sc_data = item_data.get("sub_codes", {}).get(sub_code, {})
                entry["customs_duty"] = sc_data.get("customs_duty", "")
                entry["purchase_tax"] = sc_data.get("purchase_tax", "")
                entry["conditional"] = sc_data.get("conditional", False)
                entry["hs_codes"] = sc_data.get("hs_codes", [])

            bundle.discount_codes.append(entry)


# -----------------------------------------------------------------------
#  DIRECTION-SPECIFIC ENRICHMENT
# -----------------------------------------------------------------------

def _enrich_by_direction(bundle, dir_config):
    """Add direction-specific data: valuation/release articles for import,
    approved exporter for export."""

    # Import valuation articles (130-133)
    if dir_config.get("valuation_articles"):
        _add_ordinance_articles(
            bundle.valuation_articles,
            dir_config["valuation_articles"],
            "פקודת המכס",
        )

    # Import release articles (62-63)
    if dir_config.get("release_articles"):
        _add_ordinance_articles(
            bundle.release_articles,
            dir_config["release_articles"],
            "פקודת המכס",
        )

    # Direction-specific procedures
    for proc_num in dir_config.get("procedures", []):
        proc_name = dir_config.get("procedure_names", {}).get(proc_num, f"נוהל {proc_num}")
        _add_procedure_ref(bundle.procedure_refs, proc_num, proc_name)


def _add_ordinance_articles(target_list, article_numbers, source_name):
    """Load ordinance articles by number from in-memory data."""
    try:
        from lib._ordinance_data import ORDINANCE_ARTICLES
    except ImportError:
        try:
            from _ordinance_data import ORDINANCE_ARTICLES
        except ImportError:
            return

    for art_num in article_numbers:
        art_id = str(art_num)
        art = ORDINANCE_ARTICLES.get(art_id)
        if art:
            target_list.append(EvidencePiece(
                fact=art.get("f", art.get("s", "")),
                source_name=source_name,
                source_ref=f"סעיף {art_id} לפקודת המכס",
                source_type="ordinance",
            ))


def _add_procedure_ref(target_list, proc_num, proc_name):
    """Load procedure reference from in-memory data."""
    try:
        from lib._procedures_data import get_procedure
    except ImportError:
        try:
            from _procedures_data import get_procedure
        except ImportError:
            return

    proc = get_procedure(proc_num)
    if proc:
        # Get first ~1500 chars as relevant summary (full text is huge)
        full_text = proc.get("full_text", "")
        summary = full_text[:1500] if full_text else ""
        target_list.append({
            "procedure_number": proc_num,
            "name_he": proc.get("name_he", proc_name),
            "relevant_text": summary,
            "source_name": f"נוהל מכס מס' {proc_num}" if proc_num != "approved_exporter"
                           else "נוהל יצואן מאושר",
            "source_ref": f"נוהל {proc_num}",
        })


# -----------------------------------------------------------------------
#  CASE PLAN ENRICHMENT (Chapter 98, directed discount codes)
# -----------------------------------------------------------------------

def _enrich_from_case_plan(bundle, case_plan):
    """Enrich bundle with Chapter 98 data and directed discount codes
    based on case_plan legal category and items."""

    if not case_plan or not case_plan.legal_category:
        return

    # Load Chapter 98 data for each item that has a tariff match
    try:
        from lib._chapter98_data import get_chapter98_code, get_chapter98_entry
    except ImportError:
        try:
            from _chapter98_data import get_chapter98_code, get_chapter98_entry
        except ImportError:
            return

    try:
        from lib.case_reasoning import get_discount_for_item
    except ImportError:
        try:
            from case_reasoning import get_discount_for_item
        except ImportError:
            return

    # For each tariff entry in the bundle, find Chapter 98 equivalent
    for entry in bundle.tariff_entries:
        hs_code = entry.get("hs_code", "")
        ch98_code = get_chapter98_code(hs_code)
        if ch98_code:
            ch98_entry = get_chapter98_entry(ch98_code)
            if ch98_entry:
                bundle.chapter98_entries.append({
                    "regular_hs_code": hs_code,
                    "chapter98_code": ch98_code,
                    "desc_he": ch98_entry.get("desc_he", ""),
                    "desc_en": ch98_entry.get("desc_en", ""),
                    "duty": ch98_entry.get("duty", ""),
                    "purchase_tax": ch98_entry.get("purchase_tax", ""),
                    "regular_duty": entry.get("duty", ""),
                    "regular_pt": entry.get("purchase_tax", ""),
                    "source_name": "תעריף המכס — פרק 98",
                    "source_ref": f"פרט {ch98_code[:4]}.{ch98_code[4:]}",
                })

    # For each item in case_plan, compute per-item discount
    for item in case_plan.items_to_classify:
        category = item.get("category", "")
        # Try to find matching tariff entry
        item_hs = ""
        for entry in bundle.tariff_entries:
            # Simple category match
            desc = (entry.get("description_he", "") + " " +
                    entry.get("description_en", "")).lower()
            for kw in item.get("keywords", []):
                if kw.lower() in desc:
                    item_hs = entry.get("hs_code", "")
                    break
            if item_hs:
                break

        if item_hs:
            discount = get_discount_for_item(
                item.get("name", ""), item_hs,
                case_plan.legal_category, category)
            if discount:
                item["discount_info"] = discount


# -----------------------------------------------------------------------
#  SOURCE AUDIT
# -----------------------------------------------------------------------

_ALL_SOURCE_TYPES = [
    ("ordinance_articles", "פקודת המכס"),
    ("framework_articles", "צו מסגרת"),
    ("tariff_entries", "תעריף המכס"),
    ("regulatory_requirements", "צו יבוא/יצוא חופשי"),
    ("directives", "הנחיות סיווג"),
    ("procedure_refs", "נהלי מכס"),
    ("valuation_articles", "סעיפי הערכה"),
    ("release_articles", "סעיפי שחרור"),
    ("web_results", "מקורות אינטרנט"),
    ("supplier_results", "אתר ספק"),
    ("discount_codes", "קודי הנחה"),
    ("chapter98_entries", "פרק 98 — יבוא אישי"),
]


def _build_source_audit(bundle):
    """Build the sources_found and sources_not_found lists."""
    for attr, label in _ALL_SOURCE_TYPES:
        data = getattr(bundle, attr, None)
        if data:
            bundle.sources_found.append(label)
        else:
            bundle.sources_not_found.append(label)

    if bundle.fta_data:
        bundle.sources_found.append("הסכמי סחר")
    else:
        bundle.sources_not_found.append("הסכמי סחר")
