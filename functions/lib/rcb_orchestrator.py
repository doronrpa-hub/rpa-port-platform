"""
RCB Module 6: Orchestrator
==========================
Integration layer that connects all RCB modules together.
Orchestrates the complete shipment processing workflow.

Author: RCB System
Version: 1.0
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum
from datetime import datetime

# Import other modules
try:
    from .invoice_validator import validate_invoice, InvoiceValidationResult, FIELD_DEFINITIONS
    from .clarification_generator import (
        generate_missing_docs_request,
        generate_classification_request,
        generate_cif_completion_request,
        generate_origin_request,
        ClarificationRequest,
        DocumentType,
        UrgencyLevel,
    )
except ImportError:
    # For standalone testing
    from invoice_validator import validate_invoice, InvoiceValidationResult, FIELD_DEFINITIONS
    from clarification_generator import (
        generate_missing_docs_request,
        generate_classification_request,
        generate_cif_completion_request,
        generate_origin_request,
        ClarificationRequest,
        DocumentType,
        UrgencyLevel,
    )


class ShipmentStage(Enum):
    """Stages in shipment processing"""
    RECEIVED = "received"
    VALIDATING = "validating"
    AWAITING_RESPONSE = "awaiting_response"
    CALCULATING_CIF = "calculating_cif"
    CLASSIFYING = "classifying"
    READY_FOR_DECLARATION = "ready"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessingAction(Enum):
    """Actions to take during processing"""
    CONTINUE = "continue"
    SEND_CLARIFICATION = "send_clarification"
    WAIT = "wait"
    MANUAL_REVIEW = "manual_review"
    COMPLETE = "complete"


@dataclass
class ShipmentStatus:
    """Status of a shipment being processed"""
    shipment_id: str
    stage: ShipmentStage
    invoice_validation: Optional[InvoiceValidationResult] = None
    clarification_request: Optional[ClarificationRequest] = None
    cif_calculated: bool = False
    cif_value: Optional[float] = None
    classification_complete: bool = False
    hs_codes: List[str] = field(default_factory=list)
    next_action: ProcessingAction = ProcessingAction.CONTINUE
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def summary_he(self) -> str:
        """Generate Hebrew status summary"""
        stage_names = {
            ShipmentStage.RECEIVED: "📥 התקבל",
            ShipmentStage.VALIDATING: "🔍 בבדיקה",
            ShipmentStage.AWAITING_RESPONSE: "⏳ ממתין לתגובה",
            ShipmentStage.CALCULATING_CIF: "🧮 מחשב CIF",
            ShipmentStage.CLASSIFYING: "🏷️ מסווג",
            ShipmentStage.READY_FOR_DECLARATION: "✅ מוכן להצהרה",
            ShipmentStage.COMPLETED: "✅ הושלם",
            ShipmentStage.ERROR: "❌ שגיאה",
        }
        
        lines = [f"משלוח: {self.shipment_id}"]
        lines.append(f"סטטוס: {stage_names.get(self.stage, self.stage.value)}")
        
        if self.invoice_validation:
            status = "תקין" if self.invoice_validation.is_valid else "לא שלם"
            lines.append(f"חשבון: {status} ({self.invoice_validation.score}/100)")
            if self.invoice_validation.missing_fields:
                lines.append(f"שדות חסרים: {len(self.invoice_validation.missing_fields)}")
        
        if self.cif_calculated and self.cif_value:
            lines.append(f"ערך CIF: ${self.cif_value:,.2f}")
        
        if self.classification_complete and self.hs_codes:
            lines.append(f"קודי HS: {', '.join(self.hs_codes)}")
        
        action_names = {
            ProcessingAction.CONTINUE: "המשך עיבוד",
            ProcessingAction.SEND_CLARIFICATION: "שלח בקשה להשלמת מידע",
            ProcessingAction.WAIT: "המתן לתגובה",
            ProcessingAction.MANUAL_REVIEW: "נדרשת בדיקה ידנית",
            ProcessingAction.COMPLETE: "הושלם",
        }
        lines.append(f"פעולה הבאה: {action_names.get(self.next_action, self.next_action.value)}")
        
        if self.errors:
            lines.append(f"שגיאות: {len(self.errors)}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        return {
            "shipment_id": self.shipment_id,
            "stage": self.stage.value,
            "invoice_valid": self.invoice_validation.is_valid if self.invoice_validation else None,
            "invoice_score": self.invoice_validation.score if self.invoice_validation else None,
            "cif_calculated": self.cif_calculated,
            "cif_value": self.cif_value,
            "classification_complete": self.classification_complete,
            "hs_codes": self.hs_codes,
            "next_action": self.next_action.value,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class RCBOrchestrator:
    """
    Main orchestrator that coordinates all RCB modules.
    
    Workflow:
    1. Receive shipment documents
    2. Validate invoice (Module 5)
    3. If invalid, generate clarification request (Module 4)
    4. Calculate CIF value
    5. Classify products
    6. Generate final report
    """
    
    def __init__(self, sender_name: str = "מערכת RCB"):
        self.sender_name = sender_name
        self.statuses: Dict[str, ShipmentStatus] = {}
    
    def process_shipment(
        self,
        shipment_id: str,
        invoice_data: Dict[str, Any],
        recipient_name: str = "לקוח/ה יקר/ה",
        recipient_email: Optional[str] = None,
    ) -> ShipmentStatus:
        """
        Process a shipment through the complete workflow.
        
        Args:
            shipment_id: Unique identifier for the shipment
            invoice_data: Dictionary containing invoice fields
            recipient_name: Name for addressing clarification requests
            recipient_email: Email for sending requests
            
        Returns:
            ShipmentStatus with current stage and next actions
        """
        # Create or update status
        status = ShipmentStatus(
            shipment_id=shipment_id,
            stage=ShipmentStage.VALIDATING,
        )
        
        # Step 1: Validate Invoice
        try:
            validation = validate_invoice(invoice_data)
            status.invoice_validation = validation
            
            if not validation.is_valid:
                # Generate clarification request
                status.stage = ShipmentStage.AWAITING_RESPONSE
                status.next_action = ProcessingAction.SEND_CLARIFICATION
                
                # Determine what kind of clarification is needed
                missing_docs = self._map_fields_to_docs(validation.missing_fields)
                
                if missing_docs:
                    status.clarification_request = generate_missing_docs_request(
                        missing_docs=missing_docs,
                        invoice_number=invoice_data.get("invoice_number") or invoice_data.get("date"),
                        supplier_name=invoice_data.get("seller") or invoice_data.get("supplier"),
                        recipient_name=recipient_name,
                        urgency=UrgencyLevel.HIGH if validation.score < 50 else UrgencyLevel.MEDIUM,
                        sender_name=self.sender_name,
                    )
            else:
                # Invoice is valid, continue processing
                status.stage = ShipmentStage.CALCULATING_CIF
                status.next_action = ProcessingAction.CONTINUE
                
        except Exception as e:
            status.stage = ShipmentStage.ERROR
            status.errors.append(f"Validation error: {str(e)}")
            status.next_action = ProcessingAction.MANUAL_REVIEW
        
        status.updated_at = datetime.now()
        self.statuses[shipment_id] = status
        return status
    
    def _map_fields_to_docs(self, missing_fields: List) -> List[DocumentType]:
        """Map missing invoice fields to document types"""
        docs = []
        field_to_doc = {
            "origin": DocumentType.CERTIFICATE_OF_ORIGIN,
            "packages": DocumentType.PACKING_LIST,
            "weights": DocumentType.PACKING_LIST,
            "terms": DocumentType.INVOICE,
            "price": DocumentType.INVOICE,
            "description": DocumentType.INVOICE,
        }
        
        for field in missing_fields:
            field_name = field.value if hasattr(field, 'value') else str(field)
            if field_name in field_to_doc:
                doc = field_to_doc[field_name]
                if doc not in docs:
                    docs.append(doc)
        
        return docs
    
    def quick_check(
        self,
        shipment_id: str,
        invoice_data: Dict[str, Any],
    ) -> ShipmentStatus:
        """Quick validation check without full processing"""
        status = ShipmentStatus(
            shipment_id=shipment_id,
            stage=ShipmentStage.VALIDATING,
        )
        
        validation = validate_invoice(invoice_data)
        status.invoice_validation = validation
        
        if validation.is_valid:
            status.stage = ShipmentStage.READY_FOR_DECLARATION
            status.next_action = ProcessingAction.CONTINUE
        else:
            status.stage = ShipmentStage.AWAITING_RESPONSE
            status.next_action = ProcessingAction.SEND_CLARIFICATION
        
        return status
    
    def get_status(self, shipment_id: str) -> Optional[ShipmentStatus]:
        """Get current status of a shipment"""
        return self.statuses.get(shipment_id)
    
    def process_response(
        self,
        shipment_id: str,
        additional_data: Dict[str, Any],
    ) -> ShipmentStatus:
        """Process a response to a clarification request"""
        status = self.statuses.get(shipment_id)
        if not status:
            return ShipmentStatus(
                shipment_id=shipment_id,
                stage=ShipmentStage.ERROR,
                errors=["Shipment not found"],
            )
        
        # Merge new data and re-validate
        # This would integrate with the original invoice data
        # For now, just update status
        status.stage = ShipmentStage.VALIDATING
        status.updated_at = datetime.now()
        
        return status


def create_orchestrator(sender_name: str = "מערכת RCB") -> RCBOrchestrator:
    """Factory function to create an orchestrator"""
    return RCBOrchestrator(sender_name=sender_name)


def process_and_respond(
    shipment_id: str,
    invoice_data: Dict[str, Any],
    recipient_name: str = "לקוח/ה יקר/ה",
) -> Dict[str, Any]:
    """
    Quick helper to process and get response in one call.
    
    Returns dict with:
    - status: "complete" | "needs_clarification" | "error"
    - message: Hebrew message
    - clarification: Optional clarification request details
    """
    orchestrator = create_orchestrator()
    result = orchestrator.process_shipment(shipment_id, invoice_data, recipient_name)
    
    response = {
        "status": "complete" if result.invoice_validation and result.invoice_validation.is_valid else "needs_clarification",
        "message": result.summary_he(),
        "score": result.invoice_validation.score if result.invoice_validation else 0,
    }
    
    if result.clarification_request:
        response["clarification"] = {
            "subject": result.clarification_request.subject,
            "body": result.clarification_request.body,
        }
    
    if result.errors:
        response["status"] = "error"
        response["errors"] = result.errors
    
    return response


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("RCB Orchestrator - Integration Test")
    print("=" * 60)
    
    orchestrator = create_orchestrator(sender_name="דורון")
    
    # Test 1: Complete invoice
    print("\n📦 Test 1: Complete Invoice")
    print("-" * 40)
    
    complete_invoice = {
        "invoice_number": "TEST-2026-001",
        "origin": "China",
        "date": "2026-02-01",
        "place": "Shanghai",
        "seller": "ABC Trading Co.",
        "buyer": "XYZ Import Ltd",
        "packages": "10 cartons",
        "description": "Electronic components",
        "quantity": "1000 pcs",
        "weight_gross": "500 kg",
        "weight_net": "450 kg",
        "price": "USD 10,000",
        "terms": "FOB Shanghai",
    }
    
    result = orchestrator.process_shipment("TEST-2026-001", complete_invoice)
    print(result.summary_he())
    print(f"Stage: {result.stage.value}")
    
    # Test 2: Incomplete invoice
    print("\n" + "=" * 60)
    print("📦 Test 2: Incomplete Invoice (with clarification)")
    print("-" * 40)
    
    incomplete_invoice = {
        "invoice_number": "TEST-2026-002",
        "date": "2026-02-01",
        "seller": "ABC Trading Co.",
        "description": "Electronic parts",
        "price": "USD 5,000",
    }
    
    result = orchestrator.process_shipment(
        "TEST-2026-002",
        incomplete_invoice,
        recipient_name="לקוח יקר",
    )
    print(result.summary_he())
    print(f"Stage: {result.stage.value}")
    
    if result.clarification_request:
        print("\n📧 Clarification Request:")
        print(f"Subject: {result.clarification_request.subject}")
        print(f"Body preview: {result.clarification_request.body[:300]}...")
    
    # Test 3: Quick check
    print("\n" + "=" * 60)
    print("📦 Test 3: Quick Check")
    print("-" * 40)
    
    quick_result = orchestrator.quick_check("quick-check", {"price": "100", "description": "test"})
    print(f"Valid: {quick_result.invoice_validation.is_valid if quick_result.invoice_validation else 'N/A'}")
    print(quick_result.summary_he())
    
    # Test 4: Process and respond (API style)
    print("\n" + "=" * 60)
    print("📦 Test 4: Process and Respond (API style)")
    print("-" * 40)
    
    api_response = process_and_respond(
        "api-test-001",
        complete_invoice,
    )
    print(f"Status: {api_response['status']}")
    print(f"Message: {api_response['message']}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
