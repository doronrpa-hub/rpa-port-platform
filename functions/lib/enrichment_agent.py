"""
RCB Enrichment Agent v4 - Import, Export, ALL Customs Procedures, PC Agent
Session 12: Full import+export+customs procedures + PC Agent browser delegation

KEY FLOWS:
  Researcher → finds URL → can't download → researcher_delegate_to_pc_agent()
  PC Agent → downloads via browser → uploads to storage
  Librarian → auto-tags file → check_and_tag_completed_downloads()

The agent:
1. Learns from classifications, corrections, emails (import + export)
2. Continuously scans DB for gaps in BOTH import & export
3. Generates web search queries (Israeli + international)
4. Delegates browser downloads to PC Agent for gov.il/nevo/etc PDFs
5. Geo-tags every piece of data as Israeli or foreign
6. Covers ALL customs procedures:
   שחרור, הערכה, סיווג, מצהרים, קרנה אט"א, יצוא, הישבון,
   מחסנים, פטור מותנה, פיקוח יצוא, יצואן מאושר, כללי מקור
"""

from datetime import datetime, timezone
from .librarian_researcher import (
    ENRICHMENT_TASKS,
    RESEARCH_KEYWORDS,
    EnrichmentFrequency,
    check_for_updates,
    schedule_enrichment,
    complete_enrichment,
    learn_from_classification,
    learn_from_email,
    learn_from_correction,
    learn_from_web_result,
    get_enrichment_status,
    scan_db_for_research_keywords,
    get_web_search_queries,
    geo_tag_source,
    enrich_with_geo_tags,
)
from .librarian_index import index_single_document
from .pc_agent import (
    create_download_task,
    create_bulk_download_tasks,
    get_pending_tasks as get_pending_downloads,
    get_all_tasks_status,
)
from .librarian_tags import PC_AGENT_DOWNLOAD_SOURCES, CUSTOMS_HANDBOOK_CHAPTERS


class EnrichmentAgent:
    """
    Background enrichment agent — the Librarian's research arm.
    
    Covers:
    - Import procedures (שחרור, הערכה, סיווג, חוקיות יבוא)
    - Export procedures (יצוא, יצוא חופשי, פיקוח יצוא, כללי מקור)
    - Customs procedures (מצהרים, קרנה אט"א, פטור מותנה, מחסני רישוי)
    - Legal (פקודת המכס, תקנות, צווים, פסיקה)
    - PC Agent delegation for browser-required downloads
    
    Usage:
        agent = EnrichmentAgent(db)
        
        # Event-driven:
        agent.on_classification_complete(result)
        agent.on_email_processed(email_data)
        agent.on_correction(orig_hs, corrected_hs, desc, reason)
        
        # Continuous:
        tasks = agent.run_continuous_research()
        
        # Scheduled (cron):
        agent.run_scheduled_enrichments()
        
        # PC Agent:
        agent.request_gov_downloads()
        agent.get_pc_agent_status()
    """

    def __init__(self, db):
        self.db = db

    # ─────────────────────────────────────
    #  EVENT HANDLERS
    # ─────────────────────────────────────

    def on_classification_complete(self, classification_result):
        """Learn from a completed classification (import or export)."""
        print("  🔬 ENRICHMENT: Learning from classification...")
        try:
            success = learn_from_classification(self.db, classification_result)

            items = classification_result.get("items") or \
                    classification_result.get("classification_data", [])
            for item in items:
                if isinstance(item, dict) and item.get("hs_code"):
                    doc_id = f"learn_{item['hs_code']}_{_safe_id(item.get('description', '')[:50])}"
                    index_single_document(self.db, "classification_knowledge", doc_id, item)

            return success
        except Exception as e:
            print(f"  ❌ ENRICHMENT: Error: {e}")
            return False

    def on_email_processed(self, email_data):
        """Learn from an email (import or export context)."""
        print("  🔬 ENRICHMENT: Learning from email...")
        try:
            result = learn_from_email(self.db, email_data)
            print(f"    📚 Learned: {result['learned_items']} items, "
                  f"{result['new_suppliers']} new suppliers")
            return result
        except Exception as e:
            print(f"  ❌ ENRICHMENT: Error: {e}")
            return {"learned_items": 0, "new_suppliers": 0, "new_products": 0}

    def on_correction(self, original_hs_code, corrected_hs_code,
                      description, reason=""):
        """Learn from user correction."""
        print(f"  🔬 ENRICHMENT: Learning correction "
              f"{original_hs_code} → {corrected_hs_code}")
        return learn_from_correction(
            self.db, original_hs_code, corrected_hs_code, description, reason
        )

    def on_web_result(self, web_result, research_topic):
        """Store web research result with geo-tags."""
        return learn_from_web_result(self.db, web_result, research_topic)

    # ─────────────────────────────────────
    #  PC AGENT — BROWSER DOWNLOADS
    # ─────────────────────────────────────

    def request_gov_downloads(self):
        """
        Create download tasks for all known government sources.
        The PC Agent will pick these up and download via browser.
        
        Returns:
            List[str] - Created task IDs
        """
        print("  🤖 ENRICHMENT: Creating PC Agent download tasks...")
        all_task_ids = []

        for source_key in PC_AGENT_DOWNLOAD_SOURCES:
            source = PC_AGENT_DOWNLOAD_SOURCES[source_key]
            # Only create tasks for sources that need a browser
            if source.get("requires_browser", True):
                task_ids = create_bulk_download_tasks(self.db, source_key)
                all_task_ids.extend(task_ids)
                print(f"    📥 Queued: {source.get('name_he', source_key)}")

        print(f"  🤖 Created {len(all_task_ids)} download tasks for PC Agent")
        return all_task_ids

    def request_specific_download(self, url, name, auto_tags=None, metadata=None):
        """
        Request the PC Agent to download a specific URL.
        
        Use when the Researcher finds a new URL during web search
        that it cannot download directly.
        
        Args:
            url: str - URL to download
            name: str - Human-readable name
            auto_tags: List[str] - Tags to apply
            metadata: dict - Additional info
            
        Returns:
            str - Task ID
        """
        return create_download_task(
            self.db, url, name, auto_tags, metadata
        )

    def request_customs_handbook_download(self):
        """
        Request download of ALL customs handbook chapters (אוגדן מכס).
        Covers IMPORT + EXPORT + GENERAL chapters.
        Creates PC Agent tasks for each chapter with a known PDF URL.
        """
        print("  🤖 ENRICHMENT: Requesting ALL customs handbook chapters (import + export)...")
        task_ids = []

        for chapter_num, chapter_info in CUSTOMS_HANDBOOK_CHAPTERS.items():
            pdf_url = chapter_info.get("pdf_url", "")
            scope = chapter_info.get("scope", "both")

            if pdf_url:
                auto_tags = [chapter_info["tag"], "procedure_customs", "source_israeli"]
                if scope == "export":
                    auto_tags.append("customs_export")
                elif scope == "import":
                    auto_tags.append("customs_release")

                task_id = create_download_task(
                    self.db,
                    url=pdf_url,
                    source_name=f"אוגדן מכס פרק {chapter_num} - {chapter_info['name_he']}",
                    auto_tags=auto_tags,
                    metadata={
                        "chapter": str(chapter_num),
                        "scope": scope,
                        "content_type": ["procedure_customs"],
                        "file_types": ["pdf"],
                    }
                )
                if task_id:
                    task_ids.append(task_id)

            # Also download sub-chapters if they have URLs
            for sub_key, sub_info in chapter_info.get("sub_chapters", {}).items():
                sub_pdf = sub_info.get("pdf_url", "")
                if sub_pdf:
                    task_id = create_download_task(
                        self.db,
                        url=sub_pdf,
                        source_name=f"אוגדן מכס פרק {sub_key} - {sub_info['name_he']}",
                        auto_tags=[sub_info["tag"], "procedure_customs", "source_israeli"],
                        metadata={
                            "chapter": str(sub_key),
                            "parent_chapter": str(chapter_num),
                        }
                    )
                    if task_id:
                        task_ids.append(task_id)

        print(f"  🤖 Queued {len(task_ids)} handbook chapter downloads (import + export)")
        return task_ids

    def get_pc_agent_status(self):
        """Get status of all PC Agent download tasks."""
        return get_all_tasks_status(self.db)

    # ─────────────────────────────────────
    #  RESEARCHER → PC AGENT DELEGATION
    # ─────────────────────────────────────

    def researcher_delegate_to_pc_agent(self, url, name_he, auto_tags=None,
                                         scope="both", reason="",
                                         instructions=""):
        """
        Called by the Researcher when it finds a URL it cannot download directly.
        Creates a PC Agent task to:
          1. Download the file via browser
          2. Upload to Firebase Storage
          3. Auto-tag via the Librarian

        This is the KEY INTEGRATION POINT between Researcher and PC Agent.

        Args:
            url: str - URL of the file/page
            name_he: str - Hebrew name/description
            auto_tags: List[str] - Tags to apply after download
            scope: str - "import", "export", or "both"
            reason: str - Why this download was requested
            instructions: str - Special instructions for the PC agent
                          (e.g. "Click on download button", "Navigate to PDF link")

        Returns:
            str - Task ID for tracking

        Example:
            # Researcher finds a new export procedure PDF on gov.il
            task_id = agent.researcher_delegate_to_pc_agent(
                url="https://www.gov.il/he/.../export-procedure",
                name_he="נוהל יצוא חדש - 2026",
                auto_tags=["customs_export", "procedure_customs", "source_israeli"],
                scope="export",
                reason="Found new export procedure during web research",
                instructions="Page requires JavaScript. Download the linked PDF."
            )
        """
        if auto_tags is None:
            auto_tags = ["source_pc_agent", "source_web"]

        # Ensure standard tags are present
        if "source_pc_agent" not in auto_tags:
            auto_tags.append("source_pc_agent")
        if "source_israeli" not in auto_tags:
            # Auto-detect if Israeli source
            if any(domain in url for domain in [".gov.il", ".mof.gov.il", "nevo.co.il",
                                                  "sii.org.il", ".org.il", "taxes.gov.il"]):
                auto_tags.append("source_israeli")

        # Add scope tag
        if scope == "export" and "customs_export" not in auto_tags:
            auto_tags.append("customs_export")

        metadata = {
            "scope": scope,
            "reason": reason,
            "requested_by": "researcher",
            "instructions": instructions,
        }

        task_id = create_download_task(
            self.db, url, name_he, auto_tags, metadata
        )

        if task_id:
            print(f"  🤖→📥 Researcher delegated to PC Agent: {name_he}")
            print(f"         URL: {url}")
            print(f"         Scope: {scope}")
            print(f"         Task ID: {task_id}")

        return task_id

    def researcher_delegate_batch(self, urls_list):
        """
        Delegate multiple URLs to PC Agent at once.

        Args:
            urls_list: List[dict] - Each dict has:
                - url: str
                - name_he: str
                - auto_tags: List[str] (optional)
                - scope: str (optional, default "both")
                - reason: str (optional)
                - instructions: str (optional)

        Returns:
            List[str] - Task IDs

        Example:
            tasks = agent.researcher_delegate_batch([
                {"url": "https://...", "name_he": "נוהל יצוא ימי", "scope": "export"},
                {"url": "https://...", "name_he": "נוהל מצהרים עדכון", "scope": "both"},
            ])
        """
        task_ids = []
        for item in urls_list:
            task_id = self.researcher_delegate_to_pc_agent(
                url=item["url"],
                name_he=item.get("name_he", "Unknown document"),
                auto_tags=item.get("auto_tags"),
                scope=item.get("scope", "both"),
                reason=item.get("reason", "Batch research delegation"),
                instructions=item.get("instructions", ""),
            )
            if task_id:
                task_ids.append(task_id)

        print(f"  🤖→📥 Batch delegated {len(task_ids)} URLs to PC Agent")
        return task_ids

    def check_and_tag_completed_downloads(self):
        """
        Check for completed PC Agent downloads and auto-tag them.
        This completes the cycle: Researcher → PC Agent → Librarian Tags.

        Call this periodically (e.g., every 5 minutes).

        Returns:
            List[dict] - Info about newly tagged documents
        """
        from .librarian_tags import auto_tag_pc_agent_download

        tagged = []
        status = get_all_tasks_status(self.db)

        for task in status.get("tasks", []):
            # Find tasks completed but not yet tagged
            if (task.get("status") == "complete" and
                not task.get("librarian_tagged", False)):

                file_path = task.get("file_path", "")
                source_key = task.get("source_name", "")
                metadata = task.get("metadata", {})
                existing_tags = task.get("auto_tags", [])

                if file_path:
                    # Auto-tag with librarian
                    new_tags = auto_tag_pc_agent_download(
                        file_path=file_path,
                        source_key=source_key,
                        metadata={**metadata, "existing_tags": existing_tags}
                    )

                    # Mark as tagged in database
                    try:
                        task_ref = self.db.collection("pc_agent_tasks").document(task.get("id", ""))
                        task_ref.update({
                            "librarian_tagged": True,
                            "librarian_tags": new_tags,
                            "tagged_at": datetime.now(timezone.utc).isoformat(),
                        })
                        tagged.append({
                            "task_id": task.get("id"),
                            "file_path": file_path,
                            "tags": new_tags,
                        })
                    except Exception as e:
                        print(f"  ⚠️ Failed to mark tagged: {e}")

        if tagged:
            print(f"  🏷️ Librarian tagged {len(tagged)} newly downloaded files")
        return tagged

    # ─────────────────────────────────────
    #  CONTINUOUS RESEARCH
    # ─────────────────────────────────────

    def run_continuous_research(self):
        """
        Scan DB for gaps, generate research tasks.
        Covers BOTH import AND export procedures.
        
        Flow:
          1. Scan DB for gaps (low-confidence, missing export info, etc.)
          2. Generate search queries (Hebrew + English)
          3. For URLs that need browser → delegate to PC Agent
          4. Return tasks for external search execution
        """
        print("  🔬 ENRICHMENT: Running continuous research scan (import + export)...")
        
        db_tasks = scan_db_for_research_keywords(self.db)
        search_tasks = []
        pc_agent_delegated = 0

        for task in db_tasks[:20]:
            queries = {
                "task": task,
                "search_queries_he": [],
                "search_queries_en": [],
                "target_sources_israeli": [],
                "target_sources_international": [],
                "pc_agent_downloads": [],
            }

            keywords = task.get("keywords", [])
            hs_code = task.get("hs_code", "")
            context = task.get("context", "import")  # "import" or "export"

            for kw in keywords:
                if kw:
                    # Import context
                    queries["search_queries_he"].append(f"{kw} מכס ישראל")
                    queries["search_queries_he"].append(f"{kw} צו יבוא חופשי")
                    # Export context
                    queries["search_queries_he"].append(f"{kw} יצוא ישראל")
                    queries["search_queries_he"].append(f"{kw} פיקוח יצוא")
                    # Customs procedures
                    queries["search_queries_he"].append(f"{kw} נוהל מכס")

            if hs_code:
                # Import classification
                queries["search_queries_he"].append(f"פרט מכס {hs_code} ישראל")
                queries["search_queries_en"].append(f"HS code {hs_code} classification")
                queries["target_sources_israeli"].append(
                    f"https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Import/CustomsTaarifEntry?goodsNomenclatureCode={hs_code}"
                )
                # Export classification
                queries["search_queries_he"].append(f"סיווג ביצוא {hs_code}")
                queries["target_sources_israeli"].append(
                    f"https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Export/ExportCustomsEntry"
                )
                # Export control check
                queries["search_queries_he"].append(f"פיקוח יצוא {hs_code} דו-שימושי")

            # Delegate URLs that need browser to PC Agent
            for url in queries["target_sources_israeli"]:
                if any(d in url for d in ["shaarolami", "gov.il", "nevo.co.il"]):
                    task_id = self.researcher_delegate_to_pc_agent(
                        url=url,
                        name_he=f"Research: {task.get('reason', hs_code or 'unknown')}",
                        auto_tags=["source_web", "source_pc_agent", "source_israeli"],
                        scope=context,
                        reason=task.get("reason", "Continuous research gap"),
                    )
                    if task_id:
                        queries["pc_agent_downloads"].append({
                            "url": url,
                            "task_id": task_id,
                            "requires_browser": True,
                        })
                        pc_agent_delegated += 1

            search_tasks.append(queries)

        print(f"  🔬 Generated {len(search_tasks)} research tasks, "
              f"delegated {pc_agent_delegated} to PC Agent")
        return search_tasks

    def get_research_topics_for_item(self, hs_code="", description="",
                                      context="import"):
        """
        Get research topics for an item (import or export context).
        
        Args:
            hs_code: str
            description: str
            context: "import" or "export"
        """
        queries = {
            "context": context,
            "israeli_queries": [],
            "international_queries": [],
            "israeli_sources": [],
            "international_sources": [],
        }

        if hs_code:
            chapter = hs_code[:2] if len(hs_code) >= 2 else ""
            queries["israeli_queries"].extend([
                f"פרט מכס {hs_code}",
                f"סיווג {hs_code} מכס ישראל",
                f"תוספת צו יבוא חופשי {hs_code}",
                f"אישור יבוא פרק {chapter}",
            ])

            if context == "export":
                queries["israeli_queries"].extend([
                    f"סיווג ביצוא {hs_code}",
                    f"פיקוח יצוא {hs_code}",
                    f"רישיון יצוא {hs_code}",
                    f"כללי מקור {hs_code}",
                ])

            queries["international_queries"].extend([
                f"HS {hs_code} classification",
                f"HS {hs_code} explanatory notes",
            ])

        if description:
            desc_short = description[:50]
            queries["israeli_queries"].extend([
                f"{desc_short} סיווג מכס",
                f"{desc_short} {'יצוא' if context == 'export' else 'יבוא'} ישראל",
            ])

        return queries

    # ─────────────────────────────────────
    #  SCHEDULED ENRICHMENT
    # ─────────────────────────────────────

    def run_scheduled_enrichments(self):
        """
        Run all overdue scheduled enrichment tasks.
        Covers import, export, customs procedures, legal, courts.
        """
        print("  🔬 ENRICHMENT AGENT: Running scheduled enrichments...")
        summary = {
            "tasks_checked": 0,
            "tasks_run": 0,
            "results": {},
            "pending_web_searches": [],
            "pc_agent_tasks_created": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for task_key, task_config in ENRICHMENT_TASKS.items():
            summary["tasks_checked"] += 1

            if task_config["frequency"] in (
                EnrichmentFrequency.PER_EMAIL,
                EnrichmentFrequency.CONTINUOUS,
            ):
                continue

            pending = check_for_updates(self.db, task_config["source"])
            for p in pending:
                if p["task_key"] == task_key:
                    print(f"    📋 Running: {task_config['name']} ({task_config.get('geo', 'israel')})")
                    schedule_id = schedule_enrichment(self.db, task_key)

                    if schedule_id:
                        result = self._execute_enrichment(task_key, task_config)
                        complete_enrichment(self.db, schedule_id, result)
                        summary["tasks_run"] += 1
                        summary["results"][task_key] = result

                        if result.get("web_searches"):
                            summary["pending_web_searches"].extend(result["web_searches"])

                        # Create PC Agent tasks for URLs that need browser
                        for search in result.get("web_searches", []):
                            if search.get("requires_browser"):
                                task_id = create_download_task(
                                    self.db,
                                    url=search.get("url", search.get("query", "")),
                                    source_name=f"Enrichment: {task_key}",
                                    auto_tags=["source_web", "source_pc_agent"],
                                )
                                if task_id:
                                    summary["pc_agent_tasks_created"] += 1

        print(f"  🔬 ENRICHMENT: Checked {summary['tasks_checked']}, "
              f"ran {summary['tasks_run']}, "
              f"PC agent tasks: {summary['pc_agent_tasks_created']}")
        return summary

    def _execute_enrichment(self, task_key, task_config):
        """Execute an enrichment task, generating search queries."""
        result = {
            "task": task_key,
            "status": "executed",
            "geo": task_config.get("geo", "israel"),
            "web_searches": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            research_topic = task_config.get("research_topic", "")
            research_topics = task_config.get("research_topics", [])

            all_topics = []
            if research_topic:
                all_topics.append(research_topic)
            all_topics.extend(research_topics)

            for topic in all_topics:
                topic_config = get_web_search_queries(topic)

                for kw in topic_config.get("keywords_he", []):
                    result["web_searches"].append({
                        "query": kw,
                        "language": "he",
                        "topic": topic,
                        "geo": topic_config.get("geo", "israel"),
                        "is_israeli": topic_config.get("geo") == "israel",
                    })

                for kw in topic_config.get("keywords_en", []):
                    result["web_searches"].append({
                        "query": kw,
                        "language": "en",
                        "topic": topic,
                        "geo": topic_config.get("geo", "international"),
                        "is_israeli": topic_config.get("geo") == "israel",
                    })

            result["total_queries"] = len(result["web_searches"])

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    # ─────────────────────────────────────
    #  STATUS & REPORTING
    # ─────────────────────────────────────

    def get_status(self):
        """Get full enrichment agent status."""
        status = get_enrichment_status(self.db)
        status["pc_agent"] = self.get_pc_agent_status()
        return status

    def get_learning_stats(self):
        """Get learning stats broken down by geo + import/export."""
        stats = {
            "total_learned": 0, "corrections": 0, "classifications": 0,
            "suppliers": 0, "products": 0, "web_research": 0,
            "by_geo": {"israel": 0, "foreign": 0, "unknown": 0},
            "by_context": {"import": 0, "export": 0, "general": 0},
            "pc_agent_downloads": 0,
        }

        try:
            for doc in self.db.collection("classification_knowledge").limit(1000).stream():
                data = doc.to_dict()
                stats["total_learned"] += 1

                geo = data.get("geo_origin", "unknown")
                if geo == "israel":
                    stats["by_geo"]["israel"] += 1
                elif geo in ("eu", "usa", "international", "uk", "china"):
                    stats["by_geo"]["foreign"] += 1
                else:
                    stats["by_geo"]["unknown"] += 1

                # Detect import vs export context
                tags = data.get("tags", [])
                if any(t in tags for t in ["customs_export", "free_export", "export_control"]):
                    stats["by_context"]["export"] += 1
                elif any(t in tags for t in ["free_import_order", "customs_release"]):
                    stats["by_context"]["import"] += 1
                else:
                    stats["by_context"]["general"] += 1

                if data.get("is_correction"):
                    stats["corrections"] += 1
                else:
                    stats["classifications"] += 1

            for doc in self.db.collection("knowledge_base").limit(1000).stream():
                data = doc.to_dict()
                entry_type = data.get("type", "")
                if entry_type == "supplier":
                    stats["suppliers"] += 1
                elif entry_type == "product":
                    stats["products"] += 1
                elif entry_type == "web_research":
                    stats["web_research"] += 1

            # Count PC agent downloads
            pc_status = get_all_tasks_status(self.db)
            stats["pc_agent_downloads"] = pc_status.get("by_status", {}).get("complete", 0)

        except Exception as e:
            stats["error"] = str(e)

        return stats

    def get_all_sources(self):
        """List all known data sources: Israeli, international, PC agent."""
        from .librarian_researcher import ISRAELI_WEB_SOURCES, INTERNATIONAL_WEB_SOURCES

        sources = {
            "israeli_web": [{"key": k, "name": v.get("name_he", k), "url": v["url"]}
                           for k, v in ISRAELI_WEB_SOURCES.items()],
            "international_web": [{"key": k, "name": v.get("name_en", k), "url": v["url"]}
                                  for k, v in INTERNATIONAL_WEB_SOURCES.items()],
            "pc_agent_sources": [{"key": k, "name": v.get("name_he", k), "url": v["url"],
                                   "requires_browser": v.get("requires_browser", True)}
                                  for k, v in PC_AGENT_DOWNLOAD_SOURCES.items()],
        }
        return sources


def create_enrichment_agent(db):
    """Factory function for creating an EnrichmentAgent."""
    return EnrichmentAgent(db)


def _safe_id(text):
    import re
    safe = re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '_', text.strip())
    return safe[:60].strip('_') or "unknown"
