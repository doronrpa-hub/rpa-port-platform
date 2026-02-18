"""
Route ETA Calculator — Land Transport Gate Cutoff Alerts
=========================================================
Tool #33: calculate_route_eta

Calculates driving time from pickup address to Israeli port/airport.
Primary: OpenRouteService (free, 2000 req/day, needs ORS_API_KEY)
Fallback: OSRM (completely free, no key needed)
Geocoding: Nominatim (free, no key, 1 req/sec)

Firestore cache: route_cache, TTL 24 hours.
"""

import hashlib
import time
import traceback
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

# ── Port constants ──
PORT_ADDRESSES = {
    "ILHFA": "שער הנמל 1, חיפה, ישראל",
    "ILASD": "נמל אשדוד, אשדוד, ישראל",
}
BEN_GURION_ADDRESS = "נמל התעופה בן גוריון, לוד, ישראל"

# Hardcoded coordinates — ports don't move, saves geocoding calls
PORT_COORDS = {
    "ILHFA": (32.8191, 35.0442),    # Haifa Port gate
    "ILASD": (31.8305, 34.6428),    # Ashdod Port gate
}
BEN_GURION_COORDS = (32.0055, 34.8854)

CACHE_TTL_HOURS = 24

# ── Nominatim rate limit ──
_last_nominatim_call = 0.0


def _cache_key(origin_address, port_code):
    """Deterministic cache key from origin + destination."""
    raw = (origin_address.strip().lower() + "|" + port_code.strip().upper()).encode("utf-8")
    return "route_" + hashlib.md5(raw).hexdigest()


def _geocode_address(address):
    """Geocode an address via Nominatim (free, no key).

    Returns (lat, lng) or None.
    Respects 1 req/sec rate limit.
    """
    global _last_nominatim_call
    if not requests:
        print("    ⚠️ route_eta: requests library not available")
        return None
    if not address or not address.strip():
        return None

    # Rate limit: 1 request per second
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": address,
                "format": "json",
                "limit": 1,
                "countrycodes": "il",
            },
            headers={"User-Agent": "RCB-RouteETA/1.0 (customs-broker-tool)"},
            timeout=10,
        )
        _last_nominatim_call = time.time()

        if resp.status_code != 200:
            print(f"    ⚠️ Nominatim HTTP {resp.status_code}")
            return None

        results = resp.json()
        if not results:
            print(f"    ⚠️ Nominatim: no results for '{address[:60]}'")
            return None

        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
        return (lat, lng)

    except Exception as e:
        print(f"    ⚠️ Nominatim error: {e}")
        return None


def _route_via_ors(origin_coords, dest_coords, api_key):
    """Get driving route via OpenRouteService.

    Returns {duration_minutes, distance_km, route_summary} or None.
    """
    if not requests or not api_key:
        return None

    try:
        # ORS expects [lng, lat] order
        body = {
            "coordinates": [
                [origin_coords[1], origin_coords[0]],
                [dest_coords[1], dest_coords[0]],
            ]
        }
        resp = requests.post(
            "https://api.openrouteservice.org/v2/directions/driving-car",
            json=body,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            print(f"    ⚠️ ORS HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        route = data["routes"][0]
        summary = route.get("summary", {})

        return {
            "duration_minutes": round(summary.get("duration", 0) / 60, 1),
            "distance_km": round(summary.get("distance", 0) / 1000, 1),
            "route_summary": f"ORS driving: {round(summary.get('distance', 0) / 1000, 1)} km",
            "provider": "openrouteservice",
        }

    except Exception as e:
        print(f"    ⚠️ ORS error: {e}")
        return None


def _route_via_osrm(origin_coords, dest_coords):
    """Get driving route via OSRM (completely free, no key).

    Returns {duration_minutes, distance_km, route_summary} or None.
    """
    if not requests:
        return None

    try:
        # OSRM expects lng,lat order in URL
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{origin_coords[1]},{origin_coords[0]};"
            f"{dest_coords[1]},{dest_coords[0]}"
            f"?overview=false"
        )
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            print(f"    ⚠️ OSRM HTTP {resp.status_code}")
            return None

        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            print(f"    ⚠️ OSRM: {data.get('code', 'unknown error')}")
            return None

        route = data["routes"][0]
        duration_sec = route.get("duration", 0)
        distance_m = route.get("distance", 0)

        return {
            "duration_minutes": round(duration_sec / 60, 1),
            "distance_km": round(distance_m / 1000, 1),
            "route_summary": f"OSRM driving: {round(distance_m / 1000, 1)} km",
            "provider": "osrm",
        }

    except Exception as e:
        print(f"    ⚠️ OSRM error: {e}")
        return None


def _get_dest_coords(port_code):
    """Resolve port code to coordinates."""
    if port_code in PORT_COORDS:
        return PORT_COORDS[port_code]
    # Check for Ben Gurion by common codes
    if port_code in ("ILLIB", "LLBG", "BEN_GURION"):
        return BEN_GURION_COORDS
    return None


def calculate_route_eta(db, origin_address, port_code, get_secret_func=None):
    """Calculate driving ETA from origin address to port.

    Args:
        db: Firestore client
        origin_address: Pickup address string (Hebrew or English)
        port_code: Destination port code (ILHFA, ILASD, etc.)
        get_secret_func: Function to retrieve secrets (for ORS_API_KEY)

    Returns:
        dict with {duration_minutes, distance_km, route_summary, provider, cached}
        or None if calculation fails.
    """
    if not origin_address or not port_code:
        return None

    dest_coords = _get_dest_coords(port_code)
    if not dest_coords:
        print(f"    ⚠️ route_eta: unknown port code '{port_code}'")
        return None

    # ── Check cache first ──
    cache_id = _cache_key(origin_address, port_code)
    try:
        cache_doc = db.collection("route_cache").document(cache_id).get()
        if cache_doc.exists:
            cached = cache_doc.to_dict()
            cached_at = cached.get("cached_at", "")
            if cached_at:
                if isinstance(cached_at, str):
                    cache_time = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                else:
                    # Firestore DatetimeWithNanoseconds
                    cache_time = cached_at.replace(tzinfo=timezone.utc) if cached_at.tzinfo is None else cached_at
                age_hours = (datetime.now(timezone.utc) - cache_time).total_seconds() / 3600
                if age_hours < CACHE_TTL_HOURS:
                    return {
                        "duration_minutes": cached.get("duration_minutes", 0),
                        "distance_km": cached.get("distance_km", 0),
                        "route_summary": cached.get("route_summary", ""),
                        "provider": cached.get("provider", "cache"),
                        "cached": True,
                    }
    except Exception as e:
        print(f"    ⚠️ route_eta cache read error: {e}")

    # ── Geocode origin address ──
    origin_coords = _geocode_address(origin_address)
    if not origin_coords:
        return None

    # ── Try ORS first (if API key exists) ──
    result = None
    ors_key = None
    if get_secret_func:
        try:
            ors_key = get_secret_func("ORS_API_KEY")
        except Exception:
            pass

    if ors_key:
        result = _route_via_ors(origin_coords, dest_coords, ors_key)

    # ── Fallback to OSRM ──
    if not result:
        result = _route_via_osrm(origin_coords, dest_coords)

    if not result:
        return None

    # ── Write to cache ──
    result["cached"] = False
    try:
        db.collection("route_cache").document(cache_id).set({
            "origin_address": origin_address,
            "port_code": port_code,
            "duration_minutes": result["duration_minutes"],
            "distance_km": result["distance_km"],
            "route_summary": result["route_summary"],
            "provider": result["provider"],
            "origin_coords": {"lat": origin_coords[0], "lng": origin_coords[1]},
            "dest_coords": {"lat": dest_coords[0], "lng": dest_coords[1]},
            "cached_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        print(f"    ⚠️ route_eta cache write error: {e}")

    return result
