/**
 * Librarian AI - Client-Side Wrapper
 * RPA-PORT Customs Brokerage Library System
 * 
 * Firebase Project: rpa-port-customs
 * Mission 6: Librarian AI Integration
 * 
 * Usage:
 *   import { LibrarianClient } from './LibrarianClient';
 *   const librarian = new LibrarianClient();
 *   const tariffInfo = await librarian.getTariffInfo('8536907000');
 */

import { getFunctions, httpsCallable } from 'firebase/functions';
import { getFirestore, doc, getDoc, collection, query, where, getDocs, limit } from 'firebase/firestore';

// ============================================
// LIBRARIAN CLIENT CLASS
// ============================================

export class LibrarianClient {
  constructor(firebaseApp = null) {
    this.functions = getFunctions(firebaseApp, 'us-central1');
    this.db = getFirestore(firebaseApp);
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes local cache
  }

  // ============================================
  // CACHING HELPERS
  // ============================================

  /**
   * Get from cache or fetch
   */
  async getCachedOrFetch(key, fetchFn) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }

    const data = await fetchFn();
    this.cache.set(key, { data, timestamp: Date.now() });
    return data;
  }

  /**
   * Clear cache
   */
  clearCache() {
    this.cache.clear();
  }

  // ============================================
  // MAIN API METHODS
  // ============================================

  /**
   * Get tariff information for HS code
   * @param {string} hsCode - The HS code to look up
   * @returns {Promise<TariffInfo>} Tariff information
   */
  async getTariffInfo(hsCode) {
    const cacheKey = `tariff_${hsCode}`;
    
    return this.getCachedOrFetch(cacheKey, async () => {
      const fn = httpsCallable(this.functions, 'librarian_getTariffInfo');
      const result = await fn({ hsCode });
      return result.data;
    });
  }

  /**
   * Get licensing requirements for HS code
   * @param {string} hsCode - The HS code to look up
   * @param {'import'|'export'} tradeDirection - Trade direction
   * @returns {Promise<LicensingRequirements>} Licensing requirements
   */
  async getLicensingRequirements(hsCode, tradeDirection = 'import') {
    const cacheKey = `licensing_${hsCode}_${tradeDirection}`;
    
    return this.getCachedOrFetch(cacheKey, async () => {
      const fn = httpsCallable(this.functions, 'librarian_getLicensingRequirements');
      const result = await fn({ hsCode, tradeDirection });
      return result.data;
    });
  }

  /**
   * Check if code is "אחרי" (Other)
   * @param {string} hsCode - The HS code to check
   * @returns {Promise<OtherCodeCheck>} Check result with alternatives
   */
  async checkIfOtherCode(hsCode) {
    const cacheKey = `other_${hsCode}`;
    
    return this.getCachedOrFetch(cacheKey, async () => {
      const fn = httpsCallable(this.functions, 'librarian_checkOtherCode');
      const result = await fn({ hsCode });
      return result.data;
    });
  }

  /**
   * Get all documents for HS code
   * @param {string} hsCode - The HS code to look up
   * @returns {Promise<DocumentsForHSCode>} All related documents
   */
  async getDocumentsForHSCode(hsCode) {
    const cacheKey = `docs_${hsCode}`;
    
    return this.getCachedOrFetch(cacheKey, async () => {
      const fn = httpsCallable(this.functions, 'librarian_getDocumentsForHSCode');
      const result = await fn({ hsCode });
      return result.data;
    });
  }

  /**
   * Search library
   * @param {string} query - Search query
   * @param {SearchOptions} options - Search options
   * @returns {Promise<SearchResults>} Search results
   */
  async searchLibrary(query, options = {}) {
    const fn = httpsCallable(this.functions, 'librarian_searchLibrary');
    const result = await fn({ query, options });
    return result.data;
  }

  /**
   * Get document with PDF link
   * @param {string} catalogNumber - Document catalog number
   * @returns {Promise<Document>} Full document data
   */
  async getDocument(catalogNumber) {
    const cacheKey = `doc_${catalogNumber}`;
    
    return this.getCachedOrFetch(cacheKey, async () => {
      const fn = httpsCallable(this.functions, 'librarian_getDocument');
      const result = await fn({ catalogNumber });
      return result.data;
    });
  }

  /**
   * Handle user query (AI-powered)
   * @param {string} query - User's question
   * @param {Array} conversationHistory - Previous conversation
   * @returns {Promise<QueryResponse>} AI response
   */
  async handleUserQuery(query, conversationHistory = []) {
    const fn = httpsCallable(this.functions, 'librarian_handleUserQuery');
    const result = await fn({ query, conversationHistory });
    return result.data;
  }

  // ============================================
  // CONVENIENCE METHODS
  // ============================================

  /**
   * Get complete info for HS code (all in one call)
   * @param {string} hsCode - The HS code
   * @returns {Promise<CompleteHSCodeInfo>} All information
   */
  async getCompleteHSCodeInfo(hsCode) {
    const [tariff, licensingImport, licensingExport, otherCheck, documents] = await Promise.all([
      this.getTariffInfo(hsCode),
      this.getLicensingRequirements(hsCode, 'import'),
      this.getLicensingRequirements(hsCode, 'export'),
      this.checkIfOtherCode(hsCode),
      this.getDocumentsForHSCode(hsCode),
    ]);

    return {
      hsCode,
      tariff,
      licensing: {
        import: licensingImport,
        export: licensingExport,
      },
      isOther: otherCheck.isOther,
      otherCodeDetails: otherCheck,
      documents,
      summary: this.generateSummary(tariff, licensingImport, otherCheck),
    };
  }

  /**
   * Generate human-readable summary
   */
  generateSummary(tariff, licensing, otherCheck) {
    const lines = [];

    // Code description
    if (tariff.national) {
      lines.push(`קוד: ${tariff.hsCode}`);
      lines.push(`תיאור: ${tariff.national.titleHe}`);
    } else if (tariff.subheading) {
      lines.push(`קוד: ${tariff.hsCode}`);
      lines.push(`תיאור: ${tariff.subheading.titleHe}`);
    }

    // Duty rates
    if (tariff.dutyRates) {
      const rates = [];
      if (tariff.dutyRates.duty) rates.push(`מכס: ${tariff.dutyRates.duty}`);
      if (tariff.dutyRates.purchaseTax) rates.push(`מס קנייה: ${tariff.dutyRates.purchaseTax}`);
      if (tariff.dutyRates.vat) rates.push(`מע"מ: ${tariff.dutyRates.vat}`);
      if (rates.length > 0) {
        lines.push(`שיעורי מס: ${rates.join(', ')}`);
      }
    }

    // Other code warning
    if (otherCheck.isOther) {
      lines.push(`⚠️ אזהרה: ${otherCheck.warning}`);
      if (otherCheck.specificAlternatives?.length > 0) {
        lines.push(`קודים חלופיים אפשריים: ${otherCheck.specificAlternatives.length}`);
      }
    }

    // Licensing requirements
    if (licensing.summary.requiresLicense) {
      lines.push(`📋 נדרש רישיון/אישור`);
      licensing.summary.requiredApprovals.forEach(approval => {
        lines.push(`  - ${approval.ministry}: ${approval.description}`);
      });
    }

    return lines.join('\n');
  }

  /**
   * Quick search by HS code prefix
   * @param {string} prefix - HS code prefix (2-4 digits)
   * @returns {Promise<Array>} Matching codes
   */
  async searchByHSCodePrefix(prefix) {
    const cleanPrefix = prefix.replace(/\D/g, '');
    
    if (cleanPrefix.length < 2) {
      throw new Error('Prefix must be at least 2 digits');
    }

    const chapter = cleanPrefix.substring(0, 2);
    const collectionRef = collection(this.db, 'library_import_tariff');
    
    const q = query(
      collectionRef,
      where('chapterNumber', '==', chapter),
      limit(50)
    );

    const snapshot = await getDocs(q);
    const results = [];

    snapshot.forEach(doc => {
      const data = doc.data();
      const code = data.nationalCode || data.subheadingCode || data.headingCode;
      
      if (code && code.startsWith(cleanPrefix)) {
        results.push({
          catalogNumber: doc.id,
          code,
          titleHe: data.titleHe,
          titleEn: data.titleEn,
          isOther: data.isOther || false,
        });
      }
    });

    return results.sort((a, b) => a.code.localeCompare(b.code));
  }

  /**
   * Get chapter overview
   * @param {string} chapterNumber - Chapter number (2 digits)
   * @returns {Promise<ChapterOverview>} Chapter information
   */
  async getChapterOverview(chapterNumber) {
    const chapter = chapterNumber.padStart(2, '0');
    const catalogNumber = `IMP-TAR-CH${chapter}`;
    
    const docRef = doc(this.db, 'library_import_tariff', catalogNumber);
    const docSnap = await getDoc(docRef);

    if (!docSnap.exists()) {
      throw new Error(`Chapter ${chapter} not found`);
    }

    const data = docSnap.data();

    // Get headings in this chapter
    const headingsQuery = query(
      collection(this.db, 'library_import_tariff'),
      where('chapterNumber', '==', chapter),
      where('level', '==', 'heading'),
      limit(100)
    );

    const headingsSnap = await getDocs(headingsQuery);
    const headings = [];

    headingsSnap.forEach(doc => {
      const hData = doc.data();
      headings.push({
        catalogNumber: doc.id,
        code: hData.headingCode,
        titleHe: hData.titleHe,
        titleEn: hData.titleEn,
      });
    });

    return {
      catalogNumber,
      chapterNumber: chapter,
      titleHe: data.titleHe,
      titleEn: data.titleEn,
      notes: data.notes || [],
      legalNotes: data.legalNotes || [],
      headings: headings.sort((a, b) => a.code.localeCompare(b.code)),
    };
  }
}

// ============================================
// TYPE DEFINITIONS (JSDoc)
// ============================================

/**
 * @typedef {Object} TariffInfo
 * @property {string} hsCode
 * @property {Object} chapter
 * @property {Object} heading
 * @property {Object} subheading
 * @property {Object} national
 * @property {Array} notes
 * @property {Object} dutyRates
 * @property {boolean} isOther
 * @property {Array} relatedCodes
 */

/**
 * @typedef {Object} LicensingRequirements
 * @property {string} hsCode
 * @property {string} tradeDirection
 * @property {Array} freeOrder
 * @property {Array} governmentRegs
 * @property {Array} standards
 * @property {Array} ministries
 * @property {Object} summary
 */

/**
 * @typedef {Object} OtherCodeCheck
 * @property {boolean} isOther
 * @property {boolean} found
 * @property {string} code
 * @property {string} title
 * @property {string} catalogNumber
 * @property {Array} specificAlternatives
 * @property {string} warning
 * @property {string} recommendation
 */

/**
 * @typedef {Object} SearchOptions
 * @property {string} category - all, tariff, freeImport, freeExport, govRegs, standards
 * @property {number} limit
 * @property {boolean} useIndex
 */

/**
 * @typedef {Object} SearchResults
 * @property {string} query
 * @property {Array} results
 * @property {number} totalFound
 * @property {Object} categories
 */

// ============================================
// SINGLETON INSTANCE
// ============================================

let librarianInstance = null;

/**
 * Get Librarian client singleton
 * @param {Object} firebaseApp - Firebase app instance
 * @returns {LibrarianClient}
 */
export function getLibrarian(firebaseApp = null) {
  if (!librarianInstance) {
    librarianInstance = new LibrarianClient(firebaseApp);
  }
  return librarianInstance;
}

// ============================================
// REACT HOOKS (Optional)
// ============================================

/**
 * React hook for tariff info
 * Usage: const { data, loading, error } = useTariffInfo('8536907000');
 */
export function useTariffInfo(hsCode) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    if (!hsCode) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState(prev => ({ ...prev, loading: true }));

    getLibrarian()
      .getTariffInfo(hsCode)
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [hsCode]);

  return state;
}

/**
 * React hook for licensing requirements
 */
export function useLicensingRequirements(hsCode, tradeDirection = 'import') {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    if (!hsCode) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState(prev => ({ ...prev, loading: true }));

    getLibrarian()
      .getLicensingRequirements(hsCode, tradeDirection)
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [hsCode, tradeDirection]);

  return state;
}

/**
 * React hook for complete HS code info
 */
export function useCompleteHSCodeInfo(hsCode) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    if (!hsCode) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState(prev => ({ ...prev, loading: true }));

    getLibrarian()
      .getCompleteHSCodeInfo(hsCode)
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [hsCode]);

  return state;
}

/**
 * React hook for library search
 */
export function useLibrarySearch(query, options = {}) {
  const [state, setState] = useState({ data: null, loading: false, error: null });

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState(prev => ({ ...prev, loading: true }));

    const timeoutId = setTimeout(() => {
      getLibrarian()
        .searchLibrary(query, options)
        .then(data => setState({ data, loading: false, error: null }))
        .catch(error => setState({ data: null, loading: false, error }));
    }, 300); // Debounce

    return () => clearTimeout(timeoutId);
  }, [query, JSON.stringify(options)]);

  return state;
}

// For CommonJS compatibility
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LibrarianClient, getLibrarian };
}

// Import useState and useEffect for React hooks
import { useState, useEffect } from 'react';

export default LibrarianClient;
