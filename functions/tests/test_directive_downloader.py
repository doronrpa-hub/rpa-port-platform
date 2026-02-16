"""
Unit Tests for directive_downloader
Run: pytest tests/test_directive_downloader.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock, call

from lib.data_pipeline.directive_downloader import (
    _is_valid_directive_page,
    _get_existing_source_urls,
    download_single_directive,
    download_all_directives,
    BASE_URL,
)


# ============================================================
# SAMPLE HTML FIXTURES
# ============================================================

VALID_DIRECTIVE_HTML = """
<html>
<body>
<div class="guidance-details">
    <h2>הנחיית סיווג</h2>
    <div class="field">
        <label>מספר הנחיה:</label>
        <span>001/02</span>
    </div>
    <div class="field">
        <label>תאריך פתיחה:</label>
        <span>01/05/2002</span>
    </div>
    <div class="field">
        <label>נושא:</label>
        <span>סיווג מייבשי שיער חשמליים - פרט מכס 8516.31</span>
    </div>
    <div class="content">
        <p>הנחיה זו מתייחסת לסיווג מייבשי שיער חשמליים תחת פרק 85.
        מייבש שיער חשמלי המיועד לשימוש ביתי יסווג תחת פרט 8516.31.
        מכשירים מקצועיים למספרות יסווגו תחת פרט 8516.33.</p>
    </div>
</div>
</body>
</html>
"""

EMPTY_TEMPLATE_HTML = """
<html>
<body>
<div class="guidance-details">
    <h2>הנחיית סיווג</h2>
    <div class="field">
        <label>מספר הנחיה:</label>
        <span></span>
    </div>
</div>
</body>
</html>
"""

MINIMAL_VALID_HTML = """
<html><body>
<div>מספר הנחיה: 177/63</div>
<div>תאריך פתיחה: 15/03/2023</div>
<p>תוכן ההנחיה כאן. סיווג מוצרים שונים תחת פרק 85 של ספר המכס.
הנחיה זו מתייחסת לסיווג מוצרים אלקטרוניים שונים המיועדים לשימוש ביתי ומסחרי.
יש לפעול בהתאם להנחיות הסיווג המעודכנות.</p>
</body></html>
"""


# ============================================================
# TestIsValidDirectivePage
# ============================================================

class TestIsValidDirectivePage:

    def test_valid_directive_returns_true(self):
        assert _is_valid_directive_page(VALID_DIRECTIVE_HTML) is True

    def test_minimal_valid_returns_true(self):
        assert _is_valid_directive_page(MINIMAL_VALID_HTML) is True

    def test_empty_template_returns_false(self):
        assert _is_valid_directive_page(EMPTY_TEMPLATE_HTML) is False

    def test_none_returns_false(self):
        assert _is_valid_directive_page(None) is False

    def test_empty_string_returns_false(self):
        assert _is_valid_directive_page("") is False

    def test_short_string_returns_false(self):
        assert _is_valid_directive_page("short") is False

    def test_english_page_returns_false(self):
        html = "<html><body><p>This is an English page with no directive content at all.</p></body></html>" * 3
        assert _is_valid_directive_page(html) is False

    def test_marker_without_id_returns_false(self):
        html = "<html><body><div>מספר הנחיה: תאריך פתיחה: but no ID pattern here</div></body></html>" * 3
        assert _is_valid_directive_page(html) is False

    def test_id_without_marker_returns_false(self):
        html = "<html><body><div>Some page with 001/02 but no Hebrew markers</div></body></html>" * 3
        assert _is_valid_directive_page(html) is False


# ============================================================
# TestGetExistingSourceUrls
# ============================================================

class TestGetExistingSourceUrls:

    def test_returns_existing_urls(self):
        doc1 = Mock()
        doc1.to_dict.return_value = {"source_url": "https://example.com/1"}
        doc2 = Mock()
        doc2.to_dict.return_value = {"source_url": "https://example.com/2"}

        db = Mock()
        db.collection.return_value.select.return_value.stream.return_value = [doc1, doc2]

        result = _get_existing_source_urls(db)
        assert result == {"https://example.com/1", "https://example.com/2"}

    def test_empty_collection_returns_empty_set(self):
        db = Mock()
        db.collection.return_value.select.return_value.stream.return_value = []

        result = _get_existing_source_urls(db)
        assert result == set()

    def test_firestore_error_returns_empty_set(self):
        db = Mock()
        db.collection.return_value.select.side_effect = Exception("Firestore down")

        result = _get_existing_source_urls(db)
        assert result == set()


# ============================================================
# TestDownloadSingleDirective
# ============================================================

class TestDownloadSingleDirective:

    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader.ingest_source")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_downloads_valid_directive(self, mock_existing, mock_ingest, mock_requests):
        mock_existing.return_value = set()

        resp = Mock()
        resp.text = VALID_DIRECTIVE_HTML
        resp.content = VALID_DIRECTIVE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        mock_ingest.return_value = {"doc_id": "directive_001_02", "issues": []}

        db = Mock()
        result = download_single_directive(db, 1, Mock())

        assert result["status"] == "downloaded"
        assert result["doc_id"] == "directive_001_02"
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args
        assert call_kwargs.kwargs["source_type"] == "directive"
        assert call_kwargs.kwargs["content_type"] == "text/html"

    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_skips_existing_directive(self, mock_existing):
        url = BASE_URL.format(id=5)
        mock_existing.return_value = {url}

        db = Mock()
        result = download_single_directive(db, 5, Mock())

        assert result["status"] == "skipped_exists"

    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_skips_empty_page(self, mock_existing, mock_requests):
        mock_existing.return_value = set()

        resp = Mock()
        resp.text = EMPTY_TEMPLATE_HTML
        resp.content = EMPTY_TEMPLATE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        db = Mock()
        result = download_single_directive(db, 99, Mock())

        assert result["status"] == "skipped_empty"

    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_handles_http_error(self, mock_existing, mock_requests):
        mock_existing.return_value = set()

        mock_requests.get.side_effect = Exception("Connection timeout")

        db = Mock()
        result = download_single_directive(db, 1, Mock())

        assert result["status"] == "failed"
        assert "Connection timeout" in result["error"]

    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader.ingest_source")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_handles_pipeline_failure(self, mock_existing, mock_ingest, mock_requests):
        mock_existing.return_value = set()

        resp = Mock()
        resp.text = VALID_DIRECTIVE_HTML
        resp.content = VALID_DIRECTIVE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        mock_ingest.return_value = {"doc_id": None, "issues": ["Extraction too short"]}

        db = Mock()
        result = download_single_directive(db, 1, Mock())

        assert result["status"] == "failed"
        assert "Extraction too short" in result["error"]


# ============================================================
# TestDownloadAllDirectives
# ============================================================

class TestDownloadAllDirectives:

    @patch("lib.data_pipeline.directive_downloader.time")
    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader.ingest_source")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_downloads_multiple_directives(self, mock_existing, mock_ingest, mock_requests, mock_time):
        mock_existing.return_value = set()
        mock_time.sleep = Mock()

        resp = Mock()
        resp.text = VALID_DIRECTIVE_HTML
        resp.content = VALID_DIRECTIVE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        mock_ingest.return_value = {"doc_id": "directive_001_02", "issues": []}

        db = Mock()
        stats = download_all_directives(db, Mock(), max_id=3, delay=0)

        assert stats["downloaded"] == 3
        assert stats["failed"] == 0
        assert mock_requests.get.call_count == 3

    @patch("lib.data_pipeline.directive_downloader.time")
    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_skips_existing_ids(self, mock_existing, mock_requests, mock_time):
        url_1 = BASE_URL.format(id=1)
        url_2 = BASE_URL.format(id=2)
        mock_existing.return_value = {url_1, url_2}
        mock_time.sleep = Mock()

        # ID 3 returns empty
        resp = Mock()
        resp.text = EMPTY_TEMPLATE_HTML
        resp.content = EMPTY_TEMPLATE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        db = Mock()
        stats = download_all_directives(db, Mock(), max_id=3, delay=0)

        assert stats["skipped_exists"] == 2
        assert stats["skipped_empty"] == 1
        assert stats["downloaded"] == 0
        # Only ID 3 was fetched
        assert mock_requests.get.call_count == 1

    @patch("lib.data_pipeline.directive_downloader.time")
    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_handles_mixed_results(self, mock_existing, mock_requests, mock_time):
        mock_existing.return_value = set()
        mock_time.sleep = Mock()

        # ID 1: HTTP error, ID 2: valid, ID 3: empty
        error_resp = Exception("Server error")
        valid_resp = Mock()
        valid_resp.text = VALID_DIRECTIVE_HTML
        valid_resp.content = VALID_DIRECTIVE_HTML.encode("utf-8")
        valid_resp.raise_for_status = Mock()
        empty_resp = Mock()
        empty_resp.text = EMPTY_TEMPLATE_HTML
        empty_resp.content = EMPTY_TEMPLATE_HTML.encode("utf-8")
        empty_resp.raise_for_status = Mock()

        mock_requests.get.side_effect = [error_resp, valid_resp, empty_resp]

        db = Mock()

        with patch("lib.data_pipeline.directive_downloader.ingest_source") as mock_ingest:
            mock_ingest.return_value = {"doc_id": "directive_001_02", "issues": []}
            stats = download_all_directives(db, Mock(), max_id=3, delay=0)

        assert stats["failed"] == 1
        assert stats["downloaded"] == 1
        assert stats["skipped_empty"] == 1
        assert len(stats["errors"]) == 1

    @patch("lib.data_pipeline.directive_downloader.time")
    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_rate_limiting_applied(self, mock_existing, mock_requests, mock_time):
        mock_existing.return_value = set()

        resp = Mock()
        resp.text = EMPTY_TEMPLATE_HTML
        resp.content = EMPTY_TEMPLATE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        db = Mock()
        download_all_directives(db, Mock(), max_id=3, delay=1.5)

        # Sleep called once per non-skipped ID
        assert mock_time.sleep.call_count == 3
        mock_time.sleep.assert_called_with(1.5)

    @patch("lib.data_pipeline.directive_downloader.time")
    @patch("lib.data_pipeline.directive_downloader.requests")
    @patch("lib.data_pipeline.directive_downloader.ingest_source")
    @patch("lib.data_pipeline.directive_downloader._get_existing_source_urls")
    def test_correct_url_format(self, mock_existing, mock_ingest, mock_requests, mock_time):
        mock_existing.return_value = set()
        mock_time.sleep = Mock()

        resp = Mock()
        resp.text = VALID_DIRECTIVE_HTML
        resp.content = VALID_DIRECTIVE_HTML.encode("utf-8")
        resp.raise_for_status = Mock()
        mock_requests.get.return_value = resp

        mock_ingest.return_value = {"doc_id": "test", "issues": []}

        db = Mock()
        download_all_directives(db, Mock(), max_id=1, delay=0)

        expected_url = (
            "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/"
            "Import/ClassificationGuidanceDetails?customsItemId=0&classificationGuidanceId=1"
        )
        mock_requests.get.assert_called_once_with(expected_url, timeout=30)
