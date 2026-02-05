"""
RCB Product Type Classifier
Detects product category from text and determines required documents.

File: functions/lib/product_classifier.py
Project: RCB (Robotic Customs Bot)
Session: 9
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# Import from document_tracker
try:
    from .document_tracker import ProductCategory, DocumentType, DOC_TYPE_HEBREW
except ImportError:
    from document_tracker import ProductCategory, DocumentType, DOC_TYPE_HEBREW


# =============================================================================
# KEYWORD DATABASES
# =============================================================================

# Keywords for each product category (English + Hebrew)
CATEGORY_KEYWORDS = {
    ProductCategory.CHEMICALS: {
        "en": [
            "chemical", "chemicals", "acid", "solvent", "reagent", "compound",
            "oxide", "hydroxide", "sulfate", "chloride", "nitrate", "phosphate",
            "polymer", "resin", "adhesive", "paint", "coating", "dye", "pigment",
            "fertilizer", "pesticide", "herbicide", "insecticide", "fungicide",
            "detergent", "surfactant", "catalyst", "additive", "lubricant",
            "petroleum", "oil", "fuel", "gas", "propane", "butane", "ethanol",
            "methanol", "acetone", "benzene", "toluene", "xylene", "ammonia",
            "bleach", "disinfectant", "sanitizer", "hazardous", "flammable",
            "corrosive", "toxic", "oxidizer", "explosive", "radioactive",
        ],
        "he": [
            "כימיקל", "כימיקלים", "חומצה", "ממס", "ריאגנט", "תרכובת",
            "תחמוצת", "הידרוקסיד", "סולפט", "כלוריד", "ניטרט", "פוספט",
            "פולימר", "שרף", "דבק", "צבע", "ציפוי", "פיגמנט",
            "דשן", "קוטל", "חומר הדברה", "חומר מסוכן", "דליק",
            "נפט", "שמן", "דלק", "גז", "אמוניה", "חומר מאכל",
            "חומר ניקוי", "חיטוי", "רעיל", "מחמצן", "נפיץ",
        ]
    },
    
    ProductCategory.FOOD: {
        "en": [
            "food", "edible", "consumable", "ingredient", "snack", "beverage",
            "drink", "juice", "water", "soda", "coffee", "tea", "milk", "dairy",
            "cheese", "butter", "yogurt", "cream", "meat", "beef", "pork",
            "chicken", "poultry", "fish", "seafood", "shrimp", "salmon",
            "vegetable", "fruit", "grain", "rice", "wheat", "flour", "bread",
            "pasta", "noodle", "cereal", "oat", "corn", "soy", "bean",
            "nut", "almond", "peanut", "cashew", "walnut", "seed", "oil",
            "olive", "sugar", "honey", "syrup", "chocolate", "candy", "sweet",
            "spice", "herb", "salt", "pepper", "sauce", "condiment", "vinegar",
            "frozen", "canned", "dried", "preserved", "organic", "kosher", "halal",
            "supplement", "vitamin", "protein", "nutrition", "dietary",
        ],
        "he": [
            "מזון", "אוכל", "מאכל", "רכיב", "חטיף", "משקה",
            "שתייה", "מיץ", "מים", "קפה", "תה", "חלב", "מוצר חלב",
            "גבינה", "חמאה", "יוגורט", "שמנת", "בשר", "עוף",
            "דג", "פירות ים", "דגים", "ירק", "ירקות", "פרי", "פירות",
            "דגן", "אורז", "חיטה", "קמח", "לחם", "פסטה", "אטריות",
            "דגני בוקר", "שיבולת", "תירס", "סויה", "שעועית",
            "אגוז", "שקד", "בוטן", "זרע", "שמן", "זית",
            "סוכר", "דבש", "סירופ", "שוקולד", "ממתק", "מתוק",
            "תבלין", "עשב", "מלח", "פלפל", "רוטב", "חומץ",
            "קפוא", "משומר", "מיובש", "אורגני", "כשר",
            "תוסף", "ויטמין", "חלבון", "תזונה", "דיאטטי",
        ]
    },
    
    ProductCategory.VEHICLES: {
        "en": [
            "vehicle", "car", "automobile", "auto", "truck", "van", "bus",
            "motorcycle", "motorbike", "scooter", "bicycle", "bike", "ebike",
            "suv", "sedan", "coupe", "hatchback", "convertible", "wagon",
            "pickup", "trailer", "caravan", "rv", "motorhome",
            "engine", "motor", "transmission", "gearbox", "chassis", "body",
            "wheel", "tire", "tyre", "rim", "brake", "suspension", "steering",
            "exhaust", "muffler", "radiator", "battery", "alternator", "starter",
            "headlight", "taillight", "bumper", "fender", "hood", "trunk",
            "windshield", "mirror", "seat", "dashboard", "airbag", "seatbelt",
            "toyota", "honda", "ford", "chevrolet", "bmw", "mercedes", "audi",
            "volkswagen", "nissan", "hyundai", "kia", "mazda", "subaru",
        ],
        "he": [
            "רכב", "מכונית", "אוטו", "משאית", "אוטובוס", "ואן",
            "אופנוע", "קטנוע", "אופניים", "אופניים חשמליים",
            "ג'יפ", "סדאן", "קופה", "סטיישן", "טנדר", "קרוואן",
            "מנוע", "תיבת הילוכים", "שלדה", "מרכב",
            "גלגל", "צמיג", "חישוק", "בלם", "מתלה", "הגה",
            "אגזוז", "רדיאטור", "מצבר", "אלטרנטור", "מתנע",
            "פנס", "פגוש", "כנף", "מכסה מנוע", "תא מטען",
            "שמשה", "מראה", "מושב", "לוח מחוונים", "כרית אוויר", "חגורה",
        ]
    },
    
    ProductCategory.MACHINERY: {
        "en": [
            "machine", "machinery", "equipment", "industrial", "manufacturing",
            "cnc", "lathe", "mill", "milling", "drill", "drilling", "press",
            "pump", "compressor", "generator", "transformer", "conveyor",
            "robot", "robotic", "automation", "automated", "plc", "controller",
            "motor", "actuator", "servo", "hydraulic", "pneumatic", "valve",
            "bearing", "gear", "shaft", "coupling", "belt", "chain", "sprocket",
            "sensor", "encoder", "transducer", "gauge", "meter", "instrument",
            "welder", "welding", "cutter", "cutting", "grinder", "grinding",
            "printer", "3d printer", "laser", "plasma", "waterjet",
            "crane", "hoist", "forklift", "loader", "excavator", "bulldozer",
            "tractor", "harvester", "agricultural", "farming",
        ],
        "he": [
            "מכונה", "מכונות", "ציוד", "תעשייתי", "ייצור",
            "מחרטה", "כרסום", "מקדחה", "מכבש", "משאבה",
            "מדחס", "גנרטור", "שנאי", "מסוע", "רובוט",
            "אוטומציה", "בקר", "מנוע", "מפעיל", "סרוו",
            "הידראולי", "פנאומטי", "שסתום", "מיסב", "גלגל שיניים",
            "ציר", "רצועה", "שרשרת", "חיישן", "מד",
            "ריתוך", "חיתוך", "השחזה", "מדפסת", "לייזר",
            "מנוף", "מלגזה", "טרקטור", "חקלאי",
        ]
    },
    
    ProductCategory.ELECTRONICS: {
        "en": [
            "electronic", "electronics", "electrical", "electric", "digital",
            "computer", "laptop", "desktop", "server", "workstation",
            "tablet", "phone", "smartphone", "mobile", "cellular",
            "monitor", "display", "screen", "lcd", "led", "oled", "tv",
            "keyboard", "mouse", "printer", "scanner", "webcam", "camera",
            "speaker", "headphone", "earphone", "microphone", "audio", "video",
            "router", "modem", "switch", "network", "wifi", "bluetooth",
            "cable", "wire", "connector", "adapter", "charger", "power supply",
            "circuit", "pcb", "chip", "processor", "cpu", "gpu", "memory", "ram",
            "storage", "ssd", "hdd", "hard drive", "flash", "usb",
            "semiconductor", "transistor", "capacitor", "resistor", "diode", "led",
            "battery", "lithium", "rechargeable", "solar", "panel",
            "smart", "iot", "sensor", "arduino", "raspberry", "embedded",
        ],
        "he": [
            "אלקטרוניקה", "אלקטרוני", "חשמלי", "דיגיטלי",
            "מחשב", "לפטופ", "נייד", "שרת", "טאבלט", "פלאפון", "סלולרי",
            "מסך", "צג", "מקלדת", "עכבר", "מדפסת", "סורק", "מצלמה",
            "רמקול", "אוזניות", "מיקרופון", "אודיו", "וידאו",
            "נתב", "מודם", "רשת", "כבל", "חוט", "מחבר", "מתאם", "מטען",
            "מעגל", "שבב", "מעבד", "זיכרון", "אחסון", "כונן",
            "מוליך למחצה", "סוללה", "ליתיום", "סולארי", "פאנל",
            "חכם", "חיישן",
        ]
    },
    
    ProductCategory.PHARMACEUTICALS: {
        "en": [
            "pharmaceutical", "drug", "medicine", "medication", "prescription",
            "tablet", "capsule", "pill", "syrup", "injection", "vaccine",
            "antibiotic", "antiviral", "antifungal", "antiseptic", "analgesic",
            "painkiller", "aspirin", "ibuprofen", "paracetamol", "acetaminophen",
            "insulin", "hormone", "steroid", "vitamin", "mineral", "supplement",
            "medical", "clinical", "therapeutic", "treatment", "therapy",
            "diagnostic", "laboratory", "reagent", "test", "assay",
            "hospital", "clinic", "pharmacy", "healthcare", "health",
            "fda", "approved", "controlled", "narcotic", "psychotropic",
        ],
        "he": [
            "תרופה", "תרופות", "רוקחות", "תכשיר", "מרשם",
            "טבליה", "כמוסה", "גלולה", "סירופ", "זריקה", "חיסון",
            "אנטיביוטיקה", "משכך כאבים", "אספירין",
            "אינסולין", "הורמון", "סטרואיד", "ויטמין", "מינרל", "תוסף",
            "רפואי", "קליני", "טיפולי", "אבחון", "מעבדה",
            "בית חולים", "מרפאה", "בית מרקחת", "בריאות",
        ]
    },
    
    ProductCategory.TEXTILES: {
        "en": [
            "textile", "fabric", "cloth", "clothing", "apparel", "garment",
            "shirt", "blouse", "pants", "trousers", "jeans", "shorts",
            "dress", "skirt", "suit", "jacket", "coat", "sweater", "hoodie",
            "underwear", "socks", "stockings", "lingerie", "swimwear",
            "cotton", "wool", "silk", "linen", "polyester", "nylon", "rayon",
            "spandex", "lycra", "elastane", "acrylic", "viscose", "bamboo",
            "denim", "leather", "suede", "fur", "fleece", "velvet", "satin",
            "knit", "woven", "embroidered", "printed", "dyed",
            "bedding", "sheet", "blanket", "towel", "curtain", "carpet", "rug",
        ],
        "he": [
            "טקסטיל", "בד", "אריג", "ביגוד", "לבוש", "בגד",
            "חולצה", "מכנסיים", "ג'ינס", "שמלה", "חצאית",
            "חליפה", "ז'קט", "מעיל", "סוודר", "הלבשה תחתונה",
            "גרביים", "בגד ים", "כותנה", "צמר", "משי", "פשתן",
            "פוליאסטר", "ניילון", "ספנדקס", "אקריליק",
            "ג'ינס", "עור", "פרווה", "קטיפה", "סאטן",
            "סריג", "אריג", "רקום", "מודפס", "צבוע",
            "מצעים", "סדין", "שמיכה", "מגבת", "וילון", "שטיח",
        ]
    },
    
    ProductCategory.TOYS: {
        "en": [
            "toy", "toys", "game", "games", "play", "playing",
            "doll", "action figure", "figurine", "stuffed", "plush", "teddy",
            "lego", "blocks", "building", "puzzle", "jigsaw",
            "car", "truck", "train", "plane", "boat", "vehicle",
            "ball", "sports", "outdoor", "playground", "swing", "slide",
            "board game", "card game", "chess", "checkers", "monopoly",
            "video game", "console", "playstation", "xbox", "nintendo",
            "remote control", "rc", "drone", "robot", "electronic",
            "educational", "learning", "stem", "science", "math",
            "baby", "infant", "toddler", "child", "children", "kid", "kids",
        ],
        "he": [
            "צעצוע", "צעצועים", "משחק", "משחקים",
            "בובה", "דמות", "פרוותי", "דובי",
            "לגו", "קוביות", "בנייה", "פאזל",
            "מכונית", "רכבת", "מטוס", "סירה",
            "כדור", "ספורט", "חיצוני", "מגרש משחקים",
            "משחק קופסה", "משחק קלפים", "שחמט",
            "משחק וידאו", "קונסולה", "פלייסטיישן",
            "שלט רחוק", "רחפן", "רובוט", "אלקטרוני",
            "חינוכי", "לימודי", "תינוק", "פעוט", "ילד", "ילדים",
        ]
    },
    
    ProductCategory.COSMETICS: {
        "en": [
            "cosmetic", "cosmetics", "beauty", "makeup", "make-up",
            "skincare", "skin care", "facial", "face", "body", "hand",
            "cream", "lotion", "moisturizer", "serum", "oil", "gel",
            "cleanser", "wash", "scrub", "exfoliant", "toner", "mask",
            "sunscreen", "spf", "sunblock", "tanning", "bronzer",
            "foundation", "concealer", "powder", "blush", "bronzer",
            "eyeshadow", "eyeliner", "mascara", "eyebrow", "lash",
            "lipstick", "lip gloss", "lip balm", "lip liner",
            "nail", "polish", "manicure", "pedicure",
            "perfume", "fragrance", "cologne", "deodorant", "antiperspirant",
            "shampoo", "conditioner", "hair", "styling", "dye", "color",
            "soap", "body wash", "bath", "shower",
        ],
        "he": [
            "קוסמטיקה", "יופי", "איפור", "טיפוח",
            "עור", "פנים", "גוף", "יד",
            "קרם", "תחליב", "לחות", "סרום", "שמן", "ג'ל",
            "ניקוי", "פילינג", "טונר", "מסכה",
            "קרם הגנה", "שיזוף",
            "מייקאפ", "פודרה", "סומק",
            "צללית", "אייליינר", "מסקרה", "גבות", "ריסים",
            "שפתון", "גלוס", "באלם",
            "לק", "ציפורניים", "מניקור", "פדיקור",
            "בושם", "דאודורנט",
            "שמפו", "מרכך", "שיער", "עיצוב", "צבע",
            "סבון", "אמבט", "מקלחת",
        ]
    },
}

# HS Code prefixes that indicate product categories
HS_CODE_PREFIXES = {
    ProductCategory.CHEMICALS: ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
    ProductCategory.FOOD: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", 
                           "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
    ProductCategory.VEHICLES: ["87"],
    ProductCategory.MACHINERY: ["84", "85"],
    ProductCategory.ELECTRONICS: ["85"],
    ProductCategory.PHARMACEUTICALS: ["30"],
    ProductCategory.TEXTILES: ["50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", 
                               "61", "62", "63"],
    ProductCategory.TOYS: ["95"],
    ProductCategory.COSMETICS: ["33"],
}

# Required documents per category (same as document_tracker but with descriptions)
CATEGORY_REQUIRED_DOCS = {
    ProductCategory.CHEMICALS: [
        {
            "type": DocumentType.MSDS,
            "name_he": "גיליון בטיחות חומר (MSDS)",
            "name_en": "Material Safety Data Sheet",
            "reason_he": "נדרש לזיהוי סיווג חומרים מסוכנים ודרישות בטיחות",
            "reason_en": "Required for hazardous material classification and safety requirements",
        }
    ],
    ProductCategory.FOOD: [
        {
            "type": DocumentType.COMPONENT_LIST,
            "name_he": "רשימת רכיבים עם אחוזים",
            "name_en": "Ingredient list with percentages",
            "reason_he": "נדרש לסיווג מדויק של מוצרי מזון לפי הרכב",
            "reason_en": "Required for accurate food classification by composition",
        },
        {
            "type": DocumentType.HEALTH_CERT,
            "name_he": "אישור משרד הבריאות",
            "name_en": "Ministry of Health approval",
            "reason_he": "נדרש ליבוא מוצרי מזון לישראל",
            "reason_en": "Required for food import to Israel",
        }
    ],
    ProductCategory.VEHICLES: [
        {
            "type": DocumentType.CARFAX,
            "name_he": "דו\"ח CarFax",
            "name_en": "CarFax report",
            "reason_he": "נדרש לרכבים משומשים - היסטוריית הרכב",
            "reason_en": "Required for used vehicles - vehicle history",
        },
        {
            "type": DocumentType.COC,
            "name_he": "תעודת התאמה (COC)",
            "name_en": "Certificate of Conformity",
            "reason_he": "נדרש לפי תקנות משרד התחבורה",
            "reason_en": "Required per Ministry of Transport regulations",
        }
    ],
    ProductCategory.MACHINERY: [
        {
            "type": DocumentType.CATALOGUE,
            "name_he": "קטלוג",
            "name_en": "Catalogue",
            "reason_he": "נדרש לזיהוי מדויק של סוג המכונה ופונקציונליות",
            "reason_en": "Required for accurate machine type and functionality identification",
        },
        {
            "type": DocumentType.TECH_SPECS,
            "name_he": "מפרט טכני",
            "name_en": "Technical specifications",
            "reason_he": "נדרש לסיווג מכונות מורכבות",
            "reason_en": "Required for complex machinery classification",
        }
    ],
    ProductCategory.ELECTRONICS: [
        {
            "type": DocumentType.TECH_SPECS,
            "name_he": "מפרט טכני",
            "name_en": "Technical specifications",
            "reason_he": "נדרש לסיווג מוצרי אלקטרוניקה",
            "reason_en": "Required for electronics classification",
        },
        {
            "type": DocumentType.STANDARDS_CERT,
            "name_he": "אישור תקן (CE/FCC)",
            "name_en": "Standards certificate (CE/FCC)",
            "reason_he": "נדרש ליבוא מוצרי אלקטרוניקה לישראל",
            "reason_en": "Required for electronics import to Israel",
        }
    ],
    ProductCategory.PHARMACEUTICALS: [
        {
            "type": DocumentType.HEALTH_CERT,
            "name_he": "אישור משרד הבריאות",
            "name_en": "Ministry of Health approval",
            "reason_he": "נדרש ליבוא תרופות ותכשירים רפואיים",
            "reason_en": "Required for pharmaceutical import",
        }
    ],
    ProductCategory.TEXTILES: [
        {
            "type": DocumentType.COMPONENT_LIST,
            "name_he": "הרכב בד (אחוזי סיבים)",
            "name_en": "Fabric composition (fiber percentages)",
            "reason_he": "נדרש לסיווג מוצרי טקסטיל לפי הרכב",
            "reason_en": "Required for textile classification by composition",
        }
    ],
    ProductCategory.TOYS: [
        {
            "type": DocumentType.STANDARDS_CERT,
            "name_he": "אישור תקן בטיחות",
            "name_en": "Safety standards certificate",
            "reason_he": "נדרש ליבוא צעצועים - תקני בטיחות",
            "reason_en": "Required for toy import - safety standards",
        }
    ],
    ProductCategory.COSMETICS: [
        {
            "type": DocumentType.COMPONENT_LIST,
            "name_he": "רשימת רכיבים (INCI)",
            "name_en": "Ingredient list (INCI)",
            "reason_he": "נדרש לסיווג מוצרי קוסמטיקה",
            "reason_en": "Required for cosmetics classification",
        },
        {
            "type": DocumentType.HEALTH_CERT,
            "name_he": "אישור משרד הבריאות",
            "name_en": "Ministry of Health approval",
            "reason_he": "נדרש ליבוא מוצרי קוסמטיקה לישראל",
            "reason_en": "Required for cosmetics import to Israel",
        }
    ],
    ProductCategory.GENERAL: [],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ClassificationResult:
    """Result of product classification"""
    category: ProductCategory
    confidence: float  # 0.0 - 1.0
    matched_keywords: List[str]
    required_docs: List[Dict]
    alternative_categories: List[Tuple[ProductCategory, float]]
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "matched_keywords": self.matched_keywords,
            "required_docs": self.required_docs,
            "alternative_categories": [
                {"category": cat.value, "confidence": conf}
                for cat, conf in self.alternative_categories
            ]
        }
    
    def get_summary_hebrew(self) -> str:
        """Get Hebrew summary of classification"""
        lines = []
        lines.append(f"📦 קטגוריה: {self.category.value}")
        lines.append(f"🎯 רמת ביטחון: {self.confidence:.0%}")
        
        if self.matched_keywords:
            lines.append(f"🔍 מילות מפתח: {', '.join(self.matched_keywords[:5])}")
        
        if self.required_docs:
            lines.append("")
            lines.append("📋 מסמכים נדרשים:")
            for doc in self.required_docs:
                lines.append(f"  • {doc.get('name_he', doc.get('name_en', ''))}")
                lines.append(f"    סיבה: {doc.get('reason_he', doc.get('reason_en', ''))}")
        
        if self.alternative_categories:
            lines.append("")
            lines.append("🔄 קטגוריות חלופיות:")
            for cat, conf in self.alternative_categories[:3]:
                lines.append(f"  • {cat.value} ({conf:.0%})")
        
        return "\n".join(lines)


# =============================================================================
# CLASSIFIER CLASS
# =============================================================================

class ProductClassifier:
    """
    Classifies products into categories and determines required documents.
    
    Usage:
        classifier = ProductClassifier()
        result = classifier.classify("Chemical compound sulfuric acid")
        print(result.category)  # ProductCategory.CHEMICALS
        print(result.required_docs)  # [{'type': MSDS, ...}]
    """
    
    def __init__(self):
        self.keywords = CATEGORY_KEYWORDS
        self.hs_prefixes = HS_CODE_PREFIXES
        self.required_docs = CATEGORY_REQUIRED_DOCS
    
    def classify(
        self,
        text: str,
        hs_code: Optional[str] = None,
        weight_text: float = 0.7,
        weight_hs: float = 0.3
    ) -> ClassificationResult:
        """
        Classify product based on text description and/or HS code.
        
        Args:
            text: Product description (from invoice, packing list, etc.)
            hs_code: Optional HS code (if known)
            weight_text: Weight for text-based classification (0-1)
            weight_hs: Weight for HS code-based classification (0-1)
        
        Returns:
            ClassificationResult with category, confidence, and required docs
        """
        # Normalize text
        text_lower = text.lower().strip()
        
        # Get scores from text analysis
        text_scores = self._analyze_text(text_lower)
        
        # Get scores from HS code
        hs_scores = {}
        if hs_code:
            hs_scores = self._analyze_hs_code(hs_code)
        
        # Combine scores
        combined_scores = {}
        all_categories = set(text_scores.keys()) | set(hs_scores.keys())
        
        for category in all_categories:
            text_score = text_scores.get(category, (0, []))[0]
            hs_score = hs_scores.get(category, 0)
            
            if hs_code:
                combined_score = (text_score * weight_text) + (hs_score * weight_hs)
            else:
                combined_score = text_score
            
            combined_scores[category] = combined_score
        
        # Find best category
        if combined_scores:
            best_category = max(combined_scores, key=combined_scores.get)
            best_score = combined_scores[best_category]
            matched_keywords = text_scores.get(best_category, (0, []))[1]
        else:
            best_category = ProductCategory.GENERAL
            best_score = 0.0
            matched_keywords = []
        
        # Get alternative categories
        alternatives = sorted(
            [(cat, score) for cat, score in combined_scores.items() if cat != best_category],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        # Get required documents
        required_docs = self.required_docs.get(best_category, [])
        
        return ClassificationResult(
            category=best_category,
            confidence=min(best_score, 1.0),
            matched_keywords=matched_keywords,
            required_docs=required_docs,
            alternative_categories=alternatives
        )
    
    def _analyze_text(self, text: str) -> Dict[ProductCategory, Tuple[float, List[str]]]:
        """Analyze text and return scores per category with matched keywords"""
        scores = {}
        
        for category, keywords in self.keywords.items():
            all_keywords = keywords.get("en", []) + keywords.get("he", [])
            matched = []
            
            for keyword in all_keywords:
                if keyword.lower() in text:
                    matched.append(keyword)
            
            if matched:
                # Score based on number of matches (normalized)
                score = min(len(matched) / 3, 1.0)  # 3+ matches = 100%
                scores[category] = (score, matched)
        
        return scores
    
    def _analyze_hs_code(self, hs_code: str) -> Dict[ProductCategory, float]:
        """Analyze HS code and return scores per category"""
        scores = {}
        
        # Clean HS code
        hs_clean = re.sub(r'[^0-9]', '', hs_code)
        
        if len(hs_clean) < 2:
            return scores
        
        prefix = hs_clean[:2]
        
        for category, prefixes in self.hs_prefixes.items():
            if prefix in prefixes:
                scores[category] = 1.0  # Exact match
        
        return scores
    
    def classify_from_invoice(
        self,
        product_description: str,
        hs_code: Optional[str] = None,
        supplier_name: Optional[str] = None,
        additional_info: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classify product from invoice data.
        
        Args:
            product_description: Main product description
            hs_code: HS code if provided on invoice
            supplier_name: Supplier name (may help classification)
            additional_info: Any additional text (notes, specs, etc.)
        
        Returns:
            ClassificationResult
        """
        # Combine all text
        text_parts = [product_description]
        if supplier_name:
            text_parts.append(supplier_name)
        if additional_info:
            text_parts.append(additional_info)
        
        combined_text = " ".join(text_parts)
        
        return self.classify(combined_text, hs_code)
    
    def get_required_docs_for_category(
        self,
        category: ProductCategory,
        language: str = "he"
    ) -> List[str]:
        """Get list of required document names for a category"""
        docs = self.required_docs.get(category, [])
        
        if language == "he":
            return [doc.get("name_he", doc.get("name_en", "")) for doc in docs]
        else:
            return [doc.get("name_en", doc.get("name_he", "")) for doc in docs]
    
    def get_all_categories(self) -> List[Dict]:
        """Get all categories with their required documents"""
        result = []
        
        for category in ProductCategory:
            docs = self.required_docs.get(category, [])
            result.append({
                "category": category.value,
                "required_docs": [doc.get("name_he") for doc in docs],
                "doc_count": len(docs)
            })
        
        return result


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_classifier() -> ProductClassifier:
    """Create a ProductClassifier instance"""
    return ProductClassifier()


def classify_product(
    text: str,
    hs_code: Optional[str] = None
) -> ClassificationResult:
    """
    Quick function to classify a product.
    
    Args:
        text: Product description
        hs_code: Optional HS code
    
    Returns:
        ClassificationResult
    
    Example:
        result = classify_product("Chemical compound sulfuric acid")
        print(result.category)  # ProductCategory.CHEMICALS
    """
    classifier = ProductClassifier()
    return classifier.classify(text, hs_code)


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RCB Product Classifier - Test")
    print("=" * 60)
    
    classifier = create_classifier()
    
    # Test cases
    test_cases = [
        ("Sulfuric acid industrial grade 98%", None),
        ("Cotton t-shirt 100% organic", None),
        ("iPhone 15 Pro Max smartphone", "8517120000"),
        ("חומצה גופרתית תעשייתית", None),
        ("שוקולד מריר 70% קקאו", None),
        ("Toyota Corolla 2023 sedan", "8703"),
        ("CNC milling machine 5-axis", None),
        ("Baby doll plush toy", "9503"),
        ("Face cream moisturizer SPF30", None),
        ("Aspirin tablets 500mg", "3004"),
    ]
    
    for text, hs_code in test_cases:
        print(f"\n📝 Input: {text}")
        if hs_code:
            print(f"   HS Code: {hs_code}")
        
        result = classifier.classify(text, hs_code)
        
        print(f"   ➡️  Category: {result.category.value}")
        print(f"   ➡️  Confidence: {result.confidence:.0%}")
        if result.matched_keywords:
            print(f"   ➡️  Keywords: {', '.join(result.matched_keywords[:3])}")
        if result.required_docs:
            doc_names = [d.get("name_he", d.get("name_en")) for d in result.required_docs]
            print(f"   ➡️  Required: {', '.join(doc_names)}")
    
    print("\n" + "=" * 60)
    print("Hebrew summary test:")
    print("=" * 60)
    result = classifier.classify("חומר ניקוי תעשייתי כימי")
    print(result.get_summary_hebrew())
    print("=" * 60)
