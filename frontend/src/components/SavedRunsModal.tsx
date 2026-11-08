import React, { useState, useEffect } from 'react';
import { RunSummary } from '../types';
import { listSavedRuns } from '../lib/api';
import { Database, X, Clock, Film, CheckCircle2, AlertCircle, RefreshCw, ChevronRight } from 'lucide-react';

interface SavedRunsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectRun: (runId: string) => void;
  currentRunId?: string | null;
}

export const SavedRunsModal: React.FC<SavedRunsModalProps> = ({
  isOpen,
  onClose,
  onSelectRun,
  currentRunId,
}) => {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listSavedRuns();
      setRuns(data);
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
      else setError('Failed to load saved runs from database.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchRuns();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/40 backdrop-blur-xs p-4">
      <div className="bg-paper-50 rounded-xl border border-paper-300 shadow-xl max-w-xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-paper-300 flex items-center justify-between bg-paper-100">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded bg-burnt-100 text-burnt-800">
              <Database className="w-4 h-4 text-burnt-700" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-charcoal font-serif">Saved Ingestion Runs</h3>
              <p className="text-[11px] text-charcoal-subtle">Persisted in Neon PostgreSQL database</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-charcoal-muted hover:text-charcoal hover:bg-paper-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Runs List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {isLoading && (
            <div className="py-12 text-center text-xs text-charcoal-subtle flex items-center justify-center space-x-2">
              <RefreshCw className="w-4 h-4 animate-spin text-burnt-700" />
              <span>Fetching runs from Neon...</span>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!isLoading && !error && runs.length === 0 && (
            <div className="py-12 text-center text-xs text-charcoal-subtle">
              No saved runs found in database. Ingest scripts and click "Save Run" to persist them.
            </div>
          )}

          {!isLoading &&
            runs.map((r) => {
              const isCurrent = r.id === currentRunId;
              return (
                <div
                  key={r.id}
                  onClick={() => {
                    onSelectRun(r.id);
                    onClose();
                  }}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between group ${
                    isCurrent
                      ? 'bg-burnt-50/70 border-burnt-600 ring-1 ring-burnt-600/30'
                      : 'bg-paper-50 hover:bg-paper-100 border-paper-300 hover:border-charcoal-subtle'
                  }`}
                >
                  <div className="space-y-1 pr-3">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-charcoal font-serif group-hover:text-burnt-800 transition-colors">
                        {r.name}
                      </span>
                      <span
                        className={`text-[10px] font-semibold uppercase px-1.5 py-0.2 rounded ${
                          r.status === 'completed'
                            ? 'bg-emerald-100 text-emerald-800'
                            : r.status === 'running'
                            ? 'bg-blue-100 text-blue-800 animate-pulse'
                            : r.status === 'paused'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-paper-200 text-charcoal-muted'
                        }`}
                      >
                        {r.status}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 text-[11px] text-charcoal-muted">
                      <span className="flex items-center space-x-1">
                        <Film className="w-3 h-3 text-charcoal-subtle" />
                        <span>
                          {r.completed_episodes}/{r.total_episodes} episodes
                        </span>
                      </span>
                      {r.promos_count > 0 && (
                        <span className="flex items-center space-x-1 text-burnt-800 font-medium">
                          <CheckCircle2 className="w-3 h-3 text-burnt-700" />
                          <span>{r.promos_count} promos found</span>
                        </span>
                      )}
                      <span className="flex items-center space-x-1 font-mono text-[10px] text-charcoal-subtle">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(r.created_at).toLocaleDateString()}</span>
                      </span>
                    </div>
                  </div>

                  <ChevronRight className="w-4 h-4 text-charcoal-subtle group-hover:text-charcoal transition-colors flex-shrink-0" />
                </div>
              );
            })}
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-paper-300 bg-paper-100 flex justify-between items-center text-xs">
          <button
            onClick={fetchRuns}
            className="inline-flex items-center space-x-1 text-charcoal-muted hover:text-charcoal px-2 py-1 rounded hover:bg-paper-200"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs font-semibold bg-paper-200 hover:bg-paper-300 text-charcoal"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

