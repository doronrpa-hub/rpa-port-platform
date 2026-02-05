/**
 * RPA-PORT AI Librarian & Researcher Hub
 * Component Index File
 * 
 * Session: February 3, 2026
 * Version: 2.0
 */

// ============================================
// MAIN COMPONENTS
// ============================================

// Full-featured AI Librarian Hub with all integrations
export { default as AILibrarianHub } from './AILibrarianHubEnhanced';

// Basic version (lighter weight)
export { default as AILibrarianHubBasic } from './AILibrarianHub';

// Import Customs Tariff Browser - Complete with צו מסגרת
export { default as ImportTariffBrowser } from './ImportTariffBrowserComplete';

// Tariff Browser Preview (for artifacts/demos)
export { default as TariffBrowserPreview } from './TariffBrowserPreview';

// ============================================
// SERVICES & CLIENTS
// ============================================

// Librarian Firestore Client
export { 
  getLibrarian, 
  LibrarianClient,
  createLibrarianFunctions 
} from './LibrarianClient';

// ============================================
// CLOUD FUNCTIONS
// ============================================

// Main librarian cloud functions
export * from './librarian-functions';

// Maintenance and sync functions
export * from './librarian-maintenance';

// ============================================
// CONSTANTS & CONFIG
// ============================================

export const LIBRARY_CONFIG = {
  // Firestore Collections
  collections: {
    importTariff: 'library_import_tariff',
    freeImport: 'library_free_import',
    freeExport: 'library_free_export',
    govRegulations: 'library_government_regs',
    standards: 'library_standards',
    classification: 'library_classification',
    legal: 'library_legal',
    enrichedData: 'enriched_data',
  },
  
  // Email Enrichment
  enrichmentEmail: 'airpaport@gmail.com',
  
  // Cache settings
  cacheTimeout: 5 * 60 * 1000, // 5 minutes
  
  // API endpoints (if using external)
  endpoints: {
    customsPortal: 'https://shaarolami-query.customs.mof.gov.il',
    taxAuthority: 'https://www.gov.il/he/departments/israel_tax_authority',
  },
};

// Library Wings Configuration
export const LIBRARY_WINGS = [
  {
    id: 'customs-tariff',
    titleHe: 'תעריף מכס יבוא',
    titleEn: 'Import Customs Tariff',
    collection: 'library_import_tariff',
    color: 'blue',
  },
  {
    id: 'free-import',
    titleHe: 'צו יבוא חופשי',
    titleEn: 'Free Import Order',
    collection: 'library_free_import',
    color: 'emerald',
  },
  {
    id: 'free-export',
    titleHe: 'צו יצוא חופשי',
    titleEn: 'Free Export Order',
    collection: 'library_free_export',
    color: 'violet',
  },
  {
    id: 'gov-regulations',
    titleHe: 'תקנות ממשלתיות',
    titleEn: 'Government Regulations',
    collection: 'library_government_regs',
    color: 'amber',
  },
  {
    id: 'standards',
    titleHe: 'תקנים ישראליים',
    titleEn: 'Israeli Standards',
    collection: 'library_standards',
    color: 'rose',
  },
  {
    id: 'classification',
    titleHe: 'הנחיות סיווג',
    titleEn: 'Classification Guidelines',
    collection: 'library_classification',
    color: 'cyan',
  },
  {
    id: 'legal',
    titleHe: 'חקיקה ופסיקה',
    titleEn: 'Legislation & Case Law',
    collection: 'library_legal',
    color: 'slate',
  },
  {
    id: 'enriched-db',
    titleHe: 'מאגר מועשר',
    titleEn: 'Enriched Database',
    collection: 'enriched_data',
    color: 'indigo',
  },
];

// Trade Agreement Supplements
export const TRADE_AGREEMENTS = [
  { num: 'ב׳', name: 'הוראות כלליות', country: null },
  { num: 'ג׳', name: 'WTO', country: 'WTO', flag: '🌐' },
  { num: 'ד׳', name: 'האיחוד האירופי', country: 'EU', flag: '🇪🇺' },
  { num: 'ה׳', name: 'ארצות הברית', country: 'USA', flag: '🇺🇸' },
  { num: 'ו׳', name: 'EFTA', country: 'EFTA', flag: '🇨🇭' },
  { num: 'ז׳', name: 'קנדה', country: 'Canada', flag: '🇨🇦' },
  { num: 'ח׳', name: 'מקסיקו', country: 'Mexico', flag: '🇲🇽' },
  { num: 'ט׳', name: 'טורקיה', country: 'Turkey', flag: '🇹🇷' },
  { num: 'י׳', name: 'ירדן', country: 'Jordan', flag: '🇯🇴' },
  { num: 'י״א', name: 'CAFTA', country: 'CAFTA', flag: '🌎' },
  { num: 'י״ב', name: 'MERCOSUR', country: 'MERCOSUR', flag: '🌎' },
  { num: 'י״ג', name: 'הפחתה כללית', country: null },
  { num: 'י״ד', name: 'פנמה', country: 'Panama', flag: '🇵🇦' },
  { num: 'ט״ו', name: 'קולומביה', country: 'Colombia', flag: '🇨🇴' },
  { num: 'ט״ז', name: 'אוקראינה', country: 'Ukraine', flag: '🇺🇦' },
  { num: 'י״ז', name: 'קוריאה', country: 'Korea', flag: '🇰🇷' },
];

// ============================================
// VERSION INFO
// ============================================

export const VERSION = {
  session: '2026-02-03',
  hub: '2.0.0',
  librarian: '1.0.0',
};
