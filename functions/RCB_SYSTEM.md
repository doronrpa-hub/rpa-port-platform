# RCB System Documentation - Read This First!

## 🎯 What is RCB?
AI Customs Broker for R.P.A. PORT LTD (ר.פ.א פורט בע"מ)
Email: rcb@rpa-port.co.il

## 📊 Firestore Collections Available

### Tariff Data
- `tariff` - Israeli HS codes (format: XX.XX.XXXXXX/X e.g., 87.03.808000/5)
- `tariff_chapters` - Chapter descriptions
- `hs_code_index` - Quick lookup

### Knowledge
- `knowledge_base` - Uploaded documents (נהלים, פסיקות)
- `classification_knowledge` - Classification rules
- `classification_rules` - GIR rules, Israeli rules
- `procedures` - נוהל סיווג, נוהל הערכה, נוהל תש"ר

### Regulatory
- `ministry_index` - Which HS codes need which ministry
- `regulatory` - General regulatory info
- `regulatory_approvals` - Specific approvals
- `legal_references` - Court decisions

### Agents & Tools
- `hub_agents` - Available AI agents
- `hub_tools` - Available tools
- `hub_tasks` - Task queue

## 🏛️ Israeli Ministries (NOT international)
- **MOT** (משרד התחבורה) - Vehicles, תקנה 271א for M1/M2
- **MOH** (משרד הבריאות) - Food, pharma, cosmetics
- **MOA** (משרד החקלאות) - Plants, animals
- **SII** (מכון התקנים) - Standards (ת"י)
- **MOE** (משרד הכלכלה) - צו יבוא חופשי

## 📝 Israeli HS Code Format
NOT: 8703.21.00 (international)
YES: 87.03.808000/5 (Israeli)

Structure: XX.XX.XXXXXX/X
- XX = Chapter
- XX = Heading  
- XXXXXX = Subheading
- X = Statistical suffix

## 📚 Key Documents Uploaded
1. צו תעריף המכס (יבוא)
2. צו תעריף המכס (יצוא)
3. צו יבוא חופשי (צו מסגרת)
4. נוהל סיווג טובין
5. נוהל הערכה
6. נוהל תש"ר

## 🔄 RCB Flow
1. Email arrives at rcb@rpa-port.co.il
2. Send ACK email (immediate)
3. Extract text from PDFs
4. Query Firestore for tariff data
5. Run 6 classification agents
6. Query Firestore for ministry requirements
7. Build HTML + Excel + PDF
8. Send report with original attachments

## 📤 Output Requirements
1. **Email body** - HTML report in Hebrew
2. **Excel attachment** - Multi-sheet (סיכום, סיווגים, רגולציה)
3. **PDF attachment** - Full report
4. **Original docs** - Re-attached

## ⚠️ Common Mistakes to Avoid
1. Don't use international HS format
2. Don't guess - query Firestore
3. Don't forget MOT for vehicles
4. Don't forget to re-attach original docs
5. Don't deploy helper functions as Cloud Functions (use underscore or move to lib/)

## 🔧 Project Structure
```
~/rpa-port-platform/functions/
├── main.py                 # Cloud Functions (DO NOT add helpers here)
├── lib/
│   ├── classification_agents.py  # AI agents
│   └── rcb_helpers.py            # Graph API, PDF extraction
```

## 🚀 Deploy Command
```bash
cd ~/rpa-port-platform && firebase deploy --only functions
```
