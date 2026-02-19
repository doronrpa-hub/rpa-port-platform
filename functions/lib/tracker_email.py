"""
RCB Tracker Email Builder
=========================
Builds visual HTML emails for deal status updates.
Progress bar style inspired by TaskYam but covers ALL containers in one email.
Works in Outlook, Gmail, Apple Mail (table-based, inline CSS).
All timestamps displayed in Israel time (Asia/Jerusalem).
"""
from datetime import datetime, timezone, timedelta

try:
    from lib.librarian import get_israeli_hs_format as _hs_fmt
except ImportError:
    _hs_fmt = None

# Israel timezone: UTC+2 (IST) or UTC+3 (IDT, summer)
# Simple approach: use fixed offset. For production, use zoneinfo if available.
try:
    from zoneinfo import ZoneInfo
    IL_TZ = ZoneInfo("Asia/Jerusalem")
except ImportError:
    IL_TZ = None

# Israel standard offset (UTC+2), summer (UTC+3)
_IL_STANDARD = timedelta(hours=2)
_IL_SUMMER = timedelta(hours=3)

# ── Branding / color constants ──
RPA_BLUE = "#1e3a5f"
RPA_ACCENT = "#2471a3"
COLOR_OK = "#27ae60"
COLOR_WARN = "#f39c12"
COLOR_ERR = "#e74c3c"
COLOR_PENDING = "#999999"


def _to_israel_time(dt_obj):
    """Convert a datetime to Israel time."""
    if IL_TZ:
        return dt_obj.astimezone(IL_TZ)
    # Fallback: approximate Israel DST (last Friday of March → last Sunday of October)
    month = dt_obj.month
    if 4 <= month <= 9:
        return dt_obj + _IL_SUMMER
    elif month == 3 and dt_obj.day >= 25:
        return dt_obj + _IL_SUMMER
    elif month == 10 and dt_obj.day <= 25:
        return dt_obj + _IL_SUMMER
    return dt_obj + _IL_STANDARD


def build_tracker_status_email(deal, container_statuses, update_type="status_update",
                               observation=None, extractions=None,
                               gemini_key=None, db=None):
    """
    Build consolidated HTML status email for a deal.

    Args:
        deal: dict from tracker_deals
        container_statuses: list of dicts from tracker_container_status
        update_type: "status_update", "new_deal", "follow_started", "follow_stopped"
        observation: dict (optional) observation context from tracker brain
        extractions: dict (optional) extracted data from source email
        gemini_key: Gemini API key for AI subject generation (optional)
        db: Firestore client for subject enrichment (optional)
    Returns:
        dict with {subject, body_html}
    """
    direction = deal.get('direction', 'import')
    containers = deal.get('containers', [])
    total = len(containers)

    # Count completed containers
    completed_step = 'cargo_exit' if direction != 'export' else 'ship_sailing'
    completed = sum(1 for cs in container_statuses
                    if cs.get('current_step') == completed_step)

    # Summarize steps
    steps_summary = _summarize_steps(container_statuses, direction)

    # Status label (used in subject and HTML body)
    if update_type == "new_deal":
        status_label = "Tracking Started"
    elif completed == total and total > 0:
        status_label = "All Released" if direction != 'export' else "All Sailed"
    else:
        status_word = "Released" if direction != 'export' else "Sailed"
        status_label = f"{completed}/{total} {status_word}"

    # Build subject via AI or fallback
    from lib.rcb_helpers import generate_smart_subject
    subject = generate_smart_subject(
        gemini_key=gemini_key, db=db, deal=deal,
        container_statuses=container_statuses, status=status_label,
        update_type=update_type, deal_id=deal.get('deal_id', ''),
        email_type="tracker"
    )

    # Build HTML
    body = _build_html(deal, container_statuses, steps_summary,
                        update_type, completed, total, direction)

    return {"subject": subject, "body_html": body}


# — Import process steps (ordered) —
IMPORT_STEPS = [
    ("manifest", "Manifest", "ManifestDate"),
    ("port_unloading", "Cargo Entrance", "PortUnloadingDate"),
    ("delivery_order", "Delivery Order", "DeliveryOrderDate"),
    ("customs_check", "Customs Check", "CustomsCheckDate"),
    ("customs_release", "Customs Release", "CustomsReleaseDate"),
    ("port_release", "Port Release", "PortReleaseDate"),
    ("escort_certificate", "Escort Certificate", "EscortCertificateDate"),
    ("cargo_exit_request", "Release Request", "CargoExitRequestDate"),
    ("cargo_exit", "Cargo Exit", "CargoExitDate"),
]

# — Export process steps (ordered) —
EXPORT_STEPS = [
    ("storage_id", "Storage ID", "StorageIDDate"),
    ("port_storage_feedback", "Port Feedback", "PortStorageFeedbackDate"),
    ("storage_to_customs", "To Customs", "StorageIDToCustomsDate"),
    ("driver_assignment", "Driver Assigned", "DriverAssignmentDate"),
    ("customs_check", "Customs Check", "CustomsCheckDate"),
    ("customs_release", "Customs Release", "CustomsReleaseDate"),
    ("cargo_entry", "Cargo Entry", "CargoEntryDate"),
    ("cargo_loading", "Loading", "CargoLoadingDate"),
    ("ship_sailing", "Sailing", "ShipSailingDate"),
]


def _get_steps(direction):
    return IMPORT_STEPS if direction != 'export' else EXPORT_STEPS


def _time_style(value):
    """Return inline CSS for a timing cell — green if has value, grey if empty."""
    if value:
        return "color:#27ae60;font-weight:bold;"
    return "color:#ccc;"


def _extract_ocean_times(deal, container_statuses):
    """
    Extract POL/POD timing and merged events from deal + ocean data.
    Returns dict with:
      pol_code, pol_eta, pol_ata, pol_etd, pol_atd,
      pod_code, pod_eta, pod_ata, pod_etd, pod_atd,
      sources, merged_events
    """
    result = {
        'pol_code': '', 'pol_eta': '', 'pol_ata': '', 'pol_etd': '', 'pol_atd': '',
        'pod_code': '', 'pod_eta': '', 'pod_ata': '', 'pod_etd': '', 'pod_atd': '',
        'sources': set(),
        'merged_events': [],
    }

    # Get port codes from deal
    result['pod_code'] = deal.get('port', '')[:5]
    result['pod_eta'] = _format_date(deal.get('eta', ''))
    result['pol_etd'] = _format_date(deal.get('etd', ''))

    # Merge events by code across all containers
    merged_by_code = {}
    for cs in container_statuses:
        for src in (cs.get('ocean_sources') or []):
            result['sources'].add(src)
        for evt in (cs.get('ocean_events') or []):
            code = evt.get('code', '')
            if not code:
                continue
            if code not in merged_by_code:
                merged_by_code[code] = {
                    'description': evt.get('description', code),
                    'timestamps': [],
                    'locations': set(),
                    'sources': set(),
                }
            m = merged_by_code[code]
            ts = evt.get('timestamp', '')
            if ts:
                m['timestamps'].append(ts)
            loc = evt.get('location', '')
            if loc:
                m['locations'].add(loc)
            for s in (evt.get('sources') or []):
                m['sources'].add(s)

    # Extract POL/POD timing from ocean events
    # VD = Vessel Departed from POL → POL ATD
    if 'VD' in merged_by_code:
        vd = merged_by_code['VD']
        if vd['timestamps']:
            result['pol_atd'] = _format_date(min(vd['timestamps']))
        if vd['locations']:
            result['pol_code'] = sorted(vd['locations'])[0]

    # AE = Loaded on vessel at POL → POL ATA (vessel was at POL)
    if 'AE' in merged_by_code:
        ae = merged_by_code['AE']
        if ae['timestamps'] and not result['pol_ata']:
            result['pol_ata'] = _format_date(min(ae['timestamps']))
        if ae['locations'] and not result['pol_code']:
            result['pol_code'] = sorted(ae['locations'])[0]

    # GI = Gate in at origin → confirms POL
    if 'GI' in merged_by_code and not result['pol_code']:
        gi = merged_by_code['GI']
        if gi['locations']:
            result['pol_code'] = sorted(gi['locations'])[0]

    # VA = Vessel Arrived at POD → POD ATA
    if 'VA' in merged_by_code:
        va = merged_by_code['VA']
        if va['timestamps']:
            result['pod_ata'] = _format_date(min(va['timestamps']))
        if va['locations'] and not result['pod_code']:
            result['pod_code'] = sorted(va['locations'])[0]

    # UV = Discharged at POD → confirms arrival, POD ATD (vessel leaves after discharge)
    if 'UV' in merged_by_code:
        uv = merged_by_code['UV']
        if uv['timestamps'] and not result['pod_ata']:
            result['pod_ata'] = _format_date(min(uv['timestamps']))
        if uv['locations'] and not result['pod_code']:
            result['pod_code'] = sorted(uv['locations'])[0]

    # GO = Gate out at POD → confirms POD
    if 'GO' in merged_by_code and not result['pod_code']:
        go = merged_by_code['GO']
        if go['locations']:
            result['pod_code'] = sorted(go['locations'])[0]

    # Build sorted merged event list for timeline
    sorted_events = sorted(
        merged_by_code.items(),
        key=lambda x: min(x[1]['timestamps']) if x[1]['timestamps'] else '9999'
    )
    for code, m in sorted_events:
        timestamps = sorted(set(m['timestamps']))
        if not timestamps:
            date_str = ""
        elif len(timestamps) == 1:
            date_str = _format_date(timestamps[0])
        else:
            earliest = _format_date(timestamps[0])
            latest = _format_date(timestamps[-1])
            date_str = earliest if earliest == latest else f"{earliest} - {latest}"

        result['merged_events'].append({
            'code': code,
            'description': m['description'],
            'date_str': date_str,
            'location': " / ".join(sorted(m['locations']))[:20] if m['locations'] else "",
            'confirmed': len(m['sources']),
        })

    return result


def _summarize_steps(container_statuses, direction):
    steps = _get_steps(direction)
    process_key = 'import_process' if direction != 'export' else 'export_process'
    summary = []

    for step_id, step_label, date_field in steps:
        completed_count = 0
        dates = []
        for cs in container_statuses:
            proc = cs.get(process_key) or {}
            date_val = proc.get(date_field, '')
            if date_val:
                completed_count += 1
                dates.append(str(date_val))

        summary.append({
            "step_id": step_id,
            "label": step_label,
            "completed": completed_count,
            "total": len(container_statuses),
            "dates": dates,
            "latest_date": _format_date(max(dates)) if dates else "",
        })

    return summary


def _format_date(date_str):
    """Format a timestamp string to Israel time (dd/mm HH:MM IL)."""
    if not date_str:
        return ""
    try:
        # Try parsing ISO format and converting to Israel time
        clean = str(date_str).strip()
        dt = None

        # Try ISO format: 2026-02-17T08:30:00Z or 2026-02-17T08:30:00+00:00
        if 'T' in clean or len(clean) >= 19:
            iso_str = clean.split('.')[0]  # remove fractional seconds
            if iso_str.endswith('Z'):
                iso_str = iso_str[:-1]
                dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
            elif '+' in iso_str[10:] or (iso_str[10:].count('-') > 0 and len(iso_str) > 19):
                # Has timezone offset — parse and treat as-is
                try:
                    dt = datetime.fromisoformat(clean.split('.')[0])
                except ValueError:
                    pass
            else:
                # No timezone — assume UTC
                try:
                    dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S")
                    dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

        if dt:
            # Convert to Israel time
            il_dt = _to_israel_time(dt)
            return f"{il_dt.day:02d}/{il_dt.month:02d} {il_dt.hour:02d}:{il_dt.minute:02d}"

        # Fallback: simple string parsing for date-only or non-ISO formats
        clean = clean.split('.')[0].replace('T', ' ')
        if '+' in clean:
            clean = clean.split('+')[0]
        parts = clean.split(' ')
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1][:5]
            d_parts = date_part.split('-')
            if len(d_parts) == 3:
                return f"{d_parts[2]}/{d_parts[1]} {time_part}"
        # Date only
        d_parts = clean[:10].split('-')
        if len(d_parts) == 3:
            return f"{d_parts[2]}/{d_parts[1]}"
        return clean[:16]
    except Exception:
        return str(date_str)[:16]


# ── Presentation helpers ──

def _confidence_color(confidence_str):
    """Return color hex for classification confidence level."""
    if confidence_str in ("high", "גבוהה"):
        return COLOR_OK
    if confidence_str in ("medium", "בינונית"):
        return COLOR_WARN
    return COLOR_ERR


def _change_label(update_type):
    """Return human-readable label for the update_type parameter."""
    labels = {
        "new_deal": "New deal detected",
        "status_update": "Status updated",
        "follow_started": "Follow started",
        "follow_stopped": "Follow stopped",
        "classification_linked": "Classification linked",
        "containers_updated": "Containers updated",
        "ocean_update": "Ocean tracking updated",
        "eta_changed": "ETA changed",
    }
    return labels.get(update_type, "Status updated")


def _html_open():
    """Opening HTML/body/table wrapper (Outlook-safe, RTL)."""
    return ('<!DOCTYPE html>\n'
            '<html dir="rtl" lang="he">\n'
            '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>\n'
            '<body dir="rtl" style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">\n'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px 0;">\n'
            '<tr><td align="center">\n'
            '<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;'
            'background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">\n')


def _html_close():
    """Closing tags matching _html_open."""
    return '</table>\n</td></tr></table>\n</body></html>'


# ── Section builders (each returns one or more <tr>…</tr> blocks) ──

def _section_header(deal, completed, total, direction):
    """Section 1: branded header with logo, direction badge, status badge."""
    dir_label = "Import" if direction != 'export' else "Export"
    is_completed = completed == total and total > 0
    status_badge = "Completed" if is_completed else "Active"
    badge_bg = COLOR_OK if is_completed else "#3498db"
    dir_badge_bg = RPA_ACCENT if direction != 'export' else "#8e44ad"

    return f"""
<!-- HEADER -->
<tr><td style="background:{RPA_BLUE};padding:0;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="padding:20px 30px;" valign="middle">
      <span style="display:inline-block;vertical-align:middle;width:48px;height:48px;line-height:48px;text-align:center;background:#1e3a5f;color:#ffffff;font-size:20px;font-weight:bold;border-radius:6px;font-family:Georgia,'Times New Roman',serif;">RCB</span>
      <span style="display:inline-block;vertical-align:middle;padding-left:12px;">
        <span style="color:#ffffff;font-size:18px;font-weight:bold;display:block;">R.P.A. PORT LTD</span>
        <span style="color:#aed6f1;font-size:13px;display:block;">RCB Shipment Tracker</span>
      </span>
    </td>
    <td align="left" style="padding:20px 30px;" valign="middle">
      <span style="display:inline-block;background:{dir_badge_bg};color:#fff;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:bold;margin-left:6px;">{dir_label}</span>
      <span style="display:inline-block;background:{badge_bg};color:#fff;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:bold;">{status_badge}</span>
    </td>
  </tr>
  </table>
</td></tr>
"""


def _section_change_banner(update_type):
    """Section 2: light-blue bar showing what triggered this email."""
    label = _change_label(update_type)
    return f"""
<!-- CHANGE BANNER -->
<tr><td style="background:#eaf2f8;padding:10px 30px;border-bottom:1px solid #d4e6f1;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:13px;color:{RPA_ACCENT};font-weight:bold;">&#9432;&nbsp; {label}</td>
  </tr>
  </table>
</td></tr>
"""


def _section_parties(deal):
    """Section 3: Consignee / Shipper / Customs Broker (3-column)."""
    shipper = deal.get('shipper', '')
    consignee = deal.get('consignee', '')
    if not shipper and not consignee:
        return ""
    broker = "07294 - R.P.A. PORT LTD"
    return f"""
<!-- PARTIES -->
<tr><td style="padding:20px 30px 10px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;">
  <tr>
    <td style="font-size:14px;font-weight:bold;color:{RPA_BLUE};padding-bottom:8px;" colspan="3">Parties</td>
  </tr>
  <tr>
    <td width="33%" style="background:#f8f9fa;border:1px solid #eee;padding:10px 12px;vertical-align:top;">
      <span style="font-size:10px;color:#999;text-transform:uppercase;display:block;margin-bottom:4px;">Consignee</span>
      <span style="font-size:13px;color:#333;font-weight:bold;">{consignee[:40] if consignee else '&#8212;'}</span>
    </td>
    <td width="34%" style="background:#f8f9fa;border:1px solid #eee;border-right:0;border-left:0;padding:10px 12px;vertical-align:top;">
      <span style="font-size:10px;color:#999;text-transform:uppercase;display:block;margin-bottom:4px;">Shipper</span>
      <span style="font-size:13px;color:#333;font-weight:bold;">{shipper[:40] if shipper else '&#8212;'}</span>
    </td>
    <td width="33%" style="background:#f8f9fa;border:1px solid #eee;padding:10px 12px;vertical-align:top;">
      <span style="font-size:10px;color:#999;text-transform:uppercase;display:block;margin-bottom:4px;">Customs Broker</span>
      <span style="font-size:13px;color:#333;font-weight:bold;">{broker}</span>
    </td>
  </tr>
  </table>
</td></tr>
"""


def _section_shipment(deal):
    """Section 4: 2-column key-value grid with all deal metadata."""
    bol = deal.get('bol_number', 'Unknown')
    vessel = deal.get('vessel_name', '')
    voyage = deal.get('voyage_number', '')
    shipping_line = deal.get('shipping_line', '')
    port = deal.get('port_name', '') or deal.get('port', '')
    manifest = deal.get('manifest_number', '')
    containers = deal.get('containers', [])
    total = len(containers)
    container_type = deal.get('container_type', '')
    eta = deal.get('eta', '')
    etd = deal.get('etd', '')
    customs_dec = deal.get('customs_declaration', '')

    eta_fmt = _format_date(eta) if eta else ''
    etd_fmt = _format_date(etd) if etd else ''

    def _row(label, value):
        v = value if value else '&#8212;'
        return (f'  <tr>'
                f'<td style="padding:6px 12px;color:{RPA_BLUE};font-weight:bold;font-size:13px;'
                f'width:40%;border-bottom:1px solid #f0f0f0;">{label}</td>'
                f'<td style="padding:6px 12px;color:#333;font-size:13px;'
                f'border-bottom:1px solid #f0f0f0;">{v}</td>'
                f'</tr>\n')

    html = f"""
<!-- SHIPMENT DETAILS -->
<tr><td style="padding:10px 30px 20px;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="font-size:14px;font-weight:bold;color:{RPA_BLUE};margin-bottom:8px;">
  <tr><td>Shipment Details</td></tr>
  </table>
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e0e0e0;border-radius:4px;overflow:hidden;">
"""
    html += _row("Bill of Lading", bol)
    html += _row("Vessel", vessel)
    if voyage:
        html += _row("Voyage", voyage)
    html += _row("Shipping Line", shipping_line)
    html += _row("Port", port)
    html += _row("Manifest", manifest)
    cnt_val = f"{total}" + (f" ({container_type})" if container_type else "")
    html += _row("Containers", cnt_val)
    if eta_fmt:
        html += _row("ETA", eta_fmt)
    if etd_fmt:
        html += _row("ETD", etd_fmt)
    if customs_dec:
        html += _row("Customs Declaration", customs_dec)

    html += """  </table>
</td></tr>"""
    return html


def _is_vessel_arrived(container_statuses, deal):
    """Detect whether vessel has arrived at local port.

    Returns True when TaskYam has port-side data (manifest or port_unloading)
    for ANY container, or when ocean tracking shows pod_ata (vessel arrived).
    """
    direction = deal.get('direction', 'import')
    process_key = 'import_process' if direction != 'export' else 'export_process'
    local_fields = ['ManifestDate', 'PortUnloadingDate'] if direction != 'export' else ['StorageIDDate', 'PortStorageFeedbackDate']

    for cs in container_statuses:
        proc = cs.get(process_key) or {}
        if any(proc.get(f) for f in local_fields):
            return True
        # Check ocean events for VA (Vessel Arrived) or UV (Discharged)
        for evt in (cs.get('ocean_events') or []):
            if evt.get('event_code') in ('VA', 'UV'):
                return True
    return False


def _section_progress(steps_summary, completed, total, direction,
                      container_statuses, deal):
    """Section 5: progress bar + step grid + ocean tracking OR TaskYam table."""
    steps = _get_steps(direction)
    total_steps = len(steps)

    # ── Overall progress calculation (same logic as before) ──
    if steps_summary:
        all_completed_idx = -1
        for i, s in enumerate(steps_summary):
            if s['completed'] == s['total'] and s['total'] > 0:
                all_completed_idx = i
        progress_pct = int(((all_completed_idx + 1) / total_steps) * 100) if all_completed_idx >= 0 else 5
    else:
        progress_pct = 5

    status_color = COLOR_OK if completed == total and total > 0 else COLOR_WARN if completed > 0 else "#3498db"
    status_text = f"{completed}/{total} Completed" if direction != 'export' else f"{completed}/{total} Sailed"

    html = f"""
<!-- PROGRESS -->
<tr><td style="padding:15px 30px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:14px;font-weight:bold;color:{RPA_BLUE};">Overall Progress</td>
    <td align="left" style="font-size:13px;color:{status_color};font-weight:bold;">{status_text}</td>
  </tr>
  <tr><td colspan="2" style="padding-top:8px;">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#ecf0f1;border-radius:10px;overflow:hidden;">
    <tr><td style="width:{progress_pct}%;background:{status_color};height:14px;border-radius:10px;">&nbsp;</td>
        <td style="height:14px;">&nbsp;</td></tr>
    </table>
  </td></tr>
  </table>
</td></tr>
"""

    # ── Step progress grid (same color logic) ──
    step_width = int(100 / total_steps)
    html += """
<tr><td style="padding:5px 30px 15px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;">
  <tr>
"""
    for s in steps_summary:
        html += f'    <td width="{step_width}%" align="center" style="color:#555;padding:4px 1px;font-size:11px;">{s["label"]}</td>\n'
    html += "  </tr>\n  <tr>\n"

    for s in steps_summary:
        if s['completed'] == s['total'] and s['total'] > 0:
            bg = COLOR_OK
            txt_color = "#fff"
        elif s['completed'] > 0:
            bg = "#3498db"
            txt_color = "#fff"
        else:
            bg = "#ecf0f1"
            txt_color = COLOR_PENDING
        cell_text = f"{s['completed']}/{s['total']}" if s['total'] > 1 else ("&#10003;" if s['completed'] > 0 else "&#8212;")
        html += f'    <td align="center" style="background:{bg};color:{txt_color};padding:7px 2px;font-weight:bold;font-size:12px;border:1px solid #fff;border-radius:3px;">{cell_text}</td>\n'

    html += "  </tr>\n  <tr>\n"
    for s in steps_summary:
        html += f'    <td align="center" style="color:#888;padding:2px 1px;font-size:10px;">{s["latest_date"]}</td>\n'
    html += "  </tr>\n  </table>\n</td></tr>"

    # ── Switch: show ocean tracking while at sea, TaskYam once arrived ──
    arrived = _is_vessel_arrived(container_statuses, deal)
    has_ocean = any(cs.get('ocean_events') for cs in container_statuses)

    if has_ocean and not arrived:
        ocean_times = _extract_ocean_times(deal, container_statuses)
        num_sources = len(ocean_times['sources'])
        bol = deal.get('bol_number', 'Unknown')
        vessel = deal.get('vessel_name', '')

        html += f"""
<tr><td style="padding:15px 30px 5px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:14px;font-weight:bold;color:{RPA_ACCENT};">&#127758; Global Tracking</td>
    <td align="left" style="font-size:10px;color:#999;">{num_sources} source{"s" if num_sources != 1 else ""} checked</td>
  </tr>
  </table>
</td></tr>

<!-- SHIPMENT SUMMARY: BL + Containers -->
<tr><td style="padding:8px 30px 4px;">
  <table width="100%" cellpadding="4" cellspacing="0" style="font-size:13px;color:#333;border:1px solid #d4e6f1;border-radius:4px;background:#eaf2f8;">
  <tr>
    <td width="50%"><b style="color:{RPA_ACCENT};">B/L:</b> {bol}</td>
    <td width="25%"><b style="color:{RPA_ACCENT};">Containers:</b> {total}</td>
    <td width="25%"><b style="color:{RPA_ACCENT};">Vessel:</b> {vessel[:20]}</td>
  </tr>
  </table>
</td></tr>

<!-- POL / POD TIMING TABLE -->
<tr><td style="padding:4px 30px 10px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:11px;border-collapse:collapse;border:1px solid #d4e6f1;">
  <tr style="background:{RPA_ACCENT};color:#fff;">
    <td style="padding:6px 8px;font-weight:bold;width:20%;">Port</td>
    <td style="padding:6px 6px;font-weight:bold;text-align:center;width:20%;">ETD</td>
    <td style="padding:6px 6px;font-weight:bold;text-align:center;width:20%;">ATD</td>
    <td style="padding:6px 6px;font-weight:bold;text-align:center;width:20%;">ETA</td>
    <td style="padding:6px 6px;font-weight:bold;text-align:center;width:20%;">ATA</td>
  </tr>
  <tr style="background:#eaf2f8;">
    <td style="padding:5px 8px;font-weight:bold;color:{RPA_ACCENT};">POL {ocean_times['pol_code']}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pol_etd'])}">{ocean_times['pol_etd'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pol_atd'])}">{ocean_times['pol_atd'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pol_eta'])}">{ocean_times['pol_eta'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pol_ata'])}">{ocean_times['pol_ata'] or '&#8212;'}</td>
  </tr>
  <tr style="background:#ffffff;">
    <td style="padding:5px 8px;font-weight:bold;color:{RPA_ACCENT};">POD {ocean_times['pod_code']}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pod_etd'])}">{ocean_times['pod_etd'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pod_atd'])}">{ocean_times['pod_atd'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pod_eta'])}">{ocean_times['pod_eta'] or '&#8212;'}</td>
    <td style="padding:5px 6px;text-align:center;{_time_style(ocean_times['pod_ata'])}">{ocean_times['pod_ata'] or '&#8212;'}</td>
  </tr>
  </table>
</td></tr>"""

        # ── Ocean events timeline (same confirmation color logic) ──
        merged_events = ocean_times.get('merged_events', [])
        if merged_events:
            html += f"""
<tr><td style="padding:4px 30px 15px;">
  <table width="100%" cellpadding="3" cellspacing="0" style="font-size:11px;border-collapse:collapse;border:1px solid #d4e6f1;">
  <tr style="background:{RPA_ACCENT};color:#fff;">
    <td style="padding:5px 8px;font-weight:bold;">Event</td>
    <td style="padding:5px 6px;font-weight:bold;">Date</td>
    <td style="padding:5px 6px;font-weight:bold;">Location</td>
    <td style="padding:5px 4px;font-weight:bold;text-align:center;">Confirmed</td>
  </tr>"""

            for i, evt in enumerate(merged_events):
                bg = "#f4f8fb" if i % 2 == 0 else "#ffffff"
                confirmed = evt['confirmed']
                if confirmed >= 2:
                    conf_color = COLOR_OK
                    conf_icon = "&#10003;&#10003;"
                elif confirmed == 1:
                    conf_color = "#3498db"
                    conf_icon = "&#10003;"
                else:
                    conf_color = COLOR_PENDING
                    conf_icon = "?"

                html += f"""  <tr style="background:{bg};">
    <td style="padding:4px 8px;font-size:11px;">{evt['description']}</td>
    <td style="padding:4px 6px;font-size:10px;color:#555;">{evt['date_str']}</td>
    <td style="padding:4px 6px;font-size:10px;color:#555;">{evt['location']}</td>
    <td style="padding:4px 4px;text-align:center;font-size:10px;color:{conf_color};font-weight:bold;">{conf_icon} {confirmed}/{num_sources}</td>
  </tr>\n"""

            html += "  </table>\n</td></tr>"

    # ── TaskYam Local Tracking (shown once vessel arrived at port) ──
    if arrived and len(container_statuses) > 0:
        process_key = 'import_process' if direction != 'export' else 'export_process'

        html += f"""
<tr><td style="padding:15px 30px 5px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:14px;font-weight:bold;color:{RPA_BLUE};">&#9875; TaskYam Local Tracking</td>
    <td align="left" style="font-size:10px;color:#999;">Source: TaskYam (Israel Ports)</td>
  </tr>
  </table>
</td></tr>
<tr><td style="padding:5px 30px 10px;">
  <table width="100%" cellpadding="4" cellspacing="0" style="font-size:11px;border-collapse:collapse;">
  <tr style="background:{RPA_BLUE};color:#fff;">
    <td style="padding:6px 8px;font-weight:bold;">Container</td>"""

        for s in steps_summary:
            html += f'    <td align="center" style="padding:6px 2px;font-weight:bold;font-size:11px;">{s["label"]}</td>\n'

        html += "  </tr>\n"

        for i, cs in enumerate(container_statuses):
            bg_row = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            cn = cs.get('container_id', '?')
            proc = cs.get(process_key) or {}

            html += f'  <tr style="background:{bg_row};">\n'
            html += f'    <td style="padding:5px 8px;font-weight:bold;font-size:11px;white-space:nowrap;">{cn}</td>\n'

            for _, _, date_field in steps:
                date_val = proc.get(date_field, '')
                if date_val:
                    formatted = _format_date(str(date_val))
                    html += f'    <td align="center" style="background:#d4efdf;color:{COLOR_OK};padding:3px 1px;font-size:11px;">&#10003; {formatted}</td>\n'
                else:
                    html += '    <td align="center" style="color:#ccc;padding:3px 1px;font-size:11px;">&#8212;</td>\n'

            html += "  </tr>\n"

        html += "  </table>\n</td></tr>"

    return html


def _section_goods(deal, container_statuses):
    """Section 6: container details + HS code classification pills."""
    hs_codes = deal.get('classification_hs_codes', [])

    has_container_details = any(
        cs.get('container_type') or cs.get('weight')
        for cs in container_statuses
    )

    if not hs_codes and not has_container_details:
        return ""

    html = f"""
<!-- GOODS -->
<tr><td style="padding:15px 30px 10px;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="font-size:14px;font-weight:bold;color:{RPA_BLUE};margin-bottom:8px;">
  <tr><td>Goods &amp; Classification</td></tr>
  </table>"""

    # Container type / weight table
    if has_container_details:
        html += f"""
  <table width="100%" cellpadding="4" cellspacing="0"
         style="font-size:12px;border-collapse:collapse;border:1px solid #e0e0e0;margin-bottom:10px;">
  <tr style="background:{RPA_BLUE};color:#fff;">
    <td style="padding:6px 10px;font-weight:bold;">Container</td>
    <td style="padding:6px 10px;font-weight:bold;">Type</td>
    <td style="padding:6px 10px;font-weight:bold;">Weight</td>
  </tr>"""
        for i, cs in enumerate(container_statuses):
            bg = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            cn = cs.get('container_id', '?')
            ctype = cs.get('container_type', '') or '&#8212;'
            weight = cs.get('weight', '') or '&#8212;'
            html += (f'  <tr style="background:{bg};">'
                     f'<td style="padding:5px 10px;font-size:12px;font-weight:bold;">{cn}</td>'
                     f'<td style="padding:5px 10px;font-size:12px;">{ctype}</td>'
                     f'<td style="padding:5px 10px;font-size:12px;">{weight}</td>'
                     f'</tr>\n')
        html += "  </table>"

    # HS code classification pills (same logic as original lines 396-417)
    if hs_codes:
        rcb_code = deal.get('rcb_tracking_code', '')
        hs_label = rcb_code if rcb_code else "Classification"
        html += f"""
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:4px;">
  <tr><td style="font-size:12px;font-weight:bold;color:{RPA_BLUE};padding-bottom:6px;">{hs_label}</td></tr>
  <tr><td>"""
        for hc in hs_codes[:5]:
            _raw_hs = hc.get('hs_code', '')
            hs_num = _hs_fmt(_raw_hs) if _hs_fmt and _raw_hs else _raw_hs
            hs_desc = hc.get('description', '')[:50]
            hs_conf = hc.get('confidence', '')
            conf_color = _confidence_color(hs_conf)
            html += (
                f'<span style="display:inline-block;background:#eaf2f8;border:1px solid #d4e6f1;'
                f'border-radius:4px;padding:3px 10px;margin:2px;font-size:12px;">'
                f'<b>{hs_num}</b> {hs_desc}'
                f' <span style="color:{conf_color};font-size:11px;">&#9679;</span>'
                f'</span>'
            )
        html += """</td></tr>
  </table>"""
    else:
        html += f"""
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:4px;">
  <tr><td style="font-size:12px;color:{COLOR_PENDING};font-style:italic;padding:6px 0;">Classification pending</td></tr>
  </table>"""

    html += "\n</td></tr>\n"
    return html


def _section_footer():
    """Section 7: branded footer with logo, timestamp, Hebrew stop instruction."""
    now = _to_israel_time(datetime.now(timezone.utc))
    timestamp = f"{now.day:02d}/{now.month:02d}/{now.year} {now.hour:02d}:{now.minute:02d} IL"

    return f"""
<!-- FOOTER -->
<tr><td style="padding:20px 30px;border-top:2px solid #e0e0e0;background:#f8f9fa;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="padding-bottom:10px;">
      <span style="display:inline-block;vertical-align:middle;width:32px;height:32px;line-height:32px;text-align:center;background:#1e3a5f;color:#ffffff;font-size:12px;font-weight:bold;border-radius:4px;font-family:Georgia,'Times New Roman',serif;">RCB</span>
      <span style="display:inline-block;vertical-align:middle;padding-left:8px;">
        <span style="font-size:12px;font-weight:bold;color:{RPA_BLUE};">RCB &#8212; AI Customs Broker</span><br>
        <span style="font-size:11px;color:#888;">R.P.A. PORT LTD</span>
      </span>
    </td>
  </tr>
  <tr>
    <td style="font-size:10px;color:#999;padding-top:6px;border-top:1px solid #eee;">
      {timestamp}
    </td>
  </tr>
  <tr>
    <td style="font-size:11px;color:#888;direction:rtl;text-align:right;padding-top:8px;">
      &#1506;&#1491;&#1499;&#1493;&#1503; &#1488;&#1493;&#1496;&#1493;&#1502;&#1496;&#1497; &#1499;&#1500; 30 &#1491;&#1511;&#1493;&#1514;<br>
      &#1492;&#1513;&#1489; &quot;stop following&quot; &#1500;&#1492;&#1508;&#1505;&#1511;&#1514; &#1506;&#1491;&#1499;&#1493;&#1504;&#1497;&#1501;
    </td>
  </tr>
  </table>
</td></tr>
"""


# ── Orchestrator ──

def _build_html(deal, container_statuses, steps_summary,
                update_type, completed, total, direction):
    """Build the full tracker email HTML by composing section builders."""
    html = _html_open()
    html += _section_header(deal, completed, total, direction)
    html += _section_change_banner(update_type)
    html += _section_parties(deal)
    html += _section_shipment(deal)
    html += _section_progress(steps_summary, completed, total, direction,
                              container_statuses, deal)
    html += _section_goods(deal, container_statuses)
    html += _section_footer()
    html += _html_close()
    return html
