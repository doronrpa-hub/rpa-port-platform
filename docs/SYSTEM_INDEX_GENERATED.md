# RCB System Index
## Auto-generated from actual code + live Firebase queries
## Last updated: 2026-02-13 15:37 UTC
## Generator: `functions/build_system_index.py`

To regenerate: `cd functions && python build_system_index.py`

---

## Table of Contents

1. [System Health Summary](#1-system-health-summary)
2. [Library Modules](#2-library-modules-functionslib)
3. [Cloud Functions](#3-cloud-functions-functionsmainpy)
4. [Standalone Scripts](#4-standalone-scripts)
5. [Firestore Collections](#5-firestore-collections)
6. [External APIs](#6-external-apis)
7. [Module Wiring](#7-module-wiring)
8. [Files NOT in Repo](#8-files-not-in-repo)
9. [Dead Code](#9-dead-code)

---

## 1. System Health Summary

- **Health Score:** 88/100 (DEGRADED)
- **Issues:** 1 | **Warnings:** 3
- **Last inspection:** 2026-02-13 13:00:02.926393+00:00
- **Classifications:** 86 total — 32 successful (37%), 28 clarification, 26 other
- **Emails processed (all time):** 291
- **enrichment_summary:**  (last check: )
- **rcb:** healthy (last check: 2026-02-13 15:33:05.647360+00:00)
- **rcb_monitor:** degraded (last check: 2026-02-10 20:34:06.351148+00:00)
- **source_catalog:**  (last check: )

### Last Script Runs
| Script | Last Run |
|--------|----------|
| deep_learn | 2026-02-13T11:29:33.774767+00:00 |
| enrich_knowledge | 2026-02-13T11:41:00.584617+00:00 |
| knowledge_indexer | 2026-02-13T11:31:04.210554+00:00 |
| read_everything | 2026-02-13T12:08:28.786893+00:00 |

---

## 2. Library Modules (functions/lib/)

### __init__.py (230 lines)
- RCB Library Modules

### clarification_generator.py (782 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Smart Clarification Generator
- **Classes:** RequestType, UrgencyLevel, RequestLanguage, DocumentType, ClarificationRequest
- **Functions (8):**
  - `to_dict()` :283
  - `to_html()` :296
  - `generate_missing_docs_request()` :318
  - `generate_missing_docs_request_en()` :393
  - `generate_classification_request()` :470
  - `generate_cif_completion_request()` :532
  - `generate_origin_request()` :601
  - `generate_generic_request()` :702
- **Imports from lib:** language_tools

### classification_agents.py (1634 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Multi-Agent Classification System
- **Functions (30):**
  - `_is_valid_hs()` :116
  - `_is_product_description()` :130
  - `generate_tracking_code()` :147
  - `build_rcb_subject()` :154
  - `extract_tracking_from_subject()` :230
  - `clean_firestore_data()` :239
  - `call_claude()` :250
  - `call_gemini()` :282
  - `call_gemini_fast()` :332
  - `call_gemini_pro()` :337
  - `call_ai()` :342
  - `query_tariff()` :372
  - `query_ministry_index()` :388
  - `query_classification_rules()` :399
  - `_try_parse_agent1()` :410
  - `run_document_agent()` :430
  - `run_classification_agent()` :480
  - `run_regulatory_agent()` :506
  - `run_fta_agent()` :526
  - `run_risk_agent()` :545
  - `run_synthesis_agent()` :566
  - `run_full_classification()` :598
  - `_retry_classification()` :984
  - `audit_before_send()` :994
  - `_build_unclassified_banner()` :1105
  - `_build_low_confidence_banner()` :1124
  - `build_classification_email()` :1133
  - `build_excel_report()` :1306
  - `_parse_invoice_fields_from_data()` :1364
  - `process_and_send_report()` :1399
- **Imports from lib:** librarian, invoice_validator, clarification_generator, rcb_orchestrator, language_tools, enrichment_agent, intelligence, document_parser, smart_questions, verification_loop, document_tracker, rcb_helpers
- **Firestore reads:** classification_rules, ministry_index, tariff
- **Firestore writes:** rcb_classifications
- **External APIs:** Anthropic/Claude, Google Gemini

### document_parser.py (1220 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Document Parser — Per-Document Type Identification & Field Extraction
- **Functions (20):**
  - `identify_document_type()` :296
  - `extract_structured_fields()` :386
  - `_extract_invoice_fields()` :420
  - `_extract_packing_list_fields()` :516
  - `_extract_bl_fields()` :575
  - `_extract_awb_fields()` :641
  - `_extract_coo_fields()` :693
  - `_extract_eur1_fields()` :740
  - `_extract_health_cert_fields()` :760
  - `_extract_insurance_fields()` :812
  - `_extract_do_fields()` :859
  - `_extract_generic_fields()` :893
  - `assess_document_completeness()` :931
  - `parse_document()` :1022
  - `parse_all_documents()` :1050
  - `_clean_value()` :1080
  - `_clean_multiline()` :1092
  - `_find_date()` :1102
  - `_extract_line_items()` :1119
  - `_field_name_he()` :1217

### document_tracker.py (840 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Document Phase Tracker
- **Classes:** ShipmentPhase, ProductCategory, DocumentType, Incoterm, TransportMode, Document, ClarificationRequest, DocumentTracker
- **Functions (27):**
  - `to_dict()` :113
  - `to_hebrew()` :132
  - `__init__()` :248
  - `add_document()` :268
  - `has_document()` :273
  - `get_document()` :277
  - `remove_document()` :281
  - `set_incoterms()` :291
  - `set_product_category()` :298
  - `set_transport_mode()` :305
  - `phase()` :317
  - `phase_hebrew()` :354
  - `missing_docs()` :363
  - `missing_docs_for_classification()` :392
  - `_get_missing_cif_docs()` :405
  - `_get_missing_product_docs()` :426
  - `_is_cif_complete()` :437
  - `ready_to_classify()` :461
  - `ready_for_declaration()` :476
  - `generate_clarification_request()` :499
  - `get_status_report()` :517
  - `_get_hebrew_status()` :523
  - `_get_english_status()` :567
  - `to_dict()` :602
  - `create_tracker()` :624
  - `_derive_current_step()` :697
  - `feed_parsed_documents()` :715

### enrichment_agent.py (732 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Enrichment Agent v4 - Import, Export, ALL Customs Procedures, PC Agent
- **Classes:** EnrichmentAgent
- **Functions (21):**
  - `__init__()` :79
  - `on_classification_complete()` :86
  - `on_email_processed()` :104
  - `on_correction()` :116
  - `on_web_result()` :125
  - `request_gov_downloads()` :133
  - `request_specific_download()` :155
  - `request_customs_handbook_download()` :175
  - `get_pc_agent_status()` :230
  - `researcher_delegate_to_pc_agent()` :238
  - `researcher_delegate_batch()` :308
  - `check_and_tag_completed_downloads()` :346
  - `run_continuous_research()` :403
  - `get_research_topics_for_item()` :484
  - `run_scheduled_enrichments()` :537
  - `_execute_enrichment()` :593
  - `get_status()` :645
  - `get_learning_stats()` :651
  - `get_all_sources()` :707
  - `create_enrichment_agent()` :723
  - `_safe_id()` :728
- **Imports from lib:** librarian_researcher, librarian_index, pc_agent, librarian_tags
- **Firestore reads:** classification_knowledge, knowledge_base, pc_agent_tasks

### incoterms_calculator.py (664 lines) — NOT WIRED (not reachable from main.py)
- **Purpose:** RCB Incoterms CIF Calculator
- **Classes:** Incoterm, TransportType, CIFComponents, CIFCalculation, IncotermsCalculator
- **Functions (16):**
  - `cif_value()` :220
  - `total_customs_value()` :225
  - `cif_value_ils()` :230
  - `to_dict()` :236
  - `to_dict()` :262
  - `get_summary_hebrew()` :272
  - `__init__()` :337
  - `get_incoterm_info()` :340
  - `get_missing_for_cif()` :366
  - `calculate_cif()` :383
  - `estimate_insurance()` :480
  - `get_all_incoterms()` :501
  - `get_incoterms_comparison()` :513
  - `create_calculator()` :549
  - `calculate_cif()` :554
  - `get_missing_for_cif()` :580

### intelligence.py (1892 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Intelligence Module — The System's Own Brain
- **Functions (20):**
  - `pre_classify()` :23
  - `lookup_regulatory()` :223
  - `lookup_fta()` :309
  - `validate_documents()` :476
  - `route_to_ministries()` :930
  - `query_free_import_order()` :1089
  - `_query_fio_api()` :1180
  - `_query_fio_parents()` :1269
  - `_check_fio_cache()` :1331
  - `_save_fio_cache()` :1353
  - `_extract_keywords()` :1369
  - `_search_classification_knowledge()` :1384
  - `_search_classification_rules()` :1446
  - `_search_keyword_index()` :1488
  - `_search_product_index()` :1549
  - `_search_supplier_index()` :1605
  - `_search_tariff()` :1652
  - `_lookup_regulatory_by_chapter()` :1718
  - `_search_fta_by_country()` :1744
  - `_build_pre_classify_context()` :1832
- **Firestore reads:** classification_knowledge, classification_rules, free_import_cache, fta_agreements, keyword_index, ministry_index, product_index, regulatory_requirements, supplier_index, tariff, tariff_chapters
- **Firestore writes:** free_import_cache
- **External APIs:** gov.il API

### invoice_validator.py (382 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Module 5: Invoice Validator
- **Classes:** InvoiceField, FieldValidation, InvoiceValidationResult
- **Functions (7):**
  - `summary_he()` :169
  - `get_missing_fields_request()` :186
  - `to_dict()` :200
  - `_check_field_present()` :212
  - `validate_invoice()` :248
  - `quick_validate()` :307
  - `print_requirements()` :319

### knowledge_query.py (900 lines) — DIRECT (imported by main.py)
- **Purpose:** Knowledge Query Handler for RCB v4.1.0
- **Functions (19):**
  - `_normalize()` :184
  - `_extract_sender_name_graph()` :189
  - `_get_sender_address()` :203
  - `_generate_query_id()` :211
  - `_strip_html()` :217
  - `_get_body_text()` :224
  - `_find_handbook_chapters_by_tags()` :234
  - `is_team_sender()` :270
  - `is_addressed_to_rcb()` :276
  - `has_commercial_documents()` :286
  - `_is_question_like()` :297
  - `detect_knowledge_query()` :309
  - `parse_question()` :345
  - `gather_knowledge()` :417
  - `select_attachments()` :540
  - `generate_reply()` :569
  - `send_reply()` :697
  - `log_knowledge_query()` :747
  - `handle_knowledge_query()` :783
- **Imports from lib:** librarian, librarian_researcher, librarian_tags, classification_agents, rcb_helpers
- **External APIs:** Anthropic/Claude

### language_tools.py (2069 lines) — INDIRECT (imported by wired module)
- **Purpose:** language_tools.py — Session 14: Language Tools Overhaul
- **Classes:** LetterType, Tone, LanguageRegister, SpellingIssue, GrammarIssue, StyleObservation, LetterHead, SignatureBlock, CustomsVocabulary, HebrewLanguageChecker, LetterStructure, SubjectLineGenerator, StyleAnalyzer, TextPolisher, LanguageLearner, JokeBank
- **Functions (75):**
  - `__init__()` :252
  - `add_term()` :260
  - `add_keyword()` :274
  - `add_collocation()` :281
  - `lookup()` :288
  - `suggest_correction()` :300
  - `get_formal_term()` :313
  - `get_informal_term()` :317
  - `expand_abbreviation()` :322
  - `enrich_from_text()` :326
  - `get_stats()` :345
  - `__init__()` :368
  - `check_spelling()` :371
  - `check_grammar()` :386
  - `check_hs_code_format()` :437
  - `check_legal_references()` :465
  - `check_number_formatting()` :482
  - `check_vat_rate()` :498
  - `fix_vat_rate()` :523
  - `fix_all()` :543
  - `get_all_issues()` :567
  - `__init__()` :589
  - `set_greeting()` :605
  - `set_reference()` :611
  - `add_section()` :623
  - `add_attachment()` :631
  - `add_action_item()` :637
  - `_base_css()` :643
  - `render_html()` :815
  - `render_plain_text()` :908
  - `validate_structure()` :957
  - `generate()` :1005
  - `_generate_hebrew()` :1025
  - `_generate_english()` :1073
  - `_truncate()` :1101
  - `generate_reply_subject()` :1106
  - `generate_clarification_subject()` :1112
  - `generate_knowledge_subject()` :1117
  - `__init__()` :1142
  - `analyze_text_register()` :1153
  - `learn_from_email()` :1204
  - `learn_from_official_document()` :1266
  - `get_recommended_register()` :1282
  - `adapt_text_to_contact()` :1298
  - `get_contact_summary()` :1322
  - `to_dict()` :1326
  - `from_dict()` :1338
  - `__init__()` :1360
  - `build_polish_prompt()` :1365
  - `polish_hebrew()` :1430
  - `polish_english()` :1447
  - `adapt_tone()` :1455
  - `summarize_for_email()` :1471
  - `__init__()` :1504
  - `learn_from_correction()` :1511
  - `learn_from_email_exchange()` :1539
  - `learn_from_document()` :1567
  - `learn_from_handbook()` :1572
  - `apply_learned_spelling()` :1578
  - `get_improvement_report()` :1584
  - `to_dict()` :1597
  - `from_dict()` :1607
  - `__init__()` :1637
  - `get_joke()` :1739
  - `get_customs_joke()` :1769
  - `get_friday_joke()` :1776
  - `add_joke()` :1785
  - `bootstrap_vocabulary()` :1799
  - `create_language_toolkit()` :1872
  - `_similar_words()` :1911
  - `_count_by_key()` :1920
  - `generate_tracking_code()` :1933
  - `build_rcb_subject()` :1944
  - `build_html_report()` :2002
  - `process_outgoing_text()` :2046

### librarian.py (963 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Smart Librarian - Central Knowledge Manager
- **Functions (32):**
  - `extract_search_keywords()` :17
  - `search_collection_smart()` :29
  - `search_tariff_codes()` :65
  - `search_regulations()` :122
  - `search_procedures_and_rules()` :148
  - `search_knowledge_base()` :182
  - `search_history()` :206
  - `full_knowledge_search()` :240
  - `get_israeli_hs_format()` :316
  - `normalize_hs_code()` :326
  - `validate_hs_code()` :332
  - `validate_and_correct_classifications()` :454
  - `build_classification_context()` :490
  - `find_by_hs_code()` :552
  - `find_by_ministry()` :615
  - `find_by_tags()` :671
  - `smart_search()` :717
  - `get_document_location()` :793
  - `get_all_locations_for()` :833
  - `scan_all_collections()` :864
  - `rebuild_index()` :870
  - `get_inventory_stats()` :876
  - `learn_from_classification()` :886
  - `check_for_updates()` :892
  - `get_enrichment_status()` :898
  - `get_search_analytics()` :904
  - `auto_tag_document()` :914
  - `add_tags()` :920
  - `get_tags_for_hs_code()` :926
  - `search_all_knowledge()` :936
  - `search_extended_knowledge()` :940
  - `_log_search()` :949
- **Imports from lib:** librarian_researcher, librarian_index, librarian_tags
- **Firestore reads:** hs_code_index, librarian_index, tariff, tariff_chapters
- **Firestore writes:** librarian_search_log

### librarian_index.py (468 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Librarian Index - Document Indexing & Inventory
- **Functions (7):**
  - `scan_all_collections()` :161
  - `index_collection()` :191
  - `rebuild_index()` :250
  - `index_single_document()` :287
  - `remove_from_index()` :317
  - `get_inventory_stats()` :332
  - `_build_index_entry()` :381
- **Imports from lib:** librarian_tags
- **Firestore reads:** librarian_index
- **Firestore writes:** librarian_enrichment_log, librarian_index

### librarian_researcher.py (1182 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Librarian Researcher - Continuous Knowledge Enrichment
- **Classes:** EnrichmentFrequency, EnrichmentSource
- **Functions (17):**
  - `scan_db_for_research_keywords()` :528
  - `get_web_search_queries()` :613
  - `geo_tag_source()` :636
  - `enrich_with_geo_tags()` :682
  - `learn_from_classification()` :715
  - `learn_from_correction()` :781
  - `learn_from_email()` :817
  - `learn_from_web_result()` :885
  - `find_similar_classifications()` :945
  - `check_for_updates()` :1000
  - `schedule_enrichment()` :1029
  - `complete_enrichment()` :1049
  - `get_enrichment_status()` :1066
  - `get_search_analytics()` :1104
  - `_log_enrichment()` :1139
  - `_safe_id()` :1156
  - `_is_overdue()` :1163
- **Firestore reads:** classification_knowledge, knowledge_base, librarian_enrichment_log, librarian_index, librarian_search_log, rcb_classifications
- **Firestore writes:** classification_knowledge, knowledge_base, librarian_enrichment_log
- **External APIs:** gov.il API

### librarian_tags.py (1715 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Librarian Tags - Complete Israeli Customs & Trade Document Tagging System
- **Functions (24):**
  - `auto_tag_document()` :1184
  - `auto_tag_pc_agent_download()` :1224
  - `suggest_related_tags()` :1269
  - `get_tags_for_hs_code()` :1311
  - `get_free_import_appendix_info()` :1348
  - `get_pc_agent_sources()` :1355
  - `get_pending_downloads()` :1360
  - `mark_download_complete()` :1372
  - `mark_upload_complete()` :1392
  - `add_tags()` :1414
  - `remove_tags()` :1431
  - `get_tag_stats()` :1447
  - `init_tag_definitions()` :1466
  - `_build_searchable_text()` :1500
  - `_detect_ministry_tag()` :1512
  - `_detect_free_import_appendices()` :1534
  - `_detect_court_tags()` :1550
  - `_detect_customs_handbook_chapter()` :1566
  - `_detect_export_tags()` :1613
  - `_detect_geography()` :1639
  - `_detect_data_origin()` :1660
  - `_detect_file_type()` :1675
  - `_tag_country()` :1686
  - `_replace_tag()` :1709
- **Firestore reads:** librarian_index, librarian_tags

### pc_agent.py (624 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB PC Agent Integration - Browser-Based File Download & Upload
- **Functions (19):**
  - `create_download_task()` :59
  - `create_bulk_download_tasks()` :112
  - `get_pending_tasks()` :151
  - `assign_task()` :180
  - `report_download_complete()` :194
  - `report_upload_complete()` :239
  - `report_task_failed()` :267
  - `get_task_status()` :297
  - `get_all_tasks_status()` :308
  - `get_download_queue_for_agent()` :341
  - `download_with_browser()` :408
  - `download_direct()` :433
  - `upload_to_storage()` :443
  - `run_agent()` :450
  - `get_agent_script()` :524
  - `_auto_tag_and_index_download()` :533
  - `_finalize_download()` :559
  - `_generate_download_instructions()` :593
  - `_safe_id()` :619
- **Imports from lib:** librarian_tags, pc_agent, librarian_index
- **Firestore reads:** pc_agent_tasks
- **Firestore writes:** pc_agent_tasks

### pdf_creator.py (203 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB PDF Creator - Classification Report Generator
- **Functions (5):**
  - `is_hebrew_char()` :18
  - `heb()` :22
  - `setup_fonts()` :65
  - `get_styles()` :87
  - `create_classification_pdf()` :98

### product_classifier.py (715 lines) — NOT WIRED (not reachable from main.py)
- **Purpose:** RCB Product Type Classifier
- **Classes:** ClassificationResult, ProductClassifier
- **Functions (11):**
  - `to_dict()` :413
  - `get_summary_hebrew()` :425
  - `__init__()` :465
  - `classify()` :470
  - `_analyze_text()` :543
  - `_analyze_hs_code()` :562
  - `classify_from_invoice()` :580
  - `get_required_docs_for_category()` :610
  - `get_all_categories()` :623
  - `create_classifier()` :642
  - `classify_product()` :647
- **Imports from lib:** document_tracker

### rcb_email_processor.py (415 lines) — NOT WIRED (not reachable from main.py)
- **Purpose:** RCB Email Processor
- **Classes:** RCBEmailProcessor
- **Functions (15):**
  - `_save_language_state()` :19
  - `_load_language_state()` :27
  - `_get_toolkit()` :41
  - `__init__()` :67
  - `connect()` :81
  - `disconnect()` :95
  - `get_todays_emails()` :105
  - `get_safe_id()` :136
  - `decode_header_value()` :142
  - `extract_body()` :158
  - `extract_attachments()` :184
  - `process_emails()` :203
  - `create_processor()` :288
  - `build_ack_email()` :297
  - `build_report_email()` :330
- **Imports from lib:** language_tools, librarian_tags
- **Firestore reads:** system_state
- **Firestore writes:** system_state

### rcb_helpers.py (810 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Helper functions - Graph API, PDF extraction, Hebrew names
- **Functions (27):**
  - `_assess_extraction_quality()` :15
  - `_cleanup_hebrew_text()` :45
  - `_tag_document_structure()` :66
  - `_preprocess_image_for_ocr()` :120
  - `extract_text_from_pdf_bytes()` :147
  - `_extract_with_pdfplumber()` :184
  - `_extract_with_pypdf()` :229
  - `_extract_with_vision_ocr()` :245
  - `_pdf_to_images()` :283
  - `_pdf_to_images_fallback()` :308
  - `_try_decode()` :324
  - `_extract_from_excel()` :335
  - `_extract_from_docx()` :358
  - `_extract_from_eml()` :385
  - `_extract_from_msg()` :421
  - `_extract_urls_from_text()` :453
  - `extract_text_from_attachments()` :465
  - `_ocr_image()` :623
  - `get_rcb_secrets_internal()` :643
  - `helper_get_graph_token()` :656
  - `helper_graph_messages()` :673
  - `helper_graph_attachments()` :685
  - `helper_graph_mark_read()` :694
  - `helper_graph_send()` :702
  - `to_hebrew_name()` :753
  - `build_rcb_reply()` :765
  - `get_anthropic_key()` :804
- **External APIs:** Microsoft Graph

### rcb_id.py (69 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Internal ID System v1.0
- **Classes:** RCBType
- **Functions (2):**
  - `generate_rcb_id()` :33
  - `parse_rcb_id()` :58

### rcb_inspector.py (1750 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Inspector Agent v1.0.0
- **Functions (31):**
  - `consult_librarian()` :144
  - `inspect_database()` :192
  - `_audit_collection()` :236
  - `_audit_tag_integrity()` :271
  - `_audit_knowledge_health()` :359
  - `inspect_processes()` :440
  - `_detect_scheduler_clashes()` :479
  - `_detect_race_conditions()` :499
  - `_map_write_conflicts()` :523
  - `_check_selftest_safety()` :551
  - `inspect_flows()` :591
  - `_inspect_classification_flow()` :640
  - `_inspect_knowledge_query_flow()` :703
  - `_inspect_monitor_flow()` :740
  - `inspect_monitors()` :774
  - `run_auto_fixes()` :832
  - `_fix_stuck_classifications()` :868
  - `_fix_stale_processed()` :914
  - `_fix_selftest_artifacts()` :953
  - `consult_claude_if_needed()` :982
  - `plan_next_session()` :1077
  - `_get_next_session_id()` :1166
  - `_build_task_list()` :1185
  - `_generate_mission_markdown()` :1284
  - `generate_report()` :1347
  - `_calculate_health_score()` :1405
  - `generate_email_html()` :1465
  - `run_full_inspection()` :1581
  - `_send_daily_email()` :1671
  - `handle_inspector_http()` :1713
  - `handle_inspector_daily()` :1737
- **Imports from lib:** librarian_tags, rcb_helpers, classification_agents
- **Firestore reads:** classification_knowledge, classifications, enrichment_tasks, knowledge_base, knowledge_queries, rcb_classifications, rcb_processed, sessions_backup, system_status
- **Firestore writes:** rcb_inspector_reports, session_missions
- **External APIs:** Anthropic/Claude

### rcb_orchestrator.py (409 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Module 6: Orchestrator
- **Classes:** ShipmentStage, ProcessingAction, ShipmentStatus, RCBOrchestrator
- **Functions (10):**
  - `summary_he()` :79
  - `to_dict()` :121
  - `__init__()` :151
  - `process_shipment()` :155
  - `_map_fields_to_docs()` :216
  - `quick_check()` :237
  - `get_status()` :260
  - `process_response()` :264
  - `create_orchestrator()` :287
  - `process_and_respond()` :292
- **Imports from lib:** invoice_validator, clarification_generator

### rcb_self_test.py (646 lines) — DIRECT (imported by main.py)
- **Purpose:** RCB Self-Test Engine v4.1.0 (Hardened)
- **Classes:** TestResult
- **Functions (12):**
  - `__init__()` :197
  - `to_dict()` :205
  - `_send_test_email()` :220
  - `_find_email_by_subject()` :233
  - `_delete_email()` :242
  - `_cleanup_test_emails()` :255
  - `_cleanup_firestore()` :282
  - `_guard_rcb_processed()` :347
  - `_run_detection_test()` :368
  - `_run_parse_test()` :394
  - `_run_e2e_test()` :429
  - `run_all_tests()` :556
- **Imports from lib:** rcb_helpers, knowledge_query
- **Firestore reads:** knowledge_base, librarian_enrichment_log
- **Firestore writes:** rcb_processed
- **External APIs:** Microsoft Graph

### smart_questions.py (570 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Smart Question Engine — Elimination-Based Clarification
- **Functions (11):**
  - `_get_numeric_confidence()` :40
  - `_get_chapter()` :50
  - `analyze_ambiguity()` :56
  - `_build_code_comparison_he()` :192
  - `generate_smart_questions()` :241
  - `_get_implication()` :390
  - `_parse_duty()` :416
  - `should_ask_questions()` :426
  - `format_questions_he()` :467
  - `format_questions_html()` :510
  - `_html_escape()` :561

### tracker_email.py (317 lines) — NOT WIRED (not reachable from main.py)
- **Purpose:** RCB Tracker Email Builder
- **Functions (5):**
  - `build_tracker_status_email()` :10
  - `_get_steps()` :79
  - `_summarize_steps()` :83
  - `_format_date()` :110
  - `_build_html()` :129

### verification_loop.py (457 lines) — INDIRECT (imported by wired module)
- **Purpose:** RCB Verification Loop — Verify, Enrich, Cache Every Classification
- **Functions (8):**
  - `verify_hs_code()` :77
  - `verify_all_classifications()` :177
  - `learn_from_verification()` :248
  - `_get_purchase_tax()` :307
  - `_check_verification_cache()` :338
  - `_save_verification_cache()` :365
  - `_verify_in_tariff_db()` :390
  - `_format_hs_dots()` :448
- **Firestore reads:** classification_knowledge, verification_cache
- **Firestore writes:** verification_cache

---

## 3. Cloud Functions (functions/main.py)

**1709 lines** | **39 functions** | **Imports from lib:** classification_agents, knowledge_query, rcb_id, rcb_helpers, enrichment_agent, librarian_index, pdf_creator, rcb_self_test, rcb_inspector

### Schedulers
| Function | Schedule | Line |
|----------|----------|------|
| `check_email_scheduled` | every 5 minutes | :165 |
| `enrich_knowledge` | every 1 hours | :508 |
| `rcb_check_email` | every 2 minutes | :1019 |
| `rcb_cleanup_old_processed` | every 24 hours | :1268 |
| `rcb_retry_failed` | every 6 hours | :1295 |
| `rcb_health_check` | every 1 hours | :1340 |

### HTTP Triggers
| Function | Line |
|----------|------|
| `api` | :540 |
| `graph_forward_email` | :912 |
| `rcb_api` | :933 |
| `monitor_agent_manual` | :1259 |
| `monitor_self_heal` | :1438 |
| `monitor_self_heal` | :1446 |
| `monitor_fix_all` | :1454 |
| `test_pdf_ocr` | :1475 |
| `test_pdf_report` | :1549 |
| `rcb_self_test` | :1632 |
| `rcb_inspector` | :1666 |

### Firestore Triggers
| Function | Document | Trigger | Line |
|----------|----------|---------|------|
| `on_new_classification` | classifications/{classId} | created | :333 |
| `on_classification_correction` | classifications/{classId} | updated | :414 |

---

## 4. Standalone Scripts

### Active Scripts
| File | Lines | Purpose |
|------|-------|---------|
| `batch_reprocess.py` | 1064 | Batch Reprocessor — Read, classify, verify, and LEARN from EVERYTHING |
| `build_system_index.py` | 903 | Build System Index — Auto-generate docs/SYSTEM_INDEX.md from actual code + Firebase. |
| `deep_learn.py` | 906 | Deep Knowledge Learning — Mine ALL professional documents in Firestore. |
| `enrich_knowledge.py` | 801 | Enrich Knowledge — Reclassify, extract, and link Firestore data. |
| `import_knowledge.py` | 173 | Import baseline knowledge JSONs into Firestore. |
| `knowledge_indexer.py` | 725 | Knowledge Indexer — Build inverted indexes for fast HS code lookup. |
| `main.py` | 1709 | RPA-PORT Cloud Functions |
| `read_everything.py` | 1139 | Read Everything — Build the master brain_index from ALL Firestore collections. |

### Utilities & Tests
| File | Lines | Category | Purpose |
|------|-------|----------|---------|
| `cleanup_old_results.py` | 39 | Utility | Delete old dry-run and test results from batch_reprocess_results. |
| `clear_processed.py` | 15 | Utility |  |
| `rcb_diagnostic.py` | 45 | Utility | RCB Diagnostic Tool - Run: python3 rcb_diagnostic.py |
| `remove_duplicates.py` | 31 | Utility |  |
| `test_classification.py` | 31 | Test |  |
| `test_full.py` | 27 | Test |  |
| `test_graph.py` | 26 | Test |  |
| `test_real.py` | 24 | Test |  |

---

## 5. Firestore Collections

### Live Counts (queried from Firebase)
| Collection | Docs | Read by | Written by |
|------------|------|---------|------------|
| `agent_tasks` | 731 | -- | main.py |
| `batch_reprocess_results` | 345 | cleanup_old_results.py, read_everything.py | batch_reprocess.py |
| `batch_reprocess_summary` | 4 | -- | batch_reprocess.py |
| `brain_index` | 11245 | read_everything.py | -- |
| `buyers` | 2 | read_everything.py | -- |
| `classification_knowledge` | 82 | deep_learn.py, enrichment_agent.py, intelligence.py, knowledge_indexer.py, librarian_researcher.py, rcb_inspector.py, read_everything.py, verification_loop.py | librarian_researcher.py |
| `classification_rules` | 32 | classification_agents.py, intelligence.py, read_everything.py | -- |
| `classifications` | 25 | batch_reprocess.py, knowledge_indexer.py, main.py, rcb_inspector.py, read_everything.py | main.py |
| `config` | 9 | patch_main.py | -- |
| `declarations` | 53 | batch_reprocess.py, deep_learn.py, enrich_knowledge.py | main.py |
| `document_types` | 13 | read_everything.py | -- |
| `enrichment_log` | 8 | -- | -- |
| `enrichment_tasks` | 304 | rcb_inspector.py | -- |
| `free_import_cache` | 8 | intelligence.py, read_everything.py | intelligence.py |
| `fta_agreements` | 21 | intelligence.py, read_everything.py | -- |
| `hs_code_index` | 101 | knowledge_indexer.py, librarian.py, read_everything.py | -- |
| `inbox` | 64 | batch_reprocess.py, main.py, patch_main.py | main.py, patch_main.py, patch_smart_email.py |
| `keyword_index` | 8185 | deep_learn.py, enrich_knowledge.py, intelligence.py, knowledge_indexer.py | -- |
| `knowledge` | 71 | read_everything.py | -- |
| `knowledge_base` | 297 | batch_reprocess.py, deep_learn.py, enrich_knowledge.py, enrichment_agent.py, librarian_researcher.py, main.py, rcb_inspector.py, rcb_self_test.py, read_everything.py | librarian_researcher.py |
| `knowledge_queries` | 50 | rcb_inspector.py | -- |
| `learning_log` | 0 | main.py | main.py |
| `legal_requirements` | 7443 | read_everything.py | -- |
| `librarian_enrichment_log` | 168 | librarian_researcher.py, rcb_self_test.py | librarian_index.py, librarian_researcher.py |
| `librarian_index` | 12595 | librarian.py, librarian_index.py, librarian_researcher.py, librarian_tags.py, read_everything.py | librarian_index.py |
| `librarian_search_log` | 2921 | librarian_researcher.py | librarian.py |
| `librarian_tags` | 0 | librarian_tags.py | -- |
| `licensing_knowledge` | 18 | read_everything.py | -- |
| `ministry_index` | 84 | classification_agents.py, intelligence.py, read_everything.py | import_knowledge.py |
| `monitor_errors` | 0 | main.py | -- |
| `pc_agent_tasks` | 0 | enrichment_agent.py, pc_agent.py | pc_agent.py |
| `pending_tasks` | 27 | main.py | -- |
| `procedures` | 3 | read_everything.py | -- |
| `product_index` | 65 | deep_learn.py, enrich_knowledge.py, intelligence.py, knowledge_indexer.py | -- |
| `pupil_teachings` | 202 | read_everything.py | -- |
| `rcb_classifications` | 86 | build_system_index.py, deep_learn.py, enrich_knowledge.py, knowledge_indexer.py, librarian_researcher.py, main.py, rcb_inspector.py, read_everything.py | classification_agents.py, patch_classification.py |
| `rcb_first_emails` | 2 | -- | -- |
| `rcb_inbox` | 9 | -- | -- |
| `rcb_inspector_reports` | 14 | build_system_index.py | rcb_inspector.py |
| `rcb_logs` | 101 | main.py | add_followup_trigger.py |
| `rcb_pdf_requests` | 0 | -- | -- |
| `rcb_processed` | 41 | clear_processed.py, fix_email_check.py, main.py, rcb_diagnostic.py, rcb_inspector.py | fix_email_check.py, main.py, rcb_self_test.py |
| `rcb_silent_classifications` | 128 | read_everything.py | -- |
| `rcb_stats` | 1 | -- | -- |
| `rcb_test_reports` | 3 | -- | -- |
| `regulatory_certificates` | 4 | -- | main.py |
| `regulatory_requirements` | 28 | intelligence.py, read_everything.py | -- |
| `sellers` | 4 | knowledge_indexer.py, main.py, read_everything.py | -- |
| `session_backups` | 11 | add_backup_api.py, main.py | add_backup_api.py, main.py |
| `session_missions` | 1 | -- | rcb_inspector.py |
| `sessions_backup` | 2 | rcb_inspector.py | -- |
| `shipping_lines` | 15 | read_everything.py | -- |
| `supplier_index` | 3 | deep_learn.py, enrich_knowledge.py, intelligence.py, knowledge_indexer.py | -- |
| `system_counters` | 8 | build_system_index.py | -- |
| `system_metadata` | 4 | build_system_index.py | deep_learn.py, enrich_knowledge.py, knowledge_indexer.py, read_everything.py |
| `system_state` | 0 | rcb_email_processor.py | rcb_email_processor.py |
| `system_status` | 4 | build_system_index.py, rcb_inspector.py | main.py |
| `tariff` | 11753 | classification_agents.py, intelligence.py, knowledge_indexer.py, librarian.py, read_everything.py | -- |
| `tariff_chapters` | 101 | intelligence.py, knowledge_indexer.py, librarian.py, read_everything.py | -- |
| `triangle_learnings` | 36 | read_everything.py | -- |
| `verification_cache` | 43 | read_everything.py, verification_loop.py | verification_loop.py |

### Discovered Collections (not in known list)
| Collection | Docs |
|------------|------|
| `_health` | 1 |
| `_test` | 1 |
| `agent_downloads` | 35 |
| `airlines` | 15 |
| `backup_log` | 2 |
| `backup_logs` | 45 |
| `bills_of_lading` | 23 |
| `brain_commands` | 30 |
| `classification_workflow` | 15 |
| `contacts` | 154 |
| `daily_state` | 2 |
| `files` | 37954 |
| `hub_agents` | 4 |
| `hub_links` | 6 |
| `hub_messages` | 68 |
| `hub_tasks` | 2196 |
| `hub_tools` | 6 |
| `intelligence_activity` | 1 |
| `intelligence_decisions` | 4 |
| `intelligence_files` | 5 |
| `learned_doc_templates` | 30 |
| `learned_shipping_patterns` | 63 |
| `learned_shipping_senders` | 42 |
| `legal_documents` | 4 |
| `legal_references` | 8 |
| `mission_chat` | 1 |
| `mission_decisions` | 2 |
| `missions` | 9 |
| `monitor` | 1 |
| `packing_lists` | 11 |
| `project_backups` | 3 |
| `pupil_audit_summaries` | 2 |
| `pupil_budget` | 3 |
| `pupil_observations` | 323 |
| `pupil_review_budget` | 2 |
| `pupil_reviews` | 3 |
| `regulatory` | 1 |
| `regulatory_approvals` | 2 |
| `scanner_logs` | 37964 |
| `session_history` | 13 |
| `system_tasks` | 1 |
| `tech_assistant_commands` | 420 |
| `tech_assistant_state` | 2 |
| `tracker_container_status` | 104 |
| `tracker_deals` | 50 |
| `tracker_observations` | 434 |
| `tracker_shipments` | 3 |
| `tracker_timeline` | 110 |
| `unclassified_documents` | 72 |
| `web_search_cache` | 9 |

### Empty Collections (6)
`learning_log`, `librarian_tags`, `monitor_errors`, `pc_agent_tasks`, `rcb_pdf_requests`, `system_state`

### Orphaned Collections (data exists but no code references)
`enrichment_log`, `rcb_first_emails`, `rcb_inbox`, `rcb_stats`, `rcb_test_reports`

---

## 6. External APIs

| API | Referenced in |
|-----|--------------|
| Anthropic/Claude | add_multi_agent_system.py:33, add_multi_agent_system.py:56, add_multiagent_safe.py:17, add_multiagent_safe.py:41, batch_reprocess.py:900 |
| Google Gemini | build_system_index.py:158, classification_agents.py:296 |
| Microsoft Graph | add_attachments.py:41, add_attachments.py:8, batch_reprocess.py:128, build_system_index.py:160, fix_email_check.py:30 |
| gov.il API | build_system_index.py:162, intelligence.py:1085, librarian_researcher.py:45 |

---

## 7. Module Wiring

How lib modules connect to the live pipeline via main.py:

| Module | Status |
|--------|--------|
| `clarification_generator` | INDIRECT (imported by wired module) |
| `classification_agents` | DIRECT (imported by main.py) |
| `document_parser` | INDIRECT (imported by wired module) |
| `document_tracker` | INDIRECT (imported by wired module) |
| `enrichment_agent` | DIRECT (imported by main.py) |
| `incoterms_calculator` | NOT WIRED (not reachable from main.py) |
| `intelligence` | INDIRECT (imported by wired module) |
| `invoice_validator` | INDIRECT (imported by wired module) |
| `knowledge_query` | DIRECT (imported by main.py) |
| `language_tools` | INDIRECT (imported by wired module) |
| `librarian` | INDIRECT (imported by wired module) |
| `librarian_index` | DIRECT (imported by main.py) |
| `librarian_researcher` | INDIRECT (imported by wired module) |
| `librarian_tags` | INDIRECT (imported by wired module) |
| `pc_agent` | INDIRECT (imported by wired module) |
| `pdf_creator` | DIRECT (imported by main.py) |
| `product_classifier` | NOT WIRED (not reachable from main.py) |
| `rcb_email_processor` | NOT WIRED (not reachable from main.py) |
| `rcb_helpers` | DIRECT (imported by main.py) |
| `rcb_id` | DIRECT (imported by main.py) |
| `rcb_inspector` | DIRECT (imported by main.py) |
| `rcb_orchestrator` | INDIRECT (imported by wired module) |
| `rcb_self_test` | DIRECT (imported by main.py) |
| `smart_questions` | INDIRECT (imported by wired module) |
| `tracker_email` | NOT WIRED (not reachable from main.py) |
| `verification_loop` | INDIRECT (imported by wired module) |

---

## 8. Files NOT in Repo

These files were uploaded to Claude browser sessions but never committed.
Their functionality exists ONLY in chat uploads and Firebase data.

| File | What it does | Firebase evidence |
|------|-------------|-------------------|
| `fix_silent_classify.py` | CC emails silently classified | 128 docs in rcb_silent_classifications |
| `fix_tracker_crash.py` | Patches None bug in _derive_current_step() | -- |
| `patch_tracker_v2.py` | Tracker v2 improved phase detection | -- |
| `pupil_v05_final.py` | Devil's advocate, CC email learning | 202 docs in pupil_teachings |

---

## 9. Dead Code

| File | Lines | Category |
|------|-------|----------|
| `add_attachments.py` | 96 | Dead (patch/fix) |
| `add_backup_api.py` | 83 | Dead (patch/fix) |
| `add_followup_trigger.py` | 48 | Dead (patch/fix) |
| `add_import.py` | 14 | Dead (patch/fix) |
| `add_multi_agent_system.py` | 285 | Dead (patch/fix) |
| `add_multiagent_safe.py` | 189 | Dead (patch/fix) |
| `final_fix.py` | 31 | Dead (patch/fix) |
| `fix_decorator.py` | 27 | Dead (patch/fix) |
| `fix_email_check.py` | 129 | Dead (patch/fix) |
| `fix_final.py` | 19 | Dead (patch/fix) |
| `fix_main_imports.py` | 41 | Dead (patch/fix) |
| `fix_missing_functions.py` | 214 | Dead (patch/fix) |
| `fix_signature.py` | 40 | Dead (patch/fix) |
| `fix_test.py` | 44 | Dead (patch/fix) |
| `main_fix.py` | 14 | Dead (patch/fix) |
| `move_get_secret.py` | 38 | Dead (patch/fix) |
| `name_fix.py` | 73 | Dead (patch/fix) |
| `patch_classification.py` | 165 | Dead (patch/fix) |
| `patch_main.py` | 295 | Dead (patch/fix) |
| `patch_rcb.py` | 111 | Dead (patch/fix) |
| `patch_smart_email.py` | 239 | Dead (patch/fix) |

---

## Stats

- **Lib modules:** 26 files, 22658 lines
- **main.py:** 1709 lines
- **Scripts:** 9853 lines
- **Total functions:** 669
- **Total classes:** 50
- **Firestore collections:** 111
- **Cloud Functions:** 6 schedulers, 11 HTTP, 2 Firestore triggers
