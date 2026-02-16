"""
Unit Tests for pc_agent_runner.py
Run: pytest tests/test_pc_agent_runner.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock, patch

from lib.pc_agent_runner import (
    run_pending_tasks,
    _execute_download,
    _execute_research_gap,
    _search_directive,
    _search_preruling,
    _search_tariff_data,
    _try_resolve_knowledge_gap,
    _mark_failed,
    _increment_attempts,
)


# ============================================================
# HELPERS
# ============================================================

def _mock_task_doc(task_id, data):
    """Create a mock Firestore document for a task."""
    doc = Mock()
    doc.id = task_id
    doc.to_dict.return_value = data
    return doc


def _mock_db_with_tasks(tasks):
    """Create a mock Firestore client that returns given tasks."""
    db = Mock()
    task_docs = [_mock_task_doc(tid, tdata) for tid, tdata in tasks]

    # pc_agent_tasks collection
    task_col = Mock()
    task_col.where.return_value = task_col
    task_col.limit.return_value = task_col
    task_col.stream.return_value = iter(task_docs)

    # Document access
    def mock_document(doc_id):
        doc_ref = Mock()
        doc_ref.update = Mock()
        doc_ref.set = Mock()
        # For _increment_attempts — return a mock doc
        mock_get = Mock()
        mock_get.exists = True
        for tid, tdata in tasks:
            if tid == doc_id:
                mock_get.to_dict.return_value = tdata
                break
        else:
            mock_get.to_dict.return_value = {"attempts": 0, "max_attempts": 3}
        doc_ref.get.return_value = mock_get
        return doc_ref

    task_col.document = mock_document

    def mock_collection(name):
        if name == "pc_agent_tasks":
            return task_col
        # Default mock for other collections
        other = Mock()
        other.where.return_value = other
        other.limit.return_value = other
        other.stream.return_value = iter([])
        other.document.return_value = Mock(
            get=Mock(return_value=Mock(exists=False)),
            update=Mock(),
            set=Mock(),
        )
        other.add = Mock()
        return other

    db.collection = mock_collection
    return db


# ============================================================
# RUN PENDING TASKS
# ============================================================

class TestRunPendingTasks:

    def test_empty_queue(self):
        db = _mock_db_with_tasks([])
        result = run_pending_tasks(db)
        assert result["processed"] == 0
        assert result["executed"] == 0
        assert result["failed"] == 0

    def test_skips_browser_tasks(self):
        tasks = [
            ("task1", {
                "type": "",
                "requires_browser": True,
                "url": "https://gov.il/pdf",
                "attempts": 0,
                "max_attempts": 3,
            }),
        ]
        db = _mock_db_with_tasks(tasks)
        result = run_pending_tasks(db)
        assert result["processed"] == 1
        assert result["skipped_browser"] == 1
        assert result["executed"] == 0

    def test_marks_max_attempts_as_failed(self):
        tasks = [
            ("task1", {
                "type": "",
                "requires_browser": False,
                "url": "https://example.com/file",
                "attempts": 3,
                "max_attempts": 3,
            }),
        ]
        db = _mock_db_with_tasks(tasks)
        result = run_pending_tasks(db)
        assert result["processed"] == 1
        assert result["failed"] == 1
        assert result["details"][0]["reason"] == "Max attempts reached"

    @patch("lib.pc_agent_runner._execute_download")
    def test_routes_non_browser_to_download(self, mock_dl):
        mock_dl.return_value = True
        tasks = [
            ("task1", {
                "type": "",
                "requires_browser": False,
                "url": "https://example.com/data",
                "attempts": 0,
                "max_attempts": 3,
            }),
        ]
        db = _mock_db_with_tasks(tasks)
        result = run_pending_tasks(db)
        assert mock_dl.called
        assert result["executed"] == 1

    @patch("lib.pc_agent_runner._execute_research_gap")
    def test_routes_research_gap(self, mock_rg):
        mock_rg.return_value = True
        tasks = [
            ("task1", {
                "type": "research_gap",
                "gap_type": "missing_directive",
                "hs_code": "8516.31",
                "chapter": "85",
                "attempts": 0,
                "max_attempts": 3,
            }),
        ]
        db = _mock_db_with_tasks(tasks)
        result = run_pending_tasks(db)
        assert mock_rg.called
        assert result["executed"] == 1

    def test_max_tasks_respected(self):
        db = Mock()
        col = Mock()
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([])
        db.collection.return_value = col

        run_pending_tasks(db, max_tasks=5)
        col.limit.assert_called_with(5)

    def test_db_error_returns_empty(self):
        db = Mock()
        col = Mock()
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.side_effect = Exception("Firestore down")
        db.collection.return_value = col

        result = run_pending_tasks(db)
        assert result["processed"] == 0


# ============================================================
# EXECUTE DOWNLOAD
# ============================================================

class TestExecuteDownload:

    @patch("lib.pc_agent_runner.requests.get")
    def test_successful_download(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>some content here</html>"
        mock_resp.content = b"<html>some content here</html>"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_resp

        db = _mock_db_with_tasks([("dl_test", {
            "url": "https://example.com/page",
            "source_name": "Test Source",
            "auto_tags": ["test"],
            "attempts": 0,
        })])

        result = _execute_download(db, "dl_test", {
            "url": "https://example.com/page",
            "source_name": "Test Source",
            "auto_tags": ["test"],
            "attempts": 0,
        })
        assert result is True

    @patch("lib.pc_agent_runner.requests.get")
    def test_http_error(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        db = _mock_db_with_tasks([("dl_err", {"attempts": 0, "max_attempts": 3})])
        result = _execute_download(db, "dl_err", {
            "url": "https://example.com/missing",
            "attempts": 0,
        })
        assert result is False

    def test_no_url_fails(self):
        db = _mock_db_with_tasks([("dl_nourl", {"attempts": 0, "max_attempts": 3})])
        result = _execute_download(db, "dl_nourl", {"url": "", "attempts": 0})
        assert result is False

    @patch("lib.pc_agent_runner.requests.get")
    def test_timeout_fails(self, mock_get):
        import requests
        mock_get.side_effect = requests.Timeout("timeout")

        db = _mock_db_with_tasks([("dl_timeout", {"attempts": 0, "max_attempts": 3})])
        result = _execute_download(db, "dl_timeout", {
            "url": "https://slow.example.com",
            "attempts": 0,
        })
        assert result is False

    @patch("lib.pc_agent_runner.requests.get")
    def test_connection_error_fails(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("refused")

        db = _mock_db_with_tasks([("dl_conn", {"attempts": 0, "max_attempts": 3})])
        result = _execute_download(db, "dl_conn", {
            "url": "https://down.example.com",
            "attempts": 0,
        })
        assert result is False


# ============================================================
# EXECUTE RESEARCH GAP
# ============================================================

class TestExecuteResearchGap:

    def test_directive_found_locally(self):
        db = Mock()
        task_col = Mock()
        task_col.document.return_value = Mock(update=Mock())
        db.collection.return_value = task_col

        # tariff_chapters has directive data
        def mock_collection(name):
            col = Mock()
            col.document.return_value = Mock(update=Mock())
            if name == "pc_agent_tasks":
                return col
            elif name == "tariff_chapters":
                doc = Mock()
                doc.exists = True
                doc.to_dict.return_value = {"directives": "Some directive text here"}
                col.document.return_value = Mock(
                    get=Mock(return_value=doc),
                    update=Mock(),
                )
                return col
            elif name == "knowledge_gaps":
                col.where.return_value = col
                col.limit.return_value = col
                col.stream.return_value = iter([])
                return col
            else:
                col.document.return_value = Mock(
                    get=Mock(return_value=Mock(exists=False)),
                    update=Mock(),
                )
                return col

        db.collection = mock_collection

        result = _execute_research_gap(db, "gap1", {
            "gap_type": "missing_directive",
            "hs_code": "",
            "chapter": "85",
            "description": "test",
            "attempts": 0,
        })
        assert result is True

    def test_gap_not_found_returns_false(self):
        db = Mock()

        def mock_collection(name):
            col = Mock()
            col.document.return_value = Mock(
                get=Mock(return_value=Mock(exists=False)),
                update=Mock(),
            )
            col.where.return_value = col
            col.limit.return_value = col
            col.stream.return_value = iter([])
            return col

        db.collection = mock_collection

        result = _execute_research_gap(db, "gap2", {
            "gap_type": "missing_preruling",
            "hs_code": "9999.99",
            "chapter": "99",
            "description": "nonexistent",
            "attempts": 0,
        })
        assert result is False


# ============================================================
# SEARCH HELPERS
# ============================================================

class TestSearchDirective:

    def test_found_in_tariff_chapters(self):
        db = Mock()

        def mock_collection(name):
            col = Mock()
            if name == "tariff_chapters":
                doc = Mock()
                doc.exists = True
                doc.to_dict.return_value = {"classification_notes": "Note for chapter 85"}
                col.document.return_value = Mock(
                    get=Mock(return_value=doc),
                    update=Mock(),
                )
            elif name == "pc_agent_tasks":
                col.document.return_value = Mock(update=Mock())
            else:
                col.document.return_value = Mock(
                    get=Mock(return_value=Mock(exists=False)),
                    update=Mock(),
                )
            return col

        db.collection = mock_collection
        assert _search_directive(db, "t1", "", "85") is True

    def test_found_in_chapter_notes(self):
        db = Mock()

        def mock_collection(name):
            col = Mock()
            if name == "tariff_chapters":
                doc = Mock()
                doc.exists = True
                doc.to_dict.return_value = {}  # No directives
                col.document.return_value = Mock(
                    get=Mock(return_value=doc),
                    update=Mock(),
                )
            elif name == "chapter_notes":
                doc = Mock()
                doc.exists = True
                doc.to_dict.return_value = {"preamble": "Chapter 85 covers..."}
                col.document.return_value = Mock(
                    get=Mock(return_value=doc),
                    update=Mock(),
                )
            elif name == "pc_agent_tasks":
                col.document.return_value = Mock(update=Mock())
            else:
                col.document.return_value = Mock(
                    get=Mock(return_value=Mock(exists=False)),
                    update=Mock(),
                )
            return col

        db.collection = mock_collection
        assert _search_directive(db, "t1", "", "85") is True

    def test_not_found_anywhere(self):
        db = Mock()

        def mock_collection(name):
            col = Mock()
            col.document.return_value = Mock(
                get=Mock(return_value=Mock(exists=False)),
                update=Mock(),
            )
            return col

        db.collection = mock_collection
        # Patch requests to avoid actual HTTP
        with patch("lib.pc_agent_runner.requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=404, text="")
            assert _search_directive(db, "t1", "", "99") is False

    def test_empty_chapter_returns_false(self):
        db = Mock()
        assert _search_directive(db, "t1", "", "") is False


class TestSearchPreruling:

    def test_found_in_knowledge_base(self):
        db = Mock()
        col = Mock()
        doc = Mock()
        doc.to_dict.return_value = {
            "content": {"hs_code": "8516.31", "ruling": "Pre-ruling text"},
            "category": "pre_rulings",
        }
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([doc])

        task_col = Mock()
        task_col.document.return_value = Mock(update=Mock())

        def mock_collection(name):
            if name == "knowledge_base":
                return col
            return task_col

        db.collection = mock_collection
        assert _search_preruling(db, "t1", "8516.31", "") is True

    def test_not_found(self):
        db = Mock()
        col = Mock()
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([])
        db.collection.return_value = col
        assert _search_preruling(db, "t1", "9999.99", "") is False


class TestSearchTariffData:

    def test_found_in_tariff(self):
        db = Mock()
        col = Mock()
        doc = Mock()
        doc.to_dict.return_value = {"hs_code": "8516.31", "description": "Hair dryers"}
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([doc])

        task_col = Mock()
        task_col.document.return_value = Mock(update=Mock())

        def mock_collection(name):
            if name == "tariff":
                return col
            return task_col

        db.collection = mock_collection
        assert _search_tariff_data(db, "t1", "8516") is True

    def test_empty_search_term(self):
        db = Mock()
        assert _search_tariff_data(db, "t1", "") is False


# ============================================================
# KNOWLEDGE GAP RESOLUTION
# ============================================================

class TestTryResolveKnowledgeGap:

    def test_resolves_matching_gap(self):
        db = Mock()
        gap_doc = Mock()
        gap_doc.id = "gap_123"
        gap_doc.to_dict.return_value = {
            "hs_code": "8516.31",
            "type": "missing_directive",
            "status": "open",
        }

        col = Mock()
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([gap_doc])
        col.document.return_value = Mock(update=Mock())
        db.collection.return_value = col

        _try_resolve_knowledge_gap(db, {
            "gap_type": "missing_directive",
            "hs_code": "8516.31",
            "description": "test",
        })

        # Should have called update on the gap
        col.document.assert_called_with("gap_123")

    def test_no_match_does_nothing(self):
        db = Mock()
        col = Mock()
        col.where.return_value = col
        col.limit.return_value = col
        col.stream.return_value = iter([])
        db.collection.return_value = col

        _try_resolve_knowledge_gap(db, {
            "gap_type": "missing_directive",
            "hs_code": "9999.99",
            "description": "",
        })

    def test_empty_task_does_nothing(self):
        db = Mock()
        _try_resolve_knowledge_gap(db, {
            "gap_type": "",
            "hs_code": "",
            "description": "",
        })
        db.collection.assert_not_called()


# ============================================================
# STATUS HELPERS
# ============================================================

class TestMarkFailed:

    def test_updates_status(self):
        db = Mock()
        doc_ref = Mock()
        db.collection.return_value = Mock(document=Mock(return_value=doc_ref))

        _mark_failed(db, "task1", "Timeout error")
        doc_ref.update.assert_called_once()
        args = doc_ref.update.call_args[0][0]
        assert args["status"] == "failed"
        assert args["last_error"] == "Timeout error"

    def test_handles_error_gracefully(self):
        db = Mock()
        db.collection.side_effect = Exception("DB error")
        # Should not raise
        _mark_failed(db, "task1", "test")


class TestIncrementAttempts:

    def test_sets_retry_when_under_max(self):
        db = Mock()
        doc_ref = Mock()
        doc_data = Mock()
        doc_data.exists = True
        doc_data.to_dict.return_value = {"attempts": 0, "max_attempts": 3}
        doc_ref.get.return_value = doc_data
        db.collection.return_value = Mock(document=Mock(return_value=doc_ref))

        _increment_attempts(db, "task1", "Some error")
        args = doc_ref.update.call_args[0][0]
        assert args["status"] == "retry"
        assert args["attempts"] == 1

    def test_sets_failed_at_max(self):
        db = Mock()
        doc_ref = Mock()
        doc_data = Mock()
        doc_data.exists = True
        doc_data.to_dict.return_value = {"attempts": 2, "max_attempts": 3}
        doc_ref.get.return_value = doc_data
        db.collection.return_value = Mock(document=Mock(return_value=doc_ref))

        _increment_attempts(db, "task1", "Final error")
        args = doc_ref.update.call_args[0][0]
        assert args["status"] == "failed"
        assert args["attempts"] == 3

    def test_truncates_long_error(self):
        db = Mock()
        doc_ref = Mock()
        doc_data = Mock()
        doc_data.exists = True
        doc_data.to_dict.return_value = {"attempts": 0, "max_attempts": 3}
        doc_ref.get.return_value = doc_data
        db.collection.return_value = Mock(document=Mock(return_value=doc_ref))

        long_error = "x" * 1000
        _increment_attempts(db, "task1", long_error)
        args = doc_ref.update.call_args[0][0]
        assert len(args["last_error"]) <= 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
