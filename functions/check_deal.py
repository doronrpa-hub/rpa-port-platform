import json
import sys
from google.cloud import firestore
from google.oauth2 import service_account

SA_KEY_PATH = r"C:\Users\doron\sa-key.json"
PROJECT_ID = "rpa-port-customs"
SEARCH_TERMS = ["RPA16666", "6015697", "DARBOX", "rpa16666", "darbox"]
DEAL_COLLECTION = "tracker_deals"
RELATED_COLLECTIONS = ["tracker_container_status", "tracker_observations", "tracker_timeline"]
SEARCH_FIELDS = [
    "deal_id", "dealId", "deal_number", "dealNumber",
    "declaration_number", "declarationNumber",
    "reference", "ref", "name", "title",
    "container_id", "containerId", "customs_id",
    "file_number", "fileNumber", "importer_file",
]


def get_db():
    creds = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
    return firestore.Client(project=PROJECT_ID, credentials=creds)


def make_serializable(obj):
    if obj is None: return None
    if isinstance(obj, dict): return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list): return [make_serializable(i) for i in obj]
    if hasattr(obj, "isoformat"): return obj.isoformat()
    if isinstance(obj, bytes): return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "path"): return f"<ref:{obj.path}>"
    if hasattr(obj, "latitude"): return {"lat": obj.latitude, "lng": obj.longitude}
    return obj


def doc_to_dict(doc):
    data = doc.to_dict()
    return make_serializable(data) if data else None


def psec(title):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def pdoc(doc):
    data = doc_to_dict(doc)
    if data:
        print(f"  Document ID: {doc.id}")
        print(f"  Path: {doc.reference.path}")
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"  Document ID: {doc.id} -- (empty)")


def search_by_doc_id(db):
    psec("STEP 1: Direct Document ID Lookups in tracker_deals")
    found = []
    for term in SEARCH_TERMS:
        doc = db.collection(DEAL_COLLECTION).document(term).get()
        if doc.exists:
            print(f"  FOUND by doc ID: {term!r}")
            pdoc(doc)
            found.append(doc)
        else:
            print(f"  No doc with ID {term!r}")
    return found


def search_by_fields(db):
    psec("STEP 2: Field-based Queries in tracker_deals")
    found = []
    seen = set()
    for field in SEARCH_FIELDS:
        for term in SEARCH_TERMS:
            try:
                for doc in db.collection(DEAL_COLLECTION).where(field, "==", term).limit(5).stream():
                    if doc.id not in seen:
                        seen.add(doc.id)
                        print(f"  FOUND via {field} == {term!r}")
                        pdoc(doc)
                        found.append(doc)
            except Exception as e:
                es = str(e).lower()
                if "index" not in es and "not found" not in es:
                    print(f"  Query {field}=={term!r}: {e}")
    if not found:
        print("  No documents found via field queries.")
    return found


def list_samples(db):
    psec("STEP 3: Sample Documents from tracker_deals (first 5)")
    try:
        docs = list(db.collection(DEAL_COLLECTION).limit(5).stream())
        if not docs:
            print("  Collection is EMPTY or does not exist.")
        for doc in docs:
            print(f"  --- Doc ID: {doc.id} ---")
            pdoc(doc)
    except Exception as e:
        print(f"  Error: {e}")


def brute_scan(db):
    psec("STEP 4: Brute-force Scan of tracker_deals (up to 200 docs)")
    found = []
    seen = set()
    count = 0
    try:
        for doc in db.collection(DEAL_COLLECTION).limit(200).stream():
            count += 1
            data = doc.to_dict() or {}
            s = json.dumps(make_serializable(data), ensure_ascii=False, default=str) + " " + str(doc.id)
            for term in SEARCH_TERMS:
                if term.lower() in s.lower():
                    if doc.id not in seen:
                        seen.add(doc.id)
                        print(f"  FOUND (contains {term!r}) -- Doc ID: {doc.id}")
                        pdoc(doc)
                        found.append(doc)
                    break
        print(f"  Scanned {count} docs. Found {len(found)} matches.")
    except Exception as e:
        print(f"  Error: {e}")
    return found


def search_related(db, deal_ids):
    search_ids = set(SEARCH_TERMS + deal_ids)
    for cn in RELATED_COLLECTIONS:
        psec(f"Related Collection: {cn}")
        found_here = []
        seen = set()
        for t in search_ids:
            try:
                doc = db.collection(cn).document(t).get()
                if doc.exists:
                    print(f"  FOUND by doc ID {t!r}:")
                    pdoc(doc)
                    if doc.id not in seen:
                        seen.add(doc.id)
                        found_here.append(doc)
            except Exception:
                pass
        for field in ["deal_id", "dealId", "deal_number", "dealNumber", "reference", "declaration_number"]:
            for t in search_ids:
                try:
                    for doc in db.collection(cn).where(field, "==", t).limit(20).stream():
                        if doc.id not in seen:
                            seen.add(doc.id)
                            print(f"  FOUND via {field} == {t!r}:")
                            pdoc(doc)
                            found_here.append(doc)
                except Exception:
                    pass
        print(f"  Scanning {cn} (up to 100 docs)...")
        sc = 0
        try:
            for doc in db.collection(cn).limit(100).stream():
                sc += 1
                data = doc.to_dict() or {}
                s = json.dumps(make_serializable(data), ensure_ascii=False, default=str) + " " + str(doc.id)
                for term in SEARCH_TERMS:
                    if term.lower() in s.lower():
                        if doc.id not in seen:
                            seen.add(doc.id)
                            print(f"  FOUND (scan, contains {term!r}) -- Doc ID: {doc.id}")
                            pdoc(doc)
                            found_here.append(doc)
                        break
            print(f"  Scanned {sc} docs in {cn}.")
        except Exception as e:
            print(f"  Error scanning {cn}: {e}")
        if not found_here and sc == 0:
            print(f"  Collection {cn!r} appears empty or inaccessible.")
        elif not found_here:
            print(f"  No matching documents found in {cn}.")


def list_collections(db):
    psec("Available Root Collections")
    try:
        colls = list(db.collections())
        for c in colls:
            print(f"  - {c.id}")
        if not colls:
            print("  No collections found.")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    print("Connecting to Firestore...")
    print(f"  Project: {PROJECT_ID}")
    print(f"  SA Key:  {SA_KEY_PATH}")
    db = get_db()
    print("  Connected successfully.")
    print()
    list_collections(db)
    f1 = search_by_doc_id(db)
    f2 = search_by_fields(db)
    list_samples(db)
    f3 = brute_scan(db)
    all_f = f1 + f2 + f3
    deal_ids = list(set(d.id for d in all_f))
    print(f">>> Total unique deals found: {len(deal_ids)}")
    if deal_ids:
        print(f">>> Deal IDs: {deal_ids}")
    search_related(db, deal_ids)
    psec("DONE")
    print("  Search complete.")


if __name__ == "__main__":
    main()
