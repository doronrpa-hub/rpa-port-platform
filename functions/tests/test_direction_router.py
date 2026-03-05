"""Tests for direction_router.py — import/export/transit detection."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.direction_router import detect_direction, get_direction_config


class TestImportDetection:
    def test_hebrew_import_keyword(self):
        r = detect_direction("חשבונית יבוא", "")
        assert r["direction"] == "import"
        assert r["confidence"] > 0.5

    def test_english_import_keyword(self):
        r = detect_direction("Import Invoice", "shipment importing goods")
        assert r["direction"] == "import"

    def test_cif_haifa_incoterm(self):
        r = detect_direction("", "Terms: CIF Haifa, USD 42,500")
        assert r["direction"] == "import"

    def test_pod_israel(self):
        r = detect_direction("", "POD: Ashdod, Israel. POL: Shanghai, China")
        assert r["direction"] == "import"

    def test_fio_mention(self):
        r = detect_direction("", "בהתאם לצו יבוא חופשי נדרש אישור")
        assert r["direction"] == "import"

    def test_hebrew_release_keyword(self):
        r = detect_direction("שחרור מהמכס", "")
        assert r["direction"] == "import"

    def test_hebrew_rishimon_import(self):
        r = detect_direction("", "הוגש רשימון יבוא")
        assert r["direction"] == "import"


class TestExportDetection:
    def test_hebrew_export_keyword(self):
        r = detect_direction("יצוא לאירופה", "")
        assert r["direction"] == "export"
        assert r["confidence"] > 0.5

    def test_english_export_keyword(self):
        r = detect_direction("Export Declaration", "exporting electronics")
        assert r["direction"] == "export"

    def test_fob_israel_incoterm(self):
        r = detect_direction("", "Terms: FOB Haifa")
        assert r["direction"] == "export"

    def test_pol_israel(self):
        r = detect_direction("", "POL: Haifa. POD: Rotterdam")
        assert r["direction"] == "export"

    def test_approved_exporter_mention(self):
        r = detect_direction("", "בדיקת יצואן מאושר למשלוח")
        assert r["direction"] == "export"

    def test_feo_mention(self):
        r = detect_direction("", "צו יצוא חופשי")
        assert r["direction"] == "export"


class TestTransitDetection:
    def test_hebrew_transit(self):
        r = detect_direction("טרנזיט דרך חיפה", "")
        assert r["direction"] == "transit"

    def test_english_transit(self):
        r = detect_direction("", "transit shipment in bond")
        assert r["direction"] == "transit"


class TestDealDataOverride:
    def test_deal_data_import(self):
        r = detect_direction("יצוא", "exporting", deal_data={"direction": "import"})
        assert r["direction"] == "import"
        assert r["confidence"] == 1.0

    def test_deal_data_export(self):
        r = detect_direction("יבוא", "importing", deal_data={"direction": "export"})
        assert r["direction"] == "export"

    def test_deal_data_empty_falls_through(self):
        r = detect_direction("יבוא", "", deal_data={"direction": ""})
        assert r["direction"] == "import"  # Falls through to keyword detection

    def test_deal_data_none_falls_through(self):
        r = detect_direction("יבוא", "", deal_data=None)
        assert r["direction"] == "import"


class TestUnknownDirection:
    def test_empty_input(self):
        r = detect_direction("", "")
        assert r["direction"] == "unknown"
        assert r["confidence"] == 0.0

    def test_no_direction_keywords(self):
        r = detect_direction("שלום", "מה שלומך?")
        assert r["direction"] == "unknown"

    def test_general_customs_question(self):
        r = detect_direction("", "מה המכס על פלסטיק?")
        assert r["direction"] == "unknown"


class TestAmbiguousDirection:
    def test_both_import_and_export_mentioned(self):
        r = detect_direction("", "יבוא ויצוא של טובין")
        # Both detected — confidence should be reduced
        assert r["confidence"] < 0.7

    def test_signals_list_populated(self):
        r = detect_direction("יבוא CIF Haifa", "")
        assert len(r["signals"]) >= 1
        assert any(s[1] == "import" for s in r["signals"])


class TestDirectionConfig:
    def test_import_config(self):
        cfg = get_direction_config("import")
        assert cfg["tariff_type"] == "import"
        assert cfg["decree_collection"] == "free_import_order"
        assert cfg["decree_name_he"] == "צו יבוא חופשי"
        assert 132 in cfg["valuation_articles"]
        assert 62 in cfg["release_articles"]
        assert "1" in cfg["procedures"]
        assert cfg["check_approved_exporter"] is False

    def test_export_config(self):
        cfg = get_direction_config("export")
        assert cfg["tariff_type"] == "export"
        assert cfg["decree_collection"] == "free_export_order"
        assert cfg["decree_name_he"] == "צו יצוא חופשי"
        assert cfg["valuation_articles"] == []
        assert cfg["check_approved_exporter"] is True
        assert "approved_exporter" in cfg["procedures"]

    def test_unknown_defaults_to_import(self):
        cfg = get_direction_config("unknown")
        assert cfg["tariff_type"] == "import"
        assert 132 in cfg["valuation_articles"]

    def test_transit_config(self):
        cfg = get_direction_config("transit")
        assert cfg["valuation_articles"] == []
        assert cfg["procedures"] == []

    def test_config_returns_copy(self):
        cfg1 = get_direction_config("import")
        cfg2 = get_direction_config("import")
        cfg1["tariff_type"] = "modified"
        assert cfg2["tariff_type"] == "import"

    def test_invalid_direction_defaults(self):
        cfg = get_direction_config("garbage")
        assert cfg["tariff_type"] == "import"
