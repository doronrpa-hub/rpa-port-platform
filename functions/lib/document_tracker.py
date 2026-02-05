"""
RCB Document Phase Tracker
Tracks shipment documents and identifies current phase + missing documents.

File: functions/lib/document_tracker.py
Project: RCB (Robotic Customs Bot)
Session: 9
"""

from enum import Enum
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


# =============================================================================
# ENUMS
# =============================================================================

class ShipmentPhase(Enum):
    """Shipment phases from order to release"""
    INITIAL = "initial"                          # לא התקבלו מסמכים
    ORDER_RECEIVED = "order_received"            # התקבל חשבון ספק
    PRE_SHIPMENT = "pre_shipment"                # חשבון + פירוט אריזות
    SHIPMENT_LOADED = "shipment_loaded"          # B/L או AWB התקבל
    CIF_COMPLETION = "cif_completion"            # השלמת ערך CIF
    READY_FOR_DECLARATION = "ready_for_declaration"  # מוכן להצהרה
    DECLARED = "declared"                        # הוגשה הצהרה
    RELEASED = "released"                        # הותר


class ProductCategory(Enum):
    """Product categories requiring specific documents"""
    CHEMICALS = "chemicals"              # כימיקלים
    FOOD = "food"                        # מזון
    VEHICLES = "vehicles"                # רכבים
    MACHINERY = "machinery"              # מכונות
    ELECTRONICS = "electronics"          # אלקטרוניקה
    PHARMACEUTICALS = "pharmaceuticals"  # תרופות
    TEXTILES = "textiles"                # טקסטיל
    TOYS = "toys"                        # צעצועים
    COSMETICS = "cosmetics"              # קוסמטיקה
    GENERAL = "general"                  # כללי


class DocumentType(Enum):
    """All document types in customs process"""
    # Phase 1: Pre-shipment
    INVOICE = "invoice"                      # חשבון ספק
    PACKING_LIST = "packing_list"            # מפרט אריזות
    CATALOGUE = "catalogue"                  # קטלוג
    MSDS = "msds"                            # Material Safety Data Sheet
    COMPONENT_LIST = "component_list"        # רשימת רכיבים (מזון)
    CARFAX = "carfax"                        # CarFax (רכבים)
    COC = "coc"                              # Certificate of Conformity
    TECH_SPECS = "tech_specs"                # מפרט טכני
    
    # Phase 2: Shipment loaded
    BILL_OF_LADING = "bill_of_lading"        # שטר מטען ימי
    AWB = "awb"                              # Air Waybill
    
    # Phase 3: CIF completion
    FREIGHT_INVOICE = "freight_invoice"      # חשבון מטענים
    INSURANCE_CERT = "insurance_cert"        # תעודת ביטוח
    DELIVERY_ORDER = "delivery_order"        # פקודת מסירה
    
    # Phase 4: Declaration
    IMPORT_LICENSE = "import_license"        # רישיון יבוא
    CERTIFICATE_OF_ORIGIN = "cert_of_origin" # תעודת מקור
    PREFERENCE_DOC = "preference_doc"        # מסמך העדפה
    HEALTH_CERT = "health_cert"              # אישור משרד הבריאות
    STANDARDS_CERT = "standards_cert"        # אישור תקן


class Incoterm(Enum):
    """Incoterms 2020"""
    EXW = "EXW"  # Ex Works
    FCA = "FCA"  # Free Carrier
    FAS = "FAS"  # Free Alongside Ship
    FOB = "FOB"  # Free On Board
    CFR = "CFR"  # Cost and Freight
    CIF = "CIF"  # Cost, Insurance, Freight
    CIP = "CIP"  # Carriage and Insurance Paid
    CPT = "CPT"  # Carriage Paid To
    DAP = "DAP"  # Delivered at Place
    DPU = "DPU"  # Delivered at Place Unloaded
    DDP = "DDP"  # Delivered Duty Paid


class TransportMode(Enum):
    """Transport modes"""
    SEA_FCL = "sea_fcl"      # ימי - מכולה מלאה
    SEA_LCL = "sea_lcl"      # ימי - מטען חלקי
    AIR = "air"              # אווירי
    LAND = "land"            # יבשתי
    COURIER = "courier"      # בלדרות


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Document:
    """Represents a shipment document"""
    doc_type: DocumentType
    doc_number: Optional[str] = None
    doc_date: Optional[datetime] = None
    file_path: Optional[str] = None
    verified: bool = False
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "doc_type": self.doc_type.value,
            "doc_number": self.doc_number,
            "doc_date": self.doc_date.isoformat() if self.doc_date else None,
            "file_path": self.file_path,
            "verified": self.verified,
            "notes": self.notes
        }


@dataclass
class ClarificationRequest:
    """Request for missing information"""
    missing_docs: List[str]
    reason: str
    hs_options: List[Dict[str, str]] = field(default_factory=list)
    search_findings: Dict[str, str] = field(default_factory=dict)
    
    def to_hebrew(self) -> str:
        """Generate Hebrew clarification request"""
        lines = []
        lines.append("⚠️ השלמה נדרשת לסיווג:")
        lines.append(f"סיבה: {self.reason}")
        lines.append("")
        lines.append("מסמכים חסרים:")
        for doc in self.missing_docs:
            lines.append(f"  • {doc}")
        
        if self.hs_options:
            lines.append("")
            lines.append("אפשרויות סיווג:")
            for opt in self.hs_options:
                lines.append(f"  • פרט מכס {opt.get('code', '')} - {opt.get('description', '')}")
        
        if self.search_findings:
            lines.append("")
            lines.append("ממצאי חיפוש:")
            for source, finding in self.search_findings.items():
                lines.append(f"  • {source}: {finding}")
        
        lines.append("")
        lines.append("📩 אנא שלחו בחוזר בדוא\"ל על מנת שאוכל להשלים את התהליך.")
        
        return "\n".join(lines)


# =============================================================================
# CONFIGURATION TABLES
# =============================================================================

# Incoterms: what's included in the price
INCOTERM_INCLUDES = {
    Incoterm.EXW: {"freight": False, "insurance": False},
    Incoterm.FCA: {"freight": False, "insurance": False},
    Incoterm.FAS: {"freight": False, "insurance": False},
    Incoterm.FOB: {"freight": False, "insurance": False},
    Incoterm.CFR: {"freight": True,  "insurance": False},
    Incoterm.CIF: {"freight": True,  "insurance": True},
    Incoterm.CIP: {"freight": True,  "insurance": True},
    Incoterm.CPT: {"freight": True,  "insurance": False},
    Incoterm.DAP: {"freight": True,  "insurance": False},
    Incoterm.DPU: {"freight": True,  "insurance": False},
    Incoterm.DDP: {"freight": True,  "insurance": True},
}

# Product category: required extra documents
PRODUCT_REQUIRED_DOCS = {
    ProductCategory.CHEMICALS: [DocumentType.MSDS],
    ProductCategory.FOOD: [DocumentType.COMPONENT_LIST, DocumentType.HEALTH_CERT],
    ProductCategory.VEHICLES: [DocumentType.CARFAX, DocumentType.COC],
    ProductCategory.MACHINERY: [DocumentType.CATALOGUE, DocumentType.TECH_SPECS],
    ProductCategory.ELECTRONICS: [DocumentType.TECH_SPECS, DocumentType.STANDARDS_CERT],
    ProductCategory.PHARMACEUTICALS: [DocumentType.HEALTH_CERT],
    ProductCategory.TEXTILES: [DocumentType.COMPONENT_LIST],
    ProductCategory.TOYS: [DocumentType.STANDARDS_CERT],
    ProductCategory.COSMETICS: [DocumentType.COMPONENT_LIST, DocumentType.HEALTH_CERT],
    ProductCategory.GENERAL: [],
}

# Document type Hebrew names
DOC_TYPE_HEBREW = {
    DocumentType.INVOICE: "חשבון ספק",
    DocumentType.PACKING_LIST: "מפרט אריזות",
    DocumentType.CATALOGUE: "קטלוג",
    DocumentType.MSDS: "גיליון בטיחות חומר (MSDS)",
    DocumentType.COMPONENT_LIST: "רשימת רכיבים עם אחוזים",
    DocumentType.CARFAX: "דו\"ח CarFax",
    DocumentType.COC: "תעודת התאמה (COC)",
    DocumentType.TECH_SPECS: "מפרט טכני",
    DocumentType.BILL_OF_LADING: "שטר מטען ימי (B/L)",
    DocumentType.AWB: "שטר מטען אווירי (AWB)",
    DocumentType.FREIGHT_INVOICE: "חשבון מטענים",
    DocumentType.INSURANCE_CERT: "תעודת ביטוח",
    DocumentType.DELIVERY_ORDER: "פקודת מסירה",
    DocumentType.IMPORT_LICENSE: "רישיון יבוא",
    DocumentType.CERTIFICATE_OF_ORIGIN: "תעודת מקור",
    DocumentType.PREFERENCE_DOC: "מסמך העדפה",
    DocumentType.HEALTH_CERT: "אישור משרד הבריאות",
    DocumentType.STANDARDS_CERT: "אישור תקן",
}

# Phase Hebrew names
PHASE_HEBREW = {
    ShipmentPhase.INITIAL: "טרם התקבלו מסמכים",
    ShipmentPhase.ORDER_RECEIVED: "התקבל חשבון ספק",
    ShipmentPhase.PRE_SHIPMENT: "שלב טרום משלוח",
    ShipmentPhase.SHIPMENT_LOADED: "המטען נטען",
    ShipmentPhase.CIF_COMPLETION: "השלמת ערך CIF",
    ShipmentPhase.READY_FOR_DECLARATION: "מוכן להגשת הצהרה",
    ShipmentPhase.DECLARED: "הוגשה הצהרה",
    ShipmentPhase.RELEASED: "הותר",
}


# =============================================================================
# MAIN TRACKER CLASS
# =============================================================================

class DocumentTracker:
    """
    Tracks shipment documents and determines current phase.
    
    Usage:
        tracker = DocumentTracker(shipment_id="SHP-001")
        tracker.add_document(Document(DocumentType.INVOICE, "INV-123"))
        tracker.add_document(Document(DocumentType.PACKING_LIST, "PL-123"))
        tracker.set_incoterms(Incoterm.FOB)
        tracker.set_product_category(ProductCategory.CHEMICALS)
        
        print(tracker.phase)           # ShipmentPhase.PRE_SHIPMENT
        print(tracker.missing_docs)    # ['MSDS', 'B/L or AWB', ...]
        print(tracker.phase_hebrew)    # 'שלב טרום משלוח'
    """
    
    def __init__(
        self,
        shipment_id: str,
        direction: str = "import",  # "import" or "export"
        transport_mode: Optional[TransportMode] = None
    ):
        self.shipment_id = shipment_id
        self.direction = direction
        self.transport_mode = transport_mode
        self.documents: Dict[DocumentType, Document] = {}
        self.incoterms: Optional[Incoterm] = None
        self.product_category: ProductCategory = ProductCategory.GENERAL
        self.declaration_number: Optional[str] = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------
    
    def add_document(self, doc: Document) -> None:
        """Add or update a document"""
        self.documents[doc.doc_type] = doc
        self.updated_at = datetime.now()
    
    def has_document(self, doc_type: DocumentType) -> bool:
        """Check if document exists"""
        return doc_type in self.documents
    
    def get_document(self, doc_type: DocumentType) -> Optional[Document]:
        """Get document by type"""
        return self.documents.get(doc_type)
    
    def remove_document(self, doc_type: DocumentType) -> None:
        """Remove a document"""
        if doc_type in self.documents:
            del self.documents[doc_type]
            self.updated_at = datetime.now()
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    def set_incoterms(self, incoterms) -> None:
        """Set the Incoterms"""
        if isinstance(incoterms, str):
            incoterms = Incoterm(incoterms.upper())
        self.incoterms = incoterms
        self.updated_at = datetime.now()
    
    def set_product_category(self, category) -> None:
        """Set the product category"""
        if isinstance(category, str):
            category = ProductCategory(category.lower())
        self.product_category = category
        self.updated_at = datetime.now()
    
    def set_transport_mode(self, mode) -> None:
        """Set the transport mode"""
        if isinstance(mode, str):
            mode = TransportMode(mode.lower())
        self.transport_mode = mode
        self.updated_at = datetime.now()
    
    # -------------------------------------------------------------------------
    # Phase Detection
    # -------------------------------------------------------------------------
    
    @property
    def phase(self) -> ShipmentPhase:
        """Detect current shipment phase based on documents"""
        has_invoice = self.has_document(DocumentType.INVOICE)
        has_packing = self.has_document(DocumentType.PACKING_LIST)
        has_bl = self.has_document(DocumentType.BILL_OF_LADING)
        has_awb = self.has_document(DocumentType.AWB)
        has_freight = self.has_document(DocumentType.FREIGHT_INVOICE)
        has_insurance = self.has_document(DocumentType.INSURANCE_CERT)
        has_delivery = self.has_document(DocumentType.DELIVERY_ORDER)
        
        # Check if declared
        if self.declaration_number:
            return ShipmentPhase.DECLARED
        
        # Check for delivery order (ready for declaration)
        if has_delivery:
            return ShipmentPhase.READY_FOR_DECLARATION
        
        # Check CIF completion
        if self._is_cif_complete():
            return ShipmentPhase.CIF_COMPLETION
        
        # Check if shipment loaded (has transport document)
        if has_bl or has_awb:
            return ShipmentPhase.SHIPMENT_LOADED
        
        # Check pre-shipment (has both invoice and packing)
        if has_invoice and has_packing:
            return ShipmentPhase.PRE_SHIPMENT
        
        # Check order received (has invoice)
        if has_invoice:
            return ShipmentPhase.ORDER_RECEIVED
        
        return ShipmentPhase.INITIAL
    
    @property
    def phase_hebrew(self) -> str:
        """Get phase name in Hebrew"""
        return PHASE_HEBREW.get(self.phase, "לא ידוע")
    
    # -------------------------------------------------------------------------
    # Missing Documents Detection
    # -------------------------------------------------------------------------
    
    @property
    def missing_docs(self) -> List[str]:
        """Get list of missing documents (Hebrew names)"""
        missing = []
        
        # Always required: Invoice + Packing List
        if not self.has_document(DocumentType.INVOICE):
            missing.append(DOC_TYPE_HEBREW[DocumentType.INVOICE])
        if not self.has_document(DocumentType.PACKING_LIST):
            missing.append(DOC_TYPE_HEBREW[DocumentType.PACKING_LIST])
        
        # Transport document (B/L or AWB)
        if not self.has_document(DocumentType.BILL_OF_LADING) and \
           not self.has_document(DocumentType.AWB):
            if self.transport_mode in [TransportMode.SEA_FCL, TransportMode.SEA_LCL]:
                missing.append(DOC_TYPE_HEBREW[DocumentType.BILL_OF_LADING])
            elif self.transport_mode == TransportMode.AIR:
                missing.append(DOC_TYPE_HEBREW[DocumentType.AWB])
            else:
                missing.append("שטר מטען (B/L או AWB)")
        
        # CIF components based on Incoterms
        missing.extend(self._get_missing_cif_docs())
        
        # Product-specific documents
        missing.extend(self._get_missing_product_docs())
        
        return missing
    
    @property
    def missing_docs_for_classification(self) -> List[str]:
        """Get documents missing specifically for classification"""
        missing = []
        
        # Basic documents for any classification
        if not self.has_document(DocumentType.INVOICE):
            missing.append(DOC_TYPE_HEBREW[DocumentType.INVOICE])
        
        # Product-specific
        missing.extend(self._get_missing_product_docs())
        
        return missing
    
    def _get_missing_cif_docs(self) -> List[str]:
        """Get missing CIF component documents"""
        missing = []
        
        if not self.incoterms:
            return missing
        
        includes = INCOTERM_INCLUDES.get(self.incoterms, {})
        
        # Check freight
        if not includes.get("freight", False):
            if not self.has_document(DocumentType.FREIGHT_INVOICE):
                missing.append(DOC_TYPE_HEBREW[DocumentType.FREIGHT_INVOICE])
        
        # Check insurance
        if not includes.get("insurance", False):
            if not self.has_document(DocumentType.INSURANCE_CERT):
                missing.append(DOC_TYPE_HEBREW[DocumentType.INSURANCE_CERT])
        
        return missing
    
    def _get_missing_product_docs(self) -> List[str]:
        """Get missing product-specific documents"""
        missing = []
        required = PRODUCT_REQUIRED_DOCS.get(self.product_category, [])
        
        for doc_type in required:
            if not self.has_document(doc_type):
                missing.append(DOC_TYPE_HEBREW[doc_type])
        
        return missing
    
    def _is_cif_complete(self) -> bool:
        """Check if CIF value can be calculated"""
        if not self.incoterms:
            return False
        
        includes = INCOTERM_INCLUDES.get(self.incoterms, {})
        
        # Check freight
        if not includes.get("freight", False):
            if not self.has_document(DocumentType.FREIGHT_INVOICE):
                return False
        
        # Check insurance
        if not includes.get("insurance", False):
            if not self.has_document(DocumentType.INSURANCE_CERT):
                return False
        
        return True
    
    # -------------------------------------------------------------------------
    # Classification Readiness
    # -------------------------------------------------------------------------
    
    @property
    def ready_to_classify(self) -> bool:
        """Check if we have enough documents to attempt classification"""
        # Must have invoice at minimum
        if not self.has_document(DocumentType.INVOICE):
            return False
        
        # Check product-specific requirements
        required = PRODUCT_REQUIRED_DOCS.get(self.product_category, [])
        for doc_type in required:
            if not self.has_document(doc_type):
                return False
        
        return True
    
    @property
    def ready_for_declaration(self) -> bool:
        """Check if ready to submit customs declaration"""
        # Must have basic documents
        if not self.has_document(DocumentType.INVOICE):
            return False
        if not self.has_document(DocumentType.PACKING_LIST):
            return False
        
        # Must have transport document
        if not self.has_document(DocumentType.BILL_OF_LADING) and \
           not self.has_document(DocumentType.AWB):
            return False
        
        # Must have CIF complete
        if not self._is_cif_complete():
            return False
        
        return True
    
    # -------------------------------------------------------------------------
    # Clarification Request Generation
    # -------------------------------------------------------------------------
    
    def generate_clarification_request(
        self,
        reason: str,
        hs_options: Optional[List[Dict[str, str]]] = None,
        search_findings: Optional[Dict[str, str]] = None
    ) -> ClarificationRequest:
        """Generate a clarification request for missing information"""
        return ClarificationRequest(
            missing_docs=self.missing_docs_for_classification,
            reason=reason,
            hs_options=hs_options or [],
            search_findings=search_findings or {}
        )
    
    # -------------------------------------------------------------------------
    # Status Report
    # -------------------------------------------------------------------------
    
    def get_status_report(self, language: str = "he") -> str:
        """Generate a status report"""
        if language == "he":
            return self._get_hebrew_status()
        return self._get_english_status()
    
    def _get_hebrew_status(self) -> str:
        """Generate Hebrew status report"""
        lines = []
        lines.append(f"📦 משלוח: {self.shipment_id}")
        lines.append(f"📋 שלב: {self.phase_hebrew}")
        lines.append("")
        
        # Documents received
        lines.append("✅ מסמכים שהתקבלו:")
        if self.documents:
            for doc_type, doc in self.documents.items():
                doc_name = DOC_TYPE_HEBREW.get(doc_type, doc_type.value)
                num = f" ({doc.doc_number})" if doc.doc_number else ""
                lines.append(f"  • {doc_name}{num}")
        else:
            lines.append("  (אין)")
        
        lines.append("")
        
        # Missing documents
        missing = self.missing_docs
        if missing:
            lines.append("❌ מסמכים חסרים:")
            for doc in missing:
                lines.append(f"  • {doc}")
        else:
            lines.append("✅ כל המסמכים התקבלו")
        
        lines.append("")
        
        # Incoterms
        if self.incoterms:
            lines.append(f"📜 תנאי מכר: {self.incoterms.value}")
        
        # Product category
        lines.append(f"📦 קטגוריית מוצר: {self.product_category.value}")
        
        # Readiness
        lines.append("")
        lines.append(f"🎯 מוכן לסיווג: {'כן' if self.ready_to_classify else 'לא'}")
        lines.append(f"📝 מוכן להצהרה: {'כן' if self.ready_for_declaration else 'לא'}")
        
        return "\n".join(lines)
    
    def _get_english_status(self) -> str:
        """Generate English status report"""
        lines = []
        lines.append(f"📦 Shipment: {self.shipment_id}")
        lines.append(f"📋 Phase: {self.phase.value}")
        lines.append("")
        
        lines.append("✅ Documents Received:")
        if self.documents:
            for doc_type, doc in self.documents.items():
                num = f" ({doc.doc_number})" if doc.doc_number else ""
                lines.append(f"  • {doc_type.value}{num}")
        else:
            lines.append("  (none)")
        
        lines.append("")
        
        missing = self.missing_docs
        if missing:
            lines.append("❌ Missing Documents:")
            for doc in missing:
                lines.append(f"  • {doc}")
        else:
            lines.append("✅ All documents received")
        
        lines.append("")
        lines.append(f"🎯 Ready to classify: {'Yes' if self.ready_to_classify else 'No'}")
        lines.append(f"📝 Ready for declaration: {'Yes' if self.ready_for_declaration else 'No'}")
        
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "shipment_id": self.shipment_id,
            "direction": self.direction,
            "transport_mode": self.transport_mode.value if self.transport_mode else None,
            "incoterms": self.incoterms.value if self.incoterms else None,
            "product_category": self.product_category.value,
            "documents": {k.value: v.to_dict() for k, v in self.documents.items()},
            "declaration_number": self.declaration_number,
            "phase": self.phase.value,
            "ready_to_classify": self.ready_to_classify,
            "ready_for_declaration": self.ready_for_declaration,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_tracker(
    shipment_id: str,
    direction: str = "import",
    transport_mode: Optional[str] = None,
    incoterms: Optional[str] = None,
    product_category: Optional[str] = None
) -> DocumentTracker:
    """
    Factory function to create a DocumentTracker.
    
    Args:
        shipment_id: Unique shipment identifier
        direction: "import" or "export"
        transport_mode: "sea_fcl", "sea_lcl", "air", "land", "courier"
        incoterms: e.g., "FOB", "CIF", "EXW"
        product_category: e.g., "chemicals", "food", "general"
    
    Returns:
        DocumentTracker instance
    
    Example:
        tracker = create_tracker(
            shipment_id="SHP-2026-001",
            direction="import",
            transport_mode="sea_fcl",
            incoterms="FOB",
            product_category="chemicals"
        )
    """
    tracker = DocumentTracker(
        shipment_id=shipment_id,
        direction=direction,
        transport_mode=TransportMode(transport_mode) if transport_mode else None
    )
    
    if incoterms:
        tracker.set_incoterms(incoterms)
    
    if product_category:
        tracker.set_product_category(product_category)
    
    return tracker


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    # Test the tracker
    print("=" * 60)
    print("RCB Document Tracker - Test")
    print("=" * 60)
    
    # Create tracker
    tracker = create_tracker(
        shipment_id="TEST-001",
        direction="import",
        transport_mode="sea_fcl",
        incoterms="FOB",
        product_category="chemicals"
    )
    
    # Add some documents
    tracker.add_document(Document(
        doc_type=DocumentType.INVOICE,
        doc_number="INV-2026-001"
    ))
    tracker.add_document(Document(
        doc_type=DocumentType.PACKING_LIST,
        doc_number="PL-2026-001"
    ))
    
    # Print status
    print(tracker.get_status_report("he"))
    print()
    print("=" * 60)
    print("Missing for classification:", tracker.missing_docs_for_classification)
    print("=" * 60)
