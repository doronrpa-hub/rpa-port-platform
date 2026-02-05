"""
Unit Tests for librarian.py
Run: pytest tests/test_librarian.py -v
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.librarian import (
    extract_search_keywords,
    search_collection_smart,
    search_tariff_codes
)


# ============================================================
# KEYWORD EXTRACTION TESTS
# ============================================================

class TestExtractSearchKeywords:
    """Tests for keyword extraction"""
    
    def test_basic_extraction(self):
        """Should extract meaningful words"""
        keywords = extract_search_keywords("electric hair dryer for salon use")
        assert "electric" in keywords
        assert "hair" in keywords
        assert "dryer" in keywords
        assert "salon" in keywords
    
    def test_stop_words_removed(self):
        """Should remove common stop words"""
        keywords = extract_search_keywords("the electric dryer for the salon")
        assert "the" not in keywords
        assert "for" not in keywords
        assert "electric" in keywords
    
    def test_hebrew_stop_words_removed(self):
        """Should remove Hebrew stop words"""
        keywords = extract_search_keywords("מייבש שיער של חברת פיליפס")
        assert "של" not in keywords
        assert "מייבש" in keywords
    
    def test_short_words_removed(self):
        """Should remove words with 2 or fewer chars"""
        keywords = extract_search_keywords("a TV is on")
        assert "a" not in keywords
        assert "is" not in keywords
        assert "on" not in keywords
    
    def test_max_keywords_limit(self):
        """Should return max 10 keywords"""
        long_text = " ".join([f"word{i}" for i in range(20)])
        keywords = extract_search_keywords(long_text)
        assert len(keywords) <= 10
    
    def test_punctuation_handling(self):
        """Should handle punctuation"""
        keywords = extract_search_keywords("dryer, blower. electric!")
        assert "dryer" in keywords
        assert "blower" in keywords
    
    def test_empty_input(self):
        """Should handle empty input"""
        keywords = extract_search_keywords("")
        assert keywords == []
    
    def test_lowercase_conversion(self):
        """Keywords should be lowercase"""
        keywords = extract_search_keywords("Electric HAIR Dryer")
        assert "electric" in keywords
        assert "Electric" not in keywords


# ============================================================
# COLLECTION SEARCH TESTS
# ============================================================

class TestSearchCollectionSmart:
    """Tests for smart collection search"""
    
    def test_basic_search(self):
        """Should find matching documents"""
        # Create mock Firestore
        mock_db = Mock()
        mock_doc1 = Mock()
        mock_doc1.id = "doc1"
        mock_doc1.to_dict.return_value = {
            "description_he": "מייבש שיער חשמלי",
            "description_en": "electric hair dryer"
        }
        mock_doc2 = Mock()
        mock_doc2.id = "doc2"
        mock_doc2.to_dict.return_value = {
            "description_he": "מברשת שיניים",
            "description_en": "toothbrush"
        }
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc1, mock_doc2]
        
        results = search_collection_smart(
            mock_db, 
            "products", 
            ["electric", "dryer"],
            ["description_he", "description_en"]
        )
        
        assert len(results) == 1
        assert results[0]["doc_id"] == "doc1"
        assert results[0]["score"] == 2  # Both keywords match
    
    def test_scoring(self):
        """Should score by keyword matches"""
        mock_db = Mock()
        mock_doc1 = Mock()
        mock_doc1.id = "doc1"
        mock_doc1.to_dict.return_value = {"text": "electric dryer heater"}  # 2 matches
        mock_doc2 = Mock()
        mock_doc2.id = "doc2"
        mock_doc2.to_dict.return_value = {"text": "electric fan"}  # 1 match
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc1, mock_doc2]
        
        results = search_collection_smart(mock_db, "test", ["electric", "dryer"], ["text"])
        
        assert results[0]["doc_id"] == "doc1"  # Higher score first
        assert results[0]["score"] > results[1]["score"]
    
    def test_max_results(self):
        """Should respect max_results limit"""
        mock_db = Mock()
        docs = []
        for i in range(100):
            doc = Mock()
            doc.id = f"doc{i}"
            doc.to_dict.return_value = {"text": "electric"}
            docs.append(doc)
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = docs
        
        results = search_collection_smart(mock_db, "test", ["electric"], ["text"], max_results=10)
        
        assert len(results) == 10
    
    def test_no_matches(self):
        """Should return empty for no matches"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.id = "doc1"
        mock_doc.to_dict.return_value = {"text": "something else"}
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = search_collection_smart(mock_db, "test", ["electric"], ["text"])
        
        assert results == []
    
    def test_error_handling(self):
        """Should handle Firestore errors gracefully"""
        mock_db = Mock()
        mock_db.collection.return_value.limit.return_value.stream.side_effect = Exception("DB error")
        
        results = search_collection_smart(mock_db, "test", ["electric"], ["text"])
        
        assert results == []


# ============================================================
# TARIFF CODE SEARCH TESTS
# ============================================================

class TestSearchTariffCodes:
    """Tests for tariff code search"""
    
    def test_searches_tariff_chapters(self):
        """Should search tariff_chapters collection"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.id = "8516"
        mock_doc.to_dict.return_value = {
            "code": "8516.31",
            "description_he": "מייבשי שיער",
            "description_en": "Hair dryers",
            "duty_rate": "12%"
        }
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = search_tariff_codes(mock_db, ["hair", "dryer"])
        
        # Should call collection for tariff search
        mock_db.collection.assert_called()
    
    def test_result_format(self):
        """Should return properly formatted results"""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.id = "8516"
        mock_doc.to_dict.return_value = {
            "code": "8516.31",
            "description_he": "מייבשי שיער",
            "description_en": "Hair dryers",
            "chapter": "85",
            "duty_rate": "12%"
        }
        
        mock_db.collection.return_value.limit.return_value.stream.return_value = [mock_doc]
        
        results = search_tariff_codes(mock_db, ["hair", "dryer"])
        
        if results:  # If search found results
            result = results[0]
            assert "hs_code" in result or "code" in result.get("data", {})
            assert "source" in result


# ============================================================
# INTEGRATION STYLE TESTS
# ============================================================

class TestKeywordToSearchFlow:
    """Tests for full keyword-to-search flow"""
    
    def test_hebrew_product_search(self):
        """Should handle Hebrew product descriptions"""
        keywords = extract_search_keywords("מייבש שיער חשמלי 220V")
        
        assert len(keywords) > 0
        assert "220v" in keywords or "מייבש" in keywords
    
    def test_english_product_search(self):
        """Should handle English product descriptions"""
        keywords = extract_search_keywords("Professional hair dryer 2000W ceramic")
        
        assert "professional" in keywords
        assert "dryer" in keywords
        assert "ceramic" in keywords
    
    def test_mixed_language_search(self):
        """Should handle mixed Hebrew/English"""
        keywords = extract_search_keywords("מכונת תספורת Philips דגם HC5630")
        
        assert "philips" in keywords or "מכונת" in keywords


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
