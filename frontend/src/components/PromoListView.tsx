import React, { useState } from 'react';
import { PromoAnalysisResponse, PromoCandidate } from '../types';
import { PromoCard } from './PromoCard';
import { Sparkles, AlertTriangle, ShieldAlert } from 'lucide-react';

interface PromoListViewProps {
  response: PromoAnalysisResponse;
  selectedCandidateId: string | null;
  onSelectCandidate: (candidate: PromoCandidate) => void;
}

export const PromoListView: React.FC<PromoListViewProps> = ({
  response,
  selectedCandidateId,
  onSelectCandidate,
}) => {
  const [activeTab, setActiveTab] = useState<'ranked' | 'rejected' | 'suppressed'>('ranked');

  const { candidates, rejected_proposals, suppressed_candidates, metadata } = response;

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-101px)] bg-paper-100 overflow-hidden">
      {/* Top Header Summary & Tabs */}
      <div className="p-4 border-b border-paper-300 bg-paper-50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded bg-burnt-100 text-burnt-800">
            <Sparkles className="w-4 h-4 text-burnt-700" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-charcoal font-serif tracking-tight">
                Promo Candidates: {response.episode_number !== null && response.episode_number !== undefined ? `Episode ${response.episode_number}` : 'Episode'}
              </h2>
              <span className="text-[11px] text-charcoal-subtle font-mono truncate max-w-xs">• {response.filename}</span>
            </div>
            <p className="text-[11px] text-charcoal-subtle">
              Model: <code className="font-mono">{response.model || metadata.model || 'Gemini'}</code> • Latency: {metadata.latency_ms}ms
              {response.cache_key && (
                <span className="hidden sm:inline" title={response.cache_key}> • Key: <code className="font-mono">{response.cache_key.slice(0, 16)}…</code></span>
              )}
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center space-x-1 bg-paper-200 p-1 rounded-lg border border-paper-300 text-xs">
          <button
            onClick={() => setActiveTab('ranked')}
            className={`px-3 py-1 rounded-md font-medium transition-colors ${
              activeTab === 'ranked'
                ? 'bg-paper-50 text-charcoal shadow-xs font-semibold'
                : 'text-charcoal-muted hover:text-charcoal'
            }`}
          >
            Ranked Shortlist ({candidates.length})
          </button>

          {rejected_proposals.length > 0 && (
            <button
              onClick={() => setActiveTab('rejected')}
              className={`px-3 py-1 rounded-md font-medium transition-colors ${
                activeTab === 'rejected'
                  ? 'bg-paper-50 text-charcoal shadow-xs font-semibold'
                  : 'text-charcoal-muted hover:text-charcoal'
              }`}
            >
              Rejected ({rejected_proposals.length})
            </button>
          )}

          {suppressed_candidates.length > 0 && (
            <button
              onClick={() => setActiveTab('suppressed')}
              className={`px-3 py-1 rounded-md font-medium transition-colors ${
                activeTab === 'suppressed'
                  ? 'bg-paper-50 text-charcoal shadow-xs font-semibold'
                  : 'text-charcoal-muted hover:text-charcoal'
              }`}
            >
              Suppressed ({suppressed_candidates.length})
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-5">
        {activeTab === 'ranked' && (
          <div className="space-y-4 max-w-4xl mx-auto">
            {candidates.length === 0 ? (
              <div className="py-16 text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-paper-200 flex items-center justify-center text-charcoal-subtle mb-3">
                  <AlertTriangle className="w-6 h-6 text-amber-600" />
                </div>
                <h3 className="text-sm font-bold text-charcoal mb-1">
                  No Valid Promo Candidates Found
                </h3>
                <p className="text-xs text-charcoal-muted max-w-md mx-auto leading-relaxed">
                  The model proposed {metadata.total_proposals_generated} segments, but none satisfied all strict editorial boundaries (20s–60s duration, unbroken dialogue cuts, and opening 3s hook). Inspect the "Rejected" tab for complete failure diagnostics.
                </p>
              </div>
            ) : (
              candidates.map((c) => (
                <PromoCard
                  key={c.id}
                  candidate={c}
                  isSelected={c.id === selectedCandidateId}
                  onSelect={() => onSelectCandidate(c)}
                />
              ))
            )}
          </div>
        )}

        {activeTab === 'rejected' && (
          <div className="space-y-3 max-w-4xl mx-auto">
            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 mb-4">
              <span className="font-semibold block mb-0.5">Mechanical Timeline Boundary Enforcement:</span>
              <span>
                These AI-generated proposals were rejected during deterministic code validation to protect video editing integrity (preventing mid-sentence cuts, out-of-bounds duration, or missing hooks).
              </span>
            </div>

            {rejected_proposals.map((rej, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-paper-50 border border-paper-300 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-bold text-charcoal font-serif">
                    {rej.proposal.editorial_title}
                  </h4>
                  <div className="flex items-center space-x-1 text-[11px] font-mono text-charcoal-muted">
                    <span>Events: {rej.proposal.start_event_id} → {rej.proposal.end_event_id}</span>
                  </div>
                </div>

                <div className="space-y-1 mb-3">
                  {rej.rejection_reasons.map((reason, rIdx) => (
                    <div key={rIdx} className="text-xs text-rose-800 flex items-start space-x-1.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-600 flex-shrink-0 mt-0.5" />
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>

                <div className="p-2.5 bg-paper-200/60 rounded text-[11px] text-charcoal-muted leading-relaxed">
                  <span className="font-semibold text-charcoal">Original Proposal Rationale: </span>
                  {rej.proposal.rationale}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'suppressed' && (
          <div className="space-y-3 max-w-4xl mx-auto">
            <div className="p-3 bg-paper-200 rounded-lg border border-paper-300 text-xs text-charcoal-muted mb-4">
              <span className="font-semibold text-charcoal block mb-0.5">Deduplication Suppression:</span>
              <span>
                These candidates are mechanically valid, but overlap heavily (IoU &gt; 60%) with a higher-scoring candidate. They are retained here for audit transparency.
              </span>
            </div>

            {suppressed_candidates.map((c) => (
              <PromoCard
                key={c.id}
                candidate={c}
                isSelected={c.id === selectedCandidateId}
                onSelect={() => onSelectCandidate(c)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
