"""
RCB Module 5: Invoice Validator
===============================
Validates commercial invoices according to Israeli customs regulations.
Based on תקנות (מס' 2) תשל"ג-1972 סעיף 6

Author: RCB System
Version: 1.0
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class InvoiceField(Enum):
    """Required fields per תקנות (מס' 2) תשל"ג-1972 סעיף 6"""
    ORIGIN = "origin"              # 6(1) - ארץ המקור
    PLACE_DATE = "place_date"      # 6(2) - מקום ותאריך
    SELLER_BUYER = "seller_buyer"  # 6(3) - מוכר וקונה
    PACKAGES = "packages"          # 6(4) - פרטי אריזות
    DESCRIPTION = "description"    # 6(5) - תיאור הטובין
    QUANTITY = "quantity"          # 6(6) - כמות
    WEIGHTS = "weights"            # 6(7) - משקלים
    PRICE = "price"                # 6(8) - מחיר
    TERMS = "terms"                # 6(9) - תנאי מכר


# Field definitions with Hebrew names and requirements
FIELD_DEFINITIONS = {
    InvoiceField.ORIGIN: {
        "section": "6(1)",
        "name_he": "ארץ המקור",
        "name_en": "Country of Origin",
        "description_he": "ארץ בה הסתיים תהליך העיבוד (מעובדים) או גדלו/הופקו (אחרים)",
        "required": True,
        "weight": 15,  # Importance weight for scoring
    },
    InvoiceField.PLACE_DATE: {
        "section": "6(2)",
        "name_he": "מקום ותאריך החשבון",
        "name_en": "Place and Date",
        "description_he": "המקום והתאריך בהם הוכן החשבון",
        "required": True,
        "weight": 10,
    },
    InvoiceField.SELLER_BUYER: {
        "section": "6(3)",
        "name_he": "פרטי מוכר וקונה",
        "name_en": "Seller and Buyer",
        "description_he": "השם והמען של המוכר והקונה",
        "required": True,
        "weight": 15,
    },
    InvoiceField.PACKAGES: {
        "section": "6(4)",
        "name_he": "פרטי אריזות",
        "name_en": "Package Details",
        "description_he": "כמות האריזות, תיאורם, סימונם ומספריהם",
        "required": True,
        "weight": 10,
    },
    InvoiceField.DESCRIPTION: {
        "section": "6(5)",
        "name_he": "תיאור הטובין",
        "name_en": "Goods Description",
        "description_he": "תיאור לפי סוג, מהות, טיב + תכונות מיוחדות + הרכב חומרים באחוזים",
        "required": True,
        "weight": 15,
    },
    InvoiceField.QUANTITY: {
        "section": "6(6)",
        "name_he": "כמות",
        "name_en": "Quantity",
        "description_he": "כמות הטובין לפי היחידה המסחרית המקובלת",
        "required": True,
        "weight": 10,
    },
    InvoiceField.WEIGHTS: {
        "section": "6(7)",
        "name_he": "משקלים",
        "name_en": "Weights",
        "description_he": "משקל ברוטו, נטו ונט נטו - לכל אריזה + סה\"כ",
        "required": True,
        "weight": 10,
    },
    InvoiceField.PRICE: {
        "section": "6(8)",
        "name_he": "מחיר",
        "name_en": "Price",
        "description_he": "המחיר המוסכם של הטובין",
        "required": True,
        "weight": 10,
    },
    InvoiceField.TERMS: {
        "section": "6(9)",
        "name_he": "תנאי מכר",
        "name_en": "Terms",
        "description_he": "תנאי משלוח, שיגור ותשלום (FOB, CIF, וכו') + הנחות",
        "required": True,
        "weight": 5,
    },
}

# Field mappings - different ways fields might appear in invoice data
FIELD_MAPPINGS = {
    InvoiceField.ORIGIN: ["origin", "country_of_origin", "country", "מקור", "ארץ_מקור", "ארץ"],
    InvoiceField.PLACE_DATE: ["date", "invoice_date", "place", "place_date", "תאריך", "מקום"],
    InvoiceField.SELLER_BUYER: ["seller", "buyer", "vendor", "customer", "shipper", "consignee", 
                                 "מוכר", "קונה", "ספק", "לקוח"],
    InvoiceField.PACKAGES: ["packages", "cartons", "pallets", "boxes", "package_details",
                            "אריזות", "קרטונים", "משטחים"],
    InvoiceField.DESCRIPTION: ["description", "goods", "product", "item", "commodity",
                               "תיאור", "סחורה", "מוצר", "פריט"],
    InvoiceField.QUANTITY: ["quantity", "qty", "units", "pieces", "pcs", "כמות", "יחידות"],
    InvoiceField.WEIGHTS: ["weight", "gross_weight", "net_weight", "weight_gross", "weight_net",
                           "משקל", "ברוטו", "נטו"],
    InvoiceField.PRICE: ["price", "total", "amount", "value", "unit_price", "total_amount",
                         "מחיר", "סכום", "ערך"],
    InvoiceField.TERMS: ["terms", "incoterms", "payment_terms", "delivery_terms", "fob", "cif",
                         "תנאים", "תנאי_מכר"],
}


@dataclass
class FieldValidation:
    """Validation result for a single field"""
    field: InvoiceField
    present: bool
    value: Optional[str] = None
    quality: str = "unknown"  # "good", "partial", "missing"
    notes: Optional[str] = None


@dataclass
class InvoiceValidationResult:
    """Complete validation result for an invoice"""
    is_valid: bool
    score: int  # 0-100
    fields_present: int
    fields_required: int
    field_results: List[FieldValidation] = field(default_factory=list)
    missing_fields: List[InvoiceField] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)
    
    def summary_he(self) -> str:
        """Generate Hebrew summary"""
        if self.is_valid:
            return f"✅ חשבון תקין\nציון: {self.score}/100\nשדות קיימים: {self.fields_present}/{self.fields_required}"
        else:
            lines = [
                f"❌ חשבון לא שלם",
                f"ציון: {self.score}/100",
                f"שדות קיימים: {self.fields_present}/{self.fields_required}",
            ]
            if self.missing_fields:
                lines.append("📋 שדות חסרים:")
                for f in self.missing_fields:
                    defn = FIELD_DEFINITIONS[f]
                    lines.append(f"  ☐ {defn['name_he']} - סעיף {defn['section']}")
            return "\n".join(lines)
    
    def get_missing_fields_request(self) -> str:
        """Generate a Hebrew request for missing fields"""
        if not self.missing_fields:
            return ""
        
        lines = ["📋 בהתאם לתקנות (מס' 2) תשל\"ג-1972, חסרים בחשבון המכר הפרטים הבאים:"]
        for f in self.missing_fields:
            defn = FIELD_DEFINITIONS[f]
            lines.append(f"  ☐ {defn['name_he']} ({defn['name_en']})")
            lines.append(f"     {defn['description_he']}")
        lines.append("")
        lines.append("נא להשלים פרטים אלו בחשבון מתוקן או במסמך נפרד.")
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "fields_present": self.fields_present,
            "fields_required": self.fields_required,
            "missing_fields": [f.value for f in self.missing_fields],
            "warnings": self.warnings,
            "validated_at": self.validated_at.isoformat(),
        }


def _check_field_present(data: Dict[str, Any], field: InvoiceField) -> tuple[bool, Optional[str]]:
    """Check if a field is present in the invoice data"""
    mappings = FIELD_MAPPINGS.get(field, [])
    
    for key in mappings:
        # Check exact key
        if key in data and data[key]:
            return True, str(data[key])
        
        # Check lowercase
        key_lower = key.lower()
        for data_key in data:
            if data_key.lower() == key_lower and data[data_key]:
                return True, str(data[data_key])
    
    # Special handling for composite fields
    if field == InvoiceField.PLACE_DATE:
        has_date = any(k in str(data).lower() for k in ["date", "תאריך"])
        has_place = any(k in str(data).lower() for k in ["place", "מקום"])
        if has_date or has_place:
            return True, "partial"
    
    if field == InvoiceField.SELLER_BUYER:
        has_seller = any(k in str(data).lower() for k in ["seller", "vendor", "shipper", "מוכר", "ספק"])
        has_buyer = any(k in str(data).lower() for k in ["buyer", "customer", "consignee", "קונה", "לקוח"])
        if has_seller or has_buyer:
            return True, "partial"
    
    if field == InvoiceField.WEIGHTS:
        has_weight = any(k in str(data).lower() for k in ["weight", "gross", "net", "משקל", "ברוטו", "נטו"])
        if has_weight:
            return True, "partial"
    
    return False, None


def validate_invoice(data: Dict[str, Any]) -> InvoiceValidationResult:
    """
    Validate an invoice against Israeli customs requirements.
    
    Args:
        data: Dictionary containing invoice fields
        
    Returns:
        InvoiceValidationResult with validation details
    """
    field_results = []
    missing_fields = []
    total_weight = 0
    present_weight = 0
    warnings = []
    
    for field_enum, definition in FIELD_DEFINITIONS.items():
        present, value = _check_field_present(data, field_enum)
        weight = definition["weight"]
        total_weight += weight
        
        quality = "missing"
        if present:
            if value == "partial":
                quality = "partial"
                present_weight += weight * 0.5
                warnings.append(f"{definition['name_he']} - מידע חלקי")
            else:
                quality = "good"
                present_weight += weight
        else:
            missing_fields.append(field_enum)
        
        field_results.append(FieldValidation(
            field=field_enum,
            present=present,
            value=value if value != "partial" else None,
            quality=quality,
        ))
    
    # Calculate score
    score = int((present_weight / total_weight) * 100) if total_weight > 0 else 0
    
    # Determine validity (need at least 70% and no critical fields missing)
    critical_fields = [InvoiceField.ORIGIN, InvoiceField.DESCRIPTION, InvoiceField.PRICE]
    critical_missing = [f for f in missing_fields if f in critical_fields]
    is_valid = score >= 70 and len(critical_missing) == 0
    
    return InvoiceValidationResult(
        is_valid=is_valid,
        score=score,
        fields_present=len([f for f in field_results if f.present]),
        fields_required=len(FIELD_DEFINITIONS),
        field_results=field_results,
        missing_fields=missing_fields,
        warnings=warnings,
    )


def quick_validate(data: Dict[str, Any]) -> tuple[bool, int, List[str]]:
    """
    Quick validation returning just validity, score, and missing field names.
    
    Returns:
        Tuple of (is_valid, score, list of missing field names in Hebrew)
    """
    result = validate_invoice(data)
    missing_names = [FIELD_DEFINITIONS[f]["name_he"] for f in result.missing_fields]
    return result.is_valid, result.score, missing_names


def print_requirements():
    """Print all field requirements"""
    print("📋 שדות נדרשים בחשבון מכר - תקנות (מס' 2) תשל\"ג-1972:")
    for field_enum, definition in FIELD_DEFINITIONS.items():
        print(f"  {definition['section']} {definition['name_he']}")
        print(f"      {definition['description_he']}")


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("RCB Invoice Validator - חשבון מכר")
    print("תקנות (מס' 2) תשל\"ג-1972 סעיף 6")
    print("=" * 60)
    
    # Print requirements
    print_requirements()
    
    # Test 1: Complete invoice
    print("\n" + "=" * 60)
    print("📧 Test 1: Complete Invoice")
    print("-" * 40)
    
    complete_invoice = {
        "origin": "China",
        "date": "2026-02-01",
        "place": "Shanghai",
        "seller": "ABC Trading Co., 123 Main St, Shanghai",
        "buyer": "XYZ Import Ltd, Tel Aviv",
        "packages": "10 cartons, marked 1-10",
        "description": "Electronic components - capacitors, resistors",
        "quantity": "10,000 pieces",
        "weight_gross": "500 kg",
        "weight_net": "450 kg",
        "price": "USD 10,000",
        "terms": "FOB Shanghai",
    }
    
    result = validate_invoice(complete_invoice)
    print(result.summary_he())
    
    # Test 2: Incomplete invoice
    print("\n" + "=" * 60)
    print("📧 Test 2: Incomplete Invoice")
    print("-" * 40)
    
    incomplete_invoice = {
        "date": "2026-02-01",
        "seller": "ABC Trading Co.",
        "description": "Electronic parts",
        "price": "USD 5,000",
    }
    
    result = validate_invoice(incomplete_invoice)
    print(result.summary_he())
    
    # Test 3: Get missing fields request
    print("\n" + "=" * 60)
    print("📧 Test 3: Missing Fields Request")
    print("-" * 40)
    print(result.get_missing_fields_request())
    
    print("\n" + "=" * 60)


def quick_validate(data):
    """
    Quick validation returning just validity, score, and missing field names.
    
    Returns:
        Tuple of (is_valid, score, list of missing field names in Hebrew)
    """
    result = validate_invoice(data)
    missing_names = [FIELD_DEFINITIONS[f]["name_he"] for f in result.missing_fields]
    return result.is_valid, result.score, missing_names
