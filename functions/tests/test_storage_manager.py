"""
Tests for storage_manager — Cloud Storage helper.

Session 28C — Assignment 20.
NEW FILE.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.storage_manager import (
    store_text_smart,
    retrieve_full_text,
    store_raw_file,
    TEXT_SIZE_THRESHOLD,
    BUCKET_NAME,
    BUCKET_PREFIX,
)


# ─────────────────────────────────────
#  store_text_smart
# ─────────────────────────────────────

class TestStoreTextSmart:

    def test_small_text_stays_in_firestore(self):
        """Text <= 10KB should be stored directly in Firestore."""
        text = "Hello, world! This is a small document."
        result = store_text_smart(text, "scanner_logs", "doc123")
        assert result["full_text"] == text
        assert result["full_text_storage"] == "firestore"
        assert result["full_text_length"] == len(text)
        assert "full_text_path" not in result

    @patch("lib.storage_manager.upload_to_gcs")
    def test_large_text_goes_to_cloud_storage(self, mock_upload):
        """Text > 10KB should be uploaded to Cloud Storage."""
        text = "x" * (TEXT_SIZE_THRESHOLD + 1000)
        result = store_text_smart(text, "directives", "doc456")

        assert result["full_text_storage"] == "cloud_storage"
        assert result["full_text_length"] == len(text)
        assert "full_text_preview" in result
        assert len(result["full_text_preview"]) == 500
        assert result["full_text_path"].startswith(f"gs://{BUCKET_NAME}/")

        # Verify upload was called
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert "directives" in call_args[0][1]
        assert "doc456" in call_args[0][1]

    def test_boundary_text_stays_in_firestore(self):
        """Text exactly at the threshold should stay in Firestore."""
        # Create text whose UTF-8 encoding is exactly TEXT_SIZE_THRESHOLD
        text = "a" * TEXT_SIZE_THRESHOLD
        result = store_text_smart(text, "test", "boundary")
        assert result["full_text_storage"] == "firestore"

    @patch("lib.storage_manager.upload_to_gcs")
    def test_hebrew_text_size_calculated_in_bytes(self, mock_upload):
        """Hebrew text is multi-byte in UTF-8 — size should be in bytes, not chars."""
        # Each Hebrew char is ~2 bytes in UTF-8
        hebrew_char_count = TEXT_SIZE_THRESHOLD  # chars
        text = "א" * hebrew_char_count  # Each "א" is 2 bytes in UTF-8
        # This should exceed the byte threshold
        result = store_text_smart(text, "test", "hebrew")
        assert result["full_text_storage"] == "cloud_storage"


# ─────────────────────────────────────
#  retrieve_full_text
# ─────────────────────────────────────

class TestRetrieveFullText:

    def test_retrieve_from_firestore(self):
        doc = {"full_text": "Hello world", "full_text_storage": "firestore"}
        result = retrieve_full_text(doc)
        assert result == "Hello world"

    @patch("lib.storage_manager.download_from_gcs")
    def test_retrieve_from_cloud_storage(self, mock_download):
        mock_download.return_value = b"Full text from storage"
        doc = {
            "full_text_storage": "cloud_storage",
            "full_text_path": f"gs://{BUCKET_NAME}/{BUCKET_PREFIX}/texts/test/doc1.txt",
        }
        result = retrieve_full_text(doc)
        assert result == "Full text from storage"
        mock_download.assert_called_once()

    def test_retrieve_missing_field(self):
        doc = {}
        result = retrieve_full_text(doc)
        assert result == ""

    def test_retrieve_no_storage_marker(self):
        doc = {"full_text": "Legacy doc without storage marker"}
        result = retrieve_full_text(doc)
        assert result == "Legacy doc without storage marker"


# ─────────────────────────────────────
#  store_raw_file
# ─────────────────────────────────────

class TestStoreRawFile:

    @patch("lib.storage_manager.upload_to_gcs")
    def test_raw_file_stored_with_hash(self, mock_upload):
        data = b"PDF file content here"
        path = store_raw_file(data, "attachments", "invoice.pdf")

        assert path.startswith(f"gs://{BUCKET_NAME}/")
        assert "attachments" in path
        assert "invoice.pdf" in path
        mock_upload.assert_called_once()

    @patch("lib.storage_manager.upload_to_gcs")
    def test_filename_sanitized(self, mock_upload):
        data = b"content"
        path = store_raw_file(data, "attachments", "bad name (1).pdf")
        # Special chars should be replaced with underscores
        assert "bad_name__1_.pdf" in path

    @patch("lib.storage_manager.upload_to_gcs")
    def test_raw_file_has_date_prefix(self, mock_upload):
        import re
        data = b"content"
        path = store_raw_file(data, "emails", "msg.eml")
        # Should contain a date like 2025-01-15
        assert re.search(r"\d{4}-\d{2}-\d{2}", path)
