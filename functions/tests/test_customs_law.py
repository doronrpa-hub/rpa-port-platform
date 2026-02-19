"""Tests for customs_law.py and chapter_expertise.py — the broker's embedded brain."""
import pytest
from lib.customs_law import (
    CLASSIFICATION_METHODOLOGY,
    TARIFF_SECTIONS,
    VALID_SUPPLEMENTS,
    NONEXISTENT_SUPPLEMENTS,
    GIR_RULES,
    KNOWN_FAILURES,
    CORRECT_TERMS,
    WRONG_TERMS,
    CUSTOMS_ORDINANCE_ARTICLES,
    get_classification_methodology,
    get_gir_rule,
    get_chapter_section,
    get_applicable_supplements,
    get_ordinance_article,
    get_valuation_methods,
    format_legal_context_for_prompt,
)
from lib.chapter_expertise import (
    SEED_EXPERTISE,
    get_section_for_chapter,
    get_section_data,
)


# ── BLOCK 1: CLASSIFICATION_METHODOLOGY ──────────────────────────────────


class TestClassificationMethodology:
    """Phases 0-9 must all exist and have required structure."""

    def test_all_10_phases_exist(self):
        for i in range(10):
            assert i in CLASSIFICATION_METHODOLOGY, f"Phase {i} missing"

    def test_phase_0_case_type(self):
        p = CLASSIFICATION_METHODOLOGY[0]
        assert p["name"] == "Case Type Identification"
        assert "Import" in p["steps"][0]["detail"]
        all_text = " ".join(s["action"] + " " + s["detail"] for s in p["steps"])
        assert "נהלים" in all_text

    def test_phase_1_three_pillars_in_order(self):
        p = CLASSIFICATION_METHODOLOGY[1]
        step_actions = [s["action"] for s in p["steps"]]
        physical_idx = next(i for i, a in enumerate(step_actions) if "Physical" in a or "פיזיים" in a)
        essence_idx = next(i for i, a in enumerate(step_actions) if "Essence" in a or "מהות" in a)
        function_idx = next(i for i, a in enumerate(step_actions) if "Use" in a or "Function" in a or "שימוש" in a)
        assert physical_idx < essence_idx < function_idx, "Pillars must be Physical → Essence → Function"

    def test_phase_1_has_framework_order_and_rule3(self):
        p = CLASSIFICATION_METHODOLOGY[1]
        all_text = " ".join(s["action"] + " " + s["detail"] for s in p["steps"])
        assert "צו המסגרת" in all_text
        assert "3(א)" in all_text
        assert "3(ב)" in all_text
        assert "3(ג)" in all_text

    def test_phase_2_legal_hierarchy(self):
        p = CLASSIFICATION_METHODOLOGY[2]
        step_ids = [s["id"] for s in p["steps"]]
        assert "2.א" in step_ids
        assert "2.ב" in step_ids
        assert "2.ג" in step_ids
        assert "legal_warning" in p
        assert "סיווג רשלני" in p["legal_warning"]

    def test_phase_2_skipping_bet_warning(self):
        p = CLASSIFICATION_METHODOLOGY[2]
        assert "בר-ענישה" in p["legal_warning"]
        assert "ליקויים" in p["legal_warning"]

    def test_phase_3_read_haraisha_first(self):
        p = CLASSIFICATION_METHODOLOGY[3]
        first_step = p["steps"][0]
        assert "הראישה" in first_step["action"] or "preamble" in first_step["action"].lower()

    def test_phase_3_stop_at_full_code(self):
        p = CLASSIFICATION_METHODOLOGY[3]
        all_text = " ".join(s["detail"] for s in p["steps"])
        assert "XX.XX.XXXXXX/X" in all_text

    def test_phase_3_acherim_gate(self):
        p = CLASSIFICATION_METHODOLOGY[3]
        all_text = " ".join(s["detail"] for s in p["steps"])
        assert "אחרים" in all_text

    def test_phase_4_bilingual(self):
        p = CLASSIFICATION_METHODOLOGY[4]
        assert "English" in p["description"] or "ENGLISH" in p["description"]

    def test_phase_5_nine_sources(self):
        p = CLASSIFICATION_METHODOLOGY[5]
        assert len(p["sources"]) >= 9

    def test_phase_6_nine_invoice_fields(self):
        p = CLASSIFICATION_METHODOLOGY[6]
        assert len(p["invoice_fields"]) == 9

    def test_phase_6_fta_and_import_orders(self):
        p = CLASSIFICATION_METHODOLOGY[6]
        assert "fta_check" in p
        assert "import_orders" in p
        assert "צו יבוא חופשי" in p["import_orders"]

    def test_phase_7_multi_ai(self):
        p = CLASSIFICATION_METHODOLOGY[7]
        assert len(p["models"]) >= 3

    def test_phase_8_source_attribution(self):
        p = CLASSIFICATION_METHODOLOGY[8]
        assert len(p["required_sources"]) >= 8

    def test_phase_9_max_five_candidates(self):
        p = CLASSIFICATION_METHODOLOGY[9]
        all_text = " ".join(p["rules"])
        assert "5" in all_text

    def test_get_classification_methodology_returns_all(self):
        m = get_classification_methodology()
        assert len(m) == 10
        assert m is CLASSIFICATION_METHODOLOGY


# ── BLOCK 2: TARIFF_STRUCTURE ─────────────────────────────────────────────


class TestTariffStructure:
    """Sections I-XXII and supplements."""

    def test_22_sections_exist(self):
        assert len(TARIFF_SECTIONS) == 22

    def test_section_chapter_ranges_cover_1_to_99(self):
        all_chapters = set()
        for info in TARIFF_SECTIONS.values():
            lo, hi = info["chapters"]
            all_chapters.update(range(lo, hi + 1))
        # Chapter 77 is reserved but must be in range
        for ch in range(1, 100):
            assert ch in all_chapters, f"Chapter {ch} not covered by any section"

    def test_valid_supplements(self):
        assert 2 in VALID_SUPPLEMENTS
        assert 3 in VALID_SUPPLEMENTS
        assert 17 in VALID_SUPPLEMENTS

    def test_nonexistent_supplements(self):
        assert 11 in NONEXISTENT_SUPPLEMENTS
        assert 12 in NONEXISTENT_SUPPLEMENTS
        assert 13 in NONEXISTENT_SUPPLEMENTS
        for s in NONEXISTENT_SUPPLEMENTS:
            assert s not in VALID_SUPPLEMENTS


# ── BLOCK 3: GIR_RULES ───────────────────────────────────────────────────


class TestGIRRules:
    """All 10 GIR rules present and structured."""

    EXPECTED_RULE_IDS = ["1", "2a", "2b", "3a", "3b", "3c", "4", "5a", "5b", "6"]

    def test_all_gir_rules_exist(self):
        for rid in self.EXPECTED_RULE_IDS:
            assert rid in GIR_RULES, f"GIR rule {rid} missing"

    def test_gir_rules_have_required_fields(self):
        for rid, rule in GIR_RULES.items():
            assert "name" in rule, f"Rule {rid} missing name"
            assert "name_he" in rule, f"Rule {rid} missing name_he"
            assert "text" in rule, f"Rule {rid} missing text"
            assert "application" in rule, f"Rule {rid} missing application"

    def test_rule_3a_specificity(self):
        r = GIR_RULES["3a"]
        assert "specific" in r["text"].lower()

    def test_rule_3b_essential_character(self):
        r = GIR_RULES["3b"]
        assert "essential character" in r["text"].lower()

    def test_rule_3c_last_numerical(self):
        r = GIR_RULES["3c"]
        assert "last" in r["text"].lower()

    def test_get_gir_rule_found(self):
        r = get_gir_rule("3b")
        assert r["name"].startswith("Rule 3")

    def test_get_gir_rule_not_found(self):
        r = get_gir_rule("99")
        assert r == {}

    def test_rule_6_sub_heading(self):
        r = GIR_RULES["6"]
        assert "sub-heading" in r["text"].lower() or "subheading" in r["text"].lower()


# ── BLOCK 4: KNOWN_FAILURES ──────────────────────────────────────────────


class TestKnownFailures:
    """Documented failures must exist with required fields."""

    def test_at_least_5_failures(self):
        assert len(KNOWN_FAILURES) >= 5

    def test_failures_have_required_fields(self):
        for f in KNOWN_FAILURES:
            assert "id" in f
            assert "name" in f
            assert "root_cause" in f
            assert "correct_approach" in f
            assert "lesson" in f

    def test_kiwi_caviar_failure(self):
        f = next(x for x in KNOWN_FAILURES if "Kiwi" in x["name"] or "kiwi" in x["name"].lower())
        assert "caviar" in f["name"].lower() or "Caviar" in f["name"]

    def test_ouzo_failure(self):
        f = next(x for x in KNOWN_FAILURES if "Ouzo" in x["name"] or "ouzo" in x["name"].lower())
        assert "22.08" in f["correct_approach"]

    def test_tires_failure(self):
        f = next(x for x in KNOWN_FAILURES if "Tire" in x["name"] or "rubber" in x["name"].lower())
        assert "40.11" in f["correct_approach"] or "40.01" in f["correct_approach"]


# ── BLOCK 5: SEED_EXPERTISE (from chapter_expertise.py) ──────────────────


class TestSeedExpertise:
    """Section/chapter expertise data."""

    def test_22_sections_in_seed(self):
        assert len(SEED_EXPERTISE) == 22

    def test_all_sections_have_required_fields(self):
        for sid, data in SEED_EXPERTISE.items():
            assert "name_en" in data, f"Section {sid} missing name_en"
            assert "name_he" in data, f"Section {sid} missing name_he"
            assert "chapters" in data, f"Section {sid} missing chapters"
            assert "notes" in data, f"Section {sid} missing notes"
            assert "traps" in data, f"Section {sid} missing traps"

    def test_chapter_1_in_section_I(self):
        assert 1 in SEED_EXPERTISE["I"]["chapters"]

    def test_chapter_85_in_section_XVI(self):
        assert 85 in SEED_EXPERTISE["XVI"]["chapters"]

    def test_chapter_99_in_section_XXII(self):
        assert 99 in SEED_EXPERTISE["XXII"]["chapters"]

    def test_get_section_for_chapter(self):
        assert get_section_for_chapter(1) == "I"
        assert get_section_for_chapter(40) == "VII"
        assert get_section_for_chapter(85) == "XVI"
        assert get_section_for_chapter(97) == "XXI"
        assert get_section_for_chapter(99) == "XXII"

    def test_get_section_for_invalid_chapter(self):
        assert get_section_for_chapter(0) == ""
        assert get_section_for_chapter(200) == ""

    def test_get_section_data(self):
        data = get_section_data("XVI")
        assert "Machinery" in data["name_en"]

    def test_get_section_data_invalid(self):
        assert get_section_data("XXXIII") == {}


# ── BLOCK 6: Functions ───────────────────────────────────────────────────


class TestGetChapterSection:
    def test_chapter_1(self):
        assert get_chapter_section(1) == "I"

    def test_chapter_15(self):
        assert get_chapter_section(15) == "III"

    def test_chapter_71(self):
        assert get_chapter_section(71) == "XIV"

    def test_chapter_84(self):
        assert get_chapter_section(84) == "XVI"

    def test_chapter_93(self):
        assert get_chapter_section(93) == "XIX"

    def test_chapter_98(self):
        assert get_chapter_section(98) == "XXII"

    def test_chapter_out_of_range(self):
        result = get_chapter_section(200)
        assert result == ""


class TestGetApplicableSupplements:
    def test_returns_sorted_list(self):
        s = get_applicable_supplements(1)
        assert s == sorted(s)

    def test_does_not_include_nonexistent(self):
        s = get_applicable_supplements(1)
        for ne in NONEXISTENT_SUPPLEMENTS:
            assert ne not in s

    def test_includes_supplement_2(self):
        assert 2 in get_applicable_supplements(1)


class TestFormatLegalContextForPrompt:
    """The key function — output must be embeddable prompt text."""

    def test_returns_string(self):
        result = format_legal_context_for_prompt()
        assert isinstance(result, str)

    def test_contains_embedded_expertise_header(self):
        result = format_legal_context_for_prompt()
        assert "EMBEDDED EXPERTISE" in result

    def test_contains_gir_rules(self):
        result = format_legal_context_for_prompt()
        assert "GIR RULES" in result
        assert "Rule 3א" in result

    def test_contains_known_failures(self):
        result = format_legal_context_for_prompt()
        assert "KNOWN CLASSIFICATION FAILURES" in result
        assert "Kiwi" in result

    def test_contains_critical_reminders(self):
        result = format_legal_context_for_prompt()
        assert "סיווג רשלני" in result
        assert "XX.XX.XXXXXX/X" in result
        assert "אחרים" in result

    def test_contains_nonexistent_supplement_warning(self):
        result = format_legal_context_for_prompt()
        assert "11, 12, 13" in result

    def test_with_chapters_includes_section_expertise(self):
        result = format_legal_context_for_prompt(chapters=[84, 85])
        assert "Section XVI" in result
        assert "Machinery" in result

    def test_with_chapters_includes_traps(self):
        result = format_legal_context_for_prompt(chapters=[40])
        assert "Tire" in result or "tire" in result.lower()

    def test_with_phase_focuses_on_single_phase(self):
        result = format_legal_context_for_prompt(phase=2)
        assert "Gather Information" in result or "Legally Mandated" in result
        assert "LEGAL WARNING" in result

    def test_no_chapters_still_includes_all_sections(self):
        result = format_legal_context_for_prompt()
        # All 22 sections always present even without chapters arg
        assert "TARIFF SECTION & CHAPTER EXPERTISE (ALL 22 SECTIONS)" in result
        assert "Section I:" in result
        assert "Section XXII:" in result
        # No RELEVANT markers when no chapters passed
        assert ">>> RELEVANT <<<" not in result

    def test_includes_three_pillars_order(self):
        result = format_legal_context_for_prompt()
        assert "Physical" in result
        assert "Essence" in result
        assert "Function" in result

    def test_includes_legal_hierarchy(self):
        result = format_legal_context_for_prompt()
        assert "Invoice" in result or "א" in result
        assert "Research" in result or "ב" in result

    def test_multiple_chapters_dedup_sections(self):
        result = format_legal_context_for_prompt(chapters=[84, 85])
        # Both ch.84 and ch.85 are in Section XVI — section header should appear only once
        # All 22 sections always present; ch.84+85 both map to XVI so only one RELEVANT marker
        header_lines = [l for l in result.splitlines() if l.startswith("Section XVI:")]
        assert len(header_lines) == 1
        assert ">>> RELEVANT <<<" in header_lines[0]

    def test_output_reasonable_length(self):
        result = format_legal_context_for_prompt(chapters=[1, 40, 85])
        # All 22 sections + law articles — substantial but bounded
        assert 5000 < len(result) < 35000

    def test_contains_terminology_reminder(self):
        result = format_legal_context_for_prompt()
        assert "עמיל מכס" in result
        assert "סוכן מכס" in result
        assert "מתווך מכס" in result  # mentioned as the WRONG term to avoid


# ── BLOCK 7: TERMINOLOGY ─────────────────────────────────────────────────


class TestTerminology:
    """Correct Hebrew customs terminology constants."""

    def test_correct_terms_exist(self):
        assert "customs_broker" in CORRECT_TERMS
        assert "customs_agent" in CORRECT_TERMS

    def test_correct_broker_term(self):
        assert CORRECT_TERMS["customs_broker"] == "עמיל מכס"

    def test_correct_agent_term(self):
        assert CORRECT_TERMS["customs_agent"] == "סוכן מכס"

    def test_wrong_terms_mapped(self):
        assert "מתווך מכס" in WRONG_TERMS
        assert WRONG_TERMS["מתווך מכס"] == "עמיל מכס"

    def test_wrong_plural_mapped(self):
        assert "מתווכי מכס" in WRONG_TERMS
        assert WRONG_TERMS["מתווכי מכס"] == "עמילי מכס"

    def test_wrong_qualified_mapped(self):
        assert "מתווך מכס מוסמך" in WRONG_TERMS
        assert WRONG_TERMS["מתווך מכס מוסמך"] == "עמיל מכס מוסמך"


# ── BLOCK 8: CUSTOMS ORDINANCE ARTICLES ─────────────────────────────────


class TestCustomsOrdinanceArticles:
    """Structured summaries of key פקודת המכס articles."""

    EXPECTED_ARTICLE_GROUPS = ["1", "2", "24", "62-65g", "123a-b", "124-154", "168-169", "207-223", "223a-r"]

    def test_all_article_groups_exist(self):
        for group_id in self.EXPECTED_ARTICLE_GROUPS:
            assert group_id in CUSTOMS_ORDINANCE_ARTICLES, f"Article group {group_id} missing"

    def test_article_groups_have_name_he(self):
        for group_id, data in CUSTOMS_ORDINANCE_ARTICLES.items():
            assert "name_he" in data, f"Group {group_id} missing name_he"

    def test_article_groups_have_chapter(self):
        for group_id, data in CUSTOMS_ORDINANCE_ARTICLES.items():
            assert "chapter" in data, f"Group {group_id} missing chapter"

    def test_article_1_definitions(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["1"]
        defs = art["definitions"]
        assert "טובין חבי מכס" in defs
        assert "הברחה" in defs
        assert "סוכן מכס" in defs
        assert "מסי יבוא" in defs
        assert len(defs) >= 15

    def test_article_1_has_broker_note(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["1"]
        assert "broker_note" in art
        assert "בעל" in art["broker_note"]

    def test_article_62_import_declaration(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["62-65g"]
        assert "articles" in art
        assert "62" in art["articles"]
        assert "63" in art["articles"]
        assert "סוכן מכס" in art["articles"]["62"]["text"]

    def test_article_62_deadlines(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["62-65g"]
        text_63 = art["articles"]["63"]["text"]
        assert "3 חודשים" in text_63 or "שלושה חודשים" in text_63
        assert "45 ימים" in text_63 or "45" in text_63

    def test_article_123_liability(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["123a-b"]
        assert "123a" in art["articles"]
        assert "importer" in art["articles"]["123a"]["text"].lower()

    def test_article_130_valuation_methods(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        art_130 = art["key_articles"]["130"]
        methods = art_130["methods"]
        assert len(methods) == 7
        # Check methods are in correct order
        assert methods[0]["number"] == 1
        assert methods[6]["number"] == 7

    def test_valuation_method_1_is_transaction_value(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        m1 = art["key_articles"]["130"]["methods"][0]
        assert "Transaction Value" in m1["name_en"]
        assert "ערך עסקה" in m1["name_he"]
        assert m1["section"] == "132"

    def test_valuation_method_4_is_deductive(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        m4 = art["key_articles"]["130"]["methods"][3]
        assert "Deductive" in m4["name_en"]
        assert m4["section"] == "133ד"

    def test_valuation_method_5_is_computed(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        m5 = art["key_articles"]["130"]["methods"][4]
        assert "Computed" in m5["name_en"]
        assert m5["section"] == "133ה"

    def test_valuation_method_7_is_fallback(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        m7 = art["key_articles"]["130"]["methods"][6]
        assert "Fallback" in m7["name_en"]
        assert "GATT" in m7["description"]

    def test_article_132_transaction_value_conditions(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        art_132 = art["key_articles"]["132"]
        assert "special_relationships" in art_132
        assert "CONDITIONS" in art_132["text"] or "conditions" in art_132["text"].lower()

    def test_article_133_additions(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        art_133 = art["key_articles"]["133"]
        assert "additions" in art_133
        assert len(art_133["additions"]) >= 5
        # CIF components must be there
        all_additions = " ".join(art_133["additions"])
        assert "freight" in all_additions.lower() or "transport" in all_additions.lower()
        assert "insurance" in all_additions.lower()

    def test_article_129_definitions(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        art_129 = art["key_articles"]["129"]
        assert "טובין זהים" in art_129["definitions"]
        assert "טובין דומים" in art_129["definitions"]
        assert "יחסים מיוחדים" in art_129["definitions"]

    def test_article_148_currency(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["124-154"]
        assert "148" in art["key_articles"]
        assert "exchange rate" in art["key_articles"]["148"]["text"].lower()

    def test_article_168_agents(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["168-169"]
        assert "168" in art["articles"]
        assert "169" in art["articles"]
        assert "סוכן מכס" in art["articles"]["168"]["name_he"]

    def test_article_211_smuggling(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["207-223"]
        assert "211" in art["articles"]
        assert "5 years" in art["articles"]["211"]["text"] or "5" in art["articles"]["211"]["text"]

    def test_article_220_treble_fine(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["207-223"]
        assert "220" in art["articles"]
        assert "3×" in art["articles"]["220"]["text"] or "3x" in art["articles"]["220"]["text"].lower()

    def test_article_223b_financial_penalties(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["223a-r"]
        assert "223b" in art["articles"]
        text = art["articles"]["223b"]["text"]
        assert "400" in text
        assert "5,000" in text
        assert "25,000" in text

    def test_article_223r_criminal_preserved(self):
        art = CUSTOMS_ORDINANCE_ARTICLES["223a-r"]
        assert "223r" in art["articles"]
        assert "criminal" in art["articles"]["223r"]["text"].lower()


class TestGetOrdinanceArticle:
    """Test the get_ordinance_article() helper function."""

    def test_get_existing_article(self):
        art = get_ordinance_article("1")
        assert art["name_he"] == "הגדרות"

    def test_get_valuation_articles(self):
        art = get_ordinance_article("124-154")
        assert "key_articles" in art
        assert "130" in art["key_articles"]

    def test_get_nonexistent_article(self):
        assert get_ordinance_article("999") == {}

    def test_get_agents_article(self):
        art = get_ordinance_article("168-169")
        assert art["chapter"] == 11


class TestGetValuationMethods:
    """Test the get_valuation_methods() helper function."""

    def test_returns_7_methods(self):
        methods = get_valuation_methods()
        assert len(methods) == 7

    def test_methods_in_order(self):
        methods = get_valuation_methods()
        for i, m in enumerate(methods):
            assert m["number"] == i + 1

    def test_method_has_required_fields(self):
        methods = get_valuation_methods()
        for m in methods:
            assert "number" in m
            assert "name_he" in m
            assert "name_en" in m
            assert "section" in m
            assert "description" in m


class TestFormatLegalContextIncludesLaw:
    """Verify format_legal_context_for_prompt() includes law articles."""

    def test_contains_customs_ordinance_header(self):
        result = format_legal_context_for_prompt()
        assert "CUSTOMS ORDINANCE" in result

    def test_contains_valuation_methods(self):
        result = format_legal_context_for_prompt()
        assert "Method 1:" in result
        assert "Transaction Value" in result
        assert "Method 7:" in result
        assert "Fallback" in result

    def test_contains_section_133_additions(self):
        result = format_legal_context_for_prompt()
        assert "TRANSACTION VALUE ADDITIONS" in result

    def test_contains_key_definitions(self):
        result = format_legal_context_for_prompt()
        assert "KEY DEFINITIONS" in result
        assert "טובין חבי מכס" in result

    def test_contains_agent_obligations(self):
        result = format_legal_context_for_prompt()
        assert "AGENT OBLIGATIONS" in result
        assert "168" in result

    def test_contains_penalties_summary(self):
        result = format_legal_context_for_prompt()
        assert "PENALTIES" in result
        assert "211" in result
        assert "3×" in result

    def test_contains_administrative_enforcement(self):
        result = format_legal_context_for_prompt()
        assert "ADMINISTRATIVE ENFORCEMENT" in result
        assert "223" in result

    def test_valuation_mandatory_order_rule(self):
        result = format_legal_context_for_prompt()
        assert "MUST be applied" in result or "mandatory order" in result.lower()
