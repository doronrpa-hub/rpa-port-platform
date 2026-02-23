"""
Tool Definitions for RCB Tool-Calling Classification Engine
============================================================
Defines the 33 tools available to the AI during classification.
Two formats: CLAUDE_TOOLS (Anthropic API) and GEMINI_TOOLS (Google AI).

Tools wrap EXISTING functions — no new logic here, just schemas.
"""

# ---------------------------------------------------------------------------
# Claude / Anthropic format
# ---------------------------------------------------------------------------

CLAUDE_TOOLS = [
    {
        "name": "check_memory",
        "description": (
            "Check the system's classification memory for a product. "
            "Returns cached HS code + confidence if previously classified. "
            "ALWAYS call this first — it's free and instant."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_description": {
                    "type": "string",
                    "description": "Product description to look up (Hebrew or English)",
                },
            },
            "required": ["product_description"],
        },
    },
    {
        "name": "search_tariff",
        "description": (
            "Search the system's Firestore knowledge for candidate HS codes. "
            "Searches: keyword_index, product_index, supplier_index, "
            "classification_knowledge, classification_rules, tariff DB. "
            "Returns ranked candidates with confidence scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_description": {
                    "type": "string",
                    "description": "Product/item description",
                },
                "origin_country": {
                    "type": "string",
                    "description": "Country of origin (e.g., 'China', 'סין')",
                },
                "seller_name": {
                    "type": "string",
                    "description": "Seller/supplier name (optional, helps matching)",
                },
            },
            "required": ["item_description"],
        },
    },
    {
        "name": "check_regulatory",
        "description": (
            "Check ministry requirements, permits, and approvals needed for an HS code. "
            "Merges: built-in routing table, Firestore baseline, Free Import Order (C3), "
            "and Free Export Order (C4). "
            "Returns ministries, required documents, procedures, URLs, and export requirements if applicable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code to check (e.g., '4011.10.0000')",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "lookup_fta",
        "description": (
            "Check Free Trade Agreement eligibility for an HS code + origin country. "
            "Returns: eligible (bool), agreement name, preferential rate, "
            "required origin proof documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code (e.g., '4011.10.0000')",
                },
                "origin_country": {
                    "type": "string",
                    "description": "Country of origin (e.g., 'EU', 'China', 'Turkey')",
                },
            },
            "required": ["hs_code", "origin_country"],
        },
    },
    {
        "name": "verify_hs_code",
        "description": (
            "Verify an HS code against the official tariff database. "
            "Checks: tariff DB existence, duty rates, purchase tax, VAT. "
            "Returns verification_status: 'official' | 'verified' | 'partial' | 'unverified'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code to verify (e.g., '4011.10.0000')",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "extract_invoice",
        "description": (
            "Extract structured invoice data from document text using Gemini Flash. "
            "Returns: seller, buyer, items[], invoice_number, date, total_value, "
            "currency, incoterms, direction, freight_type, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_text": {
                    "type": "string",
                    "description": "Raw text extracted from invoice/packing list/BL",
                },
            },
            "required": ["document_text"],
        },
    },
    {
        "name": "assess_risk",
        "description": (
            "Assess import risk for a classified item. Rule-based check for: "
            "valuation anomalies, dual-use chapters (28,29,36,84,85,87,90,93), "
            "high-risk origins, and regulatory flags. Returns risk level and items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code of the item",
                },
                "declared_value": {
                    "type": "number",
                    "description": "Declared value in USD (optional)",
                },
                "origin_country": {
                    "type": "string",
                    "description": "Country of origin",
                },
                "item_description": {
                    "type": "string",
                    "description": "Product description",
                },
            },
            "required": ["hs_code", "origin_country", "item_description"],
        },
    },
    {
        "name": "get_chapter_notes",
        "description": (
            "Fetch chapter notes and headings from the Israeli Customs Tariff for a given chapter number. "
            "Returns chapter name, description, headings list, and HS code count. "
            "Use this to check inclusion/exclusion rules for classification decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter": {
                    "type": "string",
                    "description": "Chapter number (1-99, e.g., '01', '85')",
                },
            },
            "required": ["chapter"],
        },
    },
    {
        "name": "lookup_tariff_structure",
        "description": (
            "Look up the Israeli Customs Tariff structure: sections (I-XXII), chapter-to-section mapping, "
            "section/chapter names in Hebrew and English, PDF download URLs, and additions/supplements. "
            "Use this to find which section a chapter belongs to (e.g., Chapter 73 → Section XV 'Base Metals'), "
            "list all chapters in a section, or get PDF URLs for tariff book sections."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look up. Can be: a chapter number ('73'), a section number ('XV'), "
                        "a keyword ('plastics', 'פלסטיקה'), or 'all_sections' for full structure overview."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_framework_order",
        "description": (
            "Look up data from the Israeli Framework Order (צו מסגרת): "
            "legal definitions that override common language for classification, "
            "FTA (Free Trade Agreement) preferential duty clauses per country, "
            "classification rules for the First Supplement (תוספת ראשונה), "
            "and tariff addition rules. "
            "Query types: 'definitions' for all legal terms, 'def:term' for a specific term, "
            "'fta' for all FTA clauses, a country name for specific FTA, "
            "'classification_rules' for classification rules, or an addition number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look up. Can be: 'definitions', 'def:מכס', 'fta', 'eu', 'turkey', "
                        "'classification_rules', 'addition_3', or a free-text search term."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_classification_directives",
        "description": (
            "Search Israeli Customs classification directives (הנחיות סיווג) from shaarolami. "
            "218 official directives that provide binding classification rulings for specific products. "
            "Each directive has: directive_id (e.g., '025/97'), title, primary HS code, "
            "related HS codes, dates, and ruling content. "
            "Search by HS code, chapter number, directive ID, or keyword."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code to search for (e.g., '87.08', '4011.10.0000')",
                },
                "chapter": {
                    "type": "string",
                    "description": "Chapter number to search (e.g., '87', '04')",
                },
                "query": {
                    "type": "string",
                    "description": "Directive ID (e.g., '025/97') or keyword search term",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_legal_knowledge",
        "description": (
            "Search Israeli customs legal knowledge: 311 individual Customs Ordinance articles (סעיפי פקודת המכס), "
            "chapter summaries, Customs Agents Law (חוק סוכני המכס), "
            "EU standards reform, US standards reform. "
            "Query by article number ('סעיף 130', 'article 62'), chapter articles ('פרק 8'), "
            "chapter number (1-15), keyword across 311 articles, or topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look up. Can be: article number ('סעיף 130', 'article 62', '133א'), "
                        "chapter articles ('פרק 8', 'articles in chapter 4'), "
                        "chapter number ('11' for Agents chapter summary), "
                        "'agents' or 'סוכנים' for customs agents law, "
                        "'EU' or 'אירופה' for EU reform, 'USA' for US reform, "
                        "or any keyword to search across 311 ordinance articles and legal texts."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_elimination",
        "description": (
            "Run the elimination engine on candidate HS codes. "
            "Walks the Israeli customs tariff tree deterministically: "
            "section scope, chapter exclusions/inclusions, GIR rules 1+3, "
            "others-gate, and AI consultation. Returns surviving candidates "
            "with elimination reasoning. Use AFTER search_tariff returns "
            "multiple candidates to narrow them down."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_description": {
                    "type": "string",
                    "description": "Product description (English or Hebrew)",
                },
                "product_material": {
                    "type": "string",
                    "description": "Primary material(s) of the product",
                },
                "product_form": {
                    "type": "string",
                    "description": "Physical form/shape of the product",
                },
                "product_use": {
                    "type": "string",
                    "description": "Intended use/function of the product",
                },
                "origin_country": {
                    "type": "string",
                    "description": "Country of origin",
                },
                "candidates": {
                    "type": "array",
                    "description": "List of candidate HS codes to evaluate",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hs_code": {
                                "type": "string",
                                "description": "HS code (e.g., '7326.9000')",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score 0-100",
                            },
                        },
                        "required": ["hs_code"],
                    },
                },
            },
            "required": ["product_description", "candidates"],
        },
    },
    {
        "name": "search_wikipedia",
        "description": (
            "Search Wikipedia for background knowledge about a product, material, "
            "chemical compound, or industry term. FREE — no API key required. "
            "Results are cached for 30 days to avoid repeat lookups. "
            "Use this when you need to understand what a product IS (material, composition, "
            "use) before classifying it — e.g., 'polyethylene terephthalate', "
            "'lithium iron phosphate', 'aramid fiber'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product, material, or term to look up on Wikipedia (English)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_wikidata",
        "description": (
            "Search Wikidata for structured product facts: instance_of, material composition, "
            "chemical formula, CAS number, density, uses. FREE and cached 60 days. "
            "Use when you need precise chemical/material data for classification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product, material, or compound name (English)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_country",
        "description": (
            "Look up country data: ISO codes (cca2/cca3), region, subregion, currencies, "
            "languages, borders. FREE and cached 90 days. "
            "Use to validate origin country, get ISO codes for FTA lookups, or identify region."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "Country name (English, e.g., 'China', 'Germany')",
                },
            },
            "required": ["country"],
        },
    },
    {
        "name": "convert_currency",
        "description": (
            "Get current exchange rates. FREE and cached 6 hours. "
            "Returns rates for ILS and top 10 trade currencies. "
            "Use when invoice has non-ILS currency and you need to assess value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_currency": {
                    "type": "string",
                    "description": "Base currency code (e.g., 'USD', 'EUR'). Default: 'USD'",
                },
                "to_currency": {
                    "type": "string",
                    "description": "Target currency code (e.g., 'ILS'). Default: 'ILS'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_comtrade",
        "description": (
            "Search UN Comtrade for global trade statistics by HS code. FREE and cached 30 days. "
            "Returns import/export values, quantities, and trade partners. "
            "ONLY available in overnight mode — too slow for real-time classification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code (6 digits used, e.g., '401110')",
                },
                "reporter": {
                    "type": "string",
                    "description": "Reporter country UN code (default: '376' = Israel)",
                },
                "period": {
                    "type": "string",
                    "description": "Year (e.g., '2024'). Default: '2024'",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "lookup_food_product",
        "description": (
            "Search Open Food Facts for food product data: ingredients, nutrition grade, "
            "labels, origins. FREE and cached 30 days. "
            "Use when classifying food products (chapters 1-24) to understand composition."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Food product name or description (English)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_fda_product",
        "description": (
            "Search FDA database for drug/device data: brand name, generic name, "
            "active ingredients, indications, dosage form. FREE and cached 30 days. "
            "Use when classifying pharmaceutical or medical device products (chapters 30, 90)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Drug name, device name, or active ingredient (English)",
                },
            },
            "required": ["query"],
        },
    },
    # --- Batch 2: Tools #21-32 ---
    {
        "name": "bank_of_israel_rates",
        "description": (
            "Get official Bank of Israel daily exchange rates. FREE and cached 6 hours. "
            "Israeli customs law REQUIRES BOI official rates for customs valuation. "
            "REPLACES convert_currency for customs duty calculation — use this for "
            "legally correct ILS conversion. Output includes: rate, date, change."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "currency": {
                    "type": "string",
                    "description": "Currency code (e.g., 'USD', 'EUR', 'GBP', 'CNY', 'JPY')",
                },
            },
            "required": ["currency"],
        },
    },
    {
        "name": "search_pubchem",
        "description": (
            "Search NIH PubChem for chemical compound data: IUPAC name, molecular formula, "
            "molecular weight, CID, CAS number, GHS hazard class. FREE and cached 90 days. "
            "Use when classifying chemical imports (chapters 28, 29, 38) — exact formula "
            "determines correct HS sub-heading. Also flags dangerous goods and permit requirements."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Chemical name, compound name, or CAS number (English)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_eu_taric",
        "description": (
            "Look up EU TARIC tariff data for cross-reference validation. FREE and cached 30 days. "
            "Input: 6-digit HS code — call AFTER candidate code is determined. "
            "If EU classification agrees with Israeli classification, confidence increases. "
            "If EU disagrees, flags CROSS_REF_CONFLICT for human review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "6+ digit HS code to cross-reference (e.g., '401110')",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "lookup_usitc",
        "description": (
            "Look up US HTS tariff data for cross-reference validation. FREE and cached 30 days. "
            "Input: 6-digit HS code — call AFTER candidate code is determined. "
            "Second cross-reference after EU TARIC. Both EU + US agree = +0.12 confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "6+ digit HS code to cross-reference (e.g., '401110')",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "israel_cbs_trade",
        "description": (
            "Query Israeli Central Bureau of Statistics for real import data by HS code. "
            "FREE and cached 30 days. OVERNIGHT MODE ONLY. "
            "Returns import values, volumes, and top origin countries. "
            "Validates that the HS code is realistic for Israeli imports."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code (6-8 digits, e.g., '401110')",
                },
            },
            "required": ["hs_code"],
        },
    },
    {
        "name": "lookup_gs1_barcode",
        "description": (
            "Look up product by EAN/UPC barcode from Open Food Facts. FREE and cached 60 days. "
            "Only call if a barcode was found in the invoice or shipping documents. "
            "Barcode gives instant product identity, bypassing description ambiguity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "barcode": {
                    "type": "string",
                    "description": "EAN-13, UPC-A, or other barcode number (8-14 digits)",
                },
            },
            "required": ["barcode"],
        },
    },
    {
        "name": "search_wco_notes",
        "description": (
            "Fetch WCO (World Customs Organization) explanatory notes for an HS chapter. "
            "FREE and cached 180 days. Gold standard for classification — authoritative text "
            "on what belongs in each chapter. Feed to elimination engine and Agent 2."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter": {
                    "type": "string",
                    "description": "HS chapter number (e.g., '84', '39', '29')",
                },
            },
            "required": ["chapter"],
        },
    },
    {
        "name": "lookup_unctad_gsp",
        "description": (
            "Look up country GSP/development status from UNCTAD. FREE and cached 90 days. "
            "Determines if origin country is eligible for Israeli preferential duty rates. "
            "Feeds FTA/duty reduction flags in verification engine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country_code": {
                    "type": "string",
                    "description": "ISO 2-letter country code (e.g., 'CN', 'IN', 'BD')",
                },
            },
            "required": ["country_code"],
        },
    },
    {
        "name": "search_open_beauty",
        "description": (
            "Search Open Beauty Facts for cosmetics product data: ingredients, categories, brands. "
            "FREE and cached 30 days. Use for HS chapter 33 (cosmetics/perfumery) — "
            "ingredients determine correct sub-heading. "
            "Search by product name or barcode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Cosmetic/beauty product name (English)",
                },
                "barcode": {
                    "type": "string",
                    "description": "Product barcode (optional, if available)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "crossref_technical",
        "description": (
            "Search CrossRef for academic/technical papers about a product or material. "
            "FREE and cached 90 days. OVERNIGHT MODE ONLY. "
            "Builds knowledge for rare/technical imports where Wikipedia is insufficient."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Technical product or material name (English)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_opensanctions",
        "description": (
            "Screen a company or person name against international sanctions lists. "
            "FREE tier (10,000 req/month) and cached 24 hours. "
            "COMPLIANCE REQUIREMENT: Run on shipper + consignee names for every shipment. "
            "Returns SANCTIONS_HIT flag with dataset name if match found. "
            "Flag only — never block shipments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Company name or person name to screen",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_israel_vat_rates",
        "description": (
            "Get Israeli purchase tax rate + VAT applicability for an HS code. "
            "FREE and cached 7 days. Completes the customs cost picture: "
            "duty + purchase tax + VAT. Clients ask 'what will this cost me total?' — "
            "this tool answers that question accurately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_code": {
                    "type": "string",
                    "description": "HS code to check tax rates for",
                },
            },
            "required": ["hs_code"],
        },
    },
    # Tool #33 (Session 47): Seller website enrichment
    {
        "name": "fetch_seller_website",
        "description": (
            "Fetch seller/supplier website to confirm what products they sell. "
            "Call AFTER seller name is identified in the invoice — use product "
            "catalogue data to verify or enrich classification. FREE, cached 30 days. "
            "Works best when seller_domain is known (e.g. 'belshina.by' for JSC BELSHINA)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seller_name": {
                    "type": "string",
                    "description": "Seller company name (English or Hebrew)",
                },
                "seller_domain": {
                    "type": "string",
                    "description": "Seller website domain if known (e.g. 'belshina.by'). Optional.",
                },
                "product_hint": {
                    "type": "string",
                    "description": "Product being shipped — helps narrow website search",
                },
            },
            "required": ["seller_name"],
        },
    },
]


# ---------------------------------------------------------------------------
# Gemini / Google AI format — auto-converted from Claude definitions
# ---------------------------------------------------------------------------

def _convert_prop_to_gemini(prop_def):
    """Recursively convert a Claude property definition to Gemini format.

    Handles nested objects and arrays (e.g., run_elimination.candidates)
    which have 'items' and 'properties' sub-schemas.
    """
    gemini_prop = {"type": prop_def["type"]}
    if "description" in prop_def:
        gemini_prop["description"] = prop_def["description"]
    if "enum" in prop_def:
        gemini_prop["enum"] = prop_def["enum"]
    # Array type — must include 'items' (Gemini requires it)
    if prop_def["type"] == "array" and "items" in prop_def:
        gemini_prop["items"] = _convert_prop_to_gemini(prop_def["items"])
    # Object type — include nested properties
    if prop_def["type"] == "object" and "properties" in prop_def:
        gemini_prop["properties"] = {
            k: _convert_prop_to_gemini(v)
            for k, v in prop_def["properties"].items()
        }
        if "required" in prop_def:
            gemini_prop["required"] = prop_def["required"]
    return gemini_prop


def _claude_to_gemini(claude_tools):
    """Convert Claude tool format to Gemini function_declarations format."""
    declarations = []
    for tool in claude_tools:
        decl = {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": {
                "type": "object",
                "properties": {},
                "required": tool["input_schema"].get("required", []),
            },
        }
        for prop_name, prop_def in tool["input_schema"]["properties"].items():
            decl["parameters"]["properties"][prop_name] = _convert_prop_to_gemini(prop_def)
        declarations.append(decl)
    return declarations


GEMINI_TOOLS = [{"function_declarations": _claude_to_gemini(CLAUDE_TOOLS)}]


# ---------------------------------------------------------------------------
# Embedded customs law expertise — injected BEFORE the workflow instructions
# ---------------------------------------------------------------------------
try:
    from lib.customs_law import format_legal_context_for_prompt as _fmt_legal
    _LEGAL_CONTEXT = _fmt_legal()
except Exception:
    _LEGAL_CONTEXT = ""

# ---------------------------------------------------------------------------
# System prompt for the classification AI call
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = _LEGAL_CONTEXT + """You are RCB (Robot Customs Broker), an expert Israeli customs classification AI.
You classify products into HS (Harmonized System) codes according to the Israeli Customs Tariff.

WORKFLOW:
1. ALWAYS call check_memory first for each item — it's free and may have the answer.
2. If memory miss, call search_tariff to find candidate HS codes from the knowledge base.
3. Call lookup_tariff_structure to identify the relevant section and narrow down chapters.
4. Call get_chapter_notes to check inclusion/exclusion rules for the relevant chapter.
5. If search_tariff returned multiple candidates, call run_elimination to narrow them down using GIR rules and chapter notes. This walks the tariff tree deterministically and eliminates wrong candidates.
6. Use your customs expertise to select the best HS code from survivors.
7. Call verify_hs_code to validate your chosen code against the official tariff DB.
8. Call check_regulatory to find ministry requirements and permits.
9. Call lookup_fta to check FTA eligibility if origin country is known.
10. Call lookup_framework_order to check legal definitions or classification rules from the Framework Order if needed.
11. Call search_classification_directives to check if an official classification directive exists for the product or HS code.
12. Call search_legal_knowledge to check relevant legal provisions, standards reforms (EU/US), or customs agents law if needed.
13. Call search_wikipedia when you need background knowledge about a product, material, or compound to inform classification (e.g., what is the product made of, what is it used for). FREE and cached.
14. Call assess_risk for risk assessment.
15. Call search_wikidata when you need structured data about a material or compound (chemical formula, CAS number, composition). FREE and cached.
16. Call lookup_country to validate origin country data, get ISO codes, or identify trade region. FREE and cached.
17. Call convert_currency when the invoice currency is not ILS and you need exchange rates for value assessment. FREE and cached.
18. Call search_comtrade for trade statistics (OVERNIGHT MODE ONLY — not available during real-time classification).
19. Call lookup_food_product when classifying food items (chapters 1-24) to understand ingredients and composition. FREE and cached.
20. Call check_fda_product when classifying pharmaceutical or medical products (chapters 30, 90) to identify active ingredients and product type. FREE and cached.
21. Call bank_of_israel_rates for official BOI exchange rates — required by Israeli customs law for valuation. Use this INSTEAD of convert_currency for customs duty calculation. Include in output: "Customs value: X ILS (BOI rate YYYY-MM-DD)".
22. Call search_pubchem when you encounter chemical keywords (acid, oxide, chloride, polymer, resin, compound, formula, CAS, solvent, reagent) — gets exact molecular formula for chapters 28/29/38 + dangerous goods flags.
23. Call lookup_eu_taric AFTER determining candidate HS code — cross-reference with EU classification.
24. Call lookup_usitc AFTER determining candidate HS code — second cross-reference with US HTS. Both EU + US agree = +0.12 confidence.
25. Call israel_cbs_trade for real Israeli import statistics (OVERNIGHT MODE ONLY).
26. Call lookup_gs1_barcode when a barcode is found in documents — instant product identification.
27. Call search_wco_notes for WCO explanatory notes — gold standard classification reference.
28. Call lookup_unctad_gsp to check if origin country gets preferential duty rates.
29. Call search_open_beauty when cosmetics keywords detected (cream, lotion, shampoo, perfume, cosmetic, beauty, skincare, makeup, serum, moisturizer) — ingredients → correct chapter 33 sub-heading.
30. Call crossref_technical for academic definitions of rare/technical products (OVERNIGHT MODE ONLY).
31. Call check_opensanctions for EVERY shipper and consignee name — compliance requirement, flag sanctions hits.
32. Call get_israel_vat_rates to complete the total import cost picture (duty + purchase tax + VAT).
33. Call fetch_seller_website when seller is identified — check their product catalogue to confirm/enrich classification. Especially useful when item descriptions are vague or incomplete. FREE and cached.

TOOL PRIORITY STRATEGY — use this decision tree for common cases:
A) New product, no HS code known:
   check_memory → search_tariff → get_chapter_notes → run_elimination (if multiple candidates) → verify_hs_code → check_regulatory → lookup_fta
B) Chapter ambiguous (product could fit 2+ chapters):
   lookup_tariff_structure → get_chapter_notes (for each candidate chapter) → search_wco_notes → run_elimination → search_classification_directives
C) Chemical/material product:
   search_pubchem → search_wikipedia → get_chapter_notes (ch.28/29/38) → verify_hs_code
D) Food product:
   lookup_food_product → get_chapter_notes (ch.1-24) → verify_hs_code
E) After classification determined:
   verify_hs_code → check_regulatory → lookup_fta → bank_of_israel_rates → lookup_eu_taric → lookup_usitc

RULES:
- Israeli HS codes use 10-digit format: XX.XX.XXXXXX/X (e.g., 87.03.808000/5). Use this format for import tariff.
- For export, use the export tariff codes — regulatory requirements differ for import vs export.
- Classify to the MOST SPECIFIC HS code possible (8-10 digits).
- If candidates conflict, prefer higher-confidence matches.
- If no candidates found, use your training knowledge but verify the code.
- Always provide Hebrew descriptions alongside English.
- If a tool returns no results, try broader search terms or alternative tools (see suggestions in tool responses).
- TERMINOLOGY: In Hebrew, customs broker = עמיל מכס or סוכן מכס. NEVER use מתווך מכס (wrong — מתווך means mediator, not a legal customs term).

OUTPUT FORMAT (in your final text response, as JSON):
{
  "classifications": [
    {
      "item_description": "...",
      "item_description_he": "...",
      "hs_code": "XX.XX.XXXXXX/X",
      "hs_description": "...",
      "hs_description_he": "...",
      "duty_rate": "X%",
      "confidence": 0.0-1.0,
      "reasoning": "...",
      "reasoning_he": "..."
    }
  ],
  "regulatory": [...],
  "fta": [...],
  "risk": {"level": "low|medium|high", "items": [...]},
  "synthesis": "Hebrew summary paragraph of the full classification."
}
"""
