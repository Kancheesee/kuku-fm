import React from 'react';
import { PromoCandidate } from '../types';
import { Award, Clock, AlertTriangle, CheckCircle2, ChevronRight, Zap, Target, FileText } from 'lucide-react';

interface PromoCardProps {
  candidate: PromoCandidate;
  isSelected: boolean;
  onSelect: () => void;
}

export const PromoCard: React.FC<PromoCardProps> = ({
  candidate,
  isSelected,
  onSelect,
}) => {
  const { rank, editorial_title, segment, rubric, review_flags, mechanical_status } = candidate;
  const epNum = candidate.episode_number ?? segment.episode_number;
  const filename = candidate.filename || segment.filename;

  return (
    <div
      onClick={onSelect}
      className={`p-4 rounded-xl border transition-all cursor-pointer relative ${
        isSelected
          ? 'bg-paper-50 border-burnt-700 shadow-md ring-2 ring-burnt-700/20'
          : 'bg-paper-50/80 hover:bg-paper-50 border-paper-300 hover:border-charcoal-subtle shadow-xs'
      }`}
    >
      {/* Episode Origin Header - prioritizing Episode number and filename */}
      <div className="flex items-center justify-between text-[11px] text-charcoal-subtle mb-2 pb-2 border-b border-paper-200">
        <div className="flex items-center space-x-1.5 font-semibold text-charcoal">
          <FileText className="w-3.5 h-3.5 text-burnt-700 flex-shrink-0" />
          <span>{epNum !== null && epNum !== undefined ? `Episode ${epNum}` : 'Episode'}</span>
          <span className="text-charcoal-subtle font-normal font-mono truncate max-w-sm">• {filename}</span>
        </div>
      </div>

      {/* Header: Rank, Title, Score */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center space-x-2">
          <span className="w-6 h-6 rounded-full bg-burnt-700 text-white font-mono text-xs font-bold flex items-center justify-center flex-shrink-0 shadow-xs">
            #{rank}
          </span>
          <h3 className="text-sm font-bold text-charcoal tracking-tight font-serif">
            {editorial_title}
          </h3>
        </div>

        <div className="flex items-center space-x-1.5 flex-shrink-0">
          {rubric ? (
            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-bold bg-burnt-100 text-burnt-800 border border-burnt-200">
              <Award className="w-3 h-3 text-burnt-700" />
              <span>{rubric.overall_score.toFixed(1)} / 5.0</span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-900 border border-amber-200">
              <span>Assessment Unavailable</span>
            </span>
          )}
        </div>
      </div>

      {/* Timing Coordinates */}
      <div className="flex items-center space-x-3 text-xs text-charcoal-muted mb-3 font-mono">
        <span className="bg-paper-200 px-2 py-0.5 rounded border border-paper-300 text-charcoal font-semibold">
          {segment.start_timestamp} – {segment.end_timestamp}
        </span>
        <span className="flex items-center space-x-1 text-burnt-800 font-semibold">
          <Clock className="w-3.5 h-3.5" />
          <span>{segment.duration_seconds}s</span>
        </span>
        <span className="text-charcoal-subtle">
          ({segment.event_ids.length} events)
        </span>
      </div>

      {/* Opening Hook & Cliffhanger Summaries */}
      <div className="space-y-1.5 text-xs text-charcoal-muted mb-3">
        <div className="flex items-start space-x-1.5">
          <Zap className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${rubric && rubric.opening_strength <= 2 ? 'text-amber-600' : 'text-burnt-700'}`} />
          <div>
            <span className="font-semibold text-charcoal">
              Opening 3s Hook{rubric ? ` (${rubric.opening_strength}/5)` : ''}:{' '}
            </span>
            <span className="text-charcoal-muted">{candidate.hook_explanation}</span>
          </div>
        </div>

        <div className="flex items-start space-x-1.5">
          <Target className="w-3.5 h-3.5 text-indigo-700 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-charcoal">
              Cliffhanger Cut{rubric ? ` (${rubric.unresolved_ending}/5)` : ''}:{' '}
            </span>
            <span className="text-charcoal-muted">{candidate.cliffhanger_explanation}</span>
          </div>
        </div>
      </div>

      {/* Editorial Rationale */}
      {candidate.rationale && (
        <div className="mb-3 text-xs text-charcoal-muted">
          <span className="font-semibold text-charcoal">Editorial Rationale:{' '}</span>
          <span className="text-charcoal-muted">{candidate.rationale}</span>
        </div>
      )}

      {/* Unresolved Question */}
      <div className="p-2.5 bg-paper-200/70 rounded-md border border-paper-300 mb-3 text-xs text-charcoal">
        <span className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-0.5">
          Unresolved Question (Grounded in Footage)
        </span>
        <p className="italic text-charcoal font-serif">"{candidate.unresolved_question}"</p>
      </div>

      {/* Editorial Rubric Scores & Mechanical Status Footer */}
      <div className="pt-2.5 border-t border-paper-200 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center space-x-2 text-charcoal-muted">
          {rubric ? (
            <>
              <span>Hook: <b className={`font-mono ${rubric.opening_strength <= 2 ? 'text-amber-700' : 'text-charcoal'}`}>{rubric.opening_strength}</b></span>
              <span>•</span>
              <span>Clarity: <b className="font-mono text-charcoal">{rubric.standalone_clarity}</b></span>
              <span>•</span>
              <span>Stakes: <b className="font-mono text-charcoal">{rubric.escalation_stakes}</b></span>
              <span>•</span>
              <span>Cut: <b className="font-mono text-charcoal">{rubric.unresolved_ending}</b></span>
            </>
          ) : (
            <span className="text-amber-800 font-medium italic">Editorial assessment unavailable</span>
          )}
        </div>

        <div className="flex items-center space-x-1.5">
          {mechanical_status === 'passed' ? (
            <span className="inline-flex items-center space-x-1 text-emerald-700 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Verified Cut</span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1 text-amber-800 font-medium">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span>{review_flags.length} flag(s)</span>
            </span>
          )}
          <ChevronRight className="w-3.5 h-3.5 text-charcoal-subtle" />
        </div>
      </div>
    </div>
  );
};
