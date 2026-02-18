"""
RCB Self-Learning Engine
========================
Version: 1.0.0
Purpose: Brain of the RCB system. Checks memory before AI calls,
         learns after every interaction, actively enriches knowledge.

Memory Levels (cheapest first):
  Level 0: Exact Match     $0.00  — Same sender + doc type + pattern
  Level 1: Similar Match   $0.00  — Similar sender or product, adapt previous
  Level 2: Pattern Match   $0.00  — Same chapter/category, from template
  Level 3: Partial Knowledge $0.003 — Know product but gap (quick Gemini)
  Level 4: No Knowledge    $0.05  — Full AI pipeline (caller handles)

Collections used:
  READ+WRITE: learned_classifications, learned_answers, learned_contacts,
              learned_patterns, learned_corrections
  READ ONLY:  brain_index, keyword_index, product_index, supplier_index,
              classification_knowledge, knowledge_base, contacts

Callers:
  - tracker.py: check_tracking_memory(), learn_tracking_extraction()
  - pupil.py: may integrate later
  - scheduler: enrich_knowledge() (active learning)
"""

import re
import json
import hashlib
from datetime import datetime, timezone, timedelta

# AI provider costs for budget tracking
AI_COSTS = {
    "gemini_flash": 0.002,
    "gemini_pro": 0.005,
    "claude": 0.05,
    "chatgpt_mini": 0.015,
    "chatgpt_4o": 0.03,
}


class SelfLearningEngine:
    """Brain of the RCB system — 5-level memory with multi-AI active enrichment."""

    def __init__(self, db, get_secret_func=None):
        """
        Args:
            db: Firestore client
            get_secret_func: optional function to get API keys from Secret Manager.
                             If None, uses Google Cloud Secret Manager directly.
        """
        self.db = db
        self._get_secret_func = get_secret_func
        self._cost_this_session = 0.0
        self._api_keys = {}  # cache: name → key
        self._chatgpt_warned = False
        self._claude_warned = False
        self._gemini_warned = False

    # ════════════════════════════════════════════════════════════════════════
    # PASSIVE MEMORY — called by tracker/pupil during email processing
    # ════════════════════════════════════════════════════════════════════════

    def check_tracking_memory(self, from_email, subject, attachment_names):
        """Check if brain already knows about this sender/pattern.

        Tries levels 0 → 1 → 2 → 3 before returning 'none' (level 4).
        Levels 0-2 use only Firestore (FREE). Level 3 uses a quick Gemini call.

        Args:
            from_email: str — sender email address
            subject: str — email subject line
            attachment_names: list[str] — attachment filenames

        Returns:
            (brain_knowledge: dict or None, brain_level: str)
            brain_level is one of: "exact", "similar", "partial", "pattern", "none"
        """
        from_email = (from_email or "").strip().lower()
        subject = subject or ""
        attachment_names = attachment_names or []

        query_fields = {
            "sender_email": from_email,
            "sender_domain": from_email.split("@")[-1] if "@" in from_email else "",
            "subject": subject,
            "subject_keywords": self._extract_keywords(subject),
            "attachment_names": attachment_names,
            "attachment_keywords": self._extract_keywords(" ".join(attachment_names)),
        }

        # Level 0: Exact match — same sender + same doc pattern
        try:
            result = self._find_exact_match("learned_contacts", query_fields)
            if result:
                print(f"    🧠 SelfLearning: Level 0 EXACT match for {from_email}")
                return result, "exact"
        except Exception as e:
            print(f"    🧠 SelfLearning: Level 0 error: {e}")

        # Level 1: Similar match — same domain or overlapping keywords
        try:
            result = self._find_similar_match("learned_contacts", query_fields)
            if result:
                print(f"    🧠 SelfLearning: Level 1 SIMILAR match for {from_email}")
                return result, "similar"
        except Exception as e:
            print(f"    🧠 SelfLearning: Level 1 error: {e}")

        # Level 2: Pattern match — known doc type patterns
        try:
            result = self._find_pattern_match("learned_patterns", query_fields)
            if result:
                print(f"    🧠 SelfLearning: Level 2 PATTERN match for {from_email}")
                return result, "pattern"
        except Exception as e:
            print(f"    🧠 SelfLearning: Level 2 error: {e}")

        # Level 3: Partial knowledge — we know something, Gemini fills gap
        try:
            result = self._try_partial_knowledge(query_fields)
            if result:
                print(f"    🧠 SelfLearning: Level 3 PARTIAL knowledge for {from_email}")
                return result, "partial"
        except Exception as e:
            print(f"    🧠 SelfLearning: Level 3 error: {e}")

        # Level 4: No knowledge — caller handles with full AI pipeline
        print(f"    🧠 SelfLearning: Level 4 — no memory for {from_email}")
        return None, "none"

    def learn_tracking_extraction(self, sender_email, doc_type, extractions,
                                  confidence, source):
        """Save what was just learned from an extraction.

        Stores sender patterns in learned_contacts and document patterns
        in learned_patterns for future Level 0/1/2 lookups.

        Args:
            sender_email: str — sender email address
            doc_type: str — e.g. "bill_of_lading", "port_report"
            extractions: dict — logistics data extracted from email
            confidence: float — 0.0-1.0
            source: str — what method produced the data
        """
        sender_email = (sender_email or "").strip().lower()
        doc_type = doc_type or "unknown"
        extractions = extractions or {}
        now = datetime.now(timezone.utc)

        # ── Save/update sender contact profile ──
        try:
            domain = sender_email.split("@")[-1] if "@" in sender_email else ""
            contact_id = self._make_id(f"contact_{sender_email}")
            contact_ref = self.db.collection("learned_contacts").document(contact_id)
            existing = contact_ref.get()

            if existing.exists:
                data = existing.to_dict() or {}
                doc_types = data.get("doc_types", [])
                if doc_type and doc_type not in doc_types:
                    doc_types.append(doc_type)
                shipping_lines = data.get("shipping_lines", [])
                for sl in (extractions.get("shipping_lines") or []):
                    if sl and sl not in shipping_lines:
                        shipping_lines.append(sl)
                contact_ref.update({
                    "doc_types": doc_types,
                    "shipping_lines": shipping_lines,
                    "last_seen": now,
                    "times_seen": (data.get("times_seen", 0) or 0) + 1,
                    "last_confidence": confidence,
                    "last_source": source,
                })
            else:
                contact_ref.set({
                    "sender_email": sender_email,
                    "sender_domain": domain,
                    "doc_types": [doc_type] if doc_type else [],
                    "shipping_lines": extractions.get("shipping_lines") or [],
                    "ports": extractions.get("ports") or [],
                    "first_seen": now,
                    "last_seen": now,
                    "times_seen": 1,
                    "last_confidence": confidence,
                    "last_source": source,
                })
            print(f"    🧠 SelfLearning: learned contact {sender_email} → {doc_type}")
        except Exception as e:
            print(f"    🧠 SelfLearning: learn contact error: {e}")

        # ── Save document pattern ──
        try:
            pattern_data = {
                "sender_email": sender_email,
                "sender_domain": sender_email.split("@")[-1] if "@" in sender_email else "",
                "doc_type": doc_type,
                "extraction_keys": list(extractions.keys()),
                "has_containers": bool(extractions.get("containers")),
                "has_bols": bool(extractions.get("bols")),
                "has_vessels": bool(extractions.get("vessels")),
                "has_shipping_lines": bool(extractions.get("shipping_lines")),
                "has_ports": bool(extractions.get("ports")),
                "container_count": len(extractions.get("containers") or []),
                "bol_count": len(extractions.get("bols") or []),
                "confidence": confidence,
                "source": source,
                "learned_at": now,
            }

            # Extract keywords from the extraction for pattern matching
            keywords = set()
            for key, val in extractions.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            keywords.update(self._extract_keywords(item))
                elif isinstance(val, str):
                    keywords.update(self._extract_keywords(val))
            pattern_data["keywords"] = list(keywords)[:100]  # cap at 100

            pattern_id = self._make_id(
                f"pattern_{sender_email}_{doc_type}_{now.strftime('%Y%m%d')}"
            )
            self.db.collection("learned_patterns").document(pattern_id).set(
                pattern_data, merge=True
            )
            print(f"    🧠 SelfLearning: learned pattern {doc_type} from {sender_email}")
        except Exception as e:
            print(f"    🧠 SelfLearning: learn pattern error: {e}")

        # ── Auto-learn BOL prefixes (new BL + known shipping line → learn prefix) ──
        try:
            bols = extractions.get('bols') or []
            shipping_lines = extractions.get('shipping_lines') or []
            if bols and shipping_lines:
                carrier = shipping_lines[0].upper().replace(' ', '_')
                for bol in bols:
                    # Extract prefix: first 4 alpha chars of BOL
                    prefix_match = re.match(r'^([A-Z]{3,5})', bol.upper())
                    if not prefix_match:
                        continue
                    prefix = prefix_match.group(1)
                    if len(prefix) < 3:
                        continue
                    # Check if already known
                    sl_ref = self.db.collection('shipping_lines').document(carrier)
                    sl_doc = sl_ref.get()
                    if sl_doc.exists:
                        existing_prefixes = sl_doc.to_dict().get('bol_prefixes', [])
                        if prefix not in existing_prefixes:
                            existing_prefixes.append(prefix)
                            sl_ref.update({'bol_prefixes': existing_prefixes})
                            print(f"    🧠 SelfLearning: learned BOL prefix {prefix} → {carrier}")
                    else:
                        sl_ref.set({
                            'carrier': carrier,
                            'bol_prefixes': [prefix],
                            'learned_at': now,
                        })
                        print(f"    🧠 SelfLearning: created shipping_lines/{carrier} with prefix {prefix}")
        except Exception as e:
            print(f"    🧠 SelfLearning: BOL prefix learn error: {e}")

        # ── Auto-learn shipping agent → carrier mapping (new domain + shipping line → learn agent) ──
        try:
            domain = sender_email.split("@")[-1] if "@" in sender_email else ""
            if domain and shipping_lines:
                # Skip known shipping line domains — they're carriers, not agents
                _carrier_domains = [
                    'zim.com', 'maersk.com', 'msc.com', 'cma-cgm.com', 'hapag-lloyd.com',
                    'evergreen-line.com', 'cosco.com', 'coscoshipping.com', 'coscon.com',
                    'one-line.com', 'hmm21.com', 'yangming.com', 'pilship.com', 'oocl.com',
                    'wanhai.com', 'turkon.com.tr',
                ]
                if not any(domain.endswith(d) for d in _carrier_domains):
                    carrier = shipping_lines[0].upper().replace(' ', '_')
                    # Check if domain already in shipping_agents
                    already_known = False
                    try:
                        for agent_doc in self.db.collection('shipping_agents').stream():
                            agent_data = agent_doc.to_dict()
                            if domain in (agent_data.get('domains') or []):
                                already_known = True
                                # Add carrier if not already mapped
                                existing_carriers = agent_data.get('carriers') or []
                                if carrier not in existing_carriers:
                                    existing_carriers.append(carrier)
                                    self.db.collection('shipping_agents').document(agent_doc.id).update({
                                        'carriers': existing_carriers,
                                        'updated_at': now,
                                    })
                                    print(f"    🧠 SelfLearning: added carrier {carrier} to agent {agent_doc.id}")
                                break
                    except Exception:
                        pass
                    if not already_known:
                        agent_slug = domain.split('.')[0].lower()
                        self.db.collection('shipping_agents').document(agent_slug).set({
                            'name': agent_slug.upper(),
                            'domains': [domain],
                            'carriers': [carrier],
                            'role': 'shipping_agent',
                            'notes': f'Auto-learned from {sender_email}',
                            'learned_at': now,
                        }, merge=True)
                        print(f"    🧠 SelfLearning: auto-learned agent {agent_slug} ({domain}) → {carrier}")
        except Exception as e:
            print(f"    🧠 SelfLearning: agent mapping learn error: {e}")

        # ── Track memory-level usage for cost stats ──
        try:
            self._record_memory_usage(source, confidence)
        except Exception:
            pass

    def check_classification_memory(self, product_description,
                                    question_type="classify"):
        """Check if brain already knows how to classify this product.

        Args:
            product_description: str — product to classify
            question_type: str — "classify", "tariff", "regulation", etc.

        Returns:
            (answer: dict or None, level: str)
        """
        product_description = (product_description or "").strip()
        if not product_description:
            return None, "none"

        keywords = self._extract_keywords(product_description)
        product_lower = product_description.lower()

        # Level 0: Exact product match in learned_classifications
        try:
            docs = (self.db.collection("learned_classifications")
                    .where("product_lower", "==", product_lower)
                    .limit(1).stream())
            for doc in docs:
                data = doc.to_dict()
                if data and data.get("hs_code"):
                    print(f"    🧠 SelfLearning: classification EXACT for '{product_description[:40]}'")
                    return data, "exact"
        except Exception as e:
            print(f"    🧠 SelfLearning: classification exact error: {e}")

        # Level 1: Keyword match in keyword_index / product_index (READ ONLY)
        try:
            for kw in keywords:
                if len(kw) < 3:
                    continue
                ki_docs = (self.db.collection("keyword_index")
                           .where("keyword", "==", kw)
                           .limit(3).stream())
                for doc in ki_docs:
                    data = doc.to_dict()
                    if data and data.get("hs_code"):
                        print(f"    🧠 SelfLearning: classification SIMILAR via keyword '{kw}'")
                        return {
                            "hs_code": data["hs_code"],
                            "source": f"keyword_index:{kw}",
                            "confidence": 0.7,
                            "product": product_description,
                        }, "similar"
        except Exception as e:
            print(f"    🧠 SelfLearning: classification keyword error: {e}")

        # Level 2: Pattern match in classification_knowledge (READ ONLY)
        try:
            for kw in keywords:
                if len(kw) < 4:
                    continue
                ck_docs = (self.db.collection("classification_knowledge")
                           .where("keywords", "array_contains", kw)
                           .limit(3).stream())
                for doc in ck_docs:
                    data = doc.to_dict()
                    if data and data.get("chapter"):
                        print(f"    🧠 SelfLearning: classification PATTERN via chapter {data.get('chapter')}")
                        return {
                            "chapter": data["chapter"],
                            "hs_code": data.get("hs_code", ""),
                            "source": f"classification_knowledge:{kw}",
                            "confidence": 0.5,
                            "product": product_description,
                        }, "pattern"
        except Exception as e:
            print(f"    🧠 SelfLearning: classification pattern error: {e}")

        return None, "none"

    def learn_classification(self, product_description, hs_code, method,
                             source, confidence):
        """Save a classification result for future use.

        Args:
            product_description: str
            hs_code: str — e.g. "4011.10"
            method: str — "ai", "manual", "cross_validated"
            source: str — "gemini", "claude", "chatgpt", "user"
            confidence: float — 0.0-1.0
        """
        if not product_description or not hs_code:
            return

        _METHOD_RANK = {"cross_validated": 3, "manual": 2, "ai": 1}

        try:
            now = datetime.now(timezone.utc)
            product_lower = product_description.strip().lower()
            doc_id = self._make_id(f"cls_{product_lower}_{hs_code}")

            # Guard: never overwrite higher-confidence expert-validated results
            doc_ref = self.db.collection("learned_classifications").document(doc_id)
            existing = doc_ref.get()
            if existing.exists:
                ex = existing.to_dict()
                ex_conf = ex.get("confidence", 0) or 0
                ex_method = ex.get("method", "ai")
                ex_rank = _METHOD_RANK.get(ex_method, 0)
                new_rank = _METHOD_RANK.get(method, 0)
                # Skip if existing has higher confidence from same-or-better method
                if ex_conf > confidence and ex_rank >= new_rank:
                    print(f"    🧠 SelfLearning: skip overwrite '{product_description[:30]}' → {hs_code} "
                          f"(existing conf={ex_conf:.2f}/{ex_method} > new {confidence:.2f}/{method})")
                    return
                # Also skip if existing method is strictly better regardless of confidence
                if ex_rank > new_rank and ex_conf >= confidence:
                    print(f"    🧠 SelfLearning: skip overwrite '{product_description[:30]}' → {hs_code} "
                          f"(existing method {ex_method} outranks {method})")
                    return

            chapter = hs_code.split(".")[0] if "." in hs_code else hs_code[:4]
            keywords = self._extract_keywords(product_description)

            doc_ref.set({
                "product": product_description.strip(),
                "product_lower": product_lower,
                "hs_code": hs_code,
                "chapter": chapter,
                "keywords": keywords[:50],
                "method": method,
                "source": source,
                "confidence": confidence,
                "learned_at": now,
                "times_used": 0,
            }, merge=True)
            print(f"    🧠 SelfLearning: saved classification '{product_description[:30]}' → {hs_code}")
        except Exception as e:
            print(f"    🧠 SelfLearning: learn classification error: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # ACTIVE ENRICHMENT — called by scheduler
    # ════════════════════════════════════════════════════════════════════════

    def enrich_knowledge(self, topic=None, max_queries=10, budget=1.0):
        """Actively research and learn. Multi-AI cross-validation.

        Strategies applied:
        1. Gap filling — bring Level 3/4 answers to Level 0
        2. Cross-validation — verify recent AI answers with second provider
        3. Corrections — research topics we got wrong

        Args:
            topic: Optional specific topic to research. If None, auto-select.
            max_queries: Maximum research queries this run.
            budget: Maximum $ to spend this run.

        Returns:
            dict with: topics_researched, new_facts_learned, corrections_made, cost_spent
        """
        print("🧠 SelfLearning: enrich_knowledge starting...")
        result = {
            "topics_researched": 0,
            "new_facts_learned": 0,
            "corrections_made": 0,
            "cost_spent": 0.0,
            "details": [],
        }
        budget_remaining = budget
        queries_remaining = max_queries

        # If specific topic given, research just that
        if topic:
            cost = self._research_topic(topic, budget_remaining)
            result["topics_researched"] = 1
            result["new_facts_learned"] += 1 if cost > 0 else 0
            result["cost_spent"] = cost
            return result

        # Strategy 1: Fill knowledge gaps (Level 3/4 → Level 0)
        try:
            gap_result = self.fill_knowledge_gaps(
                max_items=min(queries_remaining, 10)
            )
            result["new_facts_learned"] += gap_result.get("filled", 0)
            result["topics_researched"] += gap_result.get("researched", 0)
            cost = gap_result.get("cost", 0.0)
            result["cost_spent"] += cost
            budget_remaining -= cost
            queries_remaining -= gap_result.get("researched", 0)
            result["details"].append(f"Gap filling: {gap_result}")
        except Exception as e:
            print(f"    🧠 SelfLearning: gap filling error: {e}")

        if budget_remaining <= 0 or queries_remaining <= 0:
            return result

        # Strategy 2: Cross-validate recent answers
        try:
            cv_result = self.cross_validate_recent(
                days=7, max_items=min(queries_remaining, 5)
            )
            result["corrections_made"] += cv_result.get("corrections", 0)
            result["topics_researched"] += cv_result.get("validated", 0)
            cost = cv_result.get("cost", 0.0)
            result["cost_spent"] += cost
            budget_remaining -= cost
            queries_remaining -= cv_result.get("validated", 0)
            result["details"].append(f"Cross-validation: {cv_result}")
        except Exception as e:
            print(f"    🧠 SelfLearning: cross-validation error: {e}")

        if budget_remaining <= 0 or queries_remaining <= 0:
            return result

        # Strategy 3: Research corrections
        try:
            corr_result = self._research_corrections(
                max_items=min(queries_remaining, 5),
                budget=budget_remaining
            )
            result["corrections_made"] += corr_result.get("corrections", 0)
            result["topics_researched"] += corr_result.get("researched", 0)
            cost = corr_result.get("cost", 0.0)
            result["cost_spent"] += cost
            result["details"].append(f"Corrections research: {corr_result}")
        except Exception as e:
            print(f"    🧠 SelfLearning: corrections research error: {e}")

        print(f"🧠 SelfLearning: enrich_knowledge done — "
              f"{result['topics_researched']} topics, "
              f"{result['new_facts_learned']} facts, "
              f"${result['cost_spent']:.4f} spent")
        return result

    def fill_knowledge_gaps(self, max_items=20):
        """Find Level 3/4 answers and research to bring to Level 0.

        Looks at learned_patterns where source indicates expensive AI was used,
        then researches those topics with cheaper methods to cache the answer.

        Returns:
            dict with: researched, filled, cost
        """
        result = {"researched": 0, "filled": 0, "cost": 0.0}

        try:
            # Find patterns that needed expensive AI (Level 3/4)
            expensive_docs = (
                self.db.collection("learned_patterns")
                .where("confidence", "<", 0.6)
                .order_by("confidence")
                .limit(max_items)
                .stream()
            )

            for doc in expensive_docs:
                data = doc.to_dict() or {}
                doc_type = data.get("doc_type", "")
                sender = data.get("sender_email", "")

                if not doc_type or result["researched"] >= max_items:
                    continue

                # Ask Gemini to fill the gap (cheapest AI)
                prompt = (
                    f"In Israeli customs/logistics, when an email from domain "
                    f"'{data.get('sender_domain', '')}' contains a '{doc_type}' document, "
                    f"what logistics data fields should we expect to extract? "
                    f"List the typical fields: containers, BOL numbers, vessel names, "
                    f"ports, ETAs, shipping lines. Be specific and concise. "
                    f"Answer in English."
                )
                answer = self._ask_gemini(prompt)
                result["researched"] += 1

                if answer:
                    # Store enriched knowledge
                    try:
                        enrich_id = self._make_id(
                            f"enrich_{sender}_{doc_type}"
                        )
                        self.db.collection("learned_answers").document(enrich_id).set({
                            "sender_domain": data.get("sender_domain", ""),
                            "doc_type": doc_type,
                            "expected_fields": answer,
                            "source": "gemini_enrichment",
                            "confidence": 0.75,
                            "learned_at": datetime.now(timezone.utc),
                        }, merge=True)
                        result["filled"] += 1
                    except Exception as e:
                        print(f"    🧠 SelfLearning: gap save error: {e}")

                result["cost"] += AI_COSTS["gemini_flash"]

        except Exception as e:
            print(f"    🧠 SelfLearning: fill_knowledge_gaps error: {e}")

        return result

    def cross_validate_recent(self, days=7, max_items=10):
        """Cross-validate recent AI answers with a second provider.

        If providers agree → boost confidence. If disagree → flag for review.

        Returns:
            dict with: validated, confirmations, corrections, cost
        """
        result = {"validated": 0, "confirmations": 0, "corrections": 0, "cost": 0.0}

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            recent_docs = (
                self.db.collection("learned_classifications")
                .where("learned_at", ">=", cutoff)
                .where("confidence", "<", 0.9)
                .limit(max_items)
                .stream()
            )

            for doc in recent_docs:
                data = doc.to_dict() or {}
                product = data.get("product", "")
                original_hs = data.get("hs_code", "")
                original_source = data.get("source", "")

                if not product or not original_hs:
                    continue

                # Pick a different provider for validation
                if "gemini" in original_source:
                    validate_answer = self._ask_claude(
                        f"What is the HS code (Harmonized System) for: {product}? "
                        f"Answer with ONLY the HS code number, nothing else."
                    )
                    validate_source = "claude"
                    validate_cost = AI_COSTS["claude"]
                else:
                    validate_answer = self._ask_gemini(
                        f"What is the HS code (Harmonized System) for: {product}? "
                        f"Answer with ONLY the HS code number, nothing else."
                    )
                    validate_source = "gemini"
                    validate_cost = AI_COSTS["gemini_flash"]

                result["validated"] += 1
                result["cost"] += validate_cost

                if not validate_answer:
                    continue

                validated_hs = self._extract_hs_code(validate_answer)

                # Compare: same chapter = confirmation, different = correction
                original_chapter = original_hs.split(".")[0] if "." in original_hs else original_hs[:4]
                validated_chapter = validated_hs.split(".")[0] if "." in validated_hs else validated_hs[:4]

                if original_chapter == validated_chapter:
                    # Providers agree — boost confidence
                    result["confirmations"] += 1
                    try:
                        doc.reference.update({
                            "confidence": min((data.get("confidence", 0.5) or 0.5) + 0.2, 0.98),
                            "cross_validated": True,
                            "validated_by": validate_source,
                            "validated_at": datetime.now(timezone.utc),
                        })
                    except Exception:
                        pass
                else:
                    # Providers disagree — flag for human review
                    result["corrections"] += 1
                    try:
                        corr_id = self._make_id(f"corr_{product}_{original_hs}")
                        self.db.collection("learned_corrections").document(corr_id).set({
                            "product": product,
                            "original_hs": original_hs,
                            "original_source": original_source,
                            "validated_hs": validated_hs,
                            "validated_source": validate_source,
                            "status": "needs_review",
                            "flagged_at": datetime.now(timezone.utc),
                        })
                        print(f"    🧠 SelfLearning: DISAGREEMENT on '{product[:30]}': "
                              f"{original_hs} vs {validated_hs} — flagged for review")
                    except Exception as e:
                        print(f"    🧠 SelfLearning: save correction error: {e}")

        except Exception as e:
            print(f"    🧠 SelfLearning: cross_validate_recent error: {e}")

        return result

    # ════════════════════════════════════════════════════════════════════════
    # AI PROVIDER CALLS
    # ════════════════════════════════════════════════════════════════════════

    def _ask_gemini(self, prompt, context=None):
        """Quick Gemini call for factual lookups. Cost: ~$0.002/call.

        Uses the existing gemini_classifier bridge if available,
        otherwise calls classification_agents.call_gemini directly.
        """
        try:
            # Try the bridge module first (handles key retrieval internally)
            from lib.gemini_classifier import _call_gemini
            result = _call_gemini(prompt)
            if result:
                self._cost_this_session += AI_COSTS["gemini_flash"]
            return result
        except ImportError:
            pass
        except Exception as e:
            print(f"    🧠 SelfLearning: Gemini bridge error: {e}")

        # Fallback: call directly via classification_agents
        try:
            from lib.classification_agents import call_gemini
            key = self._get_secret("GEMINI_API_KEY")
            if not key:
                if not self._gemini_warned:
                    print("    🧠 SelfLearning: GEMINI_API_KEY not configured, skipping Gemini")
                    self._gemini_warned = True
                return None
            system_prompt = "You are an expert AI assistant for RCB, an Israeli customs brokerage system."
            if context:
                prompt = f"Context: {context}\n\n{prompt}"
            result = call_gemini(key, system_prompt, prompt)
            if result:
                self._cost_this_session += AI_COSTS["gemini_flash"]
            return result
        except Exception as e:
            print(f"    🧠 SelfLearning: Gemini direct error: {e}")
            return None

    def _ask_claude(self, prompt, context=None):
        """Deep Claude call for complex reasoning. Cost: ~$0.05/call."""
        try:
            from lib.classification_agents import call_claude
            key = self._get_secret("ANTHROPIC_API_KEY")
            if not key:
                if not self._claude_warned:
                    print("    🧠 SelfLearning: ANTHROPIC_API_KEY not configured, skipping Claude")
                    self._claude_warned = True
                return None
            system_prompt = (
                "You are an expert AI assistant for RCB, an Israeli customs brokerage system. "
                "You specialize in HS code classification, Israeli import/export regulations, "
                "and logistics document analysis."
            )
            if context:
                prompt = f"Context: {context}\n\n{prompt}"
            result = call_claude(key, system_prompt, prompt)
            if result:
                self._cost_this_session += AI_COSTS["claude"]
            return result
        except Exception as e:
            print(f"    🧠 SelfLearning: Claude error: {e}")
            return None

    def _ask_chatgpt(self, prompt, context=None, model="gpt-4o-mini"):
        """ChatGPT call for cross-validation. Cost: ~$0.015/call (mini).

        Requires OPENAI_API_KEY in Secret Manager. Skips gracefully if missing.
        """
        key = self._get_secret("OPENAI_API_KEY")
        if not key:
            if not self._chatgpt_warned:
                print("    🧠 SelfLearning: OPENAI_API_KEY not configured, skipping ChatGPT")
                self._chatgpt_warned = True
            return None

        try:
            import openai
            client = openai.OpenAI(api_key=key)
            system_msg = (
                "You are an expert assistant for RCB, an Israeli customs brokerage system. "
                "You specialize in HS code classification, Israeli import/export regulations, "
                "and logistics document analysis."
            )
            user_msg = f"Context: {context}\n\n{prompt}" if context else prompt

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=1500,
                temperature=0.3,
            )
            result = response.choices[0].message.content
            cost_key = "chatgpt_mini" if "mini" in model else "chatgpt_4o"
            self._cost_this_session += AI_COSTS.get(cost_key, 0.02)
            return result
        except ImportError:
            if not self._chatgpt_warned:
                print("    🧠 SelfLearning: openai package not installed, skipping ChatGPT")
                self._chatgpt_warned = True
            return None
        except Exception as e:
            print(f"    🧠 SelfLearning: ChatGPT error: {e}")
            return None

    def _cross_validate(self, question, answers_dict):
        """Compare answers from multiple providers. Return consensus or flag disagreement.

        Args:
            question: str — the question asked
            answers_dict: dict — {"gemini": "answer1", "claude": "answer2", ...}

        Returns:
            dict with: consensus (bool), answer (str), confidence (float),
                       sources_agree (list), sources_disagree (list)
        """
        valid_answers = {k: v for k, v in answers_dict.items() if v}
        if not valid_answers:
            return {"consensus": False, "answer": None, "confidence": 0.0,
                    "sources_agree": [], "sources_disagree": []}

        if len(valid_answers) == 1:
            source, answer = next(iter(valid_answers.items()))
            return {"consensus": True, "answer": answer, "confidence": 0.6,
                    "sources_agree": [source], "sources_disagree": []}

        # Extract HS codes from each answer for comparison
        hs_codes = {}
        for source, answer in valid_answers.items():
            hs = self._extract_hs_code(answer)
            if hs:
                hs_codes[source] = hs

        if not hs_codes:
            # No structured data to compare — return first answer
            source, answer = next(iter(valid_answers.items()))
            return {"consensus": False, "answer": answer, "confidence": 0.4,
                    "sources_agree": [source], "sources_disagree": []}

        # Group by chapter (first 4 digits)
        chapters = {}
        for source, hs in hs_codes.items():
            chapter = hs.split(".")[0] if "." in hs else hs[:4]
            chapters.setdefault(chapter, []).append(source)

        # Find majority chapter
        majority_chapter = max(chapters, key=lambda c: len(chapters[c]))
        agree = chapters[majority_chapter]
        disagree = [s for c, sources in chapters.items()
                    if c != majority_chapter for s in sources]

        # Pick the most specific HS code from agreeing sources
        best_hs = ""
        for source in agree:
            if len(hs_codes[source]) > len(best_hs):
                best_hs = hs_codes[source]

        confidence = len(agree) / len(hs_codes) if hs_codes else 0.0

        return {
            "consensus": len(disagree) == 0,
            "answer": best_hs,
            "confidence": min(confidence, 0.95),
            "sources_agree": agree,
            "sources_disagree": disagree,
        }

    # ════════════════════════════════════════════════════════════════════════
    # PATTERN MANAGEMENT (Levels 0-3)
    # ════════════════════════════════════════════════════════════════════════

    def _find_exact_match(self, collection, query_fields):
        """Level 0: Exact match — same sender email in learned_contacts."""
        sender = query_fields.get("sender_email", "")
        if not sender:
            return None

        try:
            docs = (self.db.collection(collection)
                    .where("sender_email", "==", sender)
                    .limit(1).stream())
            for doc in docs:
                data = doc.to_dict()
                if data and data.get("times_seen", 0) >= 1:
                    return {
                        "sender_email": sender,
                        "doc_types": data.get("doc_types", []),
                        "shipping_lines": data.get("shipping_lines", []),
                        "ports": data.get("ports", []),
                        "times_seen": data.get("times_seen", 0),
                        "level": "exact",
                    }
        except Exception:
            pass
        return None

    def _find_similar_match(self, collection, query_fields):
        """Level 1: Similar match — same domain or overlapping keywords."""
        domain = query_fields.get("sender_domain", "")
        if not domain:
            return None

        try:
            docs = (self.db.collection(collection)
                    .where("sender_domain", "==", domain)
                    .limit(5).stream())
            best_match = None
            best_score = 0
            subject_kw = set(query_fields.get("subject_keywords", []))

            for doc in docs:
                data = doc.to_dict() or {}
                # Skip the exact sender (that's Level 0)
                if data.get("sender_email") == query_fields.get("sender_email"):
                    continue
                # Score by doc_types and shipping_lines overlap
                score = data.get("times_seen", 0)
                if score > best_score:
                    best_score = score
                    best_match = data

            if best_match and best_score >= 1:
                return {
                    "sender_domain": domain,
                    "doc_types": best_match.get("doc_types", []),
                    "shipping_lines": best_match.get("shipping_lines", []),
                    "ports": best_match.get("ports", []),
                    "times_seen": best_match.get("times_seen", 0),
                    "matched_sender": best_match.get("sender_email", ""),
                    "level": "similar",
                }
        except Exception:
            pass
        return None

    def _find_pattern_match(self, collection, query_fields):
        """Level 2: Pattern match — known doc type from attachment keywords."""
        att_keywords = query_fields.get("attachment_keywords", [])
        subject_keywords = query_fields.get("subject_keywords", [])
        all_keywords = set(att_keywords + subject_keywords)

        if not all_keywords:
            return None

        # Known logistics document patterns
        doc_patterns = {
            "bill_of_lading": {"bl", "bol", "lading", "bill", "שטר"},
            "packing_list": {"packing", "list", "רשימת", "אריזה"},
            "invoice": {"invoice", "commercial", "חשבונית"},
            "arrival_notice": {"arrival", "notice", "הגעה", "הודעת"},
            "delivery_order": {"delivery", "order", "release", "שחרור"},
            "certificate": {"certificate", "cert", "origin", "תעודה", "מקור"},
            "port_report": {"port", "vessel", "report", "דוח", "כלי", "שיט"},
            "customs_declaration": {"customs", "declaration", "מכס", "הצהרה"},
        }

        best_type = None
        best_overlap = 0

        for doc_type, pattern_kws in doc_patterns.items():
            overlap = len(all_keywords & pattern_kws)
            if overlap > best_overlap:
                best_overlap = overlap
                best_type = doc_type

        if best_type and best_overlap >= 1:
            # Also check if we have learned_patterns for this doc_type
            try:
                pattern_docs = (
                    self.db.collection(collection)
                    .where("doc_type", "==", best_type)
                    .limit(3)
                    .stream()
                )
                for pdoc in pattern_docs:
                    pdata = pdoc.to_dict() or {}
                    return {
                        "doc_type": best_type,
                        "expected_fields": pdata.get("extraction_keys", []),
                        "has_containers": pdata.get("has_containers", False),
                        "has_bols": pdata.get("has_bols", False),
                        "confidence_hint": pdata.get("confidence", 0.5),
                        "level": "pattern",
                    }
            except Exception:
                pass

            # Even without stored pattern, return the detected type
            return {
                "doc_type": best_type,
                "expected_fields": [],
                "level": "pattern",
            }

        return None

    def _try_partial_knowledge(self, query_fields):
        """Level 3: Quick AI call to fill gap in partial knowledge.

        Only called if Levels 0-2 failed but we have SOME knowledge
        (sender domain is in contacts or knowledge_base).
        """
        domain = query_fields.get("sender_domain", "")
        subject = query_fields.get("subject", "")

        if not domain and not subject:
            return None

        # Check if domain exists anywhere in our read-only knowledge
        has_partial = False
        domain_info = ""

        try:
            if domain:
                # Check contacts collection (READ ONLY)
                contact_docs = (self.db.collection("contacts")
                                .where("domain", "==", domain)
                                .limit(1).stream())
                for cdoc in contact_docs:
                    cdata = cdoc.to_dict() or {}
                    has_partial = True
                    domain_info = f"Known contact: {cdata.get('name', domain)}, role: {cdata.get('role', 'unknown')}"
                    break
        except Exception:
            pass

        if not has_partial:
            try:
                # Check brain_index for domain keywords (READ ONLY)
                domain_base = domain.split(".")[0] if "." in domain else domain
                if domain_base and len(domain_base) >= 3:
                    bi_docs = (self.db.collection("brain_index")
                               .where("keyword", "==", domain_base)
                               .limit(1).stream())
                    for bdoc in bi_docs:
                        has_partial = True
                        domain_info = f"Known keyword: {domain_base}"
                        break
            except Exception:
                pass

        if not has_partial:
            return None

        # We have SOME knowledge — quick Gemini call to fill the gap
        prompt = (
            f"In Israeli customs/logistics context:\n"
            f"Sender domain: {domain}\n"
            f"Email subject: {subject}\n"
            f"Known info: {domain_info}\n\n"
            f"What type of logistics document is this likely to be? "
            f"What data should we expect? Answer briefly in JSON format: "
            f'{{"doc_type": "...", "expected_fields": [...], "confidence": 0.0-1.0}}'
        )

        answer = self._ask_gemini(prompt)
        if not answer:
            return None

        try:
            # Try to parse JSON from Gemini response
            parsed = json.loads(answer)
            return {
                "doc_type": parsed.get("doc_type", "unknown"),
                "expected_fields": parsed.get("expected_fields", []),
                "partial_source": domain_info,
                "confidence_hint": parsed.get("confidence", 0.5),
                "level": "partial",
            }
        except (json.JSONDecodeError, TypeError):
            # Gemini didn't return clean JSON — extract what we can
            return {
                "doc_type": "unknown",
                "gemini_hint": answer[:500],
                "partial_source": domain_info,
                "level": "partial",
            }

    # ════════════════════════════════════════════════════════════════════════
    # ACTIVE RESEARCH HELPERS
    # ════════════════════════════════════════════════════════════════════════

    def _research_topic(self, topic, budget=1.0):
        """Research a specific topic using available AI providers.

        Returns cost spent.
        """
        cost = 0.0
        answers = {}

        # Ask Gemini first (cheapest)
        if budget >= AI_COSTS["gemini_flash"]:
            answers["gemini"] = self._ask_gemini(
                f"In Israeli customs/logistics context, provide factual information about: {topic}. "
                f"Include HS codes, regulations, or standard procedures if applicable."
            )
            cost += AI_COSTS["gemini_flash"]

        # Ask ChatGPT for cross-validation if budget allows
        if budget - cost >= AI_COSTS["chatgpt_mini"]:
            answers["chatgpt"] = self._ask_chatgpt(
                f"In Israeli customs/logistics context, provide factual information about: {topic}. "
                f"Include HS codes, regulations, or standard procedures if applicable."
            )
            if answers.get("chatgpt"):
                cost += AI_COSTS["chatgpt_mini"]

        # Only ask Claude for complex/expensive topics
        if budget - cost >= AI_COSTS["claude"] and not answers.get("gemini"):
            answers["claude"] = self._ask_claude(
                f"In Israeli customs/logistics context, provide factual information about: {topic}. "
                f"Include HS codes, regulations, or standard procedures if applicable."
            )
            if answers.get("claude"):
                cost += AI_COSTS["claude"]

        # Cross-validate and store
        validation = self._cross_validate(topic, answers)
        if validation.get("answer"):
            try:
                topic_id = self._make_id(f"research_{topic}")
                self.db.collection("learned_answers").document(topic_id).set({
                    "topic": topic,
                    "answer": validation["answer"],
                    "full_answers": {k: (v[:1000] if v else None) for k, v in answers.items()},
                    "consensus": validation["consensus"],
                    "confidence": validation["confidence"],
                    "sources_agree": validation["sources_agree"],
                    "sources_disagree": validation["sources_disagree"],
                    "source": "active_enrichment",
                    "learned_at": datetime.now(timezone.utc),
                    "cost": cost,
                }, merge=True)
                print(f"    🧠 SelfLearning: researched '{topic[:40]}' — "
                      f"consensus={validation['consensus']}, cost=${cost:.4f}")
            except Exception as e:
                print(f"    🧠 SelfLearning: save research error: {e}")

        return cost

    def _research_corrections(self, max_items=5, budget=1.0):
        """Research topics where we previously got something wrong.

        Returns: dict with researched, corrections, cost
        """
        result = {"researched": 0, "corrections": 0, "cost": 0.0}

        try:
            corr_docs = (
                self.db.collection("learned_corrections")
                .where("status", "==", "needs_review")
                .limit(max_items)
                .stream()
            )

            for doc in corr_docs:
                if result["cost"] >= budget:
                    break

                data = doc.to_dict() or {}
                product = data.get("product", "")
                if not product:
                    continue

                # Ask a third provider to break the tie
                original_hs = data.get("original_hs", "")
                validated_hs = data.get("validated_hs", "")

                tiebreaker = self._ask_chatgpt(
                    f"What is the correct HS code for: {product}? "
                    f"Two sources disagree: {original_hs} vs {validated_hs}. "
                    f"Which is correct and why? Answer with the HS code first."
                )
                result["researched"] += 1
                if tiebreaker:
                    result["cost"] += AI_COSTS["chatgpt_mini"]

                    resolved_hs = self._extract_hs_code(tiebreaker)
                    if resolved_hs:
                        try:
                            doc.reference.update({
                                "tiebreaker_answer": tiebreaker[:500],
                                "tiebreaker_hs": resolved_hs,
                                "tiebreaker_source": "chatgpt",
                                "status": "resolved" if resolved_hs else "needs_human",
                                "resolved_at": datetime.now(timezone.utc),
                            })
                            result["corrections"] += 1

                            # Update the original classification
                            self.learn_classification(
                                product, resolved_hs, "cross_validated",
                                "tiebreaker_chatgpt", 0.85
                            )
                        except Exception as e:
                            print(f"    🧠 SelfLearning: correction save error: {e}")

        except Exception as e:
            print(f"    🧠 SelfLearning: research corrections error: {e}")

        return result

    def _search_web(self, query):
        """Search the web for information. Gracefully skips if not available.

        Designed for: Israeli customs resources, port websites, carrier tracking.
        Works from PC agents/scripts. Skips in Cloud Functions.

        Returns: str or None
        """
        try:
            import httpx
        except ImportError:
            return None

        # Sanitize and prepare query
        safe_query = query.replace('"', "").strip()
        if not safe_query:
            return None

        # Try Israeli customs Shaar Olami API
        try:
            response = httpx.get(
                "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Import/CustomsTaarifEntry",
                params={"search": safe_query},
                timeout=15.0,
                follow_redirects=True,
            )
            if response.status_code == 200 and len(response.text) > 100:
                return response.text[:3000]
        except Exception:
            pass

        return None

    # ════════════════════════════════════════════════════════════════════════
    # STATISTICS & REPORTING
    # ════════════════════════════════════════════════════════════════════════

    def get_memory_stats(self):
        """Return counts and effectiveness stats for brain commander status reports.

        Returns: dict with collection counts, hit rates, etc.
        """
        stats = {
            "collections": {},
            "session_cost": self._cost_this_session,
        }

        collections_to_count = [
            "learned_classifications",
            "learned_answers",
            "learned_contacts",
            "learned_patterns",
            "learned_corrections",
        ]

        for coll_name in collections_to_count:
            try:
                # Count documents (limit to avoid expensive full scans)
                count = 0
                docs = self.db.collection(coll_name).limit(1000).stream()
                for _ in docs:
                    count += 1
                stats["collections"][coll_name] = count
            except Exception:
                stats["collections"][coll_name] = -1

        # Read-only collection counts (approximate)
        readonly_collections = {
            "brain_index": 11254,
            "keyword_index": 8013,
            "product_index": 61,
            "supplier_index": 0,
            "classification_knowledge": 58,
            "knowledge_base": 294,
            "contacts": 9,
        }
        for coll_name, approx in readonly_collections.items():
            try:
                count = 0
                docs = self.db.collection(coll_name).limit(100).stream()
                for _ in docs:
                    count += 1
                stats["collections"][coll_name] = count if count > 0 else approx
            except Exception:
                stats["collections"][coll_name] = approx

        # Usage stats from memory_usage tracking
        try:
            usage_docs = (
                self.db.collection("learned_patterns")
                .order_by("learned_at", direction="DESCENDING")
                .limit(100)
                .stream()
            )
            level_counts = {"exact": 0, "similar": 0, "partial": 0, "pattern": 0, "none": 0}
            total = 0
            for doc in usage_docs:
                data = doc.to_dict() or {}
                source = data.get("source", "")
                for level in level_counts:
                    if level in source:
                        level_counts[level] += 1
                        break
                total += 1
            stats["recent_usage"] = level_counts
            stats["recent_total"] = total
            if total > 0:
                free_hits = level_counts["exact"] + level_counts["similar"] + level_counts["pattern"]
                stats["memory_hit_rate"] = round(free_hits / total, 2)
            else:
                stats["memory_hit_rate"] = 0.0
        except Exception:
            stats["recent_usage"] = {}
            stats["memory_hit_rate"] = 0.0

        return stats

    def get_cost_savings(self, period_days=30):
        """Calculate how much money memory saved vs full AI calls.

        Assumes: Every memory hit (Level 0/1/2) saved one full AI call ($0.05).
        Level 3 saved partial ($0.05 - $0.003 = $0.047).

        Returns: dict with estimated_savings, total_lookups, free_lookups, paid_lookups
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
            docs = (
                self.db.collection("learned_patterns")
                .where("learned_at", ">=", cutoff)
                .limit(5000)
                .stream()
            )

            total = 0
            free = 0  # Level 0/1/2
            partial = 0  # Level 3
            full = 0  # Level 4

            for doc in docs:
                data = doc.to_dict() or {}
                source = data.get("source", "")
                total += 1
                if "exact" in source or "similar" in source or "pattern" in source:
                    free += 1
                elif "partial" in source:
                    partial += 1
                else:
                    full += 1

            full_cost_per_call = 0.05
            partial_cost_per_call = 0.003
            savings = (free * full_cost_per_call) + (partial * (full_cost_per_call - partial_cost_per_call))

            return {
                "period_days": period_days,
                "total_lookups": total,
                "free_lookups": free,
                "partial_lookups": partial,
                "full_ai_lookups": full,
                "estimated_savings": round(savings, 2),
                "savings_rate": round(free / total, 2) if total > 0 else 0.0,
            }
        except Exception as e:
            print(f"    🧠 SelfLearning: cost savings calc error: {e}")
            return {
                "period_days": period_days,
                "total_lookups": 0,
                "estimated_savings": 0.0,
                "error": str(e),
            }

    # ════════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ════════════════════════════════════════════════════════════════════════

    def _get_secret(self, name):
        """Get API key from Secret Manager (with caching)."""
        if name in self._api_keys:
            return self._api_keys[name]

        key = None

        # Try provided function first
        if self._get_secret_func:
            try:
                key = self._get_secret_func(name)
            except Exception:
                pass

        # Fallback: Google Cloud Secret Manager
        if not key:
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                secret_path = f"projects/rpa-port-customs/secrets/{name}/versions/latest"
                response = client.access_secret_version(request={"name": secret_path})
                key = response.payload.data.decode("UTF-8")
            except Exception:
                pass

        # Fallback: environment variable
        if not key:
            try:
                import os
                key = os.environ.get(name)
            except Exception:
                pass

        if key:
            self._api_keys[name] = key
        return key

    def _extract_keywords(self, text):
        """Extract meaningful keywords from text (English + Hebrew)."""
        if not text:
            return []
        text = text.lower()
        # Split on non-alphanumeric (keeping Hebrew chars)
        words = re.findall(r'[a-z0-9\u0590-\u05ff]+', text)
        # Filter out very short words and common stopwords
        stopwords = {
            "the", "and", "for", "from", "with", "this", "that", "are", "was",
            "has", "have", "had", "not", "but", "pdf", "doc", "xlsx", "jpg",
            "png", "re", "fw", "fwd", "att", "com", "org", "net", "il",
            "של", "את", "על", "עם", "לא", "כי", "אם", "גם", "או", "הוא",
        }
        return [w for w in words if len(w) >= 2 and w not in stopwords]

    def _extract_hs_code(self, text):
        """Extract an HS code from AI response text."""
        if not text:
            return ""
        # Match patterns like 4011.10, 40.11, 4011.10.00, etc.
        patterns = [
            r'\b(\d{4}\.\d{2}\.\d{2})\b',  # 4011.10.00
            r'\b(\d{4}\.\d{2})\b',           # 4011.10
            r'\b(\d{2}\.\d{2})\b',           # 40.11
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _make_id(self, text):
        """Create a stable Firestore document ID from text."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:20]

    def _record_memory_usage(self, source, confidence):
        """Track memory level usage for statistics."""
        try:
            now = datetime.now(timezone.utc)
            day_key = now.strftime("%Y%m%d")
            stat_id = f"usage_{day_key}"
            stat_ref = self.db.collection("learned_patterns").document(f"_stats_{stat_id}")

            # Determine level from source
            level = "none"
            for lvl in ("exact", "similar", "pattern", "partial"):
                if lvl in (source or ""):
                    level = lvl
                    break

            # Use Firestore increment if available, else simple set
            try:
                from google.cloud.firestore_v1 import Increment
                stat_ref.set({
                    f"level_{level}": Increment(1),
                    "last_updated": now,
                }, merge=True)
            except ImportError:
                # Fallback: read-modify-write
                existing = stat_ref.get()
                if existing.exists:
                    data = existing.to_dict() or {}
                    count = (data.get(f"level_{level}", 0) or 0) + 1
                    stat_ref.update({f"level_{level}": count, "last_updated": now})
                else:
                    stat_ref.set({
                        f"level_{level}": 1,
                        "last_updated": now,
                    })
        except Exception:
            pass  # Stats tracking is best-effort

    # ════════════════════════════════════════════════════════
    #  ONE-TIME HISTORICAL BACKFILL
    # ════════════════════════════════════════════════════════

    def backfill_from_history(self, max_docs=2000):
        """One-time READ-ONLY mining of historical tracker_observations and rcb_processed.

        For each email: extract agent→carrier mappings, learn doc templates,
        extract BOL prefix patterns. Stores everything in brain collections.
        Does NOT reprocess or resend any emails.

        Args:
            max_docs: int — maximum documents to scan (safety limit)

        Returns:
            dict — stats of what was learned
        """
        stats = {
            'observations_scanned': 0,
            'rcb_processed_scanned': 0,
            'bol_prefixes_learned': 0,
            'agent_mappings_learned': 0,
            'patterns_learned': 0,
            'errors': 0,
        }

        print("🧠 Backfill: scanning tracker_observations...")
        try:
            obs_docs = self.db.collection('tracker_observations').limit(max_docs).stream()
            for doc in obs_docs:
                stats['observations_scanned'] += 1
                try:
                    data = doc.to_dict()
                    sender = data.get('from_email', '')
                    extractions = data.get('extractions', {})
                    attachments = data.get('attachment_names', [])
                    if not extractions:
                        continue

                    # Guess doc type from attachments
                    doc_type = ''
                    for name in (attachments or []):
                        n = name.lower()
                        if any(x in n for x in ['bl', 'lading', 'bol']):
                            doc_type = 'bill_of_lading'
                        elif any(x in n for x in ['booking', 'bkg']):
                            doc_type = 'booking_confirmation'
                        elif any(x in n for x in ['delivery', 'do_']):
                            doc_type = 'delivery_order'
                        elif any(x in n for x in ['invoice', 'inv']):
                            doc_type = 'invoice'
                        if doc_type:
                            break

                    # Feed through learn_tracking_extraction (reuses all learning logic)
                    self.learn_tracking_extraction(
                        sender_email=sender,
                        doc_type=doc_type or 'unknown',
                        extractions=extractions,
                        confidence=0.5,
                        source='backfill_history'
                    )
                    stats['patterns_learned'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 5:
                        print(f"    Backfill obs error: {e}")
        except Exception as e:
            print(f"🧠 Backfill: tracker_observations scan error: {e}")

        print(f"🧠 Backfill: scanned {stats['observations_scanned']} observations")

        print("🧠 Backfill: scanning rcb_processed...")
        try:
            processed_docs = self.db.collection('rcb_processed').limit(max_docs).stream()
            for doc in processed_docs:
                stats['rcb_processed_scanned'] += 1
                try:
                    data = doc.to_dict()
                    sender = data.get('from_email', '') or data.get('sender', '')
                    # rcb_processed may have extractions or structured data
                    extractions = data.get('extractions', {})
                    if not extractions:
                        # Try to reconstruct from top-level fields
                        bols = []
                        if data.get('bol_number'):
                            bols.append(data['bol_number'])
                        containers = data.get('containers', [])
                        shipping_lines = []
                        if data.get('shipping_line'):
                            shipping_lines.append(data['shipping_line'])
                        if bols or containers or shipping_lines:
                            extractions = {
                                'bols': bols,
                                'containers': containers,
                                'shipping_lines': shipping_lines,
                            }
                    if not extractions:
                        continue

                    doc_type = data.get('doc_type', data.get('document_type', 'unknown'))
                    self.learn_tracking_extraction(
                        sender_email=sender,
                        doc_type=doc_type,
                        extractions=extractions,
                        confidence=0.5,
                        source='backfill_history'
                    )
                    stats['patterns_learned'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 5:
                        print(f"    Backfill rcb error: {e}")
        except Exception as e:
            print(f"🧠 Backfill: rcb_processed scan error: {e}")

        print(f"🧠 Backfill: scanned {stats['rcb_processed_scanned']} processed docs")
        print(f"🧠 Backfill complete: {stats}")
        return stats
