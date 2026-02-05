import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  BookOpen, Search, Library, FileText, Scale, Shield, 
  ScrollText, Globe, MessageCircle, Send, Bot, User, Sparkles, Database,
  Mail, RefreshCw, ChevronRight, ChevronDown, ChevronLeft, FolderOpen, FileSearch,
  Landmark, BookMarked, HelpCircle, Clock, Ship, Plane,
  CheckCircle2, Loader2, Mic, Package, Gavel, Filter, X, Download,
  ExternalLink, AlertTriangle, Info, Star, History, Bookmark, Copy,
  ArrowLeft, Home, Settings, Zap, Layers, Network, Eye
} from 'lucide-react';

/**
 * AI Librarian & Researcher Hub - ENHANCED VERSION
 * RPA-PORT Master Hub Component
 * 
 * Features:
 * - Firestore Integration
 * - Advanced Search with Filters
 * - Wing Detail Pages
 * - Real-time Data Loading
 * - Search History
 * - Bookmarks
 * 
 * Data Sources:
 * - Firestore Library Collections
 * - Web Search (Real-time)
 * - Email Enrichment Database (airpaport@gmail.com)
 * - Classification History
 */

// ============================================
// FIRESTORE SERVICE (Mock - Replace with real Firebase)
// ============================================

class LibrarianFirestoreService {
  constructor() {
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
  }

  async getWingDocuments(wingId, sectionId = null, options = {}) {
    const cacheKey = `${wingId}-${sectionId}-${JSON.stringify(options)}`;
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }

    // Simulate Firestore query
    await new Promise(resolve => setTimeout(resolve, 500));
    
    const data = this.getMockData(wingId, sectionId, options);
    this.cache.set(cacheKey, { data, timestamp: Date.now() });
    
    return data;
  }

  async searchDocuments(query, filters = {}) {
    await new Promise(resolve => setTimeout(resolve, 800));
    return this.getMockSearchResults(query, filters);
  }

  async getDocument(wingId, documentId) {
    await new Promise(resolve => setTimeout(resolve, 300));
    return this.getMockDocument(wingId, documentId);
  }

  getMockData(wingId, sectionId, options) {
    const baseDocuments = {
      'customs-tariff': [
        { id: 'ch-85', code: '85', titleHe: 'מכונות וציוד חשמליים', titleEn: 'Electrical Machinery', documents: 450, lastUpdate: '2025-01-15' },
        { id: 'ch-84', code: '84', titleHe: 'מכונות ומתקנים מכניים', titleEn: 'Machinery', documents: 520, lastUpdate: '2025-01-15' },
        { id: 'ch-87', code: '87', titleHe: 'כלי רכב', titleEn: 'Vehicles', documents: 180, lastUpdate: '2025-01-10' },
        { id: 'ch-39', code: '39', titleHe: 'פלסטיק ומוצריו', titleEn: 'Plastics', documents: 210, lastUpdate: '2025-01-12' },
        { id: 'ch-73', code: '73', titleHe: 'מוצרי ברזל ופלדה', titleEn: 'Iron and Steel Articles', documents: 165, lastUpdate: '2025-01-08' },
      ],
      'free-import': [
        { id: 'sch-1-1', code: 'FI-001', titleHe: 'אישור משרד הבריאות - תרופות', ministry: 'בריאות', type: 'רישיון', lastUpdate: '2025-01-14' },
        { id: 'sch-1-2', code: 'FI-002', titleHe: 'אישור משרד החקלאות - מזון', ministry: 'חקלאות', type: 'אישור', lastUpdate: '2025-01-13' },
        { id: 'sch-1-3', code: 'FI-003', titleHe: 'תקן מכון התקנים', ministry: 'כלכלה', type: 'תקן', lastUpdate: '2025-01-12' },
      ],
      'enriched-db': [
        { id: 'email-1', subject: 'שאילתת סיווג - USB cables', from: 'client@example.com', date: '2025-01-20', status: 'processed' },
        { id: 'email-2', subject: 'בקשת הצעת מחיר - יבוא אלקטרוניקה', from: 'supplier@china.com', date: '2025-01-19', status: 'processed' },
        { id: 'email-3', subject: 'עדכון תעריף מכס', from: 'customs@taxes.gov.il', date: '2025-01-18', status: 'processed' },
      ]
    };

    return {
      documents: baseDocuments[wingId] || [],
      total: (baseDocuments[wingId] || []).length,
      page: options.page || 1,
      pageSize: options.pageSize || 20
    };
  }

  getMockSearchResults(query, filters) {
    const results = [
      { id: 1, type: 'tariff', code: '8517.12', titleHe: 'טלפונים לרשתות תאיות', wing: 'customs-tariff', relevance: 0.95 },
      { id: 2, type: 'regulation', code: 'FI-COMM-01', titleHe: 'אישור משרד התקשורת למכשירי קצה', wing: 'free-import', relevance: 0.88 },
      { id: 3, type: 'standard', code: 'ת"י 62368', titleHe: 'בטיחות ציוד טכנולוגיית מידע', wing: 'standards', relevance: 0.82 },
      { id: 4, type: 'email', code: 'EMAIL-2024-1205', titleHe: 'סיווג טלפונים סלולריים - תשובה', wing: 'enriched-db', relevance: 0.75 },
    ];

    return {
      results: results.filter(r => 
        !filters.wingId || r.wing === filters.wingId
      ),
      total: results.length,
      query,
      filters
    };
  }

  getMockDocument(wingId, documentId) {
    return {
      id: documentId,
      wingId,
      titleHe: 'מסמך לדוגמה',
      titleEn: 'Sample Document',
      content: 'תוכן המסמך המלא יטען מ-Firestore...',
      metadata: {
        createdAt: '2024-01-01',
        updatedAt: '2025-01-15',
        author: 'מערכת',
        version: '2.0'
      },
      relatedDocuments: []
    };
  }
}

const firestoreService = new LibrarianFirestoreService();

// ============================================
// LIBRARY WINGS DATA
// ============================================

const LIBRARY_WINGS = [
  {
    id: 'customs-tariff',
    icon: Scale,
    titleHe: 'תעריף מכס יבוא',
    titleEn: 'Import Customs Tariff',
    description: 'צו תעריף המכס והפטורים ומס קנייה על טובין',
    color: 'blue',
    gradient: 'from-blue-600 to-indigo-700',
    bgLight: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-700',
    stats: { documents: 5300, chapters: 99, supplements: 17 },
    firestoreCollection: 'library_import_tariff',
    sections: [
      { id: 'framework', name: 'צו מסגרת', nameEn: 'Framework Order', count: 1, icon: '📜' },
      { id: 'first-supplement', name: 'תוספת ראשונה (פרקים 01-99)', nameEn: 'First Supplement', count: 99, icon: '📚' },
      { id: 'supplements-2-17', name: 'תוספות ב׳-י״ז (הסכמי סחר)', nameEn: 'Trade Agreements', count: 16, icon: '🌍' },
      { id: 'discount-codes', name: 'קודי הנחה', nameEn: 'Discount Codes', count: 50, icon: '🏷️' },
    ]
  },
  {
    id: 'free-import',
    icon: Ship,
    titleHe: 'צו יבוא חופשי',
    titleEn: 'Free Import Order',
    description: 'צו יבוא חופשי, התשע"ד-2014 - רישיונות ואישורי יבוא',
    color: 'emerald',
    gradient: 'from-emerald-600 to-teal-700',
    bgLight: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    textColor: 'text-emerald-700',
    stats: { documents: 850, schedules: 7, ministries: 15 },
    firestoreCollection: 'library_free_import',
    sections: [
      { id: 'main-order', name: 'צו יבוא חופשי - גוף הצו', nameEn: 'Main Order', count: 1, icon: '📋' },
      { id: 'schedule-1', name: 'תוספת ראשונה - רישיונות יבוא', nameEn: 'First Schedule', count: 180, icon: '📝' },
      { id: 'schedule-2', name: 'תוספת שניה - אישורים ותנאים', nameEn: 'Second Schedule', count: 320, icon: '✅' },
      { id: 'schedule-3', name: 'תוספת שלישית - יבוא אישי', nameEn: 'Third Schedule', count: 95, icon: '👤' },
      { id: 'schedule-4', name: 'תוספת רביעית - סמים ורעלים', nameEn: 'Fourth Schedule', count: 45, icon: '⚠️' },
      { id: 'schedule-5', name: 'תוספת חמישית - מוצרי מזון', nameEn: 'Fifth Schedule', count: 120, icon: '🍎' },
      { id: 'schedule-6', name: 'תוספת שישית - חקלאות', nameEn: 'Sixth Schedule', count: 90, icon: '🌾' },
    ]
  },
  {
    id: 'free-export',
    icon: Plane,
    titleHe: 'צו יצוא חופשי',
    titleEn: 'Free Export Order',
    description: 'צו יצוא חופשי - פיקוח על יצוא טובין ושירותים',
    color: 'violet',
    gradient: 'from-violet-600 to-purple-700',
    bgLight: 'bg-violet-50',
    borderColor: 'border-violet-200',
    textColor: 'text-violet-700',
    stats: { documents: 320, categories: 5, controls: 45 },
    firestoreCollection: 'library_free_export',
    sections: [
      { id: 'main-order', name: 'צו יצוא חופשי - גוף הצו', nameEn: 'Main Order', count: 1, icon: '📋' },
      { id: 'schedule-1', name: 'תוספת ראשונה - יצוא מבוקר', nameEn: 'Controlled Export', count: 85, icon: '🔒' },
      { id: 'schedule-2', name: 'תוספת שניה - דו-שימושי', nameEn: 'Dual Use', count: 120, icon: '⚡' },
      { id: 'defense-export', name: 'חוק הפיקוח על יצוא ביטחוני', nameEn: 'Defense Export', count: 65, icon: '🛡️' },
      { id: 'sanctions', name: 'סנקציות ומגבלות', nameEn: 'Sanctions', count: 49, icon: '🚫' },
    ]
  },
  {
    id: 'gov-regulations',
    icon: Landmark,
    titleHe: 'תקנות ממשלתיות',
    titleEn: 'Government Regulations',
    description: 'תקנות, צווים והוראות של משרדי הממשלה',
    color: 'amber',
    gradient: 'from-amber-600 to-orange-700',
    bgLight: 'bg-amber-50',
    borderColor: 'border-amber-200',
    textColor: 'text-amber-700',
    stats: { documents: 480, ministries: 7, updates: 'שבועי' },
    firestoreCollection: 'library_government_regs',
    sections: [
      { id: 'health', name: 'משרד הבריאות', nameEn: 'Ministry of Health', count: 95, icon: '🏥' },
      { id: 'agriculture', name: 'משרד החקלאות', nameEn: 'Ministry of Agriculture', count: 78, icon: '🌾' },
      { id: 'economy', name: 'משרד הכלכלה', nameEn: 'Ministry of Economy', count: 120, icon: '📊' },
      { id: 'environment', name: 'המשרד להגנת הסביבה', nameEn: 'Environment', count: 65, icon: '🌿' },
      { id: 'transport', name: 'משרד התחבורה', nameEn: 'Ministry of Transport', count: 45, icon: '🚛' },
      { id: 'communications', name: 'משרד התקשורת', nameEn: 'Communications', count: 38, icon: '📡' },
      { id: 'defense', name: 'משרד הביטחון', nameEn: 'Ministry of Defense', count: 39, icon: '🛡️' },
    ]
  },
  {
    id: 'standards',
    icon: Shield,
    titleHe: 'תקנים ישראליים',
    titleEn: 'Israeli Standards',
    description: 'תקני מכון התקנים הישראלי (ת"י) ותקני CE',
    color: 'rose',
    gradient: 'from-rose-600 to-pink-700',
    bgLight: 'bg-rose-50',
    borderColor: 'border-rose-200',
    textColor: 'text-rose-700',
    stats: { documents: 620, mandatory: 180, voluntary: 440 },
    firestoreCollection: 'library_standards',
    sections: [
      { id: 'mandatory', name: 'תקנים רשמיים (חובה)', nameEn: 'Mandatory', count: 180, icon: '⚠️' },
      { id: 'voluntary', name: 'תקנים מומלצים', nameEn: 'Voluntary', count: 440, icon: '✨' },
      { id: 'ce-marking', name: 'תקני CE אירופיים', nameEn: 'CE Standards', count: 95, icon: '🇪🇺' },
      { id: 'testing-labs', name: 'מעבדות בדיקה מאושרות', nameEn: 'Testing Labs', count: 45, icon: '🔬' },
    ]
  },
  {
    id: 'classification',
    icon: BookMarked,
    titleHe: 'הנחיות סיווג',
    titleEn: 'Classification Guidelines',
    description: 'פסיקות סיווג, הנחיות מכס והחלטות מקדמיות',
    color: 'cyan',
    gradient: 'from-cyan-600 to-sky-700',
    bgLight: 'bg-cyan-50',
    borderColor: 'border-cyan-200',
    textColor: 'text-cyan-700',
    stats: { documents: 890, rulings: 450, guidelines: 440 },
    firestoreCollection: 'library_classification',
    sections: [
      { id: 'rulings', name: 'פסיקות סיווג', nameEn: 'Rulings', count: 450, icon: '⚖️' },
      { id: 'wco-opinions', name: 'חוות דעת WCO', nameEn: 'WCO Opinions', count: 120, icon: '🌐' },
      { id: 'court-decisions', name: 'פסקי דין', nameEn: 'Court Decisions', count: 85, icon: '🏛️' },
      { id: 'explanatory-notes', name: 'הערות הסבר', nameEn: 'Explanatory Notes', count: 235, icon: '📖' },
    ]
  },
  {
    id: 'legal',
    icon: Gavel,
    titleHe: 'חקיקה ופסיקה',
    titleEn: 'Legislation & Case Law',
    description: 'חוקים, תקנות ופסקי דין בתחום המכס והסחר',
    color: 'slate',
    gradient: 'from-slate-600 to-gray-700',
    bgLight: 'bg-slate-50',
    borderColor: 'border-slate-300',
    textColor: 'text-slate-700',
    stats: { documents: 340, laws: 45, cases: 295 },
    firestoreCollection: 'library_legal',
    sections: [
      { id: 'customs-ordinance', name: 'פקודת המכס', nameEn: 'Customs Ordinance', count: 1, icon: '📜' },
      { id: 'customs-laws', name: 'חוקי מכס', nameEn: 'Customs Laws', count: 25, icon: '⚖️' },
      { id: 'supreme-court', name: 'פסקי דין - עליון', nameEn: 'Supreme Court', count: 85, icon: '🏛️' },
      { id: 'district-court', name: 'פסקי דין - מחוזי', nameEn: 'District Court', count: 210, icon: '🏢' },
    ]
  },
  {
    id: 'enriched-db',
    icon: Database,
    titleHe: 'מאגר מועשר',
    titleEn: 'Enriched Database',
    description: 'מידע מועשר מסוכני AI - מיילים, חיפושים ולקוחות',
    color: 'indigo',
    gradient: 'from-indigo-600 to-blue-700',
    bgLight: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    textColor: 'text-indigo-700',
    stats: { emails: 1250, searches: 3400, entities: 890 },
    firestoreCollection: 'enriched_data',
    sections: [
      { id: 'email-enrichment', name: 'העשרת מיילים', nameEn: 'Email Enrichment', count: 1250, icon: '📧', note: 'airpaport@gmail.com' },
      { id: 'search-results', name: 'תוצאות חיפוש מצטברות', nameEn: 'Search Results', count: 3400, icon: '🔍' },
      { id: 'clients', name: 'מאגר לקוחות', nameEn: 'Clients', count: 320, icon: '👥' },
      { id: 'suppliers', name: 'מאגר ספקים', nameEn: 'Suppliers', count: 180, icon: '🏭' },
      { id: 'products', name: 'מאגר מוצרים וסיווגים', nameEn: 'Products', count: 890, icon: '📦' },
      { id: 'hs-history', name: 'היסטוריית סיווגים', nameEn: 'HS History', count: 2100, icon: '📋' },
    ]
  },
];

// ============================================
// ADVANCED SEARCH COMPONENT
// ============================================

const AdvancedSearch = ({ onSearch, onClose }) => {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({
    wings: [],
    dateFrom: '',
    dateTo: '',
    documentType: 'all',
    sortBy: 'relevance'
  });
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [searchHistory, setSearchHistory] = useState([
    'טלפונים סלולריים',
    'USB cables HS code',
    'אישור משרד הבריאות',
  ]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    try {
      const searchResults = await firestoreService.searchDocuments(query, filters);
      setResults(searchResults);
      
      // Add to history
      if (!searchHistory.includes(query)) {
        setSearchHistory(prev => [query, ...prev.slice(0, 9)]);
      }
    } catch (error) {
      console.error('Search error:', error);
    }
    setIsSearching(false);
  };

  const toggleWingFilter = (wingId) => {
    setFilters(prev => ({
      ...prev,
      wings: prev.wings.includes(wingId)
        ? prev.wings.filter(w => w !== wingId)
        : [...prev.wings, wingId]
    }));
  };

  return (
    <div className="bg-white rounded-2xl shadow-2xl border overflow-hidden max-w-4xl w-full max-h-[90vh] flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-l from-indigo-600 to-blue-700 text-white p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Search className="w-6 h-6" />
            <div>
              <h2 className="font-bold text-lg">חיפוש מתקדם</h2>
              <p className="text-sm opacity-80">חיפוש בכל אגפי הספרייה</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/20 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Search Input */}
      <div className="p-4 border-b">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyPress={e => e.key === 'Enter' && handleSearch()}
              placeholder="חפש קוד HS, מסמך, תקנה, פסיקה..."
              className="w-full py-3 pr-10 pl-4 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-lg"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
            className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-xl font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          >
            {isSearching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
            חפש
          </button>
        </div>

        {/* Search History */}
        {searchHistory.length > 0 && !results && (
          <div className="mt-3">
            <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
              <History className="w-3 h-3" />
              חיפושים אחרונים:
            </p>
            <div className="flex flex-wrap gap-2">
              {searchHistory.map((h, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(h)}
                  className="text-xs bg-slate-100 px-3 py-1 rounded-full hover:bg-indigo-100 hover:text-indigo-700 transition"
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="p-4 border-b bg-slate-50">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700">סינון לפי אגף:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {LIBRARY_WINGS.map(wing => {
            const Icon = wing.icon;
            const isSelected = filters.wings.includes(wing.id);
            return (
              <button
                key={wing.id}
                onClick={() => toggleWingFilter(wing.id)}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition ${
                  isSelected 
                    ? `bg-${wing.color}-100 ${wing.textColor} border-2 border-${wing.color}-300`
                    : 'bg-white border hover:bg-slate-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                {wing.titleHe}
              </button>
            );
          })}
        </div>

        {/* Additional Filters */}
        <div className="flex gap-4 mt-3">
          <select
            value={filters.documentType}
            onChange={e => setFilters(prev => ({ ...prev, documentType: e.target.value }))}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value="all">כל סוגי המסמכים</option>
            <option value="tariff">פרטי מכס</option>
            <option value="regulation">תקנות</option>
            <option value="standard">תקנים</option>
            <option value="ruling">פסיקות</option>
            <option value="email">מיילים</option>
          </select>
          <select
            value={filters.sortBy}
            onChange={e => setFilters(prev => ({ ...prev, sortBy: e.target.value }))}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value="relevance">מיון לפי רלוונטיות</option>
            <option value="date">מיון לפי תאריך</option>
            <option value="name">מיון לפי שם</option>
          </select>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4">
        {isSearching ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
            <p className="text-slate-500">מחפש בספרייה...</p>
          </div>
        ) : results ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-slate-600">
                נמצאו <strong>{results.total}</strong> תוצאות עבור "{results.query}"
              </p>
              <button
                onClick={() => setResults(null)}
                className="text-xs text-indigo-600 hover:underline"
              >
                נקה תוצאות
              </button>
            </div>
            <div className="space-y-2">
              {results.results.map(result => {
                const wing = LIBRARY_WINGS.find(w => w.id === result.wing);
                const Icon = wing?.icon || FileText;
                return (
                  <div
                    key={result.id}
                    className="flex items-start gap-3 p-3 border rounded-lg hover:bg-slate-50 cursor-pointer transition"
                  >
                    <div className={`p-2 rounded-lg bg-gradient-to-br ${wing?.gradient || 'from-slate-500 to-slate-600'}`}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-indigo-600">{result.code}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${wing?.bgLight} ${wing?.textColor}`}>
                          {wing?.titleHe}
                        </span>
                      </div>
                      <h4 className="font-medium text-slate-800 mt-1">{result.titleHe}</h4>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">{Math.round(result.relevance * 100)}%</span>
                      <ChevronLeft className="w-4 h-4 text-slate-400" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <Search className="w-12 h-12 mb-3 opacity-50" />
            <p>הזן מונח לחיפוש</p>
            <p className="text-sm">ניתן לחפש לפי קוד HS, שם מוצר, תקנה, או כל טקסט</p>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// WING DETAIL PAGE COMPONENT
// ============================================

const WingDetailPage = ({ wing, onBack }) => {
  const [activeSection, setActiveSection] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchInWing, setSearchInWing] = useState('');

  const Icon = wing.icon;

  const loadDocuments = async (sectionId = null) => {
    setIsLoading(true);
    try {
      const data = await firestoreService.getWingDocuments(wing.id, sectionId);
      setDocuments(data.documents);
    } catch (error) {
      console.error('Error loading documents:', error);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    loadDocuments();
  }, [wing.id]);

  const handleSectionClick = (section) => {
    setActiveSection(section);
    loadDocuments(section.id);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-blue-50">
      {/* Header */}
      <div className={`bg-gradient-to-l ${wing.gradient} text-white p-6`}>
        <div className="max-w-7xl mx-auto">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-1.5 bg-white/20 rounded-lg hover:bg-white/30 transition mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            חזרה לספרייה
          </button>
          
          <div className="flex items-center gap-4">
            <div className="p-4 bg-white/20 rounded-2xl">
              <Icon className="w-12 h-12" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">{wing.titleHe}</h1>
              <p className="text-white/80">{wing.titleEn}</p>
              <p className="text-sm text-white/60 mt-1">{wing.description}</p>
            </div>
          </div>

          {/* Stats */}
          <div className="flex gap-4 mt-6">
            {Object.entries(wing.stats).map(([key, value]) => (
              <div key={key} className="bg-white/20 px-4 py-2 rounded-xl">
                <div className="text-2xl font-bold">{typeof value === 'number' ? value.toLocaleString() : value}</div>
                <div className="text-xs text-white/70">{key}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto p-6">
        <div className="grid lg:grid-cols-4 gap-6">
          {/* Sections Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border shadow-sm p-4 sticky top-4">
              <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Layers className="w-5 h-5" />
                סעיפים
              </h3>
              <div className="space-y-1">
                <button
                  onClick={() => { setActiveSection(null); loadDocuments(); }}
                  className={`w-full text-right p-2 rounded-lg transition ${
                    !activeSection ? `${wing.bgLight} ${wing.textColor}` : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="font-medium text-sm">הכל</div>
                </button>
                {wing.sections.map(section => (
                  <button
                    key={section.id}
                    onClick={() => handleSectionClick(section)}
                    className={`w-full text-right p-2 rounded-lg transition ${
                      activeSection?.id === section.id ? `${wing.bgLight} ${wing.textColor}` : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span>{section.icon}</span>
                      <span className="flex-1 font-medium text-sm truncate">{section.name}</span>
                      <span className="text-xs bg-slate-100 px-2 py-0.5 rounded-full">{section.count}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Documents */}
          <div className="lg:col-span-3">
            {/* Search in Wing */}
            <div className="bg-white rounded-xl border shadow-sm p-4 mb-4">
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    value={searchInWing}
                    onChange={e => setSearchInWing(e.target.value)}
                    placeholder={`חפש ב${wing.titleHe}...`}
                    className="w-full py-2 pr-10 pl-4 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <button className="px-4 py-2 border rounded-lg hover:bg-slate-50 flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  סינון
                </button>
              </div>
            </div>

            {/* Documents List */}
            <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
              <div className="p-4 border-b bg-slate-50">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-800">
                    {activeSection ? activeSection.name : 'כל המסמכים'}
                  </h3>
                  <span className="text-sm text-slate-500">
                    {isLoading ? 'טוען...' : `${documents.length} מסמכים`}
                  </span>
                </div>
              </div>

              {isLoading ? (
                <div className="p-12 text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
                  <p className="text-slate-500">טוען מסמכים...</p>
                </div>
              ) : documents.length > 0 ? (
                <div className="divide-y">
                  {documents.map(doc => (
                    <div key={doc.id} className="p-4 hover:bg-slate-50 cursor-pointer transition">
                      <div className="flex items-start gap-3">
                        <FileText className={`w-5 h-5 ${wing.textColor} mt-0.5`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm text-indigo-600">{doc.code}</span>
                            {doc.ministry && (
                              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                                {doc.ministry}
                              </span>
                            )}
                          </div>
                          <h4 className="font-medium text-slate-800 mt-1">{doc.titleHe}</h4>
                          {doc.titleEn && (
                            <p className="text-sm text-slate-500">{doc.titleEn}</p>
                          )}
                          <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                            {doc.documents && <span>{doc.documents} מסמכים</span>}
                            {doc.lastUpdate && <span>עודכן: {doc.lastUpdate}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button className="p-2 hover:bg-slate-100 rounded-lg" title="שמור">
                            <Bookmark className="w-4 h-4 text-slate-400" />
                          </button>
                          <button className="p-2 hover:bg-slate-100 rounded-lg" title="צפה">
                            <Eye className="w-4 h-4 text-slate-400" />
                          </button>
                          <ChevronLeft className="w-5 h-5 text-slate-300" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-12 text-center text-slate-400">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>אין מסמכים להצגה</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// HELP DESK COMPONENT
// ============================================

const HelpDesk = ({ onClose }) => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      isUser: false,
      text: `שלום! אני הספרן הראשי של RPA-PORT 📚

אני מחובר למקורות המידע הבאים:
• 📚 ספריית המכס והסחר (8,460+ מסמכים)
• 🌐 חיפוש אינטרנט בזמן אמת
• 💾 מאגר מועשר - מיילים, לקוחות, היסטוריה
• 📧 Email Enrichment (airpaport@gmail.com)

במה אוכל לעזור?`,
      sources: null
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [searchScope, setSearchScope] = useState(['library', 'web', 'database']);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const generateResponse = (query) => {
    const lowerQuery = query.toLowerCase();
    
    if (lowerQuery.includes('טלפון') || lowerQuery.includes('סלולר') || lowerQuery.includes('8517')) {
      return {
        text: `מצאתי מידע מקיף על יבוא טלפונים סלולריים:

📋 **סיווג מכס**
• פרט: 8517.12.00.00
• תיאור: טלפונים לרשתות תאיות

💰 **מיסים**
• מכס: פטור (0%)
• מס קנייה: פטור
• מע"מ: 17%

📜 **דרישות יבוא**
• אישור משרד התקשורת - חובה
• תקן ת"י 62368 (בטיחות) - חובה
• סימון CE - מקובל כשווה ערך
• FCC - לא נדרש בישראל

⚠️ **הערות חשובות**
• יש לוודא תמיכה בתדרי ישראל
• נדרש אישור תקשורת לפני שחרור

במאגר המועשר מצאתי 3 עסקאות דומות מהשנה האחרונה.`,
        sources: ['📚 תעריף מכס - פרק 85', '📋 צו יבוא חופשי', '📡 תקנות משרד התקשורת', '💾 מאגר מועשר']
      };
    }
    
    if (lowerQuery.includes('קוסמטיקה') || lowerQuery.includes('33')) {
      return {
        text: `מידע על יבוא מוצרי קוסמטיקה:

📋 **סיווג**
• פרק 33 - שמני אתרים, בשמים, קוסמטיקה
• פרטים עיקריים: 3303-3307

💰 **מכס**
• בשמים (3303): 12%
• מוצרי איפור (3304): 12%
• מוצרי טיפוח שיער (3305): 8%
• תכשירי גילוח (3307): 8%

📜 **דרישות**
• רישום מוצר קוסמטי במשרד הבריאות
• תווית בעברית (חובה)
• רשימת רכיבים מלאה
• הוראות שימוש

🇪🇺 **הסכם EU**
• מוצרים מהאיחוד האירופי - פטור ממכס`,
        sources: ['📚 תעריף מכס - פרק 33', '🏥 תקנות משרד הבריאות', '🇪🇺 הסכם EU']
      };
    }

    if (lowerQuery.includes('usb') || lowerQuery.includes('כבל')) {
      return {
        text: `מידע על יבוא כבלי USB:

📋 **סיווג מכס**
• כבלי USB רגילים: 8544.42
• כבלי USB עם מחברים: 8544.42.2000
• כבלי נתונים: 8544.42.9000

💰 **מכס**
• שיעור כללי: 6%
• מ-EU: פטור
• מ-USA: פטור (בתנאים)

📜 **דרישות**
• אין צורך ברישיון יבוא
• אין דרישת תקן ספציפי
• סימון CE - מומלץ

💡 **טיפ**
במאגר המועשר מצאתי שהספק ABC מסין סיפק כבלים דומים ב-2024.`,
        sources: ['📚 תעריף מכס - פרק 85', '🇪🇺 הסכם EU', '🇺🇸 הסכם USA', '💾 מאגר ספקים']
      };
    }

    return {
      text: `מחפש מידע על "${query}"...

חיפשתי ב-${searchScope.length} מקורות ומצאתי תוצאות רלוונטיות.

📚 **בספרייה**: נמצאו 4 מסמכים רלוונטיים
🌐 **באינטרנט**: מצאתי עדכונים אחרונים
💾 **במאגר**: יש נתונים היסטוריים

האם תרצה ש:
1. אפרט על דרישות הסיווג והמכס?
2. אבדוק רישיונות ואישורים נדרשים?
3. אחפש תקנים רלוונטיים?
4. אבדוק הסכמי סחר והטבות?

בחר נושא או שאל שאלה ספציפית יותר.`,
      sources: searchScope.map(s => s === 'library' ? '📚 ספריית המכס' : s === 'web' ? '🌐 אינטרנט' : '💾 מאגר מועשר')
    };
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMessage = { id: Date.now(), isUser: true, text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);
    
    setTimeout(() => {
      const { text, sources } = generateResponse(input);
      const response = {
        id: Date.now() + 1,
        isUser: false,
        text,
        sources
      };
      setMessages(prev => [...prev, response]);
      setIsTyping(false);
    }, 1500);
  };

  const toggleScope = (scope) => {
    setSearchScope(prev => 
      prev.includes(scope) 
        ? prev.filter(s => s !== scope)
        : [...prev, scope]
    );
  };

  const sampleQueries = [
    "מה דרישות היבוא לטלפונים סלולריים?",
    "האם צריך רישיון יבוא למוצרי קוסמטיקה?",
    "מה שיעור המכס על כבלי USB?",
    "מהם הסכמי הסחר עם האיחוד האירופי?",
  ];

  return (
    <div className="bg-white rounded-2xl shadow-2xl border-2 border-emerald-200 overflow-hidden flex flex-col h-[600px]">
      {/* Header */}
      <div className="bg-gradient-to-l from-emerald-600 via-teal-600 to-cyan-600 text-white p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-xl">
              <Bot className="w-7 h-7" />
            </div>
            <div>
              <h3 className="font-bold text-lg flex items-center gap-2">
                AI Librarian
                <Sparkles className="w-4 h-4 text-yellow-300" />
              </h3>
              <p className="text-sm opacity-80">דלפק המידע החכם</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-white/20 px-2 py-1 rounded-full">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
              <span className="text-xs">מחובר</span>
            </div>
            {onClose && (
              <button onClick={onClose} className="p-2 hover:bg-white/20 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
        
        {/* Search Scope */}
        <div className="flex gap-2 mt-3 flex-wrap">
          {[
            { id: 'library', icon: Library, label: 'ספרייה', count: '8,460' },
            { id: 'web', icon: Globe, label: 'אינטרנט', count: 'Live' },
            { id: 'database', icon: Database, label: 'מאגר מועשר', count: '5,540' },
          ].map(scope => (
            <button
              key={scope.id}
              onClick={() => toggleScope(scope.id)}
              className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs transition ${
                searchScope.includes(scope.id) 
                  ? 'bg-white text-emerald-700' 
                  : 'bg-white/20 hover:bg-white/30'
              }`}
            >
              <scope.icon className="w-3 h-3" />
              {scope.label}
              {searchScope.includes(scope.id) && <CheckCircle2 className="w-3 h-3" />}
            </button>
          ))}
        </div>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-slate-50 to-white">
        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.isUser ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              msg.isUser ? 'bg-blue-600' : 'bg-gradient-to-br from-emerald-500 to-teal-600'
            }`}>
              {msg.isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
            </div>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
              msg.isUser ? 'bg-blue-600 text-white' : 'bg-white border shadow-sm'
            }`}>
              <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-200">
                  <p className="text-xs text-slate-500 mb-2">מקורות:</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.sources.map((src, i) => (
                      <span key={i} className="text-xs bg-slate-100 px-2 py-1 rounded-full text-slate-600">
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gradient-to-br from-emerald-500 to-teal-600">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white border shadow-sm rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                <span className="text-sm text-slate-500">מחפש במאגרים...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Quick Queries */}
      {messages.length <= 2 && (
        <div className="px-4 py-2 border-t bg-slate-50">
          <p className="text-xs text-slate-500 mb-2">שאילתות מהירות:</p>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {sampleQueries.map((q, i) => (
              <button
                key={i}
                onClick={() => setInput(q)}
                className="flex-shrink-0 text-xs bg-white border px-3 py-1.5 rounded-full hover:bg-emerald-50 hover:border-emerald-300 transition whitespace-nowrap"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
      
      {/* Input */}
      <div className="p-4 border-t bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyPress={e => e.key === 'Enter' && handleSend()}
            placeholder="שאל את הספרן..."
            className="flex-1 px-4 py-3 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          />
          <button className="p-3 text-slate-400 hover:text-slate-600 transition border-2 rounded-xl hover:bg-slate-50">
            <Mic className="w-5 h-5" />
          </button>
          <button 
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-5 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:opacity-90 transition disabled:opacity-50"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================
// LIBRARY WING CARD COMPONENT
// ============================================

const LibraryWingCard = ({ wing, onClick, onExpand, isExpanded }) => {
  const Icon = wing.icon;
  
  return (
    <div className={`bg-white rounded-xl border-2 ${wing.borderColor} hover:shadow-lg transition-all duration-200 overflow-hidden`}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className={`p-3 rounded-xl bg-gradient-to-br ${wing.gradient} shadow-lg flex-shrink-0`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-lg text-slate-800">{wing.titleHe}</h3>
            <p className="text-xs text-slate-500 mb-1">{wing.titleEn}</p>
            <p className="text-sm text-slate-600 line-clamp-2">{wing.description}</p>
          </div>
        </div>
        
        {/* Stats */}
        <div className="flex gap-2 mt-3 flex-wrap">
          {Object.entries(wing.stats).slice(0, 3).map(([key, value]) => (
            <span key={key} className={`px-2 py-1 rounded-full text-xs font-medium ${wing.bgLight} ${wing.textColor}`}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => onClick(wing)}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium bg-gradient-to-r ${wing.gradient} text-white hover:opacity-90 transition flex items-center justify-center gap-2`}
          >
            <Eye className="w-4 h-4" />
            צפה באגף
          </button>
          <button
            onClick={() => onExpand(wing.id)}
            className={`py-2 px-3 rounded-lg text-sm border ${wing.borderColor} hover:${wing.bgLight} transition`}
          >
            <ChevronDown className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>
      
      {/* Expanded Sections */}
      {isExpanded && (
        <div className={`border-t ${wing.borderColor} ${wing.bgLight} p-3`}>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {wing.sections.map(section => (
              <button key={section.id} className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-white transition text-right group">
                <span className="text-lg">{section.icon || '📁'}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-slate-700 truncate">{section.name}</div>
                  {section.note && <div className="text-xs text-slate-400">{section.note}</div>}
                </div>
                <span className="text-xs bg-white px-2 py-0.5 rounded-full flex-shrink-0">{section.count}</span>
                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================
// MAIN COMPONENT
// ============================================

export default function AILibrarianHubEnhanced() {
  const [viewMode, setViewMode] = useState('wings'); // 'wings', 'detail', 'helpdesk', 'search'
  const [expandedWing, setExpandedWing] = useState(null);
  const [selectedWing, setSelectedWing] = useState(null);
  const [showSearch, setShowSearch] = useState(false);
  const [showHelpDesk, setShowHelpDesk] = useState(false);

  const agents = [
    { id: 'email', name: 'Email Enrichment', description: 'airpaport@gmail.com', icon: Mail, bgColor: 'bg-blue-100', iconColor: 'text-blue-600', status: 'active' },
    { id: 'search', name: 'Search Agent', description: 'מחפש ומעדכן מהאינטרנט', icon: Search, bgColor: 'bg-purple-100', iconColor: 'text-purple-600', status: 'active' },
    { id: 'classification', name: 'Classification AI', description: 'Proposer + Reviewer', icon: FileSearch, bgColor: 'bg-emerald-100', iconColor: 'text-emerald-600', status: 'active' },
  ];

  const totalDocs = LIBRARY_WINGS.reduce((sum, w) => sum + (w.stats.documents || w.stats.emails || 0), 0);

  const handleWingClick = (wing) => {
    setSelectedWing(wing);
    setViewMode('detail');
  };

  const handleBackToWings = () => {
    setSelectedWing(null);
    setViewMode('wings');
  };

  if (viewMode === 'detail' && selectedWing) {
    return <WingDetailPage wing={selectedWing} onBack={handleBackToWings} />;
  }

  return (
    <div dir="rtl" className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-emerald-50">
      {/* Header */}
      <header className="bg-gradient-to-l from-slate-800 via-slate-700 to-slate-800 text-white">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl shadow-lg">
                <Library className="w-10 h-10" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                  AI Librarian & Researcher
                  <Sparkles className="w-6 h-6 text-yellow-300" />
                </h1>
                <p className="text-slate-300">ספריית המחקר והמידע של RPA-PORT</p>
              </div>
            </div>
            
            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowSearch(true)}
                className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-xl hover:bg-white/20 transition"
              >
                <Search className="w-5 h-5" />
                חיפוש מתקדם
              </button>
              <button
                onClick={() => setShowHelpDesk(true)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500 rounded-xl hover:bg-emerald-600 transition"
              >
                <MessageCircle className="w-5 h-5" />
                דלפק מידע
                <span className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></span>
              </button>
            </div>
          </div>
          
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
            {[
              { icon: FileText, value: totalDocs.toLocaleString() + '+', label: 'מסמכים' },
              { icon: BookOpen, value: '8', label: 'אגפים' },
              { icon: Mail, value: '1,250', label: 'מיילים' },
              { icon: Search, value: '3,400', label: 'חיפושים' },
              { icon: Bot, value: '3', label: 'סוכני AI' },
            ].map((stat, i) => (
              <div key={i} className="bg-slate-700/50 rounded-xl p-3 flex items-center gap-3">
                <stat.icon className="w-8 h-8 text-emerald-400" />
                <div>
                  <div className="text-xl font-bold">{stat.value}</div>
                  <div className="text-xs text-slate-400">{stat.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 md:p-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Wings Grid */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <FolderOpen className="w-6 h-6 text-emerald-600" />
                אגפי הספרייה
              </h2>
            </div>
            
            <div className="grid md:grid-cols-2 gap-4">
              {LIBRARY_WINGS.map(wing => (
                <LibraryWingCard
                  key={wing.id}
                  wing={wing}
                  isExpanded={expandedWing === wing.id}
                  onClick={handleWingClick}
                  onExpand={(id) => setExpandedWing(expandedWing === id ? null : id)}
                />
              ))}
            </div>
          </div>
          
          {/* Sidebar */}
          <div className="space-y-4">
            {/* Active Agents */}
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Bot className="w-5 h-5 text-purple-600" />
                סוכני AI פעילים
              </h3>
              <div className="space-y-2">
                {agents.map(agent => (
                  <div key={agent.id} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${agent.bgColor}`}>
                      <agent.icon className={`w-5 h-5 ${agent.iconColor}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-sm text-slate-800">{agent.name}</h4>
                      <p className="text-xs text-slate-500 truncate">{agent.description}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                      <span className="text-xs text-green-600">פעיל</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Quick Actions */}
            <div className="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-4 text-white">
              <h3 className="font-bold mb-3 flex items-center gap-2">
                <Zap className="w-5 h-5" />
                פעולות מהירות
              </h3>
              <div className="space-y-2">
                <button 
                  onClick={() => setShowHelpDesk(true)}
                  className="w-full py-2 bg-white/20 rounded-lg text-sm font-medium hover:bg-white/30 transition flex items-center justify-center gap-2"
                >
                  <MessageCircle className="w-4 h-4" />
                  שאל את הספרן
                </button>
                <button 
                  onClick={() => setShowSearch(true)}
                  className="w-full py-2 bg-white/20 rounded-lg text-sm font-medium hover:bg-white/30 transition flex items-center justify-center gap-2"
                >
                  <Search className="w-4 h-4" />
                  חיפוש מתקדם
                </button>
              </div>
            </div>
            
            {/* Recent Activity */}
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Clock className="w-5 h-5 text-blue-600" />
                פעילות אחרונה
              </h3>
              <div className="space-y-2 text-sm">
                {[
                  { action: 'עדכון תעריף מכס', time: 'לפני 2 שעות', icon: Scale },
                  { action: 'מייל חדש עובד', time: 'לפני 3 שעות', icon: Mail },
                  { action: 'חיפוש: USB cables', time: 'לפני 5 שעות', icon: Search },
                  { action: 'סיווג מוצר חדש', time: 'לפני 8 שעות', icon: Package },
                ].map((activity, i) => (
                  <div key={i} className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50">
                    <activity.icon className="w-4 h-4 text-slate-400" />
                    <span className="flex-1 truncate">{activity.action}</span>
                    <span className="text-xs text-slate-400 flex-shrink-0">{activity.time}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Advanced Search Modal */}
      {showSearch && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <AdvancedSearch onClose={() => setShowSearch(false)} />
        </div>
      )}

      {/* Help Desk Modal */}
      {showHelpDesk && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl">
            <HelpDesk onClose={() => setShowHelpDesk(false)} />
          </div>
        </div>
      )}

      {/* Floating Help Button */}
      {!showHelpDesk && (
        <button
          onClick={() => setShowHelpDesk(true)}
          className="fixed bottom-6 left-6 p-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-full shadow-2xl hover:scale-110 transition-all z-40"
        >
          <MessageCircle className="w-6 h-6" />
          <span className="absolute top-0 right-0 w-3 h-3 bg-green-400 rounded-full animate-ping"></span>
          <span className="absolute top-0 right-0 w-3 h-3 bg-green-500 rounded-full"></span>
        </button>
      )}

      {/* Footer */}
      <footer className="text-center p-4 text-slate-400 text-sm border-t bg-white/50 mt-8">
        <p>AI Librarian & Researcher | Firestore + Claude AI</p>
        <p className="font-semibold text-slate-600">RPA-PORT | Customs Brokerage Automation</p>
      </footer>
    </div>
  );
}
