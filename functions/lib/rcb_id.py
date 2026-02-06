"""
RCB Internal ID System v1.0
============================
Generates human-readable, sequential IDs for every email entering the RCB system.

Format: RCB-{YYYYMMDD}-{sequence:03d}-{type}
Examples:
    RCB-20260206-001-CLS   (classification)
    RCB-20260206-002-KQ    (knowledge query)
    RCB-20260206-003-TST   (self-test)
    RCB-20260206-004-SYS   (system/skip)

Sequence resets daily. Uses Firestore atomic increment for safety.

Author: RCB System
Session: 13.1
"""

from datetime import datetime, timezone


class RCBType:
    CLASSIFICATION = "CLS"
    KNOWLEDGE_QUERY = "KQ"
    SELF_TEST = "TST"
    SYSTEM = "SYS"


COUNTER_COLLECTION = "system_counters"
COUNTER_PREFIX = "rcb_seq_"


def generate_rcb_id(db, firestore_module, rcb_type: str) -> str:
    """Generate the next RCB Internal ID with atomic Firestore counter."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    counter_doc_id = f"{COUNTER_PREFIX}{today}"
    counter_ref = db.collection(COUNTER_COLLECTION).document(counter_doc_id)

    try:
        counter_ref.set(
            {"seq": firestore_module.Increment(1), "date": today},
            merge=True,
        )
        snap = counter_ref.get()
        seq = snap.to_dict().get("seq", 1)
    except (AttributeError, Exception) as e:
        snap = counter_ref.get()
        if snap.exists:
            seq = snap.to_dict().get("seq", 0) + 1
        else:
            seq = 1
        counter_ref.set({"seq": seq, "date": today}, merge=True)
        print(f"    ⚠️ RCB ID fallback used: {e}")

    return f"RCB-{today}-{seq:03d}-{rcb_type}"


def parse_rcb_id(rcb_id: str) -> dict:
    """Parse an RCB ID into components. Returns None if invalid."""
    if not rcb_id or not rcb_id.startswith("RCB-"):
        return None
    parts = rcb_id.split("-")
    if len(parts) != 4:
        return None
    try:
        return {"date": parts[1], "seq": int(parts[2]), "type": parts[3]}
    except (ValueError, IndexError):
        return None
