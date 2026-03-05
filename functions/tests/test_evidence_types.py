"""Tests for evidence_types.py — EvidenceBundle + build_evidence_bundle."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from lib.evidence_types import EvidencePiece, EvidenceBundle, build_evidence_bundle


# ---------------------------------------------------------------------------
#  Helpers — minimal fakes
# ---------------------------------------------------------------------------

class FakeContextPackage:
    """Minimal stand-in for context_engine.ContextPackage."""
    def __init__(self, **kwargs):
        self.domain = kwargs.get("domain", "customs")
        self.original_subject = kwargs.get("original_subject", "test subject")
        self.original_body = kwargs.get("original_body", "test body")
        self.detected_language = kwargs.get("detected_language", "he")
        self.entities = kwargs.get("entities", {})
        self.search_log = kwargs.get("search_log", [])
        self.ordinance_articles = kwargs.get("ordinance_articles", [])
        self.framework_articles = kwargs.get("framework_articles", [])
        self.tariff_results = kwargs.get("tariff_results", [])
        self.regulatory_results = kwargs.get("regulatory_results", [])
        self.xml_results = kwargs.get("xml_results", [])
        self.wikipedia_results = kwargs.get("wikipedia_results", [])
        self.other_tool_results = kwargs.get("other_tool_results", [])


def _dir_result(direction="import", confidence=0.9):
    return {"direction": direction, "confidence": confidence, "signals": []}


# ---------------------------------------------------------------------------
#  EvidencePiece
# ---------------------------------------------------------------------------

class TestEvidencePiece:
    def test_basic_creation(self):
        ep = EvidencePiece(
            fact="VAT is 18%",
            source_name="פקודת המכס",
            source_ref="סעיף 130",
            source_type="ordinance",
        )
        assert ep.fact == "VAT is 18%"
        assert ep.confidence == 1.0

    def test_custom_confidence(self):
        ep = EvidencePiece(fact="x", source_name="y", source_ref="z",
                           source_type="web", confidence=0.7)
        assert ep.confidence == 0.7


# ---------------------------------------------------------------------------
#  EvidenceBundle — data structure
# ---------------------------------------------------------------------------

class TestEvidenceBundleDefaults:
    def test_empty_bundle(self):
        b = EvidenceBundle()
        assert b.direction == "unknown"
        assert b.tariff_entries == []
        assert b.ordinance_articles == []
        assert b.sources_found == []
        assert b.sources_not_found == []

    def test_has_tariff_data_false(self):
        b = EvidenceBundle()
        assert b.has_tariff_data() is False

    def test_has_tariff_data_true(self):
        b = EvidenceBundle(tariff_entries=[{"hs_code": "1234"}])
        assert b.has_tariff_data() is True

    def test_has_regulatory_data(self):
        b = EvidenceBundle()
        assert b.has_regulatory_data() is False
        b.regulatory_requirements.append({"authority": "MOH"})
        assert b.has_regulatory_data() is True

    def test_has_fta_data_none(self):
        b = EvidenceBundle()
        assert b.has_fta_data() is False

    def test_has_fta_data_not_applicable(self):
        b = EvidenceBundle(fta_data={"applicable": False})
        assert b.has_fta_data() is False

    def test_has_fta_data_applicable(self):
        b = EvidenceBundle(fta_data={"applicable": True})
        assert b.has_fta_data() is True

    def test_has_web_data(self):
        b = EvidenceBundle()
        assert b.has_web_data() is False
        b.web_results.append({"title": "test"})
        assert b.has_web_data() is True

    def test_has_valuation_data(self):
        b = EvidenceBundle()
        assert b.has_valuation_data() is False


# ---------------------------------------------------------------------------
#  build_evidence_bundle — basic
# ---------------------------------------------------------------------------

class TestBuildEvidenceBundle:
    def test_minimal_empty(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result())
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.direction == "import"
        assert bundle.domain == "customs"
        assert bundle.original_subject == "test subject"

    def test_direction_export(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("export"))
        assert bundle.direction == "export"
        assert bundle.direction_config["tariff_type"] == "export"
        assert bundle.direction_config["decree_name_he"] == "צו יצוא חופשי"

    def test_direction_unknown_defaults_import(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("unknown"))
        assert bundle.direction == "unknown"
        assert bundle.direction_config["tariff_type"] == "import"

    def test_confidence_propagated(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("import", 0.75))
        assert bundle.direction_confidence == 0.75

    def test_entities_propagated(self):
        cp = FakeContextPackage(entities={"hs_codes": ["3901"]})
        bundle = build_evidence_bundle(cp, _dir_result())
        assert bundle.entities == {"hs_codes": ["3901"]}

    def test_search_log_copied(self):
        cp = FakeContextPackage(search_log=["searched tariff"])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert "searched tariff" in bundle.search_log
        # Must be a copy, not same reference
        cp.search_log.append("extra")
        assert "extra" not in bundle.search_log


# ---------------------------------------------------------------------------
#  Tagger: ordinance articles
# ---------------------------------------------------------------------------

class TestTagOrdinanceArticles:
    def test_ordinance_tagged(self):
        cp = FakeContextPackage(ordinance_articles=[
            {"article_id": "132", "title_he": "ערך עסקה", "summary_en": "Transaction value",
             "full_text_he": "הערך לצרכי מכס...", "chapter": 8},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.ordinance_articles) == 1
        art = bundle.ordinance_articles[0]
        assert art["source_name"] == "פקודת המכס"
        assert "132" in art["source_ref"]
        assert art["full_text_he"] == "הערך לצרכי מכס..."

    def test_regulations_source(self):
        cp = FakeContextPackage(ordinance_articles=[
            {"article_id": "5", "title_he": "תקנות סיווג", "source": "regulations"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        art = bundle.ordinance_articles[0]
        assert art["source_name"] == "תקנות סיווג"

    def test_empty_ordinance(self):
        cp = FakeContextPackage(ordinance_articles=None)
        bundle = build_evidence_bundle(cp, _dir_result())
        assert bundle.ordinance_articles == []


# ---------------------------------------------------------------------------
#  Tagger: tariff results
# ---------------------------------------------------------------------------

class TestTagTariffResults:
    def test_tariff_tagged(self):
        cp = FakeContextPackage(tariff_results=[
            {"hs_code": "3901100000", "description_he": "פוליאתילן",
             "duty": "5%", "purchase_tax": "0%"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.tariff_entries) == 1
        entry = bundle.tariff_entries[0]
        assert entry["source_name"] == "תעריף המכס"
        assert entry["source_ref"] == "פרט 3901100000"
        assert entry["vat"] == "18%"  # default

    def test_tariff_customs_rate_fallback(self):
        cp = FakeContextPackage(tariff_results=[
            {"hs_code": "8507", "customs_rate": "12%"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert bundle.tariff_entries[0]["duty"] == "12%"


# ---------------------------------------------------------------------------
#  Tagger: regulatory results
# ---------------------------------------------------------------------------

class TestTagRegulatoryResults:
    def test_fio_requirements(self):
        cp = FakeContextPackage(regulatory_results=[
            {"data": {
                "hs_code": "4011",
                "requirements": [
                    {"supplement": "תוספת 2", "authority": "משרד התחבורה",
                     "requirement": "אישור MOT", "standard": "SI 1022"},
                ],
            }},
        ])
        bundle = build_evidence_bundle(cp, _dir_result("import"))
        assert len(bundle.regulatory_requirements) == 1
        req = bundle.regulatory_requirements[0]
        assert req["authority"] == "משרד התחבורה"
        assert req["source_name"] == "צו יבוא חופשי"

    def test_feo_decree_name(self):
        cp = FakeContextPackage(regulatory_results=[
            {"data": {
                "hs_code": "4011",
                "requirements": [
                    {"supplement": "תוספת 3", "authority": "MOD",
                     "requirement": "export license"},
                ],
            }},
        ])
        bundle = build_evidence_bundle(cp, _dir_result("export"))
        req = bundle.regulatory_requirements[0]
        assert req["source_name"] == "צו יצוא חופשי"

    def test_authorities_summary_fallback(self):
        cp = FakeContextPackage(regulatory_results=[
            {"data": {
                "hs_code": "1234",
                "authorities_summary": ["MOH", "SII"],
            }},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.regulatory_requirements) == 2

    def test_empty_regulatory(self):
        cp = FakeContextPackage(regulatory_results=None)
        bundle = build_evidence_bundle(cp, _dir_result())
        assert bundle.regulatory_requirements == []


# ---------------------------------------------------------------------------
#  Tagger: web/wikipedia results
# ---------------------------------------------------------------------------

class TestTagWebResults:
    def test_wikipedia_tagged(self):
        cp = FakeContextPackage(wikipedia_results=[
            {"title": "Polyethylene", "extract": "PE is a polymer...",
             "url": "https://en.wikipedia.org/wiki/Polyethylene"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.web_results) == 1
        w = bundle.web_results[0]
        assert "Wikipedia" in w["source_name"]
        assert w["source_url"] == "https://en.wikipedia.org/wiki/Polyethylene"

    def test_wikipedia_text_truncated(self):
        cp = FakeContextPackage(wikipedia_results=[
            {"title": "X", "extract": "A" * 5000},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.web_results[0]["text"]) <= 2000


# ---------------------------------------------------------------------------
#  Tagger: other results (directives, FTA, supplier)
# ---------------------------------------------------------------------------

class TestTagOtherResults:
    def test_supplier_website(self):
        cp = FakeContextPackage(other_tool_results=[
            {"_tool_name": "fetch_seller_website",
             "url": "https://example.com", "content": "Products: tires"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.supplier_results) == 1
        assert bundle.supplier_results[0]["source_name"] == "supplier_website"

    def test_classification_directives(self):
        cp = FakeContextPackage(other_tool_results=[
            {"_tool_name": "search_classification_directives",
             "directives": [
                 {"directive_id": "D-2024-001", "title": "Tire classification",
                  "primary_hs_code": "4011", "content": "Tires are classified..."},
             ]},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.directives) == 1
        d = bundle.directives[0]
        assert d["source_name"] == "הנחיית סיווג"
        assert "D-2024-001" in d["source_ref"]

    def test_fta_lookup(self):
        cp = FakeContextPackage(other_tool_results=[
            {"_tool_name": "lookup_fta", "applicable": True,
             "country": "EU", "origin_rules": "CTH",
             "declaration_type": "EUR.1",
             "preferential_rate": "0%",
             "agreement_name": "EU-Israel FTA"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert bundle.fta_data is not None
        assert bundle.fta_data["applicable"] is True
        assert bundle.fta_data["country"] == "EU"
        assert "EU" in bundle.fta_data["source_name"]


# ---------------------------------------------------------------------------
#  Tagger: XML results
# ---------------------------------------------------------------------------

class TestTagXmlResults:
    def test_xml_tagged(self):
        cp = FakeContextPackage(xml_results=[
            {"title": "EU Reform", "content": "Important reform text...",
             "doc_type": "reform"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.xml_results) == 1
        assert bundle.xml_results[0]["source_name"] == "EU Reform"

    def test_xml_content_truncated(self):
        cp = FakeContextPackage(xml_results=[
            {"title": "Big doc", "content": "X" * 5000},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.xml_results[0]["content"]) <= 2000


# ---------------------------------------------------------------------------
#  Framework articles
# ---------------------------------------------------------------------------

class TestTagFrameworkArticles:
    def test_framework_tagged(self):
        cp = FakeContextPackage(framework_articles=[
            {"article_id": "5", "title_he": "הגדרת ערך",
             "full_text_he": "ערך לצרכי מכס הוא..."},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.framework_articles) == 1
        fa = bundle.framework_articles[0]
        assert fa["source_name"] == "צו מסגרת"
        assert "5" in fa["source_ref"]

    def test_framework_compact_keys(self):
        """Handle compact keys (t, f) from _framework_order_data.py."""
        cp = FakeContextPackage(framework_articles=[
            {"article_id": "10", "t": "הגדרה", "f": "הטקסט המלא"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        fa = bundle.framework_articles[0]
        assert fa["title_he"] == "הגדרה"
        assert fa["text"] == "הטקסט המלא"


# ---------------------------------------------------------------------------
#  Source audit
# ---------------------------------------------------------------------------

class TestSourceAudit:
    def test_empty_bundle_all_not_found(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result())
        assert len(bundle.sources_not_found) > 0
        assert "פקודת המכס" in bundle.sources_not_found
        assert "תעריף המכס" in bundle.sources_not_found

    def test_tariff_in_sources_found(self):
        cp = FakeContextPackage(tariff_results=[
            {"hs_code": "1234", "description_he": "test"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert "תעריף המכס" in bundle.sources_found
        assert "תעריף המכס" not in bundle.sources_not_found

    def test_fta_in_sources(self):
        cp = FakeContextPackage(other_tool_results=[
            {"_tool_name": "lookup_fta", "applicable": True, "country": "UK"},
        ])
        bundle = build_evidence_bundle(cp, _dir_result())
        assert "הסכמי סחר" in bundle.sources_found

    def test_no_fta_in_not_found(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result())
        assert "הסכמי סחר" in bundle.sources_not_found


# ---------------------------------------------------------------------------
#  Direction-specific enrichment
# ---------------------------------------------------------------------------

class TestDirectionEnrichment:
    def test_import_has_valuation_articles(self):
        """Import direction should attempt to add valuation articles 130-133."""
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("import"))
        # Whether articles are found depends on _ordinance_data import
        # but the enrichment should run without error
        assert bundle.direction == "import"
        assert bundle.direction_config.get("valuation_articles") == [130, 131, 132, 133]

    def test_export_no_valuation(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("export"))
        assert bundle.direction_config.get("valuation_articles") == []

    def test_transit_no_enrichment(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("transit"))
        assert bundle.direction_config.get("valuation_articles") == []
        assert bundle.direction_config.get("procedures") == []

    def test_import_release_articles(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("import"))
        assert bundle.direction_config.get("release_articles") == [62, 63]

    def test_export_approved_exporter(self):
        cp = FakeContextPackage()
        bundle = build_evidence_bundle(cp, _dir_result("export"))
        assert bundle.direction_config.get("check_approved_exporter") is True
        assert "approved_exporter" in bundle.direction_config.get("procedures", [])
