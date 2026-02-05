# Quick test of the full classification pipeline
import sys
sys.path.insert(0, '/home/doronrpa/rpa-port-platform/functions')

from lib.classification_agents import run_full_classification, build_classification_email

# Fake invoice text
test_doc = """
COMMERCIAL INVOICE
Seller: ABC Electronics Ltd, Shenzhen, China
Buyer: RPA Port Ltd, Israel

Items:
1. Wireless Bluetooth Headphones - 100 units - $15/unit - $1500
2. USB-C Charging Cables - 500 units - $2/unit - $1000
3. Phone Cases (plastic) - 200 units - $3/unit - $600

Total: $3,100 USD
Origin: China
Incoterms: FOB Shenzhen
"""

print("Testing with fake Anthropic key (will fail, but shows flow)...")
results = run_full_classification("test-key", test_doc)
print(f"Success: {results.get('success')}")
print(f"Error: {results.get('error', 'none')}")
