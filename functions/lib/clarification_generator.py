"""
RCB Smart Clarification Generator
Generates professional Hebrew requests for missing information.

File: functions/lib/clarification_generator.py
Project: RCB (Robotic Customs Bot)
Session: 9
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


class RequestLanguage(Enum):
    """Language for the request"""
    HEBREW = "he"
    ENGLISH = "en"
    BILINGUAL = "both"


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
    "awb": {
        "name": "שטר מטען אווירי (AWB)",
        "description": "שטר מטען אווירי",
    },
    "freight_invoice": {
        "name": "חשבון מטענים",
        "description": "חשבון עלויות הובלה מחברת השילוח",
    },
    "insurance_cert": {
        "name": "תעודת ביטוח",
        "description": "אישור ביטוח מטען",
    },
    "msds": {
        "name": "גיליון בטיחות חומר (MSDS)",
        "description": "Material Safety Data Sheet - גיליון נתוני בטיחות לחומרים כימיים",
    },
    "component_list": {
        "name": "רשימת רכיבים",
        "description": "פירוט רכיבי המוצר עם אחוזים",
    },
    "catalogue": {
        "name": "קטלוג/ברושור",
        "description": "קטלוג מוצר או ברושור טכני מהיצרן",
    },
    "tech_specs": {
        "name": "מפרט טכני",
        "description": "מפרט טכני מפורט של המוצר",
    },
    "carfax": {
        "name": "דו\"ח CarFax",
        "description": "דו\"ח היסטוריית רכב",
    },
    "coc": {
        "name": "תעודת התאמה (COC)",
        "description": "Certificate of Conformity - תעודת התאמה לתקנות",
    },
    "cert_of_origin": {
        "name": "תעודת מקור",
        "description": "תעודת מקור לצורכי העדפה מכסית",
    },
    "health_cert": {
        "name": "אישור משרד הבריאות",
        "description": "אישור יבוא ממשרד הבריאות",
    },
    "standards_cert": {
        "name": "אישור תקן",
        "description": "אישור עמידה בתקנים (CE/FCC וכו')",
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ShipmentInfo:
    """Information about the shipment"""
    shipment_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    packing_list_number: Optional[str] = None
    bl_number: Optional[str] = None
    supplier_name: Optional[str] = None
    goods_description: Optional[str] = None
    incoterms: Optional[str] = None
    vessel_name: Optional[str] = None
    eta: Optional[str] = None
    port: Optional[str] = None


@dataclass
class ClassificationDilemma:
    """Information about classification uncertainty"""
    product_description: str
    hs_options: List[Dict[str, str]]  # [{"code": "1234.56", "description": "..."}]
    reason_for_uncertainty: str
    research_findings: Dict[str, str] = field(default_factory=dict)  # {"source": "finding"}


@dataclass
class ClarificationRequest:
    """A generated clarification request"""
    request_type: RequestType
    subject: str
    body: str
    missing_items: List[str]
    urgency: UrgencyLevel
    shipment_info: Optional[ShipmentInfo] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "request_type": self.request_type.value,
            "subject": self.subject,
            "body": self.body,
            "missing_items": self.missing_items,
            "urgency": self.urgency.value,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# GENERATOR CLASS
# =============================================================================

class ClarificationGenerator:
    """
    Generates professional Hebrew clarification requests.
    
    Usage:
        gen = ClarificationGenerator()
        request = gen.generate_missing_document_request(
            missing_docs=["msds", "freight_invoice"],
            shipment_info=ShipmentInfo(invoice_number="INV-123"),
            recipient="לקוח יקר"
        )
        print(request.body)
    """
    
    def __init__(
        self,
        sender_name: str = "מערכת RCB",
        company_name: str = "ר.פ.א - פורט בע\"מ",
        sender_email: Optional[str] = None,
        sender_phone: Optional[str] = None,
    ):
        self.sender_name = sender_name
        self.company_name = company_name
        self.sender_email = sender_email
        self.sender_phone = sender_phone
    
    # -------------------------------------------------------------------------
    # Missing Document Requests
    # -------------------------------------------------------------------------
    
    def generate_missing_document_request(
        self,
        missing_docs: List[str],
        shipment_info: Optional[ShipmentInfo] = None,
        recipient: str = "לקוח/ה יקר/ה",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        tone: str = "semi_formal",
        additional_notes: Optional[str] = None,
    ) -> ClarificationRequest:
        """
        Generate a request for missing documents.
        
        Args:
            missing_docs: List of document type keys (e.g., ["msds", "freight_invoice"])
            shipment_info: Optional shipment details
            recipient: Recipient name/title
            urgency: Urgency level
            tone: "formal", "semi_formal", or "informal"
            additional_notes: Any additional notes to include
        
        Returns:
            ClarificationRequest with subject and body
        """
        # Build subject
        if len(missing_docs) == 1:
            doc_name = DOCUMENT_DESCRIPTIONS_HE.get(missing_docs[0], {}).get("name", missing_docs[0])
            subject = f"בקשה להשלמת מסמך - {doc_name}"
        else:
            subject = f"בקשה להשלמת {len(missing_docs)} מסמכים"
        
        if shipment_info and shipment_info.invoice_number:
            subject += f" | חשבון {shipment_info.invoice_number}"
        
        # Build body
        lines = []
        
        # Greeting
        lines.append(GREETINGS_HE.get(tone, GREETINGS_HE["semi_formal"]).format(recipient=recipient))
        lines.append("")
        
        # Reference to received documents
        if shipment_info:
            lines.append("קיבלנו את המסמכים הבאים:")
            if shipment_info.invoice_number:
                lines.append(f"  • חשבון ספק מספר: {shipment_info.invoice_number}")
            if shipment_info.packing_list_number:
                lines.append(f"  • מפרט אריזות מספר: {shipment_info.packing_list_number}")
            if shipment_info.bl_number:
                lines.append(f"  • שטר מטען מספר: {shipment_info.bl_number}")
            lines.append("")
        
        # Missing documents section
        lines.append("📋 לצורך המשך הטיפול במשלוח, נדרשים המסמכים הבאים:")
        lines.append("")
        
        missing_names = []
        for doc_key in missing_docs:
            doc_info = DOCUMENT_DESCRIPTIONS_HE.get(doc_key, {"name": doc_key, "description": ""})
            doc_name = doc_info["name"]
            doc_desc = doc_info.get("description", "")
            missing_names.append(doc_name)
            
            if doc_desc:
                lines.append(f"  ☐ {doc_name}")
                lines.append(f"      ({doc_desc})")
            else:
                lines.append(f"  ☐ {doc_name}")
        
        lines.append("")
        
        # Shipment context if available
        if shipment_info:
            if shipment_info.goods_description:
                lines.append(f"תיאור הסחורה: {shipment_info.goods_description}")
            if shipment_info.supplier_name:
                lines.append(f"ספק: {shipment_info.supplier_name}")
            if shipment_info.vessel_name:
                lines.append(f"אונייה: {shipment_info.vessel_name}")
            if shipment_info.eta:
                lines.append(f"הגעה משוערת: {shipment_info.eta}")
            if shipment_info.port:
                lines.append(f"נמל: {shipment_info.port}")
            if any([shipment_info.goods_description, shipment_info.supplier_name, 
                    shipment_info.vessel_name, shipment_info.eta]):
                lines.append("")
        
        # Urgency phrase
        urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
        if urgency_phrase:
            lines.append(urgency_phrase)
            lines.append("")
        
        # Additional notes
        if additional_notes:
            lines.append(additional_notes)
            lines.append("")
        
        # Request action
        lines.append("📩 נא להשיב להודעה זו עם המסמכים המבוקשים.")
        lines.append("")
        
        # Closing
        lines.append(CLOSINGS_HE.get(tone, CLOSINGS_HE["semi_formal"]).format(sender=self.sender_name))
        
        # Signature
        if self.company_name:
            lines.append(self.company_name)
        if self.sender_phone:
            lines.append(f"טל: {self.sender_phone}")
        if self.sender_email:
            lines.append(f"דוא\"ל: {self.sender_email}")
        
        body = "\n".join(lines)
        
        return ClarificationRequest(
            request_type=RequestType.MISSING_DOCUMENT,
            subject=subject,
            body=body,
            missing_items=missing_names,
            urgency=urgency,
            shipment_info=shipment_info,
        )
    
    # -------------------------------------------------------------------------
    # Classification Clarification Requests
    # -------------------------------------------------------------------------
    
    def generate_classification_request(
        self,
        dilemma: ClassificationDilemma,
        shipment_info: Optional[ShipmentInfo] = None,
        recipient: str = "לקוח/ה יקר/ה",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        tone: str = "semi_formal",
    ) -> ClarificationRequest:
        """
        Generate a request for classification clarification.
        
        Args:
            dilemma: Classification dilemma details
            shipment_info: Optional shipment details
            recipient: Recipient name/title
            urgency: Urgency level
            tone: Tone of the message
        
        Returns:
            ClarificationRequest
        """
        # Subject
        subject = "בקשה לבירור סיווג מכס"
        if shipment_info and shipment_info.invoice_number:
            subject += f" | חשבון {shipment_info.invoice_number}"
        
        # Body
        lines = []
        
        # Greeting
        lines.append(GREETINGS_HE.get(tone, GREETINGS_HE["semi_formal"]).format(recipient=recipient))
        lines.append("")
        
        # Reference documents
        if shipment_info:
            lines.append("בהתייחס למשלוח:")
            if shipment_info.invoice_number:
                lines.append(f"  • חשבון ספק: {shipment_info.invoice_number}")
            if shipment_info.packing_list_number:
                lines.append(f"  • מפרט אריזות: {shipment_info.packing_list_number}")
            lines.append("")
        
        # Product description
        lines.append(f"📦 המוצר: {dilemma.product_description}")
        lines.append("")
        
        # Research findings
        if dilemma.research_findings:
            lines.append("🔍 מחיפוש שביצענו עולה:")
            for source, finding in dilemma.research_findings.items():
                lines.append(f"  • {source}: {finding}")
            lines.append("")
        
        # Classification options
        lines.append("⚖️ אפשרויות הסיווג:")
        lines.append("")
        for i, option in enumerate(dilemma.hs_options, 1):
            code = option.get("code", "")
            desc = option.get("description", "")
            lines.append(f"  {i}. פרט מכס {code}")
            if desc:
                lines.append(f"     {desc}")
        lines.append("")
        
        # Reason for uncertainty
        lines.append(f"❓ סיבת אי-הוודאות: {dilemma.reason_for_uncertainty}")
        lines.append("")
        
        # What we need
        lines.append("📋 על מנת להכריע בסיווג הנכון, נדרש אחד מהבאים:")
        lines.append("  • מפרט טכני מפורט של המוצר")
        lines.append("  • קטלוג או ברושור מהיצרן")
        lines.append("  • הבהרה בכתב לגבי ייעוד המוצר ואופן השימוש בו")
        lines.append("")
        
        # Urgency
        urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
        if urgency_phrase:
            lines.append(urgency_phrase)
            lines.append("")
        
        # Action request
        lines.append("📩 אנא השיבו בדוא\"ל עם המידע הנדרש על מנת שנוכל להשלים את הסיווג.")
        lines.append("")
        
        # Closing
        lines.append(CLOSINGS_HE.get(tone, CLOSINGS_HE["semi_formal"]).format(sender=self.sender_name))
        if self.company_name:
            lines.append(self.company_name)
        
        body = "\n".join(lines)
        
        return ClarificationRequest(
            request_type=RequestType.CLASSIFICATION,
            subject=subject,
            body=body,
            missing_items=["מידע טכני לסיווג"],
            urgency=urgency,
            shipment_info=shipment_info,
        )
    
    # -------------------------------------------------------------------------
    # CIF Value Clarification
    # -------------------------------------------------------------------------
    
    def generate_cif_completion_request(
        self,
        missing_components: List[str],  # ["freight", "insurance"]
        goods_value: Optional[float] = None,
        currency: str = "USD",
        incoterms: Optional[str] = None,
        shipment_info: Optional[ShipmentInfo] = None,
        recipient: str = "לקוח/ה יקר/ה",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    ) -> ClarificationRequest:
        """
        Generate a request for CIF value completion documents.
        
        Args:
            missing_components: What's missing (e.g., ["freight", "insurance"])
            goods_value: Invoice value if known
            currency: Currency code
            incoterms: Incoterms if known
            shipment_info: Shipment details
            recipient: Recipient name
            urgency: Urgency level
        
        Returns:
            ClarificationRequest
        """
        subject = "השלמת ערך CIF למשלוח"
        if shipment_info and shipment_info.invoice_number:
            subject += f" | חשבון {shipment_info.invoice_number}"
        
        lines = []
        
        # Greeting
        lines.append(f"שלום {recipient},")
        lines.append("")
        
        # Context
        if shipment_info and shipment_info.invoice_number:
            lines.append(f"בהתייחס למשלוח מחשבון ספק {shipment_info.invoice_number}:")
            lines.append("")
        
        # Explain situation
        lines.append("📋 לצורך חישוב מסי היבוא, נדרש ערך CIF (עלות + ביטוח + הובלה).")
        lines.append("")
        
        if incoterms:
            lines.append(f"תנאי המכר בחשבון הספק: {incoterms}")
            lines.append("")
        
        if goods_value:
            lines.append(f"💰 ערך הסחורה בחשבון: {goods_value:,.2f} {currency}")
            lines.append("")
        
        # What's missing
        lines.append("⚠️ המרכיבים החסרים להשלמת ערך CIF:")
        lines.append("")
        
        missing_docs = []
        for component in missing_components:
            if component.lower() in ["freight", "הובלה"]:
                lines.append("  ☐ חשבון הובלה (Freight Invoice)")
                lines.append("     חשבון מחברת השילוח עבור עלות ההובלה")
                missing_docs.append("חשבון מטענים")
            elif component.lower() in ["insurance", "ביטוח"]:
                lines.append("  ☐ תעודת ביטוח (Insurance Certificate)")
                lines.append("     אישור ביטוח מטען עם פירוט עלות הביטוח")
                missing_docs.append("תעודת ביטוח")
        
        lines.append("")
        
        # Note about estimation
        lines.append("💡 הערה: במידה ואין ביטוח, ניתן להעריך את עלות הביטוח כ-0.3% מערך C+F.")
        lines.append("")
        
        # Urgency
        urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
        if urgency_phrase:
            lines.append(urgency_phrase)
            lines.append("")
        
        # Action
        lines.append("📩 נא להשיב עם המסמכים הרלוונטיים.")
        lines.append("")
        
        # Closing
        lines.append(f"בברכה,\n{self.sender_name}")
        if self.company_name:
            lines.append(self.company_name)
        
        body = "\n".join(lines)
        
        return ClarificationRequest(
            request_type=RequestType.VALUE_VERIFICATION,
            subject=subject,
            body=body,
            missing_items=missing_docs,
            urgency=urgency,
            shipment_info=shipment_info,
        )
    
    # -------------------------------------------------------------------------
    # Origin Verification Request
    # -------------------------------------------------------------------------
    
    def generate_origin_verification_request(
        self,
        verification_reason: str,  # "preferential", "anti_dumping", "embargo", "labeling", "general"
        claimed_origin: Optional[str] = None,
        suspected_origin: Optional[str] = None,
        trade_agreement: Optional[str] = None,  # "EU-Israel", "US-Israel", "EFTA", etc.
        shipment_info: Optional[ShipmentInfo] = None,
        recipient: str = "לקוח/ה יקר/ה",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        additional_questions: Optional[List[str]] = None,
    ) -> ClarificationRequest:
        """
        Generate a request for origin verification/certification.
        
        Args:
            verification_reason: Why origin needs verification
                - "preferential": For trade agreement benefits
                - "anti_dumping": Anti-dumping duty concerns
                - "embargo": Embargo/sanctions check
                - "labeling": Country of origin labeling
                - "general": General verification
            claimed_origin: Origin stated in documents
            suspected_origin: If there's reason to believe different origin
            trade_agreement: Relevant trade agreement if applicable
            shipment_info: Shipment details
            recipient: Recipient name
            urgency: Urgency level
            additional_questions: Extra questions to include
        
        Returns:
            ClarificationRequest
        """
        # Build subject based on reason
        reason_subjects = {
            "preferential": "בקשה לתעודת מקור להעדפה מכסית",
            "anti_dumping": "בירור מקור - היטלי היצף",
            "embargo": "אימות מקור סחורה",
            "labeling": "בירור ארץ מקור לסימון",
            "general": "בקשה לאימות מקור סחורה",
        }
        subject = reason_subjects.get(verification_reason, reason_subjects["general"])
        
        if shipment_info and shipment_info.invoice_number:
            subject += f" | חשבון {shipment_info.invoice_number}"
        
        lines = []
        
        # Greeting
        lines.append(f"שלום {recipient},")
        lines.append("")
        
        # Reference
        if shipment_info:
            lines.append("בהתייחס למשלוח:")
            if shipment_info.invoice_number:
                lines.append(f"  • חשבון ספק: {shipment_info.invoice_number}")
            if shipment_info.supplier_name:
                lines.append(f"  • ספק: {shipment_info.supplier_name}")
            if shipment_info.goods_description:
                lines.append(f"  • תיאור הסחורה: {shipment_info.goods_description}")
            lines.append("")
        
        # Current origin info
        if claimed_origin:
            lines.append(f"🌍 ארץ המקור המצוינת במסמכים: {claimed_origin}")
            lines.append("")
        
        # Reason-specific content
        if verification_reason == "preferential":
            lines.append("📋 לצורך קבלת הטבת מכס במסגרת הסכם סחר, נדרשת תעודת מקור מתאימה.")
            lines.append("")
            
            if trade_agreement:
                agreement_details = {
                    "EU-Israel": ("הסכם ישראל-האיחוד האירופי", "EUR.1 או הצהרת מקור על החשבון"),
                    "US-Israel": ("הסכם הסחר החופשי ישראל-ארה\"ב", "תעודת מקור ישראלית או אמריקאית"),
                    "EFTA": ("הסכם ישראל-EFTA", "EUR.1 או הצהרת מקור"),
                    "UK-Israel": ("הסכם ישראל-בריטניה", "תעודת מקור או הצהרה"),
                    "Mercosur": ("הסכם ישראל-מרקוסור", "תעודת מקור מאושרת"),
                    "Turkey": ("הסכם ישראל-טורקיה", "EUR.1 או A.TR"),
                }
                
                agreement_info = agreement_details.get(trade_agreement)
                if agreement_info:
                    lines.append(f"📜 ההסכם הרלוונטי: {agreement_info[0]}")
                    lines.append(f"📄 המסמך הנדרש: {agreement_info[1]}")
                else:
                    lines.append(f"📜 ההסכם הרלוונטי: {trade_agreement}")
                lines.append("")
            
            lines.append("⚠️ ללא תעודת מקור תקפה, המשלוח יחויב במכס מלא.")
            lines.append("")
            
            lines.append("📋 נא לספק אחד מהבאים:")
            lines.append("  ☐ תעודת מקור EUR.1 מקורית חתומה")
            lines.append("  ☐ הצהרת מקור על גבי החשבון (ליצואן מורשה)")
            lines.append("  ☐ תעודת תנועה A.TR (לטורקיה)")
            lines.append("")
            
        elif verification_reason == "anti_dumping":
            lines.append("⚠️ המוצר עשוי להיות כפוף להיטלי היצף (Anti-Dumping).")
            lines.append("")
            
            if suspected_origin:
                lines.append(f"🔍 קיים חשש שמקור הסחורה הוא: {suspected_origin}")
                lines.append("")
            
            lines.append("📋 לצורך קביעת שיעור המכס הנכון, נדרש:")
            lines.append("  ☐ תעודת מקור מאושרת על ידי לשכת מסחר")
            lines.append("  ☐ הצהרת יצרן על מקום הייצור")
            lines.append("  ☐ אישור שהמוצר לא יוצר ב: סין / מדינה בהיטל")
            lines.append("")
            
            lines.append("💡 שימו לב: יבוא ממקור שגוי עלול לגרור קנסות וחיובים רטרואקטיביים.")
            lines.append("")
            
        elif verification_reason == "embargo":
            lines.append("🚨 נדרש אימות מקור עקב מגבלות יבוא.")
            lines.append("")
            
            lines.append("📋 נא לספק:")
            lines.append("  ☐ תעודת מקור מאושרת")
            lines.append("  ☐ הצהרת ספק על מקום הייצור")
            lines.append("  ☐ אישור שהמוצר אינו ממדינה תחת סנקציות")
            lines.append("")
            
        elif verification_reason == "labeling":
            lines.append("📋 לצורך סימון \"ארץ המקור\" על המוצר, נדרש אימות.")
            lines.append("")
            
            lines.append("על פי תקנות הגנת הצרכן, יש לסמן את ארץ המקור האמיתית.")
            lines.append("")
            
            lines.append("נא לאשר:")
            lines.append("  ☐ היכן המוצר יוצר בפועל?")
            lines.append("  ☐ האם בוצע עיבוד מהותי במדינה אחרת?")
            lines.append("  ☐ מהי ארץ המקור לסימון?")
            lines.append("")
            
        else:  # general
            lines.append("📋 לצורך השלמת הליך השחרור, נדרש אימות מקור הסחורה.")
            lines.append("")
            
            lines.append("נא לספק אחד מהבאים:")
            lines.append("  ☐ תעודת מקור מלשכת המסחר")
            lines.append("  ☐ הצהרת יצרן על מקום הייצור")
            lines.append("  ☐ מסמך אחר המעיד על המקור")
            lines.append("")
        
        # Additional questions
        if additional_questions:
            lines.append("❓ שאלות נוספות:")
            for q in additional_questions:
                lines.append(f"  • {q}")
            lines.append("")
        
        # Urgency
        urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
        if urgency_phrase:
            lines.append(urgency_phrase)
            lines.append("")
        
        # Action
        lines.append("📩 נא להשיב עם המסמכים והמידע המבוקשים.")
        lines.append("")
        
        # Closing
        lines.append(f"בברכה,\n{self.sender_name}")
        if self.company_name:
            lines.append(self.company_name)
        
        body = "\n".join(lines)
        
        # Missing items list
        missing_items = ["תעודת מקור"]
        if verification_reason == "preferential":
            missing_items = ["תעודת מקור להעדפה מכסית"]
        elif verification_reason == "anti_dumping":
            missing_items = ["אימות מקור - היטלי היצף"]
        
        return ClarificationRequest(
            request_type=RequestType.ORIGIN_VERIFICATION,
            subject=subject,
            body=body,
            missing_items=missing_items,
            urgency=urgency,
            shipment_info=shipment_info,
        )
    
    # -------------------------------------------------------------------------
    # Generic Request
    # -------------------------------------------------------------------------
    
    def generate_generic_request(
        self,
        subject: str,
        main_message: str,
        action_required: str,
        shipment_info: Optional[ShipmentInfo] = None,
        recipient: str = "לקוח/ה יקר/ה",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    ) -> ClarificationRequest:
        """
        Generate a generic clarification request.
        
        Args:
            subject: Email subject
            main_message: Main body of the message
            action_required: What action is needed
            shipment_info: Shipment details
            recipient: Recipient name
            urgency: Urgency level
        
        Returns:
            ClarificationRequest
        """
        lines = []
        
        lines.append(f"שלום {recipient},")
        lines.append("")
        
        if shipment_info and shipment_info.invoice_number:
            lines.append(f"בהתייחס למשלוח מחשבון {shipment_info.invoice_number}:")
            lines.append("")
        
        lines.append(main_message)
        lines.append("")
        
        # Urgency
        urgency_phrase = URGENCY_PHRASES_HE.get(urgency, "")
        if urgency_phrase:
            lines.append(urgency_phrase)
            lines.append("")
        
        lines.append(f"📩 {action_required}")
        lines.append("")
        
        lines.append(f"בברכה,\n{self.sender_name}")
        if self.company_name:
            lines.append(self.company_name)
        
        body = "\n".join(lines)
        
        return ClarificationRequest(
            request_type=RequestType.GENERAL,
            subject=subject,
            body=body,
            missing_items=[action_required],
            urgency=urgency,
            shipment_info=shipment_info,
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_generator(
    sender_name: str = "מערכת RCB",
    company_name: str = "ר.פ.א - פורט בע\"מ",
) -> ClarificationGenerator:
    """Create a ClarificationGenerator instance"""
    return ClarificationGenerator(sender_name=sender_name, company_name=company_name)


def generate_missing_docs_request(
    missing_docs: List[str],
    invoice_number: Optional[str] = None,
    recipient: str = "לקוח/ה יקר/ה",
) -> ClarificationRequest:
    """
    Quick function to generate a missing documents request.
    
    Example:
        request = generate_missing_docs_request(
            missing_docs=["msds", "freight_invoice"],
            invoice_number="INV-123"
        )
        print(request.body)
    """
    gen = ClarificationGenerator()
    shipment_info = ShipmentInfo(invoice_number=invoice_number) if invoice_number else None
    return gen.generate_missing_document_request(
        missing_docs=missing_docs,
        shipment_info=shipment_info,
        recipient=recipient,
    )


def generate_origin_request(
    reason: str = "preferential",
    trade_agreement: Optional[str] = None,
    invoice_number: Optional[str] = None,
    claimed_origin: Optional[str] = None,
    recipient: str = "לקוח/ה יקר/ה",
) -> ClarificationRequest:
    """
    Quick function to generate an origin verification request.
    
    Args:
        reason: "preferential", "anti_dumping", "embargo", "labeling", "general"
        trade_agreement: "EU-Israel", "US-Israel", "EFTA", "UK-Israel", "Turkey"
        invoice_number: Invoice reference
        claimed_origin: Origin stated in documents
        recipient: Recipient name
    
    Example:
        request = generate_origin_request(
            reason="preferential",
            trade_agreement="EU-Israel",
            invoice_number="INV-123",
            claimed_origin="Germany"
        )
        print(request.body)
    """
    gen = ClarificationGenerator()
    shipment_info = ShipmentInfo(invoice_number=invoice_number) if invoice_number else None
    return gen.generate_origin_verification_request(
        verification_reason=reason,
        trade_agreement=trade_agreement,
        claimed_origin=claimed_origin,
        shipment_info=shipment_info,
        recipient=recipient,
    )


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Smart Clarification Generator - Test")
    print("=" * 60)
    
    gen = create_generator(
        sender_name="דורון",
        company_name="ר.פ.א - פורט בע\"מ"
    )
    
    # Test 1: Missing documents request
    print("\n📧 Test 1: Missing Documents Request")
    print("-" * 40)
    
    shipment = ShipmentInfo(
        invoice_number="INV-2026-001",
        packing_list_number="PL-2026-001",
        supplier_name="XUZHOU DRAGON GUAR",
        goods_description="חלקים למערכת נגד גביבות",
    )
    
    request = gen.generate_missing_document_request(
        missing_docs=["msds", "freight_invoice", "insurance_cert"],
        shipment_info=shipment,
        recipient="יבואן יקר",
        urgency=UrgencyLevel.HIGH,
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)
    
    # Test 2: Classification request
    print("\n" + "=" * 60)
    print("📧 Test 2: Classification Clarification Request")
    print("-" * 40)
    
    dilemma = ClassificationDilemma(
        product_description="מכשיר אלקטרוני עם מסך מגע",
        hs_options=[
            {"code": "8471.30", "description": "מחשבי כף יד (טאבלטים)"},
            {"code": "8517.12", "description": "טלפונים סלולריים"},
            {"code": "8528.72", "description": "מכשירי טלוויזיה"},
        ],
        reason_for_uncertainty="לא ברור אם המכשיר משמש בעיקר לתקשורת, לעיבוד נתונים או לצפייה",
        research_findings={
            "אתר היצרן": "מתואר כמכשיר רב-תכליתי",
            "מאגר הנתונים": "נמצאו סיווגים שונים למוצרים דומים",
        }
    )
    
    request = gen.generate_classification_request(
        dilemma=dilemma,
        shipment_info=ShipmentInfo(invoice_number="INV-2026-002"),
        recipient="לקוח נכבד",
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)
    
    # Test 3: CIF completion request
    print("\n" + "=" * 60)
    print("📧 Test 3: CIF Completion Request")
    print("-" * 40)
    
    request = gen.generate_cif_completion_request(
        missing_components=["freight", "insurance"],
        goods_value=29580,
        currency="USD",
        incoterms="FOB",
        shipment_info=ShipmentInfo(invoice_number="DG251364"),
        urgency=UrgencyLevel.URGENT,
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)
    
    # Test 4: Origin Verification - Preferential
    print("\n" + "=" * 60)
    print("📧 Test 4: Origin Verification - Preferential (EU)")
    print("-" * 40)
    
    request = gen.generate_origin_verification_request(
        verification_reason="preferential",
        claimed_origin="Germany",
        trade_agreement="EU-Israel",
        shipment_info=ShipmentInfo(
            invoice_number="EU-2026-100",
            supplier_name="Schmidt GmbH",
            goods_description="חלקי מכונות תעשייתיות",
        ),
        recipient="יבואן נכבד",
        urgency=UrgencyLevel.HIGH,
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)
    
    # Test 5: Origin Verification - Anti-Dumping
    print("\n" + "=" * 60)
    print("📧 Test 5: Origin Verification - Anti-Dumping Check")
    print("-" * 40)
    
    request = gen.generate_origin_verification_request(
        verification_reason="anti_dumping",
        claimed_origin="Vietnam",
        suspected_origin="China",
        shipment_info=ShipmentInfo(
            invoice_number="VN-2026-050",
            supplier_name="Vietnam Trading Co.",
            goods_description="פאנלים סולאריים",
        ),
        recipient="לקוח יקר",
        urgency=UrgencyLevel.URGENT,
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)
    
    # Test 6: Quick function test
    print("\n" + "=" * 60)
    print("📧 Test 6: Quick Origin Request Function")
    print("-" * 40)
    
    request = generate_origin_request(
        reason="preferential",
        trade_agreement="US-Israel",
        invoice_number="US-2026-200",
        claimed_origin="United States",
    )
    
    print(f"Subject: {request.subject}")
    print()
    print(request.body)

    print("\n" + "=" * 60)
