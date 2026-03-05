"""Tests for Customs Agents Law module (_customs_agents_law.py)."""
import pytest


class TestCustomsAgentsArticles:
    """Verify article structure and content."""

    def test_article_count(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        assert len(CUSTOMS_AGENTS_ARTICLES) >= 35

    def test_all_articles_have_required_fields(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        for art_id, art in CUSTOMS_AGENTS_ARTICLES.items():
            assert "ch" in art, f"Art {art_id} missing ch"
            assert "t" in art, f"Art {art_id} missing t"
            assert "s" in art, f"Art {art_id} missing s"
            assert "f" in art, f"Art {art_id} missing f"
            assert len(art["f"]) > 0, f"Art {art_id} has empty text"

    def test_article_1_definitions(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        art = CUSTOMS_AGENTS_ARTICLES["1"]
        assert "סוכן מכס" in art["f"]
        assert "פעולת מכס" in art["f"]
        assert "המנהל" in art["f"]

    def test_article_4_registration(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        art = CUSTOMS_AGENTS_ARTICLES["4"]
        assert "23 שנה" in art["f"]
        assert "התמחה" in art["f"]
        assert "בחינות" in art["f"]

    def test_article_27_penalties(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        art = CUSTOMS_AGENTS_ARTICLES["27"]
        assert "מאסר שלוש שנים" in art["f"]
        assert "מאסר שנה" in art["f"]

    def test_hebrew_letter_articles_exist(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        assert "3א" in CUSTOMS_AGENTS_ARTICLES
        assert "3ב" in CUSTOMS_AGENTS_ARTICLES
        assert "24א" in CUSTOMS_AGENTS_ARTICLES
        assert "24ב" in CUSTOMS_AGENTS_ARTICLES
        assert "29א" in CUSTOMS_AGENTS_ARTICLES


class TestCustomsAgentsChapters:
    """Verify chapter structure."""

    def test_chapter_count(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_CHAPTERS
        assert len(CUSTOMS_AGENTS_CHAPTERS) >= 7

    def test_chapter_2_registration(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_CHAPTERS
        ch = CUSTOMS_AGENTS_CHAPTERS["2"]
        assert ch["title_en"] == "Registration of Customs Agents"
        assert "4" in ch["articles"]
        assert "5" in ch["articles"]

    def test_chapter_6_1_forwarders(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_CHAPTERS
        ch = CUSTOMS_AGENTS_CHAPTERS["6.1"]
        assert "משלחים בינלאומיים" in ch["title_he"]
        assert "24א" in ch["articles"]

    def test_all_articles_mapped_to_chapters(self):
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES, CUSTOMS_AGENTS_CHAPTERS
        all_ch_articles = set()
        for ch_data in CUSTOMS_AGENTS_CHAPTERS.values():
            all_ch_articles.update(ch_data["articles"])
        for art_id in CUSTOMS_AGENTS_ARTICLES:
            assert art_id in all_ch_articles, f"Art {art_id} not in any chapter"


class TestSearchCustomsAgentsLaw:
    """Verify search function."""

    def test_search_article_by_number(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("סעיף 4")
        assert r["found"] is True
        assert r["type"] == "customs_agents_article"
        assert r["article_id"] == "4"

    def test_search_article_bare_number(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("27")
        assert r["found"] is True
        assert r["article_id"] == "27"

    def test_search_hebrew_letter_article(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("סעיף 3א")
        assert r["found"] is True
        assert r["article_id"] == "3א"

    def test_search_chapter(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("פרק 3")
        assert r["found"] is True
        assert r["type"] == "customs_agents_chapter"
        assert len(r["articles"]) >= 4

    def test_search_keyword_penalties(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("עונשין מאסר")
        assert r["found"] is True
        assert any(res["article_id"] == "27" for res in r["results"])

    def test_search_keyword_registration(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("רישום")
        assert r["found"] is True
        assert len(r["results"]) >= 3

    def test_search_keyword_forwarder(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("משלח בינלאומי")
        assert r["found"] is True
        assert any(res["article_id"] == "24א" for res in r["results"])

    def test_search_nonexistent(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("xyznonexistent")
        assert r["found"] is False
        assert len(r["results"]) == 0

    def test_search_english_keyword(self):
        from lib._customs_agents_law import search_customs_agents_law
        r = search_customs_agents_law("article 11")
        assert r["found"] is True
        assert r["article_id"] == "11"


class TestDocumentRegistry:
    """Verify document registry entry."""

    def test_customs_agents_law_complete(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        doc = DOCUMENT_REGISTRY["customs_agents_law"]
        assert doc["status"] == "complete"
        assert doc["python_module"] == "lib._customs_agents_law"
        assert doc["article_count"] == 35

    def test_customs_agents_law_nevo_url(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        doc = DOCUMENT_REGISTRY["customs_agents_law"]
        assert "nevo.co.il" in doc["source_url"]
        assert "265_023" in doc["source_url"]
