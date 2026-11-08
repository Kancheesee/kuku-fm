import React from 'react';
import { Film, Clock, Activity, AlertTriangle, FileArchive } from 'lucide-react';
import { formatDurationHuman } from '../lib/utils';

interface SummaryBarProps {
  totalEpisodes: number;
  totalRuntimeMs: number;
  totalEvents: number;
  totalIssues: number;
  ignoredCount: number;
}

export const SummaryBar: React.FC<SummaryBarProps> = ({
  totalEpisodes,
  totalRuntimeMs,
  totalEvents,
  totalIssues,
  ignoredCount,
}) => {
  return (
    <div className="bg-paper-50 border-b border-paper-300 px-6 py-2.5 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 text-xs">
      <div className="flex items-center space-x-2.5">
        <div className="p-1.5 rounded bg-paper-200 text-charcoal">
          <Film className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-charcoal-subtle block text-[10px] uppercase font-semibold">Episodes</span>
          <span className="font-semibold text-charcoal">{totalEpisodes}</span>
        </div>
      </div>

      <div className="flex items-center space-x-2.5">
        <div className="p-1.5 rounded bg-paper-200 text-burnt-700">
          <Clock className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-charcoal-subtle block text-[10px] uppercase font-semibold">Total Runtime</span>
          <span className="font-semibold text-charcoal">{formatDurationHuman(totalRuntimeMs)}</span>
        </div>
      </div>

      <div className="flex items-center space-x-2.5">
        <div className="p-1.5 rounded bg-paper-200 text-charcoal">
          <Activity className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-charcoal-subtle block text-[10px] uppercase font-semibold">Timed Events</span>
          <span className="font-semibold text-charcoal">{totalEvents.toLocaleString()}</span>
        </div>
      </div>

      <div className="flex items-center space-x-2.5">
        <div className={`p-1.5 rounded ${totalIssues > 0 ? 'bg-amber-100 text-amber-800' : 'bg-paper-200 text-charcoal'}`}>
          <AlertTriangle className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-charcoal-subtle block text-[10px] uppercase font-semibold">Issues Detected</span>
          <span className={`font-semibold ${totalIssues > 0 ? 'text-amber-800' : 'text-charcoal'}`}>
            {totalIssues}
          </span>
        </div>
      </div>

      {ignoredCount > 0 && (
        <div className="hidden lg:flex items-center space-x-2.5">
          <div className="p-1.5 rounded bg-paper-200 text-charcoal-muted">
            <FileArchive className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="text-charcoal-subtle block text-[10px] uppercase font-semibold">Ignored (macOS/Non-Script)</span>
            <span className="font-semibold text-charcoal">{ignoredCount}</span>
          </div>
        </div>
      )}
    </div>
  );
};

