# XML Conversion Plan — What Needs Converting

## Why XML
- Structured queries by article number, section, keyword
- Preserves legal document hierarchy
- Better search precision than JSON blobs

## Documents to Convert to XML (in priority order)

1. פקודת המכס — 311 articles currently in _ordinance_data.py Python dict
   Source: functions/lib/_ordinance_data.py → ORDINANCE_ARTICLES
   Target: legal_knowledge/ordinance_xml or separate xml_documents collection
   Priority: HIGH — most queried, already in memory but not structured

2. צו יבוא חופשי + תוספות — currently in Firestore as JSON
   Source: free_import_order collection
   Target: xml_documents/free_import_order
   Priority: HIGH

3. צו יצוא + תוספות — currently in Firestore as JSON
   Source: free_export_order collection
   Target: xml_documents/free_export_order
   Priority: HIGH

4. צו מסגרת + תוספות — currently in Firestore as JSON
   Source: framework_order collection (85 docs)
   Target: xml_documents/framework_order
   Priority: MEDIUM

5. תעריף המכס — 11,753 entries in tariff collection
   Source: tariff collection
   Target: xml_documents/tariff
   Priority: MEDIUM — already indexed, XML adds structure

6. FTA protocols — pending PC agent download
   Source: legal_knowledge/fta_* (after PC agent runs)
   Target: xml_documents/fta_*
   Priority: HIGH — once downloaded

7. נהלי מכס (procedures 1,2,3,25) — pending PC agent download
   Source: legal_knowledge/procedure_* (after PC agent runs)
   Target: xml_documents/procedure_*
   Priority: MEDIUM — once downloaded

## Conversion Approach
- Each document → structured XML with consistent schema
- Schema: `<document><metadata/><sections><section id="" title=""><articles><article id="" title=""><text/></article></articles></section></sections></document>`
- Store XML as string field in Firestore OR as file in Firebase Storage
- search_legal_knowledge tool to support XPath-style queries

## What NOT to Convert
- tariff collection (too large, already indexed)
- Knowledge cache collections (temporary data)

## Next Session Instructions
Read this file, confirm plan, start with item 1 (פקודת המכס — already in memory, lowest risk conversion)
