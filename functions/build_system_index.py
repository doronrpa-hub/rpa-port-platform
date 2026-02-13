"""
Build System Index — Auto-generate docs/SYSTEM_INDEX.md from actual code + Firebase.
======================================================================================
Reads every .py file, extracts functions/classes/imports/line counts.
Queries Firestore for live collection counts.
Maps Cloud Functions, API integrations, data flows.
Detects wired vs unwired modules.

Usage:
    python build_system_index.py              # Full rebuild (code + Firebase)
    python build_system_index.py --code-only  # Code scan only (no Firebase)
    python build_system_index.py --counts-only # Just update Firebase counts

Output: ../docs/SYSTEM_INDEX.md (overwrites)

Can be run anytime to keep the index current.
Created: Session 19 (February 13, 2026)
"""

import os
import re
import ast
import sys
import glob
from datetime import datetime, timezone
from collections import defaultdict

# ─── Configuration ───────────────────────────────────────────────────────────

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FUNCTIONS_DIR = os.path.join(REPO_ROOT, "functions")
LIB_DIR = os.path.join(FUNCTIONS_DIR, "lib")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "SYSTEM_INDEX_GENERATED.md")
SNAPSHOT_PATH = os.path.join(REPO_ROOT, "docs", "SYSTEM_SNAPSHOTS.md")
MAIN_PY = os.path.join(FUNCTIONS_DIR, "main.py")

# SYSTEM_INDEX.md is the hand-written comprehensive index — NEVER overwritten.
# SYSTEM_INDEX_GENERATED.md is the auto-generated version — overwritten each run.
# SYSTEM_SNAPSHOTS.md is the historical log — APPENDED each run, never erased.

# Collections we know about (to detect new ones)
KNOWN_COLLECTIONS = [
    "brain_index", "keyword_index", "product_index", "supplier_index",
    "tariff", "tariff_chapters", "legal_requirements",
    "librarian_index", "librarian_search_log", "librarian_enrichment_log",
    "knowledge_base", "classification_knowledge", "knowledge", "knowledge_queries",
    "rcb_classifications", "rcb_silent_classifications", "classifications",
    "rcb_processed", "rcb_logs", "rcb_inbox", "inbox",
    "session_backups", "session_missions", "sessions_backup",
    "rcb_inspector_reports", "rcb_test_reports",
    "fta_agreements", "regulatory_requirements", "classification_rules",
    "ministry_index", "enrichment_tasks", "agent_tasks",
    "batch_reprocess_results", "batch_reprocess_summary",
    "pupil_teachings", "sellers", "buyers",
    "system_metadata", "system_state", "system_status", "system_counters",
    "config", "declarations", "regulatory_certificates",
    "pc_agent_tasks", "pending_tasks", "monitor_errors", "learning_log",
    "hs_code_index", "free_import_cache", "licensing_knowledge",
    "procedures", "document_types", "shipping_lines",
    "triangle_learnings", "verification_cache",
    "enrichment_log", "rcb_first_emails", "rcb_stats", "rcb_pdf_requests",
    "librarian_tags",
]


# ─── Code Scanner ────────────────────────────────────────────────────────────

class FileInfo:
    """Information extracted from a single .py file."""
    def __init__(self, path):
        self.path = path
        self.rel_path = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        self.filename = os.path.basename(path)
        self.lines = 0
        self.functions = []      # [(name, line_no, args)]
        self.classes = []        # [(name, line_no)]
        self.imports_from_lib = []  # [module_name]
        self.docstring = ""
        self.collections_read = set()
        self.collections_write = set()
        self.decorators = []     # [(decorator_text, line_no, func_name)]
        self.api_calls = []      # [(api_name, line_no)]

    def scan(self):
        """Read and parse the file."""
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                raw_lines = content.split("\n")
        except Exception as e:
            print(f"  ERROR reading {self.rel_path}: {e}")
            return self

        self.lines = len(raw_lines)

        # Extract docstring
        try:
            tree = ast.parse(content)
            ds = ast.get_docstring(tree)
            if ds:
                self.docstring = ds.split("\n")[0].strip()
        except SyntaxError:
            pass

        # Line-by-line scan for functions, classes, decorators, collections, API calls
        pending_decorators = []
        for i, line in enumerate(raw_lines, 1):
            stripped = line.strip()

            # Decorators
            if stripped.startswith("@"):
                pending_decorators.append((stripped, i))

            # Functions
            m = re.match(r"^def\s+(\w+)\s*\((.*?)\)?", stripped)
            if m:
                fname = m.group(1)
                fargs = m.group(2) if m.group(2) else ""
                self.functions.append((fname, i, fargs))
                # Associate pending decorators
                for dec_text, dec_line in pending_decorators:
                    self.decorators.append((dec_text, dec_line, fname))
                pending_decorators = []
                continue

            # Classes
            m = re.match(r"^class\s+(\w+)", stripped)
            if m:
                self.classes.append((m.group(1), i))
                pending_decorators = []
                continue

            # Clear decorators if we hit a non-decorator, non-def, non-class, non-blank line
            if stripped and not stripped.startswith("@") and not stripped.startswith("#"):
                pending_decorators = []

            # Imports from lib
            m = re.match(r"from\s+(?:\.|\blib\.)(\w+)\s+import", stripped)
            if m:
                mod = m.group(1)
                if mod not in self.imports_from_lib:
                    self.imports_from_lib.append(mod)

            # Firestore collection references
            for cm in re.finditer(r'\.collection\(["\'](\w+)["\']\)', stripped):
                coll = cm.group(1)
                # Heuristic: .set( or .add( or .update( = write; .get( or .stream( or .where( = read
                if (".set(" in stripped or ".add(" in stripped
                        or ".update(" in stripped or ".delete(" in stripped):
                    self.collections_write.add(coll)
                else:
                    self.collections_read.add(coll)

            # API calls
            if "anthropic" in stripped.lower() or "claude" in stripped.lower():
                if "api_key" in stripped or "messages.create" in stripped or "anthropic.com" in stripped:
                    self.api_calls.append(("Anthropic/Claude", i))
            if "generativelanguage.googleapis.com" in stripped:
                self.api_calls.append(("Google Gemini", i))
            if "graph.microsoft.com" in stripped:
                self.api_calls.append(("Microsoft Graph", i))
            if "economy.gov.il" in stripped or "data.gov.il" in stripped:
                self.api_calls.append(("gov.il API", i))

        return self


def scan_all_files():
    """Scan all .py files in the project."""
    files = {}

    # Lib modules
    for path in sorted(glob.glob(os.path.join(LIB_DIR, "*.py"))):
        fi = FileInfo(path).scan()
        files[fi.rel_path] = fi

    # Top-level functions/ scripts
    for path in sorted(glob.glob(os.path.join(FUNCTIONS_DIR, "*.py"))):
        fi = FileInfo(path).scan()
        files[fi.rel_path] = fi

    # Root-level scripts
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "*.py"))):
        fi = FileInfo(path).scan()
        files[fi.rel_path] = fi

    return files


# ─── Cloud Function Detector ─────────────────────────────────────────────────

def detect_cloud_functions(main_info):
    """Extract Cloud Function definitions from main.py decorators."""
    schedulers = []
    http_triggers = []
    firestore_triggers = []

    for dec_text, dec_line, func_name in main_info.decorators:
        if "on_schedule" in dec_text:
            # Extract schedule
            sched_match = re.search(r'schedule="([^"]+)"', dec_text)
            schedule = sched_match.group(1) if sched_match else "unknown"
            schedulers.append({
                "name": func_name,
                "line": dec_line,
                "schedule": schedule,
            })
        elif "on_request" in dec_text or "https_fn" in dec_text:
            http_triggers.append({
                "name": func_name,
                "line": dec_line,
            })
        elif "on_document_created" in dec_text or "on_document_updated" in dec_text:
            doc_match = re.search(r'document="([^"]+)"', dec_text)
            document = doc_match.group(1) if doc_match else "unknown"
            trigger_type = "created" if "created" in dec_text else "updated"
            firestore_triggers.append({
                "name": func_name,
                "line": dec_line,
                "document": document,
                "trigger": trigger_type,
            })

    return schedulers, http_triggers, firestore_triggers


# ─── Module Wiring Detector ──────────────────────────────────────────────────

def detect_wiring(files):
    """Determine which lib modules are actually imported/called from main.py or other active modules."""
    main_info = files.get("functions/main.py")
    if not main_info:
        return {}

    # Direct imports from main.py
    directly_imported = set(main_info.imports_from_lib)

    # Also check which modules are imported by directly-imported modules (one level deep)
    indirectly_imported = set()
    for mod in directly_imported:
        mod_path = f"functions/lib/{mod}.py"
        if mod_path in files:
            for sub_mod in files[mod_path].imports_from_lib:
                indirectly_imported.add(sub_mod)

    wiring = {}
    for rel_path, fi in files.items():
        if not rel_path.startswith("functions/lib/") or fi.filename == "__init__.py":
            continue
        mod_name = fi.filename.replace(".py", "")
        if mod_name in directly_imported:
            wiring[mod_name] = "DIRECT (imported by main.py)"
        elif mod_name in indirectly_imported:
            wiring[mod_name] = "INDIRECT (imported by wired module)"
        else:
            wiring[mod_name] = "NOT WIRED (not reachable from main.py)"

    return wiring


# ─── Collection Reference Map ────────────────────────────────────────────────

def build_collection_map(files):
    """Build map of which files read/write each Firestore collection."""
    reads = defaultdict(list)
    writes = defaultdict(list)

    for rel_path, fi in files.items():
        short = fi.filename
        for c in fi.collections_read:
            reads[c].append(short)
        for c in fi.collections_write:
            writes[c].append(short)

    return reads, writes


# ─── Firebase Querier ─────────────────────────────────────────────────────────

def query_firestore_counts():
    """Query live Firestore collection counts."""
    try:
        import firebase_admin
        from firebase_admin import firestore as fs
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        db = fs.client()
    except Exception as e:
        print(f"  WARNING: Cannot connect to Firebase: {e}")
        return {}, {}

    counts = {}
    print("  Querying Firestore collections...")
    for coll_name in sorted(set(KNOWN_COLLECTIONS)):
        try:
            docs = list(db.collection(coll_name).select([]).stream())
            counts[coll_name] = len(docs)
        except Exception:
            counts[coll_name] = -1  # Error

    # Also discover any collections we DON'T know about
    discovered = {}
    try:
        for coll_ref in db.collections():
            if coll_ref.id not in KNOWN_COLLECTIONS:
                try:
                    docs = list(db.collection(coll_ref.id).select([]).stream())
                    discovered[coll_ref.id] = len(docs)
                except Exception:
                    discovered[coll_ref.id] = -1
    except Exception:
        pass

    return counts, discovered


def query_system_metadata():
    """Get last run times from system_metadata."""
    try:
        import firebase_admin
        from firebase_admin import firestore as fs
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        db = fs.client()

        metadata = {}
        for doc in db.collection("system_metadata").stream():
            data = doc.to_dict()
            metadata[doc.id] = {
                "last_run": str(data.get("last_run", "")),
                "mode": data.get("mode", ""),
            }

        # System status
        status = {}
        for doc in db.collection("system_status").stream():
            data = doc.to_dict()
            status[doc.id] = {
                "status": data.get("status", ""),
                "last_check": str(data.get("last_check", "")),
            }

        # Inspector health
        inspector = {}
        try:
            reports = list(db.collection("rcb_inspector_reports")
                          .order_by("timestamp", direction=fs.Query.DESCENDING)
                          .limit(1).stream())
            if reports:
                data = reports[0].to_dict()
                inspector = {
                    "health_score": data.get("health_score", "?"),
                    "health": data.get("health", "?"),
                    "issue_count": data.get("issue_count", 0),
                    "warning_count": data.get("warning_count", 0),
                    "timestamp": str(data.get("timestamp", "")),
                }
        except Exception:
            pass

        # Classification stats
        cls_stats = {"total": 0, "success": 0, "clarification": 0, "other": 0}
        try:
            for doc in db.collection("rcb_classifications").select(["subject"]).stream():
                cls_stats["total"] += 1
                subj = doc.to_dict().get("subject", "")
                if "\u2705" in subj:  # ✅
                    cls_stats["success"] += 1
                elif "\u05d4\u05d1\u05d4\u05e8\u05d4" in subj:  # הבהרה
                    cls_stats["clarification"] += 1
                else:
                    cls_stats["other"] += 1
        except Exception:
            pass

        # System counters sum
        counter_sum = 0
        try:
            for doc in db.collection("system_counters").stream():
                data = doc.to_dict()
                counter_sum += data.get("seq", 0)
        except Exception:
            pass

        return metadata, status, inspector, cls_stats, counter_sum

    except Exception as e:
        print(f"  WARNING: Cannot query metadata: {e}")
        return {}, {}, {}, {}, 0


# ─── Dead Code Detector ──────────────────────────────────────────────────────

KNOWN_ACTIVE_SCRIPTS = {
    "main.py", "batch_reprocess.py", "deep_learn.py", "enrich_knowledge.py",
    "knowledge_indexer.py", "read_everything.py", "import_knowledge.py",
    "build_system_index.py",
}

KNOWN_DEAD_PREFIXES = ("add_", "fix_", "patch_", "final_", "main_fix", "name_fix", "move_")


def classify_script(filename):
    """Classify a top-level script as active, utility, test, or dead."""
    if filename in KNOWN_ACTIVE_SCRIPTS:
        return "Active"
    if filename.startswith("test_"):
        return "Test"
    if filename.startswith(KNOWN_DEAD_PREFIXES):
        return "Dead (patch/fix)"
    if filename in ("cleanup_old_results.py", "clear_processed.py", "remove_duplicates.py",
                     "rcb_diagnostic.py"):
        return "Utility"
    return "Unknown"


# ─── Markdown Generator ──────────────────────────────────────────────────────

def generate_markdown(files, wiring, coll_reads, coll_writes, coll_counts,
                      discovered_collections, schedulers, http_triggers,
                      firestore_triggers, metadata, status, inspector,
                      cls_stats, counter_sum):
    """Generate the full SYSTEM_INDEX.md content."""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []

    def w(text=""):
        lines.append(text)

    # ── Header ──
    w("# RCB System Index")
    w("## Auto-generated from actual code + live Firebase queries")
    w(f"## Last updated: {now}")
    w(f"## Generator: `functions/build_system_index.py`")
    w()
    w("To regenerate: `cd functions && python build_system_index.py`")
    w()
    w("---")
    w()

    # ── Table of Contents ──
    w("## Table of Contents")
    w()
    w("1. [System Health Summary](#1-system-health-summary)")
    w("2. [Library Modules](#2-library-modules-functionslib)")
    w("3. [Cloud Functions](#3-cloud-functions-functionsmainpy)")
    w("4. [Standalone Scripts](#4-standalone-scripts)")
    w("5. [Firestore Collections](#5-firestore-collections)")
    w("6. [External APIs](#6-external-apis)")
    w("7. [Module Wiring](#7-module-wiring)")
    w("8. [Files NOT in Repo](#8-files-not-in-repo)")
    w("9. [Dead Code](#9-dead-code)")
    w()
    w("---")
    w()

    # ── 1. System Health ──
    w("## 1. System Health Summary")
    w()
    if inspector:
        w(f"- **Health Score:** {inspector.get('health_score', '?')}/100 ({inspector.get('health', '?')})")
        w(f"- **Issues:** {inspector.get('issue_count', '?')} | **Warnings:** {inspector.get('warning_count', '?')}")
        w(f"- **Last inspection:** {inspector.get('timestamp', '?')}")
    if cls_stats.get("total"):
        w(f"- **Classifications:** {cls_stats['total']} total — "
          f"{cls_stats['success']} successful ({cls_stats['success']*100//max(cls_stats['total'],1)}%), "
          f"{cls_stats['clarification']} clarification, {cls_stats['other']} other")
    if counter_sum:
        w(f"- **Emails processed (all time):** {counter_sum}")
    if status:
        for name, info in sorted(status.items()):
            w(f"- **{name}:** {info.get('status', '?')} (last check: {info.get('last_check', '?')})")
    if metadata:
        w()
        w("### Last Script Runs")
        w("| Script | Last Run |")
        w("|--------|----------|")
        for name, info in sorted(metadata.items()):
            w(f"| {name} | {info.get('last_run', '?')} |")
    w()
    w("---")
    w()

    # ── 2. Library Modules ──
    w("## 2. Library Modules (functions/lib/)")
    w()

    lib_files = [(rp, fi) for rp, fi in sorted(files.items())
                 if rp.startswith("functions/lib/") and fi.filename != "__init__.py"]

    # Init first
    init_info = files.get("functions/lib/__init__.py")
    if init_info:
        w(f"### __init__.py ({init_info.lines} lines)")
        if init_info.docstring:
            w(f"- {init_info.docstring}")
        w()

    for rel_path, fi in lib_files:
        mod_name = fi.filename.replace(".py", "")
        wire_status = wiring.get(mod_name, "?")
        w(f"### {fi.filename} ({fi.lines} lines) — {wire_status}")
        if fi.docstring:
            w(f"- **Purpose:** {fi.docstring}")

        if fi.classes:
            w(f"- **Classes:** {', '.join(c[0] for c in fi.classes)}")

        if fi.functions:
            w(f"- **Functions ({len(fi.functions)}):**")
            for fname, fline, fargs in fi.functions:
                # Truncate long arg lists
                args_short = fargs[:60] + "..." if len(fargs) > 60 else fargs
                w(f"  - `{fname}()` :{fline}")

        if fi.imports_from_lib:
            w(f"- **Imports from lib:** {', '.join(fi.imports_from_lib)}")

        if fi.collections_read:
            w(f"- **Firestore reads:** {', '.join(sorted(fi.collections_read))}")
        if fi.collections_write:
            w(f"- **Firestore writes:** {', '.join(sorted(fi.collections_write))}")

        if fi.api_calls:
            apis = set(a[0] for a in fi.api_calls)
            w(f"- **External APIs:** {', '.join(sorted(apis))}")

        w()

    w("---")
    w()

    # ── 3. Cloud Functions ──
    w("## 3. Cloud Functions (functions/main.py)")
    w()
    main_info = files.get("functions/main.py")
    if main_info:
        w(f"**{main_info.lines} lines** | "
          f"**{len(main_info.functions)} functions** | "
          f"**Imports from lib:** {', '.join(main_info.imports_from_lib)}")
        w()

    if schedulers:
        w("### Schedulers")
        w("| Function | Schedule | Line |")
        w("|----------|----------|------|")
        for s in schedulers:
            w(f"| `{s['name']}` | {s['schedule']} | :{s['line']} |")
        w()

    if http_triggers:
        w("### HTTP Triggers")
        w("| Function | Line |")
        w("|----------|------|")
        for h in http_triggers:
            w(f"| `{h['name']}` | :{h['line']} |")
        w()

    if firestore_triggers:
        w("### Firestore Triggers")
        w("| Function | Document | Trigger | Line |")
        w("|----------|----------|---------|------|")
        for ft in firestore_triggers:
            w(f"| `{ft['name']}` | {ft['document']} | {ft['trigger']} | :{ft['line']} |")
        w()

    w("---")
    w()

    # ── 4. Standalone Scripts ──
    w("## 4. Standalone Scripts")
    w()
    w("### Active Scripts")
    w("| File | Lines | Purpose |")
    w("|------|-------|---------|")
    for rel_path, fi in sorted(files.items()):
        if not rel_path.startswith("functions/") or rel_path.startswith("functions/lib/"):
            continue
        cat = classify_script(fi.filename)
        if cat == "Active":
            purpose = fi.docstring or ""
            w(f"| `{fi.filename}` | {fi.lines} | {purpose} |")
    w()

    w("### Utilities & Tests")
    w("| File | Lines | Category | Purpose |")
    w("|------|-------|----------|---------|")
    for rel_path, fi in sorted(files.items()):
        if not rel_path.startswith("functions/") or rel_path.startswith("functions/lib/"):
            continue
        cat = classify_script(fi.filename)
        if cat in ("Test", "Utility"):
            purpose = fi.docstring or ""
            w(f"| `{fi.filename}` | {fi.lines} | {cat} | {purpose} |")
    w()

    w("---")
    w()

    # ── 5. Firestore Collections ──
    w("## 5. Firestore Collections")
    w()
    if coll_counts:
        w("### Live Counts (queried from Firebase)")
        w("| Collection | Docs | Read by | Written by |")
        w("|------------|------|---------|------------|")
        for coll in sorted(coll_counts.keys()):
            count = coll_counts[coll]
            count_str = str(count) if count >= 0 else "ERROR"
            readers = ", ".join(sorted(set(coll_reads.get(coll, [])))) or "--"
            writers = ", ".join(sorted(set(coll_writes.get(coll, [])))) or "--"
            w(f"| `{coll}` | {count_str} | {readers} | {writers} |")
        w()

        if discovered_collections:
            w("### Discovered Collections (not in known list)")
            w("| Collection | Docs |")
            w("|------------|------|")
            for coll, count in sorted(discovered_collections.items()):
                w(f"| `{coll}` | {count} |")
            w()

        # Empty collections warning
        empty = [c for c, n in coll_counts.items() if n == 0]
        if empty:
            w(f"### Empty Collections ({len(empty)})")
            w(f"`{'`, `'.join(sorted(empty))}`")
            w()

        # Orphaned collections (in Firebase but not referenced in code)
        all_code_colls = set()
        for fi in files.values():
            all_code_colls |= fi.collections_read | fi.collections_write
        orphaned = [c for c in coll_counts if c not in all_code_colls and coll_counts[c] > 0]
        if orphaned:
            w(f"### Orphaned Collections (data exists but no code references)")
            w(f"`{'`, `'.join(sorted(orphaned))}`")
            w()
    else:
        w("*Firebase not queried — run without `--code-only` for live counts.*")
        w()

    w("---")
    w()

    # ── 6. External APIs ──
    w("## 6. External APIs")
    w()
    api_map = defaultdict(list)
    for rel_path, fi in files.items():
        for api_name, line_no in fi.api_calls:
            api_map[api_name].append(f"{fi.filename}:{line_no}")

    if api_map:
        w("| API | Referenced in |")
        w("|-----|--------------|")
        for api_name, refs in sorted(api_map.items()):
            w(f"| {api_name} | {', '.join(sorted(set(refs))[:5])} |")
    else:
        w("*No API references detected.*")
    w()
    w("---")
    w()

    # ── 7. Module Wiring ──
    w("## 7. Module Wiring")
    w()
    w("How lib modules connect to the live pipeline via main.py:")
    w()
    w("| Module | Status |")
    w("|--------|--------|")
    for mod, status_text in sorted(wiring.items()):
        w(f"| `{mod}` | {status_text} |")
    w()
    w("---")
    w()

    # ── 8. Files NOT in Repo ──
    w("## 8. Files NOT in Repo")
    w()
    w("These files were uploaded to Claude browser sessions but never committed.")
    w("Their functionality exists ONLY in chat uploads and Firebase data.")
    w()
    w("| File | What it does | Firebase evidence |")
    w("|------|-------------|-------------------|")
    silent_count = coll_counts.get("rcb_silent_classifications", "?")
    pupil_count = coll_counts.get("pupil_teachings", "?")
    w(f"| `fix_silent_classify.py` | CC emails silently classified | {silent_count} docs in rcb_silent_classifications |")
    w(f"| `fix_tracker_crash.py` | Patches None bug in _derive_current_step() | -- |")
    w(f"| `patch_tracker_v2.py` | Tracker v2 improved phase detection | -- |")
    w(f"| `pupil_v05_final.py` | Devil's advocate, CC email learning | {pupil_count} docs in pupil_teachings |")
    w()
    w("---")
    w()

    # ── 9. Dead Code ──
    w("## 9. Dead Code")
    w()
    w("| File | Lines | Category |")
    w("|------|-------|----------|")
    for rel_path, fi in sorted(files.items()):
        if not rel_path.startswith("functions/") or rel_path.startswith("functions/lib/"):
            continue
        cat = classify_script(fi.filename)
        if cat == "Dead (patch/fix)":
            w(f"| `{fi.filename}` | {fi.lines} | {cat} |")
    w()

    # ── Stats footer ──
    w("---")
    w()
    total_lib_lines = sum(fi.lines for rp, fi in files.items() if rp.startswith("functions/lib/"))
    main_fi = files.get("functions/main.py")
    total_main_lines = main_fi.lines if main_fi else 0
    total_script_lines = sum(fi.lines for rp, fi in files.items()
                             if rp.startswith("functions/") and not rp.startswith("functions/lib/"))
    total_functions = sum(len(fi.functions) for fi in files.values())
    total_classes = sum(len(fi.classes) for fi in files.values())
    total_colls = len(coll_counts) + len(discovered_collections) if coll_counts else 0

    w("## Stats")
    w()
    w(f"- **Lib modules:** {len(lib_files)} files, {total_lib_lines} lines")
    w(f"- **main.py:** {total_main_lines} lines")
    w(f"- **Scripts:** {total_script_lines} lines")
    w(f"- **Total functions:** {total_functions}")
    w(f"- **Total classes:** {total_classes}")
    w(f"- **Firestore collections:** {total_colls}")
    w(f"- **Cloud Functions:** {len(schedulers)} schedulers, {len(http_triggers)} HTTP, {len(firestore_triggers)} Firestore triggers")
    w()

    return "\n".join(lines)


# ─── Snapshot Builder (historical log, never erased) ─────────────────────────

def build_snapshot(files, coll_counts, discovered, wiring, inspector,
                   cls_stats, counter_sum, metadata):
    """Build a compact timestamped snapshot for the historical log."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []

    def w(text=""):
        lines.append(text)

    w()
    w(f"## Snapshot: {now}")
    w()

    # Health
    if inspector:
        w(f"**Health:** {inspector.get('health_score', '?')}/100 ({inspector.get('health', '?')}) | "
          f"Issues: {inspector.get('issue_count', 0)} | Warnings: {inspector.get('warning_count', 0)}")

    # Classifications
    if cls_stats.get("total"):
        w(f"**Classifications:** {cls_stats['total']} total — "
          f"{cls_stats['success']} success, "
          f"{cls_stats['clarification']} clarification, "
          f"{cls_stats['other']} other")

    if counter_sum:
        w(f"**Emails processed:** {counter_sum}")

    # Code stats
    lib_files = [fi for rp, fi in files.items() if rp.startswith("functions/lib/") and fi.filename != "__init__.py"]
    total_lib_lines = sum(fi.lines for fi in lib_files)
    total_functions = sum(len(fi.functions) for fi in files.values())
    wired_count = sum(1 for v in wiring.values() if "NOT WIRED" not in v)
    w(f"**Code:** {len(lib_files)} lib modules ({total_lib_lines} lines), "
      f"{total_functions} functions, {wired_count}/{len(wiring)} wired")

    # Key collection counts (only show ones with changes)
    if coll_counts:
        w()
        w("### Collection Counts")
        w("| Collection | Docs |")
        w("|------------|------|")
        key_colls = [
            "brain_index", "keyword_index", "product_index", "supplier_index",
            "classification_knowledge", "rcb_classifications", "rcb_silent_classifications",
            "pupil_teachings", "knowledge_base", "tariff", "legal_requirements",
            "librarian_index", "librarian_search_log", "classification_rules",
            "ministry_index", "fta_agreements", "batch_reprocess_results",
        ]
        for c in key_colls:
            if c in coll_counts:
                w(f"| `{c}` | {coll_counts[c]} |")

    # Discovered new collections
    if discovered:
        w()
        w("### New Collections Discovered")
        for c, n in sorted(discovered.items()):
            w(f"- `{c}`: {n} docs")

    # Last script runs
    if metadata:
        w()
        w("### Script Runs")
        for name, info in sorted(metadata.items()):
            w(f"- {name}: {info.get('last_run', '?')}")

    # File changes since last snapshot (line counts)
    w()
    w("### File Line Counts")
    w("| File | Lines |")
    w("|------|-------|")
    for rp, fi in sorted(files.items()):
        if rp.startswith("functions/lib/") and fi.filename != "__init__.py":
            w(f"| `{fi.filename}` | {fi.lines} |")

    w()
    w("---")
    w()

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    code_only = "--code-only" in sys.argv
    counts_only = "--counts-only" in sys.argv

    print("=" * 60)
    print("  BUILD SYSTEM INDEX")
    print("=" * 60)

    # 1. Scan code
    print("\n[1/4] Scanning code files...")
    files = scan_all_files()
    lib_count = sum(1 for rp in files if rp.startswith("functions/lib/"))
    print(f"  Found {len(files)} files ({lib_count} lib modules)")

    # 2. Detect wiring
    print("\n[2/4] Detecting module wiring...")
    wiring = detect_wiring(files)
    wired = sum(1 for v in wiring.values() if "NOT WIRED" not in v)
    print(f"  {wired}/{len(wiring)} modules wired to pipeline")

    # 3. Detect Cloud Functions
    print("\n[3/4] Detecting Cloud Functions...")
    main_info = files.get("functions/main.py")
    schedulers, http_triggers, firestore_triggers = [], [], []
    if main_info:
        schedulers, http_triggers, firestore_triggers = detect_cloud_functions(main_info)
    print(f"  {len(schedulers)} schedulers, {len(http_triggers)} HTTP, {len(firestore_triggers)} Firestore")

    # 4. Build collection map
    coll_reads, coll_writes = build_collection_map(files)

    # 5. Query Firebase
    coll_counts = {}
    discovered = {}
    metadata = {}
    status = {}
    inspector = {}
    cls_stats = {}
    counter_sum = 0

    if not code_only:
        print("\n[4/4] Querying Firebase...")
        coll_counts, discovered = query_firestore_counts()
        if discovered:
            print(f"  Discovered {len(discovered)} unknown collections!")
            for c, n in discovered.items():
                print(f"    NEW: {c} ({n} docs)")
        metadata, status, inspector, cls_stats, counter_sum = query_system_metadata()
        total_docs = sum(v for v in coll_counts.values() if v > 0)
        print(f"  {len(coll_counts)} collections, {total_docs} total documents")
    else:
        print("\n[4/4] Skipping Firebase (--code-only)")

    # 6. Generate markdown
    print("\nGenerating SYSTEM_INDEX.md...")
    md = generate_markdown(
        files, wiring, coll_reads, coll_writes, coll_counts, discovered,
        schedulers, http_triggers, firestore_triggers,
        metadata, status, inspector, cls_stats, counter_sum,
    )

    # 7. Write generated index (overwrite — this is the auto-generated one)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\nWritten to {OUTPUT_PATH}")
    print(f"  {len(md)} chars, {md.count(chr(10))} lines")

    # 8. Append snapshot to historical log (NEVER erased)
    snapshot = build_snapshot(files, coll_counts, discovered, wiring,
                              inspector, cls_stats, counter_sum, metadata)
    with open(SNAPSHOT_PATH, "a", encoding="utf-8") as f:
        f.write(snapshot)
    print(f"Appended snapshot to {SNAPSHOT_PATH}")

    print("\nDone.")


if __name__ == "__main__":
    main()
