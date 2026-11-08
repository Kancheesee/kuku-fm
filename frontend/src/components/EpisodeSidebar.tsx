import React, { useState } from 'react';
import { Episode } from '../types';
import { formatDurationHuman } from '../lib/utils';
import { Search, AlertTriangle, FileText } from 'lucide-react';

interface EpisodeSidebarProps {
  episodes: Episode[];
  selectedEpisodeId: string | null;
  onSelectEpisode: (id: string) => void;
}

export const EpisodeSidebar: React.FC<EpisodeSidebarProps> = ({
  episodes,
  selectedEpisodeId,
  onSelectEpisode,
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

            return (
              <button
                key={ep.id}
                onClick={() => onSelectEpisode(ep.id)}
                className={`w-full text-left p-3.5 transition-colors flex flex-col gap-1 focus:outline-none focus:ring-1 focus:ring-burnt-600 ${
                  isSelected
                    ? 'bg-burnt-50/70 border-l-4 border-burnt-700 pl-[10px]'
                    : 'hover:bg-paper-200/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-semibold ${isSelected ? 'text-burnt-800' : 'text-charcoal'}`}>
                    {ep.episode_number !== null ? `Episode ${ep.episode_number}` : 'Untitled Episode'}
                  </span>
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

                <div className="flex items-center space-x-1 text-[11px] text-charcoal-subtle truncate">
                  <FileText className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate">{ep.filename}</span>
                </div>

                <div className="flex items-center justify-between text-[10px] text-charcoal-muted mt-0.5">
                  <span>{ep.scenes.length} scene{ep.scenes.length === 1 ? '' : 's'}</span>
                  <span>{ep.events.length} timed events</span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Episode count footer */}
      <div className="p-2.5 border-t border-paper-300 bg-paper-100 text-[11px] text-charcoal-subtle flex justify-between items-center">
        <span>{filteredEpisodes.length} shown</span>
        <span>{episodes.length} total</span>
      </div>
    </aside>
  );
};

