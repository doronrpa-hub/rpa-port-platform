"""
Tests for route_eta.py (Tool #33) and check_gate_cutoff_alerts() in tracker.py
===============================================================================
Covers: geocoding, ORS routing, OSRM routing, caching, alert logic, dedup, email content.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os
from datetime import datetime, timezone, timedelta

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.route_eta import (
    _cache_key,
    _geocode_address,
    _route_via_ors,
    _route_via_osrm,
    _get_dest_coords,
    calculate_route_eta,
    PORT_COORDS,
    PORT_ADDRESSES,
    BEN_GURION_COORDS,
    CACHE_TTL_HOURS,
)
from lib.tracker import (
    _parse_gate_cutoff,
    _build_cutoff_subject,
    _build_cutoff_alert_html,
    check_gate_cutoff_alerts,
)


# ═══════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════

def _mock_deal(overrides=None):
    """Create a test deal dict with land transport fields."""
    deal = {
        "bol_number": "ZIMLNS1234567",
        "booking_number": "BKG001",
        "vessel_name": "ZIM SHANGHAI",
        "port": "ILHFA",
        "port_name": "Haifa",
        "status": "active",
        "follow_mode": "auto",
        "current_step": "customs_check",
        "direction": "import",
        "land_pickup_address": "אזור תעשייה ציפורית, חיפה",
        "gate_cutoff": "2026-02-19T14:00:00+02:00",
        "follower_email": "ops@import-co.co.il",
        "containers": ["ZIMU1234567"],
        "cutoff_alerts_sent": [],
    }
    if overrides:
        deal.update(overrides)
    return deal


def _mock_deal_doc(deal_id="deal_abc123", deal=None):
    """Create a mock Firestore document snapshot."""
    doc = Mock()
    doc.id = deal_id
    doc.to_dict.return_value = deal or _mock_deal()
    return doc


def _mock_db_with_deals(deal_docs):
    """Create mock DB that returns deal docs from stream()."""
    db = Mock()
    db.collection.return_value.where.return_value.where.return_value.stream.return_value = iter(deal_docs)
    db.collection.return_value.where.return_value.stream.return_value = iter(deal_docs)

    # Cache miss by default
    cache_doc = Mock()
    cache_doc.exists = False
    db.collection.return_value.document.return_value.get.return_value = cache_doc
    return db


def _mock_eta_result(duration=90, distance=75.5):
    """Create a standard ETA result."""
    return {
        "duration_minutes": duration,
        "distance_km": distance,
        "route_summary": f"OSRM driving: {distance} km",
        "provider": "osrm",
        "cached": False,
    }


# ═══════════════════════════════════════════════════
#  TestCacheKey
# ═══════════════════════════════════════════════════

class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("אזור תעשייה", "ILHFA")
        k2 = _cache_key("אזור תעשייה", "ILHFA")
        assert k1 == k2

    def test_different_addresses_different_keys(self):
        k1 = _cache_key("חיפה", "ILHFA")
        k2 = _cache_key("תל אביב", "ILHFA")
        assert k1 != k2

    def test_different_ports_different_keys(self):
        k1 = _cache_key("חיפה", "ILHFA")
        k2 = _cache_key("חיפה", "ILASD")
        assert k1 != k2

    def test_case_insensitive(self):
        k1 = _cache_key("Haifa Zone", "ILHFA")
        k2 = _cache_key("haifa zone", "ilhfa")
        assert k1 == k2

    def test_starts_with_route_prefix(self):
        k = _cache_key("test", "ILHFA")
        assert k.startswith("route_")


# ═══════════════════════════════════════════════════
#  TestGetDestCoords
# ═══════════════════════════════════════════════════

class TestGetDestCoords:
    def test_haifa_port(self):
        coords = _get_dest_coords("ILHFA")
        assert coords == PORT_COORDS["ILHFA"]

    def test_ashdod_port(self):
        coords = _get_dest_coords("ILASD")
        assert coords == PORT_COORDS["ILASD"]

    def test_ben_gurion(self):
        coords = _get_dest_coords("ILLIB")
        assert coords == BEN_GURION_COORDS

    def test_unknown_port_returns_none(self):
        assert _get_dest_coords("XXXX") is None


# ═══════════════════════════════════════════════════
#  TestGeocoding
# ═══════════════════════════════════════════════════

class TestGeocoding:
    @patch("lib.route_eta.requests")
    @patch("lib.route_eta.time")
    def test_success(self, mock_time, mock_requests):
        mock_time.time.return_value = 100.0
        mock_time.sleep = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "32.8", "lon": "35.0"}]
        mock_requests.get.return_value = mock_resp

        result = _geocode_address("חיפה")
        assert result == (32.8, 35.0)

    @patch("lib.route_eta.requests")
    @patch("lib.route_eta.time")
    def test_no_results(self, mock_time, mock_requests):
        mock_time.time.return_value = 100.0
        mock_time.sleep = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_requests.get.return_value = mock_resp

        result = _geocode_address("nonexistent place xyz123")
        assert result is None

    @patch("lib.route_eta.requests")
    @patch("lib.route_eta.time")
    def test_http_error(self, mock_time, mock_requests):
        mock_time.time.return_value = 100.0
        mock_time.sleep = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_requests.get.return_value = mock_resp

        result = _geocode_address("חיפה")
        assert result is None

    def test_empty_address(self):
        assert _geocode_address("") is None
        assert _geocode_address(None) is None

    @patch("lib.route_eta.requests")
    @patch("lib.route_eta.time")
    def test_network_exception(self, mock_time, mock_requests):
        mock_time.time.return_value = 100.0
        mock_time.sleep = Mock()
        mock_requests.get.side_effect = Exception("Connection timeout")

        result = _geocode_address("חיפה")
        assert result is None


# ═══════════════════════════════════════════════════
#  TestRouteORS
# ═══════════════════════════════════════════════════

class TestRouteORS:
    @patch("lib.route_eta.requests")
    def test_success(self, mock_requests):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "routes": [{
                "summary": {"duration": 5400, "distance": 75000}
            }]
        }
        mock_requests.post.return_value = mock_resp

        result = _route_via_ors((32.8, 35.0), (31.8, 34.6), "test-key")
        assert result is not None
        assert result["duration_minutes"] == 90.0
        assert result["distance_km"] == 75.0
        assert result["provider"] == "openrouteservice"

    @patch("lib.route_eta.requests")
    def test_auth_error(self, mock_requests):
        mock_resp = Mock()
        mock_resp.status_code = 403
        mock_resp.text = "Unauthorized"
        mock_requests.post.return_value = mock_resp

        result = _route_via_ors((32.8, 35.0), (31.8, 34.6), "bad-key")
        assert result is None

    @patch("lib.route_eta.requests")
    def test_network_error(self, mock_requests):
        mock_requests.post.side_effect = Exception("timeout")

        result = _route_via_ors((32.8, 35.0), (31.8, 34.6), "key")
        assert result is None

    def test_no_api_key(self):
        result = _route_via_ors((32.8, 35.0), (31.8, 34.6), None)
        assert result is None


# ═══════════════════════════════════════════════════
#  TestRouteOSRM
# ═══════════════════════════════════════════════════

class TestRouteOSRM:
    @patch("lib.route_eta.requests")
    def test_success(self, mock_requests):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [{
                "duration": 3600,
                "distance": 50000
            }]
        }
        mock_requests.get.return_value = mock_resp

        result = _route_via_osrm((32.8, 35.0), (31.8, 34.6))
        assert result is not None
        assert result["duration_minutes"] == 60.0
        assert result["distance_km"] == 50.0
        assert result["provider"] == "osrm"

    @patch("lib.route_eta.requests")
    def test_bad_coords(self, mock_requests):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"code": "NoRoute", "routes": []}
        mock_requests.get.return_value = mock_resp

        result = _route_via_osrm((0, 0), (0, 0))
        assert result is None

    @patch("lib.route_eta.requests")
    def test_http_error(self, mock_requests):
        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_requests.get.return_value = mock_resp

        result = _route_via_osrm((32.8, 35.0), (31.8, 34.6))
        assert result is None


# ═══════════════════════════════════════════════════
#  TestCalculateRouteEta
# ═══════════════════════════════════════════════════

class TestCalculateRouteEta:
    def test_cache_hit(self):
        """Cached result returned without calling any API."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = True
        cache_doc.to_dict.return_value = {
            "duration_minutes": 90,
            "distance_km": 75.5,
            "route_summary": "OSRM driving: 75.5 km",
            "provider": "osrm",
            "cached_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        result = calculate_route_eta(db, "חיפה", "ILHFA")
        assert result is not None
        assert result["cached"] is True
        assert result["duration_minutes"] == 90

    def test_cache_expired(self):
        """Expired cache entry triggers fresh calculation."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = True
        cache_doc.to_dict.return_value = {
            "duration_minutes": 90,
            "distance_km": 75.5,
            "route_summary": "old",
            "provider": "osrm",
            "cached_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
        }
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        with patch("lib.route_eta._geocode_address") as mock_geo, \
             patch("lib.route_eta._route_via_osrm") as mock_osrm:
            mock_geo.return_value = (32.8, 35.0)
            mock_osrm.return_value = {
                "duration_minutes": 60, "distance_km": 50,
                "route_summary": "fresh", "provider": "osrm",
            }

            result = calculate_route_eta(db, "חיפה", "ILHFA")
            assert result is not None
            assert result["cached"] is False
            assert result["duration_minutes"] == 60

    @patch("lib.route_eta._geocode_address")
    @patch("lib.route_eta._route_via_ors")
    def test_ors_primary(self, mock_ors, mock_geo):
        """ORS used when API key available."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        mock_geo.return_value = (32.8, 35.0)
        mock_ors.return_value = {
            "duration_minutes": 85, "distance_km": 70,
            "route_summary": "ORS", "provider": "openrouteservice",
        }

        get_secret = Mock(return_value="test-ors-key")
        result = calculate_route_eta(db, "חיפה", "ILHFA", get_secret)

        assert result is not None
        assert result["provider"] == "openrouteservice"
        mock_ors.assert_called_once()

    @patch("lib.route_eta._geocode_address")
    @patch("lib.route_eta._route_via_ors")
    @patch("lib.route_eta._route_via_osrm")
    def test_ors_fail_osrm_fallback(self, mock_osrm, mock_ors, mock_geo):
        """OSRM fallback when ORS fails."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        mock_geo.return_value = (32.8, 35.0)
        mock_ors.return_value = None
        mock_osrm.return_value = {
            "duration_minutes": 92, "distance_km": 76,
            "route_summary": "OSRM", "provider": "osrm",
        }

        get_secret = Mock(return_value="bad-key")
        result = calculate_route_eta(db, "חיפה", "ILHFA", get_secret)

        assert result["provider"] == "osrm"
        mock_ors.assert_called_once()
        mock_osrm.assert_called_once()

    @patch("lib.route_eta._geocode_address")
    @patch("lib.route_eta._route_via_osrm")
    def test_no_api_key_straight_to_osrm(self, mock_osrm, mock_geo):
        """No ORS key → skip ORS, go directly to OSRM."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        mock_geo.return_value = (32.8, 35.0)
        mock_osrm.return_value = {
            "duration_minutes": 88, "distance_km": 73,
            "route_summary": "OSRM", "provider": "osrm",
        }

        result = calculate_route_eta(db, "חיפה", "ILHFA", None)
        assert result["provider"] == "osrm"

    @patch("lib.route_eta._geocode_address")
    def test_geocode_fails_returns_none(self, mock_geo):
        """If geocoding fails, return None gracefully."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        mock_geo.return_value = None
        result = calculate_route_eta(db, "xxxx nowhere xxxx", "ILHFA")
        assert result is None

    def test_unknown_port_returns_none(self):
        """Unknown port code → None."""
        db = Mock()
        result = calculate_route_eta(db, "חיפה", "XXXXX")
        assert result is None

    def test_empty_inputs_return_none(self):
        db = Mock()
        assert calculate_route_eta(db, "", "ILHFA") is None
        assert calculate_route_eta(db, "חיפה", "") is None
        assert calculate_route_eta(db, None, "ILHFA") is None

    @patch("lib.route_eta._geocode_address")
    @patch("lib.route_eta._route_via_osrm")
    def test_writes_to_cache(self, mock_osrm, mock_geo):
        """Successful result is written to route_cache."""
        db = Mock()
        cache_doc = Mock()
        cache_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = cache_doc

        mock_geo.return_value = (32.8, 35.0)
        mock_osrm.return_value = {
            "duration_minutes": 60, "distance_km": 50,
            "route_summary": "test", "provider": "osrm",
        }

        calculate_route_eta(db, "חיפה", "ILHFA")

        # Verify cache write was called
        db.collection.return_value.document.return_value.set.assert_called_once()
        written_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert written_data["duration_minutes"] == 60
        assert written_data["port_code"] == "ILHFA"
        assert "cached_at" in written_data


# ═══════════════════════════════════════════════════
#  TestParseGateCutoff
# ═══════════════════════════════════════════════════

class TestParseGateCutoff:
    def test_iso_with_tz(self):
        dt = _parse_gate_cutoff("2026-02-19T14:00:00+02:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 19

    def test_iso_utc(self):
        dt = _parse_gate_cutoff("2026-02-19T12:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_datetime_gets_israel_tz(self):
        dt = _parse_gate_cutoff("2026-02-19T14:00:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_none_returns_none(self):
        assert _parse_gate_cutoff(None) is None
        assert _parse_gate_cutoff("") is None

    def test_bad_string_returns_none(self):
        assert _parse_gate_cutoff("not a date") is None

    def test_datetime_object_passthrough(self):
        original = datetime(2026, 2, 19, 14, 0, tzinfo=timezone.utc)
        dt = _parse_gate_cutoff(original)
        assert dt == original


# ═══════════════════════════════════════════════════
#  TestBuildCutoffSubject
# ═══════════════════════════════════════════════════

class TestBuildCutoffSubject:
    def test_warning_subject(self):
        deal = _mock_deal()
        subj = _build_cutoff_subject(deal, "d1", "warning", 100)
        assert "⚠️" in subj
        assert "ZIMLNS1234567" in subj
        assert "100 min" in subj
        assert "ZIM SHANGHAI" in subj

    def test_urgent_subject(self):
        deal = _mock_deal()
        subj = _build_cutoff_subject(deal, "d1", "urgent", 30)
        assert "🚨" in subj
        assert "URGENT" in subj
        assert "ZIMLNS1234567" in subj

    def test_critical_subject(self):
        deal = _mock_deal()
        subj = _build_cutoff_subject(deal, "d1", "critical", -10)
        assert "🔴" in subj
        assert "MISSED cutoff" in subj
        assert "late entry" in subj

    def test_fallback_deal_ref(self):
        deal = _mock_deal({"bol_number": "", "booking_number": ""})
        subj = _build_cutoff_subject(deal, "deal_abc123def", "warning", 100)
        assert "deal_abc123d" in subj


# ═══════════════════════════════════════════════════
#  TestBuildCutoffAlertHtml
# ═══════════════════════════════════════════════════

class TestBuildCutoffAlertHtml:
    def test_warning_html(self):
        deal = _mock_deal()
        eta = _mock_eta_result()
        html = _build_cutoff_alert_html(deal, "d1", "warning", 100, eta)
        assert "WARNING" in html
        assert "ZIMLNS1234567" in html
        assert "90" in html  # ETA minutes
        assert "Haifa" in html

    def test_critical_has_late_entry_draft(self):
        deal = _mock_deal()
        eta = _mock_eta_result()
        html = _build_cutoff_alert_html(deal, "d1", "critical", -15, eta)
        assert "Late Entry Request" in html
        assert "בקשת כניסה מאוחרת" in html
        assert "MISSED" in html

    def test_urgent_no_late_entry_section(self):
        deal = _mock_deal()
        eta = _mock_eta_result()
        html = _build_cutoff_alert_html(deal, "d1", "urgent", 30, eta)
        assert "Late Entry Request" not in html

    def test_buffer_display_negative(self):
        deal = _mock_deal()
        eta = _mock_eta_result()
        html = _build_cutoff_alert_html(deal, "d1", "critical", -20, eta)
        assert "MISSED by 20 minutes" in html


# ═══════════════════════════════════════════════════
#  TestCheckGateCutoffAlerts
# ═══════════════════════════════════════════════════

class TestCheckGateCutoffAlerts:
    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_no_active_deals(self, mock_send, mock_eta):
        db = _mock_db_with_deals([])
        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")
        assert result["status"] == "ok"
        assert result["deals_checked"] == 0
        assert result["alerts_sent"] == 0
        mock_eta.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_warning_alert_at_100_min(self, mock_send, mock_eta):
        """Buffer = 100 min → WARNING email sent."""
        # gate_cutoff in ~190 min from now, ETA=90 min → buffer=100 min
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=190)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_w1", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 1
        mock_send.assert_called_once()
        sent_subject = mock_send.call_args[0][3]
        assert "⚠️" in sent_subject

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_urgent_alert_at_30_min(self, mock_send, mock_eta):
        """Buffer = 30 min → URGENT email sent."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=120)).isoformat()  # 120 - 90 ETA = 30 buffer
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_u1", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 1
        sent_subject = mock_send.call_args[0][3]
        assert "🚨" in sent_subject

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_critical_alert_negative_buffer(self, mock_send, mock_eta):
        """Buffer < 0 → CRITICAL email with late entry draft."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=80)).isoformat()  # 80 - 90 ETA = -10 buffer
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_c1", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 1
        sent_subject = mock_send.call_args[0][3]
        assert "🔴" in sent_subject
        sent_body = mock_send.call_args[0][4]
        assert "Late Entry Request" in sent_body

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_no_alert_large_buffer(self, mock_send, mock_eta):
        """Buffer > 120 min → no alert."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(hours=5)).isoformat()  # 300 - 90 = 210 buffer
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_ok", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_dedup_already_sent(self, mock_send, mock_eta):
        """Already sent 'warning' → skip, don't resend."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=190)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff, "cutoff_alerts_sent": ["warning"]})
        deal_doc = _mock_deal_doc("deal_dup", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_escalation_warning_to_urgent(self, mock_send, mock_eta):
        """Warning already sent, now urgent → send urgent."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=120)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff, "cutoff_alerts_sent": ["warning"]})
        deal_doc = _mock_deal_doc("deal_esc", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 1
        sent_subject = mock_send.call_args[0][3]
        assert "🚨" in sent_subject

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_skip_no_pickup_address(self, mock_send, mock_eta):
        """Deal without land_pickup_address → skip."""
        deal = _mock_deal({"land_pickup_address": ""})
        deal_doc = _mock_deal_doc("deal_nopickup", deal)
        db = _mock_db_with_deals([deal_doc])

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["deals_checked"] == 0
        mock_eta.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_skip_no_gate_cutoff(self, mock_send, mock_eta):
        """Deal without gate_cutoff → skip."""
        deal = _mock_deal({"gate_cutoff": ""})
        deal_doc = _mock_deal_doc("deal_nocutoff", deal)
        db = _mock_db_with_deals([deal_doc])

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["deals_checked"] == 0
        mock_eta.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_skip_port_arrived(self, mock_send, mock_eta):
        """Deal already at port → skip."""
        deal = _mock_deal({"current_step": "port_arrived"})
        deal_doc = _mock_deal_doc("deal_arrived", deal)
        db = _mock_db_with_deals([deal_doc])

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["deals_checked"] == 0
        mock_eta.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_skip_stopped_deals(self, mock_send, mock_eta):
        """Deal with follow_mode=stopped → skip."""
        deal = _mock_deal({"follow_mode": "stopped"})
        deal_doc = _mock_deal_doc("deal_stopped", deal)
        db = _mock_db_with_deals([deal_doc])

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["deals_checked"] == 0
        mock_eta.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_eta_fails_gracefully(self, mock_send, mock_eta):
        """ETA calculation returns None → skip deal, no crash."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=60)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_noeta", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = None

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["status"] == "ok"
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_updates_deal_doc_after_alert(self, mock_send, mock_eta):
        """After sending alert, deal doc updated with cutoff_alerts_sent."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=190)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_upd", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        # Verify deal was updated
        db.collection.return_value.document.return_value.update.assert_called()
        update_args = db.collection.return_value.document.return_value.update.call_args[0][0]
        assert "warning" in update_args["cutoff_alerts_sent"]

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_no_follower_email(self, mock_send, mock_eta):
        """No follower email → alert not sent but no crash."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=190)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff, "follower_email": ""})
        deal_doc = _mock_deal_doc("deal_noemail", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_multiple_deals(self, mock_send, mock_eta):
        """Multiple qualifying deals → each checked independently."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff_warn = (now + timedelta(minutes=190)).isoformat()
        cutoff_ok = (now + timedelta(hours=5)).isoformat()

        deal1 = _mock_deal({"gate_cutoff": cutoff_warn, "bol_number": "BOL1"})
        deal2 = _mock_deal({"gate_cutoff": cutoff_ok, "bol_number": "BOL2"})
        deal3 = _mock_deal({"gate_cutoff": cutoff_warn, "bol_number": "BOL3"})

        docs = [
            _mock_deal_doc("d1", deal1),
            _mock_deal_doc("d2", deal2),
            _mock_deal_doc("d3", deal3),
        ]
        db = _mock_db_with_deals(docs)

        mock_eta.return_value = _mock_eta_result(duration=90)
        mock_send.return_value = True

        result = check_gate_cutoff_alerts(db, None, Mock(), "token", "rcb@test.com")

        assert result["deals_checked"] == 3
        assert result["alerts_sent"] == 2  # deal1 + deal3 get warning, deal2 OK

    @patch("lib.route_eta.calculate_route_eta")
    @patch("lib.rcb_helpers.helper_graph_send")
    def test_no_access_token(self, mock_send, mock_eta):
        """No access_token → can't send emails, alerts_sent stays 0."""
        now = datetime.now(timezone(timedelta(hours=2)))
        cutoff = (now + timedelta(minutes=190)).isoformat()
        deal = _mock_deal({"gate_cutoff": cutoff})
        deal_doc = _mock_deal_doc("deal_notoken", deal)
        db = _mock_db_with_deals([deal_doc])

        mock_eta.return_value = _mock_eta_result(duration=90)

        result = check_gate_cutoff_alerts(db, None, Mock(), None, None)

        assert result["alerts_sent"] == 0


# ═══════════════════════════════════════════════════
#  TestConstants
# ═══════════════════════════════════════════════════

class TestConstants:
    def test_port_coords_haifa(self):
        assert PORT_COORDS["ILHFA"][0] == pytest.approx(32.8191, abs=0.01)

    def test_port_coords_ashdod(self):
        assert PORT_COORDS["ILASD"][0] == pytest.approx(31.8305, abs=0.01)

    def test_ben_gurion_coords(self):
        assert BEN_GURION_COORDS[0] == pytest.approx(32.0055, abs=0.01)

    def test_port_addresses_hebrew(self):
        assert "חיפה" in PORT_ADDRESSES["ILHFA"]
        assert "אשדוד" in PORT_ADDRESSES["ILASD"]

    def test_cache_ttl(self):
        assert CACHE_TTL_HOURS == 24
