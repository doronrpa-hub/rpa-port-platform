# Session 62 Handoff — 2026-02-24

## FONT FIX SOLVED

The garbled Hebrew in shaarolami PDFs (supplements 3-19, discount codes) is caused by **broken ToUnicode CMap** in embedded fonts. Hebrew glyphs are mapped to wrong Unicode blocks. Two simple character substitution mappings fix ALL garbled text:

### Mapping 1: Modifier Letters → Hebrew (offset +0x0330)
```
U+02A0 (ʠ) → U+05D0 (א)
U+02A1 (ʡ) → U+05D1 (ב)
...through...
U+02BA (ʺ) → U+05EA (ת)
```
**27 characters. Covers Arial and Arial,Bold fonts.**

### Mapping 2: Oriya Block → Hebrew (offset -0x0590)
```
U+0B68 (୨) → U+05D8 (ט)
U+0B69 (୩) → U+05D9 (י)
...through...
U+0B82 (ஂ) → U+05F2 (ײ)
```
**27 characters. Covers Segoe UI and Segoe UI,Bold fonts (Identity-H CMap).**

### Python implementation (ready to paste):
```python
_GARBLED_TO_HEBREW = {}
for _i in range(27):  # Mapping 1: modifier letters
    _GARBLED_TO_HEBREW[chr(0x02A0 + _i)] = chr(0x05D0 + _i)
for _cp in range(0x0B68, 0x0B83):  # Mapping 2: Oriya block
    _dst = _cp - 0x0590
    if 0x05D0 <= _dst <= 0x05F2:
        _GARBLED_TO_HEBREW[chr(_cp)] = chr(_dst)
_GARBLED_TRANS = str.maketrans(_GARBLED_TO_HEBREW)

def fix_garbled_hebrew(text):
    return text.translate(_GARBLED_TRANS)
```

### Verified working on:
- `ExemptCustomsItems.pdf` — discount codes now readable Hebrew
- `ThirdAddition.pdf` — WTO quotas now readable Hebrew
- `AllCustomsBookDataPDF.pdf` page 3080 — garbled section now readable Hebrew

### Root cause confirmed via fonttools:
- Embedded fonts (ABCDEE+Segoe UI, ABCDEE+Arial) use Identity-H CMap
- ToUnicode CMap only maps ASCII (GIDs 3-58), NOT Hebrew (GIDs 2920-2946)
- Font cmap table confirms GID 2920=א, 2921=ב, ... 2946=ת
- PyMuPDF falls back to wrong Unicode blocks when ToUnicode is incomplete

## What Was NOT Done

- **Fix NOT integrated into pdf_to_xml.py** — edit was started but not saved
- **Batch PDF conversion NOT done** — 40 PDFs in downloads/ still unconverted
- **Playwright NOT installed**
- **Definition detection in pdf_to_xml.py still broken** (0 definitions found)

## Installed This Session
- `pdfminer.six` — alternative PDF text extraction (gives CID values)
- `fonttools` — TrueType font analysis (used to confirm GID→Unicode mapping)

## Everything from SESSION_61_HANDOFF.md still applies
- 40 PDFs in downloads/ (77MB)
- Supplements 11, 12, 13 DO NOT EXIST (confirmed)
- pdf_to_xml.py exists (420 lines), needs garbled fix + definition detection fix
- 18 PC agent tasks waiting for Playwright

## Priority for Next Session
1. Add `fix_garbled_hebrew()` to `pdf_to_xml.py` — apply to all extracted text
2. Fix definition detection in pdf_to_xml.py
3. Batch convert all 40 PDFs: `python -X utf8 scripts/pdf_to_xml.py --batch downloads/ downloads/xml/`
4. Verify converted XML has readable Hebrew in supplement sections
5. Wire XML into search tools
