"""
Tests for Block I: Port Intelligence — I1 (Deal-Schedule Linker) + I2 (Direction-Aware Views)
==============================================================================================
Covers: vessel matching (exact/fuzzy/voyage), schedule change detection, data consolidation,
        4 direction-aware views, storage risk escalation, congestion, step progress, customs status.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
from datetime import datetime, timezone, timedelta

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.port_intelligence import (
    # Constants
    SEA_PORTS, AIR_PORTS, SOURCE_PRIORITY,
    CONGESTION_BUSY, CONGESTION_CONGESTED,
    STORAGE_NOTICE_DAYS, STORAGE_WARNING_DAYS, STORAGE_CRITICAL_DAYS,
    AIR_STORAGE_NOTICE_HOURS, AIR_STORAGE_WARNING_HOURS, AIR_STORAGE_CRITICAL_HOURS,
    SCHEDULE_CHANGE_HOURS, FUZZY_MAX_DISTANCE,
    ETA_AGREEMENT_THRESHOLD_HOURS,
    # I1 functions
    levenshtein, link_deal_to_schedule, _is_schedule_change,
    # I2 view builders
    build_deal_intelligence,
    build_sea_import_intel, build_sea_export_intel,
    build_air_import_intel, build_air_export_intel,
    # I2 helpers
    _compute_storage_risk_import, _compute_storage_risk_export,
    _compute_air_storage_risk,
    _compute_congestion, _compute_step_progress, _compute_customs_status,
    _compute_export_cutoffs, _storage_level_and_message,
    # Consolidation
    consolidate_datetime_field, consolidate_string_field,
    _build_eta_sources, _build_etd_sources,
    # Utilities
    _parse_iso, _hours_until, _days_at_port, _normalize_vessel,
    _sanitize_vessel_name, _format_date_short, _now_israel,
    # I3: Alert Engine
    ALERT_DO_MISSING, ALERT_PHYSICAL_EXAM, ALERT_STORAGE_DAY3,
    check_port_intelligence_alerts, build_port_alert_subject, build_port_alert_html,
    # I4: Morning Digest
    DIGEST_SEA_PORTS, render_morning_digest_html,
    _digest_header, _digest_summary_bar, _digest_footer,
    _digest_port_status, _digest_port_card,
)


# ═══════════════════════════════════════════════════
#  TEST HELPERS
# ═══════════════════════════════════════════════════

def _mock_deal(overrides=None):
    """Create a test deal dict."""
    deal = {
        "bol_number": "ZIMLNS1234567",
        "awb_number": "",
        "vessel_name": "ZIM SHANGHAI",
        "voyage": "123W",
        "shipping_line": "ZIM",
        "port": "ILHFA",
        "port_name": "Haifa",
        "status": "active",
        "direction": "import",
        "eta": "2026-02-22T08:00:00Z",
        "etd": "",
        "gate_cutoff": "",
        "vgm_cutoff": "",
        "doc_cutoff": "",
        "container_cutoff": "",
        "containers": ["ZIMU1234567", "ZIMU7654321"],
        "customs_declaration": "26014441623750",
        "freight_kind": "FCL",
        "rcb_classification_id": "",
        "schedule_eta": "",
    }
    if overrides:
        deal.update(overrides)
    return deal


def _mock_container_status(overrides=None, container_id="ZIMU1234567",
                           import_process=None, export_process=None):
    """Create a test container_status dict.

    Can be called with a dict of overrides as first arg:
        _mock_container_status({"import_process": {...}})
    Or with keyword arguments:
        _mock_container_status(import_process={...})
    """
    cs = {
        "container_id": container_id,
        "deal_id": "test_deal_1",
        "import_process": import_process or {},
        "export_process": export_process or {},
    }
    if isinstance(overrides, dict):
        cs.update(overrides)
    elif isinstance(overrides, str):
        # Called as _mock_container_status("CONT123") — treat as container_id
        cs["container_id"] = overrides
    return cs


def _mock_schedule_doc(doc_id="sched_001", data=None):
    """Create a mock Firestore document for port_schedules."""
    doc = Mock()
    doc.id = doc_id
    doc.to_dict.return_value = data or {
        "vessel_name": "ZIM SHANGHAI",
        "port_code": "ILHFA",
        "eta": "2026-02-22T10:00:00Z",
        "etd": "",
        "voyage": "123W",
        "berth": "12",
        "confidence": "high",
        "sources": ["carrier_api", "haifa_port"],
        "shipping_line": "ZIM",
    }
    return doc


def _mock_awb_status(overrides=None):
    """Create a test AWB status dict."""
    awb = {
        "awb_number": "114-12345678",
        "awb_prefix": "114",
        "airline_name": "El Al",
        "terminal": "maman",
        "status_normalized": "arrived",
        "raw_status": "Arrived",
        "arrived_at": "2026-02-20T06:00:00Z",
        "released_at": "",
        "storage_start": "2026-02-20T06:00:00Z",
    }
    if overrides:
        awb.update(overrides)
    return awb


def _make_now(iso_str="2026-02-18T10:00:00+02:00"):
    """Parse ISO string into timezone-aware datetime for use as now_dt."""
    return _parse_iso(iso_str)


# ═══════════════════════════════════════════════════
#  CONSTANTS TESTS
# ═══════════════════════════════════════════════════

class TestConstants:
    def test_sea_ports_haifa(self):
        assert "ILHFA" in SEA_PORTS
        assert SEA_PORTS["ILHFA"]["name_en"] == "Haifa"

    def test_sea_ports_ashdod(self):
        assert "ILASD" in SEA_PORTS
        assert SEA_PORTS["ILASD"]["name_he"] == "אשדוד"

    def test_air_ports_ben_gurion(self):
        assert "ILLIB" in AIR_PORTS
        assert "LLBG" in AIR_PORTS
        assert "BEN_GURION" in AIR_PORTS

    def test_source_priority_order(self):
        assert SOURCE_PRIORITY["taskyam_deals"] < SOURCE_PRIORITY["carrier_api"]
        assert SOURCE_PRIORITY["carrier_api"] < SOURCE_PRIORITY["email"]
        assert SOURCE_PRIORITY["email"] < SOURCE_PRIORITY["aisstream"]

    def test_storage_thresholds(self):
        assert STORAGE_NOTICE_DAYS == 2
        assert STORAGE_WARNING_DAYS == 3
        assert STORAGE_CRITICAL_DAYS == 4

    def test_congestion_thresholds(self):
        assert CONGESTION_BUSY == 15
        assert CONGESTION_CONGESTED == 25

    def test_air_storage_thresholds(self):
        assert AIR_STORAGE_CRITICAL_HOURS == 48


# ═══════════════════════════════════════════════════
#  UTILITY TESTS
# ═══════════════════════════════════════════════════

class TestUtilities:
    def test_parse_iso_utc(self):
        dt = _parse_iso("2026-02-22T08:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.hour == 8

    def test_parse_iso_with_tz(self):
        dt = _parse_iso("2026-02-22T10:00:00+02:00")
        assert dt is not None

    def test_parse_iso_none(self):
        assert _parse_iso(None) is None
        assert _parse_iso("") is None

    def test_parse_iso_bare(self):
        dt = _parse_iso("2026-02-22T08:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc  # assumed UTC

    def test_parse_iso_with_fractional(self):
        dt = _parse_iso("2026-02-22T08:00:00.123456Z")
        assert dt is not None

    def test_hours_until_future(self):
        future = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
        now = datetime(2026, 2, 22, 8, 0, tzinfo=timezone.utc)
        assert _hours_until(future, now) == 2.0

    def test_hours_until_past(self):
        past = datetime(2026, 2, 22, 6, 0, tzinfo=timezone.utc)
        now = datetime(2026, 2, 22, 8, 0, tzinfo=timezone.utc)
        assert _hours_until(past, now) == -2.0

    def test_hours_until_none(self):
        assert _hours_until(None) is None

    def test_days_at_port(self):
        entry = datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc)
        now = datetime(2026, 2, 21, 8, 0, tzinfo=timezone.utc)
        assert _days_at_port(entry, now) == 3.0

    def test_sanitize_vessel_name(self):
        assert _sanitize_vessel_name("MSC ANNA\nVOY 123") == "MSC ANNA VOY 123"
        assert _sanitize_vessel_name("  ZIM  HAIFA  ") == "ZIM HAIFA"
        assert _sanitize_vessel_name("") == ""
        assert _sanitize_vessel_name(None) == ""

    def test_normalize_vessel(self):
        assert _normalize_vessel("zim shanghai") == "ZIM SHANGHAI"
        assert _normalize_vessel("  MSC Anna\n") == "MSC ANNA"

    def test_format_date_short(self):
        result = _format_date_short("2026-02-22T08:30:00Z")
        assert result  # Should produce something like "22/02 10:30" (Israel time)


# ═══════════════════════════════════════════════════
#  LEVENSHTEIN TESTS
# ═══════════════════════════════════════════════════

class TestLevenshtein:
    def test_identical(self):
        assert levenshtein("ZIM SHANGHAI", "ZIM SHANGHAI") == 0

    def test_one_char_diff(self):
        assert levenshtein("ZIM SHANGAI", "ZIM SHANGHAI") == 1

    def test_two_char_diff(self):
        assert levenshtein("ZIM SHANGH", "ZIM SHANGHAI") == 2

    def test_completely_different(self):
        assert levenshtein("MSC ANNA", "ZIM HAIFA") > FUZZY_MAX_DISTANCE

    def test_empty(self):
        assert levenshtein("", "") == 0
        assert levenshtein("ABC", "") == 3
        assert levenshtein("", "ABC") == 3

    def test_case_matters(self):
        assert levenshtein("ABC", "abc") == 3  # case-sensitive


# ═══════════════════════════════════════════════════
#  I1: DEAL-SCHEDULE LINKER TESTS
# ═══════════════════════════════════════════════════

class TestLinkDealToSchedule:
    def test_exact_match(self):
        """Exact vessel name + port_code → linked."""
        deal = _mock_deal()
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc()
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is not None
        assert result["match_type"] == "exact"
        assert result["match_distance"] == 0
        assert result["schedule_ref"] == "sched_001"
        assert result["berth"] == "12"
        assert result["schedule_confidence"] == "high"

    def test_fuzzy_match(self):
        """Vessel name with 1 char difference → fuzzy match."""
        deal = _mock_deal({"vessel_name": "ZIM SHANGAI"})  # missing H
        sched_data = {
            "vessel_name": "ZIM SHANGHAI",
            "port_code": "ILHFA",
            "eta": "2026-02-22T10:00:00Z",
            "etd": "",
            "voyage": "999W",
            "berth": "5",
            "confidence": "medium",
            "sources": ["carrier_api"],
        }
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc("sched_fuzzy", sched_data)
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is not None
        assert result["match_type"] == "fuzzy"
        assert result["match_distance"] <= FUZZY_MAX_DISTANCE

    def test_voyage_match(self):
        """No vessel name on deal but matching voyage → voyage match."""
        deal = _mock_deal({"vessel_name": "", "voyage": "123W"})
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc()
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is not None
        assert result["match_type"] == "voyage"

    def test_no_match(self):
        """Completely different vessel → None."""
        deal = _mock_deal({"vessel_name": "TOTALLY DIFFERENT VESSEL", "voyage": "999X"})
        sched_data = {
            "vessel_name": "MSC ANNA",
            "port_code": "ILHFA",
            "eta": "2026-02-25",
            "etd": "",
            "voyage": "456E",
            "berth": "",
            "confidence": "low",
            "sources": ["email"],
        }
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc("sched_other", sched_data)
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is None

    def test_no_port(self):
        """Deal without port code → None."""
        deal = _mock_deal({"port": ""})
        db = Mock()
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is None

    def test_no_vessel_no_voyage(self):
        """Deal without vessel or voyage → None."""
        deal = _mock_deal({"vessel_name": "", "voyage": ""})
        db = Mock()
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is None

    def test_no_db(self):
        """None db → None."""
        deal = _mock_deal()
        result = link_deal_to_schedule(None, "deal_1", deal)
        assert result is None

    def test_empty_schedules(self):
        """No port_schedules docs → None."""
        deal = _mock_deal()
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = []
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is None

    def test_firestore_exception(self):
        """Firestore throws → None (graceful)."""
        deal = _mock_deal()
        db = Mock()
        db.collection.return_value.where.return_value.stream.side_effect = Exception("Firestore down")
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is None

    def test_exact_wins_over_fuzzy(self):
        """When both exact and fuzzy matches exist, exact wins."""
        deal = _mock_deal({"vessel_name": "ZIM SHANGHAI"})
        exact_data = {
            "vessel_name": "ZIM SHANGHAI", "port_code": "ILHFA",
            "eta": "2026-02-22T10:00:00Z", "etd": "", "voyage": "123W",
            "berth": "12", "confidence": "high", "sources": ["carrier_api"],
        }
        fuzzy_data = {
            "vessel_name": "ZIM SHANGAI", "port_code": "ILHFA",
            "eta": "2026-02-23", "etd": "", "voyage": "999W",
            "berth": "5", "confidence": "low", "sources": ["email"],
        }
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc("sched_fuzzy", fuzzy_data),
            _mock_schedule_doc("sched_exact", exact_data),
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result["match_type"] == "exact"
        assert result["schedule_ref"] == "sched_exact"


class TestScheduleChangeDetection:
    def test_no_change(self):
        """Same ETA → no change."""
        assert not _is_schedule_change("2026-02-22T08:00:00Z", "2026-02-22T09:00:00Z")

    def test_change_detected(self):
        """ETA shifted by 5 hours → change."""
        assert _is_schedule_change("2026-02-22T08:00:00Z", "2026-02-22T13:00:00Z")

    def test_no_change_empty(self):
        """Empty values → no change."""
        assert not _is_schedule_change("", "2026-02-22T08:00:00Z")
        assert not _is_schedule_change("2026-02-22T08:00:00Z", "")

    def test_change_on_deal(self):
        """Deal has old schedule_eta, new schedule has different ETA → change detected."""
        deal = _mock_deal({"schedule_eta": "2026-02-22T08:00:00Z"})
        sched_data = {
            "vessel_name": "ZIM SHANGHAI", "port_code": "ILHFA",
            "eta": "2026-02-23T08:00:00Z",  # 24h later
            "etd": "", "voyage": "123W", "berth": "12",
            "confidence": "high", "sources": ["carrier_api"],
        }
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [
            _mock_schedule_doc("sched_001", sched_data)
        ]
        result = link_deal_to_schedule(db, "deal_1", deal)
        assert result is not None
        assert result["schedule_changed"] is True
        assert result["previous_eta"] == "2026-02-22T08:00:00Z"


# ═══════════════════════════════════════════════════
#  DATA CONSOLIDATION TESTS
# ═══════════════════════════════════════════════════

class TestConsolidateDatetimeField:
    def test_empty_sources(self):
        result = consolidate_datetime_field([])
        assert result["best"] == ""
        assert result["source_count"] == 0
        assert result["sources_agree"] is True

    def test_single_source(self):
        result = consolidate_datetime_field([
            {"value": "2026-02-22T08:00:00Z", "source": "carrier_api"}
        ])
        assert result["best"] == "2026-02-22T08:00:00Z"
        assert result["best_source"] == "carrier_api"
        assert result["source_count"] == 1

    def test_two_sources_agree(self):
        result = consolidate_datetime_field([
            {"value": "2026-02-22T08:00:00Z", "source": "carrier_api"},
            {"value": "2026-02-22T10:00:00Z", "source": "deal_email"},  # 2h diff < 6h threshold
        ])
        assert result["sources_agree"] is True
        assert result["best_source"] == "carrier_api"  # higher priority
        assert result["source_count"] == 2

    def test_two_sources_disagree(self):
        result = consolidate_datetime_field([
            {"value": "2026-02-22T08:00:00Z", "source": "deal_email"},
            {"value": "2026-02-24T08:00:00Z", "source": "carrier_api"},  # 48h diff
        ])
        assert result["sources_agree"] is False
        assert result["best_source"] == "carrier_api"  # higher priority wins
        assert "of" in result["consensus"]  # e.g., "1 of 2 say Feb 22"
        assert result["source_count"] == 2

    def test_taskyam_wins_over_all(self):
        result = consolidate_datetime_field([
            {"value": "2026-02-24T08:00:00Z", "source": "carrier_api"},
            {"value": "2026-02-22T06:00:00Z", "source": "taskyam_deals"},
            {"value": "2026-02-23T08:00:00Z", "source": "deal_email"},
        ])
        assert result["best_source"] == "taskyam_deals"
        assert result["best"] == "2026-02-22T06:00:00Z"

    def test_empty_values_filtered(self):
        result = consolidate_datetime_field([
            {"value": "", "source": "carrier_api"},
            {"value": "2026-02-22T08:00:00Z", "source": "deal_email"},
        ])
        assert result["source_count"] == 1
        assert result["best_source"] == "deal_email"

    def test_none_values_filtered(self):
        result = consolidate_datetime_field([
            {"value": None, "source": "carrier_api"},
            {"value": "2026-02-22T08:00:00Z", "source": "email"},
        ])
        assert result["source_count"] == 1


class TestConsolidateStringField:
    def test_empty(self):
        result = consolidate_string_field([])
        assert result["best"] == ""

    def test_single(self):
        result = consolidate_string_field([
            {"value": "Berth 12", "source": "haifa_port"}
        ])
        assert result["best"] == "Berth 12"

    def test_priority(self):
        result = consolidate_string_field([
            {"value": "Berth 15", "source": "email"},
            {"value": "Berth 12", "source": "haifa_port"},
        ])
        assert result["best"] == "Berth 12"  # haifa_port beats email

    def test_empty_values_skipped(self):
        result = consolidate_string_field([
            {"value": "", "source": "haifa_port"},
            {"value": "Berth 5", "source": "email"},
        ])
        assert result["best"] == "Berth 5"


class TestBuildEtaSources:
    def test_deal_only(self):
        deal = _mock_deal()
        sources = _build_eta_sources(deal, None)
        assert len(sources) == 1
        assert sources[0]["source"] == "deal_email"

    def test_deal_and_schedule(self):
        deal = _mock_deal()
        link = {
            "schedule_eta": "2026-02-22T10:00:00Z",
            "schedule_sources": ["carrier_api", "haifa_port"],
        }
        sources = _build_eta_sources(deal, link)
        assert len(sources) == 2

    def test_with_taskyam_arrival(self):
        deal = _mock_deal()
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-22T06:00:00Z"
        })]
        sources = _build_eta_sources(deal, None, cs)
        assert any(s["source"] == "taskyam_deals" for s in sources)


# ═══════════════════════════════════════════════════
#  I2: SEA IMPORT VIEW TESTS
# ═══════════════════════════════════════════════════

class TestSeaImportIntel:
    def test_basic_structure(self):
        deal = _mock_deal()
        result = build_sea_import_intel(deal, [])
        assert result["view_type"] == "sea_import"
        assert "eta" in result
        assert "vessel" in result
        assert "schedule" in result
        assert "progress" in result
        assert "customs" in result
        assert "documents" in result
        assert "storage_risk" in result
        assert "congestion" in result
        assert "port" in result

    def test_port_info(self):
        deal = _mock_deal({"port": "ILHFA"})
        result = build_sea_import_intel(deal, [])
        assert result["port"]["code"] == "ILHFA"
        assert result["port"]["name_en"] == "Haifa"

    def test_vessel_info(self):
        deal = _mock_deal()
        result = build_sea_import_intel(deal, [])
        assert result["vessel"]["name"] == "ZIM SHANGHAI"
        assert result["vessel"]["voyage"] == "123W"
        assert result["vessel"]["shipping_line"] == "ZIM"

    def test_eta_consolidated(self):
        deal = _mock_deal({"eta": "2026-02-22T08:00:00Z"})
        link = {
            "schedule_eta": "2026-02-22T10:00:00Z",
            "schedule_sources": ["carrier_api"],
        }
        result = build_sea_import_intel(deal, [], schedule_link=link)
        # carrier_api has higher priority than deal_email
        assert result["eta"]["best_source"] == "carrier_api"
        assert result["eta"]["sources_agree"] is True
        assert result["eta"]["source_count"] == 2

    def test_vessel_arrived(self):
        deal = _mock_deal()
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-22T06:00:00Z",
            "ManifestDate": "2026-02-20T08:00:00Z",
        })]
        result = build_sea_import_intel(deal, cs)
        assert result["eta"]["arrived"] is True
        assert result["eta"]["arrival_date"] == "2026-02-22T06:00:00Z"

    def test_delivery_order(self):
        deal = _mock_deal()
        cs = [_mock_container_status(import_process={
            "DeliveryOrderDate": "2026-02-23T10:00:00Z",
        })]
        result = build_sea_import_intel(deal, cs)
        assert result["documents"]["delivery_order"] is True

    def test_no_delivery_order(self):
        deal = _mock_deal()
        result = build_sea_import_intel(deal, [])
        assert result["documents"]["delivery_order"] is False

    def test_schedule_linked(self):
        deal = _mock_deal()
        link = {
            "schedule_ref": "sched_001",
            "berth": "12",
            "schedule_eta": "2026-02-22T10:00:00Z",
            "schedule_etd": "",
            "schedule_confidence": "high",
            "schedule_sources": ["carrier_api"],
            "match_type": "exact",
            "schedule_changed": False,
            "previous_eta": "",
        }
        result = build_sea_import_intel(deal, [], schedule_link=link)
        assert result["schedule"]["linked"] is True
        assert result["schedule"]["berth"] == "12"

    def test_schedule_not_linked(self):
        deal = _mock_deal()
        result = build_sea_import_intel(deal, [], schedule_link=None)
        assert result["schedule"]["linked"] is False


# ═══════════════════════════════════════════════════
#  I2: SEA EXPORT VIEW TESTS
# ═══════════════════════════════════════════════════

class TestSeaExportIntel:
    def test_basic_structure(self):
        deal = _mock_deal({"direction": "export", "etd": "2026-02-25T08:00:00Z"})
        result = build_sea_export_intel(deal, [])
        assert result["view_type"] == "sea_export"
        assert "etd" in result
        assert "cutoffs" in result
        assert "schedule" in result
        assert "progress" in result
        assert "customs" in result
        assert "storage_risk" in result

    def test_etd_consolidated(self):
        deal = _mock_deal({"direction": "export", "etd": "2026-02-25T08:00:00Z"})
        link = {
            "schedule_etd": "2026-02-25T10:00:00Z",
            "schedule_sources": ["carrier_api"],
            "schedule_eta": "",
        }
        result = build_sea_export_intel(deal, [], schedule_link=link)
        assert result["etd"]["best_source"] == "carrier_api"
        assert result["etd"]["source_count"] == 2

    def test_vessel_departed(self):
        deal = _mock_deal({"direction": "export"})
        cs = [_mock_container_status(export_process={
            "ShipSailingDate": "2026-02-25T14:00:00Z"
        })]
        result = build_sea_export_intel(deal, cs)
        assert result["etd"]["departed"] is True

    def test_cutoffs_computed(self):
        deal = _mock_deal({
            "direction": "export",
            "gate_cutoff": "2026-02-24T14:00:00Z",
            "doc_cutoff": "2026-02-24T10:00:00Z",
        })
        result = build_sea_export_intel(deal, [])
        assert result["cutoffs"]["gate_cutoff"] == "2026-02-24T14:00:00Z"
        assert result["cutoffs"]["doc_cutoff"] == "2026-02-24T10:00:00Z"
        assert result["cutoffs"]["gate_cutoff_hours"] is not None


# ═══════════════════════════════════════════════════
#  I2: AIR IMPORT VIEW TESTS
# ═══════════════════════════════════════════════════

class TestAirImportIntel:
    def test_basic_structure(self):
        deal = _mock_deal({"freight_kind": "air", "awb_number": "114-12345678"})
        awb = _mock_awb_status()
        result = build_air_import_intel(deal, awb)
        assert result["view_type"] == "air_import"
        assert result["flight"]["awb_number"] == "114-12345678"
        assert result["flight"]["airline_name"] == "El Al"
        assert result["flight"]["terminal"] == "maman"

    def test_customs_hold(self):
        deal = _mock_deal({"freight_kind": "air", "awb_number": "114-12345678"})
        awb = _mock_awb_status({"status_normalized": "customs_hold"})
        result = build_air_import_intel(deal, awb)
        assert result["customs"]["hold"] is True
        assert result["customs"]["status"] == "hold"

    def test_customs_released(self):
        deal = _mock_deal({"freight_kind": "air", "awb_number": "114-12345678"})
        awb = _mock_awb_status({
            "status_normalized": "released",
            "released_at": "2026-02-21T10:00:00Z",
        })
        result = build_air_import_intel(deal, awb)
        assert result["customs"]["released"] is True
        assert result["customs"]["released_at"] == "2026-02-21T10:00:00Z"

    def test_no_awb_status(self):
        deal = _mock_deal({"freight_kind": "air", "awb_number": "114-12345678"})
        result = build_air_import_intel(deal, None)
        assert result["view_type"] == "air_import"
        assert result["awb_status"]["status"] == ""

    def test_port_is_ben_gurion(self):
        deal = _mock_deal({"freight_kind": "air"})
        result = build_air_import_intel(deal, None)
        assert result["port"]["code"] == "ILLIB"
        assert "Ben Gurion" in result["port"]["name_en"]


# ═══════════════════════════════════════════════════
#  I2: AIR EXPORT VIEW TESTS
# ═══════════════════════════════════════════════════

class TestAirExportIntel:
    def test_basic_structure(self):
        deal = _mock_deal({
            "freight_kind": "air", "direction": "export",
            "awb_number": "114-12345678", "etd": "2026-02-25T08:00:00Z",
        })
        awb = _mock_awb_status()
        result = build_air_export_intel(deal, awb)
        assert result["view_type"] == "air_export"
        assert "etd" in result
        assert "cutoffs" in result

    def test_cutoffs(self):
        deal = _mock_deal({
            "freight_kind": "air", "direction": "export",
            "acceptance_cutoff": "2026-02-24T14:00:00Z",
            "awb_cutoff": "2026-02-24T10:00:00Z",
        })
        result = build_air_export_intel(deal, None)
        assert result["cutoffs"]["acceptance_cutoff"] == "2026-02-24T14:00:00Z"
        assert result["cutoffs"]["awb_cutoff"] == "2026-02-24T10:00:00Z"
        assert result["cutoffs"]["acceptance_cutoff_hours"] is not None


# ═══════════════════════════════════════════════════
#  STORAGE RISK TESTS
# ═══════════════════════════════════════════════════

class TestStorageRiskImport:
    def test_no_containers(self):
        result = _compute_storage_risk_import([])
        assert result["level"] == "none"
        assert result["containers_at_risk"] == 0

    def test_container_not_arrived(self):
        """Container without PortUnloadingDate → no risk."""
        cs = [_mock_container_status(import_process={})]
        result = _compute_storage_risk_import(cs)
        assert result["level"] == "none"

    def test_container_already_exited(self):
        """Container with CargoExitDate → no risk."""
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",
            "CargoExitDate": "2026-02-19T08:00:00Z",
        })]
        result = _compute_storage_risk_import(cs)
        assert result["level"] == "none"

    def test_notice_at_2_days(self):
        """Container at port 2 days → notice level."""
        now = _make_now("2026-02-20T08:00:00Z")
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",  # 2 days ago
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["level"] == "notice"
        assert result["containers_at_risk"] == 1
        assert "2" in result["message"]  # "2 more days"

    def test_warning_at_3_days(self):
        """Container at port 3 days → warning level."""
        now = _make_now("2026-02-21T08:00:00Z")
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",  # 3 days ago
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["level"] == "warning"
        assert "tomorrow" in result["message"].lower()

    def test_critical_at_4_days(self):
        """Container at port 4 days → critical level."""
        now = _make_now("2026-02-22T08:00:00Z")
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",  # 4 days ago
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["level"] == "critical"
        assert "charges" in result["message"].lower()

    def test_critical_at_6_days(self):
        """Container at port 6 days → still critical."""
        now = _make_now("2026-02-24T08:00:00Z")
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",  # 6 days ago
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["level"] == "critical"
        assert result["days_at_port"] == 6.0

    def test_hebrew_messages(self):
        now = _make_now("2026-02-20T08:00:00Z")
        cs = [_mock_container_status(import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["message_he"]  # Hebrew message populated

    def test_multiple_containers_worst_wins(self):
        """Multiple containers: worst risk level wins."""
        now = _make_now("2026-02-22T08:00:00Z")
        cs = [
            _mock_container_status("C1", import_process={
                "PortUnloadingDate": "2026-02-20T08:00:00Z",  # 2 days → notice
            }),
            _mock_container_status("C2", import_process={
                "PortUnloadingDate": "2026-02-18T08:00:00Z",  # 4 days → critical
            }),
        ]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert result["level"] == "critical"
        assert result["containers_at_risk"] == 2

    def test_container_details_populated(self):
        now = _make_now("2026-02-21T08:00:00Z")
        cs = [_mock_container_status("ZIMU1234567", import_process={
            "PortUnloadingDate": "2026-02-18T08:00:00Z",
        })]
        result = _compute_storage_risk_import(cs, now_dt=now)
        assert len(result["container_details"]) == 1
        assert result["container_details"][0]["container_id"] == "ZIMU1234567"


class TestStorageRiskExport:
    def test_no_containers(self):
        result = _compute_storage_risk_export([])
        assert result["level"] == "none"

    def test_warning_at_3_days(self):
        now = _make_now("2026-02-21T08:00:00Z")
        cs = [_mock_container_status(export_process={
            "CargoEntryDate": "2026-02-18T08:00:00Z",  # 3 days ago
        })]
        result = _compute_storage_risk_export(cs, now_dt=now)
        assert result["level"] == "warning"


class TestStorageLevelAndMessage:
    def test_none(self):
        level, msg = _storage_level_and_message(1.5)
        assert level == "none"
        assert msg == ""

    def test_notice(self):
        level, msg = _storage_level_and_message(2.0)
        assert level == "notice"

    def test_warning(self):
        level, msg = _storage_level_and_message(3.0)
        assert level == "warning"

    def test_critical(self):
        level, msg = _storage_level_and_message(4.0)
        assert level == "critical"

    def test_critical_high_days(self):
        level, msg = _storage_level_and_message(10.0)
        assert level == "critical"


class TestAirStorageRisk:
    def test_no_awb(self):
        result = _compute_air_storage_risk(None)
        assert result["level"] == "none"

    def test_released_no_risk(self):
        awb = _mock_awb_status({"status_normalized": "released"})
        result = _compute_air_storage_risk(awb)
        assert result["level"] == "none"

    def test_notice_at_24h(self):
        now = _make_now("2026-02-21T06:00:00Z")
        awb = _mock_awb_status({
            "storage_start": "2026-02-20T06:00:00Z",  # 24h ago
            "status_normalized": "arrived",
        })
        result = _compute_air_storage_risk(awb, now_dt=now)
        assert result["level"] == "notice"

    def test_warning_at_36h(self):
        now = _make_now("2026-02-21T18:00:00Z")
        awb = _mock_awb_status({
            "storage_start": "2026-02-20T06:00:00Z",  # 36h ago
            "status_normalized": "at_terminal",
        })
        result = _compute_air_storage_risk(awb, now_dt=now)
        assert result["level"] == "warning"

    def test_critical_at_48h(self):
        now = _make_now("2026-02-22T06:00:00Z")
        awb = _mock_awb_status({
            "storage_start": "2026-02-20T06:00:00Z",  # 48h ago
            "status_normalized": "at_terminal",
        })
        result = _compute_air_storage_risk(awb, now_dt=now)
        assert result["level"] == "critical"


# ═══════════════════════════════════════════════════
#  CONGESTION TESTS
# ═══════════════════════════════════════════════════

class TestCongestion:
    def test_normal(self):
        report = {"total_vessels": 10}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "normal"
        assert result["vessel_count"] == 10

    def test_busy(self):
        report = {"total_vessels": 18}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "busy"

    def test_congested(self):
        report = {"total_vessels": 30}
        result = _compute_congestion(report, "ILASD")
        assert result["level"] == "congested"

    def test_no_report(self):
        result = _compute_congestion(None, "ILHFA")
        assert result["level"] == "normal"
        assert result["vessel_count"] == 0

    def test_boundary_15(self):
        """Exactly 15 → normal (threshold is >15)."""
        report = {"total_vessels": 15}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "normal"

    def test_boundary_16(self):
        """16 → busy."""
        report = {"total_vessels": 16}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "busy"

    def test_boundary_25(self):
        """25 → busy (threshold is >25)."""
        report = {"total_vessels": 25}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "busy"

    def test_boundary_26(self):
        """26 → congested."""
        report = {"total_vessels": 26}
        result = _compute_congestion(report, "ILHFA")
        assert result["level"] == "congested"

    def test_port_name_haifa(self):
        report = {"total_vessels": 5}
        result = _compute_congestion(report, "ILHFA")
        assert result["port_name_en"] == "Haifa"
        assert result["port_name_he"] == "חיפה"


# ═══════════════════════════════════════════════════
#  STEP PROGRESS TESTS
# ═══════════════════════════════════════════════════

class TestStepProgress:
    def test_no_containers(self):
        result = _compute_step_progress([], "import")
        assert result["completed_steps"] == 0
        assert result["percent"] == 0
        assert result["containers_total"] == 0

    def test_import_at_manifest(self):
        cs = [_mock_container_status(import_process={
            "ManifestDate": "2026-02-18T08:00:00Z",
        })]
        result = _compute_step_progress(cs, "import")
        assert result["completed_steps"] == 1
        assert result["current_step"] == "manifest"
        assert result["percent"] > 0

    def test_import_at_customs_release(self):
        cs = [_mock_container_status(import_process={
            "ManifestDate": "2026-02-18T08:00:00Z",
            "PortUnloadingDate": "2026-02-19T08:00:00Z",
            "DeliveryOrderDate": "2026-02-20T08:00:00Z",
            "CustomsCheckDate": "2026-02-21T08:00:00Z",
            "CustomsReleaseDate": "2026-02-21T14:00:00Z",
        })]
        result = _compute_step_progress(cs, "import")
        assert result["completed_steps"] == 5
        assert result["current_step"] == "customs_release"

    def test_import_complete(self):
        cs = [_mock_container_status(import_process={
            "ManifestDate": "2026-02-18",
            "PortUnloadingDate": "2026-02-19",
            "DeliveryOrderDate": "2026-02-20",
            "CustomsCheckDate": "2026-02-21",
            "CustomsReleaseDate": "2026-02-21",
            "PortReleaseDate": "2026-02-22",
            "EscortCertificateDate": "2026-02-22",
            "CargoExitRequestDate": "2026-02-22",
            "CargoExitDate": "2026-02-22",
        })]
        result = _compute_step_progress(cs, "import")
        assert result["containers_done"] == 1
        assert result["percent"] == 100

    def test_export_progress(self):
        cs = [_mock_container_status(export_process={
            "StorageIDDate": "2026-02-18",
            "CargoEntryDate": "2026-02-20",
        })]
        result = _compute_step_progress(cs, "export")
        assert result["completed_steps"] > 0
        assert result["current_step"] == "cargo_entry"

    def test_multiple_containers(self):
        cs = [
            _mock_container_status("C1", import_process={
                "ManifestDate": "2026-02-18", "CargoExitDate": "2026-02-22"
            }),
            _mock_container_status("C2", import_process={
                "ManifestDate": "2026-02-18",
            }),
        ]
        result = _compute_step_progress(cs, "import")
        assert result["containers_done"] == 1
        assert result["containers_total"] == 2


# ═══════════════════════════════════════════════════
#  CUSTOMS STATUS TESTS
# ═══════════════════════════════════════════════════

class TestCustomsStatus:
    def test_no_containers(self):
        result = _compute_customs_status([], "import", _mock_deal())
        assert result["status"] == "not_applicable"

    def test_pending(self):
        cs = [_mock_container_status(import_process={
            "ManifestDate": "2026-02-18",
        })]
        result = _compute_customs_status(cs, "import", _mock_deal())
        assert result["status"] == "pending"

    def test_under_check(self):
        cs = [_mock_container_status(import_process={
            "CustomsCheckDate": "2026-02-20",
        })]
        result = _compute_customs_status(cs, "import", _mock_deal())
        assert result["status"] == "under_check"

    def test_released(self):
        cs = [_mock_container_status(import_process={
            "CustomsCheckDate": "2026-02-20",
            "CustomsReleaseDate": "2026-02-21",
        })]
        result = _compute_customs_status(cs, "import", _mock_deal())
        assert result["status"] == "released"

    def test_partially_released(self):
        cs = [
            _mock_container_status("C1", import_process={
                "CustomsCheckDate": "2026-02-20",
                "CustomsReleaseDate": "2026-02-21",
            }),
            _mock_container_status("C2", import_process={
                "CustomsCheckDate": "2026-02-20",
            }),
        ]
        result = _compute_customs_status(cs, "import", _mock_deal())
        assert result["status"] == "partially_released"
        assert result["containers_released"] == 1
        assert result["containers_total"] == 2

    def test_declaration_from_deal(self):
        deal = _mock_deal({"customs_declaration": "26014441623750"})
        cs = [_mock_container_status()]
        result = _compute_customs_status(cs, "import", deal)
        assert result["declaration"] == "26014441623750"


# ═══════════════════════════════════════════════════
#  EXPORT CUTOFFS TESTS
# ═══════════════════════════════════════════════════

class TestExportCutoffs:
    def test_no_cutoffs(self):
        deal = _mock_deal({"direction": "export"})
        result = _compute_export_cutoffs(deal)
        assert result["gate_cutoff"] == ""
        assert result["gate_cutoff_hours"] is None
        assert result["soonest_cutoff_type"] == ""

    def test_with_cutoffs(self):
        deal = _mock_deal({
            "direction": "export",
            "gate_cutoff": "2026-02-24T14:00:00Z",
            "doc_cutoff": "2026-02-24T10:00:00Z",
        })
        result = _compute_export_cutoffs(deal)
        assert result["gate_cutoff"] == "2026-02-24T14:00:00Z"
        assert result["doc_cutoff"] == "2026-02-24T10:00:00Z"
        assert result["doc_cutoff_hours"] is not None

    def test_soonest_cutoff(self):
        deal = _mock_deal({
            "gate_cutoff": "2026-02-24T14:00:00Z",
            "doc_cutoff": "2026-02-24T10:00:00Z",
        })
        result = _compute_export_cutoffs(deal)
        # doc_cutoff is sooner (10:00 < 14:00)
        assert result["soonest_cutoff_type"] == "doc_cutoff"


# ═══════════════════════════════════════════════════
#  BUILD_DEAL_INTELLIGENCE ROUTING TESTS
# ═══════════════════════════════════════════════════

class TestBuildDealIntelligence:
    def test_routes_to_sea_import(self):
        deal = _mock_deal({"direction": "import", "freight_kind": "FCL"})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "sea_import"

    def test_routes_to_sea_export(self):
        deal = _mock_deal({"direction": "export", "freight_kind": "FCL"})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "sea_export"

    def test_routes_to_air_import(self):
        deal = _mock_deal({"direction": "import", "freight_kind": "air",
                          "awb_number": "114-12345678"})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "air_import"

    def test_routes_to_air_export(self):
        deal = _mock_deal({"direction": "export", "freight_kind": "air",
                          "awb_number": "114-12345678"})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "air_export"

    def test_awb_detected_as_air(self):
        """Deal with awb_number but no freight_kind → routed as air."""
        deal = _mock_deal({"awb_number": "114-12345678", "freight_kind": ""})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "air_import"

    def test_default_is_sea_import(self):
        """Empty direction defaults to import."""
        deal = _mock_deal({"direction": "", "freight_kind": "FCL"})
        result = build_deal_intelligence(deal)
        assert result["view_type"] == "sea_import"


# ═══════════════════════════════════════════════════
#  I3: ALERT ENGINE TESTS
# ═══════════════════════════════════════════════════

class TestAlertConstants:
    def test_alert_type_values(self):
        assert ALERT_DO_MISSING == "do_missing"
        assert ALERT_PHYSICAL_EXAM == "physical_exam"
        assert ALERT_STORAGE_DAY3 == "storage_day3"


class TestCheckDoMissing:
    """D/O not received AND vessel ATA exists → alert."""

    def test_do_missing_with_ata(self):
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({
            "import_process": {
                "PortUnloadingDate": "2026-02-15T09:20:00Z",  # ATA exists
                # No DeliveryOrderDate
            }
        })]
        now = _make_now()
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        do_alerts = [a for a in alerts if a["type"] == ALERT_DO_MISSING]
        assert len(do_alerts) == 1
        assert do_alerts[0]["severity"] == "critical"

    def test_no_alert_when_do_received(self):
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({
            "import_process": {
                "PortUnloadingDate": "2026-02-15T09:20:00Z",
                "DeliveryOrderDate": "2026-02-16T10:00:00Z",
            }
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        do_alerts = [a for a in alerts if a["type"] == ALERT_DO_MISSING]
        assert len(do_alerts) == 0

    def test_no_alert_when_no_ata(self):
        """Vessel hasn't arrived → no D/O alert."""
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({"import_process": {}})]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        do_alerts = [a for a in alerts if a["type"] == ALERT_DO_MISSING]
        assert len(do_alerts) == 0

    def test_no_alert_for_export(self):
        deal = _mock_deal({"direction": "export"})
        cs = [_mock_container_status({
            "import_process": {"PortUnloadingDate": "2026-02-15T09:20:00Z"}
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        do_alerts = [a for a in alerts if a["type"] == ALERT_DO_MISSING]
        assert len(do_alerts) == 0


class TestCheckPhysicalExam:
    """CustomsCheck without release → physical exam alert."""

    def test_exam_opened(self):
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({
            "import_process": {
                "CustomsCheckDate": "2026-02-16T10:00:00Z",
                # No CustomsReleaseDate
            }
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        exam_alerts = [a for a in alerts if a["type"] == ALERT_PHYSICAL_EXAM]
        assert len(exam_alerts) == 1
        assert exam_alerts[0]["severity"] == "warning"

    def test_no_alert_when_released(self):
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({
            "import_process": {
                "CustomsCheckDate": "2026-02-16T10:00:00Z",
                "CustomsReleaseDate": "2026-02-16T14:00:00Z",
            }
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        exam_alerts = [a for a in alerts if a["type"] == ALERT_PHYSICAL_EXAM]
        assert len(exam_alerts) == 0

    def test_no_alert_when_no_check(self):
        deal = _mock_deal({"direction": "import"})
        cs = [_mock_container_status({"import_process": {}})]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        exam_alerts = [a for a in alerts if a["type"] == ALERT_PHYSICAL_EXAM]
        assert len(exam_alerts) == 0

    def test_one_alert_per_deal(self):
        """Even with 3 containers under exam, only 1 alert per deal."""
        deal = _mock_deal({"direction": "import"})
        cs = [
            _mock_container_status({"container_id": "C1", "import_process": {"CustomsCheckDate": "2026-02-16T10:00:00Z"}}),
            _mock_container_status({"container_id": "C2", "import_process": {"CustomsCheckDate": "2026-02-16T11:00:00Z"}}),
            _mock_container_status({"container_id": "C3", "import_process": {"CustomsCheckDate": "2026-02-16T12:00:00Z"}}),
        ]
        alerts = check_port_intelligence_alerts("d1", deal, cs, _make_now())
        exam_alerts = [a for a in alerts if a["type"] == ALERT_PHYSICAL_EXAM]
        assert len(exam_alerts) == 1


class TestCheckStorageDay3:
    """Storage day 3 of 4 → alert."""

    def test_storage_day3_alert(self):
        deal = _mock_deal({"direction": "import"})
        # Container arrived 3 days ago
        now = _make_now()
        entry = (now - timedelta(days=3)).isoformat()
        cs = [_mock_container_status({
            "import_process": {
                "PortUnloadingDate": entry,
                # No CargoExitDate
            }
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        storage_alerts = [a for a in alerts if a["type"] == ALERT_STORAGE_DAY3]
        assert len(storage_alerts) == 1
        assert storage_alerts[0]["severity"] == "warning"
        assert "3" in storage_alerts[0]["message_he"]

    def test_storage_day4_critical(self):
        deal = _mock_deal({"direction": "import"})
        now = _make_now()
        entry = (now - timedelta(days=4)).isoformat()
        cs = [_mock_container_status({
            "import_process": {"PortUnloadingDate": entry}
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        storage_alerts = [a for a in alerts if a["type"] == ALERT_STORAGE_DAY3]
        assert len(storage_alerts) == 1
        assert storage_alerts[0]["severity"] == "critical"

    def test_no_alert_day1(self):
        deal = _mock_deal({"direction": "import"})
        now = _make_now()
        entry = (now - timedelta(days=1)).isoformat()
        cs = [_mock_container_status({
            "import_process": {"PortUnloadingDate": entry}
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        storage_alerts = [a for a in alerts if a["type"] == ALERT_STORAGE_DAY3]
        assert len(storage_alerts) == 0

    def test_no_alert_when_exited(self):
        deal = _mock_deal({"direction": "import"})
        now = _make_now()
        entry = (now - timedelta(days=5)).isoformat()
        cs = [_mock_container_status({
            "import_process": {
                "PortUnloadingDate": entry,
                "CargoExitDate": (now - timedelta(days=1)).isoformat(),
            }
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        storage_alerts = [a for a in alerts if a["type"] == ALERT_STORAGE_DAY3]
        assert len(storage_alerts) == 0

    def test_export_storage_day3(self):
        deal = _mock_deal({"direction": "export"})
        now = _make_now()
        entry = (now - timedelta(days=3)).isoformat()
        cs = [_mock_container_status({
            "export_process": {"CargoEntryDate": entry}
        })]
        alerts = check_port_intelligence_alerts("d1", deal, cs, now)
        storage_alerts = [a for a in alerts if a["type"] == ALERT_STORAGE_DAY3]
        assert len(storage_alerts) == 1

    def test_air_cargo_no_storage_alert(self):
        """Air cargo doesn't trigger storage_day3."""
        deal = _mock_deal({"freight_kind": "air", "awb_number": "114-12345678"})
        now = _make_now()
        alerts = check_port_intelligence_alerts("d1", deal, [], now)
        assert len(alerts) == 0


class TestCheckAlertsEmpty:
    def test_no_containers(self):
        deal = _mock_deal({"direction": "import"})
        alerts = check_port_intelligence_alerts("d1", deal, [], _make_now())
        assert alerts == []

    def test_no_deal_data(self):
        deal = _mock_deal({"direction": "import", "vessel_name": "", "bol_number": ""})
        alerts = check_port_intelligence_alerts("d1", deal, [], _make_now())
        assert alerts == []


class TestBuildPortAlertSubject:
    def test_do_missing_subject(self):
        alert = {
            "type": ALERT_DO_MISSING,
            "severity": "critical",
            "deal_id": "d1",
            "details": {"container_id": "OOLU1234", "vessel_name": "MSC ANNA", "bol_number": ""},
        }
        subject = build_port_alert_subject(alert)
        assert "🚨" in subject
        assert "D/O" in subject
        assert "OOLU1234" in subject

    def test_exam_subject(self):
        alert = {
            "type": ALERT_PHYSICAL_EXAM,
            "severity": "warning",
            "deal_id": "d1",
            "details": {"container_id": "CMAU5678", "vessel_name": "ZIM HAIFA"},
        }
        subject = build_port_alert_subject(alert)
        assert "⚡" in subject
        assert "בדיקה" in subject

    def test_storage_subject(self):
        alert = {
            "type": ALERT_STORAGE_DAY3,
            "severity": "warning",
            "deal_id": "d1",
            "details": {"container_id": "MEDU1111", "vessel_name": "ITAL WIT", "days_at_port": 3},
        }
        subject = build_port_alert_subject(alert)
        assert "אחסנה" in subject
        assert "3" in subject


class TestBuildPortAlertHtml:
    def test_critical_alert_html(self):
        alert = {
            "type": ALERT_DO_MISSING,
            "severity": "critical",
            "message_he": "D/O טרם התקבל",
            "message_en": "D/O not received",
            "details": {
                "vessel_name": "MSC ANNA",
                "bol_number": "MEDURS12345",
                "container_id": "OOLU1234",
                "port_code": "ILHFA",
            },
        }
        html = build_port_alert_html(alert)
        assert "RCB" in html
        assert "D/O טרם התקבל" in html
        assert "MSC ANNA" in html
        assert "#ef233c" in html  # critical border color

    def test_warning_alert_html(self):
        alert = {
            "type": ALERT_PHYSICAL_EXAM,
            "severity": "warning",
            "message_he": "בדיקה פיזית",
            "message_en": "Physical exam",
            "details": {"vessel_name": "ZIM", "bol_number": "BL1", "container_id": "C1", "port_code": "ILASD"},
        }
        html = build_port_alert_html(alert)
        assert "#f77f00" in html  # warning border color


# ═══════════════════════════════════════════════════
#  I4: MORNING DIGEST TESTS
# ═══════════════════════════════════════════════════

class TestDigestConstants:
    def test_four_sea_ports(self):
        assert len(DIGEST_SEA_PORTS) == 4
        codes = [p["code"] for p in DIGEST_SEA_PORTS]
        assert "ILHFA" in codes
        assert "ILASD" in codes

    def test_port_has_required_fields(self):
        for p in DIGEST_SEA_PORTS:
            assert "code" in p
            assert "name_he" in p
            assert "capacity" in p
            assert "gate_hours" in p


class TestDigestHeader:
    def test_header_contains_date(self):
        now = datetime(2026, 2, 18, 7, 0, 0, tzinfo=timezone.utc)
        html = _digest_header(now)
        assert "18.02.2026" in html
        assert "07:00" in html
        assert "RCB" in html

    def test_header_contains_recipient(self):
        now = _make_now()
        html = _digest_header(now)
        assert "cc@rpa-port.co.il" in html


class TestDigestSummaryBar:
    def test_summary_counts(self):
        html = _digest_summary_bar(2, 3, 8)
        assert "<strong>2</strong>" in html
        assert "<strong>3</strong>" in html
        assert "<strong>8</strong>" in html
        assert "דחוף" in html
        assert "אזהרה" in html

    def test_zero_counts(self):
        html = _digest_summary_bar(0, 0, 0)
        assert "<strong>0</strong>" in html


class TestDigestFooter:
    def test_footer_contains_branding(self):
        now = _make_now()
        html = _digest_footer(now)
        assert "RCB" in html
        assert "R.P.A. PORT LTD" in html
        assert "cc@rpa-port.co.il" in html


class TestDigestPortStatus:
    def test_port_status_four_ports(self):
        reports = {
            "ILHFA": {"total_vessels": 18, "vessels_waiting": 3},
            "ILASD": {"total_vessels": 11, "vessels_waiting": 1},
        }
        html = _digest_port_status(reports)
        assert "נמל חיפה" in html
        assert "נמל אשדוד" in html
        assert "נמל המפרץ" in html
        assert "נמל הדרום" in html

    def test_port_congestion_chip(self):
        reports = {"ILHFA": {"total_vessels": 28}}
        html = _digest_port_status(reports)
        assert "עמוס" in html


class TestDigestPortCard:
    def test_normal_port(self):
        port_info = {"code": "ILASD", "name_he": "נמל אשדוד", "capacity": 25, "gate_hours": "06:00–20:00"}
        html = _digest_port_card(port_info, {"total_vessels": 10})
        assert "10 / 25" in html
        assert "תקין" in html

    def test_busy_port(self):
        port_info = {"code": "ILHFA", "name_he": "נמל חיפה", "capacity": 25, "gate_hours": "06:00–22:00"}
        html = _digest_port_card(port_info, {"total_vessels": 20})
        assert "עמוס" in html

    def test_empty_report(self):
        port_info = {"code": "ILKRN", "name_he": "נמל המפרץ", "capacity": 15, "gate_hours": "06:00–22:00"}
        html = _digest_port_card(port_info, {})
        assert "0 / 15" in html


class TestRenderMorningDigest:
    def test_empty_deals(self):
        html = render_morning_digest_html([], {}, _make_now())
        assert "RCB" in html
        assert "אין משלוחים פעילים כיום" in html

    def test_single_sea_import_deal(self):
        now = _make_now()
        dd = {
            "deal_id": "d1",
            "deal": _mock_deal({"direction": "import", "freight_kind": "FCL"}),
            "container_statuses": [_mock_container_status()],
            "awb_status": None,
            "schedule_link": None,
            "alerts": [],
        }
        html = render_morning_digest_html([dd], {}, now)
        assert "ייבוא ים" in html
        assert "ZIM SHANGHAI" in html
        assert "ZIMLNS1234567" in html

    def test_sea_export_deal(self):
        now = _make_now()
        dd = {
            "deal_id": "d2",
            "deal": _mock_deal({"direction": "export", "freight_kind": "FCL", "booking_number": "BK123"}),
            "container_statuses": [],
            "awb_status": None,
            "schedule_link": None,
            "alerts": [],
        }
        html = render_morning_digest_html([dd], {}, now)
        assert "יצוא ים" in html
        assert "BK123" in html

    def test_air_import_deal(self):
        now = _make_now()
        dd = {
            "deal_id": "d3",
            "deal": _mock_deal({
                "freight_kind": "air", "awb_number": "114-87654321",
                "direction": "import", "carrier_name": "EL AL",
            }),
            "container_statuses": [],
            "awb_status": {"awb_number": "114-87654321", "status_normalized": "in_transit"},
            "schedule_link": None,
            "alerts": [],
        }
        html = render_morning_digest_html([dd], {}, now)
        assert "ייבוא אוויר" in html
        assert "114-87654321" in html

    def test_digest_has_all_sections(self):
        now = _make_now()
        html = render_morning_digest_html([], {"ILHFA": {"total_vessels": 12}}, now)
        # Header + Summary + Port Status + Footer always present
        assert "דוח בוקר" in html
        assert "סטטוס נמלים" in html
        assert "R.P.A. PORT LTD" in html

    def test_digest_with_alerts(self):
        now = _make_now()
        entry = (now - timedelta(days=3)).isoformat()
        dd = {
            "deal_id": "d1",
            "deal": _mock_deal({"direction": "import"}),
            "container_statuses": [_mock_container_status({
                "import_process": {
                    "PortUnloadingDate": entry,
                }
            })],
            "awb_status": None,
            "schedule_link": None,
            "alerts": [{
                "type": ALERT_STORAGE_DAY3,
                "deal_id": "d1",
                "severity": "warning",
                "message_he": "יום אחסנה 3 מתוך 4",
                "message_en": "Storage day 3 of 4",
                "details": {"container_id": "TEST1234", "vessel_name": "ZIM", "days_at_port": 3},
            }],
        }
        html = render_morning_digest_html([dd], {}, now)
        assert "אזהרה" in html

    def test_digest_css_included(self):
        html = render_morning_digest_html([], {}, _make_now())
        # Key CSS classes from v4 template
        assert ".ew{" in html
        assert ".hdr{" in html
        assert ".sbar{" in html
        assert ".pt{" in html
