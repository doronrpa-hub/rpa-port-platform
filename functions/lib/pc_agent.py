"""
RCB PC Agent Integration - Browser-Based File Download & Upload
Session 12: Enables the Researcher to download files from sites that 
require browser interaction, then upload + tag them in Firestore.

The Problem:
  Many Israeli government sites (gov.il, nevo.co.il, shaarolami) serve 
  PDFs behind JavaScript, require cookies, or block direct API access.
  The Researcher cannot download these directly.

The Solution:
  When the Researcher identifies a file it needs but cannot access:
  1. It creates a "download task" in Firestore with the URL + metadata
  2. The PC Agent (a browser automation tool on a local machine) picks up the task
  3. The PC Agent downloads the file using a real browser
  4. The PC Agent uploads the file to Firebase Storage
  5. The PC Agent marks the task as complete
  6. The Librarian auto-tags the downloaded content

Architecture:
  ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
  │  Researcher   │────▶│  Firestore   │◀────│  PC Agent    │
  │  (Cloud Fn)   │     │  Task Queue  │     │  (Local PC)  │
  └──────────────┘     └─────────────┘     └──────┬───────┘
                              │                     │
                              ▼                     │ downloads
                       ┌─────────────┐              │ via browser
                       │  Librarian   │              ▼
                       │  Tags & Index│     ┌──────────────┐
                       └─────────────┘     │  Gov.il PDFs  │
                                           │  Nevo.co.il   │
                                           │  Shaarolami   │
                                           └──────────────┘
"""

from datetime import datetime, timezone

# ═══════════════════════════════════════════
#  DOWNLOAD TASK STATUS
# ═══════════════════════════════════════════

TASK_STATUS = {
    "pending": "ממתין להורדה",
    "assigned": "הוקצה לסוכן",
    "downloading": "בתהליך הורדה",
    "downloaded": "הורדה הושלמה",
    "uploading": "בתהליך העלאה",
    "uploaded": "הועלה למערכת",
    "tagging": "בתהליך תיוג",
    "complete": "הושלם",
    "failed": "נכשל",
    "retry": "ממתין לניסיון חוזר",
}

# ═══════════════════════════════════════════
#  CREATE DOWNLOAD TASKS
# ═══════════════════════════════════════════

def create_download_task(db, url, source_name, auto_tags=None, metadata=None):
    """
    Create a download task for the PC Agent.
    
    The Researcher calls this when it finds a URL with content it needs
    but cannot download directly (requires browser/JavaScript).

    Args:
        db: Firestore client
        url: str - URL to download
        source_name: str - Human-readable source name
        auto_tags: List[str] - Tags to apply after download
        metadata: dict - Additional metadata (content_type, file_type, etc.)

    Returns:
        str - Task ID
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        task_id = f"dl_{_safe_id(source_name)}_{now[:10]}"

        task_data = {
            "url": url,
            "source_name": source_name,
            "status": "pending",
            "auto_tags": auto_tags or [],
            "metadata": metadata or {},
            "created_at": now,
            "created_by": "researcher",
            "attempts": 0,
            "max_attempts": 3,
            "priority": metadata.get("priority", "normal") if metadata else "normal",
        }

        # Detect if this is a known source
        from .librarian_tags import PC_AGENT_DOWNLOAD_SOURCES
        for key, source_info in PC_AGENT_DOWNLOAD_SOURCES.items():
            if source_info["url"] in url or url in source_info["url"]:
                task_data["source_key"] = key
                task_data["requires_browser"] = source_info.get("requires_browser", True)
                if not auto_tags:
                    task_data["auto_tags"] = source_info.get("auto_tags", [])
                break

        db.collection("pc_agent_tasks").document(task_id).set(task_data)
        print(f"    📥 Created download task: {task_id} → {url[:80]}")
        return task_id

    except Exception as e:
        print(f"    ❌ Error creating download task: {e}")
        return ""


def create_bulk_download_tasks(db, source_key):
    """
    Create download tasks for all URLs in a known source.
    
    Args:
        db: Firestore client
        source_key: str - Key from PC_AGENT_DOWNLOAD_SOURCES
        
    Returns:
        List[str] - Created task IDs
    """
    from .librarian_tags import PC_AGENT_DOWNLOAD_SOURCES

    source_info = PC_AGENT_DOWNLOAD_SOURCES.get(source_key)
    if not source_info:
        print(f"    ❌ Unknown source key: {source_key}")
        return []

    task_id = create_download_task(
        db,
        url=source_info["url"],
        source_name=source_info.get("name_he", source_key),
        auto_tags=source_info.get("auto_tags", []),
        metadata={
            "source_key": source_key,
            "content_type": source_info.get("content_type", []),
            "file_types": source_info.get("file_types", []),
            "requires_browser": source_info.get("requires_browser", True),
        }
    )

    return [task_id] if task_id else []


# ═══════════════════════════════════════════
#  PC AGENT: PICK UP & PROCESS TASKS
#  (These functions run on the PC Agent side)
# ═══════════════════════════════════════════

def get_pending_tasks(db, limit=10):
    """
    Get pending download tasks for the PC Agent to process.
    Called by the PC Agent on the local machine.

    Returns:
        List[dict] - Tasks ready for download
    """
    try:
        tasks = []
        docs = db.collection("pc_agent_tasks") \
            .where("status", "in", ["pending", "retry"]) \
            .limit(limit).stream()

        for doc in docs:
            data = doc.to_dict()
            data["task_id"] = doc.id
            tasks.append(data)

        # Sort by priority
        priority_order = {"high": 0, "normal": 1, "low": 2}
        tasks.sort(key=lambda t: priority_order.get(t.get("priority", "normal"), 1))

        return tasks
    except Exception as e:
        print(f"    ❌ Error getting pending tasks: {e}")
        return []


def assign_task(db, task_id, agent_id="pc_agent_default"):
    """Mark a task as assigned to a PC agent."""
    try:
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "assigned",
            "assigned_to": agent_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except Exception as e:
        print(f"    ❌ Error assigning task {task_id}: {e}")
        return False


def report_download_complete(db, task_id, file_path, file_size=0,
                              storage_path="", content_preview=""):
    """
    PC Agent reports that download is complete.
    
    Args:
        db: Firestore client
        task_id: str - Task ID
        file_path: str - Local file path where file was saved
        file_size: int - File size in bytes
        storage_path: str - Firebase Storage path after upload
        content_preview: str - First ~500 chars of content (for tagging)
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": "downloaded",
            "file_path": file_path,
            "file_size": file_size,
            "downloaded_at": now,
        }

        if storage_path:
            update_data["storage_path"] = storage_path
            update_data["status"] = "uploaded"

        if content_preview:
            update_data["content_preview"] = content_preview[:2000]

        db.collection("pc_agent_tasks").document(task_id).update(update_data)

        # Auto-tag if we have content
        task_doc = db.collection("pc_agent_tasks").document(task_id).get()
        if task_doc.exists:
            task_data = task_doc.to_dict()
            _auto_tag_and_index_download(db, task_id, task_data, content_preview)

        print(f"    ✅ Download complete: {task_id}")
        return True

    except Exception as e:
        print(f"    ❌ Error reporting download complete: {e}")
        return False


def report_upload_complete(db, task_id, storage_path, firestore_collection="",
                            firestore_doc_id=""):
    """
    PC Agent reports that upload to Firebase Storage/Firestore is complete.
    Triggers auto-tagging and indexing.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "uploaded",
            "storage_path": storage_path,
            "firestore_collection": firestore_collection,
            "firestore_doc_id": firestore_doc_id,
            "uploaded_at": now,
        })

        # Final step: tag and index
        task_doc = db.collection("pc_agent_tasks").document(task_id).get()
        if task_doc.exists:
            task_data = task_doc.to_dict()
            _finalize_download(db, task_id, task_data)

        return True
    except Exception as e:
        print(f"    ❌ Error reporting upload complete: {e}")
        return False


def report_task_failed(db, task_id, error_message):
    """PC Agent reports download failure."""
    try:
        task_ref = db.collection("pc_agent_tasks").document(task_id)
        task_doc = task_ref.get()

        if task_doc.exists:
            data = task_doc.to_dict()
            attempts = data.get("attempts", 0) + 1
            max_attempts = data.get("max_attempts", 3)

            status = "retry" if attempts < max_attempts else "failed"

            task_ref.update({
                "status": status,
                "attempts": attempts,
                "last_error": error_message,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            })

        return True
    except Exception as e:
        print(f"    ❌ Error reporting failure: {e}")
        return False


# ═══════════════════════════════════════════
#  TASK STATUS & MONITORING
# ═══════════════════════════════════════════

def get_task_status(db, task_id):
    """Get status of a specific download task."""
    try:
        doc = db.collection("pc_agent_tasks").document(task_id).get()
        if doc.exists:
            return doc.to_dict()
        return {"status": "not_found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_all_tasks_status(db, limit=50):
    """Get status summary of all PC agent tasks."""
    summary = {
        "total": 0,
        "by_status": {},
        "recent_tasks": [],
    }

    try:
        docs = db.collection("pc_agent_tasks") \
            .limit(limit).stream()

        for doc in docs:
            data = doc.to_dict()
            data["task_id"] = doc.id
            summary["total"] += 1

            status = data.get("status", "unknown")
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            summary["recent_tasks"].append({
                "task_id": doc.id,
                "url": data.get("url", "")[:80],
                "source_name": data.get("source_name", ""),
                "status": status,
                "created_at": data.get("created_at", ""),
            })

    except Exception as e:
        summary["error"] = str(e)

    return summary


def get_download_queue_for_agent(db, agent_id="pc_agent_default"):
    """
    Get the download queue formatted for a PC Agent.
    Returns a simple list of {url, task_id, instructions} ready for execution.
    
    The PC Agent script can call this, iterate the results, and:
    1. Open each URL in a browser
    2. Download the file
    3. Upload to Firebase Storage
    4. Call report_download_complete / report_upload_complete
    """
    tasks = get_pending_tasks(db)
    queue = []

    for task in tasks:
        queue.append({
            "task_id": task.get("task_id"),
            "url": task.get("url"),
            "source_name": task.get("source_name", ""),
            "file_types": task.get("metadata", {}).get("file_types", ["pdf"]),
            "requires_browser": task.get("requires_browser", True),
            "instructions": _generate_download_instructions(task),
        })

    return queue


# ═══════════════════════════════════════════
#  PC AGENT SCRIPT TEMPLATE
# ═══════════════════════════════════════════

PC_AGENT_SCRIPT_TEMPLATE = """
#!/usr/bin/env python3
\"\"\"
RCB PC Agent - Browser-Based Download Agent
Run this on a local PC with Chrome/Firefox installed.

Prerequisites:
    pip install firebase-admin selenium requests
    
    # Or for Playwright:
    pip install playwright
    playwright install chromium

Usage:
    python pc_agent_runner.py
\"\"\"

import os
import time
import firebase_admin
from firebase_admin import credentials, firestore, storage

# ── Firebase Setup ──
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'rpa-port-customs.appspot.com'})
db = firestore.client()
bucket = storage.bucket()

# ── Import the PC agent functions ──
# Option 1: Copy functions locally
# Option 2: Import from lib
from lib.pc_agent import (
    get_pending_tasks, assign_task,
    report_download_complete, report_upload_complete, report_task_failed
)

def download_with_browser(url, save_path):
    \"\"\"Download a file using Selenium or Playwright.\"\"\"
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_experimental_option("prefs", {
            "download.default_directory": os.path.dirname(save_path),
            "download.prompt_for_download": False,
        })
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)  # Wait for page/download
        
        # For PDFs that open in browser:
        # driver.execute_script("window.print()")
        
        driver.quit()
        return True
    except Exception as e:
        print(f"Browser download failed: {e}")
        return False

def download_direct(url, save_path):
    \"\"\"Download a direct file link (no browser needed).\"\"\"
    import requests
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    return False

def upload_to_storage(local_path, storage_path):
    \"\"\"Upload downloaded file to Firebase Storage.\"\"\"
    blob = bucket.blob(storage_path)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url

def run_agent():
    \"\"\"Main agent loop - picks up tasks, downloads, uploads, reports.\"\"\"
    print("🤖 PC Agent starting...")
    
    while True:
        tasks = get_pending_tasks(db, limit=5)
        
        if not tasks:
            print("  💤 No pending tasks. Sleeping 60s...")
            time.sleep(60)
            continue
        
        for task in tasks:
            task_id = task["task_id"]
            url = task["url"]
            source_name = task.get("source_name", "unknown")
            requires_browser = task.get("requires_browser", True)
            
            print(f"  📥 Processing: {source_name}")
            assign_task(db, task_id)
            
            # Determine save path
            file_ext = "pdf"  # default
            file_types = task.get("metadata", {}).get("file_types", ["pdf"])
            if file_types:
                file_ext = file_types[0]
            
            save_dir = os.path.expanduser("~/rcb_downloads")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"{task_id}.{file_ext}")
            
            # Download
            success = False
            if requires_browser:
                success = download_with_browser(url, save_path)
            else:
                success = download_direct(url, save_path)
            
            if success and os.path.exists(save_path):
                # Upload to Firebase Storage
                storage_path = f"pc_agent_downloads/{task_id}.{file_ext}"
                public_url = upload_to_storage(save_path, storage_path)
                
                # Read content preview for tagging
                content_preview = ""
                if file_ext == "pdf":
                    try:
                        import fitz  # PyMuPDF
                        doc = fitz.open(save_path)
                        content_preview = " ".join(
                            page.get_text() for page in doc[:3]
                        )[:2000]
                    except Exception as e:
                        print(f"pc_agent: PDF preview extraction failed for {save_path}: {e}")

                report_upload_complete(db, task_id, storage_path)
                report_download_complete(
                    db, task_id, save_path,
                    file_size=os.path.getsize(save_path),
                    storage_path=storage_path,
                    content_preview=content_preview,
                )
                print(f"    ✅ Done: {source_name}")
            else:
                report_task_failed(db, task_id, "Download failed")
                print(f"    ❌ Failed: {source_name}")
        
        time.sleep(10)  # Brief pause between batches

if __name__ == "__main__":
    run_agent()
"""


def get_agent_script():
    """Return the PC Agent runner script template."""
    return PC_AGENT_SCRIPT_TEMPLATE


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _auto_tag_and_index_download(db, task_id, task_data, content_preview=""):
    """Auto-tag a downloaded file and add to librarian index."""
    try:
        from .librarian_tags import auto_tag_pc_agent_download, auto_tag_document

        # Generate tags from source definition + content
        source_key = task_data.get("source_key", "")
        file_path = task_data.get("file_path", "")
        tags = auto_tag_pc_agent_download(file_path, source_key, {"content": content_preview})

        # Also run content-based auto-tagging
        if content_preview:
            content_tags = auto_tag_document({"content": content_preview})
            tags = sorted(list(set(tags + content_tags)))

        # Add pre-defined auto_tags
        auto_tags = task_data.get("auto_tags", [])
        tags = sorted(list(set(tags + auto_tags)))

        # Update task with tags
        db.collection("pc_agent_tasks").document(task_id).update({"tags": tags})

    except Exception as e:
        print(f"    ⚠️ Auto-tag error for {task_id}: {e}")


def _finalize_download(db, task_id, task_data):
    """Final processing: index the downloaded document in librarian_index."""
    try:
        from .librarian_index import index_single_document

        now = datetime.now(timezone.utc).isoformat()
        tags = task_data.get("tags", task_data.get("auto_tags", []))

        index_doc = {
            "title": task_data.get("source_name", ""),
            "source_url": task_data.get("url", ""),
            "storage_path": task_data.get("storage_path", ""),
            "file_path": task_data.get("file_path", ""),
            "content_preview": task_data.get("content_preview", "")[:500],
            "tags": tags,
            "downloaded_by": "pc_agent",
            "downloaded_at": task_data.get("downloaded_at", now),
            "geo_origin": "israel" if "source_israeli" in tags else "foreign",
        }

        index_single_document(db, "pc_agent_downloads", task_id, index_doc)

        # Mark task as complete
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "complete",
            "completed_at": now,
        })

        print(f"    ✅ Indexed download: {task_id}")

    except Exception as e:
        print(f"    ⚠️ Finalize error for {task_id}: {e}")


def _generate_download_instructions(task):
    """Generate human-readable download instructions for the PC agent."""
    url = task.get("url", "")
    requires_browser = task.get("requires_browser", True)
    file_types = task.get("metadata", {}).get("file_types", ["pdf"])

    if not requires_browser:
        return f"Direct download: GET {url} → save as .{file_types[0] if file_types else 'pdf'}"

    instructions = f"Browser download required:\n"
    instructions += f"  1. Open {url}\n"
    instructions += f"  2. Wait for page to load fully\n"

    if "pdf" in file_types:
        instructions += f"  3. Find and download the PDF file(s)\n"
    elif "excel" in file_types:
        instructions += f"  3. Export/download as Excel file\n"
    elif "html" in file_types:
        instructions += f"  3. Save page content as HTML\n"

    instructions += f"  4. Upload to Firebase Storage\n"
    instructions += f"  5. Report completion via report_upload_complete()\n"

    return instructions


def _safe_id(text):
    """Create a safe Firestore document ID."""
    import re
    safe = re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '_', text.strip())
    return safe[:60].strip('_') or "unknown"
