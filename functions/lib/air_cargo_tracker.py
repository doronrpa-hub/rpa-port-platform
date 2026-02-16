"""
Air Cargo Tracker — AWB status polling for Ben Gurion Airport terminals
========================================================================
Integrates with:
  1. Maman API (PRIORITY) — mamanonline.maman.co.il — REST API for AWB status
  2. Swissport (STUB) — swissport.co.il — second cargo terminal, no API yet
  3. Aviation Edge (FUTURE) — aviation-edge.com — flight tracking for pre-arrival ETA

Collections:
  tracker_awb_status — one doc per AWB, status + history + alerts

Scheduler entry point: poll_air_cargo_for_tracker(db, firestore, get_secret)
Called by rcb_tracker_poll every 30 minutes alongside sea freight polling.
"""

import re
import requests
from datetime import datetime, timezone, timedelta


# ═══════════════════════════════════════════════════════════════
#  AIRLINE PREFIX → NAME + TERMINAL ROUTING
# ═══════════════════════════════════════════════════════════════

AIRLINE_PREFIXES = {
    "006": {"name": "Delta Air Lines", "terminal": "maman"},
    "014": {"name": "Air Canada", "terminal": "maman"},
    "020": {"name": "Lufthansa", "terminal": "maman"},
    "023": {"name": "FedEx", "terminal": "swissport"},
    "027": {"name": "Air India", "terminal": "maman"},
    "034": {"name": "Ethiopian Airlines", "terminal": "maman"},
    "047": {"name": "Avianca", "terminal": "maman"},
    "055": {"name": "Air France", "terminal": "maman"},
    "057": {"name": "Air France Cargo", "terminal": "maman"},
    "074": {"name": "KLM", "terminal": "maman"},
    "079": {"name": "Alitalia", "terminal": "maman"},
    "080": {"name": "LATAM", "terminal": "maman"},
    "081": {"name": "Qantas", "terminal": "maman"},
    "098": {"name": "Asiana Airlines", "terminal": "maman"},
    "105": {"name": "Austrian Airlines", "terminal": "maman"},
    "114": {"name": "El Al", "terminal": "maman"},
    "125": {"name": "British Airways", "terminal": "maman"},
    "160": {"name": "Cathay Pacific", "terminal": "maman"},
    "172": {"name": "EVA Air", "terminal": "maman"},
    "176": {"name": "Emirates", "terminal": "maman"},
    "180": {"name": "Korean Air", "terminal": "maman"},
    "217": {"name": "Thai Airways", "terminal": "maman"},
    "220": {"name": "Coyne Airways", "terminal": "maman"},
    "235": {"name": "Turkish Airlines", "terminal": "maman"},
    "406": {"name": "DHL Express", "terminal": "maman"},
    "580": {"name": "UPS", "terminal": "swissport"},
    "618": {"name": "Singapore Airlines", "terminal": "maman"},
    "695": {"name": "CAL Cargo Airlines", "terminal": "maman"},
    "932": {"name": "Arkia Israeli Airlines", "terminal": "maman"},
    "934": {"name": "Israir Airlines", "terminal": "maman"},
}

# Hebrew status mapping → normalized English status
_STATUS_MAP = {
    # Hebrew
    "שוחרר": "released",
    "שוחרר מהמכס": "customs_released",
    "נמסר": "delivered",
    "נחת": "arrived",
    "הגיע": "arrived",
    "הגיע למחסן": "at_terminal",
    "מוכן למסירה": "ready",
    "ממתין": "pending",
    "עיכוב": "hold",
    "בבדיקה": "hold",
    "בדיקה": "hold",
    "עוכב": "hold",
    "מעוכב": "hold",
    "עיכוב מכס": "customs_hold",
    "בבדיקת מכס": "customs_hold",
    # English
    "released": "released",
    "delivered": "delivered",
    "arrived": "arrived",
    "hold": "hold",
    "customs hold": "customs_hold",
    "ready": "ready",
    "pending": "pending",
    "in transit": "in_transit",
}

# Storage risk threshold (hours at terminal before alert)
_STORAGE_RISK_HOURS = 48


# ═══════════════════════════════════════════════════════════════
#  AWB PARSER
# ═══════════════════════════════════════════════════════════════

_AWB_RE = re.compile(r'^(\d{3})[\s\-]?(\d{8})$')


def parse_awb(awb_string):
    """
    Parse AWB string like "114-12345678" or "11412345678".

    Returns:
        dict with: prefix, serial, full, airline_name, terminal
        or None if invalid
    """
    awb_clean = (awb_string or "").strip().replace(" ", "")
    match = _AWB_RE.match(awb_clean)
    if not match:
        # Try with dash
        awb_clean = awb_clean.replace("-", "")
        if len(awb_clean) == 11 and awb_clean.isdigit():
            prefix = awb_clean[:3]
            serial = awb_clean[3:]
        else:
            return None
    else:
        prefix = match.group(1)
        serial = match.group(2)

    airline = AIRLINE_PREFIXES.get(prefix, {"name": f"Unknown ({prefix})", "terminal": "maman"})

    return {
        "prefix": prefix,
        "serial": serial,
        "full": f"{prefix}-{serial}",
        "airline_name": airline["name"],
        "terminal": airline["terminal"],
    }


# ═══════════════════════════════════════════════════════════════
#  MAMAN API CLIENT
# ═══════════════════════════════════════════════════════════════

_MAMAN_BASE = "https://mamanonline.maman.co.il/api/v1"
_MAMAN_TEST_BASE = "https://mamanonline.wsfreeze.co.il/api/v1"


class MamanClient:
    """REST API client for Maman cargo terminal at Ben Gurion."""

    def __init__(self, username, password, use_test=False):
        self._username = username
        self._password = password
        self._base = _MAMAN_TEST_BASE if use_test else _MAMAN_BASE
        self._token = None
        self._token_expiry = None

    def _authenticate(self):
        """POST /Account/authenticate → bearer token (short-lived)."""
        try:
            resp = requests.post(
                f"{self._base}/Account/authenticate",
                json={"username": self._username, "password": self._password},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token") or data.get("Token") or data.get("accessToken")
                # Assume 30-minute token life if not specified
                self._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=25)
                return True
            print(f"  ✈️ Maman auth failed: {resp.status_code} - {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"  ✈️ Maman auth error: {e}")
            return False

    def _get_token(self):
        """Get valid token, refreshing if expired."""
        if self._token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._token
        if self._authenticate():
            return self._token
        return None

    def _headers(self):
        token = self._get_token()
        if not token:
            return None
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get_awb_status(self, awb_number):
        """
        GET /Import/GetAWBStatus — get status of an AWB at Maman terminal.

        Returns dict with status fields or None on failure.
        """
        headers = self._headers()
        if not headers:
            return None

        awb_clean = awb_number.replace("-", "").replace(" ", "")
        try:
            resp = requests.get(
                f"{self._base}/Import/GetAWBStatus",
                params={"awbNumber": awb_clean},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"  ✈️ Maman AWB status error: {resp.status_code} - {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"  ✈️ Maman AWB status exception: {e}")
            return None

    def get_storage_list(self):
        """GET /General/GetStorageList — list of items in storage."""
        headers = self._headers()
        if not headers:
            return None
        try:
            resp = requests.get(
                f"{self._base}/General/GetStorageList",
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"  ✈️ Maman storage list error: {e}")
            return None

    def get_calculated_fees(self, awb_number, weight_kg=None):
        """POST /General/GetCalculatedFees — calculate storage/handling fees."""
        headers = self._headers()
        if not headers:
            return None
        try:
            payload = {"awbNumber": awb_number.replace("-", "").replace(" ", "")}
            if weight_kg:
                payload["weight"] = weight_kg
            resp = requests.post(
                f"{self._base}/General/GetCalculatedFees",
                json=payload,
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"  ✈️ Maman fees error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
#  SWISSPORT CLIENT (STUB)
# ═══════════════════════════════════════════════════════════════

class SwissportClient:
    """
    Stub client for Swissport cargo terminal at Ben Gurion.
    TODO: Check swissport.co.il for API access. Currently web portal
    only (login required). Handles FedEx, UPS, and some airlines.
    """

    def __init__(self):
        pass

    def get_awb_status(self, awb_number):
        """Stub — returns None until API access is available."""
        print(f"  ✈️ Swissport: No API yet for AWB {awb_number}")
        return None


# ═══════════════════════════════════════════════════════════════
#  FUTURE: Aviation Edge — real-time flight tracking
#  GET https://aviation-edge.com/v2/public/flights?key=KEY&arrIata=TLV
#  Covers pre-arrival ETA tracking (gap between departure and terminal).
#  $99/mo — not critical until Maman is live.
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  AWB REGISTRATION
# ═══════════════════════════════════════════════════════════════

def register_awb(db, awb_number, deal_id=None):
    """
    Register an AWB for polling. Called when tracker extracts an AWB from email.
    Creates/updates doc in tracker_awb_status collection.
    """
    parsed = parse_awb(awb_number)
    if not parsed:
        print(f"  ✈️ Invalid AWB: {awb_number}")
        return None

    doc_id = parsed["full"].replace("-", "_")
    now = datetime.now(timezone.utc).isoformat()

    existing = db.collection("tracker_awb_status").document(doc_id).get()
    if existing.exists:
        # Update deal_id if provided and not already set
        update = {"updated_at": now}
        if deal_id:
            update["deal_id"] = deal_id
        db.collection("tracker_awb_status").document(doc_id).update(update)
        print(f"  ✈️ AWB {parsed['full']} already registered, updated")
        return doc_id

    db.collection("tracker_awb_status").document(doc_id).set({
        "awb_number": parsed["full"],
        "awb_prefix": parsed["prefix"],
        "awb_serial": parsed["serial"],
        "airline_name": parsed["airline_name"],
        "terminal": parsed["terminal"],
        "deal_id": deal_id or "",
        "status": "registered",
        "status_normalized": "pending",
        "raw_status": "",
        "arrived_at": "",
        "released_at": "",
        "last_polled": "",
        "poll_count": 0,
        "alerts_sent": [],
        "storage_start": "",
        "fees": {},
        "maman_raw": {},
        "created_at": now,
        "updated_at": now,
    })
    print(f"  ✈️ AWB {parsed['full']} registered ({parsed['airline_name']} → {parsed['terminal']})")
    return doc_id


# ═══════════════════════════════════════════════════════════════
#  STATUS NORMALIZATION
# ═══════════════════════════════════════════════════════════════

def _normalize_status(raw_status):
    """Normalize Hebrew/English status string to standard status code."""
    if not raw_status:
        return "unknown"
    raw_lower = raw_status.strip().lower()
    for key, val in _STATUS_MAP.items():
        if key in raw_lower:
            return val
    return "unknown"


# ═══════════════════════════════════════════════════════════════
#  ALERT DETECTION
# ═══════════════════════════════════════════════════════════════

def _check_alerts(awb_doc, new_status, maman_data):
    """
    Check if any alerts should fire based on status change.

    Returns list of alert dicts: [{"type": "...", "message": "..."}]
    """
    alerts = []
    old_status = awb_doc.get("status_normalized", "pending")
    already_sent = set(awb_doc.get("alerts_sent", []))

    # Alert: AWB arrived at terminal
    if new_status in ("arrived", "at_terminal") and "awb_arrived" not in already_sent:
        alerts.append({
            "type": "awb_arrived",
            "message": f"✈️ AWB {awb_doc['awb_number']} הגיע למסוף {awb_doc.get('terminal', 'maman').upper()}",
        })

    # Alert: Customs hold
    if new_status in ("hold", "customs_hold") and "customs_hold" not in already_sent:
        alerts.append({
            "type": "customs_hold",
            "message": f"⚠️ AWB {awb_doc['awb_number']} מעוכב בבדיקת מכס",
        })

    # Alert: Storage risk (>48 hours at terminal)
    storage_start = awb_doc.get("storage_start", "")
    if storage_start and new_status not in ("released", "delivered", "customs_released"):
        try:
            start_dt = datetime.fromisoformat(storage_start)
            hours_stored = (datetime.now(timezone.utc) - start_dt).total_seconds() / 3600
            if hours_stored > _STORAGE_RISK_HOURS and "storage_risk" not in already_sent:
                alerts.append({
                    "type": "storage_risk",
                    "message": (
                        f"🚨 AWB {awb_doc['awb_number']} במסוף {hours_stored:.0f} שעות "
                        f"(>{_STORAGE_RISK_HOURS}h) — סיכון דמי אחסנה!"
                    ),
                })
        except (ValueError, TypeError):
            pass

    # Alert: Customs released
    if new_status in ("released", "customs_released") and "customs_released" not in already_sent:
        alerts.append({
            "type": "customs_released",
            "message": f"✅ AWB {awb_doc['awb_number']} שוחרר מהמכס — מוכן למסירה",
        })

    return alerts


# ═══════════════════════════════════════════════════════════════
#  POLLING
# ═══════════════════════════════════════════════════════════════

def poll_air_cargo(db, get_secret_func):
    """
    Poll all active AWBs via Maman API, update status, fire alerts.

    Returns dict with poll results.
    """
    # Get Maman credentials
    try:
        maman_user = get_secret_func("maman_username")
        maman_pass = get_secret_func("maman_password")
    except Exception:
        maman_user = None
        maman_pass = None

    maman = MamanClient(maman_user, maman_pass) if maman_user and maman_pass else None
    swissport = SwissportClient()

    if not maman:
        print("  ✈️ Air cargo: Maman credentials not configured — skipping poll")

    # Get all active AWBs
    try:
        awb_docs = list(
            db.collection("tracker_awb_status")
            .where("status_normalized", "not-in", ["delivered", "released", "customs_released"])
            .stream()
        )
    except Exception:
        # Fallback: get all non-delivered
        awb_docs = []
        try:
            all_docs = list(db.collection("tracker_awb_status").stream())
            for doc in all_docs:
                data = doc.to_dict()
                if data.get("status_normalized") not in ("delivered", "released", "customs_released"):
                    awb_docs.append(doc)
        except Exception as e:
            print(f"  ✈️ Air cargo: Error fetching AWBs: {e}")
            return {"status": "error", "error": str(e)}

    if not awb_docs:
        print("  ✈️ Air cargo: No active AWBs to poll")
        return {"status": "ok", "polled": 0, "alerts": 0}

    print(f"  ✈️ Air cargo: Polling {len(awb_docs)} active AWBs...")

    polled = 0
    total_alerts = []
    now = datetime.now(timezone.utc).isoformat()

    for doc in awb_docs:
        awb_data = doc.to_dict()
        awb_num = awb_data.get("awb_number", "")
        terminal = awb_data.get("terminal", "maman")

        # Route to correct terminal client
        if terminal == "swissport":
            result = swissport.get_awb_status(awb_num)
        elif maman:
            result = maman.get_awb_status(awb_num)
        else:
            result = None

        if result is None:
            # Update poll count even if no result
            db.collection("tracker_awb_status").document(doc.id).update({
                "last_polled": now,
                "poll_count": (awb_data.get("poll_count", 0) or 0) + 1,
                "updated_at": now,
            })
            polled += 1
            continue

        # Extract status from Maman response
        raw_status = (
            result.get("status") or result.get("Status") or
            result.get("statusDescription") or result.get("StatusDescription") or ""
        )
        new_status = _normalize_status(raw_status)

        # Detect arrival time
        storage_start = awb_data.get("storage_start", "")
        arrived_at = awb_data.get("arrived_at", "")
        if new_status in ("arrived", "at_terminal") and not arrived_at:
            arrived_at = now
            storage_start = now

        # Detect release time
        released_at = awb_data.get("released_at", "")
        if new_status in ("released", "customs_released") and not released_at:
            released_at = now

        # Check for alerts
        alerts = _check_alerts(awb_data, new_status, result)
        alert_types = [a["type"] for a in alerts]
        total_alerts.extend(alerts)

        # Update document
        update_data = {
            "status": raw_status,
            "status_normalized": new_status,
            "raw_status": raw_status,
            "last_polled": now,
            "poll_count": (awb_data.get("poll_count", 0) or 0) + 1,
            "maman_raw": result,
            "updated_at": now,
        }
        if arrived_at:
            update_data["arrived_at"] = arrived_at
        if storage_start:
            update_data["storage_start"] = storage_start
        if released_at:
            update_data["released_at"] = released_at
        if alert_types:
            update_data["alerts_sent"] = list(set(awb_data.get("alerts_sent", []) + alert_types))

        db.collection("tracker_awb_status").document(doc.id).update(update_data)
        polled += 1

        if alerts:
            for a in alerts:
                print(f"  ✈️ ALERT: {a['message']}")

        if new_status != awb_data.get("status_normalized", "pending"):
            print(f"  ✈️ AWB {awb_num}: {awb_data.get('status_normalized', 'pending')} → {new_status}")

    print(f"  ✈️ Air cargo poll complete: {polled} AWBs, {len(total_alerts)} alerts")
    return {"status": "ok", "polled": polled, "alerts": len(total_alerts), "alert_details": total_alerts}


# ═══════════════════════════════════════════════════════════════
#  SCHEDULER ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def poll_air_cargo_for_tracker(db, firestore_module, get_secret_func):
    """
    Entry point for rcb_tracker_poll scheduler.
    Called every 30 minutes alongside sea freight polling.
    """
    print("  ✈️ Air cargo tracker: starting poll cycle...")
    try:
        result = poll_air_cargo(db, get_secret_func)
        return result
    except Exception as e:
        print(f"  ✈️ Air cargo tracker error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
