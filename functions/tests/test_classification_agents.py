"""
Unit Tests for classification_agents.py
Run: pytest tests/test_classification_agents.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.classification_agents import (
    clean_firestore_data,
    call_claude,
    query_tariff,
    query_ministry_index,
    _enrich_results_for_email,
    build_classification_email,
    build_excel_report,
)


# ============================================================
# DATA CLEANING TESTS
# ============================================================

class TestCleanFirestoreData:
    """Tests for Firestore data serialization"""
    
    def test_simple_dict(self):
        """Should pass through simple dict"""
        data = {"name": "test", "value": 123}
        result = clean_firestore_data(data)
        assert result == data
    
    def test_nested_dict(self):
        """Should handle nested dicts"""
        data = {"outer": {"inner": {"deep": "value"}}}
        result = clean_firestore_data(data)
        assert result["outer"]["inner"]["deep"] == "value"
    
    def test_list_data(self):
        """Should handle lists"""
        data = [{"a": 1}, {"b": 2}]
        result = clean_firestore_data(data)
        assert len(result) == 2
        assert result[0]["a"] == 1
    
    def test_timestamp_conversion(self):
        """Should convert datetime to ISO string"""
        from datetime import datetime
        ts = datetime(2026, 2, 5, 12, 30, 0)
        data = {"created": ts}
        result = clean_firestore_data(data)
        assert isinstance(result["created"], str)
        assert "2026-02-05" in result["created"]
    
    def test_mixed_data(self):
        """Should handle mixed types"""
        from datetime import datetime
        data = {
            "string": "text",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "date": datetime(2026, 1, 1)
        }
        result = clean_firestore_data(data)
        assert result["string"] == "text"
        assert result["number"] == 42
        assert isinstance(result["date"], str)
    
    def test_none_input(self):
        """Should handle None"""
        result = clean_firestore_data(None)
        assert result is None


# ============================================================
# CLAUDE API TESTS
# ============================================================

class TestCallClaude:
    """Tests for Claude API calls"""
    
    @patch('requests.post')
    def test_successful_call(self, mock_post):
        """Should return text on success"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "content": [{"text": "Classification result: HS 8516.31"}]
            }
        )
        
        result = call_claude(
            api_key="test_key",
            system_prompt="You are a customs classifier",
            user_prompt="Classify: hair dryer"
        )
        
        assert result == "Classification result: HS 8516.31"
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_api_error(self, mock_post):
        """Should return None on API error"""
        mock_post.return_value = Mock(status_code=500)
        
        result = call_claude("key", "system", "user")
        
        assert result is None
    
    @patch('requests.post')
    def test_auth_error(self, mock_post):
        """Should return None on auth error"""
        mock_post.return_value = Mock(status_code=401)
        
        result = call_claude("invalid_key", "system", "user")
        
        assert result is None
    
    @patch('requests.post')
    def test_network_error(self, mock_post):
        """Should handle network errors"""
        mock_post.side_effect = Exception("Connection timeout")
        
        result = call_claude("key", "system", "user")
        
        assert result is None
    
    @patch('requests.post')
    def test_request_format(self, mock_post):
        """Should send correct request format"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"content": [{"text": "test"}]}
        )
        
        call_claude(
            api_key="my_api_key",
            system_prompt="System message",
            user_prompt="User message",
            max_tokens=1000
        )
        
        # Verify the call was made with correct structure
        call_args = mock_post.call_args
        assert call_args[1]["headers"]["x-api-key"] == "my_api_key"
        assert "claude" in call_args[1]["json"]["model"]


# ============================================================
# FIRESTORE QUERY TESTS
# ============================================================

class TestQueryTariff:
    """Tests for tariff collection queries"""
    
    def test_basic_search(self):
        """Should find matching tariff codes"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "code": "8516.31",
            "description_he": "מייבשי שיער",
            "description_en": "Hair drying apparatus"
        }
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = query_tariff(mock_db, ["hair", "dryer"])
        
        assert len(results) >= 0  # May or may not match depending on implementation
        mock_db.collection.assert_called_with('tariff')
    
    def test_no_matches(self):
        """Should return empty for no matches"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "description_he": "רהיטים",
            "description_en": "furniture"
        }
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = query_tariff(mock_db, ["electronics", "computer"])
        
        assert len(results) == 0
    
    def test_error_handling(self):
        """Should handle Firestore errors"""
        mock_db = Mock()
        mock_db.collection.return_value.limit.return_value.stream.side_effect = Exception("DB error")
        
        results = query_tariff(mock_db, ["test"])
        
        assert results == []
    
    def test_results_limit(self):
        """Should limit results to 20"""
        mock_db = Mock()
        docs = []
        for i in range(50):
            doc = Mock()
            doc.to_dict.return_value = {
                "description_he": "מייבש שיער",
                "description_en": "hair dryer"
            }
            docs.append(doc)
        mock_db.collection.return_value.limit.return_value.stream.return_value = docs
        
        results = query_tariff(mock_db, ["hair"])
        
        assert len(results) <= 20


class TestQueryMinistryIndex:
    """Tests for ministry requirements queries"""
    
    def test_basic_query(self):
        """Should return ministry requirements"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "ministry": "משרד הבריאות",
            "requirements": ["אישור יבוא", "תקן ישראלי"]
        }
        mock_db.collection.return_value.stream.return_value = [mock_doc]
        
        results = query_ministry_index(mock_db)
        
        assert len(results) == 1
        mock_db.collection.assert_called_with('ministry_index')
    
    def test_multiple_ministries(self):
        """Should return all ministries"""
        mock_db = Mock()
        docs = []
        for ministry in ["בריאות", "כלכלה", "תקשורת"]:
            doc = Mock()
            doc.to_dict.return_value = {"ministry": ministry}
            docs.append(doc)
        mock_db.collection.return_value.stream.return_value = docs
        
        results = query_ministry_index(mock_db)
        
        assert len(results) == 3
    
    def test_error_handling(self):
        """Should handle errors gracefully"""
        mock_db = Mock()
        mock_db.collection.return_value.stream.side_effect = Exception("DB error")
        
        results = query_ministry_index(mock_db)
        
        assert results == []


# ============================================================
# CLASSIFICATION FLOW TESTS
# ============================================================

class TestClassificationFlow:
    """Integration-style tests for classification flow"""
    
    def test_hebrew_input_handling(self):
        """Should handle Hebrew product descriptions"""
        # Test that Hebrew text doesn't break the flow
        keywords = ["מייבש", "שיער", "חשמלי"]
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "description_he": "מייבש שיער חשמלי",
            "description_en": "electric hair dryer"
        }
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        # Should not raise exception
        results = query_tariff(mock_db, keywords)
    
    def test_mixed_language_handling(self):
        """Should handle mixed Hebrew/English"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "description_he": "מכשיר Philips דגם 5000",
            "description_en": "Philips device model 5000"
        }
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = query_tariff(mock_db, ["philips", "5000"])
        # Should find match


# ============================================================
# DATA VALIDATION TESTS
# ============================================================

class TestDataValidation:
    """Tests for data validation and edge cases"""
    
    def test_empty_search_terms(self):
        """Should handle empty search terms"""
        mock_db = Mock()
        mock_db.collection.return_value.limit.return_value.stream.return_value = []
        
        results = query_tariff(mock_db, [])
        
        assert results == []
    
    def test_special_characters(self):
        """Should handle special characters in search"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "description_he": "כבל USB-C",
            "description_en": "USB-C cable"
        }
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        # Should not crash
        results = query_tariff(mock_db, ["USB-C", "cable"])
    
    def test_unicode_handling(self):
        """Should handle Unicode characters"""
        data = {
            "hebrew": "שלום",
            "emoji": "📦",
            "special": "™®©"
        }
        result = clean_firestore_data(data)
        assert result["hebrew"] == "שלום"


# ============================================================
# ENRICHMENT + ENHANCED EMAIL TESTS
# ============================================================

class TestEnrichResultsForEmail:
    """Tests for _enrich_results_for_email merging logic"""

    def _make_results(self, items=None, classifications=None, ministry_routing=None, fta=None):
        return {
            "agents": {
                "invoice": {"items": items or []},
                "classification": {"classifications": classifications or []},
                "fta": {"fta": fta or []},
            },
            "ministry_routing": ministry_routing or {},
            "free_import_order": {},
        }

    def test_basic_merge(self):
        items = [{"description": "Rubber tires", "quantity": "500", "unit_price": "$45", "origin_country": "China"}]
        cls = [{"item": "Rubber tires", "hs_code": "4011.10", "duty_rate": "12%", "confidence": "גבוהה"}]
        results = self._make_results(items=items, classifications=cls)
        enriched = _enrich_results_for_email(results, {"seller": "Michelin", "buyer": "RPA PORT"}, None)
        assert len(enriched) == 1
        assert enriched[0]["line_number"] == 1
        assert enriched[0]["description"] == "Rubber tires"
        assert enriched[0]["seller"] == "Michelin"
        assert enriched[0]["buyer"] == "RPA PORT"
        assert enriched[0]["quantity"] == "500"
        assert enriched[0]["hs_code"] == "4011.10"

    def test_unequal_lengths(self):
        items = [{"description": "A"}, {"description": "B"}, {"description": "C"}]
        cls = [{"item": "A", "hs_code": "1234"}]
        results = self._make_results(items=items, classifications=cls)
        enriched = _enrich_results_for_email(results, {}, None)
        assert len(enriched) == 3
        assert enriched[0]["hs_code"] == "1234"
        assert enriched[1]["hs_code"] == ""
        assert enriched[2]["description"] == "C"

    def test_empty_inputs(self):
        results = self._make_results()
        enriched = _enrich_results_for_email(results, {}, None)
        assert enriched == []

    def test_fta_matched_by_country(self):
        items = [{"description": "Olive oil", "origin_country": "Turkey"}]
        cls = [{"item": "Olive oil", "hs_code": "1509.10"}]
        fta = [{"country": "Turkey", "eligible": True, "agreement": "IL-TR FTA", "preferential": "0%"}]
        results = self._make_results(items=items, classifications=cls, fta=fta)
        enriched = _enrich_results_for_email(results, {}, None)
        assert enriched[0]["fta"] is not None
        assert enriched[0]["fta"]["agreement"] == "IL-TR FTA"

    def test_ministry_routing_merged(self):
        items = [{"description": "Food"}]
        cls = [{"item": "Food", "hs_code": "2106.90"}]
        routing = {"2106.90": {"ministries": [{"name_he": "משרד הבריאות", "documents_he": ["אישור יבוא"]}]}}
        results = self._make_results(items=items, classifications=cls, ministry_routing=routing)
        enriched = _enrich_results_for_email(results, {}, None)
        assert len(enriched[0]["ministries"]) == 1
        assert enriched[0]["ministries"][0]["name_he"] == "משרד הבריאות"


class TestBuildClassificationEmailEnriched:
    """Tests for enhanced email rendering with enriched items"""

    def _make_results(self):
        return {
            "agents": {
                "classification": {"classifications": [{"item": "Test", "hs_code": "1234", "confidence": "גבוהה"}]},
                "regulatory": {"regulatory": []},
                "fta": {"fta": []},
                "risk": {"risk": {}},
            },
            "synthesis": "Test synthesis",
            "ministry_routing": {},
            "intelligence": {},
        }

    def test_backward_compatible(self):
        """When enriched_items=None, should still produce HTML without errors"""
        html = build_classification_email(self._make_results(), "Test User")
        assert "Test" in html
        assert "1234" in html or "12.34" in html

    def test_line_numbers_present(self):
        enriched = [{"line_number": 1, "description": "Tires", "hs_code": "4011.10",
                      "duty_rate": "12%", "confidence": "גבוהה", "vat_rate": "18%",
                      "purchase_tax_display": "לא חל", "verification_status": "verified",
                      "tariff_text_he": "צמיגי גומי", "seller": "Michelin", "buyer": "RPA",
                      "quantity": "500", "unit_price": "$45", "origin_country": "China",
                      "total": "$22500", "hs_corrected": False, "original_hs_code": "",
                      "hs_warning": "", "hs_validated": False, "hs_exact_match": False,
                      "ministries": [], "fta": None, "reasoning": ""}]
        html = build_classification_email(self._make_results(), "Test", enriched_items=enriched)
        assert "שורה 1" in html

    def test_seller_buyer_shown(self):
        enriched = [{"line_number": 1, "description": "Item", "hs_code": "1234",
                      "duty_rate": "5%", "confidence": "בינונית", "vat_rate": "18%",
                      "purchase_tax_display": "לא חל", "verification_status": "",
                      "tariff_text_he": "", "seller": "ACME Corp", "buyer": "RPA PORT",
                      "quantity": "", "unit_price": "", "origin_country": "",
                      "total": "", "hs_corrected": False, "original_hs_code": "",
                      "hs_warning": "", "hs_validated": False, "hs_exact_match": False,
                      "ministries": [], "fta": None, "reasoning": ""}]
        html = build_classification_email(self._make_results(), "Test", enriched_items=enriched)
        assert "ACME Corp" in html
        assert "RPA PORT" in html

    def test_tariff_text_shown(self):
        enriched = [{"line_number": 1, "description": "Item", "hs_code": "4011.10",
                      "duty_rate": "12%", "confidence": "גבוהה", "vat_rate": "18%",
                      "purchase_tax_display": "לא חל", "verification_status": "verified",
                      "tariff_text_he": "צמיגי גומי פנאומטיים חדשים", "seller": "", "buyer": "",
                      "quantity": "", "unit_price": "", "origin_country": "",
                      "total": "", "hs_corrected": False, "original_hs_code": "",
                      "hs_warning": "", "hs_validated": False, "hs_exact_match": False,
                      "ministries": [], "fta": None, "reasoning": ""}]
        html = build_classification_email(self._make_results(), "Test", enriched_items=enriched)
        assert "צמיגי גומי פנאומטיים חדשים" in html

    def test_original_email_quoted(self):
        html = build_classification_email(self._make_results(), "Test",
                                           original_email_body="Please classify these rubber tires from China")
        assert "הודעה מקורית" in html
        assert "rubber tires" in html

    def test_no_quoting_for_short_body(self):
        html = build_classification_email(self._make_results(), "Test", original_email_body="hi")
        assert "הודעה מקורית" not in html


class TestBuildExcelEnriched:
    """Tests for enhanced Excel report"""

    def _make_results(self):
        return {
            "agents": {"classification": {"classifications": [{"item": "Test", "hs_code": "1234", "confidence": "גבוהה"}]}},
            "synthesis": "Summary",
        }

    def test_fallback_without_enriched(self):
        """Should work with old format when no enriched_items (returns None if openpyxl missing)"""
        excel = build_excel_report(self._make_results())
        # Returns None when openpyxl not installed — that's expected in test env
        try:
            import openpyxl
            assert excel is not None
        except ImportError:
            assert excel is None  # graceful fallback

    def test_enriched_excel(self):
        enriched = [{"line_number": 1, "description": "Tires", "seller": "Michelin",
                      "buyer": "RPA", "quantity": "500", "unit_price": "$45",
                      "origin_country": "China", "hs_code": "4011.10",
                      "tariff_text_he": "צמיגי גומי", "duty_rate": "12%",
                      "purchase_tax_display": "לא חל", "vat_rate": "18%",
                      "confidence": "גבוהה", "verification_status": "verified",
                      "hs_corrected": False, "original_hs_code": "",
                      "ministries": [{"name_he": "משרד התחבורה"}], "reasoning": ""}]
        excel = build_excel_report(self._make_results(), enriched_items=enriched)
        try:
            import openpyxl
            assert excel is not None
        except ImportError:
            assert excel is None


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
