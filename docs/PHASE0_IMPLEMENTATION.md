# Phase 0: Document Extraction Improvements
## Implementation Plan for Claude Code
## February 12, 2026

---

## THE PROBLEM

From the test email logs (13:05 IST today):
- PDF 1: text extraction FAILED, fell back to OCR → only 1,281 chars extracted
- PDF 2: pdfplumber got 20,223 chars (this one worked)
- PDF 3: pdfplumber got only 429 chars
- LIBRARIAN found only 5 docs, confidence: low
- HS code validation failed
- Invoice score: 32/100

The system is blind. If it can't read the documents, everything downstream fails.

---

## CURRENT CODE (in functions/lib/rcb_helpers.py)

```python
def extract_text_from_pdf_bytes(pdf_bytes):
    # Method 1: pdfplumber
    text = _extract_with_pdfplumber(pdf_bytes)
    if len(text.strip()) > 50:        # <- TOO LOW threshold
        return text
    # Method 2: pypdf
    text = _extract_with_pypdf(pdf_bytes)
    if len(text.strip()) > 50:        # <- same problem
        return text
    # Method 3: Vision OCR at 150 DPI  # <- TOO LOW DPI
    text = _extract_with_vision_ocr(pdf_bytes)
    return text
```

---

## CHANGES NEEDED (all in rcb_helpers.py + requirements.txt)

### Change 0a: Raise OCR DPI from 150 to 300

**In `_pdf_to_images()`:**
```python
# BEFORE:
pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))

# AFTER:
pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
```

### Change 0b: Add image preprocessing before OCR

**Add new function `_preprocess_image_for_ocr()`**

### Change 0c: Smarter extraction quality threshold

**Replace `len > 50` with `_assess_extraction_quality()`**

### Change 0d: Better table extraction from pdfplumber

**Improve `_extract_with_pdfplumber()` to preserve table structure**

### Change 0e: Hebrew text cleanup

**Add `_cleanup_hebrew_text()` function**

### Change 0f: Structure tagging

**Add `_tag_document_structure()` function**

---

## REQUIREMENTS.TXT CHANGE

Add: `Pillow>=10.0.0`

---

## FILES TO CHANGE

1. `functions/lib/rcb_helpers.py` — all extraction improvements
2. `functions/requirements.txt` — add Pillow
