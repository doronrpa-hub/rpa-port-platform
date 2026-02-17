"""
RCB Tracker Email Builder
=========================
Builds visual HTML emails for deal status updates.
Progress bar style inspired by TaskYam but covers ALL containers in one email.
Works in Outlook, Gmail, Apple Mail (table-based, inline CSS).
"""


def build_tracker_status_email(deal, container_statuses, update_type="status_update",
                               observation=None, extractions=None):
    """
    Build consolidated HTML status email for a deal.

    Args:
        deal: dict from tracker_deals
        container_statuses: list of dicts from tracker_container_status
        update_type: "status_update", "new_deal", "follow_started", "follow_stopped"
        observation: dict (optional) observation context from tracker brain
        extractions: dict (optional) extracted data from source email
    Returns:
        dict with {subject, body_html}
    """
    bol = deal.get('bol_number', 'Unknown')
    vessel = deal.get('vessel_name', '')
    shipping_line = deal.get('shipping_line', '')
    direction = deal.get('direction', 'import')
    eta = deal.get('eta', '')
    etd = deal.get('etd', '')
    containers = deal.get('containers', [])
    total = len(containers)

    # Count completed containers
    completed_step = 'cargo_exit' if direction != 'export' else 'ship_sailing'
    completed = sum(1 for cs in container_statuses
                    if cs.get('current_step') == completed_step)

    # Summarize steps
    steps_summary = _summarize_steps(container_statuses, direction)

    # Build subject
    status_text = f"{completed}/{total} released" if direction != 'export' else f"{completed}/{total} sailed"
    subject = f"[RCB-TRK] {bol}"
    if vessel:
        subject += f" | {vessel}"
    subject += f" | {status_text}"

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
    if not date_str:
        return ""
    try:
        clean = date_str.split('.')[0].replace('T', ' ')
        if '+' in clean:
            clean = clean.split('+')[0]
        parts = clean.split(' ')
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1][:5]
            d_parts = date_part.split('-')
            if len(d_parts) == 3:
                return f"{d_parts[2]}/{d_parts[1]} {time_part}"
        return clean[:16]
    except Exception:
        return str(date_str)[:16]


def _build_html(deal, container_statuses, steps_summary,
                update_type, completed, total, direction):
    bol = deal.get('bol_number', 'Unknown')
    vessel = deal.get('vessel_name', '')
    shipping_line = deal.get('shipping_line', '')
    port = deal.get('port_name', '') or deal.get('port', '')
    eta = deal.get('eta', '')
    etd = deal.get('etd', '')
    manifest = deal.get('manifest_number', '')
    shipper = deal.get('shipper', '')
    consignee = deal.get('consignee', '')
    customs_dec = deal.get('customs_declaration', '')

    dir_label = "Import" if direction != 'export' else "Export"
    date_label = f"ETA: {eta}" if eta else (f"ETD: {etd}" if etd else "")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

<!-- HEADER -->
<tr><td style="background:#1a5276;padding:20px 30px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="color:#ffffff;font-size:22px;font-weight:bold;">&#9875; RCB Shipment Tracker</td>
    <td align="right" style="color:#aed6f1;font-size:14px;">{dir_label} | {date_label}</td>
  </tr>
  </table>
</td></tr>

<!-- DEAL INFO -->
<tr><td style="padding:20px 30px;border-bottom:1px solid #eee;">
  <table width="100%" cellpadding="4" cellspacing="0" style="font-size:14px;color:#333;">
  <tr>
    <td width="50%"><b style="color:#1a5276;">Bill of Lading:</b> {bol}</td>
    <td width="50%"><b style="color:#1a5276;">Vessel:</b> {vessel}</td>
  </tr>
  <tr>
    <td><b style="color:#1a5276;">Shipping Line:</b> {shipping_line}</td>
    <td><b style="color:#1a5276;">Port:</b> {port}</td>
  </tr>
  <tr>
    <td><b style="color:#1a5276;">Manifest:</b> {manifest}</td>
    <td><b style="color:#1a5276;">Containers:</b> {total}</td>
  </tr>"""

    if shipper:
        html += f"""
  <tr>
    <td><b style="color:#1a5276;">Shipper:</b> {shipper[:40]}</td>
    <td><b style="color:#1a5276;">Consignee:</b> {consignee[:40]}</td>
  </tr>"""

    if customs_dec:
        html += f"""
  <tr>
    <td colspan="2"><b style="color:#1a5276;">Declaration:</b> {customs_dec}</td>
  </tr>"""

    html += """
  </table>
</td></tr>

<!-- SUMMARY BAR -->"""

    # Overall progress
    steps = _get_steps(direction)
    total_steps = len(steps)
    if steps_summary:
        all_completed_idx = -1
        for i, s in enumerate(steps_summary):
            if s['completed'] == s['total'] and s['total'] > 0:
                all_completed_idx = i
        progress_pct = int(((all_completed_idx + 1) / total_steps) * 100) if all_completed_idx >= 0 else 5
    else:
        progress_pct = 5

    status_color = "#27ae60" if completed == total and total > 0 else "#f39c12" if completed > 0 else "#3498db"
    status_text = f"{completed}/{total} Completed" if direction != 'export' else f"{completed}/{total} Sailed"

    html += f"""
<tr><td style="padding:15px 30px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:16px;font-weight:bold;color:#333;">Overall Progress</td>
    <td align="right" style="font-size:14px;color:{status_color};font-weight:bold;">{status_text}</td>
  </tr>
  <tr><td colspan="2" style="padding-top:8px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#ecf0f1;border-radius:10px;overflow:hidden;">
    <tr><td style="width:{progress_pct}%;background:{status_color};height:12px;border-radius:10px;">&nbsp;</td>
        <td style="height:12px;">&nbsp;</td></tr>
    </table>
  </td></tr>
  </table>
</td></tr>"""

    # Step progress bar
    html += """
<tr><td style="padding:5px 30px 15px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:11px;">
  <tr>"""

    step_width = int(100 / total_steps)
    for s in steps_summary:
        html += f'    <td width="{step_width}%" align="center" style="color:#666;padding:3px 1px;font-size:10px;">{s["label"]}</td>\n'
    html += "  </tr>\n  <tr>\n"

    for s in steps_summary:
        if s['completed'] == s['total'] and s['total'] > 0:
            bg = "#27ae60"
            txt_color = "#fff"
        elif s['completed'] > 0:
            bg = "#3498db"
            txt_color = "#fff"
        else:
            bg = "#ecf0f1"
            txt_color = "#999"

        cell_text = f"{s['completed']}/{s['total']}" if s['total'] > 1 else ("&#10003;" if s['completed'] > 0 else "&#8212;")
        html += f'    <td align="center" style="background:{bg};color:{txt_color};padding:6px 2px;font-weight:bold;font-size:11px;border:1px solid #fff;">{cell_text}</td>\n'

    html += "  </tr>\n  <tr>\n"

    for s in steps_summary:
        html += f'    <td align="center" style="color:#888;padding:2px 1px;font-size:9px;">{s["latest_date"]}</td>\n'

    html += "  </tr>\n  </table>\n</td></tr>"

    # ════════════════════════════════════════════════════
    #  GLOBAL TRACKING — Consolidated ocean events
    # ════════════════════════════════════════════════════
    # One row per event type. Multiple sources merged.
    # If timestamps differ across sources → show range.
    # Source count shown as confidence indicator (e.g. "3/3").
    has_ocean = any(cs.get('ocean_events') for cs in container_statuses)
    if has_ocean:
        # Merge events by code across all containers + sources
        merged_by_code = {}  # code → {timestamps, locations, vessels, sources}
        total_source_count = set()
        for cs in container_statuses:
            for src in (cs.get('ocean_sources') or []):
                total_source_count.add(src)
            for evt in (cs.get('ocean_events') or []):
                code = evt.get('code', '')
                if not code:
                    continue
                if code not in merged_by_code:
                    merged_by_code[code] = {
                        'description': evt.get('description', code),
                        'timestamps': [],
                        'locations': set(),
                        'vessels': set(),
                        'sources': set(),
                    }
                m = merged_by_code[code]
                ts = evt.get('timestamp', '')
                if ts:
                    m['timestamps'].append(ts)
                loc = evt.get('location', '')
                if loc:
                    m['locations'].add(loc)
                vsl = evt.get('vessel', '')
                if vsl:
                    m['vessels'].add(vsl)
                for s in (evt.get('sources') or []):
                    m['sources'].add(s)

        if merged_by_code:
            num_sources = len(total_source_count)

            # Sort by earliest timestamp per event code
            sorted_events = sorted(
                merged_by_code.items(),
                key=lambda x: min(x[1]['timestamps']) if x[1]['timestamps'] else '9999'
            )

            html += f"""
<tr><td style="padding:15px 30px 5px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:15px;font-weight:bold;color:#2471a3;">&#127758; Global Tracking</td>
    <td align="right" style="font-size:10px;color:#999;">{num_sources} source{"s" if num_sources != 1 else ""} checked</td>
  </tr>
  </table>
</td></tr>
<tr><td style="padding:5px 30px 15px;">
  <table width="100%" cellpadding="3" cellspacing="0" style="font-size:11px;border-collapse:collapse;border:1px solid #d4e6f1;">
  <tr style="background:#2471a3;color:#fff;">
    <td style="padding:5px 8px;font-weight:bold;">Event</td>
    <td style="padding:5px 8px;font-weight:bold;">Date</td>
    <td style="padding:5px 8px;font-weight:bold;">Location</td>
    <td style="padding:5px 8px;font-weight:bold;">Vessel</td>
    <td style="padding:5px 4px;font-weight:bold;text-align:center;">Confirmed</td>
  </tr>"""

            for i, (code, m) in enumerate(sorted_events):
                bg = "#eaf2f8" if i % 2 == 0 else "#ffffff"
                desc = m['description']

                # Date: show single date or range if sources disagree
                timestamps = sorted(set(m['timestamps']))
                if len(timestamps) == 0:
                    date_str = ""
                elif len(timestamps) == 1:
                    date_str = _format_date(timestamps[0])
                else:
                    earliest = _format_date(timestamps[0])
                    latest = _format_date(timestamps[-1])
                    if earliest == latest:
                        date_str = earliest
                    else:
                        date_str = f"{earliest} - {latest}"

                loc = " / ".join(sorted(m['locations']))[:20] if m['locations'] else ""
                vsl = " / ".join(sorted(m['vessels']))[:25] if m['vessels'] else ""

                # Confidence: how many sources confirmed this event
                confirmed = len(m['sources'])
                if confirmed >= 2:
                    conf_color = "#27ae60"  # Green — multiple sources agree
                    conf_icon = "&#10003;&#10003;"
                elif confirmed == 1:
                    conf_color = "#3498db"  # Blue — single source
                    conf_icon = "&#10003;"
                else:
                    conf_color = "#999"
                    conf_icon = "?"
                conf_label = f"{confirmed}/{num_sources}"

                html += f"""  <tr style="background:{bg};">
    <td style="padding:5px 8px;font-size:11px;font-weight:bold;">{desc}</td>
    <td style="padding:5px 8px;font-size:10px;color:#555;">{date_str}</td>
    <td style="padding:5px 8px;font-size:10px;color:#555;">{loc}</td>
    <td style="padding:5px 8px;font-size:10px;color:#555;">{vsl}</td>
    <td style="padding:5px 4px;text-align:center;font-size:11px;color:{conf_color};font-weight:bold;">{conf_icon} {conf_label}</td>
  </tr>\n"""

            html += "  </table>\n</td></tr>"

    # ════════════════════════════════════════════════════
    #  TASKYAM LOCAL TRACKING — Israeli port operations
    # ════════════════════════════════════════════════════
    # Per-container detail table from TaskYam API
    if len(container_statuses) > 0:
        process_key = 'import_process' if direction != 'export' else 'export_process'

        html += """
<tr><td style="padding:15px 30px 5px;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:15px;font-weight:bold;color:#1a5276;">&#9875; TaskYam Local Tracking</td>
    <td align="right" style="font-size:10px;color:#999;">Source: TaskYam (Israel Ports)</td>
  </tr>
  </table>
</td></tr>
<tr><td style="padding:5px 30px 10px;">
  <table width="100%" cellpadding="4" cellspacing="0" style="font-size:11px;border-collapse:collapse;">
  <tr style="background:#1a5276;color:#fff;">
    <td style="padding:6px 8px;font-weight:bold;">Container</td>"""

        for s in steps_summary:
            html += f'    <td align="center" style="padding:6px 2px;font-weight:bold;font-size:9px;">{s["label"]}</td>\n'

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
                    html += f'    <td align="center" style="background:#d4efdf;color:#27ae60;padding:3px 1px;font-size:9px;">&#10003; {formatted}</td>\n'
                else:
                    html += f'    <td align="center" style="color:#ccc;padding:3px 1px;font-size:9px;">&#8212;</td>\n'

            html += "  </tr>\n"

        html += "  </table>\n</td></tr>"

    # Footer
    html += f"""
<tr><td style="padding:15px 30px;border-top:1px solid #eee;background:#f8f9fa;">
  <table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="font-size:11px;color:#888;">
      RCB Tracker by RPA-PORT | Auto-updated every 30 min<br>
      Reply "stop following" to stop updates
    </td>
    <td align="right" style="font-size:11px;color:#aaa;">
      Powered by TaskYam + Ocean APIs
    </td>
  </tr>
  </table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

    return html
