"""
RCB Invoice Validator - חשבון מכר
Validates commercial invoices per תקנות (מס' 2) תשל"ג-1972

File: functions/lib/invoice_validator.py
Project: RCB (Robotic Customs Bot)
Session: 10
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# REQUIRED FIELDS - פרק רביעי סעיף 6
# =============================================================================

class InvoiceField(Enum):
    """Required invoice fields per תקנות (מס' 2) תשל"ג-1972 סעיף 6"""
    
    ORIGIN = "origin"                    # (1) ארץ המקור
    PLACE_DATE = "place_date"            # (2) המקום והתאריך
    SELLER_BUYER = "seller_buyer"        # (3) שם ומען המוכר והקונה
    PACKAGES = "packages"                # (4) כמות אריזות, תיאור, סימון, מספרים
    GOODS_DESC = "goods_description"     # (5) תיאור הטובין
    QUANTITY = "quantity"                # (6) כמות לפי יחידה מסחרית
    WEIGHTS = "weights"                  # (7) משקל ברוטו, נטו, נט נטו
    PRICE = "price"                      # (8) המחיר המוסכם
    TERMS = "terms"                      # (9) תנאי משלוח, שיגור, תשלום


# Field definitions with Hebrew names and descriptions
FIELD_DEFINITIONS = {
    InvoiceField.ORIGIN: {
        "name_he": "ארץ המקור",
        "name_en": "Country of Origin",
        "section": "6(1)",
        "description": "ארץ בה הסתיים תהליך העיבוד (מעובדים) או גדלו/הופקו (אחרים)",
        "keywords": ["origin", "country of origin", "made in", "מקור", "ארץ מקור"],
    },
    InvoiceField.PLACE_DATE: {
        "name_he": "מקום ותאריך החשבון",
        "name_en": "Invoice Place & Date",
        "section": "6(2)",
        "description": "המקום והתאריך בהם הוכן החשבון",
        "keywords": ["date", "invoice date", "תאריך", "place"],
    },
    InvoiceField.SELLER_BUYER: {
        "name_he": "פרטי מוכר וקונה",
        "name_en": "Seller & Buyer Details",
        "section": "6(3)",
        "description": "השם והמען של המוכר והקונה",
        "keywords": ["seller", "buyer", "consignee", "shipper", "מוכר", "קונה", "יבואן", "יצואן"],
    },
    InvoiceField.PACKAGES: {
        "name_he": "פרטי אריזות",
        "name_en": "Package Details",
        "section": "6(4)",
        "description": "כמות האריזות, תיאורם, סימונם ומספריהם",
        "keywords": ["packages", "cartons", "boxes", "pallets", "marks", "אריזות", "קרטונים"],
    },
    InvoiceField.GOODS_DESC: {
        "name_he": "תיאור הטובין",
        "name_en": "Goods Description",
        "section": "6(5)",
        "description": "תיאור לפי סוג, מהות, טיב + תכונות מיוחדות + הרכב חומרים באחוזים",
        "keywords": ["description", "goods", "commodity", "תיאור", "סחורה", "פריט"],
    },
    InvoiceField.QUANTITY: {
        "name_he": "כמות",
        "name_en": "Quantity",
        "section": "6(6)",
        "description": "כמות הטובין לפי היחידה המסחרית המקובלת",
        "keywords": ["quantity", "qty", "units", "pcs", "כמות", "יחידות"],
    },
    InvoiceField.WEIGHTS: {
        "name_he": "משקלים",
        "name_en": "Weights",
        "section": "6(7)",
        "description": "משקל ברוטו, נטו ונט נטו - לכל אריזה + סה\"כ",
        "keywords": ["weight", "gross", "net", "g.w", "n.w", "משקל", "ברוטו", "נטו"],
    },
    InvoiceField.PRICE: {
        "name_he": "מחיר",
        "name_en": "Price",
        "section": "6(8)",
        "description": "המחיר המוסכם של הטובין",
        "keywords": ["price", "amount", "total", "value", "מחיר", "סכום", "ערך"],
    },
    InvoiceField.TERMS: {
        "name_he": "תנאי מכר",
        "name_en": "Terms",
        "section": "6(9)",
        "description": "תנאי משלוח, שיגור ותשלום (FOB, CIF, וכו') + הנחות",
        "keywords": ["terms", "incoterms", "fob", "cif", "exw", "payment", "תנאים", "תנאי תשלום"],
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FieldStatus:
    """Status of a single field"""
    field: InvoiceField
    found: bool
    value: Optional[str] = None
    confidence: float = 0.0  # 0-1
    notes: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result"""
    is_valid: bool
    score: float  # 0-100
    found_fields: List[InvoiceField]
    missing_fields: List[InvoiceField]
    field_details: Dict[InvoiceField, FieldStatus]
    warnings: List[str] = field(default_factory=list)
    
    def summary_he(self) -> str:
        """Hebrew summary of validation"""
        lines = []
        lines.append(f"{'✅ חשבון תקין' if self.is_valid else '❌ חשבון לא שלם'}")
        lines.append(f"ציון: {self.score:.0f}/100")
        lines.append(f"שדות קיימים: {len(self.found_fields)}/9")
        
        if self.missing_fields:
            lines.append("")
            lines.append("📋 שדות חסרים:")
            for f in self.missing_fields:
                info = FIELD_DEFINITIONS[f]
                lines.append(f"  ☐ {info['name_he']} - סעיף {info['section']}")
        
        if self.warnings:
            lines.append("")
            lines.append("⚠️ הערות:")
            for w in self.warnings:
                lines.append(f"  • {w}")
        
        return "\n".join(lines)


# =============================================================================
# VALIDATOR CLASS
# =============================================================================

class InvoiceValidator:
    """
    Validates commercial invoices per Israeli customs regulations.
    
    Usage:
        validator = InvoiceValidator()
        result = validator.validate(invoice_data)
        print(result.summary_he())
    """
    
    def __init__(self):
        self.field_definitions = FIELD_DEFINITIONS
    
    def validate(self, invoice_data: Dict) -> ValidationResult:
        """
        Validate invoice data against required fields.
        
        Args:
            invoice_data: Dictionary with invoice field values
            
        Returns:
            ValidationResult with complete analysis
        """
        field_details = {}
        found_fields = []
        missing_fields = []
        warnings = []
        
        # Check each required field
        for inv_field in InvoiceField:
            status = self._check_field(inv_field, invoice_data)
            field_details[inv_field] = status
            
            if status.found:
                found_fields.append(inv_field)
            else:
                missing_fields.append(inv_field)
        
        # Special validations
        warnings.extend(self._check_special_rules(invoice_data, field_details))
        
        # Calculate score
        score = (len(found_fields) / len(InvoiceField)) * 100
        
        # Valid if all fields present (or 8/9 with minor missing)
        is_valid = len(missing_fields) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            score=score,
            found_fields=found_fields,
            missing_fields=missing_fields,
            field_details=field_details,
            warnings=warnings,
        )
    
    def _check_field(self, inv_field: InvoiceField, data: Dict) -> FieldStatus:
        """Check if a specific field exists in data"""
        
        # Map field to possible keys in data
        field_mappings = {
            InvoiceField.ORIGIN: ["origin", "country_of_origin", "made_in", "ארץ_מקור"],
            InvoiceField.PLACE_DATE: ["date", "invoice_date", "place", "תאריך"],
            InvoiceField.SELLER_BUYER: ["seller", "buyer", "consignee", "shipper", "מוכר", "קונה"],
            InvoiceField.PACKAGES: ["packages", "cartons", "marks", "אריזות"],
            InvoiceField.GOODS_DESC: ["description", "goods", "items", "תיאור"],
            InvoiceField.QUANTITY: ["quantity", "qty", "units", "כמות"],
            InvoiceField.WEIGHTS: ["weight", "gross_weight", "net_weight", "משקל"],
            InvoiceField.PRICE: ["price", "amount", "total", "value", "מחיר"],
            InvoiceField.TERMS: ["terms", "incoterms", "payment_terms", "תנאים"],
        }
        
        possible_keys = field_mappings.get(inv_field, [])
        
        # Check if any key exists and has value
        for key in possible_keys:
            if key in data and data[key]:
                return FieldStatus(
                    field=inv_field,
                    found=True,
                    value=str(data[key]),
                    confidence=1.0,
                )
        
        # Also check with lowercase
        data_lower = {k.lower(): v for k, v in data.items()}
        for key in possible_keys:
            if key.lower() in data_lower and data_lower[key.lower()]:
                return FieldStatus(
                    field=inv_field,
                    found=True,
                    value=str(data_lower[key.lower()]),
                    confidence=0.9,
                )
        
        return FieldStatus(
            field=inv_field,
            found=False,
            confidence=0.0,
        )
    
    def _check_special_rules(self, data: Dict, details: Dict) -> List[str]:
        """Check special validation rules"""
        warnings = []
        
        # Rule 6(5): If goods are composite, must have material percentages
        if details[InvoiceField.GOODS_DESC].found:
            desc = details[InvoiceField.GOODS_DESC].value or ""
            composite_keywords = ["composite", "mixed", "blend", "מורכב", "תערובת"]
            if any(kw in desc.lower() for kw in composite_keywords):
                if "%" not in desc:
                    warnings.append("סעיף 6(5): טובין מורכבים - חסר פירוט אחוזי חומרים")
        
        # Rule 6(7): Should have both gross and net weights
        if details[InvoiceField.WEIGHTS].found:
            weight_val = details[InvoiceField.WEIGHTS].value or ""
            has_gross = any(x in weight_val.lower() for x in ["gross", "g.w", "ברוטו"])
            has_net = any(x in weight_val.lower() for x in ["net", "n.w", "נטו"])
            if not (has_gross and has_net):
                warnings.append("סעיף 6(7): מומלץ לציין משקל ברוטו וגם נטו")
        
        # Check for Incoterms in terms
        if details[InvoiceField.TERMS].found:
            terms_val = details[InvoiceField.TERMS].value or ""
            incoterms = ["FOB", "CIF", "CFR", "EXW", "DDP", "DAP", "FCA", "CPT", "CIP"]
            if not any(term in terms_val.upper() for term in incoterms):
                warnings.append("סעיף 6(9): לא זוהו תנאי מסירה (Incoterms)")
        
        return warnings
    
    def get_required_fields_list(self) -> str:
        """Return formatted list of all required fields"""
        lines = ["📋 שדות נדרשים בחשבון מכר - תקנות (מס' 2) תשל\"ג-1972:", ""]
        
        for inv_field in InvoiceField:
            info = self.field_definitions[inv_field]
            lines.append(f"  {info['section']} {info['name_he']}")
            lines.append(f"      {info['description']}")
            lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_validator() -> InvoiceValidator:
    """Create an InvoiceValidator instance"""
    return InvoiceValidator()


def validate_invoice(invoice_data: Dict) -> ValidationResult:
    """
    Quick function to validate an invoice.
    
    Example:
        result = validate_invoice({
            "origin": "China",
            "date": "2026-02-01",
            "seller": "XUZHOU DRAGON",
            "buyer": "RPA Port Ltd",
            "description": "Machine parts",
            "quantity": "100 pcs",
            "weight": "500 kg gross",
            "price": "10,000 USD",
            "terms": "FOB Shanghai"
        })
        print(result.summary_he())
    """
    validator = InvoiceValidator()
    return validator.validate(invoice_data)


def get_missing_fields_request(result: ValidationResult) -> str:
    """
    Generate a request for missing fields based on validation result.
    
    Returns Hebrew text ready to send to customer.
    """
    if result.is_valid:
        return "✅ החשבון מכיל את כל השדות הנדרשים"
    
    lines = []
    lines.append("📋 בהתאם לתקנות (מס' 2) תשל\"ג-1972, חסרים בחשבון המכר הפרטים הבאים:")
    lines.append("")
    
    for f in result.missing_fields:
        info = FIELD_DEFINITIONS[f]
        lines.append(f"  ☐ {info['name_he']} ({info['name_en']})")
        lines.append(f"     {info['description']}")
        lines.append("")
    
    lines.append("נא להשלים פרטים אלו בחשבון מתוקן או במסמך נפרד.")
    
    return "\n".join(lines)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Invoice Validator - חשבון מכר")
    print("תקנות (מס' 2) תשל\"ג-1972 סעיף 6")
    print("=" * 60)
    
    validator = create_validator()
    
    # Print required fields
    print("\n" + validator.get_required_fields_list())
    
    # Test 1: Complete invoice
    print("=" * 60)
    print("📧 Test 1: Complete Invoice")
    print("-" * 40)
    
    complete_invoice = {
        "origin": "China",
        "date": "2026-02-01",
        "seller": "XUZHOU DRAGON GUAR CO., LTD",
        "buyer": "RPA Port Ltd, Israel",
        "packages": "10 cartons, marks: DG-2026",
        "description": "Machine parts for anti-scaling system",
        "quantity": "100 pcs",
        "weight": "Gross: 520 kg, Net: 480 kg",
        "price": "USD 10,000.00",
        "terms": "FOB Shanghai, T/T 30 days",
    }
    
    result = validate_invoice(complete_invoice)
    print(result.summary_he())
    
    # Test 2: Incomplete invoice
    print("\n" + "=" * 60)
    print("📧 Test 2: Incomplete Invoice")
    print("-" * 40)
    
    incomplete_invoice = {
        "date": "2026-02-01",
        "seller": "Some Company",
        "description": "Various goods",
        "price": "USD 5,000",
    }
    
    result = validate_invoice(incomplete_invoice)
    print(result.summary_he())
    
    # Test 3: Generate missing fields request
    print("\n" + "=" * 60)
    print("📧 Test 3: Missing Fields Request")
    print("-" * 40)
    
    print(get_missing_fields_request(result))
    
    print("\n" + "=" * 60)
