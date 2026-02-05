"""
Unit Tests for rcb_helpers.py
Run: pytest tests/test_rcb_helpers.py -v
"""
import pytest
import base64
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.rcb_helpers import (
    to_hebrew_name,
    build_rcb_reply,
    extract_text_from_pdf_bytes,
    extract_text_from_attachments,
    helper_get_graph_token,
    HEBREW_NAMES
)


# ============================================================
# HEBREW NAME TESTS
# ============================================================

class TestHebrewNames:
    """Tests for Hebrew name conversion"""
    
    def test_known_name_lowercase(self):
        """Should convert known English name to Hebrew"""
        assert to_hebrew_name("doron") == "דורון"
        assert to_hebrew_name("amit") == "עמית"
        assert to_hebrew_name("moshe") == "משה"
    
    def test_known_name_uppercase(self):
        """Should handle uppercase names"""
        assert to_hebrew_name("DORON") == "דורון"
        assert to_hebrew_name("Doron") == "דורון"
    
    def test_known_name_with_spaces(self):
        """Should handle names with whitespace"""
        assert to_hebrew_name("  doron  ") == "דורון"
    
    def test_unknown_name_returns_original(self):
        """Should return original if name not in dictionary"""
        assert to_hebrew_name("John") == "John"
        assert to_hebrew_name("Michael") == "Michael"
    
    def test_already_hebrew(self):
        """Should return Hebrew name as-is"""
        assert to_hebrew_name("דורון") == "דורון"
        assert to_hebrew_name("משה") == "משה"
    
    def test_empty_name(self):
        """Should return שלום for empty/None"""
        assert to_hebrew_name("") == "שלום"
        assert to_hebrew_name(None) == "שלום"
    
    def test_all_names_in_dictionary(self):
        """Verify all names in HEBREW_NAMES are valid"""
        assert len(HEBREW_NAMES) > 20  # Should have many names
        for eng, heb in HEBREW_NAMES.items():
            assert eng.islower()  # Keys should be lowercase
            assert any('\u0590' <= c <= '\u05FF' for c in heb)  # Should contain Hebrew


# ============================================================
# EMAIL BUILDER TESTS
# ============================================================

class TestBuildRcbReply:
    """Tests for email reply builder"""
    
    def test_basic_reply(self):
        """Should build basic HTML reply"""
        html = build_rcb_reply("Test User", [])
        assert "שלום" in html or "טוב" in html  # Greeting
        assert "dir=\"rtl\"" in html  # RTL support
        assert "RCB" in html  # Brand
    
    def test_reply_with_known_name(self):
        """Should convert sender name to Hebrew"""
        html = build_rcb_reply("Doron <doron@test.com>", [])
        assert "דורון" in html
    
    def test_reply_with_attachments(self):
        """Should list attachments"""
        attachments = [
            {"filename": "invoice.pdf", "type": ".pdf"},
            {"filename": "photo.jpg", "type": ".jpg"}
        ]
        html = build_rcb_reply("Test", attachments)
        assert "invoice.pdf" in html
        assert "photo.jpg" in html
        assert "2 קבצים" in html  # Count in Hebrew
    
    def test_reply_with_subject(self):
        """Should include subject"""
        html = build_rcb_reply("Test", [], subject="Test Shipment 123")
        assert "Test Shipment 123" in html
    
    def test_reply_has_signature(self):
        """Should include signature block"""
        html = build_rcb_reply("Test", [])
        assert "rcb@rpa-port.co.il" in html
        assert "R.P.A. PORT" in html
    
    def test_reply_email_only_sender(self):
        """Should handle email-only sender gracefully"""
        html = build_rcb_reply("test@example.com", [])
        assert "שלום" in html  # Default greeting


# ============================================================
# PDF EXTRACTION TESTS
# ============================================================

class TestPdfExtraction:
    """Tests for PDF text extraction"""
    
    def test_extract_empty_bytes(self):
        """Should handle empty input"""
        result = extract_text_from_pdf_bytes(b"")
        assert result == ""
    
    def test_extract_invalid_pdf(self):
        """Should handle invalid PDF gracefully"""
        result = extract_text_from_pdf_bytes(b"not a pdf")
        assert result == ""  # Should not crash
    
    @patch('lib.rcb_helpers._extract_with_pdfplumber')
    def test_pdfplumber_success(self, mock_pdfplumber):
        """Should return pdfplumber result if successful"""
        mock_pdfplumber.return_value = "This is extracted text with more than 50 characters to pass the threshold check."
        result = extract_text_from_pdf_bytes(b"fake pdf bytes")
        assert "extracted text" in result
        mock_pdfplumber.assert_called_once()
    
    @patch('lib.rcb_helpers._extract_with_pdfplumber')
    @patch('lib.rcb_helpers._extract_with_pypdf')
    def test_pypdf_fallback(self, mock_pypdf, mock_pdfplumber):
        """Should fall back to pypdf if pdfplumber fails"""
        mock_pdfplumber.return_value = ""  # pdfplumber fails
        mock_pypdf.return_value = "pypdf extracted this text successfully with enough characters"
        result = extract_text_from_pdf_bytes(b"fake pdf")
        assert "pypdf extracted" in result
    
    @patch('lib.rcb_helpers._extract_with_pdfplumber')
    @patch('lib.rcb_helpers._extract_with_pypdf')
    @patch('lib.rcb_helpers._extract_with_vision_ocr')
    def test_ocr_fallback(self, mock_ocr, mock_pypdf, mock_pdfplumber):
        """Should fall back to OCR if text extraction fails"""
        mock_pdfplumber.return_value = ""
        mock_pypdf.return_value = ""
        mock_ocr.return_value = "OCR extracted this from scanned document with sufficient length"
        result = extract_text_from_pdf_bytes(b"fake scanned pdf")
        assert "OCR extracted" in result


class TestExtractFromAttachments:
    """Tests for attachment extraction"""
    
    def test_empty_attachments(self):
        """Should handle empty list"""
        result = extract_text_from_attachments([])
        assert result == ""
    
    def test_non_pdf_skipped(self):
        """Should skip non-PDF attachments (except images)"""
        attachments = [
            {"name": "doc.docx", "contentBytes": base64.b64encode(b"word doc").decode()},
            {"name": "data.csv", "contentBytes": base64.b64encode(b"csv data").decode()}
        ]
        result = extract_text_from_attachments(attachments)
        assert result == ""  # Non-PDF/image files skipped
    
    def test_missing_content_bytes(self):
        """Should skip attachments without content"""
        attachments = [
            {"name": "doc.pdf"},  # No contentBytes
            {"name": "doc2.pdf", "contentBytes": ""}  # Empty contentBytes
        ]
        result = extract_text_from_attachments(attachments)
        assert result == "" or "[No text" in result
    
    @patch('lib.rcb_helpers.extract_text_from_pdf_bytes')
    def test_pdf_extraction_called(self, mock_extract):
        """Should call PDF extraction for PDF files"""
        mock_extract.return_value = "Extracted PDF text"
        attachments = [
            {"name": "invoice.pdf", "contentBytes": base64.b64encode(b"pdf content").decode()}
        ]
        result = extract_text_from_attachments(attachments)
        mock_extract.assert_called_once()
        assert "invoice.pdf" in result


# ============================================================
# GRAPH API TESTS
# ============================================================

class TestGraphToken:
    """Tests for Microsoft Graph API token"""
    
    @patch('requests.post')
    def test_successful_token(self, mock_post):
        """Should return token on success"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"access_token": "test_token_123"}
        )
        secrets = {
            'RCB_GRAPH_CLIENT_ID': 'client_id',
            'RCB_GRAPH_CLIENT_SECRET': 'secret',
            'RCB_GRAPH_TENANT_ID': 'tenant_id'
        }
        token = helper_get_graph_token(secrets)
        assert token == "test_token_123"
    
    @patch('requests.post')
    def test_failed_token(self, mock_post):
        """Should return None on failure"""
        mock_post.return_value = Mock(status_code=401)
        secrets = {
            'RCB_GRAPH_CLIENT_ID': 'client_id',
            'RCB_GRAPH_CLIENT_SECRET': 'wrong_secret',
            'RCB_GRAPH_TENANT_ID': 'tenant_id'
        }
        token = helper_get_graph_token(secrets)
        assert token is None
    
    @patch('requests.post')
    def test_network_error(self, mock_post):
        """Should handle network errors"""
        mock_post.side_effect = Exception("Network error")
        secrets = {
            'RCB_GRAPH_CLIENT_ID': 'client_id',
            'RCB_GRAPH_CLIENT_SECRET': 'secret',
            'RCB_GRAPH_TENANT_ID': 'tenant_id'
        }
        token = helper_get_graph_token(secrets)
        assert token is None


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
