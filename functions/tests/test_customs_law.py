"""Tests for customs_law.py and chapter_expertise.py — the broker's embedded brain."""
import pytest
from lib.customs_law import (
    CLASSIFICATION_METHODOLOGY,
    TARIFF_SECTIONS,
    VALID_SUPPLEMENTS,
    NONEXISTENT_SUPPLEMENTS,
    GIR_RULES,
    KNOWN_FAILURES,
    get_classification_methodology,
    get_gir_rule,
    get_chapter_section,
    get_applicable_supplements,
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

    def test_no_chapters_no_section_expertise(self):
        result = format_legal_context_for_prompt()
        assert "RELEVANT SECTION/CHAPTER EXPERTISE" not in result

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
        # (trap text may also mention "Section XVI" — that's fine, we check the header line)
        section_block = result.split("RELEVANT SECTION/CHAPTER EXPERTISE")[1] if "RELEVANT SECTION/CHAPTER EXPERTISE" in result else ""
        header_lines = [l for l in section_block.splitlines() if l.startswith("Section XVI:")]
        assert len(header_lines) == 1

    def test_output_reasonable_length(self):
        result = format_legal_context_for_prompt(chapters=[1, 40, 85])
        # Should be substantial but not enormous
        assert 500 < len(result) < 10000
