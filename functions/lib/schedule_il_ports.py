"""
Daily Israeli Port Schedule Module
====================================
Aggregates vessel schedules for Israeli ports (Haifa, Ashdod, Eilat)
from multiple FREE data sources.

Sources (all FREE):
  1. Carrier Schedule APIs (via ocean_tracker.py) — Maersk, ZIM, Hapag-Lloyd, COSCO
  2. aisstream.io — Real-time AIS data (free API key)
  3. Haifa Port portal — haifa-port.ynadev.com (public)
  4. ZIM Expected Vessels — zim.com Israel page (public)
  5. TaskYam active deals — vessel/ETA data from tracker_deals
  6. cc@rpa-port.co.il emails — schedule notifications

Firestore collections:
  - port_schedules: one doc per vessel visit per port
  - daily_port_report: aggregate per port per day

Session C — Assignment: Daily Schedule per IL Ports
R.P.A.PORT LTD — February 2026
"""

import json
import re
import time
import hashlib
import requests
from datetime import datetime, timedelta, timezone

# Israel timezone support
try:
    from zoneinfo import ZoneInfo
    _IL_TZ = ZoneInfo("Asia/Jerusalem")
except ImportError:
    _IL_TZ = timezone(timedelta(hours=2))  # Fallback UTC+2


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IL_PORTS = {
    "ILHFA": {"name_en": "Haifa", "name_he": "חיפה", "unlocode": "ILHFA"},
    "ILASD": {"name_en": "Ashdod", "name_he": "אשדוד", "unlocode": "ILASD"},
    "ILELT": {"name_en": "Eilat", "name_he": "אילת", "unlocode": "ILELT"},
}

# Major origin ports for Israel-bound schedules
MAJOR_ORIGINS = [
    "CNSHA",  # Shanghai
    "CNNGB",  # Ningbo
    "CNYTN",  # Yantian/Shenzhen
    "SGSIN",  # Singapore
    "TRIST",  # Istanbul
    "GRPIR",  # Piraeus
    "ITGOA",  # Gioia Tauro
    "EGPSD",  # Port Said
    "ESVLC",  # Valencia
    "DEHAM",  # Hamburg
    "NLRTM",  # Rotterdam
    "BEANR",  # Antwerp
    "INMUN",  # Mumbai (Nhava Sheva)
    "KRPUS",  # Busan
    "USNYC",  # New York
]

# AIS bounding boxes for Israeli ports (lat/lon)
AIS_BOUNDING_BOXES = {
    "ILHFA": [[32.75, 34.90], [32.90, 35.10]],  # Haifa Bay
    "ILASD": [[31.75, 34.55], [31.88, 34.75]],  # Ashdod area
    "ILELT": [[29.50, 34.90], [29.60, 35.00]],  # Eilat Gulf
}

# Vessel type codes that are cargo-related (filter AIS noise)
CARGO_VESSEL_TYPES = {
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79,  # Cargo ships
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89,  # Tankers
}

# Schedule email keywords
SCHEDULE_KEYWORDS_EN = [
    'vessel schedule', 'sailing schedule', 'ship schedule',
    'port schedule', 'arrival schedule', 'departure schedule',
    'expected vessels', 'vessel arrival', 'vessel departure',
    'eta', 'etd', 'berth', 'berthing', 'anchorage',
    'working plan', 'work schedule', 'daily report',
    'port call', 'port rotation',
]
SCHEDULE_KEYWORDS_HE = [
    'לוח הפלגות', 'סידור עבודה', 'הגעת אוניה', 'עזיבת אוניה',
    'תכנית עבודה', 'דו"ח יומי', 'עוגנת', 'רציף',
    'אוניות צפויות', 'לוח שיוט',
]


# ---------------------------------------------------------------------------
# Source 1: Carrier Schedule APIs (via ocean_tracker.py)
# ---------------------------------------------------------------------------

def _query_carrier_schedules(dest_port, date_from, get_secret_func):
    """
    Query carrier APIs for vessel schedules arriving at an Israeli port.
    Uses existing ocean_tracker.query_vessel_schedule().
    """
    results = []
    try:
        from lib.ocean_tracker import query_vessel_schedule
    except ImportError:
        print("  [SCHEDULE] ocean_tracker not available")
        return results

    # Query each major carrier for schedules to this port
    for origin in MAJOR_ORIGINS[:5]:  # Limit to top 5 origins to control API costs
        try:
            schedules = query_vessel_schedule(
                origin_port=origin,
                dest_port=dest_port,
                date_from=date_from,
                get_secret_func=get_secret_func,
            )
            if schedules:
                for s in schedules:
                    if isinstance(s, dict):
                        s["source"] = s.get("source", "carrier_api")
                        s["dest_port"] = dest_port
                        results.append(s)
        except Exception as e:
            print(f"  [SCHEDULE] Carrier query {origin}→{dest_port} error: {e}")

    print(f"  [SCHEDULE] Carrier APIs: {len(results)} schedules for {dest_port}")
    return results


# ---------------------------------------------------------------------------
# Source 2: AIS Stream (aisstream.io — FREE)
# ---------------------------------------------------------------------------

def _query_ais_vessels(port_code, get_secret_func):
    """
    Query aisstream.io for vessels near an Israeli port.
    Uses REST API (not WebSocket) for one-shot queries.
    Returns list of vessel position dicts.
    """
    results = []
    try:
        api_key = get_secret_func("AISSTREAM_API_KEY")
    except Exception:
        return results  # No key configured yet

    if not api_key or port_code not in AIS_BOUNDING_BOXES:
        return results

    bbox = AIS_BOUNDING_BOXES[port_code]
    try:
        # aisstream.io REST endpoint for latest positions in bounding box
        resp = requests.get(
            "https://api.aisstream.io/v0/vessels",
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "lat_min": bbox[0][0],
                "lon_min": bbox[0][1],
                "lat_max": bbox[1][0],
                "lon_max": bbox[1][1],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            vessels = data if isinstance(data, list) else data.get("vessels", [])
            for v in vessels:
                if not isinstance(v, dict):
                    continue
                vessel_type = v.get("vessel_type", 0)
                if vessel_type and vessel_type not in CARGO_VESSEL_TYPES:
                    continue
                results.append({
                    "vessel_name": v.get("name", "").strip(),
                    "mmsi": v.get("mmsi", ""),
                    "imo": v.get("imo", ""),
                    "vessel_type": v.get("vessel_type_text", ""),
                    "flag": v.get("flag", ""),
                    "destination": v.get("destination", ""),
                    "eta": v.get("eta", ""),
                    "lat": v.get("latitude", 0),
                    "lon": v.get("longitude", 0),
                    "speed": v.get("speed", 0),
                    "heading": v.get("heading", 0),
                    "source": "aisstream",
                    "port_code": port_code,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        else:
            print(f"  [SCHEDULE] AIS API error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  [SCHEDULE] AIS query error for {port_code}: {e}")

    print(f"  [SCHEDULE] AIS: {len(results)} vessels near {port_code}")
    return results


# ---------------------------------------------------------------------------
# Source 3: Haifa Port Portal (haifa-port.ynadev.com — FREE public)
# ---------------------------------------------------------------------------

def _query_haifa_port_schedule():
    """
    Attempt to fetch vessel schedule from Haifa Port digital portal.
    The portal is JavaScript-rendered; we try to find the underlying API.
    Returns list of schedule dicts or empty list.
    """
    results = []
    urls_to_try = [
        "https://haifa-port.ynadev.com/api/ship-schedules",
        "https://haifa-port.ynadev.com/api/ships",
        "https://haifa-port.ynadev.com/api/work-schedule",
    ]

    for url in urls_to_try:
        try:
            resp = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "RPA-PORT-Schedule/1.0",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                vessels = data if isinstance(data, list) else data.get("data", [])
                for v in vessels:
                    if not isinstance(v, dict):
                        continue
                    results.append({
                        "vessel_name": v.get("shipName", v.get("vessel_name", "")),
                        "lloyds_number": v.get("lloydNumber", ""),
                        "eta": v.get("eta", v.get("arrivalDate", "")),
                        "etd": v.get("etd", v.get("departureDate", "")),
                        "berth": v.get("berth", v.get("berthNumber", "")),
                        "agent": v.get("agent", v.get("agentName", "")),
                        "cargo_type": v.get("cargoType", ""),
                        "shipping_line": v.get("shippingLine", v.get("carrier", "")),
                        "source": "haifa_port",
                        "port_code": "ILHFA",
                    })
                if results:
                    print(f"  [SCHEDULE] Haifa Port: {len(results)} vessels from {url}")
                    return results
        except Exception:
            continue

    # Fallback: try the HTML page and extract structured data
    try:
        resp = requests.get(
            "https://haifa-port.ynadev.com/en/ship-schedules/",
            headers={"User-Agent": "RPA-PORT-Schedule/1.0"},
            timeout=15,
        )
        if resp.status_code == 200 and resp.text:
            # Look for JSON data embedded in the page
            json_match = re.search(
                r'(?:window\.__INITIAL_STATE__|window\.scheduleData|var\s+data)\s*=\s*(\[.*?\]);',
                resp.text, re.DOTALL
            )
            if json_match:
                data = json.loads(json_match.group(1))
                for v in data:
                    if isinstance(v, dict):
                        results.append({
                            "vessel_name": v.get("shipName", v.get("name", "")),
                            "eta": v.get("eta", v.get("arrival", "")),
                            "etd": v.get("etd", v.get("departure", "")),
                            "berth": v.get("berth", ""),
                            "source": "haifa_port",
                            "port_code": "ILHFA",
                        })
    except Exception as e:
        print(f"  [SCHEDULE] Haifa Port HTML parse error: {e}")

    print(f"  [SCHEDULE] Haifa Port: {len(results)} vessels")
    return results


# ---------------------------------------------------------------------------
# Source 4: ZIM Expected Vessels (zim.com — FREE public page)
# ---------------------------------------------------------------------------

def _query_zim_expected_vessels():
    """
    Attempt to fetch ZIM's expected vessels page for Israel.
    This is a public page — we try to get structured data from it.
    """
    results = []
    try:
        resp = requests.get(
            "https://www.zim.com/global-network/asia-oceania/israel/expected-vessels",
            headers={
                "Accept": "text/html",
                "User-Agent": "RPA-PORT-Schedule/1.0",
            },
            timeout=15,
        )
        if resp.status_code == 200 and resp.text:
            # Look for embedded JSON data or structured table data
            json_match = re.search(
                r'(?:window\.__data__|expectedVesselsData|var\s+vessels)\s*=\s*(\[.*?\]);',
                resp.text, re.DOTALL
            )
            if json_match:
                data = json.loads(json_match.group(1))
                for v in data:
                    if isinstance(v, dict):
                        results.append({
                            "vessel_name": v.get("vesselName", v.get("name", "")),
                            "voyage": v.get("voyage", ""),
                            "port_code": _resolve_zim_port(v.get("port", "")),
                            "eta": v.get("eta", ""),
                            "etd": v.get("etd", ""),
                            "service": v.get("service", v.get("tradeLane", "")),
                            "shipping_line": "ZIM",
                            "source": "zim_expected",
                        })

            # Fallback: try regex on HTML table rows
            if not results:
                rows = re.findall(
                    r'<tr[^>]*>(.*?)</tr>', resp.text, re.DOTALL
                )
                for row in rows:
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                    if len(cells) >= 4:
                        vessel = re.sub(r'<[^>]+>', '', cells[0]).strip()
                        port_text = re.sub(r'<[^>]+>', '', cells[1]).strip()
                        eta_text = re.sub(r'<[^>]+>', '', cells[2]).strip()
                        if vessel and port_text:
                            results.append({
                                "vessel_name": vessel,
                                "port_code": _resolve_zim_port(port_text),
                                "eta": eta_text,
                                "shipping_line": "ZIM",
                                "source": "zim_expected",
                            })
    except Exception as e:
        print(f"  [SCHEDULE] ZIM expected vessels error: {e}")

    print(f"  [SCHEDULE] ZIM expected: {len(results)} vessels")
    return results


def _resolve_zim_port(port_text):
    """Resolve port text to IL port code."""
    if not port_text:
        return ""
    t = port_text.lower().strip()
    if "haifa" in t or "חיפה" in t:
        return "ILHFA"
    elif "ashdod" in t or "אשדוד" in t:
        return "ILASD"
    elif "eilat" in t or "אילת" in t:
        return "ILELT"
    return port_text


# ---------------------------------------------------------------------------
# Source 5: TaskYam active deals — extract vessel/port data
# ---------------------------------------------------------------------------

def _extract_from_active_deals(db, port_code):
    """
    Extract vessel schedule data from active tracker deals
    that match the given port. TaskYam data is 100% authoritative.
    """
    results = []
    try:
        deals_ref = db.collection("tracker_deals")
        query = deals_ref.where("status", "==", "active")
        if port_code:
            query = query.where("port", "==", port_code)

        docs = query.limit(100).stream()
        for doc in docs:
            deal = doc.to_dict()
            if not deal:
                continue
            vessel = deal.get("vessel_name", "")
            if not vessel:
                continue

            results.append({
                "vessel_name": vessel,
                "voyage": deal.get("voyage", ""),
                "port_code": deal.get("port", port_code),
                "eta": deal.get("eta", ""),
                "etd": deal.get("etd", ""),
                "shipping_line": deal.get("shipping_line", ""),
                "direction": deal.get("direction", ""),
                "bol_number": deal.get("bol_number", ""),
                "containers": len(deal.get("containers", [])),
                "manifest_number": deal.get("manifest_number", ""),
                "source": "taskyam_deals",
                "confidence": "high",
            })
    except Exception as e:
        print(f"  [SCHEDULE] Active deals extraction error: {e}")

    print(f"  [SCHEDULE] TaskYam deals: {len(results)} vessels at {port_code}")
    return results


# ---------------------------------------------------------------------------
# Source 6: Email schedule parsing
# ---------------------------------------------------------------------------

def is_schedule_email(subject, body, from_email):
    """
    Detect if an email contains vessel/port schedule information.
    Called from main.py email processing pipeline.
    """
    text = f"{subject} {body}".lower()

    # Check English keywords
    en_hits = sum(1 for kw in SCHEDULE_KEYWORDS_EN if kw in text)
    # Check Hebrew keywords
    he_hits = sum(1 for kw in SCHEDULE_KEYWORDS_HE if kw in text)

    # Must have at least 2 keyword hits
    if en_hits + he_hits < 2:
        return False

    # Boost if from known port authority or shipping line
    from_lower = from_email.lower() if from_email else ""
    port_senders = ['haifaport.co.il', 'ashdodport.co.il', 'israports.co.il']
    line_senders = ['zim.com', 'maersk.com', 'hapag-lloyd.com', 'cma-cgm.com',
                    'cosco.com', 'one-line.com', 'evergreen-marine.com']
    if any(s in from_lower for s in port_senders + line_senders):
        return True

    return en_hits + he_hits >= 3


def parse_schedule_from_email(subject, body, from_email):
    """
    Extract vessel schedule data from an email body.
    Returns list of schedule dicts.
    """
    results = []
    text = f"{subject}\n{body}"

    # Extract vessel names (patterns: M/V VESSEL_NAME, MV VESSEL_NAME, VESSEL: name)
    vessel_patterns = [
        r'(?:M/?V|VESSEL|אוניה|אוניית)\s+[:\-]?\s*([A-Z][A-Z0-9\s\-\.]{3,30})',
        r'(?:SHIP|שם אוניה)\s*[:\-]\s*([A-Z][A-Z0-9\s\-\.]{3,30})',
    ]
    vessels = set()
    for pat in vessel_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            v = m.group(1).strip().rstrip('.,;:')
            if len(v) > 3:
                vessels.add(v)

    # Extract ETAs
    eta_pattern = r'ETA\s*[:\-]?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}(?:\s+\d{1,2}:\d{2})?)'
    etas = re.findall(eta_pattern, text, re.IGNORECASE)

    # Extract ETDs
    etd_pattern = r'ETD\s*[:\-]?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}(?:\s+\d{1,2}:\d{2})?)'
    etds = re.findall(etd_pattern, text, re.IGNORECASE)

    # Extract port references
    port_code = ""
    port_patterns = {
        "ILHFA": r'(?:haifa|חיפה|ILHFA)',
        "ILASD": r'(?:ashdod|אשדוד|ILASD)',
        "ILELT": r'(?:eilat|אילת|ILELT)',
    }
    for code, pat in port_patterns.items():
        if re.search(pat, text, re.IGNORECASE):
            port_code = code
            break

    # Extract voyage numbers
    voyage_pattern = r'(?:VOY(?:AGE)?|V)\s*[:\-#]?\s*([A-Z0-9]{2,10})'
    voyages = re.findall(voyage_pattern, text, re.IGNORECASE)

    # Build schedule entries
    for i, vessel in enumerate(vessels):
        entry = {
            "vessel_name": vessel,
            "port_code": port_code,
            "eta": etas[i] if i < len(etas) else (etas[0] if etas else ""),
            "etd": etds[i] if i < len(etds) else (etds[0] if etds else ""),
            "voyage": voyages[i] if i < len(voyages) else (voyages[0] if voyages else ""),
            "shipping_line": _identify_sender_carrier(from_email),
            "source": "email",
            "source_email": from_email,
            "confidence": "medium",
        }
        results.append(entry)

    return results


def _identify_sender_carrier(from_email):
    """Identify carrier from email sender domain."""
    if not from_email:
        return ""
    domain = from_email.lower().split("@")[-1] if "@" in from_email else ""
    carrier_domains = {
        "zim.com": "ZIM",
        "maersk.com": "Maersk",
        "hapag-lloyd.com": "Hapag-Lloyd",
        "cma-cgm.com": "CMA CGM",
        "cosco.com": "COSCO",
        "one-line.com": "ONE",
        "evergreen-marine.com": "Evergreen",
        "msc.com": "MSC",
        "haifaport.co.il": "Haifa Port",
        "ashdodport.co.il": "Ashdod Port",
        "israports.co.il": "IsraPorts",
    }
    for d, carrier in carrier_domains.items():
        if d in domain:
            return carrier
    return ""


# ---------------------------------------------------------------------------
# Aggregation & Deduplication
# ---------------------------------------------------------------------------

def _make_schedule_key(entry):
    """
    Create deduplication key for a schedule entry.
    Key: (port_code, vessel_name_normalized, eta_date)
    """
    vessel = (entry.get("vessel_name", "") or "").upper().strip()
    vessel = re.sub(r'\s+', ' ', vessel)
    port = (entry.get("port_code", "") or "").upper().strip()
    eta = entry.get("eta", "") or ""
    # Normalize ETA to date only
    eta_date = ""
    if eta:
        eta_clean = re.sub(r'[T ].*', '', str(eta)[:10])
        eta_date = eta_clean
    return f"{port}_{vessel}_{eta_date}"


def _merge_schedule_entries(entries):
    """
    Merge schedule entries from multiple sources.
    Priority: taskyam_deals > carrier_api > haifa_port > zim_expected > email > aisstream
    """
    SOURCE_PRIORITY = {
        "taskyam_deals": 1,
        "carrier_api": 2,
        "haifa_port": 3,
        "zim_expected": 4,
        "email": 5,
        "aisstream": 6,
    }

    merged = {}
    for entry in entries:
        key = _make_schedule_key(entry)
        if not key or key == "__":
            continue

        source = entry.get("source", "unknown")
        priority = SOURCE_PRIORITY.get(source, 99)

        if key not in merged:
            merged[key] = {**entry, "_sources": [source], "_priority": priority}
        else:
            existing = merged[key]
            existing["_sources"].append(source)
            merge_fields = ["etd", "eta", "berth", "agent", "voyage", "shipping_line",
                            "cargo_type", "bol_number", "manifest_number", "imo",
                            "lloyds_number", "containers", "direction"]
            if priority < existing.get("_priority", 99):
                # Higher-priority source replaces, but keep fields from lower-priority
                sources = existing["_sources"]
                old_data = {f: existing[f] for f in merge_fields if existing.get(f)}
                merged[key] = {**entry, "_sources": sources, "_priority": priority}
                # Fill in any fields the higher-priority entry is missing
                for field, val in old_data.items():
                    if not merged[key].get(field):
                        merged[key][field] = val
            else:
                # Fill missing fields from lower-priority source
                for field in merge_fields:
                    if not existing.get(field) and entry.get(field):
                        existing[field] = entry[field]

    return list(merged.values())


# ---------------------------------------------------------------------------
# Firestore Storage
# ---------------------------------------------------------------------------

def _store_port_schedule(db, schedule_entry):
    """Store or update a single port schedule entry in Firestore."""
    key = _make_schedule_key(schedule_entry)
    if not key or key == "__":
        return

    doc_id = hashlib.md5(key.encode()).hexdigest()[:16]
    doc_ref = db.collection("port_schedules").document(doc_id)

    # Clean up internal fields
    entry = {k: v for k, v in schedule_entry.items() if not k.startswith("_")}
    entry["schedule_key"] = key
    entry["sources"] = schedule_entry.get("_sources", [])
    entry["source_count"] = len(entry["sources"])
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Convert ETA/ETD to Israel time if possible
    for field in ["eta", "etd"]:
        val = entry.get(field, "")
        if val:
            il_time = _to_israel_time_str(val)
            if il_time:
                entry[f"{field}_israel"] = il_time

    # Confidence scoring
    sources = entry["sources"]
    if "taskyam_deals" in sources:
        entry["confidence"] = "high"
    elif len(sources) >= 2:
        entry["confidence"] = "high"
    elif any(s in sources for s in ["carrier_api", "haifa_port"]):
        entry["confidence"] = "medium"
    else:
        entry["confidence"] = "low"

    doc_ref.set(entry, merge=True)
    return doc_id


def _store_daily_report(db, port_code, report_date, vessels):
    """Store the daily aggregated port report."""
    doc_id = f"{port_code}_{report_date}"
    port_info = IL_PORTS.get(port_code, {})

    # Count by carrier
    carrier_counts = {}
    for v in vessels:
        carrier = v.get("shipping_line", "Unknown")
        carrier_counts[carrier] = carrier_counts.get(carrier, 0) + 1

    # Count by direction
    incoming = sum(1 for v in vessels if v.get("direction") != "export")
    outgoing = sum(1 for v in vessels if v.get("direction") == "export")

    report = {
        "port_code": port_code,
        "port_name_en": port_info.get("name_en", ""),
        "port_name_he": port_info.get("name_he", ""),
        "report_date": report_date,
        "total_vessels": len(vessels),
        "incoming_vessels": incoming,
        "outgoing_vessels": outgoing,
        "vessels": [_clean_vessel_summary(v) for v in vessels],
        "carrier_breakdown": carrier_counts,
        "sources_used": list(set(
            s for v in vessels for s in v.get("_sources", [v.get("source", "")])
        )),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    db.collection("daily_port_report").document(doc_id).set(report, merge=True)
    return doc_id


def _clean_vessel_summary(entry):
    """Clean a vessel entry for storage in daily report."""
    return {
        "vessel_name": entry.get("vessel_name", ""),
        "shipping_line": entry.get("shipping_line", ""),
        "eta": entry.get("eta", ""),
        "etd": entry.get("etd", ""),
        "eta_israel": entry.get("eta_israel", ""),
        "etd_israel": entry.get("etd_israel", ""),
        "voyage": entry.get("voyage", ""),
        "berth": entry.get("berth", ""),
        "direction": entry.get("direction", ""),
        "containers": entry.get("containers", 0),
        "confidence": entry.get("confidence", "low"),
        "sources": entry.get("_sources", [entry.get("source", "")]),
    }


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _to_israel_time_str(ts_str):
    """Convert a timestamp string to Israel time display string."""
    if not ts_str:
        return ""
    try:
        # Try ISO format
        if "T" in str(ts_str):
            dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        else:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"]:
                try:
                    dt = datetime.strptime(str(ts_str)[:10], fmt)
                    dt = dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            else:
                return ""

        # Convert to Israel time
        if hasattr(_IL_TZ, 'key'):  # zoneinfo
            il_dt = dt.astimezone(_IL_TZ)
        else:
            il_dt = dt + timedelta(hours=2)  # Simplified fallback

        return il_dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _today_str():
    """Get today's date in YYYY-MM-DD format (Israel time)."""
    now = datetime.now(timezone.utc)
    if hasattr(_IL_TZ, 'key'):
        now = now.astimezone(_IL_TZ)
    else:
        now = now + timedelta(hours=2)
    return now.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Main Entry Points
# ---------------------------------------------------------------------------

def build_daily_port_schedule(db, port_code, get_secret_func=None):
    """
    Build daily schedule for a single Israeli port.
    Queries all available sources, merges, deduplicates, stores.

    Args:
        db: Firestore client
        port_code: str — "ILHFA", "ILASD", or "ILELT"
        get_secret_func: callable to get API secrets

    Returns:
        dict with port_code, date, vessel_count, report_id
    """
    if port_code not in IL_PORTS:
        return {"error": f"Unknown port: {port_code}"}

    t0 = time.time()
    today = _today_str()
    port_info = IL_PORTS[port_code]
    print(f"  [SCHEDULE] Building daily schedule for {port_info['name_en']} ({port_code}) — {today}")

    all_entries = []

    # Source 1: Carrier APIs
    if get_secret_func:
        try:
            carrier_results = _query_carrier_schedules(port_code, today, get_secret_func)
            all_entries.extend(carrier_results)
        except Exception as e:
            print(f"  [SCHEDULE] Carrier API source error: {e}")

    # Source 2: AIS data
    if get_secret_func:
        try:
            ais_results = _query_ais_vessels(port_code, get_secret_func)
            all_entries.extend(ais_results)
        except Exception as e:
            print(f"  [SCHEDULE] AIS source error: {e}")

    # Source 3: Haifa Port portal (only for Haifa)
    if port_code == "ILHFA":
        try:
            haifa_results = _query_haifa_port_schedule()
            all_entries.extend(haifa_results)
        except Exception as e:
            print(f"  [SCHEDULE] Haifa Port source error: {e}")

    # Source 4: ZIM expected vessels (for all ports)
    try:
        zim_results = _query_zim_expected_vessels()
        # Filter for this port
        for r in zim_results:
            if r.get("port_code") == port_code or not r.get("port_code"):
                all_entries.append(r)
    except Exception as e:
        print(f"  [SCHEDULE] ZIM expected source error: {e}")

    # Source 5: TaskYam active deals
    try:
        deal_results = _extract_from_active_deals(db, port_code)
        all_entries.extend(deal_results)
    except Exception as e:
        print(f"  [SCHEDULE] TaskYam deals source error: {e}")

    # Merge and deduplicate
    merged = _merge_schedule_entries(all_entries)

    # Store individual schedule entries
    stored_count = 0
    for entry in merged:
        try:
            _store_port_schedule(db, entry)
            stored_count += 1
        except Exception as e:
            print(f"  [SCHEDULE] Store error: {e}")

    # Store daily report
    report_id = _store_daily_report(db, port_code, today, merged)

    elapsed = time.time() - t0
    print(f"  [SCHEDULE] {port_info['name_en']}: {len(merged)} vessels from {len(all_entries)} raw entries in {elapsed:.1f}s")

    return {
        "port_code": port_code,
        "port_name": port_info["name_en"],
        "date": today,
        "vessel_count": len(merged),
        "raw_entries": len(all_entries),
        "stored": stored_count,
        "report_id": report_id,
        "elapsed_seconds": round(elapsed, 1),
    }


def build_all_port_schedules(db, get_secret_func=None):
    """
    Build daily schedules for ALL Israeli ports.
    Called by the scheduled function (e.g., daily at 02:00 Israel time).
    """
    t0 = time.time()
    print("[SCHEDULE] ═══ Building daily schedules for all Israeli ports ═══")

    results = {}
    for port_code in IL_PORTS:
        try:
            result = build_daily_port_schedule(db, port_code, get_secret_func)
            results[port_code] = result
        except Exception as e:
            print(f"[SCHEDULE] Error building schedule for {port_code}: {e}")
            results[port_code] = {"error": str(e)}

    elapsed = time.time() - t0
    total_vessels = sum(r.get("vessel_count", 0) for r in results.values())
    print(f"[SCHEDULE] ═══ Done: {total_vessels} vessels across {len(results)} ports in {elapsed:.1f}s ═══")

    return results


def process_schedule_email(db, subject, body, from_email, msg_id):
    """
    Process an incoming schedule email and store extracted data.
    Called from main.py email pipeline when is_schedule_email() returns True.
    """
    schedules = parse_schedule_from_email(subject, body, from_email)
    if not schedules:
        print(f"  [SCHEDULE] No schedule data extracted from email")
        return 0

    stored = 0
    for entry in schedules:
        entry["email_msg_id"] = msg_id
        entry["extracted_at"] = datetime.now(timezone.utc).isoformat()
        try:
            _store_port_schedule(db, entry)
            stored += 1
        except Exception as e:
            print(f"  [SCHEDULE] Store error: {e}")

    print(f"  [SCHEDULE] Extracted {stored} schedule entries from email")
    return stored


# ---------------------------------------------------------------------------
# Daily Report Email Template
# ---------------------------------------------------------------------------

def build_schedule_email_html(db, port_code=None):
    """
    Build HTML email with daily port schedule report.
    If port_code is None, includes all ports.
    """
    today = _today_str()
    ports = [port_code] if port_code else list(IL_PORTS.keys())

    sections = []
    for pc in ports:
        doc_id = f"{pc}_{today}"
        doc = db.collection("daily_port_report").document(doc_id).get()
        if not doc.exists:
            continue
        report = doc.to_dict()
        sections.append(_build_port_section_html(report))

    if not sections:
        return None

    html = f"""
    <div dir="rtl" style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px">
      <h2 style="color:#1a237e;border-bottom:3px solid #1a237e;padding-bottom:10px">
        🚢 דו"ח לוח זמנים יומי — נמלי ישראל
      </h2>
      <p style="color:#666;font-size:13px">תאריך: {today} | עודכן: {datetime.now(timezone.utc).strftime('%H:%M')} UTC</p>
      {''.join(sections)}
      <hr style="border:1px solid #e0e0e0;margin:20px 0">
      <p style="color:#999;font-size:11px;text-align:center">
        Powered by RPA-PORT Schedule Engine | Sources: TaskYam, Carrier APIs, AIS, Port Authorities
      </p>
    </div>
    """
    return html


def _build_port_section_html(report):
    """Build HTML section for one port's daily report."""
    port_name = report.get("port_name_he", report.get("port_code", ""))
    vessels = report.get("vessels", [])
    total = report.get("total_vessels", 0)
    carrier_breakdown = report.get("carrier_breakdown", {})

    if not vessels:
        return f"""
        <div style="margin:20px 0;padding:15px;background:#f5f5f5;border-radius:8px">
          <h3 style="color:#333">⚓ {port_name}</h3>
          <p style="color:#999">אין אוניות צפויות להיום</p>
        </div>
        """

    # Vessel table rows
    rows = []
    for v in sorted(vessels, key=lambda x: x.get("eta", "") or "zzzz"):
        eta_display = v.get("eta_israel", "") or v.get("eta", "") or "—"
        etd_display = v.get("etd_israel", "") or v.get("etd", "") or "—"
        confidence = v.get("confidence", "low")
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
        sources_count = len(v.get("sources", []))

        rows.append(f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0">{v.get('vessel_name', '—')}</td>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0">{v.get('shipping_line', '—')}</td>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0">{eta_display}</td>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0">{etd_display}</td>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0">{v.get('voyage', '—')}</td>
          <td style="padding:8px;border-bottom:1px solid #e0e0e0;text-align:center">{conf_icon} {sources_count}</td>
        </tr>
        """)

    # Carrier summary
    carrier_chips = " ".join(
        f'<span style="background:#e8eaf6;color:#1a237e;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px">'
        f'{carrier}: {count}</span>'
        for carrier, count in sorted(carrier_breakdown.items(), key=lambda x: -x[1])
    )

    return f"""
    <div style="margin:20px 0;padding:15px;background:#fafafa;border-radius:8px;border-left:4px solid #1a237e">
      <h3 style="color:#1a237e;margin-top:0">⚓ {port_name} — {total} אוניות</h3>
      <div style="margin-bottom:10px">{carrier_chips}</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="background:#e8eaf6">
            <th style="padding:8px;text-align:right">אוניה</th>
            <th style="padding:8px;text-align:right">חברת שיט</th>
            <th style="padding:8px;text-align:right">ETA</th>
            <th style="padding:8px;text-align:right">ETD</th>
            <th style="padding:8px;text-align:right">מסע</th>
            <th style="padding:8px;text-align:center">אמינות</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


# ---------------------------------------------------------------------------
# Utility: Get schedule for a specific vessel
# ---------------------------------------------------------------------------

def get_vessel_schedule(db, vessel_name, port_code=None):
    """
    Look up schedule entries for a specific vessel.
    Useful for cross-referencing with tracker deals.
    """
    results = []
    query = db.collection("port_schedules")

    # Firestore doesn't support case-insensitive queries,
    # so we search with uppercase vessel name
    docs = query.where("vessel_name", "==", vessel_name.upper().strip()).limit(10).stream()
    for doc in docs:
        entry = doc.to_dict()
        if port_code and entry.get("port_code") != port_code:
            continue
        entry["doc_id"] = doc.id
        results.append(entry)

    return results


def get_daily_report(db, port_code, date=None):
    """
    Get the daily port report for a specific port and date.
    """
    if not date:
        date = _today_str()
    doc_id = f"{port_code}_{date}"
    doc = db.collection("daily_port_report").document(doc_id).get()
    if doc.exists:
        return doc.to_dict()
    return None
