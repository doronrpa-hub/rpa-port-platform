"""
Pytest Configuration and Shared Fixtures
"""
import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add lib directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# MOCK FIRESTORE
# ============================================================

@pytest.fixture
def mock_db():
    """Create a mock Firestore database"""
    db = Mock()
    return db


@pytest.fixture
def mock_firestore_doc():
    """Create a mock Firestore document"""
    def _create(doc_id, data):
        doc = Mock()
        doc.id = doc_id
        doc.to_dict.return_value = data
        return doc
    return _create


@pytest.fixture
def sample_tariff_data():
    """Sample tariff data for testing"""
    return [
        {
            "code": "8516.31",
            "description_he": "מייבשי שיער",
            "description_en": "Hair drying apparatus",
            "chapter": "85",
            "duty_rate": "12%"
        },
        {
            "code": "8516.32",
            "description_he": "מכשירים אחרים לטיפוח שיער",
            "description_en": "Other hair-dressing apparatus",
            "chapter": "85",
            "duty_rate": "12%"
        },
        {
            "code": "8509.40",
            "description_he": "מטחנות מזון ומערבלים",
            "description_en": "Food grinders and mixers",
            "chapter": "85",
            "duty_rate": "8%"
        }
    ]


@pytest.fixture
def sample_ministry_data():
    """Sample ministry requirements data"""
    return [
        {
            "ministry": "משרד הבריאות",
            "ministry_en": "Ministry of Health",
            "requirements": ["אישור יבוא", "תעודת בטיחות"],
            "categories": ["medical", "cosmetics", "food"]
        },
        {
            "ministry": "משרד התקשורת",
            "ministry_en": "Ministry of Communications",
            "requirements": ["אישור תקשורת", "תקן אלחוטי"],
            "categories": ["electronics", "wireless"]
        }
    ]


# ============================================================
# MOCK GRAPH API
# ============================================================

@pytest.fixture
def mock_graph_secrets():
    """Mock Graph API secrets"""
    return {
        'RCB_GRAPH_CLIENT_ID': 'test-client-id',
        'RCB_GRAPH_CLIENT_SECRET': 'test-secret',
        'RCB_GRAPH_TENANT_ID': 'test-tenant'
    }


@pytest.fixture
def sample_email():
    """Sample email data"""
    return {
        "id": "msg123",
        "subject": "Test Shipment 12345",
        "from": {
            "emailAddress": {
                "name": "Doron Test",
                "address": "doron@test.com"
            }
        },
        "receivedDateTime": "2026-02-05T12:00:00Z",
        "body": {
            "content": "Please classify attached documents"
        }
    }


@pytest.fixture
def sample_attachment():
    """Sample PDF attachment data"""
    import base64
    return {
        "id": "att123",
        "name": "invoice.pdf",
        "contentType": "application/pdf",
        "contentBytes": base64.b64encode(b"fake pdf content").decode(),
        "size": 1024
    }


# ============================================================
# MOCK CLAUDE API
# ============================================================

@pytest.fixture
def mock_claude_response():
    """Create a mock Claude API response"""
    def _create(text):
        return Mock(
            status_code=200,
            json=lambda: {
                "content": [{"text": text}]
            }
        )
    return _create


# ============================================================
# TEST HELPERS
# ============================================================

@pytest.fixture
def hebrew_text_samples():
    """Hebrew text samples for testing"""
    return {
        "product": "מייבש שיער חשמלי פיליפס",
        "description": "מכשיר לייבוש שיער עם 3 מהירויות",
        "greeting": "שלום רב",
        "mixed": "מכשיר Philips דגם BHD123"
    }


# ============================================================
# PYTEST CONFIGURATION
# ============================================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
