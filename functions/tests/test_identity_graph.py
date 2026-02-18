"""
Tests for Deal Identity Graph — Session 46
===========================================
Tests all 5 core functions + helpers in identity_graph.py.

Covers:
  - extract_identifiers_from_email (pure regex, no Firestore)
  - find_deal_by_identifier (mock Firestore queries)
  - register_identifier (mock Firestore read/write)
  - merge_deals (mock Firestore merge logic)
  - link_email_to_deal (integration of extract + find + register)
  - register_deal_from_tracker (bulk sync utility)
  - Edge cases: empty input, Hebrew text, dedup, merged records
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add functions/ and functions/lib/ to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.identity_graph import (
    extract_identifiers_from_email,
    find_deal_by_identifier,
    register_identifier,
    merge_deals,
    link_email_to_deal,
    register_deal_from_tracker,
    _normalize_subject,
    _validate_container,
    _empty_graph,
    COLLECTION,
    IDENTIFIER_FIELDS,
    SCALAR_ID_FIELDS,
    LEARNED_PATTERNS_COLLECTION,
)


# ═══════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Create a mock Firestore database."""
    return Mock()


@pytest.fixture
def mock_graph_doc():
    """Factory for mock identity graph documents."""
    def _create(deal_id, data=None):
        doc = Mock()
        doc.id = deal_id
        doc.exists = True
        doc.to_dict.return_value = data or _empty_graph(deal_id)
        return doc
    return _create


@pytest.fixture
def sample_graph_data():
    """A populated identity graph entry for testing."""
    return {
        "deal_id": "deal_abc123",
        "bl_numbers": ["ZIMU001234AB"],
        "booking_refs": ["BKG123456"],
        "awb_numbers": [],
        "container_numbers": ["ZIMU1234560"],
        "invoice_numbers": ["INV-2026-001"],
        "po_numbers": ["PO-5555"],
        "packing_list_refs": [],
        "email_thread_ids": ["thread_xyz"],
        "client_name": "Acme Import Ltd",
        "client_ref": "FILE-001",
        "internal_file_ref": "RPA-2026-100",
        "job_order_number": "JO-2026-042",
        "file_number": "412345",
        "import_number": "IL-IMP-2026-001",
        "export_number": "",
        "seped_number": "98765432",
        "email_subjects": ["Shipment from China - Acme"],
        "last_updated": "2026-02-18T10:00:00+00:00",
        "confidence": 0.8,
    }


# ═══════════════════════════════════════════
#  TEST: _normalize_subject
# ═══════════════════════════════════════════

class TestNormalizeSubject:
    def test_strips_re_prefix(self):
        assert _normalize_subject("Re: Shipment 123") == "Shipment 123"

    def test_strips_fwd_prefix(self):
        assert _normalize_subject("Fwd: Invoice attached") == "Invoice attached"

    def test_strips_multiple_prefixes(self):
        assert _normalize_subject("Re: Re: FW: Fwd: Actual Subject") == "Actual Subject"

    def test_strips_case_variants(self):
        assert _normalize_subject("RE: FWD: Test") == "Test"

    def test_empty_subject(self):
        assert _normalize_subject("") == ""

    def test_none_subject(self):
        assert _normalize_subject(None) == ""

    def test_no_prefix(self):
        assert _normalize_subject("Clean Subject") == "Clean Subject"

    def test_collapses_whitespace(self):
        assert _normalize_subject("Re:   Subject  with   spaces") == "Subject with spaces"

    def test_hebrew_subject(self):
        result = _normalize_subject("Re: משלוח מסין - חברת אקמה")
        assert "משלוח מסין" in result


# ═══════════════════════════════════════════
#  TEST: _validate_container
# ═══════════════════════════════════════════

class TestValidateContainer:
    def test_valid_container(self):
        # MSKU9070323 — valid check digit
        assert _validate_container("MSKU9070323") is True

    def test_invalid_check_digit(self):
        assert _validate_container("MSCU5361175") is False

    def test_wrong_format_short(self):
        assert _validate_container("MSC123") is False

    def test_wrong_format_no_digits(self):
        assert _validate_container("ABCDEFGHIJK") is False

    def test_lowercase_normalized(self):
        # Should uppercase and validate
        assert _validate_container("msku9070323") is True

    def test_empty_string(self):
        assert _validate_container("") is False


# ═══════════════════════════════════════════
#  TEST: extract_identifiers_from_email
# ═══════════════════════════════════════════

class TestExtractIdentifiers:
    """Tests for extract_identifiers_from_email — pure regex, no Firestore."""

    def test_empty_input(self):
        result = extract_identifiers_from_email("", "", "")
        assert result["bl_numbers"] == []
        assert result["container_numbers"] == []
        assert result["invoice_numbers"] == []

    def test_none_input(self):
        result = extract_identifiers_from_email(None, None, None)
        assert result["bl_numbers"] == []

    def test_extract_bl_labeled(self):
        body = "Please track B/L ZIMU001234AB for our shipment"
        result = extract_identifiers_from_email("", body)
        assert "ZIMU001234AB" in result["bl_numbers"]

    def test_extract_bl_hebrew(self):
        body = "שטר מטען ZIMU001234AB"
        result = extract_identifiers_from_email("", body)
        assert "ZIMU001234AB" in result["bl_numbers"]

    def test_extract_bl_msc_format(self):
        body = "Our MSC booking MEDURS12345678"
        result = extract_identifiers_from_email("", body)
        assert "MEDURS12345678" in result["bl_numbers"]

    def test_extract_container_valid(self):
        body = "Container MSKU9070323 arrived at port"
        result = extract_identifiers_from_email("", body)
        assert "MSKU9070323" in result["container_numbers"]

    def test_extract_container_invalid_check_digit(self):
        """Invalid check digit should be filtered out."""
        body = "Container XXXX0000000 at port"
        result = extract_identifiers_from_email("", body)
        assert "XXXX0000000" not in result["container_numbers"]

    def test_extract_multiple_containers(self):
        body = "Containers: MSKU9070323 and CSQU3054383"
        result = extract_identifiers_from_email("", body)
        # At least the format-valid ones should appear
        assert len(result["container_numbers"]) >= 1

    def test_extract_awb_labeled(self):
        body = "AWB: 020-12345678"
        result = extract_identifiers_from_email("", body)
        assert len(result["awb_numbers"]) >= 1

    def test_extract_awb_hebrew(self):
        body = "שטר מטען אווירי 020-12345678"
        result = extract_identifiers_from_email("", body)
        assert len(result["awb_numbers"]) >= 1

    def test_awb_bare_only_with_air_context(self):
        """Bare AWB pattern should only match when air cargo context present."""
        body_no_context = "Reference 020 1234 5678 for your order"
        result = extract_identifiers_from_email("", body_no_context)
        assert result["awb_numbers"] == []

        body_with_context = "AWB reference 020 1234 5678"
        result = extract_identifiers_from_email("", body_with_context)
        assert len(result["awb_numbers"]) >= 1

    def test_extract_booking(self):
        body = "Booking BKG123456 confirmed"
        result = extract_identifiers_from_email("", body)
        assert "BKG123456" in result["booking_refs"]

    def test_extract_booking_hebrew(self):
        body = "הזמנה ABC987654"
        result = extract_identifiers_from_email("", body)
        assert "ABC987654" in result["booking_refs"]

    def test_extract_booking_ebkg(self):
        body = "Your booking EBKG123456789 is ready"
        result = extract_identifiers_from_email("", body)
        assert "EBKG123456789" in result["booking_refs"]

    def test_extract_invoice(self):
        body = "Invoice No. INV-2026-001 attached"
        result = extract_identifiers_from_email("", body)
        assert "INV-2026-001" in result["invoice_numbers"]

    def test_extract_invoice_hebrew(self):
        body = "חשבונית מס 12345"
        result = extract_identifiers_from_email("", body)
        assert len(result["invoice_numbers"]) >= 1

    def test_extract_po_number(self):
        body = "Purchase Order PO-2026-789"
        result = extract_identifiers_from_email("", body)
        assert "PO-2026-789" in result["po_numbers"]

    def test_extract_po_hebrew(self):
        body = "הזמנת רכש ABC123"
        result = extract_identifiers_from_email("", body)
        assert "ABC123" in result["po_numbers"]

    def test_extract_packing_list(self):
        body = "Packing List No. PL-001 enclosed"
        result = extract_identifiers_from_email("", body)
        assert "PL-001" in result["packing_list_refs"]

    def test_extract_packing_list_hebrew(self):
        body = "מפרט אריזות 12345"
        result = extract_identifiers_from_email("", body)
        assert "12345" in result["packing_list_refs"]

    def test_extract_client_ref(self):
        body = "Your ref: FILE-001"
        result = extract_identifiers_from_email("", body)
        assert result["client_ref"] == "FILE-001"

    def test_extract_internal_ref(self):
        body = "Our ref: RPA-2026-100"
        result = extract_identifiers_from_email("", body)
        assert result["internal_file_ref"] == "RPA-2026-100"

    def test_subject_normalized(self):
        result = extract_identifiers_from_email("Re: FW: Shipment from China", "body text")
        assert result["email_subject_normalized"] == "Shipment from China"

    def test_combined_extraction(self):
        """Test extracting multiple identifier types from one email."""
        subject = "Re: Shipment ZIMU001234AB"
        body = """
        Dear Sir,
        B/L: ZIMU001234AB
        Container: MSKU9070323
        Booking: BKG123456
        Invoice No. INV-2026-001
        Your ref: FILE-001
        """
        result = extract_identifiers_from_email(subject, body)
        assert "ZIMU001234AB" in result["bl_numbers"]
        assert "MSKU9070323" in result["container_numbers"]
        assert "BKG123456" in result["booking_refs"]
        assert "INV-2026-001" in result["invoice_numbers"]
        assert result["client_ref"] == "FILE-001"

    def test_attachments_text_included(self):
        """Identifiers in attachments_text should also be found."""
        result = extract_identifiers_from_email(
            "", "", "Invoice #ATT-999 in attachment"
        )
        assert "ATT-999" in result["invoice_numbers"]

    def test_dedup_same_bl(self):
        """Same BL appearing multiple times should be deduped."""
        body = "B/L ZIMU001234AB confirmed\nBL: ZIMU001234AB again"
        result = extract_identifiers_from_email("", body)
        assert result["bl_numbers"].count("ZIMU001234AB") == 1

    def test_container_not_in_bl(self):
        """Container numbers should not appear in BL list."""
        body = "Container MSKU9070323"
        result = extract_identifiers_from_email("", body)
        assert "MSKU9070323" not in result["bl_numbers"]

    # ── New fields: file_number, job_order, import, export, seped ──

    def test_extract_file_number_import(self):
        """File number starting with 4 = import."""
        body = "תיק מספר 412345"
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == "412345"

    def test_extract_file_number_export(self):
        """File number starting with 6 = transit/export."""
        body = "File No. 678901"
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == "678901"

    def test_extract_file_number_hebrew(self):
        body = "תיק מס 456789"
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == "456789"

    def test_extract_job_order(self):
        body = "Job Order: WO-2026-042"
        result = extract_identifiers_from_email("", body)
        assert result["job_order_number"] == "WO-2026-042"

    def test_extract_job_order_hebrew(self):
        body = "פקודת עבודה 12345"
        result = extract_identifiers_from_email("", body)
        assert result["job_order_number"] == "12345"

    def test_extract_import_number(self):
        body = "Import License: IL-IMP-2026-001"
        result = extract_identifiers_from_email("", body)
        assert result["import_number"] == "IL-IMP-2026-001"

    def test_extract_import_number_hebrew(self):
        body = "רישיון יבוא 987654"
        result = extract_identifiers_from_email("", body)
        assert result["import_number"] == "987654"

    def test_extract_export_number(self):
        body = "Export permit: EXP-2026-099"
        result = extract_identifiers_from_email("", body)
        assert result["export_number"] == "EXP-2026-099"

    def test_extract_export_number_hebrew(self):
        body = "רישיון יצוא 123456"
        result = extract_identifiers_from_email("", body)
        assert result["export_number"] == "123456"

    def test_extract_seped_number(self):
        body = "ספד 98765432"
        result = extract_identifiers_from_email("", body)
        assert result["seped_number"] == "98765432"

    def test_extract_seped_english(self):
        body = "Entry No. 12345678"
        result = extract_identifiers_from_email("", body)
        assert result["seped_number"] == "12345678"

    def test_no_file_number_wrong_prefix(self):
        """File numbers not starting with 4 or 6 should not match."""
        body = "File No. 312345"
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == ""

    def test_combined_new_fields(self):
        """All new fields extracted from one email."""
        body = """
        תיק מספר 412345
        Job Order: WO-001
        רישיון יבוא IMP-999
        ספד 87654321
        """
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == "412345"
        assert result["job_order_number"] == "WO-001"
        assert result["import_number"] == "IMP-999"
        assert result["seped_number"] == "87654321"


# ═══════════════════════════════════════════
#  TEST: find_deal_by_identifier
# ═══════════════════════════════════════════

class TestFindDealByIdentifier:
    def test_none_db(self):
        assert find_deal_by_identifier(None, "ZIMU001234AB") is None

    def test_empty_identifier(self):
        assert find_deal_by_identifier(Mock(), "") is None

    def test_none_identifier(self):
        assert find_deal_by_identifier(Mock(), None) is None

    def test_finds_by_bl(self, mock_db, mock_graph_doc, sample_graph_data):
        """Should find deal when BL matches."""
        doc = mock_graph_doc("deal_abc123", sample_graph_data)

        # Mock the Firestore query chain
        mock_query = Mock()
        mock_query.limit.return_value.stream.return_value = [doc]
        mock_db.collection.return_value.where.return_value = mock_query

        result = find_deal_by_identifier(mock_db, "ZIMU001234AB")
        assert result == "deal_abc123"

    def test_returns_none_when_not_found(self, mock_db):
        """Should return None when no match."""
        mock_query = Mock()
        mock_query.limit.return_value.stream.return_value = []
        mock_db.collection.return_value.where.return_value = mock_query

        result = find_deal_by_identifier(mock_db, "NONEXISTENT123")
        assert result is None

    def test_follows_merged_into(self, mock_db, mock_graph_doc):
        """Should follow merged_into pointer to primary deal."""
        merged_data = {
            "deal_id": "deal_old",
            "merged_into": "deal_primary",
            "bl_numbers": ["ZIMU001234AB"],
        }
        doc = mock_graph_doc("deal_old", merged_data)

        mock_query = Mock()
        mock_query.limit.return_value.stream.return_value = [doc]
        mock_db.collection.return_value.where.return_value = mock_query

        result = find_deal_by_identifier(mock_db, "ZIMU001234AB")
        assert result == "deal_primary"

    def test_searches_scalar_fields(self, mock_db, mock_graph_doc, sample_graph_data):
        """Should search client_ref and internal_file_ref."""
        doc = mock_graph_doc("deal_abc123", sample_graph_data)

        # First N array queries return empty, then scalar query returns match
        call_count = [0]
        def mock_where(field, op, value):
            call_count[0] += 1
            q = Mock()
            # Only return match for client_ref == "FILE-001"
            if field == "client_ref" and value == "FILE-001":
                q.limit.return_value.stream.return_value = [doc]
            else:
                q.limit.return_value.stream.return_value = []
            return q

        mock_db.collection.return_value.where = mock_where
        result = find_deal_by_identifier(mock_db, "FILE-001")
        assert result == "deal_abc123"

    def test_handles_firestore_exception(self, mock_db):
        """Should handle Firestore errors gracefully."""
        mock_db.collection.return_value.where.side_effect = Exception("Connection timeout")
        result = find_deal_by_identifier(mock_db, "ZIMU001234AB")
        assert result is None


# ═══════════════════════════════════════════
#  TEST: register_identifier
# ═══════════════════════════════════════════

class TestRegisterIdentifier:
    def test_none_db(self):
        assert register_identifier(None, "deal_1", "bl_numbers", "BL123") is False

    def test_empty_value(self, mock_db):
        assert register_identifier(mock_db, "deal_1", "bl_numbers", "") is False

    def test_none_value(self, mock_db):
        assert register_identifier(mock_db, "deal_1", "bl_numbers", None) is False

    def test_whitespace_value(self, mock_db):
        assert register_identifier(mock_db, "deal_1", "bl_numbers", "   ") is False

    def test_creates_new_graph_entry(self, mock_db):
        """Should create a new graph doc if one doesn't exist."""
        doc = Mock()
        doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = doc

        result = register_identifier(mock_db, "deal_new", "bl_numbers", "BL999")
        assert result is True
        mock_db.collection.return_value.document.return_value.set.assert_called_once()

    def test_appends_to_existing_array(self, mock_db, sample_graph_data):
        """Should append new BL to existing array."""
        doc = Mock()
        doc.exists = True
        doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = doc

        result = register_identifier(mock_db, "deal_abc123", "bl_numbers", "NEWBL999")
        assert result is True
        mock_db.collection.return_value.document.return_value.update.assert_called_once()

    def test_dedup_existing_value(self, mock_db, sample_graph_data):
        """Should return False if value already in array."""
        doc = Mock()
        doc.exists = True
        doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = doc

        result = register_identifier(mock_db, "deal_abc123", "bl_numbers", "ZIMU001234AB")
        assert result is False

    def test_sets_scalar_field(self, mock_db, sample_graph_data):
        """Should set client_name as a scalar field."""
        doc = Mock()
        doc.exists = True
        doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = doc

        result = register_identifier(mock_db, "deal_abc123", "client_name", "New Client")
        assert result is True

    def test_scalar_no_change(self, mock_db, sample_graph_data):
        """Should return False if scalar value unchanged."""
        doc = Mock()
        doc.exists = True
        doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = doc

        result = register_identifier(mock_db, "deal_abc123", "client_name", "Acme Import Ltd")
        assert result is False

    def test_handles_exception(self, mock_db):
        """Should handle Firestore errors gracefully."""
        mock_db.collection.return_value.document.return_value.get.side_effect = Exception("DB error")
        result = register_identifier(mock_db, "deal_1", "bl_numbers", "BL999")
        assert result is False


# ═══════════════════════════════════════════
#  TEST: merge_deals
# ═══════════════════════════════════════════

class TestMergeDeals:
    def test_none_db(self):
        assert merge_deals(None, "a", "b") is False

    def test_same_deal(self, mock_db):
        assert merge_deals(mock_db, "deal_1", "deal_1") is False

    def test_empty_deal_ids(self, mock_db):
        assert merge_deals(mock_db, "", "deal_1") is False
        assert merge_deals(mock_db, "deal_1", "") is False

    def test_merge_combines_arrays(self, mock_db):
        """Arrays from B should be merged into A."""
        data_a = _empty_graph("deal_a")
        data_a["bl_numbers"] = ["BL-A"]
        data_a["container_numbers"] = ["CONT0000001"]
        data_a["confidence"] = 0.7

        data_b = _empty_graph("deal_b")
        data_b["bl_numbers"] = ["BL-B"]
        data_b["container_numbers"] = ["CONT0000001", "CONT0000002"]
        data_b["invoice_numbers"] = ["INV-B"]
        data_b["confidence"] = 0.9

        doc_a = Mock()
        doc_a.exists = True
        doc_a.to_dict.return_value = data_a

        doc_b = Mock()
        doc_b.exists = True
        doc_b.to_dict.return_value = data_b

        # Stable mock refs for each deal_id
        ref_a = Mock()
        ref_a.get.return_value = doc_a
        ref_b = Mock()
        ref_b.get.return_value = doc_b

        def mock_get_doc(deal_id):
            if deal_id == "deal_a":
                return ref_a
            elif deal_id == "deal_b":
                return ref_b
            return Mock()

        mock_db.collection.return_value.document = mock_get_doc

        result = merge_deals(mock_db, "deal_a", "deal_b")
        assert result is True

        # Verify A was written with merged data
        assert ref_a.set.called
        merged_data = ref_a.set.call_args[0][0]
        assert "BL-A" in merged_data["bl_numbers"]
        assert "BL-B" in merged_data["bl_numbers"]
        assert "CONT0000002" in merged_data["container_numbers"]
        assert "INV-B" in merged_data["invoice_numbers"]
        assert merged_data["confidence"] == 0.9  # Higher of the two

        # Verify B was marked as merged
        assert ref_b.set.called
        merged_marker = ref_b.set.call_args[0][0]
        assert merged_marker["merged_into"] == "deal_a"

    def test_merge_fills_empty_scalars(self, mock_db):
        """Empty scalars in A should be filled from B."""
        data_a = _empty_graph("deal_a")
        data_a["client_name"] = ""

        data_b = _empty_graph("deal_b")
        data_b["client_name"] = "Acme Corp"
        data_b["client_ref"] = "REF-999"

        doc_a = Mock()
        doc_a.exists = True
        doc_a.to_dict.return_value = data_a

        doc_b = Mock()
        doc_b.exists = True
        doc_b.to_dict.return_value = data_b

        ref_a = Mock()
        ref_a.get.return_value = doc_a
        ref_b = Mock()
        ref_b.get.return_value = doc_b

        def mock_get_doc(deal_id):
            if deal_id == "deal_a":
                return ref_a
            elif deal_id == "deal_b":
                return ref_b
            return Mock()

        mock_db.collection.return_value.document = mock_get_doc

        result = merge_deals(mock_db, "deal_a", "deal_b")
        assert result is True

        merged_data = ref_a.set.call_args[0][0]
        assert merged_data["client_name"] == "Acme Corp"
        assert merged_data["client_ref"] == "REF-999"

    def test_merge_b_not_exists(self, mock_db):
        """Should return False if B doesn't exist."""
        doc_a = Mock()
        doc_a.exists = True
        doc_a.to_dict.return_value = _empty_graph("deal_a")

        doc_b = Mock()
        doc_b.exists = False

        ref_a = Mock()
        ref_a.get.return_value = doc_a
        ref_b = Mock()
        ref_b.get.return_value = doc_b

        def mock_get_doc(deal_id):
            if deal_id == "deal_a":
                return ref_a
            elif deal_id == "deal_b":
                return ref_b
            return Mock()

        mock_db.collection.return_value.document = mock_get_doc

        result = merge_deals(mock_db, "deal_a", "deal_b")
        assert result is False


# ═══════════════════════════════════════════
#  TEST: link_email_to_deal
# ═══════════════════════════════════════════

class TestLinkEmailToDeal:
    def test_none_db(self):
        result = link_email_to_deal(None, {"subject": "test"})
        assert result["deal_id"] is None

    def test_none_email_data(self, mock_db):
        result = link_email_to_deal(mock_db, None)
        assert result["deal_id"] is None

    def test_extracts_identifiers(self, mock_db):
        """Should extract identifiers even if no match found."""
        # All queries return empty
        mock_query = Mock()
        mock_query.limit.return_value.stream.return_value = []
        mock_db.collection.return_value.where.return_value = mock_query

        email = {
            "subject": "Re: Shipment BL ZIMU001234AB",
            "body": "Container MSKU9070323 at port",
        }
        result = link_email_to_deal(mock_db, email)
        assert result["deal_id"] is None
        assert "ZIMU001234AB" in result["identifiers"]["bl_numbers"]
        assert "MSKU9070323" in result["identifiers"]["container_numbers"]

    def test_matches_by_bl(self, mock_db, mock_graph_doc, sample_graph_data):
        """Should match deal by BL number."""
        doc = mock_graph_doc("deal_abc123", sample_graph_data)

        call_count = [0]
        def mock_where(field, op, value):
            call_count[0] += 1
            q = Mock()
            # Match on bl_numbers array_contains
            if field == "bl_numbers" and value == "ZIMU001234AB":
                q.limit.return_value.stream.return_value = [doc]
            else:
                q.limit.return_value.stream.return_value = []
            return q

        mock_db.collection.return_value.where = mock_where
        # Mock the register side
        reg_doc = Mock()
        reg_doc.exists = True
        reg_doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = reg_doc

        email = {
            "subject": "Shipment update",
            "body": "B/L ZIMU001234AB - new invoice INV-NEW-002",
        }
        result = link_email_to_deal(mock_db, email)
        assert result["deal_id"] == "deal_abc123"
        assert "bl_number:ZIMU001234AB" in result["matched_by"]

    def test_matches_by_thread_id(self, mock_db, mock_graph_doc, sample_graph_data):
        """Should match deal by email thread ID (priority 0)."""
        doc = mock_graph_doc("deal_abc123", sample_graph_data)

        def mock_where(field, op, value):
            q = Mock()
            if field == "email_thread_ids" and value == "thread_xyz":
                q.limit.return_value.stream.return_value = [doc]
            else:
                q.limit.return_value.stream.return_value = []
            return q

        mock_db.collection.return_value.where = mock_where
        reg_doc = Mock()
        reg_doc.exists = True
        reg_doc.to_dict.return_value = sample_graph_data
        mock_db.collection.return_value.document.return_value.get.return_value = reg_doc

        email = {
            "subject": "Update",
            "body": "some body text",
            "thread_id": "thread_xyz",
        }
        result = link_email_to_deal(mock_db, email)
        assert result["deal_id"] == "deal_abc123"
        assert result["matched_by"] == "email_thread_id"

    def test_no_match_returns_none(self, mock_db):
        """Should return None when no deal matches."""
        mock_query = Mock()
        mock_query.limit.return_value.stream.return_value = []
        mock_db.collection.return_value.where.return_value = mock_query

        email = {
            "subject": "Hello",
            "body": "No identifiers here",
        }
        result = link_email_to_deal(mock_db, email)
        assert result["deal_id"] is None
        assert result["matched_by"] == ""


# ═══════════════════════════════════════════
#  TEST: register_deal_from_tracker
# ═══════════════════════════════════════════

class TestRegisterDealFromTracker:
    def test_none_db(self):
        assert register_deal_from_tracker(None, "deal_1", {}) == 0

    def test_empty_deal_data(self, mock_db):
        assert register_deal_from_tracker(mock_db, "deal_1", {}) == 0

    def test_registers_bl_and_containers(self, mock_db):
        """Should register BL, containers, booking from tracker deal."""
        # First call: doc doesn't exist (creates new)
        # Subsequent calls: doc exists (appends)
        call_num = [0]
        def mock_get():
            call_num[0] += 1
            doc = Mock()
            if call_num[0] == 1:
                doc.exists = False
            else:
                doc.exists = True
                data = _empty_graph("deal_1")
                data["bl_numbers"] = ["ZIMU001234AB"]
                doc.to_dict.return_value = data
            return doc

        mock_db.collection.return_value.document.return_value.get = mock_get
        mock_db.collection.return_value.document.return_value.set = Mock()
        mock_db.collection.return_value.document.return_value.update = Mock()

        deal_data = {
            "bol_number": "ZIMU001234AB",
            "awb_number": "",
            "booking_number": "BKG999",
            "containers": ["MSKU9070323", "CSQU3054383"],
            "source_email_thread_id": "thread_abc",
            "consignee": "Test Importer",
        }

        added = register_deal_from_tracker(mock_db, "deal_1", deal_data)
        # BL + booking + 2 containers + thread_id = at least 5 register attempts
        assert added >= 1  # At least the BL was registered

    def test_skips_empty_fields(self, mock_db):
        """Should skip empty string fields."""
        doc = Mock()
        doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = doc
        mock_db.collection.return_value.document.return_value.set = Mock()

        deal_data = {
            "bol_number": "",
            "awb_number": "",
            "booking_number": "",
            "containers": [],
        }
        added = register_deal_from_tracker(mock_db, "deal_1", deal_data)
        assert added == 0


# ═══════════════════════════════════════════
#  TEST: _empty_graph
# ═══════════════════════════════════════════

class TestEmptyGraph:
    def test_has_all_fields(self):
        graph = _empty_graph("deal_test")
        assert graph["deal_id"] == "deal_test"
        assert graph["bl_numbers"] == []
        assert graph["booking_refs"] == []
        assert graph["awb_numbers"] == []
        assert graph["container_numbers"] == []
        assert graph["invoice_numbers"] == []
        assert graph["po_numbers"] == []
        assert graph["packing_list_refs"] == []
        assert graph["email_thread_ids"] == []
        assert graph["client_name"] == ""
        assert graph["client_ref"] == ""
        assert graph["internal_file_ref"] == ""
        assert graph["job_order_number"] == ""
        assert graph["file_number"] == ""
        assert graph["import_number"] == ""
        assert graph["export_number"] == ""
        assert graph["seped_number"] == ""
        assert graph["email_subjects"] == []
        assert isinstance(graph["last_updated"], str)
        assert graph["confidence"] == 0.5

    def test_all_array_fields_are_lists(self):
        graph = _empty_graph("test")
        for field in IDENTIFIER_FIELDS:
            assert isinstance(graph[field], list), f"{field} should be a list"

    def test_all_scalar_id_fields_are_strings(self):
        graph = _empty_graph("test")
        for field in SCALAR_ID_FIELDS:
            assert isinstance(graph[field], str), f"{field} should be a string"


# ═══════════════════════════════════════════
#  TEST: Constants
# ═══════════════════════════════════════════

class TestConstants:
    def test_collection_name(self):
        assert COLLECTION == "deal_identity_graph"

    def test_identifier_fields_count(self):
        assert len(IDENTIFIER_FIELDS) == 8

    def test_scalar_id_fields_count(self):
        assert len(SCALAR_ID_FIELDS) == 7

    def test_identifier_fields_are_strings(self):
        for f in IDENTIFIER_FIELDS:
            assert isinstance(f, str)
            assert f.endswith("s")  # All plural

    def test_scalar_fields_include_new_ids(self):
        assert "job_order_number" in SCALAR_ID_FIELDS
        assert "file_number" in SCALAR_ID_FIELDS
        assert "import_number" in SCALAR_ID_FIELDS
        assert "export_number" in SCALAR_ID_FIELDS
        assert "seped_number" in SCALAR_ID_FIELDS

    def test_learned_patterns_collection(self):
        assert LEARNED_PATTERNS_COLLECTION == "learned_identifier_patterns"


# ═══════════════════════════════════════════
#  TEST: Edge cases and real-world patterns
# ═══════════════════════════════════════════

class TestRealWorldPatterns:
    """Test with realistic email content from logistics industry."""

    def test_typical_arrival_notice(self):
        subject = "Notice of Arrival - M/V ZIM SHANGHAI V.123W"
        body = """
        Notice of Goods Arrival

        B/L: ZIMU001234AB
        Vessel: ZIM SHANGHAI
        Voyage: 123W
        ETA: 22/02/2026

        Containers:
        MSKU9070323 - 40HC - Gross: 12,500 KG
        """
        result = extract_identifiers_from_email(subject, body)
        assert "ZIMU001234AB" in result["bl_numbers"]
        assert "MSKU9070323" in result["container_numbers"]

    def test_invoice_with_po(self):
        subject = "Invoice INV-2026-042 for PO-12345"
        body = """
        Commercial Invoice

        Invoice No: INV-2026-042
        P/O Number: PO-12345
        Your Ref: FILE-888

        Item: Electric motors
        Amount: USD 15,000.00
        """
        result = extract_identifiers_from_email(subject, body)
        assert "INV-2026-042" in result["invoice_numbers"]
        assert "PO-12345" in result["po_numbers"]
        assert result["client_ref"] == "FILE-888"

    def test_hebrew_forwarded_email(self):
        subject = "Fwd: Re: FW: משלוח מסין - B/L ZIMU999888AB"
        body = "שטר מטען ZIMU999888AB\nמכולה MSKU9070323"
        result = extract_identifiers_from_email(subject, body)
        assert result["email_subject_normalized"] == "משלוח מסין - B/L ZIMU999888AB"
        assert "ZIMU999888AB" in result["bl_numbers"]

    def test_air_freight_email(self):
        subject = "AWB 020-12345678 - Shipment ready"
        body = """
        Air Waybill: 020-12345678
        Flight: LY 008
        Origin: Shanghai (PVG)
        Destination: Tel Aviv (TLV)
        """
        result = extract_identifiers_from_email(subject, body)
        assert len(result["awb_numbers"]) >= 1

    def test_booking_confirmation(self):
        subject = "Booking Confirmation EBKG123456789"
        body = """
        Booking confirmed.
        Booking: EBKG123456789
        Vessel: MSC ANNA
        Container type: 2x40HC
        """
        result = extract_identifiers_from_email(subject, body)
        assert "EBKG123456789" in result["booking_refs"]

    def test_internal_file_and_seped(self):
        """RPA PORT internal workflow: file number + seped."""
        subject = "Re: תיק 412345 - ספד 87654321"
        body = """
        שלום,
        תיק מספר 412345
        ספד 87654321
        רישיון יבוא IMP-2026-555
        פקודת עבודה WO-999
        """
        result = extract_identifiers_from_email(subject, body)
        assert result["file_number"] == "412345"
        assert result["seped_number"] == "87654321"
        assert result["import_number"] == "IMP-2026-555"
        assert result["job_order_number"] == "WO-999"

    def test_export_file_number(self):
        """Export file numbers start with 6."""
        body = "תיק מספר 678901 - רישיון יצוא EXP-2026-010"
        result = extract_identifiers_from_email("", body)
        assert result["file_number"] == "678901"
        assert result["export_number"] == "EXP-2026-010"
