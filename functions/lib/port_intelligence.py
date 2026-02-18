"""
Block I: Port Intelligence — I1 (Deal-Schedule Linker) + I2 (Direction-Aware Views)
====================================================================================

I1: Links tracker_deals to port_schedules by vessel name + port code.
    Returns linkage data (schedule_ref, berth, confidence, schedule change detection).

I2: Builds direction-aware intelligence views for each deal type:
    - SEA_IMPORT: ETA, discharge, customs, D/O, storage risk, congestion
    - SEA_EXPORT: cutoffs, ETD, loading, customs, congestion
    - AIR_IMPORT: flight ETA, terminal, AWB status, customs, storage risk
    - AIR_EXPORT: cutoffs, ETD, AWB status

Data consolidation (critical rule):
    Multiple sources may report the same field (ETA, ETD, berth, etc.).
    We do NOT return all raw results. Instead:
      - Single best answer: when sources agree or one is authoritative
      - Range with consensus: when sources disagree, show range + note
    Source priority: TaskYam > port_portal > carrier_api > schedule_email > AIS > deal_email

Hard constraints (Session 43):
    - NO emails sent
    - NO alerts triggered or queued
    - NO main.py changes
    - Data computation only — pure functions returning dicts
"""

import re
from datetime import datetime, timezone, timedelta
from collections import Counter

# ── Israel Timezone ──
try:
    from zoneinfo import ZoneInfo
    IL_TZ = ZoneInfo("Asia/Jerusalem")
except ImportError:
    IL_TZ = None

_IL_STANDARD = timedelta(hours=2)
_IL_SUMMER = timedelta(hours=3)


# ═══════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════

# Ports supported for sea cargo intelligence
SEA_PORTS = {
    "ILHFA": {"name_en": "Haifa", "name_he": "חיפה"},
    "ILASD": {"name_en": "Ashdod", "name_he": "אשדוד"},
}

# Air cargo facility
AIR_PORTS = {
    "ILLIB": {"name_en": "Ben Gurion Airport", "name_he": "נתב\"ג"},
    "LLBG": {"name_en": "Ben Gurion Airport", "name_he": "נתב\"ג"},
    "BEN_GURION": {"name_en": "Ben Gurion Airport", "name_he": "נתב\"ג"},
}

# Congestion thresholds (vessel count at port on same day)
CONGESTION_BUSY = 15
CONGESTION_CONGESTED = 25

# Storage risk thresholds (days at port without cargo_exit)
STORAGE_NOTICE_DAYS = 2    # "2 more days before storage charges"
STORAGE_WARNING_DAYS = 3   # "must be taken out tomorrow"
STORAGE_CRITICAL_DAYS = 4  # storage charges apply

# Air cargo storage threshold (hours at terminal)
AIR_STORAGE_NOTICE_HOURS = 24
AIR_STORAGE_WARNING_HOURS = 36
AIR_STORAGE_CRITICAL_HOURS = 48

# Schedule change detection threshold
SCHEDULE_CHANGE_HOURS = 2

# Fuzzy match max Levenshtein distance
FUZZY_MAX_DISTANCE = 2

# Source priority for data consolidation (lower = more authoritative)
# When multiple sources report the same field, the highest-priority source wins.
SOURCE_PRIORITY = {
    "taskyam_deals": 1,     # Israeli port authority system — always authoritative
    "port_portal": 2,       # Haifa/Ashdod port website (official)
    "haifa_port": 2,        # alias
    "carrier_api": 3,       # Maersk, ZIM, Hapag-Lloyd, etc.
    "zim_expected": 4,      # ZIM expected vessels page
    "email": 5,             # Shipping line schedule emails
    "aisstream": 6,         # AIS position (real-time but not schedule)
    "deal_email": 7,        # Original deal email extraction (lowest confidence)
}

# How close two ETAs must be to be considered "in agreement" (hours)
ETA_AGREEMENT_THRESHOLD_HOURS = 6

# Import process step → TaskYam date field mapping
_IMPORT_STEP_FIELDS = [
    ("manifest", "ManifestDate"),
    ("port_unloading", "PortUnloadingDate"),
    ("delivery_order", "DeliveryOrderDate"),
    ("customs_check", "CustomsCheckDate"),
    ("customs_release", "CustomsReleaseDate"),
    ("port_release", "PortReleaseDate"),
    ("escort_certificate", "EscortCertificateDate"),
    ("cargo_exit_request", "CargoExitRequestDate"),
    ("cargo_exit", "CargoExitDate"),
]

# Export process step → TaskYam date field mapping
_EXPORT_STEP_FIELDS = [
    ("storage_id", "StorageIDDate"),
    ("port_storage_feedback", "PortStorageFeedbackDate"),
    ("storage_to_customs", "StorageIDToCustomsDate"),
    ("driver_assignment", "DriverAssignmentDate"),
    ("customs_check", "CustomsCheckDate"),
    ("customs_release", "CustomsReleaseDate"),
    ("cargo_entry", "CargoEntryDate"),
    ("cargo_loading", "CargoLoadingDate"),
    ("ship_sailing", "ShipSailingDate"),
]


# ═══════════════════════════════════════════════════
#  SHARED UTILITIES
# ═══════════════════════════════════════════════════

def _now_israel():
    """Get current time in Israel timezone."""
    now_utc = datetime.now(timezone.utc)
    return _to_israel_time(now_utc)


def _to_israel_time(dt_obj):
    """Convert a datetime to Israel time."""
    if dt_obj is None:
        return None
    if IL_TZ:
        return dt_obj.astimezone(IL_TZ)
    month = dt_obj.month
    if 4 <= month <= 9:
        return dt_obj + _IL_SUMMER
    elif month == 3 and dt_obj.day >= 25:
        return dt_obj + _IL_SUMMER
    elif month == 10 and dt_obj.day <= 25:
        return dt_obj + _IL_SUMMER
    return dt_obj + _IL_STANDARD


def _parse_iso(dt_str):
    """Parse ISO datetime string → timezone-aware datetime or None."""
    if not dt_str:
        return None
    try:
        clean = str(dt_str).strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        # Remove fractional seconds for simpler parsing
        dot = clean.find(".")
        if dot > 0:
            # Find timezone part after fractional
            tz_start = -1
            for i in range(dot + 1, len(clean)):
                if clean[i] in ("+", "-") or clean[i:] == "Z":
                    tz_start = i
                    break
            if tz_start > 0:
                clean = clean[:dot] + clean[tz_start:]
            else:
                clean = clean[:dot]
        # Try fromisoformat
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _hours_until(target_dt, from_dt=None):
    """Hours from from_dt (default: now Israel) until target_dt. Negative if past."""
    if target_dt is None:
        return None
    if from_dt is None:
        from_dt = _now_israel()
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)
    delta = target_dt - from_dt
    return round(delta.total_seconds() / 3600, 1)


def _days_at_port(entry_dt, now_dt=None):
    """Days since container entered port. Returns float or None."""
    if entry_dt is None:
        return None
    if now_dt is None:
        now_dt = _now_israel()
    if entry_dt.tzinfo is None:
        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    delta = now_dt - entry_dt
    return round(delta.total_seconds() / 86400, 1)


def _sanitize_vessel_name(name):
    """Clean vessel name: remove newlines, extra spaces, control chars.
    Matches schedule_il_ports._sanitize_vessel_name()."""
    if not name:
        return ""
    clean = re.sub(r'[\r\n\t]+', ' ', str(name))
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def _normalize_vessel(name):
    """Normalize vessel name for matching: sanitize + uppercase."""
    return _sanitize_vessel_name(name).upper()


def _format_date_short(dt_str):
    """Format ISO date string to DD/MM HH:MM or DD/MM."""
    if not dt_str:
        return ""
    dt = _parse_iso(dt_str)
    if dt:
        il = _to_israel_time(dt)
        if il.hour == 0 and il.minute == 0:
            return f"{il.day:02d}/{il.month:02d}"
        return f"{il.day:02d}/{il.month:02d} {il.hour:02d}:{il.minute:02d}"
    # Fallback: raw string truncation
    return str(dt_str)[:16]


# ═══════════════════════════════════════════════════
#  DATA CONSOLIDATION
# ═══════════════════════════════════════════════════

def consolidate_datetime_field(source_values):
    """
    Consolidate multiple source values for a datetime field (ETA, ETD, berth, etc.).

    Args:
        source_values: list of {"value": str (ISO), "source": str}
            e.g. [{"value": "2026-02-22T08:00:00Z", "source": "carrier_api"},
                  {"value": "2026-02-22T10:00:00Z", "source": "taskyam_deals"}]

    Returns:
        {
            "best": str,              # single best ISO value
            "best_formatted": str,    # DD/MM HH:MM
            "best_source": str,       # source that provided best value
            "consensus": str,         # human-readable consensus note
            "sources_agree": bool,    # True if all sources within threshold
            "source_count": int,      # how many sources provided data
        }
    """
    # Filter out empty values
    valid = [sv for sv in (source_values or []) if sv.get("value")]
    if not valid:
        return {
            "best": "",
            "best_formatted": "",
            "best_source": "",
            "consensus": "",
            "sources_agree": True,
            "source_count": 0,
        }

    if len(valid) == 1:
        v = valid[0]
        return {
            "best": v["value"],
            "best_formatted": _format_date_short(v["value"]),
            "best_source": v.get("source", ""),
            "consensus": "",
            "sources_agree": True,
            "source_count": 1,
        }

    # Sort by source priority (lower = more authoritative)
    valid_sorted = sorted(valid, key=lambda x: SOURCE_PRIORITY.get(x.get("source", ""), 99))
    best = valid_sorted[0]

    # Check agreement: are all values within ETA_AGREEMENT_THRESHOLD_HOURS?
    parsed = []
    for sv in valid:
        dt = _parse_iso(sv["value"])
        if dt:
            parsed.append((dt, sv.get("source", ""), sv["value"]))

    if len(parsed) < 2:
        return {
            "best": best["value"],
            "best_formatted": _format_date_short(best["value"]),
            "best_source": best.get("source", ""),
            "consensus": "",
            "sources_agree": True,
            "source_count": len(valid),
        }

    # Group by date (YYYY-MM-DD) to build consensus note
    date_groups = Counter()
    for dt, src, raw in parsed:
        date_key = dt.strftime("%b %d")
        date_groups[date_key] += 1

    # Check if all agree (within threshold)
    min_dt = min(dt for dt, _, _ in parsed)
    max_dt = max(dt for dt, _, _ in parsed)
    spread_hours = abs((max_dt - min_dt).total_seconds()) / 3600
    sources_agree = spread_hours <= ETA_AGREEMENT_THRESHOLD_HOURS

    # Build consensus note
    total = len(parsed)
    if sources_agree:
        consensus = f"{total} sources agree"
    else:
        parts = []
        for date_str, count in date_groups.most_common():
            parts.append(f"{count} of {total} say {date_str}")
        consensus = ", ".join(parts)

    return {
        "best": best["value"],
        "best_formatted": _format_date_short(best["value"]),
        "best_source": best.get("source", ""),
        "consensus": consensus,
        "sources_agree": sources_agree,
        "source_count": total,
    }


def consolidate_string_field(source_values):
    """
    Consolidate multiple source values for a string field (berth, vessel name, etc.).
    Highest-priority non-empty value wins.

    Args:
        source_values: list of {"value": str, "source": str}

    Returns:
        {"best": str, "best_source": str, "source_count": int}
    """
    valid = [sv for sv in (source_values or []) if (sv.get("value") or "").strip()]
    if not valid:
        return {"best": "", "best_source": "", "source_count": 0}

    valid_sorted = sorted(valid, key=lambda x: SOURCE_PRIORITY.get(x.get("source", ""), 99))
    best = valid_sorted[0]
    return {
        "best": best["value"],
        "best_source": best.get("source", ""),
        "source_count": len(valid),
    }


def _build_eta_sources(deal, schedule_link, container_statuses=None):
    """Collect ETA values from all available sources for consolidation."""
    sources = []

    # Deal email ETA
    deal_eta = (deal.get("eta") or "").strip()
    if deal_eta:
        sources.append({"value": deal_eta, "source": "deal_email"})

    # Schedule ETA (already merged from multiple sources by schedule_il_ports)
    if schedule_link:
        sched_eta = (schedule_link.get("schedule_eta") or "").strip()
        if sched_eta:
            # The schedule_sources list tells us which original sources contributed
            sched_sources = schedule_link.get("schedule_sources") or []
            # Use the highest-priority source from the schedule's source list
            best_sched_source = "carrier_api"
            for s in sched_sources:
                if SOURCE_PRIORITY.get(s, 99) < SOURCE_PRIORITY.get(best_sched_source, 99):
                    best_sched_source = s
            sources.append({"value": sched_eta, "source": best_sched_source})

    # TaskYam: if any container has ManifestDate, the vessel arrived (ATA, not ETA)
    if container_statuses:
        for cs in container_statuses:
            proc = cs.get("import_process") or {}
            unload = proc.get("PortUnloadingDate", "")
            if unload:
                sources.append({"value": unload, "source": "taskyam_deals"})
                break  # One is enough — TaskYam is authoritative

    return sources


def _build_etd_sources(deal, schedule_link, container_statuses=None):
    """Collect ETD values from all available sources for consolidation."""
    sources = []

    deal_etd = (deal.get("etd") or "").strip()
    if deal_etd:
        sources.append({"value": deal_etd, "source": "deal_email"})

    if schedule_link:
        sched_etd = (schedule_link.get("schedule_etd") or "").strip()
        if sched_etd:
            sched_sources = schedule_link.get("schedule_sources") or []
            best_sched_source = "carrier_api"
            for s in sched_sources:
                if SOURCE_PRIORITY.get(s, 99) < SOURCE_PRIORITY.get(best_sched_source, 99):
                    best_sched_source = s
            sources.append({"value": sched_etd, "source": best_sched_source})

    # TaskYam: if ship_sailing date exists, vessel departed (ATD, not ETD)
    if container_statuses:
        for cs in container_statuses:
            proc = cs.get("export_process") or {}
            sail = proc.get("ShipSailingDate", "")
            if sail:
                sources.append({"value": sail, "source": "taskyam_deals"})
                break

    return sources


# ═══════════════════════════════════════════════════
#  I1: DEAL-SCHEDULE LINKER
# ═══════════════════════════════════════════════════

def levenshtein(s1, s2):
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            ins = prev_row[j + 1] + 1
            dele = curr_row[j] + 1
            sub = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(ins, dele, sub))
        prev_row = curr_row
    return prev_row[-1]


def link_deal_to_schedule(db, deal_id, deal):
    """
    I1: Find matching port_schedule entry for a tracker deal.

    Matching strategy (in priority order):
      1. Exact vessel name (normalized) + port_code
      2. Fuzzy vessel name (Levenshtein <= 2) + port_code
      3. Voyage number + port_code

    Returns:
        dict with linkage data, or None if no match found.
        {
            "schedule_ref": str,       # port_schedule doc ID
            "vessel_name": str,        # from schedule
            "berth": str,
            "schedule_eta": str,
            "schedule_etd": str,
            "schedule_confidence": str,
            "schedule_sources": list,
            "match_type": str,         # "exact", "fuzzy", "voyage"
            "match_distance": int,     # Levenshtein distance (0 for exact/voyage)
            "schedule_changed": bool,
            "previous_eta": str,       # old ETA if changed
        }
    """
    if db is None:
        return None

    vessel_name = (deal.get("vessel_name") or "").strip()
    port_code = (deal.get("port") or "").strip().upper()
    voyage = (deal.get("voyage") or "").strip().upper()

    if not port_code:
        return None
    if not vessel_name and not voyage:
        return None

    # Load schedules for this port
    try:
        schedules = list(
            db.collection("port_schedules")
            .where("port_code", "==", port_code)
            .stream()
        )
    except Exception:
        return None

    if not schedules:
        return None

    vessel_norm = _normalize_vessel(vessel_name)
    best_match = None
    best_type = None
    best_distance = 999

    for doc in schedules:
        data = doc.to_dict()
        doc_vessel = _normalize_vessel(data.get("vessel_name", ""))
        doc_voyage = (data.get("voyage") or "").strip().upper()

        # Strategy 1: Exact vessel match
        if vessel_norm and doc_vessel and vessel_norm == doc_vessel:
            if best_type != "exact" or _schedule_is_closer(data, deal, best_match):
                best_match = (doc.id, data)
                best_type = "exact"
                best_distance = 0

        # Strategy 2: Fuzzy vessel match
        elif vessel_norm and doc_vessel and best_type not in ("exact",):
            dist = levenshtein(vessel_norm, doc_vessel)
            if dist <= FUZZY_MAX_DISTANCE and dist < best_distance:
                best_match = (doc.id, data)
                best_type = "fuzzy"
                best_distance = dist

        # Strategy 3: Voyage match
        if voyage and doc_voyage and voyage == doc_voyage:
            if best_type is None:
                best_match = (doc.id, data)
                best_type = "voyage"
                best_distance = 0

    if best_match is None:
        return None

    doc_id, sched = best_match
    schedule_eta = sched.get("eta", "")
    schedule_etd = sched.get("etd", "")

    # Detect schedule change
    changed = False
    previous_eta = ""
    old_eta = deal.get("schedule_eta", "")
    if old_eta and schedule_eta and old_eta != schedule_eta:
        changed = _is_schedule_change(old_eta, schedule_eta)
        if changed:
            previous_eta = old_eta

    return {
        "schedule_ref": doc_id,
        "vessel_name": sched.get("vessel_name", ""),
        "berth": sched.get("berth", ""),
        "schedule_eta": schedule_eta,
        "schedule_etd": schedule_etd,
        "schedule_confidence": sched.get("confidence", ""),
        "schedule_sources": sched.get("sources", []),
        "match_type": best_type,
        "match_distance": best_distance,
        "schedule_changed": changed,
        "previous_eta": previous_eta,
    }


def _schedule_is_closer(new_sched, deal, old_match):
    """When multiple exact matches, prefer the one with ETA closest to deal ETA."""
    if old_match is None:
        return True
    deal_eta = _parse_iso(deal.get("eta", ""))
    if deal_eta is None:
        return False
    new_eta = _parse_iso(new_sched.get("eta", ""))
    old_eta = _parse_iso(old_match[1].get("eta", ""))
    if new_eta is None:
        return False
    if old_eta is None:
        return True
    return abs((new_eta - deal_eta).total_seconds()) < abs((old_eta - deal_eta).total_seconds())


def _is_schedule_change(old_eta_str, new_eta_str):
    """Return True if ETAs differ by more than SCHEDULE_CHANGE_HOURS."""
    old_dt = _parse_iso(old_eta_str)
    new_dt = _parse_iso(new_eta_str)
    if old_dt is None or new_dt is None:
        return False
    delta_hours = abs((new_dt - old_dt).total_seconds()) / 3600
    return delta_hours > SCHEDULE_CHANGE_HOURS


# ═══════════════════════════════════════════════════
#  I2: DIRECTION-AWARE INTELLIGENCE VIEWS
# ═══════════════════════════════════════════════════

def build_deal_intelligence(deal, container_statuses=None, awb_status=None,
                            schedule_link=None, port_report=None):
    """
    Main entry: build direction-aware intelligence view for a deal.

    Args:
        deal: tracker_deals document dict
        container_statuses: list of tracker_container_status dicts (sea cargo)
        awb_status: tracker_awb_status dict (air cargo)
        schedule_link: result from link_deal_to_schedule() or None
        port_report: daily_port_report dict or None

    Returns:
        dict with view_type and direction-specific intelligence data
    """
    direction = (deal.get("direction") or "").lower()
    freight_kind = (deal.get("freight_kind") or "").lower()

    # Determine deal type
    if freight_kind == "air" or deal.get("awb_number"):
        if direction == "export":
            return build_air_export_intel(deal, awb_status)
        return build_air_import_intel(deal, awb_status)
    else:
        if direction == "export":
            return build_sea_export_intel(
                deal, container_statuses or [],
                schedule_link=schedule_link, port_report=port_report,
            )
        return build_sea_import_intel(
            deal, container_statuses or [],
            schedule_link=schedule_link, port_report=port_report,
        )


# ── SEA IMPORT ──

def build_sea_import_intel(deal, container_statuses, schedule_link=None, port_report=None):
    """Build import-specific intelligence view for a sea cargo deal."""
    port_code = (deal.get("port") or "").upper()
    port_info = SEA_PORTS.get(port_code, {"name_en": port_code, "name_he": port_code})

    # ── Consolidated ETA from all sources ──
    eta_sources = _build_eta_sources(deal, schedule_link, container_statuses)
    eta_consolidated = consolidate_datetime_field(eta_sources)

    best_eta = eta_consolidated["best"]
    best_eta_dt = _parse_iso(best_eta)
    hours_to_arrival = _hours_until(best_eta_dt) if best_eta_dt else None

    # Check if vessel has arrived (any container has port_unloading date)
    arrival_date = ""
    arrived = False
    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        unload = proc.get("PortUnloadingDate", "")
        if unload:
            arrived = True
            if not arrival_date or unload < arrival_date:
                arrival_date = unload
            break

    # Step progress
    progress = _compute_step_progress(container_statuses, "import")

    # Customs status
    customs = _compute_customs_status(container_statuses, "import", deal)

    # Delivery order status
    do_issued = False
    do_date = ""
    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        do_val = proc.get("DeliveryOrderDate", "")
        if do_val:
            do_issued = True
            do_date = do_val
            break

    # Storage risk
    storage = _compute_storage_risk_import(container_statuses)

    # Congestion
    congestion = _compute_congestion(port_report, port_code)

    # Schedule info
    schedule = _build_schedule_section(schedule_link)

    return {
        "view_type": "sea_import",
        "vessel": {
            "name": deal.get("vessel_name", ""),
            "voyage": deal.get("voyage", ""),
            "shipping_line": deal.get("shipping_line") or deal.get("carrier_name", ""),
        },
        "eta": {
            "best": eta_consolidated["best"],
            "best_formatted": eta_consolidated["best_formatted"],
            "best_source": eta_consolidated["best_source"],
            "consensus": eta_consolidated["consensus"],
            "sources_agree": eta_consolidated["sources_agree"],
            "source_count": eta_consolidated["source_count"],
            "hours_until_arrival": hours_to_arrival,
            "arrived": arrived,
            "arrival_date": arrival_date,
            "arrival_date_formatted": _format_date_short(arrival_date),
        },
        "schedule": schedule,
        "progress": progress,
        "customs": customs,
        "documents": {
            "delivery_order": do_issued,
            "delivery_order_date": do_date,
            "delivery_order_formatted": _format_date_short(do_date),
        },
        "storage_risk": storage,
        "congestion": congestion,
        "port": {
            "code": port_code,
            "name_en": port_info.get("name_en", ""),
            "name_he": port_info.get("name_he", ""),
        },
    }


# ── SEA EXPORT ──

def build_sea_export_intel(deal, container_statuses, schedule_link=None, port_report=None):
    """Build export-specific intelligence view for a sea cargo deal."""
    port_code = (deal.get("port") or "").upper()
    port_info = SEA_PORTS.get(port_code, {"name_en": port_code, "name_he": port_code})

    # ── Consolidated ETD from all sources ──
    etd_sources = _build_etd_sources(deal, schedule_link, container_statuses)
    etd_consolidated = consolidate_datetime_field(etd_sources)

    best_etd = etd_consolidated["best"]
    best_etd_dt = _parse_iso(best_etd)
    hours_to_departure = _hours_until(best_etd_dt) if best_etd_dt else None

    # Check if vessel has departed
    departed = False
    departure_date = ""
    for cs in container_statuses:
        proc = cs.get("export_process") or {}
        sail = proc.get("ShipSailingDate", "")
        if sail:
            departed = True
            departure_date = sail
            break

    # Cutoffs
    cutoffs = _compute_export_cutoffs(deal)

    # Step progress
    progress = _compute_step_progress(container_statuses, "export")

    # Customs status
    customs = _compute_customs_status(container_statuses, "export", deal)

    # Storage risk for export (time at port before loading)
    storage = _compute_storage_risk_export(container_statuses)

    # Congestion
    congestion = _compute_congestion(port_report, port_code)

    # Schedule info
    schedule = _build_schedule_section(schedule_link)

    return {
        "view_type": "sea_export",
        "vessel": {
            "name": deal.get("vessel_name", ""),
            "voyage": deal.get("voyage", ""),
            "shipping_line": deal.get("shipping_line") or deal.get("carrier_name", ""),
        },
        "etd": {
            "best": etd_consolidated["best"],
            "best_formatted": etd_consolidated["best_formatted"],
            "best_source": etd_consolidated["best_source"],
            "consensus": etd_consolidated["consensus"],
            "sources_agree": etd_consolidated["sources_agree"],
            "source_count": etd_consolidated["source_count"],
            "hours_until_departure": hours_to_departure,
            "departed": departed,
            "departure_date": departure_date,
            "departure_date_formatted": _format_date_short(departure_date),
        },
        "cutoffs": cutoffs,
        "schedule": schedule,
        "progress": progress,
        "customs": customs,
        "storage_risk": storage,
        "congestion": congestion,
        "port": {
            "code": port_code,
            "name_en": port_info.get("name_en", ""),
            "name_he": port_info.get("name_he", ""),
        },
    }


# ── AIR IMPORT ──

def build_air_import_intel(deal, awb_status):
    """Build air import intelligence view."""
    awb = awb_status or {}
    awb_number = deal.get("awb_number", "") or awb.get("awb_number", "")

    deal_eta = deal.get("eta", "")
    best_eta_dt = _parse_iso(deal_eta)
    hours_to_arrival = _hours_until(best_eta_dt) if best_eta_dt else None

    # AWB status
    status_norm = awb.get("status_normalized", "")
    arrived = status_norm in ("arrived", "at_terminal", "ready", "hold",
                              "customs_hold", "released", "customs_released",
                              "delivered")
    arrival_date = awb.get("arrived_at", "")

    # Customs from AWB
    hold = status_norm in ("hold", "customs_hold")
    released = status_norm in ("released", "customs_released")
    released_at = awb.get("released_at", "")

    # Air storage risk (hours at terminal)
    air_storage = _compute_air_storage_risk(awb)

    return {
        "view_type": "air_import",
        "flight": {
            "awb_number": awb_number,
            "airline_name": awb.get("airline_name", ""),
            "terminal": awb.get("terminal", ""),
        },
        "eta": {
            "deal_eta": deal_eta,
            "best_eta": deal_eta,
            "best_eta_formatted": _format_date_short(deal_eta),
            "hours_until_arrival": hours_to_arrival,
            "arrived": arrived,
            "arrival_date": arrival_date,
            "arrival_date_formatted": _format_date_short(arrival_date),
        },
        "awb_status": {
            "status": status_norm,
            "raw_status": awb.get("raw_status") or awb.get("status", ""),
        },
        "customs": {
            "status": "hold" if hold else ("released" if released else
                      ("cleared" if arrived and not hold else "pending")),
            "hold": hold,
            "released": released,
            "released_at": released_at,
            "released_at_formatted": _format_date_short(released_at),
        },
        "storage_risk": air_storage,
        "port": {
            "code": "ILLIB",
            "name_en": "Ben Gurion Airport",
            "name_he": "נתב\"ג",
        },
    }


# ── AIR EXPORT ──

def build_air_export_intel(deal, awb_status):
    """Build air export intelligence view."""
    awb = awb_status or {}
    awb_number = deal.get("awb_number", "") or awb.get("awb_number", "")

    deal_etd = deal.get("etd", "")
    best_etd_dt = _parse_iso(deal_etd)
    hours_to_departure = _hours_until(best_etd_dt) if best_etd_dt else None

    # AWB status
    status_norm = awb.get("status_normalized", "")

    # Customs from AWB
    hold = status_norm in ("hold", "customs_hold")
    released = status_norm in ("released", "customs_released")

    # Export cutoffs
    acceptance_cutoff = deal.get("acceptance_cutoff", "")
    awb_cutoff = deal.get("awb_cutoff", "")

    acc_dt = _parse_iso(acceptance_cutoff)
    awb_dt = _parse_iso(awb_cutoff)

    return {
        "view_type": "air_export",
        "flight": {
            "awb_number": awb_number,
            "airline_name": awb.get("airline_name", ""),
            "terminal": awb.get("terminal", ""),
        },
        "etd": {
            "deal_etd": deal_etd,
            "best_etd": deal_etd,
            "best_etd_formatted": _format_date_short(deal_etd),
            "hours_until_departure": hours_to_departure,
        },
        "cutoffs": {
            "acceptance_cutoff": acceptance_cutoff,
            "acceptance_cutoff_formatted": _format_date_short(acceptance_cutoff),
            "acceptance_cutoff_hours": _hours_until(acc_dt) if acc_dt else None,
            "awb_cutoff": awb_cutoff,
            "awb_cutoff_formatted": _format_date_short(awb_cutoff),
            "awb_cutoff_hours": _hours_until(awb_dt) if awb_dt else None,
        },
        "awb_status": {
            "status": status_norm,
            "raw_status": awb.get("raw_status") or awb.get("status", ""),
        },
        "customs": {
            "status": "hold" if hold else ("released" if released else "pending"),
            "hold": hold,
            "released": released,
        },
        "port": {
            "code": "ILLIB",
            "name_en": "Ben Gurion Airport",
            "name_he": "נתב\"ג",
        },
    }


# ═══════════════════════════════════════════════════
#  I2 HELPERS: STORAGE RISK
# ═══════════════════════════════════════════════════

def _compute_storage_risk_import(container_statuses, now_dt=None):
    """
    Compute storage risk for import containers at port.

    Escalation levels:
      - "none":     < 2 days at port, or already exited
      - "notice":   >= 2 days — "2 more days before storage charges"
      - "warning":  >= 3 days — "must be taken out tomorrow"
      - "critical": >= 4 days — storage charges apply

    Returns dict with level, days, affected containers, message.
    """
    if not container_statuses:
        return _empty_storage_risk()

    if now_dt is None:
        now_dt = _now_israel()

    max_days = 0.0
    containers_at_risk = 0
    container_details = []

    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        entry_date_str = proc.get("PortUnloadingDate", "")
        exit_date_str = proc.get("CargoExitDate", "")

        # Skip containers that already exited or haven't arrived yet
        if exit_date_str or not entry_date_str:
            continue

        entry_dt = _parse_iso(entry_date_str)
        if entry_dt is None:
            continue

        days = _days_at_port(entry_dt, now_dt)
        if days is None or days < 0:
            continue

        if days >= STORAGE_NOTICE_DAYS:
            containers_at_risk += 1
            container_details.append({
                "container_id": cs.get("container_id", ""),
                "days_at_port": days,
                "entry_date": entry_date_str,
            })

        if days > max_days:
            max_days = days

    level, message = _storage_level_and_message(max_days)

    return {
        "level": level,
        "days_at_port": max_days,
        "containers_at_risk": containers_at_risk,
        "container_details": container_details,
        "message": message,
        "message_he": _storage_message_he(level),
    }


def _compute_storage_risk_export(container_statuses, now_dt=None):
    """
    Compute storage risk for export containers waiting at port.
    Export: time from cargo_entry to ship_sailing.
    Same escalation thresholds as import.
    """
    if not container_statuses:
        return _empty_storage_risk()

    if now_dt is None:
        now_dt = _now_israel()

    max_days = 0.0
    containers_at_risk = 0
    container_details = []

    for cs in container_statuses:
        proc = cs.get("export_process") or {}
        entry_date_str = proc.get("CargoEntryDate", "")
        exit_date_str = proc.get("ShipSailingDate", "")

        if exit_date_str or not entry_date_str:
            continue

        entry_dt = _parse_iso(entry_date_str)
        if entry_dt is None:
            continue

        days = _days_at_port(entry_dt, now_dt)
        if days is None or days < 0:
            continue

        if days >= STORAGE_NOTICE_DAYS:
            containers_at_risk += 1
            container_details.append({
                "container_id": cs.get("container_id", ""),
                "days_at_port": days,
                "entry_date": entry_date_str,
            })

        if days > max_days:
            max_days = days

    level, message = _storage_level_and_message(max_days)

    return {
        "level": level,
        "days_at_port": max_days,
        "containers_at_risk": containers_at_risk,
        "container_details": container_details,
        "message": message,
        "message_he": _storage_message_he(level),
    }


def _storage_level_and_message(days):
    """Determine storage risk level and English message from days at port."""
    if days >= STORAGE_CRITICAL_DAYS:
        return "critical", f"Storage charges apply — {days:.0f} days at port"
    elif days >= STORAGE_WARNING_DAYS:
        return "warning", "Must be taken out tomorrow — 1 day before storage charges"
    elif days >= STORAGE_NOTICE_DAYS:
        remaining = STORAGE_CRITICAL_DAYS - days
        return "notice", f"{remaining:.0f} more days before storage charges"
    return "none", ""


def _storage_message_he(level):
    """Hebrew storage risk message per level."""
    if level == "critical":
        return "דמי אחסנה חלים — יש לפנות מיידית"
    elif level == "warning":
        return "יש לפנות מחר — יום אחד לפני דמי אחסנה"
    elif level == "notice":
        return "עוד 2 ימים לפני דמי אחסנה"
    return ""


def _compute_air_storage_risk(awb_status, now_dt=None):
    """
    Compute storage risk for air cargo at terminal.
    Threshold: 48 hours (same as air_cargo_tracker).
    Escalation: 24h notice → 36h warning → 48h critical.
    """
    if not awb_status:
        return {
            "level": "none",
            "hours_at_terminal": 0,
            "message": "",
            "message_he": "",
        }

    if now_dt is None:
        now_dt = _now_israel()

    status = awb_status.get("status_normalized", "")
    # Skip if already released/delivered
    if status in ("released", "customs_released", "delivered"):
        return {
            "level": "none",
            "hours_at_terminal": 0,
            "message": "",
            "message_he": "",
        }

    storage_start_str = awb_status.get("storage_start") or awb_status.get("arrived_at", "")
    if not storage_start_str:
        return {
            "level": "none",
            "hours_at_terminal": 0,
            "message": "",
            "message_he": "",
        }

    start_dt = _parse_iso(storage_start_str)
    if start_dt is None:
        return {
            "level": "none",
            "hours_at_terminal": 0,
            "message": "",
            "message_he": "",
        }

    hours = _hours_until(now_dt, start_dt)  # hours from start to now
    if hours is None or hours < 0:
        hours = 0

    level = "none"
    message = ""
    message_he = ""

    if hours >= AIR_STORAGE_CRITICAL_HOURS:
        level = "critical"
        message = f"At terminal {hours:.0f}h — storage charges apply"
        message_he = f"במסוף {hours:.0f} שעות — דמי אחסנה חלים"
    elif hours >= AIR_STORAGE_WARNING_HOURS:
        level = "warning"
        remaining = AIR_STORAGE_CRITICAL_HOURS - hours
        message = f"At terminal {hours:.0f}h — {remaining:.0f}h before storage charges"
        message_he = f"במסוף {hours:.0f} שעות — {remaining:.0f} שעות לדמי אחסנה"
    elif hours >= AIR_STORAGE_NOTICE_HOURS:
        level = "notice"
        remaining = AIR_STORAGE_CRITICAL_HOURS - hours
        message = f"At terminal {hours:.0f}h — {remaining:.0f}h before storage charges"
        message_he = f"במסוף {hours:.0f} שעות — {remaining:.0f} שעות לדמי אחסנה"

    return {
        "level": level,
        "hours_at_terminal": hours,
        "message": message,
        "message_he": message_he,
    }


def _empty_storage_risk():
    """Return empty storage risk dict."""
    return {
        "level": "none",
        "days_at_port": 0,
        "containers_at_risk": 0,
        "container_details": [],
        "message": "",
        "message_he": "",
    }


# ═══════════════════════════════════════════════════
#  I2 HELPERS: CONGESTION
# ═══════════════════════════════════════════════════

def _compute_congestion(port_report, port_code):
    """
    Compute congestion level from daily_port_report data.

    Thresholds:
      <= 15 vessels: "normal"
      16-25 vessels: "busy"
      > 25 vessels:  "congested"
    """
    port_info = SEA_PORTS.get(port_code, {"name_en": port_code, "name_he": port_code})
    vessel_count = 0

    if port_report:
        vessel_count = port_report.get("total_vessels", 0)

    if vessel_count > CONGESTION_CONGESTED:
        level = "congested"
    elif vessel_count > CONGESTION_BUSY:
        level = "busy"
    else:
        level = "normal"

    return {
        "level": level,
        "vessel_count": vessel_count,
        "port_name_en": port_info.get("name_en", ""),
        "port_name_he": port_info.get("name_he", ""),
    }


# ═══════════════════════════════════════════════════
#  I2 HELPERS: STEP PROGRESS
# ═══════════════════════════════════════════════════

def _compute_step_progress(container_statuses, direction):
    """
    Compute step completion progress across all containers.

    Returns:
        {
            "completed_steps": int,  # max completed step index (furthest container)
            "total_steps": int,
            "current_step": str,     # step name of the furthest step
            "current_step_label": str,
            "percent": int,          # 0-100
            "containers_done": int,  # containers at terminal step
            "containers_total": int,
        }
    """
    steps = _IMPORT_STEP_FIELDS if direction != "export" else _EXPORT_STEP_FIELDS
    process_key = "import_process" if direction != "export" else "export_process"
    terminal_field = steps[-1][1]  # Last step's date field

    total_containers = len(container_statuses)
    containers_done = 0
    max_step_idx = -1
    current_step = "pending"
    current_step_label = "Pending"

    for cs in container_statuses:
        proc = cs.get(process_key) or {}

        # Check terminal step
        if proc.get(terminal_field):
            containers_done += 1

        # Find highest completed step
        for idx, (step_name, date_field) in enumerate(steps):
            if proc.get(date_field):
                if idx > max_step_idx:
                    max_step_idx = idx
                    current_step = step_name

    total_steps = len(steps)
    completed_steps = max_step_idx + 1 if max_step_idx >= 0 else 0

    # Look up label for current step
    for step_name, date_field in steps:
        if step_name == current_step:
            # Generate label from step name
            current_step_label = step_name.replace("_", " ").title()
            break

    percent = round((completed_steps / total_steps) * 100) if total_steps > 0 else 0

    return {
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "current_step": current_step,
        "current_step_label": current_step_label,
        "percent": percent,
        "containers_done": containers_done,
        "containers_total": total_containers,
    }


# ═══════════════════════════════════════════════════
#  I2 HELPERS: CUSTOMS STATUS
# ═══════════════════════════════════════════════════

def _compute_customs_status(container_statuses, direction, deal):
    """
    Extract customs check/release status from container processes.

    Returns:
        {
            "status": str,          # "pending", "under_check", "released", "not_applicable"
            "check_date": str,
            "release_date": str,
            "declaration": str,     # customs declaration number
            "containers_released": int,
            "containers_total": int,
        }
    """
    process_key = "import_process" if direction != "export" else "export_process"
    total = len(container_statuses)
    checked = 0
    released = 0
    check_date = ""
    release_date = ""

    for cs in container_statuses:
        proc = cs.get(process_key) or {}
        if proc.get("CustomsCheckDate"):
            checked += 1
            if not check_date:
                check_date = proc["CustomsCheckDate"]
        if proc.get("CustomsReleaseDate"):
            released += 1
            if not release_date:
                release_date = proc["CustomsReleaseDate"]

    if total == 0:
        status = "not_applicable"
    elif released == total:
        status = "released"
    elif released > 0:
        status = "partially_released"
    elif checked > 0:
        status = "under_check"
    else:
        status = "pending"

    return {
        "status": status,
        "check_date": check_date,
        "check_date_formatted": _format_date_short(check_date),
        "release_date": release_date,
        "release_date_formatted": _format_date_short(release_date),
        "declaration": deal.get("customs_declaration", ""),
        "containers_released": released,
        "containers_total": total,
    }


# ═══════════════════════════════════════════════════
#  I2 HELPERS: EXPORT CUTOFFS
# ═══════════════════════════════════════════════════

def _compute_export_cutoffs(deal):
    """
    Compute hours remaining for all export cutoffs.

    Returns dict with each cutoff's raw value, formatted value, and hours remaining.
    """
    fields = [
        ("gate_cutoff", "gate_cutoff"),
        ("vgm_cutoff", "vgm_cutoff"),
        ("doc_cutoff", "doc_cutoff"),
        ("container_cutoff", "container_cutoff"),
    ]
    result = {}
    soonest_hours = None
    soonest_type = ""

    for field_name, deal_key in fields:
        val = deal.get(deal_key, "")
        dt = _parse_iso(val)
        hours = _hours_until(dt) if dt else None

        result[field_name] = val
        result[f"{field_name}_formatted"] = _format_date_short(val)
        result[f"{field_name}_hours"] = hours

        if hours is not None and (soonest_hours is None or hours < soonest_hours):
            soonest_hours = hours
            soonest_type = field_name

    result["soonest_cutoff_type"] = soonest_type
    result["soonest_cutoff_hours"] = soonest_hours
    return result


# ═══════════════════════════════════════════════════
#  I2 HELPERS: SCHEDULE SECTION
# ═══════════════════════════════════════════════════

def _build_schedule_section(schedule_link):
    """Build schedule section dict from I1 linkage result."""
    if not schedule_link:
        return {
            "linked": False,
            "schedule_ref": "",
            "berth": "",
            "confidence": "",
            "sources": [],
            "match_type": "",
            "changed": False,
            "previous_eta": "",
        }

    return {
        "linked": True,
        "schedule_ref": schedule_link.get("schedule_ref", ""),
        "berth": schedule_link.get("berth", ""),
        "confidence": schedule_link.get("schedule_confidence", ""),
        "sources": schedule_link.get("schedule_sources", []),
        "match_type": schedule_link.get("match_type", ""),
        "changed": schedule_link.get("schedule_changed", False),
        "previous_eta": schedule_link.get("previous_eta", ""),
    }


# ═══════════════════════════════════════════════════
#  I3: ALERT ENGINE (event-triggered, per shipment)
# ═══════════════════════════════════════════════════

# Alert type constants
ALERT_DO_MISSING = "do_missing"
ALERT_PHYSICAL_EXAM = "physical_exam"
ALERT_STORAGE_DAY3 = "storage_day3"
ALERT_EXPORT_CUTOFF = "export_cutoff"

_ALERT_SEVERITY = {
    ALERT_DO_MISSING: "critical",
    ALERT_PHYSICAL_EXAM: "warning",
    ALERT_STORAGE_DAY3: "warning",
    ALERT_EXPORT_CUTOFF: "warning",
}

# Export cutoff alert thresholds (hours before cutoff)
_CUTOFF_WARNING_HOURS = 24
_CUTOFF_CRITICAL_HOURS = 6


def check_port_intelligence_alerts(deal_id, deal, container_statuses, now_dt=None):
    """
    I3: Check all alert conditions for a single deal.

    Pure function — no Firestore access, no email sending.
    Caller should filter out already-sent alerts using deal.get("port_alerts_sent", []).

    Args:
        deal_id: Firestore document ID
        deal: tracker_deals dict
        container_statuses: list of tracker_container_status dicts
        now_dt: override for testing (Israel time)

    Returns:
        list of alert dicts, each with:
            type, deal_id, severity, message_he, message_en, details
    """
    if now_dt is None:
        now_dt = _now_israel()

    alerts = []
    direction = (deal.get("direction") or "").lower()
    freight_kind = (deal.get("freight_kind") or "").lower()

    # Only sea import alerts for now (air handled separately)
    if freight_kind == "air" or deal.get("awb_number"):
        return alerts

    if direction == "export":
        _check_export_cutoffs(deal_id, deal, now_dt, alerts)
        _check_storage_day3_export(deal_id, deal, container_statuses, now_dt, alerts)
        return alerts

    # ── Import alerts ──
    _check_do_missing(deal_id, deal, container_statuses, alerts)
    _check_physical_exam(deal_id, deal, container_statuses, alerts)
    _check_storage_day3_import(deal_id, deal, container_statuses, now_dt, alerts)

    return alerts


def _check_do_missing(deal_id, deal, container_statuses, alerts):
    """Alert: D/O not received AND vessel ATA exists (import)."""
    if not container_statuses:
        return

    # Check if vessel has arrived (any container has PortUnloadingDate = ATA)
    ata_exists = False
    ata_date = ""
    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        unload = proc.get("PortUnloadingDate", "")
        if unload:
            ata_exists = True
            ata_date = unload
            break

    if not ata_exists:
        return

    # Check if D/O has been received
    do_received = False
    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        if proc.get("DeliveryOrderDate"):
            do_received = True
            break

    if do_received:
        return

    vessel = deal.get("vessel_name", "")
    bol = deal.get("bol_number", "")
    port_code = (deal.get("port") or "").upper()
    port_info = SEA_PORTS.get(port_code, {"name_he": port_code, "name_en": port_code})

    alerts.append({
        "type": ALERT_DO_MISSING,
        "deal_id": deal_id,
        "severity": "critical",
        "message_he": (
            f"D/O טרם התקבל · {vessel} · {bol} · "
            f"{port_info.get('name_he', '')} · ATA {_format_date_short(ata_date)}"
        ),
        "message_en": (
            f"D/O not received — vessel arrived · {vessel} · {bol} · "
            f"{port_info.get('name_en', '')} · ATA {_format_date_short(ata_date)}"
        ),
        "details": {
            "vessel_name": vessel,
            "bol_number": bol,
            "port_code": port_code,
            "ata_date": ata_date,
        },
    })


def _check_physical_exam(deal_id, deal, container_statuses, alerts):
    """Alert: Physical examination opened (customs check without release)."""
    if not container_statuses:
        return

    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        check_date = proc.get("CustomsCheckDate", "")
        release_date = proc.get("CustomsReleaseDate", "")

        if check_date and not release_date:
            container_id = cs.get("container_id", "")
            vessel = deal.get("vessel_name", "")
            bol = deal.get("bol_number", "")
            port_code = (deal.get("port") or "").upper()
            port_info = SEA_PORTS.get(port_code, {"name_he": port_code, "name_en": port_code})

            alerts.append({
                "type": ALERT_PHYSICAL_EXAM,
                "deal_id": deal_id,
                "severity": "warning",
                "message_he": (
                    f"בדיקה פיזית נפתחה · {container_id} · {vessel} · "
                    f"{port_info.get('name_he', '')} · {_format_date_short(check_date)}"
                ),
                "message_en": (
                    f"Physical examination opened · {container_id} · {vessel} · "
                    f"{port_info.get('name_en', '')} · {_format_date_short(check_date)}"
                ),
                "details": {
                    "container_id": container_id,
                    "vessel_name": vessel,
                    "bol_number": bol,
                    "port_code": port_code,
                    "check_date": check_date,
                },
            })
            return  # One alert per deal, not per container


def _check_storage_day3_import(deal_id, deal, container_statuses, now_dt, alerts):
    """Alert: Storage day 3 of 4 — must be taken out tomorrow."""
    if not container_statuses:
        return

    for cs in container_statuses:
        proc = cs.get("import_process") or {}
        entry_str = proc.get("PortUnloadingDate", "")
        exit_str = proc.get("CargoExitDate", "")

        if exit_str or not entry_str:
            continue

        entry_dt = _parse_iso(entry_str)
        if entry_dt is None:
            continue

        days = _days_at_port(entry_dt, now_dt)
        if days is None:
            continue

        if days >= STORAGE_WARNING_DAYS:
            container_id = cs.get("container_id", "")
            vessel = deal.get("vessel_name", "")
            bol = deal.get("bol_number", "")
            port_code = (deal.get("port") or "").upper()

            alerts.append({
                "type": ALERT_STORAGE_DAY3,
                "deal_id": deal_id,
                "severity": "critical" if days >= STORAGE_CRITICAL_DAYS else "warning",
                "message_he": (
                    f"יום אחסנה {days:.0f} מתוך {STORAGE_CRITICAL_DAYS} · "
                    f"{container_id} · {vessel} · {bol} · "
                    f"{'דמי אחסנה חלים' if days >= STORAGE_CRITICAL_DAYS else 'יש לפנות מחר'}"
                ),
                "message_en": (
                    f"Storage day {days:.0f} of {STORAGE_CRITICAL_DAYS} · "
                    f"{container_id} · {vessel} · {bol} · "
                    f"{'charges apply' if days >= STORAGE_CRITICAL_DAYS else 'must evacuate tomorrow'}"
                ),
                "details": {
                    "container_id": container_id,
                    "vessel_name": vessel,
                    "bol_number": bol,
                    "port_code": port_code,
                    "days_at_port": days,
                    "entry_date": entry_str,
                },
            })
            return  # One storage alert per deal


def _check_storage_day3_export(deal_id, deal, container_statuses, now_dt, alerts):
    """Alert: Storage day 3 for export containers at port."""
    if not container_statuses:
        return

    for cs in container_statuses:
        proc = cs.get("export_process") or {}
        entry_str = proc.get("CargoEntryDate", "")
        exit_str = proc.get("ShipSailingDate", "")

        if exit_str or not entry_str:
            continue

        entry_dt = _parse_iso(entry_str)
        if entry_dt is None:
            continue

        days = _days_at_port(entry_dt, now_dt)
        if days is None:
            continue

        if days >= STORAGE_WARNING_DAYS:
            container_id = cs.get("container_id", "")
            vessel = deal.get("vessel_name", "")

            alerts.append({
                "type": ALERT_STORAGE_DAY3,
                "deal_id": deal_id,
                "severity": "critical" if days >= STORAGE_CRITICAL_DAYS else "warning",
                "message_he": (
                    f"יום אחסנה {days:.0f} מתוך {STORAGE_CRITICAL_DAYS} · "
                    f"{container_id} · {vessel} · "
                    f"{'דמי אחסנה חלים' if days >= STORAGE_CRITICAL_DAYS else 'יש לפנות מחר'}"
                ),
                "message_en": (
                    f"Storage day {days:.0f} of {STORAGE_CRITICAL_DAYS} · "
                    f"{container_id} · {vessel} · "
                    f"{'charges apply' if days >= STORAGE_CRITICAL_DAYS else 'must evacuate tomorrow'}"
                ),
                "details": {
                    "container_id": container_id,
                    "vessel_name": vessel,
                    "days_at_port": days,
                    "entry_date": entry_str,
                },
            })
            return


def _check_export_cutoffs(deal_id, deal, now_dt, alerts):
    """Alert: VGM / doc cutoff / container closing approaching for export deals."""
    cutoff_fields = [
        ("vgm_cutoff", "VGM"),
        ("doc_cutoff", "סגירת דוקומנטים"),
        ("container_cutoff", "סגירת מכולות בנמל"),
    ]

    vessel = deal.get("vessel_name", "")
    booking = deal.get("booking_number", "") or deal.get("bol_number", "")
    port_code = (deal.get("port") or "").upper()

    for field, label_he in cutoff_fields:
        val = deal.get(field, "")
        dt = _parse_iso(val)
        if dt is None:
            continue

        hours = _hours_until(dt, now_dt)
        if hours is None or hours > _CUTOFF_WARNING_HOURS or hours < -2:
            continue  # Not yet in window, or long past

        severity = "critical" if hours <= _CUTOFF_CRITICAL_HOURS else "warning"
        if hours <= 0:
            time_note_he = "עבר"
            time_note_en = "PASSED"
        elif hours < 1:
            time_note_he = f"בעוד {int(hours * 60)} דקות"
            time_note_en = f"in {int(hours * 60)} minutes"
        else:
            time_note_he = f"בעוד {hours:.0f} שעות"
            time_note_en = f"in {hours:.0f} hours"

        alerts.append({
            "type": ALERT_EXPORT_CUTOFF,
            "deal_id": deal_id,
            "severity": severity,
            "message_he": (
                f"{label_he} {time_note_he} · {booking} · {vessel} · "
                f"{_format_date_short(val)}"
            ),
            "message_en": (
                f"{label_he} {time_note_en} · {booking} · {vessel} · "
                f"{_format_date_short(val)}"
            ),
            "details": {
                "cutoff_type": field,
                "cutoff_label": label_he,
                "cutoff_datetime": val,
                "hours_remaining": hours,
                "vessel_name": vessel,
                "bol_number": booking,
                "port_code": port_code,
            },
        })


def build_port_alert_subject(alert):
    """Build email subject line for a port intelligence alert."""
    severity = alert.get("severity", "warning")
    alert_type = alert.get("type", "")
    deal_id = alert.get("deal_id", "")
    details = alert.get("details", {})

    icon = "🚨" if severity == "critical" else "⚡"
    container = details.get("container_id", "")
    vessel = details.get("vessel_name", "")
    identifier = container or details.get("bol_number", deal_id)

    if alert_type == ALERT_DO_MISSING:
        return f"{icon} RCB | {identifier} | D/O טרם התקבל | {vessel}"
    elif alert_type == ALERT_PHYSICAL_EXAM:
        return f"{icon} RCB | {identifier} | בדיקה פיזית | {vessel}"
    elif alert_type == ALERT_STORAGE_DAY3:
        days = details.get("days_at_port", 3)
        return f"{icon} RCB | {identifier} | יום אחסנה {days:.0f} | {vessel}"
    elif alert_type == ALERT_EXPORT_CUTOFF:
        label = details.get("cutoff_label", "cutoff")
        return f"{icon} RCB | {identifier} | {label} | {vessel}"
    return f"{icon} RCB | {identifier} | התראת נמל"


def build_port_alert_html(alert):
    """Build HTML email body for a single port intelligence alert."""
    severity = alert.get("severity", "warning")
    message_he = alert.get("message_he", "")
    message_en = alert.get("message_en", "")
    details = alert.get("details", {})

    bg = "#fff0f3" if severity == "critical" else "#fff8f0"
    border = "#ef233c" if severity == "critical" else "#f77f00"
    icon = "🚨" if severity == "critical" else "⚡"
    level_he = "דחוף" if severity == "critical" else "אזהרה"

    return f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#eef0f3">
<div style="max-width:640px;margin:0 auto;background:#fff">
<div style="background:#0d1b2a;padding:14px 24px;border-bottom:3px solid #00b4d8">
  <table width="100%"><tr>
    <td style="color:#fff;font-size:15px;font-weight:700;letter-spacing:2px">
      <span style="background:linear-gradient(135deg,#00b4d8,#0077b6);border-radius:5px;padding:4px 8px;font-size:11px;color:#fff;margin-left:8px">RCB</span>
      R.P.A. PORT LTD
    </td>
    <td style="text-align:left;color:#caf0f8;font-size:12px;direction:ltr">
      התראת נמל | {level_he}
    </td>
  </tr></table>
</div>
<div style="padding:20px 24px;background:{bg};border-right:4px solid {border}">
  <div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:8px">{icon} {message_he}</div>
  <div style="font-size:12px;color:#495057;direction:ltr">{message_en}</div>
</div>
<div style="padding:14px 24px;font-size:12px;color:#495057;line-height:1.8">
  <table style="width:100%;border-collapse:collapse;font-size:12px">
    <tr><td style="padding:4px 8px;font-weight:700;color:#6c757d;width:120px">אוניה</td><td style="padding:4px 8px;font-family:monospace">{details.get("vessel_name", "—")}</td></tr>
    <tr><td style="padding:4px 8px;font-weight:700;color:#6c757d">B/L</td><td style="padding:4px 8px;font-family:monospace">{details.get("bol_number", "—")}</td></tr>
    <tr><td style="padding:4px 8px;font-weight:700;color:#6c757d">מכולה</td><td style="padding:4px 8px;font-family:monospace">{details.get("container_id", "—")}</td></tr>
    <tr><td style="padding:4px 8px;font-weight:700;color:#6c757d">נמל</td><td style="padding:4px 8px">{details.get("port_code", "—")}</td></tr>
  </table>
</div>
<div style="background:#0d1b2a;padding:10px 24px;text-align:center;direction:ltr">
  <div style="color:#48cae4;font-size:10px;font-family:monospace">RCB · R.P.A. PORT LTD · Haifa · rcb@rpa-port.co.il</div>
</div>
</div>
</body>
</html>'''


# ═══════════════════════════════════════════════════
#  I4: MORNING DIGEST
# ═══════════════════════════════════════════════════

# All Israeli sea ports shown in digest (ordered north → south)
DIGEST_SEA_PORTS = [
    {"code": "ILHFA", "name_he": "נמל חיפה", "code_display": "ILHFA", "capacity": 25, "gate_hours": "06:00–22:00"},
    {"code": "ILKRN", "name_he": "נמל המפרץ", "code_display": "ILKRN", "capacity": 15, "gate_hours": "06:00–22:00"},
    {"code": "ILASD", "name_he": "נמל אשדוד", "code_display": "ILASD", "capacity": 25, "gate_hours": "06:00–20:00"},
    {"code": "ILASH", "name_he": "נמל הדרום", "code_display": "ILASH", "capacity": 10, "gate_hours": "06:00–20:00"},
]

_HEBREW_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"


def build_morning_digest(db, now_dt=None):
    """
    I4: Build complete morning digest HTML by querying real Firestore data.

    Queries tracker_deals, tracker_container_status, daily_port_report,
    and port_schedules. Groups deals by direction × port.

    Args:
        db: Firestore client
        now_dt: override for testing

    Returns:
        str: complete HTML string, or None if no active deals
    """
    if db is None:
        return None

    if now_dt is None:
        now_dt = _now_israel()

    # 1. Query all active deals
    try:
        deal_snaps = list(
            db.collection("tracker_deals")
            .where("status", "in", ["active", "pending"])
            .stream()
        )
    except Exception:
        deal_snaps = []

    if not deal_snaps:
        return None

    # 2. Build deal data with container statuses + schedule links
    deals_data = []
    for snap in deal_snaps:
        deal = snap.to_dict()
        deal_id = snap.id

        # Get container statuses
        try:
            cs_snaps = list(
                db.collection("tracker_container_status")
                .where("deal_id", "==", deal_id)
                .stream()
            )
            container_statuses = [c.to_dict() for c in cs_snaps]
        except Exception:
            container_statuses = []

        # Get AWB status for air cargo
        awb_status = None
        awb_num = deal.get("awb_number", "")
        if awb_num:
            try:
                awb_snaps = list(
                    db.collection("tracker_awb_status")
                    .where("awb_number", "==", awb_num)
                    .limit(1)
                    .stream()
                )
                if awb_snaps:
                    awb_status = awb_snaps[0].to_dict()
            except Exception:
                pass

        # Link to schedule
        schedule_link = link_deal_to_schedule(db, deal_id, deal)

        # Check alerts
        deal_alerts = check_port_intelligence_alerts(
            deal_id, deal, container_statuses, now_dt
        )

        deals_data.append({
            "deal_id": deal_id,
            "deal": deal,
            "container_statuses": container_statuses,
            "awb_status": awb_status,
            "schedule_link": schedule_link,
            "alerts": deal_alerts,
        })

    # 3. Query port reports for today
    today_str = now_dt.strftime("%Y-%m-%d")
    port_reports = {}
    for port_info in DIGEST_SEA_PORTS:
        code = port_info["code"]
        doc_id = f"{code}_{today_str}"
        try:
            doc = db.collection("daily_port_report").document(doc_id).get()
            if doc.exists:
                port_reports[code] = doc.to_dict()
        except Exception:
            pass

    # 4. Render HTML
    return render_morning_digest_html(deals_data, port_reports, now_dt)


def render_morning_digest_html(deals_data, port_reports, now_dt=None):
    """
    I4: Pure render function — generates digest HTML from pre-fetched data.

    Args:
        deals_data: list of dicts with deal, container_statuses, schedule_link, alerts
        port_reports: dict of port_code → daily_port_report dict
        now_dt: Israel time datetime

    Returns:
        str: complete HTML
    """
    if now_dt is None:
        now_dt = _now_israel()

    # Group deals by category
    sea_import = {}   # port_code → list of deal_data
    sea_export = {}
    air_import = []
    air_export = []

    all_alerts = []

    for dd in deals_data:
        deal = dd["deal"]
        direction = (deal.get("direction") or "").lower()
        freight_kind = (deal.get("freight_kind") or "").lower()
        port_code = (deal.get("port") or "").upper()
        all_alerts.extend(dd.get("alerts", []))

        if freight_kind == "air" or deal.get("awb_number"):
            if direction == "export":
                air_export.append(dd)
            else:
                air_import.append(dd)
        else:
            if direction == "export":
                sea_export.setdefault(port_code, []).append(dd)
            else:
                sea_import.setdefault(port_code, []).append(dd)

    # Count summary
    urgent_count = sum(1 for a in all_alerts if a.get("severity") == "critical")
    warning_count = sum(1 for a in all_alerts if a.get("severity") == "warning")
    active_count = len(deals_data)

    # Build HTML
    parts = []
    parts.append(_digest_html_open())
    parts.append(_digest_header(now_dt))
    parts.append(_digest_summary_bar(urgent_count, warning_count, active_count))

    if all_alerts:
        parts.append(_digest_alerts_section(all_alerts))

    # Sea Import sections (per port)
    first_import = True
    for port_info in DIGEST_SEA_PORTS:
        code = port_info["code"]
        deals = sea_import.get(code, [])
        margin = "" if first_import else ' style="margin-top:10px"'
        parts.append(_digest_section_header("⚓ ייבוא ים", port_info["name_he"], code, margin))
        if deals:
            parts.append(_digest_sea_import_table(deals, now_dt))
            # Per-port alert row
            port_alerts = [a for d in deals for a in d.get("alerts", [])]
            if port_alerts:
                parts.append(_digest_alert_row(port_alerts))
        else:
            parts.append('<div class="empty-port">אין משלוחים פעילים כיום</div>')
        first_import = False

    # Sea Export sections (per port)
    for port_info in DIGEST_SEA_PORTS:
        code = port_info["code"]
        deals = sea_export.get(code, [])
        parts.append(_digest_section_header("📦 יצוא ים", port_info["name_he"], code, ' style="margin-top:10px"'))
        if deals:
            parts.append(_digest_sea_export_table(deals, now_dt))
            port_alerts = [a for d in deals for a in d.get("alerts", [])]
            if port_alerts:
                parts.append(_digest_alert_row(port_alerts))
        else:
            parts.append('<div class="empty-port">אין משלוחים פעילים כיום</div>')

    # Air Import
    parts.append(_digest_section_header("✈ ייבוא אוויר", "נתב״ג", "TLV · LLBG", ' style="margin-top:10px"', is_air=True))
    if air_import:
        parts.append(_digest_air_import_table(air_import, now_dt))
    else:
        parts.append('<div class="empty-port">אין משלוחים פעילים כיום</div>')

    # Air Export
    parts.append(_digest_section_header("📤 יצוא אוויר", "נתב״ג", "TLV · LLBG", ' style="margin-top:10px"', is_air=True))
    if air_export:
        parts.append(_digest_air_export_table(air_export, now_dt))
    else:
        parts.append('<div class="empty-port">אין משלוחים פעילים כיום</div>')

    # Divider
    parts.append('<hr class="dv" style="margin-top:14px">')

    # Port Status
    parts.append(_digest_port_status(port_reports))

    # Elaboration
    notes = _collect_elaboration_notes(deals_data, port_reports)
    if notes:
        parts.append(_digest_elaboration(notes))

    parts.append(_digest_footer(now_dt))
    parts.append(_digest_html_close())

    return "\n".join(parts)


# ── Digest HTML structure ──

def _digest_html_open():
    """HTML open with full CSS from v4 template."""
    return '''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#eef0f3;font-family:'Heebo',Arial,sans-serif;color:#1a1a2e;direction:rtl;font-size:13px}
.ew{max-width:960px;margin:0 auto;background:#fff}
.hdr{background:#0d1b2a;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #00b4d8}
.brand{display:flex;align-items:center;gap:10px}
.bbox{background:linear-gradient(135deg,#00b4d8,#0077b6);border-radius:6px;padding:5px 9px;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;color:#fff}
.bn{color:#fff;font-size:16px;font-weight:700;letter-spacing:2px}
.bs{color:#90e0ef;font-size:10px;font-weight:300;margin-top:1px}
.hr2{text-align:left;direction:ltr}
.hd{color:#caf0f8;font-size:13px;font-weight:600}
.ht{color:#48cae4;font-size:10px;font-family:'IBM Plex Mono',monospace;margin-top:2px}
.sbar{background:#023e8a;padding:8px 24px;display:flex;gap:20px;align-items:center;justify-content:flex-end}
.sp{display:flex;align-items:center;gap:5px;font-size:12px;color:#caf0f8}
.sp strong{color:#fff;font-size:14px}
.dot{width:7px;height:7px;border-radius:50%}
.dr{background:#ef233c}.do{background:#f77f00}.dg{background:#06d6a0}
.to-badge{font-size:11px;padding:3px 12px;border-radius:12px;background:#1a3a5c;color:#90e0ef;font-family:'IBM Plex Mono',monospace;margin-right:auto;direction:ltr}
.ab{padding:10px 24px 0;display:flex;flex-direction:column;gap:6px}
.as{border-radius:4px;padding:8px 14px;font-size:12px;display:flex;align-items:center;gap:8px}
.as.crit{background:#fde8ec;border-right:4px solid #ef233c;color:#7d0012}
.as.warn{background:#fff3cd;border-right:4px solid #f77f00;color:#7d4f00}
.sec{padding:16px 24px 5px;display:flex;align-items:center;gap:10px}
.sl{font-size:11px;font-weight:700;letter-spacing:2px;color:#495057;white-space:nowrap}
.ptag{font-size:11px;font-weight:700;padding:2px 10px;border-radius:12px;background:#e8f4fd;color:#023e8a;letter-spacing:0.5px;white-space:nowrap;font-family:'IBM Plex Mono',monospace}
.ptag.air{background:#f3e8fd;color:#4a0d8f}
.sln{flex:1;height:1px;background:#dee2e6}
.tw{padding:0 24px;overflow-x:auto}
.pt{width:100%;border-collapse:collapse;font-size:11px;direction:rtl;min-width:800px}
.pt thead tr{background:#f1f3f5;border-top:1px solid #dee2e6;border-bottom:2px solid #dee2e6}
.pt thead th{padding:6px 7px;text-align:right;font-size:10px;font-weight:700;color:#6c757d;letter-spacing:.3px;white-space:nowrap}
.pt thead th.grp-arr{background:#eaf4fb;color:#023e8a;border-bottom:2px solid #00b4d8}
.pt thead th.grp-dep{background:#eafbf0;color:#1b4332;border-bottom:2px solid #06d6a0}
.pt thead th.grp-ops{background:#f8f9fa;color:#495057}
.pt tbody tr{border-bottom:1px solid #f1f3f5}
.pt tbody tr:hover{background:#f8f9fa}
.pt tbody tr.ra{background:#fffdf0;border-right:3px solid #f77f00}
.pt tbody tr.rc{background:#fff5f7;border-right:3px solid #ef233c}
.pt td{padding:6px 7px;vertical-align:middle}
.en{font-family:'IBM Plex Mono',monospace;direction:ltr;text-align:left;font-size:11px}
.vn{font-family:'IBM Plex Mono',monospace;direction:ltr;font-size:11px;font-weight:600;color:#0d1b2a}
.dt{font-family:'IBM Plex Mono',monospace;font-size:11px;direction:ltr;text-align:center;white-space:nowrap}
.dta{color:#ef233c;font-weight:700}
.dtw{color:#d97706;font-weight:700}
.sub{font-size:10px;color:#adb5bd;font-family:'IBM Plex Mono',monospace;margin-top:2px;line-height:1.3}
.sw{color:#d97706}.sc{color:#ef233c}
.ctr{text-align:center}
.sb{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:10px;background:#e8f4fd;color:#023e8a}
.chip{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;white-space:nowrap}
.cr{background:#fde8ec;color:#c9184a}
.co{background:#fff3cd;color:#d97706}
.cg{background:#d8f3dc;color:#1b4332}
.cb{background:#e8f4fd;color:#023e8a}
.cgr{background:#f1f3f5;color:#6c757d}
.cp{background:#f3e8fd;color:#6a0dad}
.yy{color:#1b4332;font-weight:700;font-size:13px}
.yn{color:#c9184a;font-weight:700;font-size:13px}
.na{color:#adb5bd;font-size:12px}
.ar{padding:7px 14px;font-size:11px;display:flex;align-items:center;gap:6px;border-top:1px solid #ffe8cc;border-bottom:1px solid #ffe8cc;background:#fff8f0;color:#7d4f00}
.ar.crit{background:#fff0f3;color:#7d0012;border-color:#ffc0cb}
.psr{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin:4px 24px 12px}
.pb{border:1px solid #dee2e6;border-radius:6px;overflow:hidden}
.pbh{background:#f1f3f5;padding:5px 10px;font-size:10px;font-weight:700;color:#495057;letter-spacing:.5px;display:flex;justify-content:space-between;align-items:center;white-space:nowrap}
.pbb{padding:7px 10px}
.psl{display:flex;justify-content:space-between;font-size:10px;color:#6c757d;margin-bottom:3px}
.psv{font-weight:700;color:#1a1a2e;font-family:'IBM Plex Mono',monospace;font-size:10px}
.bw{height:3px;background:#dee2e6;border-radius:2px;margin-top:5px;overflow:hidden}
.bf{height:100%;border-radius:2px}
.bok{background:#06d6a0}.bwn{background:#f77f00}
.el{margin:0 24px 14px;border:1px solid #e9ecef;border-radius:6px;overflow:hidden}
.elh{background:#f8f9fa;padding:7px 14px;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#adb5bd;border-bottom:1px solid #e9ecef}
.elb{padding:12px 14px;font-size:12px;color:#495057;line-height:1.8}
.elb p{margin-bottom:8px}
.elb p:last-child{margin-bottom:0}
.ftr{background:#0d1b2a;padding:14px 24px;text-align:center;direction:ltr}
.fm{color:#48cae4;font-size:11px;font-family:'IBM Plex Mono',monospace}
.fs{color:#4a5568;font-size:10px;margin-top:3px}
hr.dv{border:none;border-top:1px solid #dee2e6;margin:8px 24px}
.col-arr{border-left:2px solid #00b4d8;border-right:none}
.col-dep{border-left:2px solid #06d6a0;border-right:none}
.empty-port{padding:8px 24px;font-size:11px;color:#adb5bd;font-style:italic}
</style>
</head>
<body>
<div class="ew">'''


def _digest_html_close():
    return '</div>\n</body>\n</html>'


def _digest_header(now_dt):
    date_str = now_dt.strftime("%d.%m.%Y")
    time_str = now_dt.strftime("%H:%M")
    return f'''
<div class="hdr">
  <div class="brand">
    <div class="bbox">RCB</div>
    <div><div class="bn">R.P.A. PORT LTD</div><div class="bs">Robot Customs Broker · Haifa</div></div>
  </div>
  <div class="hr2"><div class="hd">דוח בוקר | {date_str}</div><div class="ht">{time_str} · AUTO-GENERATED · TO: cc@rpa-port.co.il</div></div>
</div>'''


def _digest_summary_bar(urgent, warning, active):
    return f'''
<div class="sbar">
  <div class="sp"><div class="dot dr"></div><strong>{urgent}</strong> דחוף</div>
  <div class="sp"><div class="dot do"></div><strong>{warning}</strong> אזהרה</div>
  <div class="sp"><div class="dot dg"></div><strong>{active}</strong> משלוחים פעילים</div>
</div>'''


def _digest_alerts_section(alerts):
    parts = ['<div class="ab">']
    for a in alerts:
        severity = a.get("severity", "warning")
        css = "crit" if severity == "critical" else "warn"
        icon = "🚨" if severity == "critical" else "⚡"
        msg = a.get("message_he", "")
        parts.append(f'  <div class="as {css}">{icon} <strong>{a.get("details", {}).get("container_id") or a.get("details", {}).get("bol_number", "")}:</strong> {msg}</div>')
    parts.append('</div>')
    return "\n".join(parts)


def _digest_section_header(icon_label, port_name, code, margin_style="", is_air=False):
    tag_class = "ptag air" if is_air else "ptag"
    return f'<div class="sec"{margin_style}><span class="sl">{icon_label}</span><span class="{tag_class}">{port_name} · {code}</span><div class="sln"></div></div>'


def _digest_alert_row(alerts):
    """Build inline alert row below a table."""
    if not alerts:
        return ""
    severity = max((a.get("severity", "warning") for a in alerts), key=lambda s: 0 if s == "warning" else 1)
    css = " crit" if severity == "critical" else ""
    icon = "🚨" if severity == "critical" else "⚡"
    msgs = [a.get("message_he", "") for a in alerts]
    return f'<div class="ar{css}">{icon} {" &nbsp;|&nbsp; ".join(msgs)}</div>'


# ── Sea Import Table ──

def _digest_sea_import_table(deals, now_dt):
    """Build complete sea import table for a port."""
    parts = ['<div class="tw"><table class="pt">', '<thead>', '  <tr>',
        '    <th rowspan="2" class="grp-ops">שם אוניה</th>',
        '    <th rowspan="2" class="grp-ops">B/L</th>',
        '    <th rowspan="2" class="grp-ops">משמרת</th>',
        '    <th colspan="2" class="grp-arr" style="text-align:center">הגעה</th>',
        '    <th colspan="2" class="grp-dep" style="text-align:center">עזיבה</th>',
        '    <th rowspan="2" class="grp-ops">רציף</th>',
        '    <th rowspan="2" class="grp-ops">D/O<br>התקבל</th>',
        '    <th rowspan="2" class="grp-ops">עצירה /<br>בדיקה</th>',
        '    <th rowspan="2" class="grp-ops">ימי<br>אחסנה</th>',
        '    <th rowspan="2" class="grp-ops">מכולה<br>פונתה</th>',
        '    <th rowspan="2" class="grp-ops">סטטוס</th>',
        '  </tr>', '  <tr>',
        '    <th class="grp-arr">ETA</th>',
        '    <th class="grp-arr">ATA</th>',
        '    <th class="grp-dep">ETD</th>',
        '    <th class="grp-dep">ATD</th>',
        '  </tr>', '</thead>', '<tbody>']

    for idx, dd in enumerate(deals):
        parts.append(_digest_sea_import_row(idx, dd, now_dt))

    parts.append('</tbody>\n</table></div>')
    return "\n".join(parts)


def _digest_sea_import_row(idx, dd, now_dt):
    """Build a single sea import row."""
    deal = dd["deal"]
    css = dd.get("container_statuses", [])
    schedule = dd.get("schedule_link") or {}
    containers = dd.get("container_statuses", [])
    deal_alerts = dd.get("alerts", [])

    vessel = _sanitize_vessel_name(deal.get("vessel_name", ""))
    bol = deal.get("bol_number", "")
    letter = _HEBREW_LETTERS[idx % len(_HEBREW_LETTERS)] + "׳"

    # ETA / ATA
    eta_sources = _build_eta_sources(deal, schedule, containers)
    eta_consol = consolidate_datetime_field(eta_sources)
    eta_str = _format_date_short(eta_consol["best"]) if eta_consol["best"] else "—"

    ata_str = "—"
    arrived = False
    for cs in containers:
        proc = cs.get("import_process") or {}
        if proc.get("PortUnloadingDate"):
            ata_str = _format_date_short(proc["PortUnloadingDate"])
            arrived = True
            break

    # ETD / ATD
    etd_str = _format_date_short(schedule.get("schedule_etd", "")) if schedule else "—"
    atd_str = "—"  # ATD only if vessel departed — not typically relevant for import

    # Berth
    berth = schedule.get("berth", "—") if schedule else "—"

    # D/O received
    do_received = False
    for cs in containers:
        proc = cs.get("import_process") or {}
        if proc.get("DeliveryOrderDate"):
            do_received = True
            break
    do_cell = '<span class="yy">✓</span>' if do_received else '<span class="yn">✗</span>'

    # Examination
    exam_open = False
    for cs in containers:
        proc = cs.get("import_process") or {}
        if proc.get("CustomsCheckDate") and not proc.get("CustomsReleaseDate"):
            exam_open = True
            break
    if exam_open:
        exam_cell = '<span class="chip co">בדיקה</span>'
    else:
        released = any(
            (cs.get("import_process") or {}).get("CustomsReleaseDate")
            for cs in containers
        )
        exam_cell = '<span class="chip cg">שוחרר</span>' if released else '<span class="na">—</span>'

    # Storage days
    storage = _compute_storage_risk_import(containers, now_dt)
    days = storage["days_at_port"]
    if days > 0 and storage["level"] != "none":
        if storage["level"] == "critical":
            storage_cell = f'<div class="ctr"><strong>{days:.0f}</strong></div><div class="sub sc ctr">חיוב</div>'
        elif storage["level"] == "warning":
            storage_cell = f'<div class="ctr"><strong>{days:.0f}</strong></div><div class="sub sc ctr">מחר חיוב</div>'
        elif storage["level"] == "notice":
            storage_cell = f'<div class="ctr"><strong>{days:.0f}</strong></div><div class="sub sw ctr">עוד {STORAGE_CRITICAL_DAYS - days:.0f} ימים</div>'
        else:
            storage_cell = f'<div class="ctr"><strong>{days:.0f}</strong></div>'
    elif arrived:
        storage_cell = f'<div class="ctr"><strong>{max(days, 0):.0f}</strong></div>'
    else:
        storage_cell = '<span class="chip cgr">טרם הגיע</span>'

    # Container evacuated
    all_exited = containers and all(
        (cs.get("import_process") or {}).get("CargoExitDate")
        for cs in containers
    )
    exit_cell = '<span class="yy">✓</span>' if all_exited else '<span class="yn">✗</span>'

    # Status chip
    has_critical = any(a.get("severity") == "critical" for a in deal_alerts)
    has_warning = any(a.get("severity") == "warning" for a in deal_alerts)
    if has_critical:
        status_chip = '<span class="chip cr">דחוף</span>'
        row_class = ' class="rc"'
    elif has_warning:
        status_chip = '<span class="chip co">אזהרה</span>'
        row_class = ' class="ra"'
    elif all_exited:
        status_chip = '<span class="chip cg">הושלם</span>'
        row_class = ''
    elif arrived:
        status_chip = '<span class="chip cg">תקין</span>'
        row_class = ''
    else:
        status_chip = '<span class="chip cg">תקין</span>'
        row_class = ''

    eta_cls = ""
    ata_cls = ' class="na"' if ata_str == "—" else ""
    atd_cls = ' class="na"' if atd_str == "—" else ""

    return f'''<tr{row_class}>
  <td><div class="vn">{vessel}</div></td>
  <td><div class="en">{bol}</div></td>
  <td class="ctr"><span class="sb">{letter}</span></td>
  <td class="col-arr"><div class="dt{eta_cls}">{eta_str}</div></td>
  <td><div class="dt{ata_cls}">{ata_str}</div></td>
  <td class="col-dep"><div class="dt">{etd_str}</div></td>
  <td><div class="dt{atd_cls}">{atd_str}</div></td>
  <td class="ctr">{berth if berth and berth != "—" else "—"}</td>
  <td class="ctr">{do_cell}</td>
  <td class="ctr">{exam_cell}</td>
  <td>{storage_cell}</td>
  <td class="ctr">{exit_cell}</td>
  <td>{status_chip}</td>
</tr>'''


# ── Sea Export Table ──

def _digest_sea_export_table(deals, now_dt):
    parts = ['<div class="tw"><table class="pt">', '<thead>', '  <tr>',
        '    <th rowspan="2" class="grp-ops">שם אוניה</th>',
        '    <th rowspan="2" class="grp-ops">Booking</th>',
        '    <th rowspan="2" class="grp-ops">משמרת</th>',
        '    <th colspan="2" class="grp-arr" style="text-align:center">הגעה לנמל</th>',
        '    <th colspan="2" class="grp-dep" style="text-align:center">יציאה מנמל</th>',
        '    <th rowspan="2" class="grp-ops">רציף</th>',
        '    <th rowspan="2" class="grp-ops">סגירת<br>דוקומנטים</th>',
        '    <th rowspan="2" class="grp-ops">VGM</th>',
        '    <th rowspan="2" class="grp-ops">סגירת מכולות<br>בנמל</th>',
        '    <th rowspan="2" class="grp-ops">מכולה<br>נכנסה</th>',
        '    <th rowspan="2" class="grp-ops">B/L<br>הוצא</th>',
        '    <th rowspan="2" class="grp-ops">סטטוס</th>',
        '  </tr>', '  <tr>',
        '    <th class="grp-arr">ETA</th><th class="grp-arr">ATA</th>',
        '    <th class="grp-dep">ETD</th><th class="grp-dep">ATD</th>',
        '  </tr>', '</thead>', '<tbody>']

    for idx, dd in enumerate(deals):
        parts.append(_digest_sea_export_row(idx, dd, now_dt))

    parts.append('</tbody>\n</table></div>')
    return "\n".join(parts)


def _digest_sea_export_row(idx, dd, now_dt):
    deal = dd["deal"]
    schedule = dd.get("schedule_link") or {}
    containers = dd.get("container_statuses", [])
    deal_alerts = dd.get("alerts", [])

    vessel = _sanitize_vessel_name(deal.get("vessel_name", ""))
    booking = deal.get("booking_number", "") or deal.get("bol_number", "")
    letter = _HEBREW_LETTERS[idx % len(_HEBREW_LETTERS)] + "׳"

    # ETA / ATA (vessel arrival at port)
    eta_str = _format_date_short(schedule.get("schedule_eta", "")) if schedule else "—"
    ata_str = "—"

    # ETD / ATD
    etd_sources = _build_etd_sources(deal, schedule, containers)
    etd_consol = consolidate_datetime_field(etd_sources)
    etd_str = _format_date_short(etd_consol["best"]) if etd_consol["best"] else "—"

    atd_str = "—"
    for cs in containers:
        proc = cs.get("export_process") or {}
        if proc.get("ShipSailingDate"):
            atd_str = _format_date_short(proc["ShipSailingDate"])
            break

    berth = schedule.get("berth", "—") if schedule else "—"

    # Cutoffs
    doc_cutoff = _format_date_short(deal.get("doc_cutoff", "")) or "—"
    vgm_cutoff = _format_date_short(deal.get("vgm_cutoff", "")) or "—"
    container_cutoff = _format_date_short(deal.get("container_cutoff", "")) or "—"

    # Cutoff urgency styling
    def _cutoff_cell(val, raw_dt_str):
        if val == "—":
            return f'<div class="dt">{val}</div>'
        dt = _parse_iso(raw_dt_str)
        if dt:
            hours = _hours_until(dt, now_dt)
            if hours is not None and 0 < hours < 24:
                return f'<div class="dt dtw">{val}</div><div class="sub sw">מחר</div>'
            elif hours is not None and hours <= 0:
                return f'<div class="dt dta">{val}</div><div class="sub sc">עבר</div>'
        return f'<div class="dt">{val}</div>'

    doc_cell = _cutoff_cell(doc_cutoff, deal.get("doc_cutoff", ""))
    vgm_cell = _cutoff_cell(vgm_cutoff, deal.get("vgm_cutoff", ""))
    cnt_cell = _cutoff_cell(container_cutoff, deal.get("container_cutoff", ""))

    # Container entered port
    cargo_entered = any(
        (cs.get("export_process") or {}).get("CargoEntryDate")
        for cs in containers
    )
    enter_cell = '<span class="yy">✓</span>' if cargo_entered else '<span class="yn">✗</span>'

    # BL issued
    bl_issued = bool(deal.get("bol_number"))
    bl_cell = '<span class="yy">✓</span>' if bl_issued else '<span class="yn">✗</span>'

    # Status
    has_critical = any(a.get("severity") == "critical" for a in deal_alerts)
    has_warning = any(a.get("severity") == "warning" for a in deal_alerts)
    departed = atd_str != "—"
    if has_critical:
        status_chip = '<span class="chip cr">דחוף</span>'
        row_class = ' class="rc"'
    elif has_warning:
        status_chip = '<span class="chip co">אזהרה</span>'
        row_class = ' class="ra"'
    elif departed:
        status_chip = '<span class="chip cg">הפליגה</span>'
        row_class = ''
    else:
        status_chip = '<span class="chip cg">תקין</span>'
        row_class = ''

    return f'''<tr{row_class}>
  <td><div class="vn">{vessel}</div></td>
  <td><div class="en">{booking}</div></td>
  <td class="ctr"><span class="sb">{letter}</span></td>
  <td class="col-arr"><div class="dt">{eta_str}</div></td>
  <td><div class="dt na">{"—" if ata_str == "—" else ata_str}</div></td>
  <td class="col-dep"><div class="dt">{etd_str}</div></td>
  <td><div class="dt na">{"—" if atd_str == "—" else atd_str}</div></td>
  <td class="ctr">{berth if berth and berth != "—" else "—"}</td>
  <td>{doc_cell}</td>
  <td>{vgm_cell}</td>
  <td>{cnt_cell}</td>
  <td class="ctr">{enter_cell}</td>
  <td class="ctr">{bl_cell}</td>
  <td>{status_chip}</td>
</tr>'''


# ── Air Import Table ──

def _digest_air_import_table(deals, now_dt):
    parts = ['<div class="tw"><table class="pt">', '<thead>', '  <tr>',
        '    <th rowspan="2" class="grp-ops">טיסה</th>',
        '    <th rowspan="2" class="grp-ops">AWB</th>',
        '    <th rowspan="2" class="grp-ops">נוחת מ</th>',
        '    <th colspan="2" class="grp-arr" style="text-align:center">הגעה</th>',
        '    <th rowspan="2" class="grp-ops">טרמינל<br>מטענים</th>',
        '    <th rowspan="2" class="grp-ops">AWB<br>התקבל</th>',
        '    <th rowspan="2" class="grp-ops">טיפול<br>מיוחד</th>',
        '    <th rowspan="2" class="grp-ops">עצירה /<br>בדיקה</th>',
        '    <th rowspan="2" class="grp-ops">שוחרר<br>מכס</th>',
        '    <th rowspan="2" class="grp-ops">סטטוס</th>',
        '  </tr>', '  <tr>',
        '    <th class="grp-arr">ETA</th><th class="grp-arr">ATA</th>',
        '  </tr>', '</thead>', '<tbody>']

    for idx, dd in enumerate(deals):
        parts.append(_digest_air_import_row(idx, dd, now_dt))

    parts.append('</tbody>\n</table></div>')
    return "\n".join(parts)


def _digest_air_import_row(idx, dd, now_dt):
    deal = dd["deal"]
    awb = dd.get("awb_status") or {}

    awb_number = deal.get("awb_number", "") or awb.get("awb_number", "")
    flight_info = deal.get("flight_number", "") or awb.get("flight_number", "")
    airline = deal.get("carrier_name", "") or awb.get("airline_name", "")
    if flight_info and airline:
        flight_display = f"{airline} {flight_info}"
    elif flight_info:
        flight_display = flight_info
    else:
        flight_display = airline or "—"

    origin = deal.get("pol", "") or deal.get("origin", "") or "—"

    # ETA / ATA
    eta_str = _format_date_short(deal.get("eta", "")) or "—"
    ata_str = "—"
    status_norm = awb.get("status_normalized", "")
    arrived = status_norm in ("arrived", "at_terminal", "ready", "hold",
                              "customs_hold", "released", "customs_released", "delivered")
    if arrived and awb.get("arrived_at"):
        ata_str = _format_date_short(awb["arrived_at"])

    terminal = awb.get("terminal", "") or "—"
    awb_received = bool(awb_number)
    awb_cell = '<span class="yy">✓</span>' if awb_received else '<span class="yn">✗</span>'

    # Special handling
    special = deal.get("special_handling", "") or "—"
    if special and special != "—":
        special_cell = f'<span class="chip cp">{special}</span>'
    else:
        special_cell = '<span class="na">—</span>'

    # Examination
    hold = status_norm in ("hold", "customs_hold")
    released = status_norm in ("released", "customs_released")
    if hold:
        exam_cell = '<span class="chip co">עצירה</span>'
    else:
        exam_cell = '<span class="na">—</span>'

    release_cell = '<span class="yy">✓</span>' if released else '<span class="yn">✗</span>'

    # Status chip
    if hold:
        status_chip = '<span class="chip cr">עצירה</span>'
        row_class = ' class="rc"'
    elif not arrived and eta_str != "—":
        eta_dt = _parse_iso(deal.get("eta", ""))
        hours = _hours_until(eta_dt, now_dt) if eta_dt else None
        if hours is not None and 0 < hours < 12:
            status_chip = '<span class="chip co">הלילה</span>' if hours < 8 else '<span class="chip cb">ממתין</span>'
            row_class = ' class="ra"'
        else:
            status_chip = '<span class="chip cb">ממתין</span>'
            row_class = ''
    elif released:
        status_chip = '<span class="chip cg">שוחרר</span>'
        row_class = ''
    else:
        status_chip = '<span class="chip cb">ממתין</span>'
        row_class = ''

    return f'''<tr{row_class}>
  <td><div class="vn">{flight_display}</div></td>
  <td><div class="en">{awb_number}</div></td>
  <td>{origin}</td>
  <td class="col-arr"><div class="dt">{eta_str}</div></td>
  <td><div class="dt{"" if ata_str != "—" else " na"}">{ata_str}</div></td>
  <td class="ctr">{terminal}</td>
  <td class="ctr">{awb_cell}</td>
  <td class="ctr">{special_cell}</td>
  <td class="ctr">{exam_cell}</td>
  <td class="ctr">{release_cell}</td>
  <td>{status_chip}</td>
</tr>'''


# ── Air Export Table ──

def _digest_air_export_table(deals, now_dt):
    parts = ['<div class="tw"><table class="pt">', '<thead>', '  <tr>',
        '    <th rowspan="2" class="grp-ops">טיסה</th>',
        '    <th rowspan="2" class="grp-ops">AWB</th>',
        '    <th rowspan="2" class="grp-ops">יעד</th>',
        '    <th colspan="2" class="grp-dep" style="text-align:center">יציאה</th>',
        '    <th rowspan="2" class="grp-ops">כניסה לשדה<br>(48–24h לפני)</th>',
        '    <th rowspan="2" class="grp-ops">מטען נבנה<br>ל-ULD</th>',
        '    <th rowspan="2" class="grp-ops">AWB<br>הוצא</th>',
        '    <th rowspan="2" class="grp-ops">דוקומנטים<br>נשלחו</th>',
        '    <th rowspan="2" class="grp-ops">טיפול<br>מיוחד</th>',
        '    <th rowspan="2" class="grp-ops">סטטוס</th>',
        '  </tr>', '  <tr>',
        '    <th class="grp-dep">ETD</th><th class="grp-dep">ATD</th>',
        '  </tr>', '</thead>', '<tbody>']

    for idx, dd in enumerate(deals):
        parts.append(_digest_air_export_row(idx, dd, now_dt))

    parts.append('</tbody>\n</table></div>')
    return "\n".join(parts)


def _digest_air_export_row(idx, dd, now_dt):
    deal = dd["deal"]
    awb = dd.get("awb_status") or {}

    awb_number = deal.get("awb_number", "") or awb.get("awb_number", "")
    flight_info = deal.get("flight_number", "") or awb.get("flight_number", "")
    airline = deal.get("carrier_name", "") or awb.get("airline_name", "")
    flight_display = f"{airline} {flight_info}" if flight_info and airline else (flight_info or airline or "—")

    destination = deal.get("pod", "") or deal.get("destination", "") or "—"

    # ETD / ATD
    etd_str = _format_date_short(deal.get("etd", "")) or "—"
    atd_str = "—"

    # Field entry window (48-24h before ETD)
    etd_dt = _parse_iso(deal.get("etd", ""))
    if etd_dt:
        entry_window = f'{_format_date_short((etd_dt - timedelta(hours=48)).isoformat())}–{_format_date_short((etd_dt - timedelta(hours=24)).isoformat())}'
        hours_to = _hours_until(etd_dt, now_dt)
        if hours_to is not None and 24 < hours_to < 48:
            entry_cell = f'<div class="dt dtw">{entry_window}</div><div class="sub sw">חלון פתוח</div>'
        elif hours_to is not None and hours_to <= 24:
            entry_cell = f'<div class="dt dta">{entry_window}</div><div class="sub sc">דחוף</div>'
        else:
            entry_cell = f'<div class="dt">{entry_window}</div><div class="sub">חלון 48–24h</div>'
    else:
        entry_cell = '<div class="dt na">—</div>'

    # ULD built
    uld_cell = '<span class="na">—</span>'

    # AWB issued
    awb_issued = bool(awb_number)
    awb_cell = '<span class="yy">✓</span>' if awb_issued else '<span class="yn">✗</span>'

    # Docs sent
    docs_sent = bool(deal.get("docs_sent"))
    docs_cell = '<span class="yy">✓</span>' if docs_sent else '<span class="yn">✗</span>'

    # Special handling
    special = deal.get("special_handling", "") or "—"
    special_cell = f'<span class="chip cp">{special}</span>' if special and special != "—" else '<span class="na">—</span>'

    # Status
    status_chip = '<span class="chip cb">בתהליך</span>'
    row_class = ''
    if etd_dt:
        hours = _hours_until(etd_dt, now_dt)
        if hours is not None and 0 < hours < 12:
            status_chip = '<span class="chip co">אזהרה</span>'
            row_class = ' class="ra"'

    return f'''<tr{row_class}>
  <td><div class="vn">{flight_display}</div></td>
  <td><div class="en">{awb_number}</div></td>
  <td>{destination}</td>
  <td class="col-dep"><div class="dt">{etd_str}</div></td>
  <td><div class="dt na">{atd_str}</div></td>
  <td>{entry_cell}</td>
  <td class="ctr">{uld_cell}</td>
  <td class="ctr">{awb_cell}</td>
  <td class="ctr">{docs_cell}</td>
  <td class="ctr">{special_cell}</td>
  <td>{status_chip}</td>
</tr>'''


# ── Port Status ──

def _digest_port_status(port_reports):
    parts = [
        '<div class="sec"><span class="sl">🏭 סטטוס נמלים</span><div class="sln"></div></div>',
        '<div class="psr">',
    ]
    for port_info in DIGEST_SEA_PORTS:
        code = port_info["code"]
        report = port_reports.get(code, {})
        parts.append(_digest_port_card(port_info, report))
    parts.append('</div>')
    return "\n".join(parts)


def _digest_port_card(port_info, report):
    code = port_info["code"]
    name = port_info["name_he"]
    capacity = port_info["capacity"]
    gate_hours = port_info["gate_hours"]

    total_vessels = report.get("total_vessels", 0)
    waiting = report.get("vessels_waiting", 0)
    avg_delay = report.get("average_delay_hours")

    # Congestion level
    if total_vessels > CONGESTION_CONGESTED:
        chip = '<span class="chip cr">עמוס מאוד</span>'
        bar_class = "bwn"
    elif total_vessels > CONGESTION_BUSY:
        chip = '<span class="chip co">עמוס</span>'
        bar_class = "bwn"
    else:
        chip = '<span class="chip cg">תקין</span>'
        bar_class = "bok"

    pct = min(100, round((total_vessels / max(capacity, 1)) * 100))
    delay_str = f"+{avg_delay:.0f} שעות" if avg_delay and avg_delay > 0 else "תקין"

    return f'''  <div class="pb">
    <div class="pbh">{name} · {code} {chip}</div>
    <div class="pbb">
      <div class="psl"><span>כלי שיט בנמל</span><span class="psv">{total_vessels} / {capacity}</span></div>
      <div class="psl"><span>ממתינים לעגינה</span><span class="psv">{waiting}</span></div>
      <div class="psl"><span>עיכוב ממוצע</span><span class="psv">{delay_str}</span></div>
      <div class="psl"><span>שעות שער</span><span class="psv">{gate_hours}</span></div>
      <div class="bw"><div class="bf {bar_class}" style="width:{pct}%"></div></div>
    </div>
  </div>'''


# ── Elaboration ──

def _collect_elaboration_notes(deals_data, port_reports):
    """Collect automatic elaboration notes from deal data."""
    notes = []
    for dd in deals_data:
        deal = dd["deal"]
        deal_alerts = dd.get("alerts", [])
        if not deal_alerts:
            continue

        vessel = deal.get("vessel_name", "")
        bol = deal.get("bol_number", "") or deal.get("awb_number", "") or deal.get("booking_number", "")
        port_code = (deal.get("port") or "").upper()
        port_info = SEA_PORTS.get(port_code, AIR_PORTS.get(port_code, {}))
        port_name = port_info.get("name_he", port_code) if port_info else port_code

        for alert in deal_alerts:
            msg = alert.get("message_he", "")
            notes.append(f"<strong>{bol} / {vessel} / {port_name}:</strong> {msg}")

    # Port congestion notes
    for port_info in DIGEST_SEA_PORTS:
        code = port_info["code"]
        report = port_reports.get(code, {})
        total = report.get("total_vessels", 0)
        if total > CONGESTION_BUSY:
            notes.append(
                f'<strong>{port_info["name_he"]} — עומס:</strong> '
                f'{total} כלי שיט בנמל (סף עמוס &gt;{CONGESTION_BUSY}). '
                f'לתכנן פינויים בהתאם.'
            )

    return notes


def _digest_elaboration(notes):
    if not notes:
        return ""
    parts = [
        '<div class="sec"><span class="sl">📋 פירוט · הערות</span><div class="sln"></div></div>',
        '<div class="el">',
        '  <div class="elh">פירוט נוסף · הערות צוות</div>',
        '  <div class="elb">',
    ]
    for note in notes:
        parts.append(f'    <p>{note}</p>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


def _digest_footer(now_dt):
    date_str = now_dt.strftime("%d.%m.%Y")
    time_str = now_dt.strftime("%H:%M")
    return f'''
<div class="ftr">
  <div class="fm">RCB · R.P.A. PORT LTD · Haifa · rcb@rpa-port.co.il · TO: cc@rpa-port.co.il</div>
  <div class="fs">Generated automatically · {date_str} {time_str} · אין להשיב למייל זה · RCB חבר בקבוצת CC@ ואינו משיב לעצמו</div>
</div>'''
