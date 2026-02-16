"""
language_tools.py — Session 14: Language Tools Overhaul
=======================================================
RCB system language engine: vocabulary, spelling, grammar, letter structure,
subject lines, text polishing, style learning, and communication-based learning.

Classes:
    CustomsVocabulary      — Domain vocabulary extracted from librarian documents
    HebrewLanguageChecker  — Spell & grammar checking for Hebrew customs text
    LetterStructure        — Visual letter structure for all output types
    SubjectLineGenerator   — Professional, readable subject lines
    TextPolisher           — LLM-powered final text polish
    StyleAnalyzer          — Formal vs. casual register detection from real communication
    LanguageLearner        — Learn from corrections, documents, and actual communication
    JokeBank               — Curated non-offensive humor for personality

Version: 4.1.0 (Session 14)
"""

import re
import json
import random
import string
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "4.1.0"

# ═══════════════════════════════════════════════════════════════════════════
# VERIFIED ISRAELI CUSTOMS CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️  CRITICAL: These values affect duty calculations and classifications.
#     Do NOT change without verifying against official Israeli customs sources.
#     Last verified: 2026-02-06
# ═══════════════════════════════════════════════════════════════════════════

# Israeli VAT rate — changed from 17% to 18% on January 1, 2025
# Source: Israel Tax Authority, 2025 Budget Law
ISRAEL_VAT_RATE = 0.18          # 18%
ISRAEL_VAT_RATE_DISPLAY = "18%"
ISRAEL_VAT_RATE_PERCENT = 18

# Israeli HS code structure — 10 digits (international 6 + 4 Israeli national)
# Display format: XX.XX.XXXXXX/X (e.g., 87.08.998000/0)
# Internal format: 10 digits zero-padded (e.g., 8708998000)
# Source: Israel Tax Authority — "פרט מכס הינו מספר בין 10 ספרות"
# Note: librarian.py has get_israeli_hs_format() and normalize_hs_code() — use those
#       for actual formatting. These constants are for reference and validation only.
ISRAEL_HS_CODE_DIGITS = 10
ISRAEL_HS_CODE_FORMAT = "XX.XX.XXXXXX/X"
ISRAEL_HS_CODE_EXAMPLE = "87.08.998000/0"
ISRAEL_HS_CODE_PATTERN = r'^\d{2}\.\d{2}\.\d{6}/\d$'  # Israeli display format

# De minimis threshold for personal imports
# Source: Finance Ministry order, signed Nov 2025 (Smotrich), effective Dec 2025
# Note: This is USD, not ILS. Approximately 545 ILS at current exchange rates.
# Under legislative review/challenge from business groups.
ISRAEL_DE_MINIMIS_USD = 150
ISRAEL_DE_MINIMIS_CURRENCY = "USD"
ISRAEL_DE_MINIMIS_NOTE = "Updated Dec 2025 ($75→$150 USD), under legislative review"

class LetterType(Enum):
    CLASSIFICATION_REPORT = "classification_report"
    CLARIFICATION_REQUEST = "clarification_request"
    KNOWLEDGE_RESPONSE = "knowledge_response"
    MISSING_DOCS_REQUEST = "missing_docs_request"
    STATUS_UPDATE = "status_update"
    COMBINED_REQUEST = "combined_request"
    GENERIC = "generic"

class Tone(Enum):
    CUSTOMS_BROKER = "customs_broker"      # Professional Hebrew, technical terms, concise
    IMPORTER = "importer"                  # Professional but explanatory
    SUPPLIER = "supplier"                  # English, formal business
    INTERNAL = "internal"                  # Casual Hebrew, abbreviations OK

class LanguageRegister(Enum):
    """Register levels learned from comparing official docs vs. real emails."""
    OFFICIAL = "official"          # פקודת המכס, תקנות, חוזרים
    PROFESSIONAL = "professional"  # Broker-to-customs, formal letters
    BUSINESS = "business"          # Importer-to-broker emails
    CASUAL = "casual"              # Internal team chat, quick emails
    COLLOQUIAL = "colloquial"      # Slang, abbreviations, SMS-style

# Status emojis for subject lines
STATUS_EMOJI = {
    "approved": "✅",
    "needs_action": "⚠️",
    "info": "📋",
    "in_progress": "🔄",
    "urgent": "🚨",
    "completed": "✔️",
    "rejected": "❌",
    "waiting": "⏳",
}

# ─── Known customs abbreviations ─────────────────────────────────────────────
CUSTOMS_ABBREVIATIONS = {
    'תש"ר': "תהליך שחרור רגיל",
    'מצ"ב': "מצורף בזה",
    'רש"מ': "רשימון מכס",
    'שע"מ': "שער עולמי",
    'מע"מ': "מס ערך מוסף (18%)",
    'מס"ב': "מס ערך מוסף בשיעור אפס",
    'אפ"י': "אגף פיקוח על היצוא",
    'סב"ן': "סחורה בלתי נתבעת",
    'פט"מ': "פטור ממכס",
    'רל"ן': "רשימון לניכוי",
    'בל"ד': "בית לחם דרום (מעבר)",
    "מ.ב": "מסמך ביטחון",
    "CIF": "Cost Insurance Freight",
    "FOB": "Free On Board",
    "CFR": "Cost and Freight",
    "EXW": "Ex Works",
    "FCA": "Free Carrier",
    "DDP": "Delivered Duty Paid",
    "DAP": "Delivered at Place",
    "EUR.1": "תעודת תנועה אירופית",
    "A.TR": "תעודת תנועה טורקיה",
    "CO": "Certificate of Origin / תעודת מקור",
    "B/L": "Bill of Lading / שטר מטען",
    "AWB": "Air Waybill / שטר מטען אווירי",
    "HS": "Harmonized System / שיטה מתואמת",
}

# ─── Common Hebrew typos in customs domain ────────────────────────────────────
KNOWN_TYPOS = {
    "רישמון": "רשימון",
    "הצאהרה": "הצהרה",
    "סיווג": "סיווג",      # correct form — listed to avoid "סווג"
    "סווג": "סיווג",
    "שיחרור": "שחרור",
    "מישלוח": "משלוח",
    "חישבון": "חשבון",
    "תיעוד": "תיעוד",      # correct
    "תעוד": "תיעוד",
    "אישפוז": "אחסון",     # common confusion
    "מחסן": "מחסן",         # correct
    "מחסאן": "מחסן",
    "ייבוא": "יבוא",
    "ייצוא": "יצוא",
    "פאקטורה": "פקטורה",
    "אינבויס": "חשבונית",
    "ארנונה": "ארנונה",     # correct — not customs
    "פרופורמה": "פרופורמה", # correct
    "פרופרמה": "פרופורמה",
    "קונסיגנציה": "קונסיגנציה",  # correct
    "קונסיגנצייה": "קונסיגנציה",
    "רגולציה": "רגולציה",   # correct
    "רגולצייה": "רגולציה",
    "דקלרציה": "הצהרה",     # translate to Hebrew
    "טריף": "תעריף",
}

# ─── Common Hebrew formal ↔ informal equivalents ──────────────────────────────
FORMAL_INFORMAL_MAP = {
    # informal → formal
    "להוציא את הסחורה": "לשחרר את המשלוח",
    "לשלם מכס": "לשלם את חיובי המכס",
    "ניירת": "מסמכים נלווים",
    "לסגור תיק": "להשלים את תהליך השחרור",
    "בעיה עם המכס": "עיכוב בתהליך השחרור",
    "הכל בסדר": "המשלוח אושר לשחרור",
    "חסר": "נדרש להשלמה",
    "צריך לתקן": "נדרש תיקון",
    "שלחו לי": "נא להעביר",
    "אפשר לקבל": "נבקש לקבל",
    "תבדקו": "נא לבדוק",
    "תעדכנו": "נא לעדכן",
    "בהקדם": "בהקדם האפשרי",
    "ישר": "באופן ישיר",
    "סבבה": "מאושר",
    "יאללה": "נא להמשיך",
    "מגניב": "מצוין",
    "אחלה": "תודה רבה",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SpellingIssue:
    original: str
    suggestion: str
    position: int = 0
    confidence: float = 1.0
    source: str = "typo_dict"  # typo_dict, vocabulary, pattern

@dataclass
class GrammarIssue:
    text: str
    issue_type: str         # gender_agreement, construct_state, punctuation, rtl_mix
    suggestion: str
    explanation: str = ""

@dataclass
class StyleObservation:
    """Learned from real communication — what register a phrase belongs to."""
    phrase: str
    register: LanguageRegister
    source_type: str        # "official_doc", "email_incoming", "email_outgoing", "correction"
    frequency: int = 1
    last_seen: str = ""
    context: str = ""

@dataclass
class LetterHead:
    company_name_he: str = 'ר.פ.א - פורט בע"מ'
    company_name_en: str = "RPA Port Ltd."
    logo_url: str = ""
    date: str = ""
    reference: str = ""

@dataclass
class SignatureBlock:
    name: str = "מערכת RCB"
    title: str = "מערכת סיווג אוטומטית"
    company: str = 'ר.פ.א - פורט בע"מ'
    email: str = ""
    phone: str = ""


# ═════════════════════════════════════════════════════════════════════════════
# 1. CUSTOMS VOCABULARY ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class CustomsVocabulary:
    """
    Domain vocabulary extracted from librarian documents.
    
    Built from:
    - DOCUMENT_TAGS (226 tags with Hebrew names)
    - CUSTOMS_HANDBOOK_CHAPTERS (86 chapters with Hebrew names)
    - TAG_KEYWORDS (160 keyword rules)
    - Known abbreviations
    - Learned terms from actual documents in Firestore
    - Learned terms from real email communication
    """

    def __init__(self):
        self.terms_he: dict = {}          # Hebrew term → {definition, context, usage, register}
        self.terms_en: dict = {}          # English term → Hebrew equivalent
        self.abbreviations: dict = dict(CUSTOMS_ABBREVIATIONS)
        self.collocations: dict = {}      # Common word pairs/phrases
        self.keywords_to_tags: dict = {}  # keyword → tag mapping
        self._initialized = False

    def add_term(self, term_he: str, term_en_or_key: str, 
                 source: str = "manual", definition: str = "",
                 register: str = "professional"):
        """Add a Hebrew term with its English key and metadata."""
        self.terms_he[term_he] = {
            "key": term_en_or_key,
            "source": source,
            "definition": definition,
            "register": register,
            "added": datetime.now(timezone.utc).isoformat(),
        }
        if term_en_or_key and not term_en_or_key.startswith("tag_"):
            self.terms_en[term_en_or_key.lower()] = term_he

    def add_keyword(self, keyword: str, tag: str, source: str = "tag_keywords"):
        """Add a keyword → tag mapping."""
        self.keywords_to_tags[keyword.lower()] = {
            "tag": tag,
            "source": source,
        }

    def add_collocation(self, phrase: str, meaning: str, register: str = "professional"):
        """Add a common word pair/phrase."""
        self.collocations[phrase] = {
            "meaning": meaning,
            "register": register,
        }

    def lookup(self, term: str) -> Optional[dict]:
        """Look up a term in Hebrew or English."""
        if term in self.terms_he:
            return {"lang": "he", "term": term, **self.terms_he[term]}
        lower = term.lower()
        if lower in self.terms_en:
            he_term = self.terms_en[lower]
            return {"lang": "en", "term": he_term, **self.terms_he.get(he_term, {})}
        if term in self.abbreviations:
            return {"lang": "abbr", "term": term, "expansion": self.abbreviations[term]}
        return None

    def suggest_correction(self, text: str) -> list:
        """Check text against vocabulary, suggest corrections for unknown terms."""
        suggestions = []
        for typo, correction in KNOWN_TYPOS.items():
            if typo in text and typo != correction:
                suggestions.append(SpellingIssue(
                    original=typo,
                    suggestion=correction,
                    confidence=0.95,
                    source="typo_dict",
                ))
        return suggestions

    def get_formal_term(self, informal: str) -> Optional[str]:
        """Convert colloquial/informal term to official customs term."""
        return FORMAL_INFORMAL_MAP.get(informal)

    def get_informal_term(self, formal: str) -> Optional[str]:
        """Convert formal term to common informal equivalent."""
        reverse = {v: k for k, v in FORMAL_INFORMAL_MAP.items()}
        return reverse.get(formal)

    def expand_abbreviation(self, abbr: str) -> Optional[str]:
        """Expand a known abbreviation."""
        return self.abbreviations.get(abbr)

    def enrich_from_text(self, text: str, source: str = "document",
                         register: str = "professional"):
        """
        Extract potential new terms from document/email text.
        Simple heuristic: find quoted terms, terms near keywords like 'נקרא', 'מוגדר'.
        """
        # Pattern: "X" (מונח) — quoted Hebrew terms
        quoted = re.findall(r'"([^"]{2,30})"', text)
        for q in quoted:
            if q not in self.terms_he and any('\u0590' <= c <= '\u05FF' for c in q):
                self.add_term(q, "", source=source, register=register)

        # Pattern: terms defined with "נקרא", "מוגדר כ", "הוא"
        defined = re.findall(r'(\S+)\s+(?:נקרא|מוגדר כ|הינו|הוא)\s+"?([^".\n]{2,40})"?', text)
        for term, definition in defined:
            if term not in self.terms_he:
                self.add_term(term, "", source=source, definition=definition,
                              register=register)

    def get_stats(self) -> dict:
        return {
            "terms_he": len(self.terms_he),
            "terms_en": len(self.terms_en),
            "abbreviations": len(self.abbreviations),
            "collocations": len(self.collocations),
            "keywords": len(self.keywords_to_tags),
        }


# ═════════════════════════════════════════════════════════════════════════════
# 2. HEBREW SPELL & GRAMMAR CHECKER
# ═════════════════════════════════════════════════════════════════════════════

class HebrewLanguageChecker:
    """
    Spell and grammar checking for Hebrew customs text.
    
    Approach: Hybrid (Option C from mission doc)
    - Rule-based for known patterns (typos, HS codes, abbreviations, numbers)
    - LLM fallback for edge cases (called via TextPolisher when needed)
    """

    def __init__(self, vocabulary: CustomsVocabulary = None):
        self.vocabulary = vocabulary or CustomsVocabulary()

    def check_spelling(self, text: str) -> list:
        """Check for known spelling errors in customs Hebrew."""
        issues = []
        for typo, correction in KNOWN_TYPOS.items():
            if typo != correction and typo in text:
                pos = text.find(typo)
                issues.append(SpellingIssue(
                    original=typo,
                    suggestion=correction,
                    position=pos,
                    confidence=0.95,
                    source="typo_dict",
                ))
        return issues

    def check_grammar(self, text: str) -> list:
        """Check for common Hebrew grammar issues."""
        issues = []

        # ── Gender agreement: נדרש/נדרשת with common nouns ──
        # "הצהרה" is feminine → should be "נדרשת" not "נדרש"
        feminine_nouns = ["הצהרה", "חשבונית", "תעודה", "רשימה", "בקשה", "תוספת", "הודעה", "אסמכתא"]
        masculine_nouns = ["רשימון", "מסמך", "חשבון", "אישור", "היתר", "טופס", "דוח", "פריט"]
        
        for noun in feminine_nouns:
            pattern = rf'{noun}\s+(?:נדרש|חסר|מצורף|נשלח|הוגש)(?!ת)'
            match = re.search(pattern, text)
            if match:
                wrong = match.group(0)
                # Extract the adjective and add ת
                adj = wrong.split()[-1]
                issues.append(GrammarIssue(
                    text=wrong,
                    issue_type="gender_agreement",
                    suggestion=wrong + "ת",
                    explanation=f'"{noun}" נקבה — יש להשתמש בצורת נקבה: {adj}ת',
                ))

        for noun in masculine_nouns:
            pattern = rf'{noun}\s+(?:נדרשת|חסרה|מצורפת|נשלחה|הוגשה)'
            match = re.search(pattern, text)
            if match:
                wrong = match.group(0)
                adj = wrong.split()[-1]
                # Remove the ת/ה ending
                fixed_adj = re.sub(r'[תה]$', '', adj)
                issues.append(GrammarIssue(
                    text=wrong,
                    issue_type="gender_agreement",
                    suggestion=f"{noun} {fixed_adj}",
                    explanation=f'"{noun}" זכר — יש להשתמש בצורת זכר',
                ))

        # ── RTL/LTR mixing: English terms should be wrapped properly ──
        # Detect bare English in Hebrew sentence without proper spacing
        mixed = re.findall(r'[\u0590-\u05FF][A-Za-z]|[A-Za-z][\u0590-\u05FF]', text)
        if mixed:
            issues.append(GrammarIssue(
                text=str(mixed[:3]),
                issue_type="rtl_mix",
                suggestion="הוסף רווח בין טקסט עברי לאנגלי",
                explanation="יש להפריד בין טקסט עברי לאנגלי ברווח",
            ))

        return issues

    def check_hs_code_format(self, code: str) -> bool:
        """
        Validate Israeli HS code format.
        
        Israel uses 10-digit codes: XX.XX.XXXXXX/X (e.g., 87.08.998000/0)
        - First 6 digits: international HS (WCO standard)
        - Digits 7-10: Israeli national subdivision
        - Display format has dots and slash: XX.XX.XXXXXX/X
        
        Note: For actual formatting, prefer importing get_israeli_hs_format()
        from librarian.py rather than reimplementing here.
        
        Accepted formats:
        - 87.08.998000/0  (Israeli display format — XX.XX.XXXXXX/X)
        - 8708998000       (flat 10-digit — for data systems)
        - 8708.99.80       (legacy 8-digit — will be zero-padded to 10)
        - 8471.30          (6-digit international HS — valid but incomplete)
        """
        code = code.strip()
        patterns = [
            r'^\d{2}\.\d{2}\.\d{6}/\d$',   # 87.08.998000/0 — Israeli 10-digit display
            r'^\d{10}$',                      # 8708998000   — flat 10-digit
            r'^\d{4}\.\d{2}\.\d{2}$',        # 8708.99.80   — legacy 8-digit (acceptable)
            r'^\d{8}$',                       # 87089980     — flat 8-digit (will pad to 10)
            r'^\d{4}\.\d{2}$',               # 8471.30      — 6-digit international (incomplete)
        ]
        return any(re.match(p, code) for p in patterns)

    def check_legal_references(self, text: str) -> list:
        """Validate legal reference format: סעיף 53 לפקודת המכס."""
        issues = []
        # Pattern: סעיף + number should be followed by ל + law name
        refs = re.findall(r'סעיף\s+(\d+[א-ת]?)', text)
        for ref in refs:
            # Check if the reference has the law name after it
            pattern = rf'סעיף\s+{re.escape(ref)}\s+(?:ל|של|ב)'
            if not re.search(pattern, text):
                issues.append(GrammarIssue(
                    text=f"סעיף {ref}",
                    issue_type="legal_reference",
                    suggestion=f'סעיף {ref} — נא לציין את שם החוק (לדוגמה: "סעיף {ref} לפקודת המכס")',
                    explanation="הפניות חוקיות צריכות לכלול את שם החוק",
                ))
        return issues

    def check_number_formatting(self, text: str) -> list:
        """Check Hebrew number conventions (thousands separator, currency)."""
        issues = []
        # Large numbers without separator: 1000000 → 1,000,000
        bare_numbers = re.findall(r'\b(\d{5,})\b', text)
        for num in bare_numbers:
            if ',' not in num and '.' not in num:
                formatted = f"{int(num):,}"
                issues.append(GrammarIssue(
                    text=num,
                    issue_type="number_format",
                    suggestion=formatted,
                    explanation="מספרים גדולים צריכים מפריד אלפים",
                ))
        return issues

    def check_vat_rate(self, text: str) -> list:
        """
        ⚠️ CRITICAL: Catch wrong VAT rate in any outgoing text.
        
        Israeli VAT is 18% since Jan 1, 2025 (was 17%).
        This check prevents the old 17% from leaking into outputs.
        """
        issues = []
        # Look for 17% near VAT-related words
        vat_context_patterns = [
            r'17\s*%\s*(?:מע"מ|מע״מ|VAT|vat|מס ערך)',
            r'(?:מע"מ|מע״מ|VAT|vat|מס ערך)\s*[:\-]?\s*17\s*%',
            r'(?:\+|plus|בתוספת)\s*17\s*%',
        ]
        for pattern in vat_context_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(GrammarIssue(
                    text="17%",
                    issue_type="wrong_vat_rate",
                    suggestion=f"שיעור מע\"מ נכון: {ISRAEL_VAT_RATE_DISPLAY} (עודכן ב-1.1.2025)",
                    explanation=f"מע\"מ בישראל הוא {ISRAEL_VAT_RATE_DISPLAY} מאז 1 בינואר 2025, לא 17%",
                ))
                break
        return issues

    def fix_vat_rate(self, text: str) -> str:
        """Auto-fix wrong VAT rate (17% → 18%) in context of VAT references."""
        # Only fix 17% when it's clearly about VAT, not other percentages
        text = re.sub(
            r'(מע"מ|מע״מ|VAT|מס ערך מוסף)(\s*[:\-]?\s*)17(\s*%)',
            rf'\g<1>\g<2>{ISRAEL_VAT_RATE_PERCENT}\3',
            text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'17(\s*%\s*)(מע"מ|מע״מ|VAT|מס ערך)',
            rf'{ISRAEL_VAT_RATE_PERCENT}\1\2',
            text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'(\+|plus|בתוספת)(\s*)17(\s*%)',
            rf'\1\g<2>{ISRAEL_VAT_RATE_PERCENT}\3',
            text, flags=re.IGNORECASE
        )
        return text

    def fix_all(self, text: str) -> str:
        """Auto-correct obvious issues. Returns cleaned text."""
        result = text

        # Fix known typos
        for typo, correction in KNOWN_TYPOS.items():
            if typo != correction:
                result = result.replace(typo, correction)

        # Fix wrong VAT rate (17% → 18% in VAT context)
        result = self.fix_vat_rate(result)

        # Fix RTL/LTR spacing: add space between Hebrew and English
        result = re.sub(r'([\u0590-\u05FF])([A-Za-z])', r'\1 \2', result)
        result = re.sub(r'([A-Za-z])([\u0590-\u05FF])', r'\1 \2', result)

        # Fix double spaces
        result = re.sub(r'  +', ' ', result)

        # Fix missing space after punctuation
        result = re.sub(r'([.!?])([^\s\d"\')\]])', r'\1 \2', result)

        return result.strip()

    def get_all_issues(self, text: str) -> dict:
        """Run all checks and return categorized results."""
        return {
            "spelling": self.check_spelling(text),
            "grammar": self.check_grammar(text),
            "legal_refs": self.check_legal_references(text),
            "numbers": self.check_number_formatting(text),
            "vat_rate": self.check_vat_rate(text),
            "auto_fixed": self.fix_all(text),
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. LETTER STRUCTURE ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class LetterStructure:
    """
    Manages visual letter structure for different output types.
    Produces clean, RTL-aware HTML for emails and reports.
    """

    def __init__(self,
                 letter_type: LetterType = LetterType.GENERIC,
                 language: str = "he"):
        self.letter_type = letter_type
        self.language = language
        self.letterhead = LetterHead(date=datetime.now().strftime("%d/%m/%Y"))
        self.greeting: str = ""
        self.reference_block: dict = {}
        self.body_sections: list = []    # [{"title": str, "content": str, "type": "text"|"table"|"list"}]
        self.attachments_block: list = []
        self.action_items: list = []
        self.closing: str = "בברכה," if language == "he" else "Best regards,"
        self.signature = SignatureBlock()
        self.footer: str = ""
        self.custom_css: str = ""

    def set_greeting(self, recipient_name: str = ""):
        if self.language == "he":
            self.greeting = f"שלום {recipient_name}," if recipient_name else "שלום רב,"
        else:
            self.greeting = f"Dear {recipient_name}," if recipient_name else "Dear Sir/Madam,"

    def set_reference(self, tracking: str = "", invoice: str = "",
                      supplier: str = "", extra: dict = None):
        self.reference_block = {
            k: v for k, v in {
                "אסמכתא" if self.language == "he" else "Reference": tracking,
                "חשבון" if self.language == "he" else "Invoice": invoice,
                "ספק" if self.language == "he" else "Supplier": supplier,
            }.items() if v
        }
        if extra:
            self.reference_block.update(extra)

    def add_section(self, title: str, content: str, section_type: str = "text"):
        """Add a body section. Types: text, table, list, highlight, warning."""
        self.body_sections.append({
            "title": title,
            "content": content,
            "type": section_type,
        })

    def add_attachment(self, filename: str, description: str = ""):
        self.attachments_block.append({
            "filename": filename,
            "description": description,
        })

    def add_action_item(self, action: str, deadline: str = ""):
        self.action_items.append({
            "action": action,
            "deadline": deadline,
        })

    def _base_css(self) -> str:
        direction = "rtl" if self.language == "he" else "ltr"
        font = "'Segoe UI', 'Arial', sans-serif"
        return f"""
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                direction: {direction};
                font-family: {font};
                font-size: 14px;
                line-height: 1.6;
                color: #1a1a2e;
                background: #f8f9fa;
            }}
            .letter-container {{
                max-width: 700px;
                margin: 20px auto;
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
            }}
            .letterhead {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #ffffff;
                padding: 20px 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .letterhead .company-name {{
                font-size: 20px;
                font-weight: 700;
            }}
            .letterhead .date {{
                font-size: 13px;
                opacity: 0.85;
            }}
            .reference-block {{
                background: #f0f4f8;
                padding: 12px 30px;
                border-bottom: 2px solid #e0e0e0;
                font-size: 13px;
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .reference-block .ref-item {{
                display: flex;
                gap: 6px;
            }}
            .reference-block .ref-label {{
                font-weight: 600;
                color: #555;
            }}
            .body {{
                padding: 25px 30px;
            }}
            .greeting {{
                font-size: 15px;
                margin-bottom: 18px;
                color: #333;
            }}
            .section {{
                margin-bottom: 18px;
            }}
            .section-title {{
                font-size: 14px;
                font-weight: 600;
                color: #1a1a2e;
                margin-bottom: 6px;
                padding-bottom: 4px;
                border-bottom: 1px solid #eee;
            }}
            .section-content {{
                color: #444;
                font-size: 14px;
            }}
            .section-highlight {{
                background: #fff3cd;
                border-right: 4px solid #ffc107;
                padding: 10px 15px;
                border-radius: 0 4px 4px 0;
                margin: 8px 0;
            }}
            .section-warning {{
                background: #f8d7da;
                border-right: 4px solid #dc3545;
                padding: 10px 15px;
                border-radius: 0 4px 4px 0;
                margin: 8px 0;
            }}
            .attachments {{
                background: #f8f9fa;
                padding: 12px 20px;
                border-radius: 4px;
                margin: 15px 0;
            }}
            .attachments-title {{
                font-weight: 600;
                margin-bottom: 6px;
                color: #555;
            }}
            .attachment-item {{
                padding: 3px 0;
                font-size: 13px;
            }}
            .action-items {{
                background: #e8f5e9;
                border-right: 4px solid #4caf50;
                padding: 12px 20px;
                border-radius: 0 4px 4px 0;
                margin: 15px 0;
            }}
            .action-title {{
                font-weight: 600;
                color: #2e7d32;
                margin-bottom: 6px;
            }}
            .action-item {{
                padding: 3px 0;
                font-size: 14px;
            }}
            .action-item::before {{
                content: "☐ ";
                color: #4caf50;
            }}
            .closing {{
                margin-top: 25px;
                color: #555;
            }}
            .signature {{
                margin-top: 5px;
                font-weight: 600;
                color: #1a1a2e;
            }}
            .signature-company {{
                font-size: 13px;
                color: #777;
            }}
            .footer {{
                background: #f8f9fa;
                padding: 10px 30px;
                font-size: 11px;
                color: #999;
                border-top: 1px solid #e0e0e0;
                text-align: center;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 8px 0;
                font-size: 13px;
            }}
            th {{
                background: #f0f4f8;
                padding: 8px 10px;
                text-align: right;
                font-weight: 600;
                border: 1px solid #ddd;
            }}
            td {{
                padding: 6px 10px;
                border: 1px solid #eee;
            }}
            tr:nth-child(even) td {{
                background: #fafafa;
            }}
            {self.custom_css}
        </style>
        """

    def render_html(self) -> str:
        """Render the full letter as clean HTML."""
        parts = []
        direction = "rtl" if self.language == "he" else "ltr"

        # Open
        parts.append(f'<!DOCTYPE html><html lang="{self.language}" dir="{direction}"><head>')
        parts.append('<meta charset="UTF-8">')
        parts.append(self._base_css())
        parts.append('</head><body><div class="letter-container">')

        # Letterhead
        company = self.letterhead.company_name_he if self.language == "he" else self.letterhead.company_name_en
        parts.append(f'''
        <div class="letterhead">
            <div class="company-name">{company}</div>
            <div class="date">{self.letterhead.date}</div>
        </div>
        ''')

        # Reference block
        if self.reference_block:
            refs_html = ""
            for label, value in self.reference_block.items():
                refs_html += f'<div class="ref-item"><span class="ref-label">{label}:</span> <span>{value}</span></div>'
            parts.append(f'<div class="reference-block">{refs_html}</div>')

        # Body
        parts.append('<div class="body">')

        # Greeting
        if self.greeting:
            parts.append(f'<div class="greeting">{self.greeting}</div>')

        # Sections
        for section in self.body_sections:
            css_class = "section"
            if section["type"] == "highlight":
                css_class = "section-highlight"
            elif section["type"] == "warning":
                css_class = "section-warning"

            title_html = f'<div class="section-title">{section["title"]}</div>' if section["title"] else ""
            parts.append(f'''
            <div class="{css_class}">
                {title_html}
                <div class="section-content">{section["content"]}</div>
            </div>
            ''')

        # Attachments
        if self.attachments_block:
            label = "מצורפים:" if self.language == "he" else "Attachments:"
            items_html = ""
            for i, att in enumerate(self.attachments_block, 1):
                desc = f' — {att["description"]}' if att["description"] else ""
                items_html += f'<div class="attachment-item">{i}. {att["filename"]}{desc}</div>'
            parts.append(f'''
            <div class="attachments">
                <div class="attachments-title">{label}</div>
                {items_html}
            </div>
            ''')

        # Action items
        if self.action_items:
            label = "פעולות נדרשות:" if self.language == "he" else "Action Required:"
            items_html = ""
            for item in self.action_items:
                deadline = f' (עד {item["deadline"]})' if item["deadline"] else ""
                items_html += f'<div class="action-item">{item["action"]}{deadline}</div>'
            parts.append(f'''
            <div class="action-items">
                <div class="action-title">{label}</div>
                {items_html}
            </div>
            ''')

        # Closing & signature
        parts.append(f'<div class="closing">{self.closing}</div>')
        parts.append(f'<div class="signature">{self.signature.name}</div>')
        if self.signature.company:
            parts.append(f'<div class="signature-company">{self.signature.company}</div>')

        parts.append('</div>')  # end body

        # Footer
        if self.footer:
            parts.append(f'<div class="footer">{self.footer}</div>')

        parts.append('</div></body></html>')
        return "\n".join(parts)

    def render_plain_text(self) -> str:
        """Render as plain text for non-HTML contexts."""
        lines = []
        company = self.letterhead.company_name_he if self.language == "he" else self.letterhead.company_name_en
        lines.append(f"{company}")
        lines.append(f"{self.letterhead.date}")
        lines.append("─" * 50)

        for label, value in self.reference_block.items():
            lines.append(f"{label}: {value}")
        if self.reference_block:
            lines.append("─" * 50)

        if self.greeting:
            lines.append(f"\n{self.greeting}\n")

        for section in self.body_sections:
            if section["title"]:
                lines.append(f"\n{section['title']}")
                lines.append("-" * len(section["title"]))
            # Strip HTML tags for plain text
            content = re.sub(r'<[^>]+>', '', section["content"])
            lines.append(content)

        if self.attachments_block:
            label = "מצורפים:" if self.language == "he" else "Attachments:"
            lines.append(f"\n{label}")
            for i, att in enumerate(self.attachments_block, 1):
                desc = f" — {att['description']}" if att["description"] else ""
                lines.append(f"  {i}. {att['filename']}{desc}")

        if self.action_items:
            label = "פעולות נדרשות:" if self.language == "he" else "Action Required:"
            lines.append(f"\n{label}")
            for item in self.action_items:
                deadline = f" (עד {item['deadline']})" if item["deadline"] else ""
                lines.append(f"  ☐ {item['action']}{deadline}")

        lines.append(f"\n{self.closing}")
        lines.append(self.signature.name)
        if self.signature.company:
            lines.append(self.signature.company)

        if self.footer:
            lines.append(f"\n{'─' * 50}")
            lines.append(self.footer)

        return "\n".join(lines)

    def validate_structure(self) -> list:
        """Check that the letter has all required components."""
        issues = []
        if not self.greeting:
            issues.append("Missing greeting / פתיחה חסרה")
        if not self.body_sections:
            issues.append("No body sections / אין תוכן גוף המכתב")
        if not self.closing:
            issues.append("Missing closing / סיום חסר")
        if self.letter_type == LetterType.CLARIFICATION_REQUEST and not self.action_items:
            issues.append("Clarification letter should have action items / מכתב הבהרה צריך לכלול פעולות נדרשות")
        if self.letter_type == LetterType.CLASSIFICATION_REPORT and not self.reference_block:
            issues.append("Classification report should have reference block / דוח סיווג צריך אסמכתאות")
        return issues


# ═════════════════════════════════════════════════════════════════════════════
# 4. SUBJECT LINE GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

class SubjectLineGenerator:
    """
    Generate professional, readable subject lines.
    
    Rules:
    - Always starts with tracking code in brackets
    - Hebrew for internal (@rpa-port.co.il), English for external
    - Status emoji prefix
    - Max 120 chars
    - Key info first (what + who), details after pipe
    """

    MAX_LENGTH = 120

    # Hebrew direction words
    DIRECTION_HE = {
        "import": "יבוא",
        "export": "יצוא",
        "transit": "מעבר",
    }

    # Hebrew transport words
    TRANSPORT_HE = {
        "sea": "ימי",
        "air": "אווירי",
        "land": "יבשתי",
    }

    def generate(self, context: dict) -> str:
        """
        Generate a subject line from context.
        
        Context keys: tracking_code, direction, seller, buyer, items_summary,
                      status, urgency, language, freight_terms, transport_mode,
                      item_count, hs_code, item_description
        """
        tracking = context.get("tracking_code", "")
        language = context.get("language", "he")
        status = context.get("status", "info")

        emoji = STATUS_EMOJI.get(status, "📋")
        bracket = f"[{tracking}]" if tracking else ""

        if language == "he":
            return self._generate_hebrew(bracket, emoji, context)
        else:
            return self._generate_english(bracket, emoji, context)

    def _generate_hebrew(self, bracket: str, emoji: str, ctx: dict) -> str:
        direction = self.DIRECTION_HE.get(ctx.get("direction", ""), "")
        transport = self.TRANSPORT_HE.get(ctx.get("transport_mode", ""), "")
        freight = ctx.get("freight_terms", "")
        seller = ctx.get("seller", "")
        buyer = ctx.get("buyer", "")
        item_desc = ctx.get("item_description", "")
        hs_code = ctx.get("hs_code", "")
        item_count = ctx.get("item_count", 0)

        # Build the main part: "סיווג יבוא | ACME Corp → RPA Port"
        main_parts = []

        # Action word based on letter type
        letter_type = ctx.get("letter_type", "classification")
        action_map = {
            "classification": "סיווג",
            "clarification": "בקשת הבהרה",
            "missing_docs": "השלמת מסמכים",
            "status_update": "עדכון סטטוס",
            "knowledge": "תשובה לשאילתה",
        }
        action = action_map.get(letter_type, "סיווג")

        if direction:
            main_parts.append(f"{action} {direction}")
        else:
            main_parts.append(action)

        # Parties
        if seller and buyer:
            main_parts.append(f"{seller} → {buyer}")
        elif seller:
            main_parts.append(seller)

        # Item info (brief)
        if hs_code and item_desc:
            main_parts.append(f"{hs_code} {item_desc}")
        elif item_count and item_count > 1:
            main_parts.append(f"{item_count} פריטים")

        # Transport + freight
        if transport and freight:
            main_parts.append(f"{freight} {transport}")

        subject = f"{bracket} {emoji} {' | '.join(main_parts)}"
        return self._truncate(subject)

    def _generate_english(self, bracket: str, emoji: str, ctx: dict) -> str:
        direction = ctx.get("direction", "").upper()
        seller = ctx.get("seller", "")
        item_count = ctx.get("item_count", 0)
        transport = ctx.get("transport_mode", "").upper()
        freight = ctx.get("freight_terms", "").upper()

        letter_type = ctx.get("letter_type", "classification")
        action_map = {
            "classification": "Classification Report",
            "clarification": "Clarification Required",
            "missing_docs": "Documents Required",
            "status_update": "Status Update",
            "knowledge": "Query Response",
        }
        action = action_map.get(letter_type, "Classification Report")

        main_parts = [action]
        if seller:
            main_parts.append(seller)
        if item_count and item_count > 1:
            main_parts.append(f"{item_count} items")
        if transport and freight:
            main_parts.append(f"{transport}-{freight}")

        subject = f"{bracket} {emoji} {' | '.join(main_parts)}"
        return self._truncate(subject)

    def _truncate(self, subject: str) -> str:
        if len(subject) <= self.MAX_LENGTH:
            return subject
        return subject[:self.MAX_LENGTH - 1] + "…"

    def generate_reply_subject(self, original_subject: str, context: dict) -> str:
        """Generate Re: subject maintaining tracking code."""
        if original_subject.startswith("Re:"):
            return original_subject
        return f"Re: {original_subject}"

    def generate_clarification_subject(self, context: dict) -> str:
        context["letter_type"] = "clarification"
        context["status"] = "needs_action"
        return self.generate(context)

    def generate_knowledge_subject(self, context: dict) -> str:
        context["letter_type"] = "knowledge"
        context["status"] = "info"
        return self.generate(context)


# ═════════════════════════════════════════════════════════════════════════════
# 5. STYLE ANALYZER  (NEW — per user request)
# ═════════════════════════════════════════════════════════════════════════════

class StyleAnalyzer:
    """
    Learn language registers from real communication.
    
    Compares official customs documents with actual emails to understand:
    - What is "high" / formal language (official docs, regulations)
    - What is "day-to-day" language (real emails, chat)
    - How to match the appropriate register for each recipient
    
    Also learns individual contact style preferences:
    - Does this person write formally or casually?
    - Do they use abbreviations?
    - Do they prefer Hebrew or English terms?
    """

    def __init__(self):
        self.style_observations: list = []
        self.contact_profiles: dict = {}   # email → {style traits}
        self.register_examples: dict = {   # register → [example phrases]
            LanguageRegister.OFFICIAL.value: [],
            LanguageRegister.PROFESSIONAL.value: [],
            LanguageRegister.BUSINESS.value: [],
            LanguageRegister.CASUAL.value: [],
            LanguageRegister.COLLOQUIAL.value: [],
        }

    def analyze_text_register(self, text: str) -> LanguageRegister:
        """
        Detect the language register of a text sample.
        Uses heuristic markers to classify.
        """
        text_lower = text.lower()

        # ── Official markers: legal references, formal verb forms ──
        official_markers = [
            "בהתאם ל", "על פי", "מכוח", "לפי הוראות", "בכפוף ל",
            "הננו להודיע", "ניתנת בזה", "דין וחשבון", "פקודת המכס",
            "תקנות", "חוזר מכס", "צו מכס", "נוהל מכס",
        ]
        official_score = sum(1 for m in official_markers if m in text)

        # ── Casual markers: slang, short forms ──
        casual_markers = [
            "סבבה", "יאללה", "אחלה", "תודה", "היי", "שלום!",
            "בקיצור", "מה קורה", "תגיד", "תראה", "נו",
            "בסדר", "אין בעיה", "בכיף", "תכלס",
            "👍", "🙏", "😊",
        ]
        casual_score = sum(1 for m in casual_markers if m in text)

        # ── Professional markers ──
        professional_markers = [
            "בברכה", "שלום רב", "לכבוד", "הריני",
            "נא ", "נודה ", "נבקש ", "מצ\"ב",
            "בהמשך ל", "כפי שסוכם", "בהתאם לשיחתנו",
        ]
        professional_score = sum(1 for m in professional_markers if m in text)

        # ── Colloquial markers ──
        colloquial_markers = [
            "חחח", "לול", "btw", "fyi", "tbh",
            "...", "????", "!!!!",
        ]
        colloquial_score = sum(1 for m in colloquial_markers if m in text_lower)

        scores = {
            LanguageRegister.OFFICIAL: official_score * 3,
            LanguageRegister.PROFESSIONAL: professional_score * 2,
            LanguageRegister.CASUAL: casual_score * 2,
            LanguageRegister.COLLOQUIAL: colloquial_score * 3,
        }

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return LanguageRegister.BUSINESS  # default middle register
        return best

    def learn_from_email(self, email_address: str, text: str, 
                         direction: str = "incoming"):
        """
        Learn a contact's style from their actual emails.
        
        direction: "incoming" = they wrote to us, "outgoing" = we wrote to them
        """
        register = self.analyze_text_register(text)
        
        # Update contact profile
        if email_address not in self.contact_profiles:
            self.contact_profiles[email_address] = {
                "registers_seen": {},
                "preferred_language": "he",
                "uses_abbreviations": False,
                "formality_score": 0.5,  # 0=very casual, 1=very formal
                "message_count": 0,
                "last_seen": "",
            }

        profile = self.contact_profiles[email_address]
        profile["message_count"] += 1
        profile["last_seen"] = datetime.now(timezone.utc).isoformat()

        reg_key = register.value
        profile["registers_seen"][reg_key] = profile["registers_seen"].get(reg_key, 0) + 1

        # Detect language preference
        he_chars = len(re.findall(r'[\u0590-\u05FF]', text))
        en_chars = len(re.findall(r'[A-Za-z]', text))
        if en_chars > he_chars * 2:
            profile["preferred_language"] = "en"

        # Detect abbreviation usage
        abbr_count = sum(1 for abbr in CUSTOMS_ABBREVIATIONS if abbr in text)
        if abbr_count >= 2:
            profile["uses_abbreviations"] = True

        # Update formality score (rolling average)
        formality_map = {
            LanguageRegister.OFFICIAL: 1.0,
            LanguageRegister.PROFESSIONAL: 0.75,
            LanguageRegister.BUSINESS: 0.5,
            LanguageRegister.CASUAL: 0.25,
            LanguageRegister.COLLOQUIAL: 0.1,
        }
        new_formality = formality_map.get(register, 0.5)
        n = profile["message_count"]
        profile["formality_score"] = (
            (profile["formality_score"] * (n - 1) + new_formality) / n
        )

        # Store example phrases from this register
        sentences = re.split(r'[.!?\n]', text)
        for s in sentences[:5]:  # Take up to 5 sentences
            s = s.strip()
            if 5 < len(s) < 100:
                self.register_examples[reg_key].append(s)
                # Keep max 50 examples per register
                if len(self.register_examples[reg_key]) > 50:
                    self.register_examples[reg_key] = self.register_examples[reg_key][-50:]

    def learn_from_official_document(self, text: str, doc_type: str = "regulation"):
        """Learn formal register patterns from official customs documents."""
        self.register_examples[LanguageRegister.OFFICIAL.value].append(text[:200])
        
        # Extract formal phrases
        formal_phrases = re.findall(
            r'(?:בהתאם ל|על פי|מכוח|לפי|בכפוו ל)[^.]{5,60}', text
        )
        for phrase in formal_phrases:
            self.style_observations.append(StyleObservation(
                phrase=phrase.strip(),
                register=LanguageRegister.OFFICIAL,
                source_type="official_doc",
                context=doc_type,
            ))

    def get_recommended_register(self, email_address: str) -> LanguageRegister:
        """What register should we use when writing to this contact?"""
        profile = self.contact_profiles.get(email_address)
        if not profile:
            return LanguageRegister.PROFESSIONAL  # safe default

        score = profile["formality_score"]
        if score >= 0.8:
            return LanguageRegister.OFFICIAL
        elif score >= 0.6:
            return LanguageRegister.PROFESSIONAL
        elif score >= 0.4:
            return LanguageRegister.BUSINESS
        else:
            return LanguageRegister.CASUAL

    def adapt_text_to_contact(self, text: str, email_address: str) -> str:
        """
        Adjust text register to match what we've learned about a contact's style.
        """
        recommended = self.get_recommended_register(email_address)
        current = self.analyze_text_register(text)

        if recommended == current:
            return text

        # Upgrade casual → professional
        if (recommended in (LanguageRegister.PROFESSIONAL, LanguageRegister.OFFICIAL)
                and current in (LanguageRegister.CASUAL, LanguageRegister.COLLOQUIAL)):
            for informal, formal in FORMAL_INFORMAL_MAP.items():
                text = text.replace(informal, formal)

        # Downgrade formal → casual (for internal / casual contacts)
        elif (recommended in (LanguageRegister.CASUAL, LanguageRegister.COLLOQUIAL)
              and current in (LanguageRegister.OFFICIAL, LanguageRegister.PROFESSIONAL)):
            for informal, formal in FORMAL_INFORMAL_MAP.items():
                text = text.replace(formal, informal)

        return text

    def get_contact_summary(self, email_address: str) -> Optional[dict]:
        """Get what we've learned about a contact's communication style."""
        return self.contact_profiles.get(email_address)

    def to_dict(self) -> dict:
        """Serialize for Firestore storage."""
        return {
            "contact_profiles": self.contact_profiles,
            "register_examples": {
                k: v[-20:] for k, v in self.register_examples.items()
            },
            "observations_count": len(self.style_observations),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StyleAnalyzer":
        """Restore from Firestore."""
        analyzer = cls()
        analyzer.contact_profiles = data.get("contact_profiles", {})
        analyzer.register_examples = data.get("register_examples", analyzer.register_examples)
        return analyzer


# ═════════════════════════════════════════════════════════════════════════════
# 6. LLM-POWERED TEXT POLISHER
# ═════════════════════════════════════════════════════════════════════════════

class TextPolisher:
    """
    Use LLM to polish generated text before sending.
    
    Design decisions:
    - Only invoked for high-value outputs (letters, reports) — not every subject line
    - Can extend existing Claude API calls instead of separate calls where possible
    - Includes vocabulary context so the LLM uses correct customs terminology
    """

    def __init__(self, vocabulary: CustomsVocabulary = None,
                 style_analyzer: StyleAnalyzer = None):
        self.vocabulary = vocabulary or CustomsVocabulary()
        self.style_analyzer = style_analyzer or StyleAnalyzer()

    def build_polish_prompt(self, text: str, language: str = "he",
                            tone: str = "professional",
                            recipient_email: str = "") -> str:
        """
        Build a system prompt addition for polishing text.
        
        This prompt can be appended to an existing Claude API call
        to avoid a separate round-trip.
        """
        vocab_sample = list(self.vocabulary.abbreviations.items())[:15]
        vocab_str = "\n".join(f"  {k} = {v}" for k, v in vocab_sample)

        register_hint = ""
        if recipient_email and self.style_analyzer:
            recommended = self.style_analyzer.get_recommended_register(recipient_email)
            register_hint = f"\nTarget register: {recommended.value}"
            profile = self.style_analyzer.get_contact_summary(recipient_email)
            if profile:
                register_hint += f"\nContact formality: {profile['formality_score']:.2f}"
                register_hint += f"\nContact language: {profile['preferred_language']}"

        if language == "he":
            return f"""
--- TEXT POLISH INSTRUCTIONS ---
Polish the following Hebrew text for a professional customs brokerage context.
Target tone: {tone}
{register_hint}

Rules:
1. Fix any spelling or grammar errors
2. Use correct gender agreement (נדרש/נדרשת based on noun gender)
3. Use proper customs terminology from this vocabulary:
{vocab_str}
4. Maintain RTL formatting — keep English terms (HS codes, company names, trade terms) intact
5. Ensure natural sentence flow — not mechanical/concatenated
6. Keep it concise and professional
7. Do NOT translate technical English terms (CIF, FOB, EUR.1, HS codes)

⚠️ CRITICAL VERIFIED FACTS — do NOT deviate:
- Israeli VAT rate is {ISRAEL_VAT_RATE_DISPLAY} (since 1 Jan 2025, NOT 17%)
- Israeli HS codes are {ISRAEL_HS_CODE_DIGITS} digits: {ISRAEL_HS_CODE_FORMAT} (e.g., {ISRAEL_HS_CODE_EXAMPLE})
- De minimis threshold for personal imports: ${ISRAEL_DE_MINIMIS_USD} {ISRAEL_DE_MINIMIS_CURRENCY}

Text to polish:
{text}
--- END POLISH INSTRUCTIONS ---
"""
        else:
            return f"""
--- TEXT POLISH INSTRUCTIONS ---
Polish the following English text for a professional customs brokerage context.
Target tone: {tone}
{register_hint}

Rules:
1. Fix grammar and spelling
2. Use standard international trade terminology
3. Keep it clear and actionable
4. Professional but not overly formal

Text to polish:
{text}
--- END POLISH INSTRUCTIONS ---
"""

    def polish_hebrew(self, text: str, context: dict = None,
                      tone: str = "professional") -> str:
        """
        Polish Hebrew text. For use when LLM call is available.
        
        Returns the prompt to include in an LLM call.
        In production, the calling code should:
        1. Add this prompt to the Claude API call
        2. Parse the polished text from the response
        
        For standalone use without LLM, falls back to rule-based fixes.
        """
        # Always apply rule-based fixes first
        checker = HebrewLanguageChecker(self.vocabulary)
        text = checker.fix_all(text)
        return text

    def polish_english(self, text: str, context: dict = None,
                       tone: str = "professional") -> str:
        """Polish English text — rule-based baseline."""
        # Basic fixes
        text = re.sub(r'  +', ' ', text)
        text = re.sub(r'([.!?])([^\s\d"\')\]])', r'\1 \2', text)
        return text.strip()

    def adapt_tone(self, text: str, recipient_type: str = "professional",
                   recipient_email: str = "") -> str:
        """Adjust text tone based on recipient type or learned preferences."""
        if recipient_email and self.style_analyzer:
            return self.style_analyzer.adapt_text_to_contact(text, recipient_email)

        if recipient_type == "internal":
            # More casual
            for informal, formal in FORMAL_INFORMAL_MAP.items():
                text = text.replace(formal, informal)
        elif recipient_type in ("customs_broker", "official"):
            # More formal
            for informal, formal in FORMAL_INFORMAL_MAP.items():
                text = text.replace(informal, formal)
        return text

    def summarize_for_email(self, long_text: str, max_sentences: int = 5) -> str:
        """Condense text into email-appropriate length (rule-based)."""
        sentences = re.split(r'(?<=[.!?])\s+', long_text)
        if len(sentences) <= max_sentences:
            return long_text
        # Take first and last sentences plus key ones from the middle
        if max_sentences >= 3:
            result = sentences[:2] + sentences[-(max_sentences - 2):]
        else:
            result = sentences[:max_sentences]
        return " ".join(result)


# ═════════════════════════════════════════════════════════════════════════════
# 7. LANGUAGE LEARNER (with communication-based learning)
# ═════════════════════════════════════════════════════════════════════════════

class LanguageLearner:
    """
    Learn from corrections, new documents, and actual communication.
    
    Three learning channels:
    1. Corrections — when team manually edits RCB's output
    2. Documents — new terms from tagged documents
    3. Communication — style & vocabulary from real emails
    
    Learns:
    - Spelling corrections specific to this organization
    - Style preferences per contact
    - New domain terms from documents
    - Register patterns (formal docs vs. day-to-day email)
    """

    def __init__(self, vocabulary: CustomsVocabulary = None,
                 style_analyzer: StyleAnalyzer = None):
        self.vocabulary = vocabulary or CustomsVocabulary()
        self.style_analyzer = style_analyzer or StyleAnalyzer()
        self.corrections: list = []
        self.learned_spelling: dict = {}  # original → corrected (from real usage)

    def learn_from_correction(self, original: str, corrected: str,
                              context: str = "", correction_type: str = "spelling"):
        """
        When team manually edits RCB's output, learn the pattern.
        
        This is the most valuable learning signal — real humans fixing real output.
        """
        correction = {
            "original": original,
            "corrected": corrected,
            "type": correction_type,
            "context": context,
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "applied_count": 0,
        }
        self.corrections.append(correction)

        # If it's a spelling correction, add to the typo dictionary
        if correction_type == "spelling":
            # Find the words that changed
            orig_words = set(original.split())
            corr_words = set(corrected.split())
            for ow in orig_words - corr_words:
                for cw in corr_words - orig_words:
                    if _similar_words(ow, cw):
                        self.learned_spelling[ow] = cw
                        logger.info(f"Learned spelling: {ow} → {cw}")

    def learn_from_email_exchange(self, email_address: str, text: str,
                                   direction: str = "incoming"):
        """
        Learn from actual email communication.
        
        - Incoming: learn the contact's style
        - Outgoing: learn what register we used with them
        - Both: extract new vocabulary terms
        """
        # Learn style
        self.style_analyzer.learn_from_email(email_address, text, direction)

        # Extract potential new terms
        self.vocabulary.enrich_from_text(
            text,
            source=f"email_{direction}",
            register=self.style_analyzer.analyze_text_register(text).value,
        )

        # Learn spelling patterns from incoming (they may correct our terms)
        if direction == "incoming":
            # If they consistently use a term differently than our dictionary,
            # note it (but don't auto-correct — flag for review)
            for typo, correction in KNOWN_TYPOS.items():
                if typo in text:
                    # Someone out there uses the "typo" form — log it
                    logger.debug(f"Contact {email_address} uses '{typo}' (our dict says '{correction}')")

    def learn_from_document(self, doc_text: str, doc_tags: list = None):
        """Extract new vocabulary from newly tagged documents."""
        self.vocabulary.enrich_from_text(doc_text, source="tagged_document",
                                         register="professional")

    def learn_from_handbook(self, chapter_text: str):
        """Extract formal terms and phrases from handbook chapters."""
        self.vocabulary.enrich_from_text(chapter_text, source="handbook",
                                         register="official")
        self.style_analyzer.learn_from_official_document(chapter_text, "handbook")

    def apply_learned_spelling(self, text: str) -> str:
        """Apply spelling corrections learned from actual team edits."""
        for original, corrected in self.learned_spelling.items():
            text = text.replace(original, corrected)
        return text

    def get_improvement_report(self) -> dict:
        """Stats: corrections made, new terms learned, common errors."""
        return {
            "total_corrections": len(self.corrections),
            "learned_spelling_rules": len(self.learned_spelling),
            "vocabulary_stats": self.vocabulary.get_stats(),
            "contacts_profiled": len(self.style_analyzer.contact_profiles),
            "register_examples": {
                k: len(v) for k, v in self.style_analyzer.register_examples.items()
            },
            "correction_types": _count_by_key(self.corrections, "type"),
        }

    def to_dict(self) -> dict:
        """Serialize for Firestore."""
        return {
            "corrections": self.corrections[-100:],  # Keep last 100
            "learned_spelling": self.learned_spelling,
            "style_analyzer": self.style_analyzer.to_dict(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict, vocabulary: CustomsVocabulary = None) -> "LanguageLearner":
        """Restore from Firestore."""
        style = StyleAnalyzer.from_dict(data.get("style_analyzer", {}))
        learner = cls(vocabulary=vocabulary, style_analyzer=style)
        learner.corrections = data.get("corrections", [])
        learner.learned_spelling = data.get("learned_spelling", {})
        return learner


# ═════════════════════════════════════════════════════════════════════════════
# 8. JOKE BANK  (non-offensive, non-political, gender/race neutral)
# ═════════════════════════════════════════════════════════════════════════════

class JokeBank:
    """
    Curated collection of clean, non-offensive humor.
    
    Rules:
    - No gender-specific jokes
    - No race/ethnicity jokes
    - No political jokes
    - No religious jokes
    - Work-safe, family-friendly
    - Mix of Hebrew and English
    - Customs/shipping/office themed where possible
    
    Usage: Add a joke to status updates, Friday emails, or long wait notifications
    to add personality to RCB's communication.
    """

    def __init__(self):
        self.jokes_he = [
            # ─── Customs & shipping themed (Hebrew) ───
            {
                "text": "למה המכולה לא אהבה את בית המכס? כי תמיד עיכבו אותה.",
                "category": "customs",
            },
            {
                "text": "מה אמר הרשימון לחשבונית? בלעדייך אני חסר ערך.",
                "category": "customs",
            },
            {
                "text": "למה סוכן המכס תמיד שמח? כי הוא יודע לשחרר.",
                "category": "customs",
            },
            {
                "text": "מה ההבדל בין FOB ל-CIF? בערך כמו ההבדל בין 'אני אביא' ל'אני אביא ואשלם על הדרך'.",
                "category": "trade_terms",
            },
            {
                "text": "למה קוד HS תמיד מבולבל? כי יש לו יותר מדי ספרות.",
                "category": "customs",
            },
            # ─── Office / work humor (Hebrew) ───
            {
                "text": "מה הדבר הראשון שעושים בבוקר במשרד? בודקים אם הקפה עדיין קיים.",
                "category": "office",
            },
            {
                "text": "למה המחשב הלך לרופא? כי היה לו וירוס.",
                "category": "tech",
            },
            {
                "text": "מה אמר האקסל לוורד? אתה תמיד עם מילים, אני עם מספרים, ביחד אנחנו מצגת.",
                "category": "office",
            },
            {
                "text": "כמה אנשי IT צריך כדי להחליף נורה? אף אחד, זו בעיית חומרה.",
                "category": "tech",
            },
            {
                "text": "מה אמר הלוח שנה? 'הימים שלי ספורים'.",
                "category": "general",
            },
            # ─── General clean humor (Hebrew) ───
            {
                "text": "למה העיפרון כתב מכתב? כי רצה להביע את עצמו.",
                "category": "general",
            },
            {
                "text": "מה אמר הים לחוף? שום דבר, הוא רק נפנף.",
                "category": "general",
            },
        ]

        self.jokes_en = [
            # ─── Customs & shipping themed (English) ───
            {
                "text": "Why did the container go to therapy? Too many attachment issues.",
                "category": "customs",
            },
            {
                "text": "What's a customs broker's favorite game? Duty free!",
                "category": "customs",
            },
            {
                "text": "Why was the HS code feeling lost? It couldn't find its classification.",
                "category": "customs",
            },
            {
                "text": "What did CIF say to FOB? 'I've got you covered — insurance and all.'",
                "category": "trade_terms",
            },
            {
                "text": "Why don't containers ever get lonely? They always travel in groups.",
                "category": "shipping",
            },
            # ─── Office / general clean humor (English) ───
            {
                "text": "Why did the spreadsheet break up with the calculator? It felt they were just going in circles.",
                "category": "office",
            },
            {
                "text": "What's the best thing about teamwork? Someone else can take the blame.",
                "category": "office",
            },
            {
                "text": "Why do programmers prefer dark mode? Because light attracts bugs.",
                "category": "tech",
            },
            {
                "text": "I told my computer I needed a break. It said: 'I've got Windows.'",
                "category": "tech",
            },
            {
                "text": "What did the ocean say to the shore? Nothing, it just waved.",
                "category": "general",
            },
        ]

        self.used_recently: list = []

    def get_joke(self, language: str = "he", category: str = None) -> Optional[dict]:
        """
        Get a random joke, avoiding recent repeats.
        
        Args:
            language: "he" or "en"
            category: optional filter — "customs", "office", "tech", "general", "trade_terms"
        """
        jokes = self.jokes_he if language == "he" else self.jokes_en

        if category:
            jokes = [j for j in jokes if j["category"] == category]

        # Avoid recent jokes
        available = [j for j in jokes if j["text"] not in self.used_recently]
        if not available:
            self.used_recently.clear()
            available = jokes

        if not available:
            return None

        joke = random.choice(available)
        self.used_recently.append(joke["text"])
        # Keep recent list manageable
        if len(self.used_recently) > len(jokes) // 2:
            self.used_recently = self.used_recently[-3:]

        return joke

    def get_customs_joke(self, language: str = "he") -> Optional[str]:
        """Convenience: get a customs-themed joke text."""
        joke = self.get_joke(language, category="customs")
        if not joke:
            joke = self.get_joke(language, category="trade_terms")
        return joke["text"] if joke else None

    def get_friday_joke(self, language: str = "he") -> Optional[str]:
        """Get a joke suitable for Friday/end-of-week email."""
        joke = self.get_joke(language)
        if joke and language == "he":
            return f"🎉 בדיחת סוף שבוע: {joke['text']}"
        elif joke:
            return f"🎉 Weekend joke: {joke['text']}"
        return None

    def add_joke(self, text: str, language: str = "he",
                 category: str = "general"):
        """Add a new joke (after manual review for appropriateness)."""
        joke = {"text": text, "category": category}
        if language == "he":
            self.jokes_he.append(joke)
        else:
            self.jokes_en.append(joke)


# ═════════════════════════════════════════════════════════════════════════════
# VOCABULARY BOOTSTRAP
# ═════════════════════════════════════════════════════════════════════════════

def bootstrap_vocabulary(document_tags: dict = None,
                         handbook_chapters: dict = None,
                         tag_keywords: dict = None) -> CustomsVocabulary:
    """
    Build initial vocabulary from existing system data.
    
    Called on first run with data from:
    - librarian_tags.DOCUMENT_TAGS
    - librarian_tags.CUSTOMS_HANDBOOK_CHAPTERS
    - librarian_tags.TAG_KEYWORDS
    """
    vocab = CustomsVocabulary()

    # 1. From DOCUMENT_TAGS (226 terms)
    if document_tags:
        for tag_key, tag_he in document_tags.items():
            if isinstance(tag_he, str):
                vocab.add_term(tag_he, tag_key, source="document_tags")
            elif isinstance(tag_he, dict) and "name_he" in tag_he:
                vocab.add_term(tag_he["name_he"], tag_key, source="document_tags")

    # 2. From CUSTOMS_HANDBOOK_CHAPTERS (86 chapter names)
    if handbook_chapters:
        for ch_num, ch_info in handbook_chapters.items():
            if isinstance(ch_info, dict):
                name = ch_info.get("name_he", ch_info.get("name", ""))
                tag = ch_info.get("tag", str(ch_num))
                if name:
                    vocab.add_term(name, tag, source="handbook",
                                   register="official")
                for sub_k, sub_v in ch_info.get("sub_chapters", {}).items():
                    if isinstance(sub_v, dict):
                        sub_name = sub_v.get("name_he", sub_v.get("name", ""))
                        sub_tag = sub_v.get("tag", str(sub_k))
                        if sub_name:
                            vocab.add_term(sub_name, sub_tag,
                                           source="handbook_sub",
                                           register="official")

    # 3. From TAG_KEYWORDS (160 keyword lists)
    if tag_keywords:
        for tag, keywords in tag_keywords.items():
            if isinstance(keywords, (list, tuple)):
                for kw in keywords:
                    vocab.add_keyword(kw, tag, source="tag_keywords")

    # 4. Known collocations in customs domain
    customs_collocations = {
        "יבוא אישי": "סחורה המיובאת לשימוש אישי ולא למטרות מסחריות",
        "יבוא מסחרי": "סחורה המיובאת למטרות מסחריות",
        "אישור יבוא": "היתר מרשות מוסמכת לייבא סחורה מסוימת",
        "שחרור ממכס": "תהליך הוצאת סחורה ממחסן ערובה לאחר תשלום מיסים",
        "תעריף מכס": "שיעור המס המוטל על סחורה מיובאת",
        "ארץ מקור": "המדינה בה יוצרה הסחורה",
        "הסכם סחר חופשי": "הסכם בין-לאומי להפחתת מכסים",
        "ערך עסקה": "המחיר ששולם עבור הסחורה בעסקה",
        "פקודת מסירה": "הוראה לשחרור סחורה ממחסן",
        "עסקת אב": "העסקה הראשית הכוללת",
        "עסקת בן": "עסקה משנית הנגזרת מעסקת האב",
        "מצהר יבוא": "הצהרה על סחורה המיובאת לארץ",
    }
    for phrase, meaning in customs_collocations.items():
        vocab.add_collocation(phrase, meaning, register="professional")

    vocab._initialized = True
    logger.info(f"Vocabulary bootstrapped: {vocab.get_stats()}")
    return vocab


# ═════════════════════════════════════════════════════════════════════════════
# INITIALIZATION — create default instances
# ═════════════════════════════════════════════════════════════════════════════

def create_language_toolkit(document_tags: dict = None,
                            handbook_chapters: dict = None,
                            tag_keywords: dict = None) -> dict:
    """
    Create all language tool instances, wired together.
    
    Returns dict with all tools ready to use:
    {
        "vocabulary": CustomsVocabulary,
        "checker": HebrewLanguageChecker,
        "subject_gen": SubjectLineGenerator,
        "polisher": TextPolisher,
        "style_analyzer": StyleAnalyzer,
        "learner": LanguageLearner,
        "joke_bank": JokeBank,
    }
    """
    vocab = bootstrap_vocabulary(document_tags, handbook_chapters, tag_keywords)
    style_analyzer = StyleAnalyzer()
    checker = HebrewLanguageChecker(vocabulary=vocab)
    polisher = TextPolisher(vocabulary=vocab, style_analyzer=style_analyzer)
    learner = LanguageLearner(vocabulary=vocab, style_analyzer=style_analyzer)

    return {
        "vocabulary": vocab,
        "checker": checker,
        "letter": LetterStructure,  # Class, not instance — instantiate per letter
        "subject_gen": SubjectLineGenerator(),
        "polisher": polisher,
        "style_analyzer": style_analyzer,
        "learner": learner,
        "joke_bank": JokeBank(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _similar_words(w1: str, w2: str) -> bool:
    """Check if two words are similar enough to be a spelling correction."""
    if abs(len(w1) - len(w2)) > 3:
        return False
    # Simple: more than 50% of characters match
    common = sum(1 for a, b in zip(w1, w2) if a == b)
    return common / max(len(w1), len(w2)) > 0.5


def _count_by_key(items: list, key: str) -> dict:
    """Count occurrences of each value for a key in a list of dicts."""
    counts = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION HELPERS — for wiring into existing modules
# ═════════════════════════════════════════════════════════════════════════════

def generate_tracking_code() -> str:
    """
    Generate unique RCB tracking code: RCB-YYYYMMDD-XXXXX
    
    Matches classification_agents.generate_tracking_code() signature.
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"RCB-{date_part}-{random_part}"


def build_rcb_subject(invoice_data: dict, status: str = "ACK",
                      invoice_score: float = None) -> tuple:
    """
    Drop-in replacement for classification_agents.build_rcb_subject().
    
    CRITICAL: Returns (subject, tracking) TUPLE — not a single string.
    Matches actual signature: build_rcb_subject(invoice_data, status, invoice_score)
    
    Generates improved, readable subject lines while maintaining
    backward compatibility with the existing call pattern:
        subject_line, tracking_code = build_rcb_subject(invoice_data, status, score)
    """
    tracking = generate_tracking_code()
    
    gen = SubjectLineGenerator()
    
    # Map invoice_data fields to SubjectLineGenerator context
    direction = invoice_data.get("direction", "unknown")
    seller = invoice_data.get("seller", "")
    if seller:
        seller = seller.split(",")[0].strip()[:25]
    buyer = invoice_data.get("buyer", "")
    if buyer:
        buyer = buyer.split(",")[0].strip()[:25]
    
    # Determine status emoji/type
    if status == "CLARIFICATION" or (invoice_score is not None and invoice_score < 70):
        status_key = "needs_action"
        letter_type = "clarification"
    elif status == "FINAL" or (invoice_score is not None and invoice_score >= 70):
        status_key = "approved"
        letter_type = "classification"
    else:
        status_key = "info"
        letter_type = "classification"
    
    # Detect language: Hebrew for rpa-port domain, English otherwise
    language = "he"  # default
    
    freight_type = invoice_data.get("freight_type", "")
    transport_map = {"sea": "sea", "air": "air", "land": "land"}
    
    context = {
        "tracking_code": tracking,
        "direction": direction,
        "seller": seller,
        "buyer": buyer,
        "status": status_key,
        "letter_type": letter_type,
        "language": language,
        "transport_mode": transport_map.get(freight_type, ""),
        "freight_terms": invoice_data.get("incoterms", ""),
    }
    
    subject = gen.generate(context)
    return subject, tracking


def build_html_report(letter_type: str, context: dict,
                      sections: list, language: str = "he") -> str:
    """
    Build an HTML report using LetterStructure.
    
    Args:
        letter_type: one of LetterType values
        context: dict with tracking_code, invoice, supplier, recipient_name
        sections: list of {"title": str, "content": str, "type": str}
        language: "he" or "en"
    
    Returns: complete HTML string
    """
    lt = LetterType(letter_type) if isinstance(letter_type, str) else letter_type
    letter = LetterStructure(letter_type=lt, language=language)

    letter.set_greeting(context.get("recipient_name", ""))
    letter.set_reference(
        tracking=context.get("tracking_code", ""),
        invoice=context.get("invoice", ""),
        supplier=context.get("supplier", ""),
    )

    for section in sections:
        letter.add_section(
            title=section.get("title", ""),
            content=section.get("content", ""),
            section_type=section.get("type", "text"),
        )

    for att in context.get("attachments", []):
        letter.add_attachment(att.get("filename", ""), att.get("description", ""))

    for action in context.get("action_items", []):
        letter.add_action_item(action.get("action", ""), action.get("deadline", ""))

    # Validate
    issues = letter.validate_structure()
    if issues:
        logger.warning(f"Letter structure issues: {issues}")

    return letter.render_html()


def process_outgoing_text(text: str, toolkit: dict,
                          recipient_email: str = "",
                          language: str = "he") -> str:
    """
    Full pipeline: check, fix, adapt, polish outgoing text.
    
    This is the main entry point for all text before it leaves the system.
    """
    checker = toolkit["checker"]
    polisher = toolkit["polisher"]
    learner = toolkit["learner"]

    # 1. Apply learned spelling corrections
    text = learner.apply_learned_spelling(text)

    # 2. Rule-based fixes (typos, spacing, RTL)
    text = checker.fix_all(text)

    # 3. Adapt tone to recipient (if we know them)
    if recipient_email:
        text = polisher.adapt_tone(text, recipient_email=recipient_email)

    return text
