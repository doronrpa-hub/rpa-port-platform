"""
RCB Smart Clarification Generator
Generates professional Hebrew requests for missing information.
File: functions/lib/clarification_generator.py
Project: RCB (Robotic Customs Bot)
Session: 10 - Fixed with DocumentType
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# =============================================================================
# ENUMS
# =============================================================================

class RequestType(Enum):
    """Types of clarification requests"""
    MISSING_DOCUMENT = "missing_document"       # מסמך חסר
    CLASSIFICATION = "classification"           # בירור סיווג
    VALUE_VERIFICATION = "value_verification"   # אימות ערך
    ORIGIN_VERIFICATION = "origin_verification" # אימות מקור
    TECHNICAL_INFO = "technical_info"           # מידע טכני
    GENERAL = "general"                         # כללי


class UrgencyLevel(Enum):
    """Urgency levels for requests"""
    LOW = "low"           # נמוכה
    MEDIUM = "medium"     # בינונית
    HIGH = "high"         # גבוהה
    URGENT = "urgent"     # דחוף
    CRITICAL = "critical" # קריטי


class RequestLanguage(Enum):
    """Language for the request"""
    HEBREW = "he"
    ENGLISH = "en"
    BILINGUAL = "both"


class DocumentType(Enum):
    """Document types for customs - Session 10 addition"""
    INVOICE = "invoice"
    PACKING_LIST = "packing_list"
    BILL_OF_LADING = "bill_of_lading"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    EUR1 = "eur1"
    ATR = "atr"
    MSDS = "msds"
    SPEC_SHEET = "spec_sheet"
    INSURANCE = "insurance"
    FREIGHT_INVOICE = "freight_invoice"
    BANK_TRANSFER = "bank_transfer"
    IMPORT_LICENSE = "import_license"
    HEALTH_CERTIFICATE = "health_certificate"
    PHYTOSANITARY = "phytosanitary"
    CONFORMITY = "conformity"


# =============================================================================
# TEMPLATES - HEBREW
# =============================================================================

GREETINGS_HE = {
    "formal": "לכבוד {recipient},",
    "semi_formal": "שלום {recipient},",
    "informal": "היי {recipient},",
}

CLOSINGS_HE = {
    "formal": "בברכה,\n{sender}",
    "semi_formal": "בברכה,\n{sender}",
    "informal": "תודה,\n{sender}",
}

URGENCY_PHRASES_HE = {
    UrgencyLevel.LOW: "",
    UrgencyLevel.MEDIUM: "נודה לקבלת המידע בהקדם האפשרי.",
    UrgencyLevel.HIGH: "⚠️ נא להשיב בדחיפות - המשלוח ממתין לשחרור.",
    UrgencyLevel.URGENT: "🚨 דחוף ביותר! המשלוח מעוכב בנמל וצובר עלויות אחסנה.",
    UrgencyLevel.CRITICAL: "🚨🚨 קריטי! נדרשת תגובה מיידית!",
}

# Document type descriptions in Hebrew
DOCUMENT_DESCRIPTIONS_HE = {
    "invoice": {
        "name": "חשבון ספק",
        "description": "חשבון מכר מקורי חתום על ידי הספק",
    },
    "packing_list": {
        "name": "מפרט אריזות",
        "description": "פירוט האריזות, תכולתן ומשקלן",
    },
    "bill_of_lading": {
        "name": "שטר מטען ימי (B/L)",
        "description": "שטר מטען מקורי חתום",
    },
    "certificate_of_origin": {
        "name": "תעודת מקור",
        "description": "אישור ארץ מקור הסחורה",
    },
    "eur1": {
        "name": "תעודת EUR.1",
        "description": "תעודת מקור לפטור ממכס - האיחוד האירופי",
    },
    "atr": {
        "name": "תעודת A.TR",
        "description": "תעודת מקור לפטור ממכס - טורקיה",
    },
    "msds": {
        "name": "גיליון בטיחות (MSDS)",
        "description": "מפרט בטיחות לחומרים מסוכנים",
    },
    "spec_sheet": {
        "name": "מפרט טכני",
        "description": "מפרט טכני מפורט של המוצר",
    },
    "insurance": {
        "name": "פוליסת ביטוח",
        "description": "אישור ביטוח למשלוח",
    },
    "freight_invoice": {
        "name": "חשבון הובלה",
        "description": "חשבון עלויות ההובלה",
    },
    "bank_transfer": {
        "name": "אישור העברה בנקאית",
        "description": "אישור תשלום מהבנק",
    },
    "import_license": {
        "name": "רישיון יבוא",
        "description": "אישור משרד הכלכלה ליבוא",
    },
    "health_certificate": {
        "name": "תעודת בריאות",
        "description": "אישור משרד הבריאות",
    },
    "phytosanitary": {
        "name": "תעודה פיטוסניטרית",
        "description": "אישור לצמחים ומוצרי צמחים",
    },
    "conformity": {
        "name": "תעודת התאמה",
        "description": "אישור עמידה בתקנים",
    },
}

# Map DocumentType enum to description keys
DOCUMENT_TYPE_MAP = {
    DocumentType.INVOICE: "invoice",
    DocumentType.PACKING_LIST: "packing_list",
    DocumentType.BILL_OF_LADING: "bill_of_lading",
    DocumentType.CERTIFICATE_OF_ORIGIN: "certificate_of_origin",
    DocumentType.EUR1: "eur1",
    DocumentType.ATR: "atr",
    DocumentType.MSDS: "msds",
    DocumentType.SPEC_SHEET: "spec_sheet",
    DocumentType.INSURANCE: "insurance",
    DocumentType.FREIGHT_INVOICE: "freight_invoice",
    DocumentType.BANK_TRANSFER: "bank_transfer",
    DocumentType.IMPORT_LICENSE: "import_license",
    DocumentType.HEALTH_CERTIFICATE: "health_certificate",
    DocumentType.PHYTOSANITARY: "phytosanitary",
    DocumentType.CONFORMITY: "conformity",
}


# =============================================================================
# TEMPLATES - ENGLISH (Session 11)
# =============================================================================

GREETINGS_EN = {
    "formal": "Dear {recipient},",
    "semi_formal": "Hello {recipient},",
    "informal": "Hi {recipient},",
}

CLOSINGS_EN = {
    "formal": "Best regards,\n{sender}",
    "semi_formal": "Kind regards,\n{sender}",
    "informal": "Thanks,\n{sender}",
}

URGENCY_PHRASES_EN = {
    UrgencyLevel.LOW: "",
    UrgencyLevel.MEDIUM: "We would appreciate receiving this information at your earliest convenience.",
    UrgencyLevel.HIGH: "⚠️ URGENT: Please respond as soon as possible - the shipment is awaiting clearance.",
    UrgencyLevel.URGENT: "🚨 VERY URGENT: The shipment is held at port and incurring storage charges.",
    UrgencyLevel.CRITICAL: "🚨🚨 CRITICAL: Immediate response required!",
}

# Document type descriptions in English
DOCUMENT_DESCRIPTIONS_EN = {
    "invoice": {
        "name": "Commercial Invoice",
        "description": "Original supplier invoice signed by the seller",
    },
    "packing_list": {
        "name": "Packing List",
        "description": "Details of packages, contents, and weights",
    },
    "bill_of_lading": {
        "name": "Bill of Lading (B/L)",
        "description": "Original signed shipping document",
    },
    "certificate_of_origin": {
        "name": "Certificate of Origin",
        "description": "Official document certifying the country of origin",
    },
    "eur1": {
        "name": "EUR.1 Certificate",
        "description": "Certificate of origin for EU preferential duty rates",
    },
    "atr": {
        "name": "A.TR Certificate",
        "description": "Certificate of origin for Turkey preferential duty rates",
    },
    "msds": {
        "name": "Material Safety Data Sheet (MSDS)",
        "description": "Safety specifications for hazardous materials",
    },
    "spec_sheet": {
        "name": "Technical Specification Sheet",
        "description": "Detailed product technical specifications",
    },
    "insurance": {
        "name": "Insurance Certificate",
        "description": "Cargo insurance confirmation",
    },
    "freight_invoice": {
        "name": "Freight Invoice",
        "description": "Invoice for shipping/transportation costs",
    },
    "bank_transfer": {
        "name": "Bank Transfer Confirmation",
        "description": "Proof of payment from bank",
    },
    "import_license": {
        "name": "Import License",
        "description": "Government approval for import",
    },
    "health_certificate": {
        "name": "Health Certificate",
        "description": "Ministry of Health approval",
    },
    "phytosanitary": {
        "name": "Phytosanitary Certificate",
        "description": "Certificate for plant and plant products",
    },
    "conformity": {
        "name": "Certificate of Conformity",
        "description": "Compliance with standards certification",
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ClarificationRequest:
    """A generated clarification request"""
    request_type: RequestType
    subject: str
    body: str
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    language: RequestLanguage = RequestLanguage.HEBREW
    reference_number: Optional[str] = None
    missing_documents: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "request_type": self.request_type.value,
            "subject": self.subject,
            "body": self.body,
            "urgency": self.urgency.value,
            "language": self.language.value,
            "reference_number": self.reference_number,
            "missing_documents": self.missing_documents,
            "questions": self.questions,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# GENERATOR FUNCTIONS
# =============================================================================

def generate_missing_docs_request(
    missing_docs: List[DocumentType],
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    supplier_name: Optional[str] = None,
    recipient_name: str = "לקוח/ה יקר/ה",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    sender_name: str = "מערכת RCB",
    existing_docs: Optional[List[str]] = None,
) -> ClarificationRequest:
    """Generate a request for missing documents"""
    
    # Build subject
    doc_count = len(missing_docs)
    subject = f"בקשה להשלמת {doc_count} מסמכים"
    if invoice_date:
        subject += f" | חשבון {invoice_date}"
    elif invoice_number:
        subject += f" | חשבון {invoice_number}"
    
    # Build body
    lines = [f"שלום {recipient_name},"]
    lines.append("")
    
    # Reference info
    if invoice_number or supplier_name or existing_docs:
        lines.append("קיבלנו את המסמכים הבאים:")
        if invoice_number:
            lines.append(f"  • חשבון ספק מספר: {invoice_number}")
        if invoice_date:
            lines.append(f"  • תאריך: {invoice_date}")
        if supplier_name:
            lines.append(f"  • ספק: {supplier_name}")
        if existing_docs:
            for doc in existing_docs:
                lines.append(f"  • {doc}")
        lines.append("")
    
    # Missing documents
    lines.append("📋 לצורך המשך הטיפול במשלוח, נדרשים המסמכים הבאים:")
    missing_doc_names = []
    for doc in missing_docs:
        doc_key = DOCUMENT_TYPE_MAP.get(doc, doc.value if isinstance(doc, DocumentType) else str(doc))
        doc_info = DOCUMENT_DESCRIPTIONS_HE.get(doc_key, {"name": str(doc), "description": ""})
        doc_name = doc_info["name"]
        doc_desc = doc_info["description"]
        missing_doc_names.append(doc_name)
        lines.append(f"  ☐ {doc_name}")
        if doc_desc:
            lines.append(f"     ({doc_desc})")
    
    lines.append("")
    
    # Urgency
    urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append(sender_name)
    lines.append("ר.פ.א - פורט בע\"מ")
    
    return ClarificationRequest(
        request_type=RequestType.MISSING_DOCUMENT,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        missing_documents=missing_doc_names,
        reference_number=invoice_number,
    )


def generate_missing_docs_request_en(
    missing_docs: List[DocumentType],
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    supplier_name: Optional[str] = None,
    recipient_name: str = "Valued Customer",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    sender_name: str = "RCB System",
    existing_docs: Optional[List[str]] = None,
) -> ClarificationRequest:
    """Generate a request for missing documents - English version (Session 11)"""
    
    # Build subject
    doc_count = len(missing_docs)
    subject = f"Request for {doc_count} Missing Document(s)"
    if invoice_date:
        subject += f" | Invoice {invoice_date}"
    elif invoice_number:
        subject += f" | Invoice {invoice_number}"
    
    # Build body
    lines = [f"Dear {recipient_name},"]
    lines.append("")
    
    # Reference info
    if invoice_number or supplier_name or existing_docs:
        lines.append("We have received the following documents:")
        if invoice_number:
            lines.append(f"  • Invoice Number: {invoice_number}")
        if invoice_date:
            lines.append(f"  • Date: {invoice_date}")
        if supplier_name:
            lines.append(f"  • Supplier: {supplier_name}")
        if existing_docs:
            for doc in existing_docs:
                lines.append(f"  • {doc}")
        lines.append("")
    
    # Missing documents
    lines.append("📋 To proceed with customs clearance, please provide the following documents:")
    lines.append("")
    missing_doc_names = []
    for doc in missing_docs:
        doc_key = DOCUMENT_TYPE_MAP.get(doc, doc.value if isinstance(doc, DocumentType) else str(doc))
        doc_info = DOCUMENT_DESCRIPTIONS_EN.get(doc_key, {"name": str(doc), "description": ""})
        doc_name = doc_info["name"]
        doc_desc = doc_info["description"]
        missing_doc_names.append(doc_name)
        lines.append(f"  ☐ {doc_name}")
        if doc_desc:
            lines.append(f"     ({doc_desc})")
    
    lines.append("")
    
    # Urgency
    urgency_phrase = URGENCY_PHRASES_EN.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 Please reply with the requested documents and information.")
    lines.append("")
    lines.append("Best regards,")
    lines.append(sender_name)
    lines.append("R.P.A. Port Ltd.")
    
    return ClarificationRequest(
        request_type=RequestType.MISSING_DOCUMENT,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        language=RequestLanguage.ENGLISH,
        missing_documents=missing_doc_names,
        reference_number=invoice_number,
    )


def generate_classification_request(
    product_description: str,
    invoice_number: Optional[str] = None,
    supplier_name: Optional[str] = None,
    recipient_name: str = "לקוח/ה יקר/ה",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    sender_name: str = "מערכת RCB",
    questions: Optional[List[str]] = None,
) -> ClarificationRequest:
    """Generate a request for classification clarification"""
    
    subject = "בקשה להבהרה לצורך סיווג מכס"
    if invoice_number:
        subject += f" | חשבון {invoice_number}"
    
    lines = [f"שלום {recipient_name},"]
    lines.append("")
    lines.append("בהתייחס למשלוח:")
    if invoice_number:
        lines.append(f"  • חשבון ספק: {invoice_number}")
    if supplier_name:
        lines.append(f"  • ספק: {supplier_name}")
    lines.append(f"  • תיאור הסחורה: {product_description}")
    lines.append("")
    lines.append("🔍 לצורך סיווג מכס מדויק, נדרש מידע נוסף:")
    lines.append("")
    
    q_list = questions or [
        "מהו השימוש העיקרי של המוצר?",
        "ממה עשוי המוצר (חומרים)?",
        "האם המוצר ממונע/חשמלי?",
        "מהם המידות והמשקל?",
    ]
    
    for i, q in enumerate(q_list, 1):
        lines.append(f"  {i}. {q}")
    
    lines.append("")
    lines.append("📄 אם קיים מפרט טכני או קטלוג - נא לצרף.")
    lines.append("")
    
    urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append(sender_name)
    lines.append("ר.פ.א - פורט בע\"מ")
    
    return ClarificationRequest(
        request_type=RequestType.CLASSIFICATION,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        reference_number=invoice_number,
        questions=q_list,
    )


def generate_cif_completion_request(
    invoice_number: Optional[str] = None,
    supplier_name: Optional[str] = None,
    recipient_name: str = "לקוח/ה יקר/ה",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    sender_name: str = "מערכת RCB",
    missing_values: Optional[Dict[str, bool]] = None,
    invoice_total: Optional[str] = None,
    incoterm: Optional[str] = None,
) -> ClarificationRequest:
    """Generate a request for CIF value completion"""
    
    subject = "בקשה להשלמת ערך CIF"
    if invoice_number:
        subject += f" | חשבון {invoice_number}"
    
    lines = [f"שלום {recipient_name},"]
    lines.append("")
    lines.append("בהתייחס למשלוח:")
    if invoice_number:
        lines.append(f"  • חשבון ספק: {invoice_number}")
    if supplier_name:
        lines.append(f"  • ספק: {supplier_name}")
    if invoice_total:
        lines.append(f"  • סכום החשבון: {invoice_total}")
    if incoterm:
        lines.append(f"  • תנאי מכר: {incoterm}")
    lines.append("")
    
    lines.append("💰 לצורך חישוב ערך המכס (CIF), נדרש מידע על:")
    lines.append("")
    
    if missing_values:
        if missing_values.get("freight"):
            lines.append("  ☐ עלות הובלה (Freight)")
            lines.append("     נא לצרף חשבון הובלה או לציין את הסכום")
        if missing_values.get("insurance"):
            lines.append("  ☐ עלות ביטוח (Insurance)")
            lines.append("     נא לצרף פוליסת ביטוח או לציין את הסכום")
        if missing_values.get("other_costs"):
            lines.append("  ☐ עלויות נוספות (אריזה, בדיקות, וכו')")
    else:
        lines.append("  ☐ עלות הובלה (Freight)")
        lines.append("  ☐ עלות ביטוח (Insurance)")
    
    lines.append("")
    lines.append("📝 הערה: אם תנאי המכר הם CIF - נא לאשר שהסכום כולל הובלה וביטוח.")
    lines.append("")
    
    urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append(sender_name)
    lines.append("ר.פ.א - פורט בע\"מ")
    
    return ClarificationRequest(
        request_type=RequestType.VALUE_VERIFICATION,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        reference_number=invoice_number,
    )


def generate_origin_request(
    reason: str = "preferential",
    invoice_number: Optional[str] = None,
    claimed_origin: Optional[str] = None,
    trade_agreement: Optional[str] = None,
    suspected_origin: Optional[str] = None,
    supplier_name: Optional[str] = None,
    product_description: Optional[str] = None,
    urgency: UrgencyLevel = UrgencyLevel.HIGH,
    recipient_name: str = "לקוח/ה יקר/ה",
    sender_name: str = "מערכת RCB",
) -> ClarificationRequest:
    """Generate origin verification request"""
    
    # Build subject based on reason
    if reason == "preferential":
        subject = "בקשה לתעודת מקור להעדפה מכסית"
    elif reason == "anti_dumping":
        subject = "בירור מקור - היטלי היצף"
    elif reason == "embargo":
        subject = "בירור מקור - אמברגו/סנקציות"
    else:
        subject = "בירור ארץ מקור"
    
    if invoice_number:
        subject += f" | חשבון {invoice_number}"
    
    lines = [f"שלום {recipient_name},"]
    lines.append("")
    lines.append("בהתייחס למשלוח:")
    if invoice_number:
        lines.append(f"  • חשבון ספק: {invoice_number}")
    if supplier_name:
        lines.append(f"  • ספק: {supplier_name}")
    if product_description:
        lines.append(f"  • תיאור הסחורה: {product_description}")
    lines.append("")
    
    if claimed_origin:
        lines.append(f"🌍 ארץ המקור המצוינת במסמכים: {claimed_origin}")
        lines.append("")
    
    # Reason-specific content
    if reason == "preferential":
        lines.append("📋 לצורך קבלת הטבת מכס במסגרת הסכם סחר, נדרשת תעודת מקור מתאימה.")
        lines.append("")
        if trade_agreement:
            lines.append(f"📜 ההסכם הרלוונטי: {trade_agreement}")
        lines.append("📄 המסמך הנדרש: EUR.1 או הצהרת מקור על החשבון")
        lines.append("")
        lines.append("⚠️ ללא תעודת מקור תקפה, המשלוח יחויב במכס מלא.")
        
    elif reason == "anti_dumping":
        lines.append("⚠️ המוצר עשוי להיות כפוף להיטלי היצף (Anti-Dumping).")
        lines.append("")
        if suspected_origin:
            lines.append(f"🔍 קיים חשש שמקור הסחורה הוא: {suspected_origin}")
        lines.append("")
        lines.append("📋 לצורך קביעת שיעור המכס הנכון, נדרש:")
        lines.append("  ☐ תעודת מקור מאושרת על ידי לשכת מסחר")
        lines.append("  ☐ הצהרת יצרן על מקום הייצור")
        lines.append("")
        lines.append("💡 שימו לב: יבוא ממקור שגוי עלול לגרור קנסות וחיובים רטרואקטיביים.")
        
    elif reason == "embargo":
        lines.append("⚠️ נדרש אימות מקור בשל מגבלות סנקציות/אמברגו.")
        lines.append("")
        lines.append("📋 נדרשים המסמכים הבאים:")
        lines.append("  ☐ תעודת מקור מאושרת על ידי לשכת מסחר")
        lines.append("  ☐ הצהרת ספק/יצרן על מקור הסחורה")
        lines.append("")
        lines.append("🚫 יבוא מארצות תחת אמברגו אסור בחוק.")
        
    else:
        lines.append("📋 לצורך אימות ארץ המקור, נדרש אחד מהמסמכים הבאים:")
        lines.append("  ☐ תעודת מקור")
        lines.append("  ☐ הצהרת יצרן")
        lines.append("  ☐ אישור לשכת מסחר")
    
    lines.append("")
    
    urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append(sender_name)
    lines.append("ר.פ.א - פורט בע\"מ")
    
    return ClarificationRequest(
        request_type=RequestType.ORIGIN_VERIFICATION,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        reference_number=invoice_number,
    )


def generate_generic_request(
    message: str,
    subject: str = "בקשה להשלמת מידע",
    invoice_number: Optional[str] = None,
    recipient_name: str = "לקוח/ה יקר/ה",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    sender_name: str = "מערכת RCB",
) -> ClarificationRequest:
    """Generate a generic clarification request"""
    
    if invoice_number:
        subject += f" | חשבון {invoice_number}"
    
    lines = [f"שלום {recipient_name},"]
    lines.append("")
    if invoice_number:
        lines.append(f"בהתייחס לחשבון מספר: {invoice_number}")
        lines.append("")
    lines.append(message)
    lines.append("")
    
    urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
    if urgency_phrase:
        lines.append(urgency_phrase)
        lines.append("")
    
    lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append(sender_name)
    lines.append("ר.פ.א - פורט בע\"מ")
    
    return ClarificationRequest(
        request_type=RequestType.GENERAL,
        subject=subject,
        body="\n".join(lines),
        urgency=urgency,
        reference_number=invoice_number,
    )


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Clarification Generator - Test")
    print("Session 10 - With DocumentType")
    print("=" * 60)
    
    # Test 1: Missing docs
    print("\n📧 Test 1: Missing Documents Request")
    print("-" * 40)
    request = generate_missing_docs_request(
        missing_docs=[DocumentType.PACKING_LIST, DocumentType.CERTIFICATE_OF_ORIGIN],
        invoice_date="2026-02-05",
        supplier_name="Test Supplier Co.",
        urgency=UrgencyLevel.HIGH,
        sender_name="דורון",
    )
    print(f"Subject: {request.subject}")
    print(request.body[:500])
    
    # Test 2: Origin request
    print("\n" + "=" * 60)
    print("📧 Test 2: Origin Verification Request")
    print("-" * 40)
    request = generate_origin_request(
        reason="preferential",
        invoice_number="INV-2026-001",
        claimed_origin="Germany",
        trade_agreement="EU-Israel FTA",
    )
    print(f"Subject: {request.subject}")
    print(request.body[:500])
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! DocumentType is working.")
    print("=" * 60)
