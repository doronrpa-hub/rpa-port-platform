"""
RCB Incoterms CIF Calculator
Calculates CIF value components based on Incoterms and determines missing documents.

File: functions/lib/incoterms_calculator.py
Project: RCB (Robotic Customs Bot)
Session: 9
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP


# =============================================================================
# ENUMS
# =============================================================================

class Incoterm(Enum):
    """Incoterms 2020 - International Commercial Terms"""
    # Group E - Departure
    EXW = "EXW"  # Ex Works
    
    # Group F - Main Carriage Unpaid
    FCA = "FCA"  # Free Carrier
    FAS = "FAS"  # Free Alongside Ship
    FOB = "FOB"  # Free On Board
    
    # Group C - Main Carriage Paid
    CFR = "CFR"  # Cost and Freight
    CIF = "CIF"  # Cost, Insurance and Freight
    CPT = "CPT"  # Carriage Paid To
    CIP = "CIP"  # Carriage and Insurance Paid To
    
    # Group D - Arrival
    DAP = "DAP"  # Delivered at Place
    DPU = "DPU"  # Delivered at Place Unloaded
    DDP = "DDP"  # Delivered Duty Paid


class TransportType(Enum):
    """Transport types for Incoterms applicability"""
    ANY = "any"          # Any mode of transport
    SEA_ONLY = "sea"     # Sea and inland waterway only


# =============================================================================
# INCOTERMS DATA
# =============================================================================

INCOTERMS_DATA = {
    Incoterm.EXW: {
        "name_en": "Ex Works",
        "name_he": "מחיר במפעל",
        "description_en": "Seller makes goods available at their premises. Buyer bears all costs and risks.",
        "description_he": "המוכר מעמיד את הסחורה לרשות הקונה במפעלו. הקונה נושא בכל העלויות והסיכונים.",
        "transport": TransportType.ANY,
        "includes_freight": False,
        "includes_insurance": False,
        "includes_export_customs": False,
        "includes_import_customs": False,
        "risk_transfer": "At seller's premises",
        "risk_transfer_he": "במפעל המוכר",
    },
    Incoterm.FCA: {
        "name_en": "Free Carrier",
        "name_he": "מסור למוביל",
        "description_en": "Seller delivers goods to carrier nominated by buyer. Seller clears for export.",
        "description_he": "המוכר מוסר את הסחורה למוביל שמינה הקונה. המוכר מבצע עמילות יצוא.",
        "transport": TransportType.ANY,
        "includes_freight": False,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "When delivered to carrier",
        "risk_transfer_he": "עם מסירה למוביל",
    },
    Incoterm.FAS: {
        "name_en": "Free Alongside Ship",
        "name_he": "מסור לאורך דופן האונייה",
        "description_en": "Seller delivers goods alongside the vessel at port of shipment.",
        "description_he": "המוכר מוסר את הסחורה לאורך דופן האונייה בנמל המוצא.",
        "transport": TransportType.SEA_ONLY,
        "includes_freight": False,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "Alongside ship at port",
        "risk_transfer_he": "לאורך האונייה בנמל",
    },
    Incoterm.FOB: {
        "name_en": "Free On Board",
        "name_he": "מסור על סיפון האונייה",
        "description_en": "Seller delivers goods on board the vessel. Risk transfers when goods are on board.",
        "description_he": "המוכר מוסר את הסחורה על סיפון האונייה. הסיכון עובר עם העלאת הסחורה לאונייה.",
        "transport": TransportType.SEA_ONLY,
        "includes_freight": False,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "On board vessel",
        "risk_transfer_he": "על סיפון האונייה",
    },
    Incoterm.CFR: {
        "name_en": "Cost and Freight",
        "name_he": "עלות והובלה",
        "description_en": "Seller pays freight to destination port. Risk transfers when goods are on board.",
        "description_he": "המוכר משלם את ההובלה עד נמל היעד. הסיכון עובר עם העלאת הסחורה לאונייה.",
        "transport": TransportType.SEA_ONLY,
        "includes_freight": True,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "On board vessel",
        "risk_transfer_he": "על סיפון האונייה",
    },
    Incoterm.CIF: {
        "name_en": "Cost, Insurance and Freight",
        "name_he": "עלות, ביטוח והובלה",
        "description_en": "Seller pays freight and insurance to destination port. Risk transfers on board.",
        "description_he": "המוכר משלם הובלה וביטוח עד נמל היעד. הסיכון עובר עם העלאת הסחורה לאונייה.",
        "transport": TransportType.SEA_ONLY,
        "includes_freight": True,
        "includes_insurance": True,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "On board vessel",
        "risk_transfer_he": "על סיפון האונייה",
    },
    Incoterm.CPT: {
        "name_en": "Carriage Paid To",
        "name_he": "הובלה משולמת עד",
        "description_en": "Seller pays freight to destination. Risk transfers when goods delivered to first carrier.",
        "description_he": "המוכר משלם את ההובלה עד היעד. הסיכון עובר עם מסירה למוביל הראשון.",
        "transport": TransportType.ANY,
        "includes_freight": True,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "When delivered to first carrier",
        "risk_transfer_he": "עם מסירה למוביל הראשון",
    },
    Incoterm.CIP: {
        "name_en": "Carriage and Insurance Paid To",
        "name_he": "הובלה וביטוח משולמים עד",
        "description_en": "Seller pays freight and insurance to destination. Risk transfers at first carrier.",
        "description_he": "המוכר משלם הובלה וביטוח עד היעד. הסיכון עובר עם מסירה למוביל הראשון.",
        "transport": TransportType.ANY,
        "includes_freight": True,
        "includes_insurance": True,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "When delivered to first carrier",
        "risk_transfer_he": "עם מסירה למוביל הראשון",
    },
    Incoterm.DAP: {
        "name_en": "Delivered at Place",
        "name_he": "מסור במקום",
        "description_en": "Seller delivers goods at named place, ready for unloading. Buyer handles import.",
        "description_he": "המוכר מוסר את הסחורה במקום הנקוב, מוכנה לפריקה. הקונה מטפל ביבוא.",
        "transport": TransportType.ANY,
        "includes_freight": True,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "At named place of destination",
        "risk_transfer_he": "במקום היעד הנקוב",
    },
    Incoterm.DPU: {
        "name_en": "Delivered at Place Unloaded",
        "name_he": "מסור במקום פרוק",
        "description_en": "Seller delivers goods unloaded at named place. Buyer handles import.",
        "description_he": "המוכר מוסר את הסחורה פרוקה במקום הנקוב. הקונה מטפל ביבוא.",
        "transport": TransportType.ANY,
        "includes_freight": True,
        "includes_insurance": False,
        "includes_export_customs": True,
        "includes_import_customs": False,
        "risk_transfer": "At named place, unloaded",
        "risk_transfer_he": "במקום היעד, פרוק",
    },
    Incoterm.DDP: {
        "name_en": "Delivered Duty Paid",
        "name_he": "מסור מושלם",
        "description_en": "Seller delivers goods cleared for import at destination. Maximum seller obligation.",
        "description_he": "המוכר מוסר את הסחורה מעומלסת ליבוא ביעד. חובה מקסימלית של המוכר.",
        "transport": TransportType.ANY,
        "includes_freight": True,
        "includes_insurance": True,
        "includes_export_customs": True,
        "includes_import_customs": True,
        "risk_transfer": "At named place of destination",
        "risk_transfer_he": "במקום היעד הנקוב",
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CIFComponents:
    """Components needed to calculate CIF value"""
    goods_value: Decimal = Decimal("0")      # C - Cost (invoice value)
    freight_value: Decimal = Decimal("0")    # F - Freight
    insurance_value: Decimal = Decimal("0")  # I - Insurance
    
    # Additional costs that may be added
    port_fees: Decimal = Decimal("0")        # אגרות נמל
    handling_fees: Decimal = Decimal("0")    # דמי טיפול
    other_costs: Decimal = Decimal("0")      # עלויות אחרות
    
    # Currency info
    currency: str = "USD"
    exchange_rate: Optional[Decimal] = None
    
    @property
    def cif_value(self) -> Decimal:
        """Calculate total CIF value"""
        return self.goods_value + self.freight_value + self.insurance_value
    
    @property
    def total_customs_value(self) -> Decimal:
        """Calculate total customs value including additional costs"""
        return self.cif_value + self.port_fees + self.handling_fees + self.other_costs
    
    @property
    def cif_value_ils(self) -> Optional[Decimal]:
        """CIF value in ILS if exchange rate is set"""
        if self.exchange_rate:
            return (self.cif_value * self.exchange_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return None
    
    def to_dict(self) -> Dict:
        return {
            "goods_value": float(self.goods_value),
            "freight_value": float(self.freight_value),
            "insurance_value": float(self.insurance_value),
            "port_fees": float(self.port_fees),
            "handling_fees": float(self.handling_fees),
            "other_costs": float(self.other_costs),
            "cif_value": float(self.cif_value),
            "total_customs_value": float(self.total_customs_value),
            "currency": self.currency,
            "exchange_rate": float(self.exchange_rate) if self.exchange_rate else None,
            "cif_value_ils": float(self.cif_value_ils) if self.cif_value_ils else None,
        }


@dataclass
class CIFCalculation:
    """Result of CIF calculation"""
    incoterm: Incoterm
    components: CIFComponents
    missing_components: List[str]
    missing_documents: List[str]
    is_complete: bool
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "incoterm": self.incoterm.value,
            "components": self.components.to_dict(),
            "missing_components": self.missing_components,
            "missing_documents": self.missing_documents,
            "is_complete": self.is_complete,
            "warnings": self.warnings,
        }
    
    def get_summary_hebrew(self) -> str:
        """Get Hebrew summary of calculation"""
        lines = []
        incoterm_data = INCOTERMS_DATA.get(self.incoterm, {})
        
        lines.append(f"📜 תנאי מכר: {self.incoterm.value} - {incoterm_data.get('name_he', '')}")
        lines.append("")
        
        lines.append("💰 מרכיבי ערך:")
        lines.append(f"  • ערך סחורה (C): {self.components.goods_value:,.2f} {self.components.currency}")
        lines.append(f"  • הובלה (F): {self.components.freight_value:,.2f} {self.components.currency}")
        lines.append(f"  • ביטוח (I): {self.components.insurance_value:,.2f} {self.components.currency}")
        lines.append(f"  ─────────────────")
        lines.append(f"  • ערך CIF: {self.components.cif_value:,.2f} {self.components.currency}")
        
        if self.components.cif_value_ils:
            lines.append(f"  • ערך CIF בש\"ח: ₪{self.components.cif_value_ils:,.2f}")
        
        if self.missing_components:
            lines.append("")
            lines.append("⚠️ מרכיבים חסרים:")
            for comp in self.missing_components:
                lines.append(f"  • {comp}")
        
        if self.missing_documents:
            lines.append("")
            lines.append("📋 מסמכים חסרים:")
            for doc in self.missing_documents:
                lines.append(f"  • {doc}")
        
        lines.append("")
        if self.is_complete:
            lines.append("✅ ערך CIF מלא - ניתן להגיש הצהרה")
        else:
            lines.append("❌ ערך CIF לא מלא - נדרשת השלמה")
        
        if self.warnings:
            lines.append("")
            lines.append("⚡ הערות:")
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        
        return "\n".join(lines)


# =============================================================================
# CALCULATOR CLASS
# =============================================================================

class IncotermsCalculator:
    """
    Calculates CIF value based on Incoterms and identifies missing components.
    
    Usage:
        calc = IncotermsCalculator()
        result = calc.calculate_cif(
            incoterm="FOB",
            goods_value=10000,
            freight_value=500,
            insurance_value=50
        )
        print(result.components.cif_value)  # 10550
        print(result.is_complete)           # True
    """
    
    def __init__(self):
        self.incoterms_data = INCOTERMS_DATA
    
    def get_incoterm_info(self, incoterm: Incoterm | str, language: str = "he") -> Dict:
        """Get information about an Incoterm"""
        if isinstance(incoterm, str):
            incoterm = Incoterm(incoterm.upper())
        
        data = self.incoterms_data.get(incoterm, {})
        
        if language == "he":
            return {
                "code": incoterm.value,
                "name": data.get("name_he", ""),
                "description": data.get("description_he", ""),
                "includes_freight": data.get("includes_freight", False),
                "includes_insurance": data.get("includes_insurance", False),
                "risk_transfer": data.get("risk_transfer_he", ""),
            }
        else:
            return {
                "code": incoterm.value,
                "name": data.get("name_en", ""),
                "description": data.get("description_en", ""),
                "includes_freight": data.get("includes_freight", False),
                "includes_insurance": data.get("includes_insurance", False),
                "risk_transfer": data.get("risk_transfer", ""),
            }
    
    def get_missing_for_cif(self, incoterm: Incoterm | str) -> Dict[str, bool]:
        """
        Get what's missing to reach CIF value based on Incoterm.
        
        Returns:
            Dict with 'freight_needed' and 'insurance_needed' booleans
        """
        if isinstance(incoterm, str):
            incoterm = Incoterm(incoterm.upper())
        
        data = self.incoterms_data.get(incoterm, {})
        
        return {
            "freight_needed": not data.get("includes_freight", False),
            "insurance_needed": not data.get("includes_insurance", False),
        }
    
    def calculate_cif(
        self,
        incoterm: Incoterm | str,
        goods_value: float,
        freight_value: Optional[float] = None,
        insurance_value: Optional[float] = None,
        currency: str = "USD",
        exchange_rate: Optional[float] = None,
        port_fees: float = 0,
        handling_fees: float = 0,
        other_costs: float = 0,
        auto_calculate_insurance: bool = True,
        insurance_rate: float = 0.003,  # 0.3% default
    ) -> CIFCalculation:
        """
        Calculate CIF value and identify missing components.
        
        Args:
            incoterm: The Incoterm (e.g., "FOB", "CIF")
            goods_value: Value of goods (C component)
            freight_value: Freight cost (F component) - None if unknown
            insurance_value: Insurance cost (I component) - None if unknown
            currency: Currency code (default USD)
            exchange_rate: Exchange rate to ILS (optional)
            port_fees: Port fees (optional)
            handling_fees: Handling fees (optional)
            other_costs: Other costs (optional)
            auto_calculate_insurance: If True, estimate insurance when missing
            insurance_rate: Rate for auto-calculating insurance (default 0.3%)
        
        Returns:
            CIFCalculation with components, missing items, and completeness status
        """
        if isinstance(incoterm, str):
            incoterm = Incoterm(incoterm.upper())
        
        data = self.incoterms_data.get(incoterm, {})
        includes_freight = data.get("includes_freight", False)
        includes_insurance = data.get("includes_insurance", False)
        
        # Initialize components
        components = CIFComponents(
            goods_value=Decimal(str(goods_value)),
            currency=currency,
            exchange_rate=Decimal(str(exchange_rate)) if exchange_rate else None,
            port_fees=Decimal(str(port_fees)),
            handling_fees=Decimal(str(handling_fees)),
            other_costs=Decimal(str(other_costs)),
        )
        
        missing_components = []
        missing_documents = []
        warnings = []
        
        # Handle Freight
        if includes_freight:
            # Freight is included in the price
            components.freight_value = Decimal("0")
        else:
            # Need freight separately
            if freight_value is not None:
                components.freight_value = Decimal(str(freight_value))
            else:
                missing_components.append("הובלה (Freight)")
                missing_documents.append("חשבון מטענים")
        
        # Handle Insurance
        if includes_insurance:
            # Insurance is included in the price
            components.insurance_value = Decimal("0")
        else:
            # Need insurance separately
            if insurance_value is not None:
                components.insurance_value = Decimal(str(insurance_value))
            elif auto_calculate_insurance and components.freight_value > 0:
                # Auto-calculate insurance as percentage of C+F
                cf_value = components.goods_value + components.freight_value
                components.insurance_value = (cf_value * Decimal(str(insurance_rate))).quantize(
                    Decimal("0.01"), ROUND_HALF_UP
                )
                warnings.append(f"ביטוח חושב אוטומטית ({insurance_rate:.1%} מערך C+F)")
            else:
                missing_components.append("ביטוח (Insurance)")
                missing_documents.append("תעודת ביטוח")
        
        # Determine if complete
        is_complete = len(missing_components) == 0
        
        return CIFCalculation(
            incoterm=incoterm,
            components=components,
            missing_components=missing_components,
            missing_documents=missing_documents,
            is_complete=is_complete,
            warnings=warnings,
        )
    
    def estimate_insurance(
        self,
        goods_value: float,
        freight_value: float = 0,
        rate: float = 0.003
    ) -> float:
        """
        Estimate insurance cost based on C+F value.
        
        Args:
            goods_value: Value of goods
            freight_value: Freight cost
            rate: Insurance rate (default 0.3%)
        
        Returns:
            Estimated insurance cost
        """
        cf_value = Decimal(str(goods_value)) + Decimal(str(freight_value))
        insurance = cf_value * Decimal(str(rate))
        return float(insurance.quantize(Decimal("0.01"), ROUND_HALF_UP))
    
    def get_all_incoterms(self, language: str = "he") -> List[Dict]:
        """Get list of all Incoterms with their info"""
        result = []
        
        for incoterm in Incoterm:
            info = self.get_incoterm_info(incoterm, language)
            info["needs_freight"] = not INCOTERMS_DATA[incoterm].get("includes_freight", False)
            info["needs_insurance"] = not INCOTERMS_DATA[incoterm].get("includes_insurance", False)
            result.append(info)
        
        return result
    
    def get_incoterms_comparison(self, language: str = "he") -> str:
        """Get a comparison table of all Incoterms"""
        if language == "he":
            lines = [
                "┌─────────┬────────────────────────┬──────────┬──────────┐",
                "│ קוד     │ שם                     │ הובלה    │ ביטוח    │",
                "├─────────┼────────────────────────┼──────────┼──────────┤",
            ]
            for incoterm in Incoterm:
                data = INCOTERMS_DATA[incoterm]
                name = data.get("name_he", "")[:20].ljust(20)
                freight = "כלול ✓" if data.get("includes_freight") else "נדרש ✗"
                insurance = "כלול ✓" if data.get("includes_insurance") else "נדרש ✗"
                lines.append(f"│ {incoterm.value.ljust(7)} │ {name} │ {freight.ljust(8)} │ {insurance.ljust(8)} │")
            lines.append("└─────────┴────────────────────────┴──────────┴──────────┘")
        else:
            lines = [
                "┌─────────┬────────────────────────────────┬──────────┬──────────┐",
                "│ Code    │ Name                           │ Freight  │ Insurance│",
                "├─────────┼────────────────────────────────┼──────────┼──────────┤",
            ]
            for incoterm in Incoterm:
                data = INCOTERMS_DATA[incoterm]
                name = data.get("name_en", "")[:28].ljust(28)
                freight = "Incl ✓" if data.get("includes_freight") else "Need ✗"
                insurance = "Incl ✓" if data.get("includes_insurance") else "Need ✗"
                lines.append(f"│ {incoterm.value.ljust(7)} │ {name} │ {freight.ljust(8)} │ {insurance.ljust(8)} │")
            lines.append("└─────────┴────────────────────────────────┴──────────┴──────────┘")
        
        return "\n".join(lines)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_calculator() -> IncotermsCalculator:
    """Create an IncotermsCalculator instance"""
    return IncotermsCalculator()


def calculate_cif(
    incoterm: str,
    goods_value: float,
    freight_value: Optional[float] = None,
    insurance_value: Optional[float] = None,
    currency: str = "USD",
    exchange_rate: Optional[float] = None,
) -> CIFCalculation:
    """
    Quick function to calculate CIF value.
    
    Example:
        result = calculate_cif("FOB", 10000, freight_value=500)
        print(result.components.cif_value)  # 10550.15 (with auto insurance)
    """
    calc = IncotermsCalculator()
    return calc.calculate_cif(
        incoterm=incoterm,
        goods_value=goods_value,
        freight_value=freight_value,
        insurance_value=insurance_value,
        currency=currency,
        exchange_rate=exchange_rate,
    )


def get_missing_for_cif(incoterm: str) -> Dict[str, bool]:
    """
    Quick function to check what's missing for CIF.
    
    Example:
        missing = get_missing_for_cif("FOB")
        print(missing)  # {'freight_needed': True, 'insurance_needed': True}
    """
    calc = IncotermsCalculator()
    return calc.get_missing_for_cif(incoterm)


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Incoterms CIF Calculator - Test")
    print("=" * 60)
    
    calc = create_calculator()
    
    # Show Incoterms comparison
    print("\n📊 Incoterms 2020 Comparison:")
    print(calc.get_incoterms_comparison("he"))
    
    # Test calculations
    print("\n" + "=" * 60)
    print("Test Calculations:")
    print("=" * 60)
    
    # Test 1: FOB with all values
    print("\n📝 Test 1: FOB $10,000 + Freight $500 + Insurance $50")
    result = calc.calculate_cif(
        incoterm="FOB",
        goods_value=10000,
        freight_value=500,
        insurance_value=50,
        currency="USD",
        exchange_rate=3.65
    )
    print(result.get_summary_hebrew())
    
    # Test 2: FOB missing freight
    print("\n" + "-" * 40)
    print("📝 Test 2: FOB $10,000 (no freight provided)")
    result = calc.calculate_cif(
        incoterm="FOB",
        goods_value=10000,
    )
    print(result.get_summary_hebrew())
    
    # Test 3: CIF (all included)
    print("\n" + "-" * 40)
    print("📝 Test 3: CIF $10,000 (freight & insurance included)")
    result = calc.calculate_cif(
        incoterm="CIF",
        goods_value=10000,
        exchange_rate=3.65
    )
    print(result.get_summary_hebrew())
    
    # Test 4: EXW (nothing included)
    print("\n" + "-" * 40)
    print("📝 Test 4: EXW $10,000 (nothing included)")
    result = calc.calculate_cif(
        incoterm="EXW",
        goods_value=10000,
    )
    print(result.get_summary_hebrew())
    
    # Test 5: FOB with auto insurance calculation
    print("\n" + "-" * 40)
    print("📝 Test 5: FOB $10,000 + Freight $500 (auto insurance)")
    result = calc.calculate_cif(
        incoterm="FOB",
        goods_value=10000,
        freight_value=500,
        auto_calculate_insurance=True
    )
    print(result.get_summary_hebrew())
    
    print("\n" + "=" * 60)
