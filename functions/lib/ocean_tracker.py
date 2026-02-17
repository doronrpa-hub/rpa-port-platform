"""
Ocean Tracker — Phase 2 Multi-Source Ocean Visibility
=====================================================
Supplements TaskYam (Phase 1) with ocean-leg tracking data.
TaskYam is ALWAYS the primary source for Israeli port operations.
This module fills the gap: vessel departure → vessel arrival.

Sources (priority order — ALL FREE):
  1. Maersk Track & Trace — DCSA v2.2, confirmed free (Consumer-Key auth)
  2. Terminal49 — free tier 100 containers (API key auth, multi-carrier)
  3. INTTRA by e2open — free for shippers (OAuth2, needs agreement)
  4. VesselFinder — PAID, vessel-only, optional fallback (not registered by default)

Design:
  - Each source is a Provider with a common interface
  - query_ocean_status() queries available providers and merges results
  - Returns normalized OceanEvent list that tracker.py can consume
  - Cross-checks between sources for data quality
  - Never overrides TaskYam data — only supplements

Collections:
  - tracker_container_status — adds ocean_events, ocean_last_check fields
  - tracker_deals — fills journey_id, loyds_number, sailing_date, eta

Used by: tracker.py tracker_poll_active_deals() (Phase 2 branch)
Email:  Global Tracking section (separate from TaskYam Local Tracking)
"""

import re
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════
#  NORMALIZED OCEAN EVENTS
# ═══════════════════════════════════════════════════════════
#
# All providers normalize their data into these standard events.
# Codes aligned with INTTRA's 8-event model + extensions.

OCEAN_EVENT_CODES = {
    "EE": "Empty container picked up",
    "GI": "Gate in at origin terminal",
    "AE": "Loaded on vessel",
    "VD": "Vessel departed",
    "TS": "Transshipment (discharged at intermediate port)",
    "TL": "Transshipment (loaded at intermediate port)",
    "VA": "Vessel arrived at destination",
    "UV": "Discharged from vessel",
    "GO": "Gate out at destination terminal",
    "RD": "Empty container returned",
}

# Map ocean events to tracker.py step names
# These steps fill the gap between TaskYam's port operations
OCEAN_EVENT_TO_STEP = {
    # Import direction: ocean events precede TaskYam port steps
    "import": {
        "AE": "vessel_loaded",
        "VD": "vessel_departed",
        "TS": "transshipment",
        "TL": "transshipment_loaded",
        "VA": "vessel_arrived",
        "UV": "port_unloading",      # Overlaps with TaskYam — TaskYam wins
    },
    # Export direction: ocean events follow TaskYam port steps
    "export": {
        "EE": "empty_pickup",
        "GI": "cargo_entry",          # Overlaps with TaskYam — TaskYam wins
        "AE": "vessel_loaded",
        "VD": "vessel_departed",
        "VA": "vessel_arrived",
        "RD": "container_returned",
    },
}

# Step priority for ocean leg (highest = most advanced)
OCEAN_STEP_PRIORITY = {
    "pending": 0,
    "empty_pickup": 10,
    "cargo_entry": 20,
    "vessel_loaded": 30,
    "vessel_departed": 40,
    "transshipment": 45,
    "transshipment_loaded": 46,
    "vessel_arrived": 50,
    "port_unloading": 60,
    "container_returned": 90,
}


def make_ocean_event(code, timestamp, location="", vessel="", voyage="",
                     source="", raw=None):
    """Create a normalized ocean event dict."""
    return {
        "code": code,
        "description": OCEAN_EVENT_CODES.get(code, code),
        "timestamp": timestamp,
        "location": location,        # UN/LOCODE e.g. "ILHFA", "NLRTM"
        "vessel": vessel,
        "voyage": voyage,
        "source": source,            # "maersk", "terminal49", "inttra", etc.
        "raw": raw or {},
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════
#  PROVIDER BASE
# ═══════════════════════════════════════════════════════════

class OceanProvider:
    """Base class for ocean tracking data providers."""
    name = "base"
    requires_secrets = []
    is_free = True         # Only free providers are registered by default

    def __init__(self, get_secret_func=None):
        self.get_secret = get_secret_func
        self._available = None

    def is_available(self):
        """Check if this provider has required credentials configured."""
        if self._available is not None:
            return self._available
        if not self.requires_secrets:
            self._available = True
            return True
        try:
            for secret_name in self.requires_secrets:
                val = self.get_secret(secret_name)
                if not val:
                    self._available = False
                    return False
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def track_container(self, container_number):
        """Track by container number. Returns list of OceanEvent dicts."""
        return []

    def track_bol(self, bol_number):
        """Track by B/L number. Returns list of OceanEvent dicts."""
        return []

    def get_vessel_eta(self, vessel_name, port_code):
        """Get ETA for vessel at port. Returns ISO datetime string or None."""
        return None


# ═══════════════════════════════════════════════════════════
#  MAERSK PROVIDER — FREE, DCSA v2.2 compliant
# ═══════════════════════════════════════════════════════════
#
# Developer portal: developer.maersk.com
# Auth: Consumer-Key header (register app → get key)
# Cost: FREE — confirmed at maersk.com/support/faqs
# Standard: DCSA Track & Trace v2.2
# Coverage: Maersk ocean shipments only
#
# Event types: TRANSPORT (ARRI/DEPA), EQUIPMENT (LOAD/DISC/GTIN/GTOT)
# Classifier: ACT (actual), PLN (planned), EST (estimated)

class MaerskProvider(OceanProvider):
    name = "maersk"
    requires_secrets = ["MAERSK_CONSUMER_KEY"]
    is_free = True

    BASE_URL = "https://api.maersk.com"
    EVENTS_PATH = "/track-and-trace-private/v2/events"

    # DCSA event codes → our normalized codes
    # Equipment events need emptyIndicatorCode context
    _EQUIP_CODE_MAP = {
        "GTIN": "GI",     # Gate in
        "LOAD": "AE",     # Loaded on vessel
        "DISC": "UV",     # Discharged from vessel
        "GTOT": "GO",     # Gate out
    }
    # Transport events
    _TRANSPORT_CODE_MAP = {
        "DEPA": "VD",     # Vessel departed
        "ARRI": "VA",     # Vessel arrived
    }

    def _get(self, path, params=None):
        """GET request with Consumer-Key auth."""
        import requests
        try:
            key = self.get_secret("MAERSK_CONSUMER_KEY")
            resp = requests.get(
                f"{self.BASE_URL}{path}",
                headers={
                    "Consumer-Key": key,
                    "Accept": "application/json",
                },
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    Maersk GET {path}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    Maersk error: {e}")
            return None

    def _normalize_dcsa_events(self, raw_events):
        """Convert DCSA v2.2 events to normalized OceanEvent list."""
        events = []
        for evt in (raw_events or []):
            classifier = evt.get("eventClassifierCode", "")
            if classifier != "ACT":
                continue  # Only actual events, not planned/estimated

            event_type = evt.get("eventType", "")
            code = None
            if event_type == "EQUIPMENT":
                equip_code = evt.get("equipmentEventTypeCode", "")
                empty = evt.get("emptyIndicatorCode", "")
                # Empty pickup / return
                if equip_code == "GTOT" and empty == "EMPTY":
                    code = "EE"
                elif equip_code == "GTIN" and empty == "EMPTY":
                    code = "RD"
                else:
                    code = self._EQUIP_CODE_MAP.get(equip_code)
            elif event_type == "TRANSPORT":
                transport_code = evt.get("transportEventTypeCode", "")
                code = self._TRANSPORT_CODE_MAP.get(transport_code)

            if not code or code not in OCEAN_EVENT_CODES:
                continue

            # Extract vessel info from transportCall
            tc = evt.get("transportCall") or {}
            vessel_obj = tc.get("vessel") or {}

            events.append(make_ocean_event(
                code=code,
                timestamp=evt.get("eventDateTime", ""),
                location=tc.get("UNLocationCode", ""),
                vessel=vessel_obj.get("vesselName", ""),
                voyage=tc.get("exportVoyageNumber") or tc.get("importVoyageNumber", ""),
                source="maersk",
                raw=evt,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track container via Maersk DCSA Track & Trace."""
        if not self.is_available():
            return []
        data = self._get(self.EVENTS_PATH, {
            "equipmentReference": container_number,
            "eventType": "EQUIPMENT,TRANSPORT",
        })
        if not data:
            return []
        raw_events = data if isinstance(data, list) else data.get("events", [])
        return self._normalize_dcsa_events(raw_events)

    def track_bol(self, bol_number):
        """Track by B/L via Maersk DCSA Track & Trace."""
        if not self.is_available():
            return []
        data = self._get(self.EVENTS_PATH, {
            "transportDocumentReference": bol_number,
            "eventType": "EQUIPMENT,TRANSPORT",
        })
        if not data:
            return []
        raw_events = data if isinstance(data, list) else data.get("events", [])
        return self._normalize_dcsa_events(raw_events)

    def get_schedule(self, origin_port, dest_port, date_from=None):
        """Query Maersk vessel schedules (free, DCSA Commercial Schedules)."""
        if not self.is_available():
            return None
        params = {"originPort": origin_port, "destinationPort": dest_port}
        if date_from:
            params["startDate"] = date_from
        return self._get("/schedules/point-to-point", params)


# ═══════════════════════════════════════════════════════════
#  TERMINAL49 PROVIDER — FREE tier (100 containers)
# ═══════════════════════════════════════════════════════════
#
# API: api.terminal49.com/v2, JSON:API format
# Auth: Authorization: Token API_KEY
# Cost: FREE tier up to 100 containers
# Coverage: 35+ shipping lines, multi-carrier
#
# Workflow: POST tracking_request → GET shipments → GET transport_events
# For polling: we store terminal49_tracking_id on the deal, then query events.

# Terminal49 event codes → our normalized codes
_T49_EVENT_MAP = {
    "container.transport.empty_out": "EE",
    "container.transport.full_in": "GI",
    "container.transport.vessel_loaded": "AE",
    "container.transport.vessel_departed": "VD",
    "container.transport.vessel_arrived": "VA",
    "container.transport.vessel_discharged": "UV",
    "container.transport.vessel_berthed": "VA",   # treat berthed as arrived
    "container.transport.full_out": "GO",
    "container.transport.empty_in": "RD",
    "container.transport.transshipment_arrived": "TS",
    "container.transport.transshipment_discharged": "TS",
    "container.transport.transshipment_loaded": "TL",
    "container.transport.transshipment_departed": "TL",
    "container.transport.feeder_arrived": "VA",
    "container.transport.feeder_discharged": "UV",
    "container.transport.feeder_loaded": "AE",
    "container.transport.feeder_departed": "VD",
}

# SCAC codes for carriers we track (used when creating tracking requests)
CARRIER_SCAC = {
    "ZIM":         "ZIMU",
    "MAERSK":      "MAEU",
    "MSC":         "MSCU",
    "EVERGREEN":   "EGLV",
    "HAPAG-LLOYD": "HLCU",
    "ONE":         "ONEY",
    "COSCO":       "COSU",
    "YANG MING":   "YMLU",
    "OOCL":        "OOLU",
    "CMA CGM":     "CMDU",
    "HMM":         "HDMU",
    "PIL":         "PCIU",
}


class Terminal49Provider(OceanProvider):
    name = "terminal49"
    requires_secrets = ["TERMINAL49_API_KEY"]
    is_free = True

    BASE_URL = "https://api.terminal49.com/v2"

    def _headers(self):
        return {
            "Authorization": f"Token {self.get_secret('TERMINAL49_API_KEY')}",
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    def _get(self, path, params=None):
        """GET request to Terminal49 API."""
        import requests
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{path}",
                headers=self._headers(),
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    Terminal49 GET {path}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    Terminal49 error: {e}")
            return None

    def _post(self, path, payload):
        """POST request to Terminal49 API."""
        import requests
        import json
        try:
            resp = requests.post(
                f"{self.BASE_URL}/{path}",
                headers=self._headers(),
                data=json.dumps(payload),
                timeout=20,
            )
            if resp.status_code in (200, 201, 202):
                return resp.json()
            print(f"    Terminal49 POST {path}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    Terminal49 POST error: {e}")
            return None

    def create_tracking_request(self, bol_number, scac):
        """Create a tracking request. Returns tracking_request_id or None."""
        if not self.is_available() or not scac:
            return None
        payload = {
            "data": {
                "type": "tracking_request",
                "attributes": {
                    "request_type": "bill_of_lading",
                    "request_number": bol_number,
                    "scac": scac,
                }
            }
        }
        data = self._post("tracking_requests", payload)
        if data and data.get("data"):
            return data["data"].get("id")
        return None

    def _normalize_t49_events(self, raw_events):
        """Convert Terminal49 transport_events to normalized OceanEvent list."""
        events = []
        for item in (raw_events or []):
            attrs = item.get("attributes") or item
            t49_code = attrs.get("event", "")
            code = _T49_EVENT_MAP.get(t49_code)
            if not code or code not in OCEAN_EVENT_CODES:
                continue

            # Extract vessel from relationships
            vessel_name = ""
            rels = item.get("relationships") or {}
            vessel_rel = rels.get("vessel", {}).get("data") or {}
            if vessel_rel.get("id"):
                vessel_name = vessel_rel.get("id", "")  # Will be UUID — resolved below

            events.append(make_ocean_event(
                code=code,
                timestamp=attrs.get("timestamp", ""),
                location=attrs.get("location_locode", ""),
                vessel=vessel_name,
                voyage=attrs.get("voyage_number", ""),
                source="terminal49",
                raw=attrs,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def _get_shipment_containers(self, bol_number):
        """Find containers for a BOL via shipments endpoint."""
        data = self._get("shipments", {"filter[bill_of_lading_number]": bol_number})
        if not data or not data.get("data"):
            return []
        container_ids = []
        for shipment in (data["data"] if isinstance(data["data"], list) else [data["data"]]):
            rels = shipment.get("relationships", {})
            containers_rel = rels.get("containers", {}).get("data", [])
            for c in containers_rel:
                if c.get("id"):
                    container_ids.append(c["id"])
        return container_ids

    def track_bol(self, bol_number):
        """Track by B/L — query shipments, then get transport_events for each container."""
        if not self.is_available():
            return []
        container_ids = self._get_shipment_containers(bol_number)
        all_events = []
        for cid in container_ids[:10]:  # Limit to prevent excessive calls
            data = self._get(f"containers/{cid}/transport_events")
            if data and data.get("data"):
                events = self._normalize_t49_events(data["data"])
                all_events.extend(events)
        return sorted(all_events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track by container number — query containers endpoint."""
        if not self.is_available():
            return []
        data = self._get("containers", {"filter[number]": container_number})
        if not data or not data.get("data"):
            return []
        containers = data["data"] if isinstance(data["data"], list) else [data["data"]]
        all_events = []
        for c in containers[:5]:
            cid = c.get("id")
            if not cid:
                continue
            ev_data = self._get(f"containers/{cid}/transport_events")
            if ev_data and ev_data.get("data"):
                events = self._normalize_t49_events(ev_data["data"])
                all_events.extend(events)
        return sorted(all_events, key=lambda e: e["timestamp"] or "")

    def get_shipment_info(self, bol_number):
        """Get shipment-level info (vessel, ETA, ports)."""
        if not self.is_available():
            return None
        data = self._get("shipments", {"filter[bill_of_lading_number]": bol_number})
        if not data or not data.get("data"):
            return None
        shipments = data["data"] if isinstance(data["data"], list) else [data["data"]]
        if not shipments:
            return None
        attrs = shipments[0].get("attributes", {})
        return {
            "vessel": attrs.get("pod_vessel_name", ""),
            "pol": attrs.get("port_of_lading_locode", ""),
            "pod": attrs.get("port_of_discharge_locode", ""),
            "etd": attrs.get("pol_etd_at", ""),
            "atd": attrs.get("pol_atd_at", ""),
            "eta": attrs.get("pod_eta_at", ""),
            "ata": attrs.get("pod_ata_at", ""),
        }


# ═══════════════════════════════════════════════════════════
#  INTTRA PROVIDER — Free for shippers (needs agreement)
# ═══════════════════════════════════════════════════════════
#
# REST API: apidocs.inttra.com
# Auth: OAuth2 Client Credentials (token-based)
# Products: Visibility / Track & Trace
# Cost: Free for shippers (carrier-sponsored), API access may require agreement
#
# INTTRA normalizes carrier data into 8 standard events:
# EE, I(GI), AE, VD, VA, UV, OA(GO), RD

class INTTRAProvider(OceanProvider):
    name = "inttra"
    requires_secrets = ["INTTRA_CLIENT_ID", "INTTRA_CLIENT_SECRET"]
    is_free = True  # Free for shippers, API needs onboarding agreement

    BASE_URL = "https://api.inttra.com/v1"
    TOKEN_URL = "https://api.inttra.com/oauth/token"

    def __init__(self, get_secret_func=None):
        super().__init__(get_secret_func)
        self._token = None
        self._token_expires = None

    def _authenticate(self):
        """Get bearer token via OAuth2 client credentials."""
        import requests
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token
        try:
            client_id = self.get_secret("INTTRA_CLIENT_ID")
            client_secret = self.get_secret("INTTRA_CLIENT_SECRET")
            resp = requests.post(self.TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                from datetime import timedelta
                self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                return self._token
            print(f"    INTTRA auth failed: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    INTTRA auth error: {e}")
            return None

    def _get(self, endpoint, params=None):
        """Authenticated GET request to INTTRA API."""
        import requests
        token = self._authenticate()
        if not token:
            return None
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    INTTRA GET {endpoint}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    INTTRA error ({endpoint}): {e}")
            return None

    def _normalize_inttra_events(self, raw_events):
        """Convert INTTRA IFTSTA events to normalized OceanEvent list."""
        events = []
        # INTTRA event code mapping
        code_map = {
            "EE": "EE", "I": "GI", "AE": "AE", "VD": "VD",
            "VA": "VA", "UV": "UV", "OA": "GO", "RD": "RD",
        }
        for evt in (raw_events or []):
            inttra_code = evt.get("eventCode") or evt.get("statusCode", "")
            code = code_map.get(inttra_code, inttra_code)
            if code not in OCEAN_EVENT_CODES:
                continue
            events.append(make_ocean_event(
                code=code,
                timestamp=evt.get("eventDateTime") or evt.get("actualDateTime", ""),
                location=evt.get("locationCode") or evt.get("facilityCode", ""),
                vessel=evt.get("vesselName", ""),
                voyage=evt.get("voyageNumber", ""),
                source="inttra",
                raw=evt,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track container via INTTRA Visibility API."""
        if not self.is_available():
            return []
        data = self._get("visibility/containers", {"containerNumber": container_number})
        if not data:
            return []
        raw_events = data.get("events") or data.get("statusEvents", [])
        return self._normalize_inttra_events(raw_events)

    def track_bol(self, bol_number):
        """Track by B/L via INTTRA Visibility API."""
        if not self.is_available():
            return []
        data = self._get("visibility/shipments", {"billOfLadingNumber": bol_number})
        if not data:
            return []
        raw_events = data.get("events") or data.get("statusEvents", [])
        return self._normalize_inttra_events(raw_events)


# ═══════════════════════════════════════════════════════════
#  ZIM PROVIDER — FREE (currently, may charge later)
# ═══════════════════════════════════════════════════════════
#
# Developer portal: api.zim.com (Azure APIM)
# Auth: API Token (apply via portal)
# Cost: FREE currently — ZIM reserves right to charge with 30-day notice
# Coverage: ZIM ocean shipments only

class ZIMProvider(OceanProvider):
    name = "zim"
    requires_secrets = ["ZIM_API_TOKEN"]
    is_free = True

    BASE_URL = "https://api.zim.com"

    # ZIM uses similar event codes — map to our normalized codes
    _EVENT_MAP = {
        "Gate In": "GI",
        "Loaded": "AE",
        "Vessel Departure": "VD",
        "Vessel Arrival": "VA",
        "Discharged": "UV",
        "Gate Out": "GO",
        "Empty Return": "RD",
        "Empty Pickup": "EE",
        "Transshipment Discharge": "TS",
        "Transshipment Load": "TL",
        # DCSA-style codes (ZIM may also use these)
        "GTIN": "GI", "LOAD": "AE", "DEPA": "VD",
        "ARRI": "VA", "DISC": "UV", "GTOT": "GO",
    }

    def _get(self, endpoint, params=None):
        """GET request with API Token auth."""
        import requests
        try:
            token = self.get_secret("ZIM_API_TOKEN")
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    ZIM GET {endpoint}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    ZIM error: {e}")
            return None

    def _normalize_zim_events(self, raw_events):
        """Convert ZIM tracking events to normalized OceanEvent list."""
        events = []
        for evt in (raw_events or []):
            event_desc = evt.get("eventDescription") or evt.get("eventType") or ""
            event_code = evt.get("eventCode") or ""
            code = self._EVENT_MAP.get(event_code) or self._EVENT_MAP.get(event_desc)
            if not code or code not in OCEAN_EVENT_CODES:
                continue
            events.append(make_ocean_event(
                code=code,
                timestamp=evt.get("eventDate") or evt.get("actualDate", ""),
                location=evt.get("locationCode") or evt.get("portCode", ""),
                vessel=evt.get("vesselName", ""),
                voyage=evt.get("voyageNumber", ""),
                source="zim",
                raw=evt,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track container via ZIM API."""
        if not self.is_available():
            return []
        data = self._get("tracking/containers", {"containerNumber": container_number})
        if not data:
            return []
        raw_events = data.get("events") or data.get("trackingEvents", [])
        return self._normalize_zim_events(raw_events)

    def track_bol(self, bol_number):
        """Track by B/L via ZIM API."""
        if not self.is_available():
            return []
        data = self._get("tracking/shipments", {"billOfLadingNumber": bol_number})
        if not data:
            return []
        raw_events = data.get("events") or data.get("trackingEvents", [])
        return self._normalize_zim_events(raw_events)

    def get_schedule(self, origin_port, dest_port, date_from=None):
        """Query ZIM vessel schedules (free)."""
        if not self.is_available():
            return None
        params = {"originPort": origin_port, "destinationPort": dest_port}
        if date_from:
            params["dateFrom"] = date_from
        return self._get("schedules/pointToPoint", params)


# ═══════════════════════════════════════════════════════════
#  HAPAG-LLOYD PROVIDER — FREE (EUR 0, needs approval)
# ═══════════════════════════════════════════════════════════
#
# Developer portal: api-portal.hlag.com
# Auth: OAuth2 Client Credentials (Client-ID + Client-Secret)
# Cost: EUR 0 — free registration, approval required
# Coverage: Hapag-Lloyd ocean shipments
# Sandbox available for testing

class HapagLloydProvider(OceanProvider):
    name = "hapag_lloyd"
    requires_secrets = ["HAPAG_CLIENT_ID", "HAPAG_CLIENT_SECRET"]
    is_free = True

    BASE_URL = "https://api.hlag.com"
    TOKEN_URL = "https://api.hlag.com/oauth2/token"

    def __init__(self, get_secret_func=None):
        super().__init__(get_secret_func)
        self._token = None
        self._token_expires = None

    def _authenticate(self):
        """Get bearer token via OAuth2 client credentials."""
        import requests
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token
        try:
            client_id = self.get_secret("HAPAG_CLIENT_ID")
            client_secret = self.get_secret("HAPAG_CLIENT_SECRET")
            resp = requests.post(self.TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                from datetime import timedelta
                self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                return self._token
            print(f"    Hapag-Lloyd auth failed: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    Hapag-Lloyd auth error: {e}")
            return None

    def _get(self, endpoint, params=None):
        """Authenticated GET request."""
        import requests
        token = self._authenticate()
        if not token:
            return None
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    Hapag-Lloyd GET {endpoint}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    Hapag-Lloyd error ({endpoint}): {e}")
            return None

    def _normalize_hlag_events(self, raw_events):
        """Convert Hapag-Lloyd DCSA events to normalized OceanEvent list."""
        # Hapag-Lloyd follows DCSA standard — same mapping as Maersk
        equip_map = {"GTIN": "GI", "LOAD": "AE", "DISC": "UV", "GTOT": "GO"}
        transport_map = {"DEPA": "VD", "ARRI": "VA"}
        events = []
        for evt in (raw_events or []):
            classifier = evt.get("eventClassifierCode", "")
            if classifier != "ACT":
                continue
            event_type = evt.get("eventType", "")
            code = None
            if event_type == "EQUIPMENT":
                equip_code = evt.get("equipmentEventTypeCode", "")
                empty = evt.get("emptyIndicatorCode", "")
                if equip_code == "GTOT" and empty == "EMPTY":
                    code = "EE"
                elif equip_code == "GTIN" and empty == "EMPTY":
                    code = "RD"
                else:
                    code = equip_map.get(equip_code)
            elif event_type == "TRANSPORT":
                code = transport_map.get(evt.get("transportEventTypeCode", ""))
            if not code or code not in OCEAN_EVENT_CODES:
                continue
            tc = evt.get("transportCall") or {}
            vessel_obj = tc.get("vessel") or {}
            events.append(make_ocean_event(
                code=code,
                timestamp=evt.get("eventDateTime", ""),
                location=tc.get("UNLocationCode", ""),
                vessel=vessel_obj.get("vesselName", ""),
                voyage=tc.get("exportVoyageNumber") or tc.get("importVoyageNumber", ""),
                source="hapag_lloyd",
                raw=evt,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track container via Hapag-Lloyd DCSA Track & Trace."""
        if not self.is_available():
            return []
        data = self._get("v2/events", {
            "equipmentReference": container_number,
            "eventType": "EQUIPMENT,TRANSPORT",
        })
        if not data:
            return []
        raw_events = data if isinstance(data, list) else data.get("events", [])
        return self._normalize_hlag_events(raw_events)

    def track_bol(self, bol_number):
        """Track by B/L via Hapag-Lloyd DCSA Track & Trace."""
        if not self.is_available():
            return []
        data = self._get("v2/events", {
            "transportDocumentReference": bol_number,
            "eventType": "EQUIPMENT,TRANSPORT",
        })
        if not data:
            return []
        raw_events = data if isinstance(data, list) else data.get("events", [])
        return self._normalize_hlag_events(raw_events)

    def get_schedule(self, origin_port, dest_port, date_from=None):
        """Query Hapag-Lloyd vessel schedules."""
        if not self.is_available():
            return None
        params = {"placeOfReceipt": origin_port, "placeOfDelivery": dest_port}
        if date_from:
            params["departureDateTime"] = date_from
        return self._get("v1/schedules/pointToPoint", params)


# ═══════════════════════════════════════════════════════════
#  COSCO PROVIDER — FREE (trial period)
# ═══════════════════════════════════════════════════════════
#
# COP Portal: cop.lines.coscoshipping.com
# GitHub docs: github.com/cop-cos/COP
# Auth: HMAC-SHA1 (API Key + Secret Key)
# Cost: FREE during trial — 1000 calls/day, 30,000/month
# Coverage: COSCO Shipping Lines

class COSCOProvider(OceanProvider):
    name = "cosco"
    requires_secrets = ["COSCO_API_KEY", "COSCO_SECRET_KEY"]
    is_free = True

    BASE_URL = "https://api.lines.coscoshipping.com/service"

    def _sign_request(self, method, path, body=""):
        """Generate HMAC-SHA1 signature for COSCO COP API."""
        import hmac
        import hashlib
        import base64
        api_key = self.get_secret("COSCO_API_KEY")
        secret_key = self.get_secret("COSCO_SECRET_KEY")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Content MD5
        content_md5 = ""
        if body:
            content_md5 = base64.b64encode(
                hashlib.md5(body.encode()).digest()
            ).decode()

        # Content SHA-256 digest
        digest = hashlib.sha256(body.encode() if body else b"").hexdigest()

        # String to sign
        string_to_sign = f"{method}\n{content_md5}\napplication/json\n{timestamp}\n{path}"

        # HMAC-SHA1
        signature = base64.b64encode(
            hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()

        return {
            "X-Coscon-Date": timestamp,
            "X-Coscon-Content-Md5": content_md5,
            "X-Coscon-Digest": f"SHA-256={digest}",
            "X-Coscon-Authorization": f"SignAlgorithm=HmacSHA1,SignedHeaders=,Signature={signature}",
            "X-Coscon-Hmac": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path, params=None):
        """Signed GET request to COSCO COP API."""
        import requests
        try:
            headers = self._sign_request("GET", path)
            resp = requests.get(
                f"{self.BASE_URL}{path}",
                headers=headers,
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:
                print(f"    COSCO GET {path}: {resp.status_code}")
            return None
        except Exception as e:
            print(f"    COSCO error: {e}")
            return None

    def _normalize_cosco_events(self, raw_events):
        """Convert COSCO tracking events to normalized OceanEvent list."""
        code_map = {
            "Gate In": "GI", "GATE_IN": "GI",
            "Load": "AE", "LOADED": "AE",
            "Departure": "VD", "DEPARTURE": "VD",
            "Arrival": "VA", "ARRIVAL": "VA",
            "Discharge": "UV", "DISCHARGED": "UV",
            "Gate Out": "GO", "GATE_OUT": "GO",
            "Empty Return": "RD",
            "Empty Pickup": "EE",
            "Transshipment Discharge": "TS",
            "Transshipment Load": "TL",
        }
        events = []
        for evt in (raw_events or []):
            event_type = evt.get("eventType") or evt.get("transportEventType", "")
            code = code_map.get(event_type)
            if not code or code not in OCEAN_EVENT_CODES:
                continue
            events.append(make_ocean_event(
                code=code,
                timestamp=evt.get("eventDate") or evt.get("timeOfIssue", ""),
                location=evt.get("portCode") or evt.get("locationCode", ""),
                vessel=evt.get("vesselName", ""),
                voyage=evt.get("voyageNo") or evt.get("voyageNumber", ""),
                source="cosco",
                raw=evt,
            ))
        return sorted(events, key=lambda e: e["timestamp"] or "")

    def track_container(self, container_number):
        """Track container via COSCO COP API."""
        if not self.is_available():
            return []
        data = self._get("/synconhub/tracking/containerNo", {"containerNo": container_number})
        if not data:
            return []
        raw_events = data.get("data", {}).get("trackingEvents", []) if isinstance(data.get("data"), dict) else []
        return self._normalize_cosco_events(raw_events)

    def track_bol(self, bol_number):
        """Track by B/L via COSCO COP API."""
        if not self.is_available():
            return []
        data = self._get("/synconhub/tracking/billOfLadingNo", {"billOfLadingNo": bol_number})
        if not data:
            return []
        raw_events = data.get("data", {}).get("trackingEvents", []) if isinstance(data.get("data"), dict) else []
        return self._normalize_cosco_events(raw_events)


# ═══════════════════════════════════════════════════════════
#  DATA PROTECTION — Never expose internal data to outside
# ═══════════════════════════════════════════════════════════
#
# Rules:
#  1. ONLY send container_number, bol_number, vessel IMO to external APIs
#     NEVER send: deal_id, customer name, email, Firestore paths, internal refs
#  2. Sanitize all incoming data before writing to Firestore
#  3. Strip raw responses of any PII or injection attempts
#  4. Validate container numbers and BOL format before querying
#  5. Rate-limit outbound calls per provider

# Allowed characters in external data fields
_SAFE_TEXT = re.compile(r'^[\w\s\-./,():#@+&;\'\"]*$', re.UNICODE)
_SAFE_CODE = re.compile(r'^[A-Z0-9\-]+$')
_SAFE_TIMESTAMP = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}')

def _sanitize_text(value, max_len=200):
    """Sanitize a text value from external API response."""
    if not isinstance(value, str):
        return str(value)[:max_len] if value is not None else ""
    # Strip control characters
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    # Truncate
    return clean[:max_len]

def _sanitize_code(value, max_len=20):
    """Sanitize a code value (port, event code, etc.)."""
    if not isinstance(value, str):
        return ""
    clean = value.strip().upper()[:max_len]
    return clean if _SAFE_CODE.match(clean) else ""

def _sanitize_timestamp(value):
    """Sanitize a timestamp value."""
    if not isinstance(value, str):
        return ""
    clean = value.strip()[:30]
    if _SAFE_TIMESTAMP.match(clean):
        return clean
    return ""

def sanitize_ocean_event(event):
    """Sanitize a single ocean event before storing in Firestore."""
    return {
        "code": _sanitize_code(event.get("code"), 4),
        "description": _sanitize_text(event.get("description"), 100),
        "timestamp": _sanitize_timestamp(event.get("timestamp")),
        "location": _sanitize_code(event.get("location"), 10),
        "vessel": _sanitize_text(event.get("vessel"), 80),
        "voyage": _sanitize_text(event.get("voyage"), 30),
        "sources": [_sanitize_text(s, 30) for s in event.get("sources", [])[:5]],
    }

def sanitize_ocean_result(ocean_result):
    """Sanitize entire ocean query result before any Firestore write."""
    if not ocean_result:
        return ocean_result
    return {
        "events": [sanitize_ocean_event(e) for e in ocean_result.get("events", [])],
        "ocean_step": _sanitize_code(ocean_result.get("ocean_step") or "", 30) or None,
        "vessel_info": _sanitize_vessel_info(ocean_result.get("vessel_info")),
        "shipment_info": _sanitize_shipment_info(ocean_result.get("shipment_info")),
        "sources_queried": [_sanitize_text(s, 30) for s in ocean_result.get("sources_queried", [])[:10]],
    }

def _sanitize_vessel_info(info):
    """Sanitize vessel info from external source."""
    if not info:
        return None
    return {
        "imo": _sanitize_text(str(info.get("imo", "")), 10),
        "name": _sanitize_text(info.get("name", ""), 80),
        "status": _sanitize_text(info.get("status", ""), 50),
        "speed": info.get("speed") if isinstance(info.get("speed"), (int, float)) else None,
        "destination": _sanitize_text(info.get("destination", ""), 80),
        "eta": _sanitize_timestamp(info.get("eta", "")),
    }

def _sanitize_shipment_info(info):
    """Sanitize shipment info from external source."""
    if not info:
        return None
    return {
        "vessel": _sanitize_text(info.get("vessel", ""), 80),
        "pol": _sanitize_code(info.get("pol", ""), 10),
        "pod": _sanitize_code(info.get("pod", ""), 10),
        "etd": _sanitize_timestamp(info.get("etd", "")),
        "atd": _sanitize_timestamp(info.get("atd", "")),
        "eta": _sanitize_timestamp(info.get("eta", "")),
        "ata": _sanitize_timestamp(info.get("ata", "")),
    }

def validate_container_for_query(container_number):
    """Validate container number format before sending to external API.
    ISO 6346: 4 letters + 7 digits."""
    if not container_number or not isinstance(container_number, str):
        return False
    clean = container_number.strip().upper()
    return bool(re.match(r'^[A-Z]{4}\d{7}$', clean))

def validate_bol_for_query(bol_number):
    """Validate B/L number format before sending to external API.
    Must be alphanumeric, 6-30 chars."""
    if not bol_number or not isinstance(bol_number, str):
        return False
    clean = bol_number.strip().upper()
    return bool(re.match(r'^[A-Z0-9\-/]{6,30}$', clean))


# ═══════════════════════════════════════════════════════════
#  VESSEL FINDER PROVIDER — PAID (optional, not default)
# ═══════════════════════════════════════════════════════════
#
# VesselFinder API: api.vesselfinder.com
# Cost: PAID — credit-based, NO free tier
# Tracks VESSELS (not containers) — provides position, ETA, route.
# Registered ONLY if VESSELFINDER_API_KEY secret is set.
# NOT in default provider list — must be explicitly enabled.

class VesselFinderProvider(OceanProvider):
    name = "vesselfinder"
    requires_secrets = ["VESSELFINDER_API_KEY"]
    is_free = False  # PAID — credit-based, no free tier

    BASE_URL = "https://api.vesselfinder.com"

    def _get(self, endpoint, params=None):
        """GET request to VesselFinder API."""
        import requests
        try:
            params = params or {}
            params["userkey"] = self.get_secret("VESSELFINDER_API_KEY")
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"    VesselFinder error ({endpoint}): {e}")
            return None

    def get_vessel_eta(self, vessel_name=None, imo=None, port_code=None):
        """Get vessel ETA at destination port."""
        if not self.is_available():
            return None
        params = {}
        if imo:
            params["imo"] = imo
        elif vessel_name:
            params["name"] = vessel_name
        if port_code:
            params["portcode"] = port_code

        data = self._get("expectedarrivals", params)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get("eta")
        return None

    def get_vessel_position(self, imo=None, vessel_name=None):
        """Get current vessel position and status."""
        if not self.is_available():
            return None
        params = {}
        if imo:
            params["imo"] = imo
        data = self._get("vessels", params)
        if data and isinstance(data, list) and len(data) > 0:
            v = data[0]
            return {
                "imo": v.get("IMO"),
                "name": v.get("SHIPNAME"),
                "status": v.get("NAVIGATION_STATUS"),
                "speed": v.get("SPEED"),
                "lat": v.get("LAT"),
                "lon": v.get("LON"),
                "destination": v.get("DESTINATION"),
                "eta": v.get("ETA"),
                "last_pos_time": v.get("LAST_POS_UTC"),
            }
        return None


# ═══════════════════════════════════════════════════════════
#  CROSS-CHECK & MERGE ENGINE
# ═══════════════════════════════════════════════════════════

def _merge_ocean_events(events_by_source):
    """
    Merge events from multiple sources into a single timeline.
    Rules:
      - Deduplicate by (code, date) — same event from multiple sources
      - If timestamps differ for same event code, keep the earliest
      - Attach source list to each merged event
    """
    merged = {}  # key: (code, date_prefix) → event
    for source_name, events in events_by_source.items():
        for evt in events:
            code = evt["code"]
            ts = evt.get("timestamp", "")
            date_prefix = ts[:10] if ts else ""  # YYYY-MM-DD
            key = (code, date_prefix)

            if key not in merged:
                evt["sources"] = [source_name]
                merged[key] = evt
            else:
                # Event already seen — cross-check
                existing = merged[key]
                existing.setdefault("sources", []).append(source_name)
                # Keep earlier timestamp
                if ts and (not existing["timestamp"] or ts < existing["timestamp"]):
                    existing["timestamp"] = ts
                # Merge vessel/voyage if missing
                if not existing.get("vessel") and evt.get("vessel"):
                    existing["vessel"] = evt["vessel"]
                if not existing.get("voyage") and evt.get("voyage"):
                    existing["voyage"] = evt["voyage"]

    # Sort by timestamp
    result = sorted(merged.values(), key=lambda e: e.get("timestamp") or "9999")
    return result


def _derive_ocean_step(events, direction):
    """Derive the current ocean-leg step from merged events."""
    if not events:
        return None

    step_map = OCEAN_EVENT_TO_STEP.get(direction, OCEAN_EVENT_TO_STEP["import"])
    best_step = None
    best_priority = -1

    for evt in events:
        step = step_map.get(evt["code"])
        if step:
            priority = OCEAN_STEP_PRIORITY.get(step, 0)
            if priority > best_priority:
                best_priority = priority
                best_step = step

    return best_step


# ═══════════════════════════════════════════════════════════
#  MAIN QUERY FUNCTION — Called by tracker.py
# ═══════════════════════════════════════════════════════════

# Provider registry — initialized once per cold start
_providers = None


def _init_providers(get_secret_func):
    """Initialize available ocean tracking providers.
    Priority: free carrier direct APIs first, then multi-carrier, then INTTRA.
    VesselFinder (paid) only if explicitly configured."""
    global _providers
    if _providers is not None:
        return _providers

    _providers = []

    # Register providers in priority order — FREE CARRIER DIRECT FIRST
    candidates = [
        # Priority 1: Free carrier direct APIs (best data, no middleman)
        MaerskProvider(get_secret_func),         # Free, DCSA v2.2
        ZIMProvider(get_secret_func),            # Free (currently)
        HapagLloydProvider(get_secret_func),     # Free (EUR 0, needs approval)
        COSCOProvider(get_secret_func),          # Free (trial, 1000/day)
        # Priority 2: Free multi-carrier aggregators
        Terminal49Provider(get_secret_func),      # Free tier 100 containers
        INTTRAProvider(get_secret_func),          # Free for shippers
        # Priority 3: Paid (optional — only if explicitly configured)
        VesselFinderProvider(get_secret_func),    # PAID — vessel-only
    ]

    for provider in candidates:
        if provider.is_available():
            _providers.append(provider)
            cost_tag = "free" if provider.is_free else "PAID"
            print(f"    Ocean tracker: {provider.name} provider available ({cost_tag})")
        else:
            print(f"    Ocean tracker: {provider.name} provider not configured (missing secrets)")

    return _providers


# Carrier name → provider name mapping (which carrier-direct provider to use)
_CARRIER_PROVIDER_MAP = {
    "MAERSK": "maersk", "SEALAND": "maersk", "SAFMARINE": "maersk",
    "ZIM": "zim",
    "HAPAG-LLOYD": "hapag_lloyd", "HAPAG LLOYD": "hapag_lloyd",
    "COSCO": "cosco", "COSCO SHIPPING": "cosco",
}


def query_ocean_status(container_number=None, bol_number=None,
                       vessel_name=None, imo=None, direction="import",
                       get_secret_func=None, carrier_name=None):
    """
    Query all available ocean tracking providers for a container/shipment.

    DATA PROTECTION: Only container_number and bol_number are sent to external APIs.
    No deal_id, customer data, or internal references ever leave our system.

    Returns dict with:
      - events: merged ocean event timeline (sanitized)
      - ocean_step: current ocean-leg step name
      - vessel_info: vessel position/ETA (sanitized)
      - shipment_info: shipment-level data (sanitized)
      - sources_queried: list of provider names that responded
    """
    providers = _init_providers(get_secret_func)
    if not providers:
        return {"events": [], "ocean_step": None, "vessel_info": None,
                "shipment_info": None, "sources_queried": []}

    # DATA PROTECTION: Validate inputs before sending to any external API
    safe_container = None
    safe_bol = None
    if container_number and validate_container_for_query(container_number):
        safe_container = container_number.strip().upper()
    if bol_number and validate_bol_for_query(bol_number):
        safe_bol = bol_number.strip().upper()

    if not safe_container and not safe_bol:
        print("    Ocean tracker: no valid container/BOL to query")
        return {"events": [], "ocean_step": None, "vessel_info": None,
                "shipment_info": None, "sources_queried": []}

    # Determine which carrier-direct provider matches this shipment
    preferred_carrier_provider = None
    if carrier_name:
        preferred_carrier_provider = _CARRIER_PROVIDER_MAP.get(carrier_name.upper())

    events_by_source = {}
    sources_queried = []
    vessel_info = None
    shipment_info = None

    for provider in providers:
        try:
            events = []

            # Smart carrier routing: skip carrier-specific providers for wrong carriers
            if provider.name in ("maersk", "zim", "hapag_lloyd", "cosco"):
                if preferred_carrier_provider and provider.name != preferred_carrier_provider:
                    continue  # Skip — this is a different carrier's API
                if not preferred_carrier_provider:
                    continue  # Unknown carrier — don't waste calls on carrier-direct APIs

            # DATA PROTECTION: Only send validated container/BOL — nothing else
            if safe_bol:
                events = provider.track_bol(safe_bol)
            if not events and safe_container:
                events = provider.track_container(safe_container)

            if events:
                events_by_source[provider.name] = events
                sources_queried.append(provider.name)

            # Get shipment info from Terminal49 if available
            if not shipment_info and provider.name == "terminal49" and safe_bol:
                shipment_info = provider.get_shipment_info(safe_bol)

            # Get vessel info from VesselFinder if available (paid, optional)
            if not vessel_info and hasattr(provider, 'get_vessel_position'):
                if imo:
                    vessel_info = provider.get_vessel_position(imo=imo)

        except Exception as e:
            print(f"    Ocean tracker: {provider.name} error: {e}")

    # Merge events from all sources
    merged_events = _merge_ocean_events(events_by_source)

    # Derive current ocean step
    ocean_step = _derive_ocean_step(merged_events, direction)

    result = {
        "events": merged_events,
        "ocean_step": ocean_step,
        "vessel_info": vessel_info,
        "shipment_info": shipment_info,
        "sources_queried": sources_queried,
    }

    # DATA PROTECTION: Sanitize all external data before returning
    return sanitize_ocean_result(result)


def enrich_deal_from_ocean(db, deal_id, deal, ocean_result):
    """
    Enrich deal record with ocean tracking data.
    Same pattern as tracker.py _enrich_deal_from_taskyam() — only fill if empty.
    """
    if not ocean_result or not ocean_result.get("events"):
        return

    updates = {}
    events = ocean_result["events"]

    # Extract vessel info from events
    for evt in events:
        if not deal.get("vessel_name") and evt.get("vessel"):
            updates["vessel_name"] = evt["vessel"]
        if not deal.get("voyage") and evt.get("voyage"):
            updates["voyage"] = evt["voyage"]

    # Extract ETD from VD (vessel departed) event
    for evt in events:
        if evt["code"] == "VD" and evt.get("timestamp"):
            if not deal.get("etd"):
                updates["etd"] = evt["timestamp"][:10]
            if not deal.get("sailing_date"):
                updates["sailing_date"] = evt["timestamp"][:10]

    # Extract ETA from Terminal49 shipment info
    shipment_info = ocean_result.get("shipment_info")
    if shipment_info:
        if not deal.get("eta") and shipment_info.get("eta"):
            eta_val = shipment_info["eta"]
            updates["eta"] = eta_val[:10] if len(eta_val) >= 10 else eta_val
        if not deal.get("etd") and shipment_info.get("atd"):
            atd_val = shipment_info["atd"]
            updates["etd"] = atd_val[:10] if len(atd_val) >= 10 else atd_val

    # Extract ETA from vessel info (VesselFinder fallback)
    vessel_info = ocean_result.get("vessel_info")
    if vessel_info and vessel_info.get("eta"):
        if not deal.get("eta") and "eta" not in updates:
            updates["eta"] = vessel_info["eta"][:10] if len(vessel_info["eta"]) >= 10 else vessel_info["eta"]

    # Fill IMO / Lloyd's number
    if vessel_info and vessel_info.get("imo"):
        if not deal.get("loyds_number"):
            updates["loyds_number"] = str(vessel_info["imo"])

    # Fill journey_id from INTTRA reference if available
    for evt in events:
        if evt.get("source") == "inttra" and evt.get("raw", {}).get("shipmentId"):
            if not deal.get("journey_id"):
                updates["journey_id"] = evt["raw"]["shipmentId"]
                break

    # Store which sources were queried
    if ocean_result.get("sources_queried"):
        updates["ocean_sources"] = ocean_result["sources_queried"]

    if updates:
        updates["ocean_last_check"] = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        # DATA PROTECTION: sanitize all values before writing to Firestore
        safe_updates = {}
        for k, v in updates.items():
            if isinstance(v, str):
                safe_updates[k] = _sanitize_text(v, 200)
            else:
                safe_updates[k] = v
        db.collection("tracker_deals").document(deal_id).update(safe_updates)


def update_container_ocean_events(db, deal_id, container_id, ocean_result):
    """
    Store ocean events on the container status document.
    Additive — appends new events, doesn't replace TaskYam data.
    """
    if not ocean_result or not ocean_result.get("events"):
        return

    doc_id = f"{deal_id}_{container_id}"
    doc_ref = db.collection("tracker_container_status").document(doc_id)

    now = datetime.now(timezone.utc).isoformat()

    # Store ocean events and step alongside existing TaskYam data
    # DATA PROTECTION: use sanitize_ocean_event for all external data
    update_data = {
        "ocean_events": [sanitize_ocean_event(e) for e in ocean_result["events"]],
        "ocean_step": ocean_result.get("ocean_step"),
        "ocean_last_check": now,
        "ocean_sources": ocean_result.get("sources_queried", []),
        "updated_at": now,
    }

    # Add vessel info if available
    if ocean_result.get("vessel_info"):
        update_data["vessel_info"] = ocean_result["vessel_info"]

    try:
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.update(update_data)
        else:
            update_data["deal_id"] = deal_id
            update_data["container_id"] = container_id
            update_data["created_at"] = now
            doc_ref.set(update_data)
    except Exception as e:
        print(f"    Ocean tracker: container status update error: {e}")


# ═══════════════════════════════════════════════════════════
#  TERMINAL49 TRACKING REQUEST MANAGEMENT
# ═══════════════════════════════════════════════════════════
#
# Terminal49 uses a subscription model: you create a tracking_request once,
# then poll shipments/containers. These helpers manage that lifecycle.

def ensure_terminal49_tracking(db, deal_id, deal, get_secret_func):
    """
    Ensure a Terminal49 tracking request exists for this deal.
    Called once per deal — stores terminal49_tracking_id on the deal.
    Returns True if tracking is active, False if not possible.
    """
    # Already tracking?
    if deal.get("terminal49_tracking_id"):
        return True

    bol = deal.get("bol_number", "")
    carrier = deal.get("shipping_line", "").upper()
    scac = CARRIER_SCAC.get(carrier, "")

    if not bol or not scac:
        return False

    providers = _init_providers(get_secret_func)
    t49 = next((p for p in providers if p.name == "terminal49"), None)
    if not t49:
        return False

    tracking_id = t49.create_tracking_request(bol, scac)
    if tracking_id:
        db.collection("tracker_deals").document(deal_id).update({
            "terminal49_tracking_id": tracking_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"    Terminal49: tracking request created for {bol} ({scac}): {tracking_id}")
        return True

    return False


# ═══════════════════════════════════════════════════════════
#  VESSEL SCHEDULE QUERY
# ═══════════════════════════════════════════════════════════
#
# Query vessel schedules from carrier direct APIs.
# Used for: proactive ETA updates, route planning, transit time estimation.
# All free — uses Maersk, ZIM, Hapag-Lloyd, COSCO schedule endpoints.

def query_vessel_schedule(origin_port, dest_port, date_from=None,
                          carrier_name=None, get_secret_func=None):
    """
    Query vessel schedules between two ports.
    DATA PROTECTION: Only sends port codes (UN/LOCODE) — no internal data.

    Args:
        origin_port: UN/LOCODE e.g. "CNSHA"
        dest_port: UN/LOCODE e.g. "ILHFA"
        date_from: ISO date string for departure window start
        carrier_name: specific carrier to query, or None for all available
        get_secret_func: secret retrieval function

    Returns list of schedule results (carrier-specific format).
    """
    providers = _init_providers(get_secret_func)
    if not providers:
        return []

    # DATA PROTECTION: Validate port codes
    safe_origin = _sanitize_code(origin_port, 10)
    safe_dest = _sanitize_code(dest_port, 10)
    if not safe_origin or not safe_dest:
        return []

    results = []
    preferred = _CARRIER_PROVIDER_MAP.get((carrier_name or "").upper())

    for provider in providers:
        if not hasattr(provider, 'get_schedule'):
            continue
        # Only query matching carrier, or all if no preference
        if preferred and provider.name != preferred:
            continue
        if not preferred and provider.name not in ("maersk", "zim", "hapag_lloyd", "cosco"):
            continue

        try:
            data = provider.get_schedule(safe_origin, safe_dest, date_from)
            if data:
                results.append({
                    "source": provider.name,
                    "schedules": data,
                })
        except Exception as e:
            print(f"    Schedule query {provider.name} error: {e}")

    return results
