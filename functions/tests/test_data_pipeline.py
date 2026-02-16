"""
Unit Tests for data_pipeline package
Run: pytest tests/test_data_pipeline.py -v
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock

from lib.data_pipeline.extractor import extract_text, _detect_language, _extract_html
from lib.data_pipeline.structurer import (
    structure_with_llm, _fallback_structure, _extract_key_terms, _parse_json_response,
)
from lib.data_pipeline.indexer import index_document, _gather_hs_codes, _gather_all_hs_mentions
from lib.data_pipeline.pipeline import (
    ingest_source, SOURCE_TYPE_TO_COLLECTION, _validate, _generate_doc_id,
)


# ============================================================
# EXTRACTOR
# ============================================================

class TestExtractText:

    def test_empty_bytes_returns_empty(self):
        result = extract_text(None, "text/plain")
        assert result["char_count"] == 0
        assert result["extraction_method"] == "empty_input"

    def test_plain_text(self):
        content = b"Hello world, this is a test document with some content."
        result = extract_text(content, "text/plain")
        assert result["char_count"] > 0
        assert "Hello world" in result["full_text"]
        assert result["extraction_method"] == "plain_text"

    def test_html_extraction(self):
        html = b"<html><body><h1>Title</h1><p>Some content here</p><script>bad()</script></body></html>"
        result = extract_text(html, "text/html")
        assert "Title" in result["full_text"]
        assert "Some content" in result["full_text"]
        assert "bad()" not in result["full_text"]

    def test_html_table_extraction(self):
        html = b"""<html><body>
        <table>
            <tr><th>Code</th><th>Description</th></tr>
            <tr><td>8516</td><td>Hair dryers</td></tr>
            <tr><td>8471</td><td>Computers</td></tr>
        </table>
        </body></html>"""
        result = extract_text(html, "text/html")
        assert len(result["tables"]) == 2
        assert result["tables"][0]["Code"] == "8516"
        assert result["tables"][1]["Description"] == "Computers"

    def test_filename_fallback_for_type(self):
        content = b"Some text content here for testing the filename route."
        result = extract_text(content, "", filename="data.txt")
        assert result["char_count"] > 0

    def test_json_content(self):
        content = json.dumps({"key": "value", "data": [1, 2, 3]}).encode()
        result = extract_text(content, "application/json")
        assert "key" in result["full_text"]

    def test_caps_text_at_200k(self):
        content = ("x" * 300000).encode()
        result = extract_text(content, "text/plain")
        assert result["char_count"] <= 200000


class TestDetectLanguage:

    def test_hebrew_text(self):
        assert _detect_language("זהו טקסט בעברית עם הרבה מילים") == "he"

    def test_english_text(self):
        assert _detect_language("This is an English text with many words") == "en"

    def test_mixed_text(self):
        lang = _detect_language("Hello שלום this is mixed טקסט content תוכן")
        assert lang in ("mixed", "he", "en")

    def test_empty_text(self):
        assert _detect_language("") == "unknown"

    def test_numbers_only(self):
        assert _detect_language("12345 67890") == "unknown"


# ============================================================
# STRUCTURER
# ============================================================

class TestStructureWithLlm:

    def test_short_text_returns_empty(self):
        result = structure_with_llm("short", "directive")
        assert result == {}

    def test_fallback_when_no_gemini_key(self):
        text = "This is a classification directive about chapter 85 for HS code 85.16.310000"
        result = structure_with_llm(text, "directive")
        # Should use fallback structurer
        assert "key_terms" in result

    @patch("lib.classification_agents.call_gemini_fast")
    def test_gemini_success(self, mock_gemini):
        mock_gemini.return_value = json.dumps({
            "directive_id": "CD-2024-001",
            "title": "Test directive",
            "key_terms": ["test", "directive"],
        })

        get_secret = Mock(return_value="fake-key")
        text = "This is a long enough text for testing the structurer module with gemini" * 3

        result = structure_with_llm(text, "directive", get_secret_func=get_secret)
        assert result.get("directive_id") == "CD-2024-001"

    def test_unknown_source_type_uses_fallback(self):
        text = "This is some unknown source type text that has enough content for processing"
        result = structure_with_llm(text, "unknown_type")
        assert "key_terms" in result


class TestFallbackStructure:

    def test_extracts_hs_codes(self):
        text = "This directive covers HS code 85.16.31 and 84.71.30 for classification"
        result = _fallback_structure(text, "directive")
        assert "hs_codes_mentioned" in result
        assert len(result["hs_codes_mentioned"]) >= 2

    def test_extracts_chapters(self):
        text = "Chapter 85 items including code 85.16.31 and chapter 84 code 84.71.30"
        result = _fallback_structure(text, "directive")
        assert "chapters_covered" in result

    def test_extracts_key_terms(self):
        text = "Classification directive about electrical machines and computing devices"
        result = _fallback_structure(text, "directive")
        assert len(result["key_terms"]) > 0

    def test_handles_empty_text(self):
        result = _fallback_structure("", "directive")
        assert "key_terms" in result


class TestExtractKeyTerms:

    def test_basic_extraction(self):
        terms = _extract_key_terms("classification customs tariff import export")
        assert len(terms) > 0

    def test_removes_stop_words(self):
        terms = _extract_key_terms("the and for classification")
        assert "the" not in terms
        assert "and" not in terms

    def test_hebrew_stop_words(self):
        terms = _extract_key_terms("של את על סיווג מכס יבוא")
        assert "של" not in terms
        assert "את" not in terms

    def test_max_terms(self):
        long_text = " ".join([f"word{i}" for i in range(100)])
        terms = _extract_key_terms(long_text, max_terms=10)
        assert len(terms) <= 10


class TestParseJsonResponse:

    def test_direct_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_embedded_json(self):
        result = _parse_json_response('Here is the result: {"key": "value"} done')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        result = _parse_json_response("not json at all")
        assert result is None

    def test_empty_input(self):
        result = _parse_json_response("")
        assert result is None


# ============================================================
# INDEXER
# ============================================================

class TestGatherHsCodes:

    def test_single_code(self):
        codes = _gather_hs_codes({"hs_code": "8516.31"})
        assert "8516.31" in codes

    def test_assigned_code(self):
        codes = _gather_hs_codes({"hs_code_assigned": "84.71.300000/8"})
        assert "84.71.300000/8" in codes

    def test_empty_doc(self):
        codes = _gather_hs_codes({})
        assert codes == []


class TestGatherAllHsMentions:

    def test_multiple_fields(self):
        doc = {
            "hs_code": "8516.31",
            "hs_codes_mentioned": ["8516.31", "8471.30"],
            "hs_codes_discussed": ["8501.10"],
        }
        codes = _gather_all_hs_mentions(doc)
        assert len(codes) >= 3

    def test_deduplication(self):
        doc = {
            "hs_code": "8516.31",
            "hs_codes_mentioned": ["8516.31"],
        }
        codes = _gather_all_hs_mentions(doc)
        assert codes.count("8516.31") == 1


class TestIndexDocument:

    def test_indexes_to_librarian(self):
        db = Mock()
        db.collection.return_value = Mock(
            document=Mock(return_value=Mock(
                set=Mock(), get=Mock(return_value=Mock(exists=False)),
            )),
        )

        doc = {
            "title": "Test directive",
            "key_terms": ["test", "directive"],
            "hs_code": "8516.31",
        }

        with patch("lib.librarian_index.index_single_document", return_value=True):
            result = index_document(db, "classification_directives", "doc1", doc)

        assert result["librarian_indexed"] is True


# ============================================================
# PIPELINE
# ============================================================

class TestSourceTypeMapping:

    def test_all_types_have_collections(self):
        for stype, coll in SOURCE_TYPE_TO_COLLECTION.items():
            assert coll, f"Source type {stype} has empty collection"

    def test_directive_maps_correctly(self):
        assert SOURCE_TYPE_TO_COLLECTION["directive"] == "classification_directives"

    def test_pre_ruling_maps_correctly(self):
        assert SOURCE_TYPE_TO_COLLECTION["pre_ruling"] == "pre_rulings"


class TestValidate:

    def test_valid_document(self):
        doc = {
            "full_text": "x" * 200,
            "key_terms": ["test", "document"],
        }
        result = _validate(doc, "test_collection", "doc1")
        assert result["valid"] is True

    def test_short_text_fails(self):
        doc = {"full_text": "short", "key_terms": ["test"]}
        result = _validate(doc, "test_collection", "doc1")
        assert result["valid"] is False
        assert any("too short" in i for i in result["issues"])

    def test_no_key_terms_fails(self):
        doc = {"full_text": "x" * 200, "key_terms": []}
        result = _validate(doc, "test_collection", "doc1")
        assert result["valid"] is False

    def test_israeli_source_english_warns(self):
        doc = {
            "full_text": "x" * 200,
            "key_terms": ["test"],
            "language": "en",
            "source_url": "https://www.gov.il/some/page",
        }
        result = _validate(doc, "test", "doc1")
        assert any("Hebrew" in i for i in result["issues"])


class TestGenerateDocId:

    def test_uses_directive_id(self):
        doc_id = _generate_doc_id(
            {"directive_id": "CD-2024-001"}, "directive", "", ""
        )
        assert "CD-2024-001" in doc_id

    def test_uses_ruling_id(self):
        doc_id = _generate_doc_id(
            {"ruling_id": "PR-2023-456"}, "pre_ruling", "", ""
        )
        assert "PR-2023-456" in doc_id

    def test_fallback_to_hash(self):
        doc_id = _generate_doc_id(
            {}, "directive", "https://example.com/page", ""
        )
        assert doc_id.startswith("directive_")
        assert len(doc_id) > 10


class TestIngestSource:

    def test_no_bytes_returns_invalid(self):
        db = Mock()
        db.collection.return_value = Mock(add=Mock())
        result = ingest_source(db, "directive", raw_bytes=None)
        assert result["valid"] is False
        assert "No raw_bytes" in result["issues"][0]

    def test_short_extraction_returns_invalid(self):
        db = Mock()
        db.collection.return_value = Mock(add=Mock())
        result = ingest_source(
            db, "directive",
            content_type="text/plain",
            raw_bytes=b"too short",
        )
        assert result["valid"] is False

    def test_full_pipeline_with_good_content(self):
        db = Mock()
        doc_ref = Mock()
        doc_ref.set = Mock()
        col = Mock()
        col.document.return_value = doc_ref
        col.add = Mock()
        db.collection.return_value = col

        content = (
            "This is a classification directive about chapter 85 covering "
            "electrical machines and devices. HS code 85.16.31 applies to "
            "hair dryers and similar appliances. The directive was issued "
            "by the customs authority on 2024-03-15."
        ).encode()

        with patch("lib.librarian_index.index_single_document", return_value=True):
            result = ingest_source(
                db, "directive",
                content_type="text/plain",
                raw_bytes=content,
                source_url="https://gov.il/test",
            )

        assert result["doc_id"] is not None
        assert result["collection"] == "classification_directives"
        assert result["extraction"]["char_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
