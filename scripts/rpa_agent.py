#!/usr/bin/env python3
"""
RPA-PORT Local Agent
====================
Runs on your personal computer.
Monitors Firebase for download tasks, fetches files from government/any websites,
uploads to Firebase Storage, extracts text, stores metadata, and cleans up.

SETUP:
  1. pip install firebase-admin requests pdfplumber beautifulsoup4
  2. Copy your firebase-credentials.json to same folder
  3. Run: python rpa_agent.py

The AI creates tasks in Firebase → this agent executes them → results go back to Firebase
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
import requests
import os
import sys
import time
import json
import re
import hashlib
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

# ============================================================
# CONFIGURATION
# ============================================================
AGENT_VERSION = "1.0.0"
TEMP_DIR = os.path.join(tempfile.gettempdir(), "rpa_agent_downloads")
CHECK_INTERVAL = 10  # seconds between checking for new tasks
FIREBASE_CRED_PATH = "firebase-credentials.json"  # in same directory as script
STORAGE_BUCKET = "rpa-port-customs.firebasestorage.app"

# Create temp directory
os.makedirs(TEMP_DIR, exist_ok=True)

# ============================================================
# FIREBASE INIT
# ============================================================
def init_firebase():
    """Initialize Firebase connection"""
    # Look for credentials file
    cred_path = FIREBASE_CRED_PATH
    if not os.path.exists(cred_path):
        # Try in script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cred_path = os.path.join(script_dir, FIREBASE_CRED_PATH)
    
    if not os.path.exists(cred_path):
        print(f"❌ Cannot find {FIREBASE_CRED_PATH}")
        print(f"   Please copy your firebase-credentials.json to: {os.getcwd()}")
        sys.exit(1)
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})
    
    db = firestore.client()
    bucket = storage.bucket()
    return db, bucket


# ============================================================
# FILE DOWNLOAD
# ============================================================
def download_file(url, headers=None):
    """Download a file from URL to temp directory"""
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
            'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    
    print(f"  📥 Downloading: {url[:80]}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=60, allow_redirects=True, stream=True)
        response.raise_for_status()
        
        # Determine filename
        content_disp = response.headers.get('Content-Disposition', '')
        if 'filename=' in content_disp:
            filename = re.findall(r'filename[^;=\n]*=(["\']?)([^"\';\n]*)\1', content_disp)
            if filename:
                filename = filename[0][1]
            else:
                filename = None
        else:
            filename = None
        
        if not filename:
            # Extract from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or '.' not in filename:
                # Guess from content type
                ct = response.headers.get('Content-Type', '')
                ext = '.html'
                if 'pdf' in ct: ext = '.pdf'
                elif 'excel' in ct or 'spreadsheet' in ct: ext = '.xlsx'
                elif 'word' in ct: ext = '.docx'
                elif 'json' in ct: ext = '.json'
                elif 'xml' in ct: ext = '.xml'
                elif 'csv' in ct: ext = '.csv'
                filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        # Clean filename
        filename = re.sub(r'[^\w\-_\. ]', '_', filename)
        local_path = os.path.join(TEMP_DIR, filename)
        
        # Save file
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(local_path)
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        print(f"  ✅ Saved: {filename} ({file_size:,} bytes)")
        
        return {
            'local_path': local_path,
            'filename': filename,
            'size': file_size,
            'content_type': content_type,
            'url': url,
            'status_code': response.status_code
        }
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Download failed: {e}")
        return {'error': str(e), 'url': url}


# ============================================================
# TEXT EXTRACTION
# ============================================================
def extract_text(filepath):
    """Extract text from PDF or other document"""
    ext = os.path.splitext(filepath)[1].lower()
    text = ""
    
    if ext == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages[:50]):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {i+1} ---\n{page_text}"
            print(f"  📄 Extracted {len(text):,} chars from PDF ({len(pdf.pages)} pages)")
        except ImportError:
            print(f"  ⚠️ pdfplumber not installed. Run: pip install pdfplumber")
        except Exception as e:
            print(f"  ⚠️ PDF extraction error: {e}")
    
    elif ext in ['.html', '.htm']:
        try:
            from bs4 import BeautifulSoup
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                # Remove scripts and styles
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                text = soup.get_text(separator='\n', strip=True)
            print(f"  📄 Extracted {len(text):,} chars from HTML")
        except ImportError:
            print(f"  ⚠️ beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        except Exception as e:
            print(f"  ⚠️ HTML extraction error: {e}")
    
    elif ext in ['.txt', '.csv', '.json', '.xml']:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            print(f"  📄 Read {len(text):,} chars from {ext}")
        except Exception as e:
            print(f"  ⚠️ Text read error: {e}")
    
    return text


# ============================================================
# FIREBASE UPLOAD
# ============================================================
def upload_to_firebase(bucket, db, file_info, task_data, extracted_text=""):
    """Upload file to Firebase Storage and store metadata in Firestore"""
    local_path = file_info['local_path']
    filename = file_info['filename']
    
    # Generate storage path
    category = task_data.get('category', 'downloads')
    date_prefix = datetime.now().strftime('%Y%m%d')
    storage_path = f"agent/{category}/{date_prefix}_{filename}"
    
    print(f"  ☁️ Uploading to Firebase Storage: {storage_path}")
    
    # Upload to Storage
    blob = bucket.blob(storage_path)
    blob.upload_from_filename(local_path)
    
    # Try to make public (may fail depending on rules)
    try:
        blob.make_public()
        download_url = blob.public_url
    except:
        download_url = f"gs://{STORAGE_BUCKET}/{storage_path}"
    
    # Generate document hash
    with open(local_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    
    # Store metadata in Firestore
    doc_data = {
        'filename': filename,
        'storage_path': storage_path,
        'download_url': download_url,
        'source_url': file_info.get('url', ''),
        'content_type': file_info.get('content_type', ''),
        'size': file_info.get('size', 0),
        'file_hash': file_hash,
        'category': category,
        'tags': task_data.get('tags', []),
        'description': task_data.get('description', ''),
        'extracted_text': extracted_text[:100000] if extracted_text else '',
        'text_length': len(extracted_text) if extracted_text else 0,
        'uploaded_at': firestore.SERVER_TIMESTAMP,
        'uploaded_by': 'rpa_agent',
        'task_id': task_data.get('task_id', '')
    }
    
    # Choose collection based on category
    collection = task_data.get('collection', 'agent_downloads')
    doc_id = f"agent_{date_prefix}_{file_hash[:8]}"
    
    db.collection(collection).document(doc_id).set(doc_data)
    
    print(f"  ✅ Stored metadata in {collection}/{doc_id}")
    
    return {
        'storage_path': storage_path,
        'download_url': download_url,
        'doc_id': doc_id,
        'collection': collection,
        'file_hash': file_hash
    }


# ============================================================
# WEBPAGE SCRAPING
# ============================================================
def scrape_webpage(url, selectors=None):
    """Download webpage and extract content"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF/document links
        doc_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xlsx', '.xls', '.csv']):
                full_url = urljoin(url, href)
                link_text = a.get_text(strip=True)
                doc_links.append({'url': full_url, 'text': link_text})
        
        # Extract page text
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        page_text = soup.get_text(separator='\n', strip=True)
        
        return {
            'page_text': page_text,
            'doc_links': doc_links,
            'title': soup.title.string if soup.title else '',
            'url': url
        }
    
    except Exception as e:
        return {'error': str(e), 'url': url}


# ============================================================
# TASK PROCESSOR
# ============================================================
def process_task(db, bucket, task_id, task_data):
    """Process a single download/scrape task"""
    task_type = task_data.get('type', 'download')
    url = task_data.get('url', '')
    urls = task_data.get('urls', [])
    
    print(f"\n{'='*50}")
    print(f"📋 Task: {task_id}")
    print(f"   Type: {task_type}")
    print(f"   Description: {task_data.get('description', 'N/A')}")
    
    results = []
    
    if task_type == 'download' and url:
        # Single file download
        file_info = download_file(url)
        if 'error' not in file_info:
            text = extract_text(file_info['local_path'])
            upload_result = upload_to_firebase(bucket, db, file_info, task_data, text)
            results.append(upload_result)
            # Clean up
            os.remove(file_info['local_path'])
            print(f"  🗑️ Cleaned up local file")
        else:
            results.append(file_info)
    
    elif task_type == 'download_multiple' and urls:
        # Multiple file downloads
        for u in urls:
            file_info = download_file(u)
            if 'error' not in file_info:
                text = extract_text(file_info['local_path'])
                upload_result = upload_to_firebase(bucket, db, file_info, task_data, text)
                results.append(upload_result)
                os.remove(file_info['local_path'])
                print(f"  🗑️ Cleaned up")
            else:
                results.append(file_info)
            time.sleep(1)  # Be polite to servers
    
    elif task_type == 'scrape' and url:
        # Scrape webpage and find documents
        scrape_result = scrape_webpage(url)
        
        if 'error' not in scrape_result:
            # Store page content
            page_doc = {
                'type': 'webpage',
                'url': url,
                'title': scrape_result.get('title', ''),
                'text': scrape_result['page_text'][:100000],
                'doc_links_found': len(scrape_result.get('doc_links', [])),
                'doc_links': scrape_result.get('doc_links', [])[:50],
                'scraped_at': firestore.SERVER_TIMESTAMP,
                'task_id': task_id
            }
            collection = task_data.get('collection', 'scraped_pages')
            db.collection(collection).add(page_doc)
            
            # Auto-download found PDFs if requested
            if task_data.get('auto_download_docs', False):
                for link in scrape_result.get('doc_links', [])[:20]:
                    print(f"  📎 Found document: {link['text'][:50]} → {link['url'][:60]}")
                    file_info = download_file(link['url'])
                    if 'error' not in file_info:
                        text = extract_text(file_info['local_path'])
                        link_task = {**task_data, 'description': link['text']}
                        upload_result = upload_to_firebase(bucket, db, file_info, link_task, text)
                        results.append(upload_result)
                        os.remove(file_info['local_path'])
                    time.sleep(1)
            
            results.append({'page_scraped': url, 'docs_found': len(scrape_result.get('doc_links', []))})
        else:
            results.append(scrape_result)
    
    elif task_type == 'search_and_download':
        # Search a site for specific content and download matching docs
        search_url = task_data.get('search_url', '')
        search_terms = task_data.get('search_terms', [])
        
        if search_url:
            scrape_result = scrape_webpage(search_url)
            if 'error' not in scrape_result:
                # Filter links by search terms
                matching = []
                for link in scrape_result.get('doc_links', []):
                    link_text_lower = (link['text'] + ' ' + link['url']).lower()
                    if any(term.lower() in link_text_lower for term in search_terms):
                        matching.append(link)
                
                print(f"  🔍 Found {len(matching)} matching documents out of {len(scrape_result.get('doc_links', []))}")
                
                for link in matching[:10]:
                    file_info = download_file(link['url'])
                    if 'error' not in file_info:
                        text = extract_text(file_info['local_path'])
                        link_task = {**task_data, 'description': link['text']}
                        upload_result = upload_to_firebase(bucket, db, file_info, link_task, text)
                        results.append(upload_result)
                        os.remove(file_info['local_path'])
                    time.sleep(1)
    
    # Update task status
    db.collection('agent_tasks').document(task_id).update({
        'status': 'completed' if results else 'failed',
        'results': json.dumps(results, default=str)[:50000],
        'completed_at': firestore.SERVER_TIMESTAMP,
        'agent_version': AGENT_VERSION
    })
    
    print(f"  ✅ Task {task_id} completed with {len(results)} results")
    return results


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    """Main agent loop - watches Firebase for tasks"""
    print(f"""
╔══════════════════════════════════════════════════╗
║          RPA-PORT Local Agent v{AGENT_VERSION}          ║
║     Document Downloader & Firebase Uploader      ║
╠══════════════════════════════════════════════════╣
║  Watching Firebase for download tasks...         ║
║  Press Ctrl+C to stop                            ║
╚══════════════════════════════════════════════════╝
""")
    
    db, bucket = init_firebase()
    
    # Register agent
    db.collection('config').document('agent_status').set({
        'status': 'online',
        'version': AGENT_VERSION,
        'started_at': firestore.SERVER_TIMESTAMP,
        'machine': os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown')),
        'temp_dir': TEMP_DIR
    })
    print(f"✅ Agent registered. Temp dir: {TEMP_DIR}")
    print(f"✅ Watching collection: agent_tasks (status=pending)")
    print(f"   Checking every {CHECK_INTERVAL} seconds...\n")
    
    try:
        while True:
            # Query for pending tasks (simple filter, no composite index needed)
            tasks = db.collection('agent_tasks') \
                      .where(filter=firestore.FieldFilter('status', '==', 'pending')) \
                      .limit(5) \
                      .get()
            
            for task in tasks:
                task_data = task.to_dict()
                
                # Mark as processing
                db.collection('agent_tasks').document(task.id).update({
                    'status': 'processing',
                    'processing_started': firestore.SERVER_TIMESTAMP
                })
                
                try:
                    process_task(db, bucket, task.id, task_data)
                except Exception as e:
                    print(f"  ❌ Task error: {e}")
                    db.collection('agent_tasks').document(task.id).update({
                        'status': 'error',
                        'error': str(e),
                        'error_at': firestore.SERVER_TIMESTAMP
                    })
            
            if not tasks:
                print(f"  ⏳ {datetime.now().strftime('%H:%M:%S')} - No pending tasks", end='\r')
            
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print(f"\n\n🛑 Agent stopped by user")
        db.collection('config').document('agent_status').update({
            'status': 'offline',
            'stopped_at': firestore.SERVER_TIMESTAMP
        })
    
    finally:
        # Cleanup temp directory
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            print(f"🗑️ Cleaned up temp directory")


# ============================================================
# MANUAL MODE - for testing / one-off downloads
# ============================================================
def manual_download(url, category="manual", description="Manual download"):
    """Quick manual download - useful for testing"""
    db, bucket = init_firebase()
    
    file_info = download_file(url)
    if 'error' not in file_info:
        text = extract_text(file_info['local_path'])
        task_data = {
            'category': category,
            'description': description,
            'collection': 'agent_downloads',
            'tags': ['manual'],
            'task_id': 'manual'
        }
        result = upload_to_firebase(bucket, db, file_info, task_data, text)
        os.remove(file_info['local_path'])
        print(f"\n✅ Done! Document stored in Firebase")
        print(f"   Storage: {result['storage_path']}")
        print(f"   Firestore: {result['collection']}/{result['doc_id']}")
        return result
    else:
        print(f"\n❌ Failed: {file_info['error']}")
        return None


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Manual mode: python rpa_agent.py <url> [category] [description]
        url = sys.argv[1]
        category = sys.argv[2] if len(sys.argv) > 2 else "manual"
        description = sys.argv[3] if len(sys.argv) > 3 else "Manual download"
        manual_download(url, category, description)
    else:
        # Daemon mode: watch for tasks
        main()
