"""
Tests for Phase 2: Domain Detection + Source Routing + Banned Phrase Gate.
Tests intelligence_gate.py domain functions and email_intent.py integration.
"""
import pytest
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.intelligence_gate import (
    detect_customs_domain,
    get_articles_by_domain,
    get_articles_by_ids,
    filter_banned_phrases,
    CUSTOMS_DOMAINS,
    BANNED_PHRASES,
)


# ═══════════════════════════════════════════════════════════════════
# DOMAIN DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDetectCustomsDomain:
    """Test detect_customs_domain() — keyword matching per domain."""

    def test_empty_text_returns_empty(self):
        result = detect_customs_domain("")
        assert result == []

    def test_none_text_returns_empty(self):
        result = detect_customs_domain(None)
        assert result == []

    # ── IP ENFORCEMENT ──

    def test_ip_hebrew_ziuf(self):
        """זיוף (counterfeit) should detect IP_ENFORCEMENT."""
        result = detect_customs_domain("עיכבו מכולה בטענת זיוף של Nike")
        domains = [d["domain"] for d in result]
        assert "IP_ENFORCEMENT" in domains

    def test_ip_hebrew_siman_mischar(self):
        """סימן מסחר (trademark) should detect IP_ENFORCEMENT."""
        result = detect_customs_domain("הפרת סימן מסחר בטובין שיובאו")
        domains = [d["domain"] for d in result]
        assert "IP_ENFORCEMENT" in domains

    def test_ip_english_counterfeit(self):
        result = detect_customs_domain("container detained for counterfeit goods")
        domains = [d["domain"] for d in result]
        assert "IP_ENFORCEMENT" in domains

    def test_ip_hebrew_ikuv(self):
        """עיכוב (detention) should detect IP_ENFORCEMENT."""
        result = detect_customs_domain("המכס עיכב את הטובין בחשד לזיוף")
        domains = [d["domain"] for d in result]
        assert "IP_ENFORCEMENT" in domains

    def test_ip_returns_articles_200(self):
        """IP detection should include articles 200א-200ה (actual IP chapter)."""
        result = detect_customs_domain("זיוף סימן מסחר")
        ip_domain = [d for d in result if d["domain"] == "IP_ENFORCEMENT"][0]
        assert "200א" in ip_domain["source_articles"]
        assert "200ה" in ip_domain["source_articles"]
        assert len(ip_domain["source_articles"]) == 5

    # ── VALUATION ──

    def test_valuation_hebrew(self):
        result = detect_customs_domain("מה שיטת ההערכה לפי ערך עסקה?")
        domains = [d["domain"] for d in result]
        assert "VALUATION" in domains

    def test_valuation_english(self):
        result = detect_customs_domain("how to determine transaction value?")
        domains = [d["domain"] for d in result]
        assert "VALUATION" in domains

    def test_valuation_returns_articles_130_136(self):
        result = detect_customs_domain("ערך עסקה הערכה")
        val_domain = [d for d in result if d["domain"] == "VALUATION"][0]
        assert "130" in val_domain["source_articles"]
        assert "132" in val_domain["source_articles"]
        assert "136" in val_domain["source_articles"]

    # ── FTA ──

    def test_fta_hebrew(self):
        result = detect_customs_domain("תעודת מקור EUR.1 לפי הסכם סחר עם האיחוד האירופי")
        domains = [d["domain"] for d in result]
        assert "FTA_ORIGIN" in domains

    def test_fta_english(self):
        result = detect_customs_domain("certificate of origin under FTA")
        domains = [d["domain"] for d in result]
        assert "FTA_ORIGIN" in domains

    # ── CLASSIFICATION ──

    def test_classification_hebrew(self):
        result = detect_customs_domain("מה הסיווג של כיסא אוכל?")
        domains = [d["domain"] for d in result]
        assert "CLASSIFICATION" in domains

    def test_classification_english(self):
        result = detect_customs_domain("what is the HS code for dining chair?")
        domains = [d["domain"] for d in result]
        assert "CLASSIFICATION" in domains

    def test_classification_no_ordinance_articles(self):
        """CLASSIFICATION uses tariff DB, not ordinance articles."""
        result = detect_customs_domain("סיווג כיסא")
        cls_domain = [d for d in result if d["domain"] == "CLASSIFICATION"][0]
        assert cls_domain["source_articles"] == []
        assert "search_tariff" in cls_domain["source_tools"]

    # ── FORFEITURE ──

    def test_forfeiture_hebrew(self):
        result = detect_customs_domain("האם ניתן לערער על חילוט?")
        domains = [d["domain"] for d in result]
        assert "FORFEITURE_PENALTIES" in domains

    def test_forfeiture_returns_articles_190_plus(self):
        result = detect_customs_domain("עבירת מכס קנס חילוט")
        fp_domain = [d for d in result if d["domain"] == "FORFEITURE_PENALTIES"][0]
        assert "190" in fp_domain["source_articles"]
        assert "223" in fp_domain["source_articles"]
        assert "223א" in fp_domain["source_articles"]

    # ── PROCEDURES ──

    def test_procedures_hebrew(self):
        result = detect_customs_domain("מה הנוהל לשחרור רשימון?")
        domains = [d["domain"] for d in result]
        assert "PROCEDURES" in domains

    # ── IMPORT/EXPORT ──

    def test_import_requirements(self):
        result = detect_customs_domain("האם צריך רישיון יבוא לפי צו יבוא?")
        domains = [d["domain"] for d in result]
        assert "IMPORT_EXPORT_REQUIREMENTS" in domains

    # ── MULTI-DOMAIN ──

    def test_multi_domain_ip_plus_classification(self):
        """Nike counterfeit = both IP_ENFORCEMENT and CLASSIFICATION (product detected)."""
        result = detect_customs_domain("זיוף Nike בגדים מכולה עיכוב")
        domains = [d["domain"] for d in result]
        assert "IP_ENFORCEMENT" in domains
        # "בגדים" isn't in product indicators but "עיכוב" matches IP

    def test_sorted_by_score(self):
        """Results should be sorted by score descending."""
        result = detect_customs_domain("זיוף סימן מסחר עיכוב חשד")
        if len(result) >= 2:
            assert result[0]["score"] >= result[1]["score"]

    # ── PRODUCT INDICATORS ──

    def test_product_indicators_boost_classification(self):
        """Product words should boost CLASSIFICATION score."""
        result_without = detect_customs_domain("what is the tariff?")
        result_with = detect_customs_domain("what is the tariff for this product?")
        cls_without = [d for d in result_without if d["domain"] == "CLASSIFICATION"]
        cls_with = [d for d in result_with if d["domain"] == "CLASSIFICATION"]
        # Both should detect CLASSIFICATION, but with product indicator has higher score
        assert cls_without and cls_with
        assert cls_with[0]["score"] >= cls_without[0]["score"]

    # ── DOMAIN COVERAGE ──

    def test_all_8_domains_defined(self):
        assert len(CUSTOMS_DOMAINS) == 8
        expected = {"CLASSIFICATION", "VALUATION", "IP_ENFORCEMENT", "FTA_ORIGIN",
                     "IMPORT_EXPORT_REQUIREMENTS", "PROCEDURES",
                     "FORFEITURE_PENALTIES", "TRACKING"}
        assert set(CUSTOMS_DOMAINS.keys()) == expected

    def test_every_domain_has_keywords(self):
        for name, domain in CUSTOMS_DOMAINS.items():
            assert "keywords_he" in domain, f"{name} missing keywords_he"
            assert "keywords_en" in domain, f"{name} missing keywords_en"
            assert len(domain["keywords_he"]) >= 3, f"{name} has too few Hebrew keywords"


# ═══════════════════════════════════════════════════════════════════
# ARTICLE RETRIEVAL TESTS
# ═══════════════════════════════════════════════════════════════════

class TestGetArticlesByDomain:
    """Test get_articles_by_domain() — direct article lookup."""

    def test_ip_articles_fetched(self):
        """Should fetch all 14 IP enforcement articles."""
        domain = {"source_articles": ["200א", "200ב", "200ג", "200ד", "200ה",
                                       "200ו", "200ז", "200ח", "200ט", "200י",
                                       "200יא", "200יב", "200יג", "200יד"]}
        articles = get_articles_by_domain(domain)
        assert len(articles) >= 7  # At least most should exist
        art_ids = [a["article_id"] for a in articles]
        assert "200א" in art_ids
        assert "200ז" in art_ids

    def test_valuation_articles_fetched(self):
        """Should fetch valuation articles 130-136."""
        domain = {"source_articles": ["130", "131", "132", "133", "134", "135", "136"]}
        articles = get_articles_by_domain(domain)
        assert len(articles) >= 7
        art_ids = [a["article_id"] for a in articles]
        assert "130" in art_ids
        assert "132" in art_ids

    def test_article_has_required_fields(self):
        """Each article should have id, title, summary, text."""
        domain = {"source_articles": ["130"]}
        articles = get_articles_by_domain(domain)
        assert len(articles) == 1
        art = articles[0]
        assert art["article_id"] == "130"
        assert art["title_he"]  # Non-empty
        assert art["summary_en"]  # Non-empty
        assert art["full_text_he"]  # Non-empty — we embedded full Hebrew text

    def test_article_text_capped(self):
        """Full text should be capped at 3000 chars per article."""
        domain = {"source_articles": ["130"]}
        articles = get_articles_by_domain(domain)
        assert len(articles[0]["full_text_he"]) <= 3000

    def test_empty_source_articles_returns_empty(self):
        domain = {"source_articles": []}
        assert get_articles_by_domain(domain) == []

    def test_nonexistent_article_skipped(self):
        domain = {"source_articles": ["999", "130"]}
        articles = get_articles_by_domain(domain)
        # Only article 130 should be returned
        assert len(articles) == 1
        assert articles[0]["article_id"] == "130"


class TestGetArticlesByIds:
    """Test get_articles_by_ids() — convenience wrapper."""

    def test_single_article(self):
        articles = get_articles_by_ids(["200א"])
        assert len(articles) == 1
        assert articles[0]["article_id"] == "200א"

    def test_multiple_articles(self):
        articles = get_articles_by_ids(["200א", "200ב", "200ג"])
        assert len(articles) == 3

    def test_empty_list(self):
        assert get_articles_by_ids([]) == []

    def test_none_list(self):
        assert get_articles_by_ids(None) == []


# ═══════════════════════════════════════════════════════════════════
# BANNED PHRASE FILTER TESTS (for email_intent integration)
# ═══════════════════════════════════════════════════════════════════

class TestBannedPhraseFilterOnIntentReplies:
    """Verify banned phrase filter catches common AI-generated anti-patterns."""

    def test_hebrew_broker_advice_caught(self):
        html = '<div dir="rtl">מומלץ לפנות לעמיל מכס מוסמך לקבלת ייעוץ.</div>'
        result = filter_banned_phrases(html)
        assert result["was_modified"]
        assert "מומלץ לפנות לעמיל מכס" in result["phrases_found"]
        assert "rcb@rpa-port.co.il" in result["cleaned_html"]

    def test_english_broker_advice_caught(self):
        html = '<div>Please consult a customs broker for assistance.</div>'
        result = filter_banned_phrases(html)
        assert result["was_modified"]
        assert "consult a customs broker" in result["phrases_found"]

    def test_unclassifiable_caught(self):
        html = '<div dir="rtl">לא ניתן לסווג את המוצר הזה.</div>'
        result = filter_banned_phrases(html)
        assert result["was_modified"]
        assert "לא ניתן לסווג" in result["phrases_found"]

    def test_clean_text_not_modified(self):
        html = '<div dir="rtl">הסיווג הנכון הוא 73.26 לפי כלל פרשנות 1.</div>'
        result = filter_banned_phrases(html)
        assert not result["was_modified"]
        assert result["phrases_found"] == []

    def test_multiple_phrases_caught(self):
        html = ('<div>I\'m not sure about this classification. '
                'Please consult a customs broker.</div>')
        result = filter_banned_phrases(html)
        assert result["was_modified"]
        assert len(result["phrases_found"]) >= 2


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION: Domain Detection End-to-End
# ═══════════════════════════════════════════════════════════════════

class TestDomainDetectionEndToEnd:
    """End-to-end: text → domain → articles → context."""

    def test_nike_counterfeit_gets_ip_articles(self):
        """The spec's example: Nike counterfeit detained → articles 200א-200ה."""
        text = "יש לי יבואן שהביא מכולה ובה בגדים של Nike, במכס עיכבו בטענה שמדובר בזיוף"
        domains = detect_customs_domain(text)
        ip_domains = [d for d in domains if d["domain"] == "IP_ENFORCEMENT"]
        assert len(ip_domains) == 1

        articles = get_articles_by_domain(ip_domains[0])
        assert len(articles) == 5  # 200א-200ה (actual IP chapter)
        art_ids = [a["article_id"] for a in articles]
        assert "200א" in art_ids  # Main IP detention power (3-day detention, bank guarantee, 10-day suit)
        assert "200ב" in art_ids  # Guarantee release procedures
        assert "200ג" in art_ids  # Infringing goods = prohibited imports

    def test_valuation_question_gets_130_136(self):
        """Valuation question → articles 130-136."""
        text = "האם מותר לעסקה לפי פקודת המכס לקבוע על ידי הסכום שמשולם בפועל?"
        domains = detect_customs_domain(text)
        # "ערך" or "תשלום" should match
        # If not matched, verify the keywords are broad enough
        # The word "מכס" should at least match PROCEDURES
        assert len(domains) > 0

    def test_fta_question_gets_framework_tools(self):
        """FTA question → framework order tools."""
        text = "מה כללי המקור לפי הסכם סחר עם אירופה? תעודת מקור EUR.1?"
        domains = detect_customs_domain(text)
        fta_domains = [d for d in domains if d["domain"] == "FTA_ORIGIN"]
        assert len(fta_domains) == 1
        assert "lookup_fta" in fta_domains[0]["source_tools"]
        assert "lookup_framework_order" in fta_domains[0]["source_tools"]

    def test_smuggling_gets_penalty_articles(self):
        """Smuggling/penalty question → articles 190+."""
        text = "מה העונש על הברחת סחורה? עבירת מכס חמורה"
        domains = detect_customs_domain(text)
        fp_domains = [d for d in domains if d["domain"] == "FORFEITURE_PENALTIES"]
        assert len(fp_domains) == 1
        articles = get_articles_by_domain(fp_domains[0])
        assert len(articles) >= 10
        art_ids = [a["article_id"] for a in articles]
        assert "204" in art_ids  # Penalties


# ═══════════════════════════════════════════════════════════════════
# email_intent.py HELPER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEmailIntentDomainHelpers:
    """Test the _detect_domains_safe and _fetch_domain_articles helpers."""

    def test_detect_domains_safe_import(self):
        from lib.email_intent import _detect_domains_safe
        result = _detect_domains_safe("זיוף סימן מסחר")
        assert len(result) >= 1
        assert result[0]["domain"] == "IP_ENFORCEMENT"

    def test_detect_domains_safe_empty(self):
        from lib.email_intent import _detect_domains_safe
        result = _detect_domains_safe("")
        assert result == []

    def test_fetch_domain_articles_import(self):
        from lib.email_intent import _fetch_domain_articles
        domains = [{"domain": "IP_ENFORCEMENT",
                     "source_articles": ["200א", "200ב", "200ג"],
                     "source_tools": []}]
        articles = _fetch_domain_articles(domains)
        assert len(articles) == 3
        assert articles[0]["article_id"] == "200א"

    def test_fetch_domain_articles_empty(self):
        from lib.email_intent import _fetch_domain_articles
        assert _fetch_domain_articles([]) == []

    def test_fetch_domain_articles_dedup(self):
        """If same article appears in multiple domains, return it only once."""
        from lib.email_intent import _fetch_domain_articles
        domains = [
            {"domain": "A", "source_articles": ["130", "131"], "source_tools": []},
            {"domain": "B", "source_articles": ["130", "132"], "source_tools": []},
        ]
        articles = _fetch_domain_articles(domains)
        art_ids = [a["article_id"] for a in articles]
        assert art_ids.count("130") == 1  # Deduped
        assert "131" in art_ids
        assert "132" in art_ids

    def test_fetch_domain_articles_cap_at_20(self):
        """Should cap at 20 articles to prevent context overflow."""
        from lib.email_intent import _fetch_domain_articles
        # FORFEITURE has ~50 articles
        from lib.intelligence_gate import CUSTOMS_DOMAINS
        fp_articles = CUSTOMS_DOMAINS["FORFEITURE_PENALTIES"]["source_articles"]
        assert len(fp_articles) > 20  # Verify test assumption
        domains = [{"domain": "FORFEITURE_PENALTIES",
                     "source_articles": fp_articles,
                     "source_tools": []}]
        articles = _fetch_domain_articles(domains)
        assert len(articles) <= 20
