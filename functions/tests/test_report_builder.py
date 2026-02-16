"""
Unit Tests for report_builder.py
Run: pytest tests/test_report_builder.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock

from lib.report_builder import (
    build_legal_strength_badge,
    build_justification_html,
    build_challenge_html,
    build_gaps_summary_html,
    build_cross_check_badge,
    build_report_document,
    build_full_daily_digest,
    _gather_digest_stats,
    _build_section1_html,
    _build_section2_html,
    _build_section3_html,
    _build_section4_html,
    _build_section5_html,
    _escape,
)


# ============================================================
# LEGAL STRENGTH BADGE
# ============================================================

class TestLegalStrengthBadge:

    def test_strong_badge(self):
        html = build_legal_strength_badge("strong", 85)
        assert "dcfce7" in html  # green background
        assert "85%" in html
        assert "חזק" in html

    def test_moderate_badge(self):
        html = build_legal_strength_badge("moderate", 60)
        assert "fef3c7" in html  # yellow background
        assert "60%" in html
        assert "בינוני" in html

    def test_weak_badge(self):
        html = build_legal_strength_badge("weak", 20)
        assert "fee2e2" in html  # red background
        assert "20%" in html
        assert "חלש" in html

    def test_unknown_defaults_to_weak(self):
        html = build_legal_strength_badge("unknown", 0)
        assert "חלש" in html

    def test_zero_coverage(self):
        html = build_legal_strength_badge("strong", 0)
        assert "0%" in html


# ============================================================
# JUSTIFICATION HTML
# ============================================================

class TestJustificationHtml:

    def test_renders_chain(self):
        justification = {
            "chain": [
                {
                    "step": 1,
                    "decision": "Chapter 85 — Electrical machines",
                    "source_type": "heading_to_chapter",
                    "source_text": "This chapter covers...",
                    "has_source": True,
                },
                {
                    "step": 2,
                    "decision": "Heading 85.16",
                    "source_type": "tariff",
                    "source_text": "Hair dryers",
                    "has_source": True,
                },
            ],
            "legal_strength": "strong",
            "coverage_pct": 80,
        }
        html = build_justification_html(justification)
        assert "שרשרת נימוק משפטי" in html
        assert "Chapter 85" in html
        assert "85.16" in html
        assert "#22c55e" in html  # green dot for has_source=True

    def test_empty_chain(self):
        html = build_justification_html({"chain": []})
        assert html == ""

    def test_no_chain_key(self):
        html = build_justification_html({})
        assert html == ""

    def test_missing_source_shows_red_dot(self):
        justification = {
            "chain": [
                {
                    "step": 1,
                    "decision": "Chapter 84",
                    "has_source": False,
                    "source_text": "",
                },
            ],
            "legal_strength": "weak",
            "coverage_pct": 20,
        }
        html = build_justification_html(justification)
        assert "#ef4444" in html  # red dot

    def test_html_escaping(self):
        justification = {
            "chain": [
                {
                    "step": 1,
                    "decision": "Chapter <script>alert(1)</script>",
                    "has_source": True,
                    "source_text": "text with <b>html</b>",
                },
            ],
            "legal_strength": "moderate",
            "coverage_pct": 50,
        }
        html = build_justification_html(justification)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ============================================================
# CHALLENGE HTML
# ============================================================

class TestChallengeHtml:

    def test_challenge_passed(self):
        challenge = {
            "alternatives": [
                {
                    "chapter": "84",
                    "reason_for": "Could be a machine",
                    "reason_against": "Chapter 85 exclusion applies",
                },
            ],
            "challenge_passed": True,
            "unresolved_count": 0,
        }
        html = build_challenge_html(challenge)
        assert "הסיווג עמד בבדיקה" in html
        assert "dcfce7" in html  # green

    def test_challenge_open(self):
        challenge = {
            "alternatives": [
                {
                    "chapter": "39",
                    "reason_for": "Plastic article",
                    "reason_against": "",
                },
            ],
            "challenge_passed": False,
            "unresolved_count": 1,
        }
        html = build_challenge_html(challenge)
        assert "חלופות פתוחות" in html
        assert "fef3c7" in html  # yellow

    def test_no_alternatives(self):
        html = build_challenge_html({"alternatives": []})
        assert html == ""

    def test_max_3_shown(self):
        alts = [
            {"chapter": str(i).zfill(2), "reason_for": f"Alt {i}", "reason_against": ""}
            for i in range(5)
        ]
        challenge = {
            "alternatives": alts,
            "challenge_passed": False,
            "unresolved_count": 5,
        }
        html = build_challenge_html(challenge)
        assert "CH 00" in html
        assert "CH 01" in html
        assert "CH 02" in html
        assert "CH 04" not in html  # 4th and 5th hidden


# ============================================================
# GAPS SUMMARY
# ============================================================

class TestGapsSummary:

    def test_shows_high_priority(self):
        gaps = [
            {"type": "missing_preamble", "priority": "high", "description": "test"},
            {"type": "missing_directive", "priority": "medium", "description": "test"},
        ]
        html = build_gaps_summary_html(gaps)
        assert "1 פערי ידע זוהו" in html

    def test_no_high_priority(self):
        gaps = [
            {"type": "missing_preruling", "priority": "low", "description": "test"},
        ]
        html = build_gaps_summary_html(gaps)
        assert html == ""

    def test_empty_gaps(self):
        html = build_gaps_summary_html([])
        assert html == ""

    def test_critical_and_high(self):
        gaps = [
            {"type": "a", "priority": "critical"},
            {"type": "b", "priority": "high"},
            {"type": "c", "priority": "high"},
        ]
        html = build_gaps_summary_html(gaps)
        assert "3 פערי ידע" in html


# ============================================================
# CROSS-CHECK BADGE
# ============================================================

class TestCrossCheckBadge:

    def test_tier_1(self):
        html = build_cross_check_badge({"cross_check_tier": 1})
        assert "T1" in html
        assert "Unanimous" in html

    def test_tier_3(self):
        html = build_cross_check_badge({"cross_check_tier": 3})
        assert "T3" in html
        assert "Conflict" in html

    def test_no_tier(self):
        html = build_cross_check_badge({})
        assert html == ""

    def test_tier_zero(self):
        html = build_cross_check_badge({"cross_check_tier": 0})
        assert html == ""


# ============================================================
# REPORT DOCUMENT
# ============================================================

class TestBuildReportDocument:

    def test_basic_document(self):
        results = {
            "agents": {
                "classification": {
                    "classifications": [
                        {
                            "hs_code": "8516.31",
                            "item": "Hair dryer",
                            "confidence": "high",
                            "justification": {
                                "legal_strength": "strong",
                                "coverage_pct": 80,
                                "sources_found": 4,
                                "sources_needed": 5,
                                "gaps": [],
                            },
                            "challenge": {
                                "challenge_passed": True,
                                "chapters_checked": 2,
                            },
                        }
                    ]
                }
            }
        }
        invoice_data = {
            "direction": "import",
            "seller": "Acme Corp",
            "buyer": "Test Ltd",
            "bl_number": "BL123",
        }

        doc = build_report_document(results, "RCB-ABC123", "test@test.com", invoice_data)

        assert doc["tracking_code"] == "RCB-ABC123"
        assert doc["to_email"] == "test@test.com"
        assert doc["items_count"] == 1
        assert doc["strength_summary"]["strong"] == 1
        assert doc["items"][0]["legal_strength"] == "strong"
        assert doc["items"][0]["challenge_passed"] is True
        assert "created_at" in doc

    def test_with_invoice_validation(self):
        results = {"agents": {"classification": {"classifications": []}}}
        invoice_data = {"direction": "import"}
        validation = {"score": 85, "is_valid": True}

        doc = build_report_document(results, "X", "a@b.com", invoice_data, validation)

        assert doc["invoice_score"] == 85
        assert doc["invoice_valid"] is True

    def test_with_cross_check(self):
        results = {
            "agents": {"classification": {"classifications": []}},
            "cross_check": [{"tier": 1}, {"tier": 2}],
        }
        invoice_data = {}

        doc = build_report_document(results, "X", "a@b.com", invoice_data)

        assert doc["cross_check_tiers"] == [1, 2]
        assert doc["cross_check_avg"] == 1.5


# ============================================================
# ESCAPE UTILITY
# ============================================================

class TestEscape:

    def test_html_chars(self):
        assert _escape("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"

    def test_ampersand(self):
        assert _escape("a & b") == "a &amp; b"

    def test_quotes(self):
        assert _escape('"hello"') == "&quot;hello&quot;"

    def test_empty(self):
        assert _escape("") == ""

    def test_none(self):
        assert _escape(None) == ""


# ============================================================
# DAILY DIGEST — SECTION BUILDERS (Assignment 13)
# ============================================================

class TestSection1Summary:

    def test_renders_metrics(self):
        stats = {
            "reports": 5, "items_classified": 12, "emails_processed": 20,
            "deals_tracked": 3, "cross_check_total": 10, "cross_check_t1": 7,
            "strong": 8, "moderate": 3, "weak": 1,
            "cross_check_t2": 2, "cross_check_t3": 1, "cross_check_t4": 0,
        }
        html = _build_section1_html(stats)
        assert "5" in html  # reports
        assert "12" in html  # items
        assert "70%" in html  # agreement (7/10)
        assert "סיכום יומי" in html

    def test_zero_cross_checks(self):
        stats = {
            "reports": 1, "items_classified": 2, "emails_processed": 3,
            "deals_tracked": 0, "cross_check_total": 0, "cross_check_t1": 0,
            "strong": 0, "moderate": 0, "weak": 0,
            "cross_check_t2": 0, "cross_check_t3": 0, "cross_check_t4": 0,
        }
        html = _build_section1_html(stats)
        assert "N/A" in html


class TestSection2Questions:

    def test_renders_questions(self):
        stats = {
            "pupil_questions": 2,
            "_questions_data": [
                {
                    "question_he": "Is this chapter 84 or 85?",
                    "context": "Electric motor for pump",
                    "primary_hs": "8501.10",
                    "type": "chapter_dispute",
                },
                {
                    "question_he": "Missing preamble for chapter 39",
                    "context": "Plastic container",
                    "primary_hs": "3923.10",
                    "type": "knowledge_gap",
                },
            ],
        }
        html = _build_section2_html(stats)
        assert "שאלות תלמיד (2)" in html
        assert "Q1." in html
        assert "Q2." in html
        assert "8501.10" in html
        assert "chapter dispute" in html

    def test_no_questions(self):
        stats = {"pupil_questions": 0, "_questions_data": []}
        html = _build_section2_html(stats)
        assert html == ""


class TestSection3Gaps:

    def test_renders_gaps(self):
        stats = {
            "gaps_open": 5, "gaps_filled": 3,
            "_open_gaps_data": [
                {"type": "missing_directive", "description": "No directive for 8516", "priority": "high"},
                {"type": "missing_preamble", "description": "Preamble chapter 39 empty", "priority": "critical"},
            ],
        }
        html = _build_section3_html(stats)
        assert "5 פתוחים" in html
        assert "3 הושלמו אתמול" in html
        assert "[HIGH]" in html
        assert "[CRITICAL]" in html

    def test_no_gaps(self):
        stats = {"gaps_open": 0, "gaps_filled": 0, "_open_gaps_data": []}
        html = _build_section3_html(stats)
        assert html == ""


class TestSection4Enrichment:

    def test_renders_enrichment(self):
        stats = {
            "enrichment": {
                "processed": 10, "filled": 6, "failed": 2, "skipped": 2,
                "details": [
                    {"action": "filled", "description": "Chapter 85 preamble found"},
                    {"action": "could_not_fill", "description": "Directive 8516 not available"},
                    {"action": "flagged_for_pc_agent", "description": "Pre-ruling for 3923"},
                ],
            }
        }
        html = _build_section4_html(stats)
        assert "העשרה אוטומטית" in html
        assert "10" in html  # processed
        assert "6" in html  # filled
        assert "Chapter 85 preamble" in html

    def test_no_enrichment(self):
        stats = {"enrichment": {}}
        html = _build_section4_html(stats)
        assert html == ""


class TestSection5Alerts:

    def test_renders_low_confidence(self):
        stats = {
            "low_confidence_items": [
                {"hs_code": "8516.31", "item": "Hair dryer", "strength": "weak", "tracking": "RCB-X123"},
            ],
            "cross_check_t3": 2, "cross_check_t4": 1,
            "pc_agent_pending": 3,
        }
        html = _build_section5_html(stats)
        assert "חריגים" in html
        assert "8516.31" in html
        assert "Hair dryer" in html
        assert "1 disagreements (T4)" in html
        assert "2 conflicts (T3)" in html
        assert "3 tasks pending" in html

    def test_no_alerts(self):
        stats = {
            "low_confidence_items": [],
            "cross_check_t3": 0, "cross_check_t4": 0,
            "pc_agent_pending": 0,
        }
        html = _build_section5_html(stats)
        assert html == ""


class TestFullDigest:

    def _mock_db(self):
        """Create a mock Firestore that returns empty collections."""
        db = Mock()
        empty_stream = Mock()
        empty_stream.stream.return_value = []
        empty_stream.limit.return_value = empty_stream
        db.collection.return_value = empty_stream
        empty_stream.where.return_value = empty_stream
        return db

    def test_builds_complete_html(self):
        db = self._mock_db()
        html, stats = build_full_daily_digest(db, "2026-02-15T00:00:00", "16/02/2026")
        assert "סיכום יומי" in html
        assert "16/02/2026" in html
        assert "RCB" in html
        assert isinstance(stats, dict)

    def test_returns_stats_dict(self):
        db = self._mock_db()
        _, stats = build_full_daily_digest(db, "2026-02-15T00:00:00", "16/02/2026")
        assert "reports" in stats
        assert "gaps_open" in stats
        assert "pupil_questions" in stats
        assert "emails_processed" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
