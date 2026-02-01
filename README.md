# RPA-PORT: Israeli Customs Intelligence Platform

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FIREBASE (The Brain)                   │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Firestore │  │ Storage  │  │  Auth    │  │ Hosting │ │
│  │ Database  │  │ (PDFs)   │  │ (Users)  │  │(Web App)│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │             │              │      │
│  ┌────┴──────────────┴─────────────┴──────────────┴────┐ │
│  │              Cloud Functions (Serverless)             │ │
│  │  • check_email (every 5 min)                         │ │
│  │  • classify_document (on new document)               │ │
│  │  • enrich_knowledge (every hour)                     │ │
│  │  • learn_from_correction (on user correction)        │ │
│  │  • api (HTTP endpoints for web app)                  │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │  Gmail  │         │  Claude │         │  Gov.il │
    │ (inbox) │         │  (AI)   │         │ (data)  │
    └─────────┘         └─────────┘         └─────────┘
         │
    ┌────┴────┐
    │ Office  │
    │   PC    │
    │ (agent) │
    └─────────┘
```

## Project Structure

```
rpa-port-platform/
├── firebase.json              # Firebase project config
├── firestore.rules            # Database security rules
├── firestore.indexes.json     # Database indexes
├── storage.rules              # File storage rules
├── functions/                 # Cloud Functions (serverless)
│   ├── main.py               # All cloud functions
│   └── requirements.txt      # Python dependencies
├── web-app/                   # Web dashboard
│   └── public/
│       └── index.html         # Main app (React)
├── scripts/                   # Utility scripts
│   ├── rpa_agent.py           # Office PC agent (downloads)
│   ├── upload_knowledge.py    # Knowledge base uploader
│   └── migrate.py             # Data migration tools
├── docs/                      # Documentation
│   └── setup.md               # Setup guide
└── README.md                  # This file
```

## Firestore Collections

### Core Data
| Collection | Purpose | Key Fields |
|---|---|---|
| `knowledge_base` | Master customs knowledge | category, title, content |
| `classifications` | HS code classifications | seller, product, hs_code, status |
| `sellers` | Known seller profiles | name, country, known_hs_codes |
| `inbox` | Processed emails | from, subject, attachments |

### Document Collections
| Collection | Purpose |
|---|---|
| `declarations` | Customs declarations (WG) |
| `regulatory_certificates` | EMC/RF/Safety certs |
| `origin_certificates` | EUR.1, Form A |
| `packing_lists` | Packing lists |
| `bills_of_lading` | BOL/AWB |
| `import_permits` | Licenses/permits |
| `lab_reports` | Lab test results |

### System Collections
| Collection | Purpose |
|---|---|
| `agent_tasks` | Tasks for office PC agent |
| `pending_tasks` | Items needing attention |
| `enrichment_log` | Knowledge update tracking |
| `learning_log` | AI learning events |
| `config` | System configuration |
| `companies` | Multi-tenant company data |

## Self-Learning System

The platform learns automatically:

1. **Email arrives** → Documents classified → Knowledge gaps identified
2. **User corrects** a classification → System updates seller profile + HS knowledge
3. **Declaration arrives** → Compared with AI classification → Differences logged for learning
4. **New seller seen** → Profile created → Future invoices pre-classified
5. **Certificate expires** → Alert created → Renewal tracked

## Setup

### Prerequisites
- Node.js 18+
- Firebase CLI (`npm install -g firebase-tools`)
- Python 3.12+

### Deploy
```bash
firebase login
firebase init
firebase deploy
```

### Local Development
```bash
cd functions
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
firebase emulators:start
```

## Multi-Tenant Architecture

Each customs brokerage company gets:
- Their own email inbox monitoring
- Private classifications and documents
- Access to shared knowledge base (read-only)
- Their own users and permissions

Shared across all companies:
- Master knowledge base (HS codes, procedures, regulations)
- Seller database (enriched from all companies' data)
- Regulatory updates and alerts
