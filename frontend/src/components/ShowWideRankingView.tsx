import React from 'react';
import { PromoCandidate } from '../types';
import { PromoCard } from './PromoCard';
import { Trophy, FileSpreadsheet, FileCode, Clock } from 'lucide-react';

interface ShowWideRankingViewProps {
  runName: string;
  candidates: PromoCandidate[];
  selectedCandidateId: string | null;
  onSelectCandidate: (candidate: PromoCandidate) => void;
  onExportCsv: () => void;
  onExportJson: () => void;
  isProvisional?: boolean;
  completedEpisodes?: number;
  totalEpisodes?: number;
  coveragePercentage?: number;
}

export const ShowWideRankingView: React.FC<ShowWideRankingViewProps> = ({
  runName,
  candidates,
  selectedCandidateId,
  onSelectCandidate,
  onExportCsv,
  onExportJson,
  isProvisional = false,
  completedEpisodes = 0,
  totalEpisodes = 0,
  coveragePercentage = 0,
}) => {
  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-101px)] bg-paper-100 overflow-hidden">
      {/* Top Header Summary */}
      <div className="p-4 border-b border-paper-300 bg-paper-50 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded bg-amber-100 text-amber-800">
            <Trophy className="w-5 h-5 text-amber-700" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-charcoal font-serif tracking-tight">
                Show-Wide Top Promos: {runName}
              </h2>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-burnt-100 text-burnt-800 border border-burnt-200">
                {candidates.length} Scored Candidate{candidates.length === 1 ? '' : 's'}
              </span>
              {isProvisional && (
                <span className="inline-flex items-center space-x-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300">
                  <Clock className="w-3 h-3 text-amber-700" />
                  <span>Provisional ({completedEpisodes}/{totalEpisodes} episodes • {coveragePercentage}%)</span>
                </span>
              )}
            </div>
            <p className="text-[11px] text-charcoal-subtle">
              {isProvisional
                ? `Provisional ranking across ${completedEpisodes} of ${totalEpisodes} completed episodes. Remaining episodes are pending analysis.`
                : `Complete show ranking evaluated across all ${totalEpisodes} episodes by weighted editorial score.`}
            </p>
          </div>
        </div>

        {/* Export Buttons */}
        {candidates.length > 0 && (
          <div className="flex items-center space-x-2">
            <button
              onClick={onExportCsv}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-paper-200 hover:bg-paper-300 text-charcoal border border-paper-300 transition-colors shadow-xs"
              title="Export all show-wide candidates to CSV"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-700" />
              <span>Export CSV</span>
            </button>
            <button
              onClick={onExportJson}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-paper-200 hover:bg-paper-300 text-charcoal border border-paper-300 transition-colors shadow-xs"
              title="Export full run audit to JSON"
            >
              <FileCode className="w-3.5 h-3.5 text-burnt-700" />
              <span>Export Audit JSON</span>
            </button>
          </div>
        )}
      </div>

      {/* Main Content List */}
      <div className="flex-1 overflow-y-auto p-5">
        {candidates.length === 0 ? (
          <div className="py-16 text-center text-xs text-charcoal-subtle max-w-sm mx-auto space-y-2">
            <Trophy className="w-8 h-8 mx-auto text-charcoal-subtle opacity-40" />
            <p className="font-semibold text-charcoal">No scored promo candidates found yet.</p>
            <p>Analyze episodes to discover and rank promo candidates across the show.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-7xl mx-auto">
            {candidates.map((candidate) => (
              <PromoCard
                key={candidate.id}
                candidate={candidate}
                isSelected={candidate.id === selectedCandidateId}
                onSelect={() => onSelectCandidate(candidate)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
