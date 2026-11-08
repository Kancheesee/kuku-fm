import React from 'react';
import { Film, Sparkles, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';

interface HeaderProps {
  hasLoadedScripts: boolean;
  onReset: () => void;
  isBackendConnected: boolean | null;
}

export const Header: React.FC<HeaderProps> = ({
  hasLoadedScripts,
  onReset,
  isBackendConnected,
}) => {
  return (
    <header className="border-b border-paper-300 bg-paper-50 px-6 py-3.5 sticky top-0 z-30 flex items-center justify-between shadow-sm">
      <div className="flex items-center space-x-3.5">
        <div className="w-8 h-8 rounded bg-burnt-700 flex items-center justify-center text-white shadow-sm">
          <Film className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-semibold text-charcoal tracking-tight">
              Kuku Promo Studio
            </h1>
            <span className="text-[11px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-paper-200 text-charcoal-muted border border-paper-300">
              Inspection Milestone
            </span>
          </div>
          <p className="text-xs text-charcoal-subtle">Editorial Screenplay Ingestion & Timeline Inspector</p>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        {/* Backend health status indicator */}
        <div className="hidden sm:flex items-center space-x-1.5 text-xs text-charcoal-muted px-2.5 py-1 rounded bg-paper-200 border border-paper-300">
          {isBackendConnected === true && (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Backend Ready (FastAPI)</span>
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
            className="text-xs font-medium text-charcoal-muted hover:text-charcoal px-3 py-1.5 rounded border border-paper-300 hover:bg-paper-200 transition-colors focus:outline-none focus:ring-2 focus:ring-burnt-600 focus:ring-offset-1"
          >
            Upload New Batch
          </button>
        )}

        {/* Disabled future AI promo generation action */}
        <div className="relative group">
          <button
            disabled
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded text-xs font-medium bg-paper-300 text-charcoal-subtle cursor-not-allowed opacity-75 border border-paper-400"
            title="AI promo candidate generation is disabled for Milestone 1"
          >
            <Sparkles className="w-3.5 h-3.5 text-burnt-600" />
            <span>Find Promos</span>
          </button>
          <div className="absolute right-0 top-full mt-1.5 hidden group-hover:block z-50 w-56 p-2 text-[11px] bg-charcoal text-paper-100 rounded shadow-lg border border-charcoal-muted leading-tight">
            AI promo generation is disconnected in Milestone 1 (Script ingestion & inspection contract).
          </div>
        </div>
      </div>
    </header>
  );
};

