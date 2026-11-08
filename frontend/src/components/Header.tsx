import React from 'react';
import {
  Film,
  Sparkles,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  FileSpreadsheet,
  FileCode,
  Database,
  Play,
  Pause,
  Save,
} from 'lucide-react';

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
  // Milestone 3 Persistence Props
  currentRunName?: string | null;
  currentRunStatus?: string | null;
  hasSavedRun?: boolean;
  onOpenSavedRuns: () => void;
  onSaveRun?: () => void;
  isSavingRun?: boolean;
  onAnalyzeAll?: () => void;
  isBatchRunning?: boolean;
  onPauseRun?: () => void;
  onResumeRun?: () => void;
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
  currentRunName,
  currentRunStatus,
  hasSavedRun,
  onOpenSavedRuns,
  onSaveRun,
  isSavingRun,
  onAnalyzeAll,
  isBatchRunning,
  onPauseRun,
  onResumeRun,
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
              Milestone 3: Resumable Persistence
            </span>
          </div>
          <p className="text-xs text-charcoal-subtle">
            {currentRunName ? (
              <span className="flex items-center space-x-1.5 text-burnt-800 font-medium">
                <span>Active Run: {currentRunName}</span>
                {currentRunStatus && (
                  <span className="text-[10px] uppercase font-bold px-1.5 py-0.2 rounded bg-paper-200 text-charcoal">
                    {currentRunStatus}
                  </span>
                )}
              </span>
            ) : (
              'Screenplay Ingestion, Continuous Promo Candidate Discovery & Neon DB Persistence'
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-2.5">
        {/* Saved Runs Button */}
        <button
          onClick={onOpenSavedRuns}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-paper-200 hover:bg-paper-300 text-charcoal border border-paper-300 transition-colors shadow-xs"
          title="Browse saved runs in Neon database"
        >
          <Database className="w-3.5 h-3.5 text-burnt-700" />
          <span>Saved Runs</span>
        </button>

        {/* Save Run Button if scripts loaded but not yet persisted */}
        {hasLoadedScripts && !hasSavedRun && onSaveRun && (
          <button
            onClick={onSaveRun}
            disabled={isSavingRun}
            className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-burnt-50 hover:bg-burnt-100 text-burnt-800 border border-burnt-300 transition-colors shadow-xs"
            title="Persist this screenplay run to Neon database"
          >
            {isSavingRun ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-burnt-700" />
            ) : (
              <Save className="w-3.5 h-3.5 text-burnt-700" />
            )}
            <span>Save Run</span>
          </button>
        )}

        {/* Backend health status indicator */}
        <div className="hidden sm:flex items-center space-x-1.5 text-xs text-charcoal-muted px-2.5 py-1.5 rounded bg-paper-200 border border-paper-300">
          {isBackendConnected === true && (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Neon DB Ready</span>
            </>
          )}
          {isBackendConnected === false && (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              <span>Offline</span>
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

        {/* Batch Analyze All / Pause / Resume Controls for saved runs */}
        {hasSavedRun && onAnalyzeAll && (
          <div className="flex items-center space-x-1.5">
            {isBatchRunning ? (
              <button
                onClick={onPauseRun}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300 hover:bg-amber-200 transition-all shadow-xs"
              >
                <Pause className="w-3.5 h-3.5 text-amber-700" />
                <span>Pause Batch</span>
              </button>
            ) : currentRunStatus === 'paused' ? (
              <button
                onClick={onResumeRun}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-700 text-white hover:bg-emerald-800 transition-all shadow-xs"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Resume Batch</span>
              </button>
            ) : (
              <button
                onClick={onAnalyzeAll}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-burnt-700 text-white hover:bg-burnt-800 transition-all shadow-xs"
              >
                <Play className="w-3.5 h-3.5 text-burnt-200" />
                <span>Analyze All</span>
              </button>
            )}
          </div>
        )}

        {/* Primary Find Promos Action Button (Single Episode) */}
        {hasLoadedScripts && !isBatchRunning && (
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
                <span>
                  Analyzing Ep {selectedEpisodeNumber !== null && selectedEpisodeNumber !== undefined ? selectedEpisodeNumber : ''}...
                </span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-burnt-200" />
                <span>
                  Find Promos
                  {selectedEpisodeNumber !== null && selectedEpisodeNumber !== undefined
                    ? ` (Ep ${selectedEpisodeNumber})`
                    : ''}
                </span>
              </>
            )}
          </button>
        )}
      </div>
    </header>
  );
};
