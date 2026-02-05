"""
RCB Orchestrator - Integration Layer
=====================================
Connects all RCB modules into a unified processing pipeline.

File: functions/lib/rcb_orchestrator.py
Project: RCB (Robotic Customs Bot)
Session: 10

Pipeline:
1. Document arrives (email/upload)
2. Validate invoice fields (invoice_validator)
3. If missing → generate request (clarification_generator)
4. Extract values → calculate CIF (incoterms_calculator)
5. Classify products (product_classifier / classification_agents)
6. Track status (document_tracker)
7. Generate reports (pdf_creator)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback

# =============================================================================
# IMPORTS - All RCB Modules
# =============================================================================

# These will be imported when the module is used in the main project
# For standalone testing, we'll handle import errors gracefully

def safe_import(module_name: str, class_names: List[str]) -> Dict:
    """Safely import modules, return empty dict if not found"""
    try:
        module = __import__(f"lib.{module_name}", fromlist=class_names)
        return {name: getattr(module, name, None) for name in class_names}
    except ImportError:
        try:
            module = __import__(module_name, fromlist=class_names)
            return {name: getattr(module, name, None) for name in class_names}
        except ImportError:
            return {name: None for name in class_names}


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ProcessingStage(Enum):
    """Stages in the RCB processing pipeline"""
    RECEIVED = "received"                    # קיבלנו
    VALIDATING = "validating"                # בבדיקה
    MISSING_INFO = "missing_info"            # חסר מידע
    AWAITING_RESPONSE = "awaiting_response"  # ממתין לתגובה
    CLASSIFYING = "classifying"              # בסיווג
    CALCULATING = "calculating"              # בחישוב
    READY = "ready"                          # מוכן לשחרור
    COMPLETED = "completed"                  # הושלם
    ERROR = "error"                          # שגיאה


class DocumentType(Enum):
    """Types of customs documents"""
    INVOICE = "invoice"
    PACKING_LIST = "packing_list"
    BILL_OF_LADING = "bill_of_lading"
    AWB = "awb"
    CERTIFICATE_ORIGIN = "certificate_origin"
    MSDS = "msds"
    OTHER = "other"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ShipmentFile:
    """A single file in a shipment"""
    filename: str
    doc_type: DocumentType
    storage_path: str
    extracted_text: Optional[str] = None
    extracted_data: Dict = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of processing a shipment"""
    shipment_id: str
    stage: ProcessingStage
    invoice_valid: bool = False
    invoice_score: float = 0.0
    missing_fields: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_request: Optional[Dict] = None
    cif_value: Optional[float] = None
    classification: Optional[Dict] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    next_action: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "shipment_id": self.shipment_id,
            "stage": self.stage.value,
            "invoice_valid": self.invoice_valid,
            "invoice_score": self.invoice_score,
            "missing_fields": self.missing_fields,
            "clarification_needed": self.clarification_needed,
            "clarification_request": self.clarification_request,
            "cif_value": self.cif_value,
            "classification": self.classification,
            "errors": self.errors,
            "warnings": self.warnings,
            "next_action": self.next_action,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def summary_he(self) -> str:
        """Hebrew summary"""
        stage_names = {
            ProcessingStage.RECEIVED: "📥 התקבל",
            ProcessingStage.VALIDATING: "🔍 בבדיקה",
            ProcessingStage.MISSING_INFO: "⚠️ חסר מידע",
            ProcessingStage.AWAITING_RESPONSE: "⏳ ממתין לתגובה",
            ProcessingStage.CLASSIFYING: "🏷️ בסיווג",
            ProcessingStage.CALCULATING: "🧮 בחישוב",
            ProcessingStage.READY: "✅ מוכן לשחרור",
            ProcessingStage.COMPLETED: "🎉 הושלם",
            ProcessingStage.ERROR: "❌ שגיאה",
        }
        
        lines = [f"משלוח: {self.shipment_id}"]
        lines.append(f"סטטוס: {stage_names.get(self.stage, self.stage.value)}")
        lines.append(f"חשבון: {'תקין' if self.invoice_valid else 'לא שלם'} ({self.invoice_score:.0f}/100)")
        
        if self.missing_fields:
            lines.append(f"שדות חסרים: {len(self.missing_fields)}")
        
        if self.cif_value:
            lines.append(f"ערך CIF: ${self.cif_value:,.2f}")
        
        if self.next_action:
            lines.append(f"פעולה הבאה: {self.next_action}")
        
        return "\n".join(lines)


# =============================================================================
# ORCHESTRATOR CLASS
# =============================================================================

class RCBOrchestrator:
    """
    Main orchestrator that coordinates all RCB modules.
    
    Usage:
        orchestrator = RCBOrchestrator()
        result = orchestrator.process_shipment(shipment_data)
        print(result.summary_he())
    """
    
    def __init__(self, sender_name: str = "מערכת RCB", company_name: str = "ר.פ.א - פורט בע\"מ"):
        self.sender_name = sender_name
        self.company_name = company_name
        
        # Load modules
        self._load_modules()
    
    def _load_modules(self):
        """Load all RCB modules"""
        # Invoice Validator
        iv = safe_import("invoice_validator", ["validate_invoice", "get_missing_fields_request", "InvoiceField"])
        self.validate_invoice = iv.get("validate_invoice")
        self.get_missing_fields_request = iv.get("get_missing_fields_request")
        
        # Clarification Generator
        cg = safe_import("clarification_generator", [
            "create_generator", "generate_missing_docs_request", "generate_origin_request",
            "ShipmentInfo", "UrgencyLevel"
        ])
        self.create_generator = cg.get("create_generator")
        self.generate_missing_docs_request = cg.get("generate_missing_docs_request")
        self.generate_origin_request = cg.get("generate_origin_request")
        self.ShipmentInfo = cg.get("ShipmentInfo")
        self.UrgencyLevel = cg.get("UrgencyLevel")
        
        # Incoterms Calculator
        ic = safe_import("incoterms_calculator", ["calculate_cif", "IncotermsCalculator"])
        self.calculate_cif = ic.get("calculate_cif")
        self.IncotermsCalculator = ic.get("IncotermsCalculator")
        
        # Product Classifier
        pc = safe_import("product_classifier", ["classify_product", "ProductClassifier"])
        self.classify_product = pc.get("classify_product")
        
        # Document Tracker
        dt = safe_import("document_tracker", ["DocumentTracker", "track_document"])
        self.DocumentTracker = dt.get("DocumentTracker")
    
    # -------------------------------------------------------------------------
    # Main Processing Pipeline
    # -------------------------------------------------------------------------
    
    def process_shipment(
        self,
        shipment_id: str,
        invoice_data: Dict,
        files: Optional[List[ShipmentFile]] = None,
        auto_send_clarification: bool = False,
    ) -> ProcessingResult:
        """
        Process a complete shipment through all stages.
        
        Args:
            shipment_id: Unique shipment identifier
            invoice_data: Extracted invoice data dictionary
            files: List of shipment files
            auto_send_clarification: If True, prepare clarification emails
        
        Returns:
            ProcessingResult with complete status
        """
        result = ProcessingResult(
            shipment_id=shipment_id,
            stage=ProcessingStage.VALIDATING,
        )
        
        try:
            # Stage 1: Validate Invoice
            result = self._stage_validate_invoice(result, invoice_data)
            
            # Stage 2: If missing info, generate clarification
            if not result.invoice_valid and auto_send_clarification:
                result = self._stage_generate_clarification(result, invoice_data)
            
            # Stage 3: Calculate CIF (if we have enough data)
            if result.invoice_score >= 60:  # At least 60% complete
                result = self._stage_calculate_cif(result, invoice_data)
            
            # Stage 4: Classify products (if we have description)
            if "description" in invoice_data or "goods" in invoice_data:
                result = self._stage_classify(result, invoice_data)
            
            # Determine final stage
            result = self._determine_final_stage(result)
            
        except Exception as e:
            result.stage = ProcessingStage.ERROR
            result.errors.append(f"Processing error: {str(e)}")
            result.errors.append(traceback.format_exc())
        
        return result
    
    # -------------------------------------------------------------------------
    # Pipeline Stages
    # -------------------------------------------------------------------------
    
    def _stage_validate_invoice(self, result: ProcessingResult, invoice_data: Dict) -> ProcessingResult:
        """Stage 1: Validate invoice fields"""
        if not self.validate_invoice:
            result.warnings.append("Invoice validator not available")
            return result
        
        validation = self.validate_invoice(invoice_data)
        result.invoice_valid = validation.is_valid
        result.invoice_score = validation.score
        result.missing_fields = [f.value for f in validation.missing_fields]
        result.warnings.extend(validation.warnings)
        
        if not validation.is_valid:
            result.stage = ProcessingStage.MISSING_INFO
        
        return result
    
    def _stage_generate_clarification(self, result: ProcessingResult, invoice_data: Dict) -> ProcessingResult:
        """Stage 2: Generate clarification request if needed"""
        result.clarification_needed = True
        
        if self.get_missing_fields_request and hasattr(result, '_validation_result'):
            # Use invoice validator's built-in request
            result.clarification_request = {
                "type": "invoice_fields",
                "body": self.get_missing_fields_request(result._validation_result),
            }
        elif self.create_generator:
            # Use clarification generator
            gen = self.create_generator(self.sender_name, self.company_name)
            
            # Map missing fields to document types
            missing_docs = self._map_fields_to_docs(result.missing_fields)
            
            if missing_docs and self.ShipmentInfo:
                shipment_info = self.ShipmentInfo(
                    invoice_number=invoice_data.get("invoice_number", invoice_data.get("date", "")),
                    supplier_name=invoice_data.get("seller", invoice_data.get("supplier", "")),
                    goods_description=invoice_data.get("description", invoice_data.get("goods", "")),
                )
                
                urgency = self.UrgencyLevel.MEDIUM if self.UrgencyLevel else None
                
                request = gen.generate_missing_document_request(
                    missing_docs=missing_docs,
                    shipment_info=shipment_info,
                    urgency=urgency,
                )
                
                result.clarification_request = {
                    "type": request.request_type.value,
                    "subject": request.subject,
                    "body": request.body,
                    "missing_items": request.missing_items,
                }
        
        result.stage = ProcessingStage.AWAITING_RESPONSE
        result.next_action = "שלח בקשה להשלמת מידע ללקוח"
        
        return result
    
    def _stage_calculate_cif(self, result: ProcessingResult, invoice_data: Dict) -> ProcessingResult:
        """Stage 3: Calculate CIF value"""
        result.stage = ProcessingStage.CALCULATING
        
        if not self.calculate_cif:
            result.warnings.append("CIF calculator not available")
            return result
        
        try:
            # Extract values from invoice data
            goods_value = self._extract_numeric(invoice_data.get("price", invoice_data.get("value", 0)))
            freight = self._extract_numeric(invoice_data.get("freight", 0))
            insurance = self._extract_numeric(invoice_data.get("insurance", 0))
            incoterms = invoice_data.get("terms", invoice_data.get("incoterms", "FOB"))
            
            if goods_value > 0:
                cif_result = self.calculate_cif(
                    goods_value=goods_value,
                    freight=freight if freight > 0 else None,
                    insurance=insurance if insurance > 0 else None,
                    incoterms=incoterms,
                )
                
                if hasattr(cif_result, 'cif_value'):
                    result.cif_value = cif_result.cif_value
                elif isinstance(cif_result, (int, float)):
                    result.cif_value = float(cif_result)
                elif isinstance(cif_result, dict):
                    result.cif_value = cif_result.get("cif_value", cif_result.get("total"))
        
        except Exception as e:
            result.warnings.append(f"CIF calculation issue: {str(e)}")
        
        return result
    
    def _stage_classify(self, result: ProcessingResult, invoice_data: Dict) -> ProcessingResult:
        """Stage 4: Classify products"""
        result.stage = ProcessingStage.CLASSIFYING
        
        if not self.classify_product:
            result.warnings.append("Product classifier not available")
            return result
        
        try:
            description = invoice_data.get("description", invoice_data.get("goods", ""))
            
            if description:
                classification = self.classify_product(description)
                
                if classification:
                    if hasattr(classification, 'to_dict'):
                        result.classification = classification.to_dict()
                    elif isinstance(classification, dict):
                        result.classification = classification
                    else:
                        result.classification = {"result": str(classification)}
        
        except Exception as e:
            result.warnings.append(f"Classification issue: {str(e)}")
        
        return result
    
    def _determine_final_stage(self, result: ProcessingResult) -> ProcessingResult:
        """Determine the final processing stage"""
        if result.errors:
            result.stage = ProcessingStage.ERROR
            result.next_action = "בדוק שגיאות ונסה שוב"
        elif result.clarification_needed:
            result.stage = ProcessingStage.AWAITING_RESPONSE
            result.next_action = "שלח בקשה להשלמת מידע"
        elif not result.invoice_valid:
            result.stage = ProcessingStage.MISSING_INFO
            result.next_action = "השלם פרטים חסרים"
        elif result.classification and result.cif_value:
            result.stage = ProcessingStage.READY
            result.next_action = "מוכן להגשת רשימון"
        else:
            result.stage = ProcessingStage.VALIDATING
            result.next_action = "המשך עיבוד"
        
        return result
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _map_fields_to_docs(self, missing_fields: List[str]) -> List[str]:
        """Map missing invoice fields to document type codes"""
        field_to_doc = {
            "origin": "cert_of_origin",
            "packages": "packing_list",
            "weights": "packing_list",
            "terms": "invoice",
            "price": "invoice",
            "quantity": "invoice",
            "goods_description": "invoice",
        }
        
        docs = set()
        for f in missing_fields:
            if f in field_to_doc:
                docs.add(field_to_doc[f])
        
        return list(docs) if docs else ["invoice"]
    
    def _extract_numeric(self, value: Any) -> float:
        """Extract numeric value from string or number"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = value.replace("$", "").replace("USD", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0
    
    # -------------------------------------------------------------------------
    # Quick Processing Methods
    # -------------------------------------------------------------------------
    
    def quick_validate(self, invoice_data: Dict) -> Tuple[bool, str]:
        """
        Quick validation - returns (is_valid, hebrew_summary)
        
        Example:
            valid, summary = orchestrator.quick_validate(data)
            if not valid:
                print(summary)
        """
        result = self.process_shipment(
            shipment_id="quick-check",
            invoice_data=invoice_data,
            auto_send_clarification=False,
        )
        return result.invoice_valid, result.summary_he()
    
    def process_and_respond(self, shipment_id: str, invoice_data: Dict) -> Dict:
        """
        Process and generate response ready for email/API.
        
        Returns dict with:
        - status: "complete" | "needs_info" | "error"
        - message_he: Hebrew message
        - clarification: Clarification request if needed
        - data: Full result data
        """
        result = self.process_shipment(
            shipment_id=shipment_id,
            invoice_data=invoice_data,
            auto_send_clarification=True,
        )
        
        if result.errors:
            status = "error"
            message = "❌ אירעה שגיאה בעיבוד"
        elif result.clarification_needed:
            status = "needs_info"
            message = "⚠️ נדרש מידע נוסף להמשך הטיפול"
        elif result.invoice_valid:
            status = "complete"
            message = "✅ המסמכים תקינים"
        else:
            status = "needs_info"
            message = "⚠️ חסרים פרטים בחשבון המכר"
        
        return {
            "status": status,
            "message_he": message,
            "summary_he": result.summary_he(),
            "clarification": result.clarification_request,
            "data": result.to_dict(),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_orchestrator(
    sender_name: str = "מערכת RCB",
    company_name: str = "ר.פ.א - פורט בע\"מ"
) -> RCBOrchestrator:
    """Create an RCB Orchestrator instance"""
    return RCBOrchestrator(sender_name=sender_name, company_name=company_name)


def process_shipment(shipment_id: str, invoice_data: Dict) -> ProcessingResult:
    """Quick function to process a shipment"""
    orchestrator = RCBOrchestrator()
    return orchestrator.process_shipment(shipment_id, invoice_data)


def quick_check(invoice_data: Dict) -> Tuple[bool, str]:
    """Quick validation check"""
    orchestrator = RCBOrchestrator()
    return orchestrator.quick_validate(invoice_data)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Orchestrator - Integration Test")
    print("=" * 60)
    
    orchestrator = create_orchestrator(
        sender_name="דורון",
        company_name="ר.פ.א - פורט בע\"מ"
    )
    
    # Test 1: Complete invoice
    print("\n📦 Test 1: Complete Invoice")
    print("-" * 40)
    
    complete_data = {
        "origin": "China",
        "date": "2026-02-01",
        "seller": "XUZHOU DRAGON GUAR CO., LTD",
        "buyer": "RPA Port Ltd, Israel",
        "packages": "10 cartons, marks: DG-2026",
        "description": "Machine parts for anti-scaling system",
        "quantity": "100 pcs",
        "weight": "Gross: 520 kg, Net: 480 kg",
        "price": "USD 10,000.00",
        "terms": "FOB Shanghai",
        "freight": "USD 1,200",
        "insurance": "USD 50",
    }
    
    result = orchestrator.process_shipment(
        shipment_id="TEST-2026-001",
        invoice_data=complete_data,
    )
    
    print(result.summary_he())
    print(f"\nStage: {result.stage.value}")
    
    # Test 2: Incomplete invoice
    print("\n" + "=" * 60)
    print("📦 Test 2: Incomplete Invoice (with clarification)")
    print("-" * 40)
    
    incomplete_data = {
        "date": "2026-02-01",
        "seller": "Some Supplier",
        "description": "Electronic components",
        "price": "USD 5,000",
    }
    
    result = orchestrator.process_shipment(
        shipment_id="TEST-2026-002",
        invoice_data=incomplete_data,
        auto_send_clarification=True,
    )
    
    print(result.summary_he())
    print(f"\nStage: {result.stage.value}")
    
    if result.clarification_request:
        print("\n📧 Clarification Request:")
        print(f"Subject: {result.clarification_request.get('subject', 'N/A')}")
        print(f"Body preview: {result.clarification_request.get('body', 'N/A')[:200]}...")
    
    # Test 3: Quick check
    print("\n" + "=" * 60)
    print("📦 Test 3: Quick Check")
    print("-" * 40)
    
    valid, summary = quick_check({"origin": "Germany", "price": "1000 EUR"})
    print(f"Valid: {valid}")
    print(summary)
    
    # Test 4: Process and respond (API-style)
    print("\n" + "=" * 60)
    print("📦 Test 4: Process and Respond (API style)")
    print("-" * 40)
    
    response = orchestrator.process_and_respond(
        shipment_id="API-TEST-001",
        invoice_data=complete_data,
    )
    
    print(f"Status: {response['status']}")
    print(f"Message: {response['message_he']}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
