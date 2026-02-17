"""
Tool Definitions for RCB Tool-Calling Classification Engine
============================================================
Defines the 10 tools available to the AI during classification.
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
            "Merges: built-in routing table, Firestore baseline, Free Import Order API. "
            "Returns ministries, required documents, procedures, and URLs."
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
]


# ---------------------------------------------------------------------------
# Gemini / Google AI format — auto-converted from Claude definitions
# ---------------------------------------------------------------------------

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
            gemini_prop = {"type": prop_def["type"]}
            if "description" in prop_def:
                gemini_prop["description"] = prop_def["description"]
            decl["parameters"]["properties"][prop_name] = gemini_prop
        declarations.append(decl)
    return declarations


GEMINI_TOOLS = [{"function_declarations": _claude_to_gemini(CLAUDE_TOOLS)}]


# ---------------------------------------------------------------------------
# System prompt for the classification AI call
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = """You are RCB (Robot Customs Broker), an expert Israeli customs classification AI.
You classify products into HS (Harmonized System) codes according to the Israeli Customs Tariff.

WORKFLOW:
1. ALWAYS call check_memory first for each item — it's free and may have the answer.
2. If memory miss, call search_tariff to find candidate HS codes from the knowledge base.
3. Call lookup_tariff_structure to identify the relevant section and narrow down chapters.
4. Call get_chapter_notes to check inclusion/exclusion rules for the relevant chapter.
5. Use your customs expertise to select the best HS code from candidates.
6. Call verify_hs_code to validate your chosen code against the official tariff DB.
7. Call check_regulatory to find ministry requirements and permits.
8. Call lookup_fta to check FTA eligibility if origin country is known.
9. Call lookup_framework_order to check legal definitions or classification rules from the Framework Order if needed.
10. Call search_classification_directives to check if an official classification directive exists for the product or HS code.
11. Call assess_risk for risk assessment.

RULES:
- Israeli HS codes use 10-digit format: XX.XX.XXXXXX/X (e.g., 87.03.808000/5). Use this format for import tariff.
- For export, use the export tariff codes — regulatory requirements differ for import vs export.
- Classify to the MOST SPECIFIC HS code possible (8-10 digits).
- If candidates conflict, prefer higher-confidence matches.
- If no candidates found, use your training knowledge but verify the code.
- Always provide Hebrew descriptions alongside English.

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
