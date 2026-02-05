import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()
docs = db.collection("rcb_processed").stream()
count = 0
for doc in docs:
    doc.reference.delete()
    count += 1
    
print(f"Cleared {count} processed records")
