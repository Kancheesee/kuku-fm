import React from 'react';
import { Film, Sparkles, RefreshCw, AlertCircle, CheckCircle2, FileSpreadsheet, FileCode } from 'lucide-react';

interface HeaderProps {
  hasLoadedScripts: boolean;
  selectedEpisodeNumber?: number | null;
  onReset: () => void;
  isBackendConnected: boolean | null;
  onFindPromos: () => void;
  isAnalyzingPromos: boolean;
  hasPromoResults: boolean;
  onExportCsv: () => void;
  onExportJson: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  hasLoadedScripts,
  selectedEpisodeNumber,
  onReset,
  isBackendConnected,
  onFindPromos,
  isAnalyzingPromos,
  hasPromoResults,
  onExportCsv,
  onExportJson,
}) => {
  return (
    <header className="border-b border-paper-300 bg-paper-50 px-6 py-3 sticky top-0 z-30 flex items-center justify-between shadow-xs">
      <div className="flex items-center space-x-3.5">
        <div className="w-8 h-8 rounded bg-burnt-700 flex items-center justify-center text-white shadow-xs">
          <Film className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-semibold text-charcoal tracking-tight font-serif">
              Kuku Promo Studio
            </h1>
            <span className="text-[11px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-burnt-100 text-burnt-800 border border-burnt-200">
              Milestone 2: Gemini Promo Engine
            </span>
          </div>
          <p className="text-xs text-charcoal-subtle">Editorial Screenplay Ingestion & Continuous Promo Candidate Discovery</p>
        </div>
      </div>

      <div className="flex items-center space-x-2.5">
        {/* Backend health status indicator */}
        <div className="hidden sm:flex items-center space-x-1.5 text-xs text-charcoal-muted px-2.5 py-1.5 rounded bg-paper-200 border border-paper-300">
          {isBackendConnected === true && (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Backend Ready</span>
            </>
          )}
          {isBackendConnected === false && (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              <span>Backend Offline</span>
            </>
          )}
          {isBackendConnected === null && (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-charcoal-subtle" />
              <span>Connecting...</span>
            </>
          )}
        </div>

        {hasLoadedScripts && (
          <button
            onClick={onReset}
            className="text-xs font-medium text-charcoal-muted hover:text-charcoal px-3 py-1.5 rounded border border-paper-300 hover:bg-paper-200 transition-colors focus:outline-none focus:ring-2 focus:ring-burnt-600"
          >
            New Batch
          </button>
        )}

        {/* Export Buttons when results available */}
        {hasPromoResults && (
          <div className="flex items-center space-x-1.5">
            <button
              onClick={onExportCsv}
              className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded text-xs font-medium bg-paper-200 hover:bg-paper-300 text-charcoal border border-paper-300 transition-colors"
              title="Export validated candidate shortlist to CSV"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-700" />
              <span>CSV Shortlist</span>
            </button>
            <button
              onClick={onExportJson}
              className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded text-xs font-medium bg-paper-200 hover:bg-paper-300 text-charcoal border border-paper-300 transition-colors"
              title="Export complete raw audit bundle to JSON"
            >
              <FileCode className="w-3.5 h-3.5 text-burnt-700" />
              <span>Raw Audit (JSON)</span>
            </button>
          </div>
        )}

        {/* Primary Find Promos Action Button */}
        {hasLoadedScripts && (
          <button
            onClick={onFindPromos}
            disabled={isAnalyzingPromos}
            className={`inline-flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all shadow-xs focus:outline-none focus:ring-2 focus:ring-burnt-600 focus:ring-offset-1 ${
              isAnalyzingPromos
                ? 'bg-paper-300 text-charcoal-muted cursor-wait border border-paper-400'
                : 'bg-burnt-700 hover:bg-burnt-800 text-white active:scale-[0.98]'
            }`}
          >
            {isAnalyzingPromos ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-burnt-700" />
                <span>Analyzing Ep {selectedEpisodeNumber ?? ''}...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-burnt-200" />
                <span>Find Promos (Ep {selectedEpisodeNumber ?? ''})</span>
              </>
            )}
          </button>
        )}
      </div>
    </header>
  );
};
