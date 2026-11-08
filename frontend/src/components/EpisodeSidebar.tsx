import React, { useState } from 'react';
import { Episode } from '../types';
import { formatDurationHuman } from '../lib/utils';
import { Search, AlertTriangle, FileText, CheckCircle2, RefreshCw, AlertCircle, RotateCcw } from 'lucide-react';

export interface EpisodeStatusInfo {
  status: 'pending' | 'analyzing' | 'completed' | 'failed' | 'paused';
  retry_count?: number;
  error?: string | null;
}

interface EpisodeSidebarProps {
  episodes: Episode[];
  selectedEpisodeId: string | null;
  onSelectEpisode: (id: string) => void;
  episodeStatuses?: Record<string, EpisodeStatusInfo>;
  onRetryEpisode?: (episodeId: string) => void;
}

export const EpisodeSidebar: React.FC<EpisodeSidebarProps> = ({
  episodes,
  selectedEpisodeId,
  onSelectEpisode,
  episodeStatuses,
  onRetryEpisode,
}) => {
  const [filterText, setFilterText] = useState('');

  const filteredEpisodes = episodes.filter((ep) => {
    const term = filterText.toLowerCase();
    const epNumMatch = ep.episode_number ? `episode ${ep.episode_number}`.includes(term) : false;
    const filenameMatch = ep.filename.toLowerCase().includes(term);
    const loglineMatch = ep.logline ? ep.logline.toLowerCase().includes(term) : false;
    return epNumMatch || filenameMatch || loglineMatch;
  });

  return (
    <aside className="w-72 lg:w-80 flex-shrink-0 border-r border-paper-300 bg-paper-50 flex flex-col h-[calc(100vh-101px)]">
      {/* Sidebar search bar */}
      <div className="p-3 border-b border-paper-300">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-charcoal-subtle absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Search episodes..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-paper-200 border border-paper-300 rounded focus:outline-none focus:ring-1 focus:ring-burnt-600 focus:bg-paper-50 transition-colors"
          />
        </div>
      </div>

      {/* Episode list */}
      <div className="flex-1 overflow-y-auto divide-y divide-paper-200">
        {filteredEpisodes.length === 0 ? (
          <div className="p-6 text-center text-xs text-charcoal-subtle">
            No episodes matching "{filterText}"
          </div>
        ) : (
          filteredEpisodes.map((ep) => {
            const isSelected = ep.id === selectedEpisodeId;
            const issueCount = ep.warnings.length;
            const statusInfo = episodeStatuses ? episodeStatuses[ep.id] : undefined;

            return (
              <div
                key={ep.id}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectEpisode(ep.id);
                  }
                }}
                onClick={() => onSelectEpisode(ep.id)}
                className={`w-full text-left p-3.5 transition-colors flex flex-col gap-1 cursor-pointer focus:outline-none focus:ring-1 focus:ring-burnt-600 ${
                  isSelected
                    ? 'bg-burnt-50/70 border-l-4 border-burnt-700 pl-[10px]'
                    : 'hover:bg-paper-200/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <span className={`text-xs font-semibold ${isSelected ? 'text-burnt-800' : 'text-charcoal'}`}>
                      {ep.episode_number !== null ? `Episode ${ep.episode_number}` : 'Untitled Episode'}
                    </span>
                    {/* Status badge */}
                    {statusInfo && statusInfo.status === 'completed' && (
                      <span title="Analysis completed and saved" className="flex items-center">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                      </span>
                    )}
                    {statusInfo && statusInfo.status === 'analyzing' && (
                      <span title="Analyzing promos..." className="flex items-center">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-burnt-700 flex-shrink-0" />
                      </span>
                    )}
                    {statusInfo && statusInfo.status === 'failed' && (
                      <span title={statusInfo.error || 'Analysis failed'} className="flex items-center">
                        <AlertCircle className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-1.5">
                    {issueCount > 0 && (
                      <span
                        className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200"
                        title={`${issueCount} parsing warning(s)`}
                      >
                        <AlertTriangle className="w-2.5 h-2.5" />
                        <span>{issueCount}</span>
                      </span>
                    )}
                    <span className="text-[11px] font-mono text-charcoal-muted">
                      {formatDurationHuman(ep.duration_ms)}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-charcoal-subtle">
                  <div className="flex items-center space-x-1 truncate max-w-[170px]">
                    <FileText className="w-3 h-3 flex-shrink-0" />
                    <span className="truncate">{ep.filename}</span>
                  </div>

                  {statusInfo && statusInfo.status === 'failed' && onRetryEpisode && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRetryEpisode(ep.id);
                      }}
                      className="inline-flex items-center space-x-0.5 text-[10px] font-semibold text-rose-700 hover:text-rose-900 bg-rose-100 px-1.5 py-0.5 rounded border border-rose-200 transition-colors"
                      title="Retry analysis for this episode"
                    >
                      <RotateCcw className="w-2.5 h-2.5" />
                      <span>Retry</span>
                    </button>
                  )}
                </div>

                <div className="flex items-center justify-between text-[10px] text-charcoal-muted mt-0.5">
                  <span>{ep.scenes.length} scene{ep.scenes.length === 1 ? '' : 's'}</span>
                  <span>{ep.events.length} timed events</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Episode count footer */}
      <div className="p-2.5 border-t border-paper-300 bg-paper-100 text-[11px] text-charcoal-subtle flex justify-between items-center">
        <span>{episodes.length} episodes total</span>
        <span>{filteredEpisodes.length} visible</span>
      </div>
    </aside>
  );
};
