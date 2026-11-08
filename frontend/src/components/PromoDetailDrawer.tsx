import React from 'react';
import { PromoCandidate } from '../types';
import { X, Award, Zap, Target, AlertTriangle, ShieldCheck, Film, FileText, HelpCircle } from 'lucide-react';

interface PromoDetailDrawerProps {
  candidate: PromoCandidate | null;
  onClose: () => void;
}

export const PromoDetailDrawer: React.FC<PromoDetailDrawerProps> = ({
  candidate,
  onClose,
}) => {
  if (!candidate) return null;

  const { rank, editorial_title, segment, rubric, review_flags } = candidate;
  const epNum = candidate.episode_number ?? segment.episode_number;
  const filename = candidate.filename || segment.filename;
  const hash = candidate.source_content_hash || segment.source_content_hash;

  return (
    <aside className="w-80 lg:w-96 flex-shrink-0 border-l border-paper-300 bg-paper-50 flex flex-col h-[calc(100vh-101px)] shadow-lg overflow-hidden">
      {/* Drawer Header */}
      <div className="p-4 border-b border-paper-300 flex items-center justify-between bg-paper-100">
        <div className="flex items-center space-x-2">
          <span className="w-5 h-5 rounded-full bg-burnt-700 text-white font-mono text-[11px] font-bold flex items-center justify-center">
            #{rank}
          </span>
          <span className="text-xs font-semibold text-charcoal uppercase tracking-wider">
            Candidate Review
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-paper-200 text-charcoal-muted hover:text-charcoal transition-colors focus:outline-none focus:ring-1 focus:ring-burnt-600"
          aria-label="Close promo inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Source Identity Badge */}
        <div className="p-2.5 bg-paper-200/80 rounded border border-paper-300 text-xs">
          <div className="flex items-center space-x-1.5 font-bold text-charcoal mb-0.5">
            <FileText className="w-3.5 h-3.5 text-burnt-700 flex-shrink-0" />
            <span>{epNum !== null && epNum !== undefined ? `Episode ${epNum}` : 'Episode'}</span>
            <span className="text-charcoal-subtle font-normal font-mono truncate">• {filename}</span>
          </div>
          {hash && (
            <div className="text-[10px] text-charcoal-subtle font-mono truncate">
              Content Hash: {hash}
            </div>
          )}
        </div>

        {/* Title and Overall Score */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle">
              Editorial Premise
            </span>
            {rubric ? (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-bold bg-burnt-100 text-burnt-800 border border-burnt-200">
                <Award className="w-3 h-3 text-burnt-700" />
                <span>{rubric.overall_score.toFixed(1)} / 5.0</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-200">
                <span>Assessment Unavailable</span>
              </span>
            )}
          </div>
          <h3 className="text-base font-bold text-charcoal font-serif tracking-tight">
            {editorial_title}
          </h3>
        </div>

        {/* Timeline Coordinates */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Segment Interval
          </label>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">Start</span>
              <span className="font-mono text-xs font-semibold text-charcoal">
                {segment.start_timestamp}
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{segment.start_ms}ms</span>
            </div>
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">End</span>
              <span className="font-mono text-xs font-semibold text-charcoal">
                {segment.end_timestamp}
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{segment.end_ms}ms</span>
            </div>
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">Duration</span>
              <span className="font-mono text-xs font-semibold text-burnt-800">
                {segment.duration_seconds}s
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{segment.event_ids.length} events</span>
            </div>
          </div>
        </div>

        {/* Hook Breakdown */}
        <div className="p-3 bg-paper-100 rounded-lg border border-paper-300">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-burnt-800">
              <Zap className="w-3.5 h-3.5 text-burnt-700" />
              <span>Opening 3-Second Hook</span>
            </div>
            {rubric && (
              <span className={`text-[11px] font-bold font-mono px-1.5 py-0.5 rounded ${rubric.opening_strength <= 2 ? 'bg-amber-100 text-amber-800' : 'bg-burnt-100 text-burnt-800'}`}>
                {rubric.opening_strength} / 5
              </span>
            )}
          </div>
          <p className="text-xs text-charcoal leading-relaxed mb-1.5">
            {candidate.hook_explanation}
          </p>
          {rubric?.opening_reason && (
            <p className="text-[11px] text-charcoal-muted mb-2 italic">
              Rubric rationale: {rubric.opening_reason}
            </p>
          )}
          <div className="text-[10px] text-charcoal-subtle font-mono">
            Supporting Events: {candidate.hook_event_ids.join(', ') || 'Auto-resolved'}
          </div>
        </div>

        {/* Cliffhanger Cut Breakdown */}
        <div className="p-3 bg-paper-100 rounded-lg border border-paper-300">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-indigo-900">
              <Target className="w-3.5 h-3.5 text-indigo-700" />
              <span>Unresolved Cliffhanger Ending</span>
            </div>
            {rubric && (
              <span className="text-[11px] font-bold font-mono px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
                {rubric.unresolved_ending} / 5
              </span>
            )}
          </div>
          <p className="text-xs text-charcoal leading-relaxed mb-2">
            {candidate.cliffhanger_explanation}
          </p>
          <div className="p-2 bg-paper-200/80 rounded border border-paper-300 text-xs text-charcoal mb-2">
            <span className="text-[10px] uppercase font-bold text-charcoal-subtle block mb-0.5">
              Unresolved Question (Grounded):
            </span>
            <p className="italic font-serif font-medium">"{candidate.unresolved_question}"</p>
          </div>
          {rubric?.ending_reason && (
            <p className="text-[11px] text-charcoal-muted mb-2 italic">
              Rubric rationale: {rubric.ending_reason}
            </p>
          )}
          <div className="text-[10px] text-charcoal-subtle font-mono">
            Cliffhanger Events: {candidate.cliffhanger_event_ids.join(', ') || 'Auto-resolved'}
          </div>
        </div>

        {/* Editorial Rubric Breakdown or Fallback Notice */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1.5">
            Complete Editorial Rubric (1–5)
          </label>
          {rubric ? (
            <div className="space-y-1.5 text-xs bg-paper-100 p-3 rounded-lg border border-paper-300">
              <div className="flex items-center justify-between border-b border-paper-200 pb-1">
                <span className="font-medium text-charcoal">Opening Hook Strength:</span>
                <span className="font-bold font-mono text-burnt-800">{rubric.opening_strength} / 5</span>
              </div>
              <p className="text-[11px] text-charcoal-muted mb-2">{rubric.opening_reason}</p>

              <div className="flex items-center justify-between border-b border-paper-200 pb-1">
                <span className="font-medium text-charcoal">Standalone Clarity:</span>
                <span className="font-bold font-mono text-burnt-800">{rubric.standalone_clarity} / 5</span>
              </div>
              <p className="text-[11px] text-charcoal-muted mb-2">{rubric.clarity_reason}</p>

              <div className="flex items-center justify-between border-b border-paper-200 pb-1">
                <span className="font-medium text-charcoal">Escalation & Stakes:</span>
                <span className="font-bold font-mono text-burnt-800">{rubric.escalation_stakes} / 5</span>
              </div>
              <p className="text-[11px] text-charcoal-muted mb-2">{rubric.stakes_reason}</p>

              <div className="flex items-center justify-between border-b border-paper-200 pb-1">
                <span className="font-medium text-charcoal">Unresolved Cut Timing:</span>
                <span className="font-bold font-mono text-burnt-800">{rubric.unresolved_ending} / 5</span>
              </div>
              <p className="text-[11px] text-charcoal-muted">{rubric.ending_reason}</p>

              {rubric.uncertainty_or_weakness && (
                <div className="mt-2 pt-2 border-t border-paper-200 text-amber-900 bg-amber-50 p-2 rounded">
                  <div className="flex items-center space-x-1 font-semibold text-[11px] mb-0.5">
                    <HelpCircle className="w-3.5 h-3.5 text-amber-700" />
                    <span>Editorial Uncertainty / Weakness:</span>
                  </div>
                  <p className="text-[11px]">{rubric.uncertainty_or_weakness}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900">
              <div className="font-semibold mb-1 flex items-center space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                <span>Editorial assessment unavailable</span>
              </div>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                This candidate passed all mechanical timeline boundary checks and is preserved for manual editorial review. Heuristic scores are not fabricated when the assessment model is unavailable.
              </p>
            </div>
          )}
        </div>

        {/* Mechanical Check Checklist */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Mechanical Timeline Verification
          </label>
          <div className="p-3 rounded-lg bg-paper-200/60 border border-paper-300 space-y-1.5 text-xs">
            <div className="flex items-center space-x-1.5 text-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Duration {segment.duration_seconds}s within 20s–60s limit</span>
            </div>
            <div className="flex items-center space-x-1.5 text-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Boundary cuts do not split active dialogue lines</span>
            </div>
            <div className="flex items-center space-x-1.5 text-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Opening hook intersects first 3.0 seconds</span>
            </div>
            <div className="flex items-center space-x-1.5 text-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Ending cliffhanger occurs within 6.0 seconds of cut</span>
            </div>
          </div>
        </div>

        {/* Review Flags & Editorial Risks */}
        {(candidate.editorial_risks.length > 0 || review_flags.length > 0) && (
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-amber-800 block mb-1">
              Editorial Review Flags
            </label>
            <div className="space-y-1.5">
              {review_flags.map((flag, i) => (
                <div key={`flag-${i}`} className="p-2 rounded bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-700 flex-shrink-0 mt-0.5" />
                  <span>{flag}</span>
                </div>
              ))}
              {candidate.editorial_risks.map((risk, i) => (
                <div key={`risk-${i}`} className="p-2 rounded bg-paper-200 border border-paper-300 text-xs text-charcoal-muted flex items-start space-x-1.5">
                  <Film className="w-3.5 h-3.5 text-charcoal-subtle flex-shrink-0 mt-0.5" />
                  <span>{risk}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-paper-300 bg-paper-100 text-[11px] text-charcoal-subtle flex justify-between">
        <span>ID: <code className="font-mono text-[10px]">{candidate.id}</code></span>
        <span>Events: <code className="font-mono text-[10px]">{segment.event_ids.length}</code></span>
      </div>
    </aside>
  );
};
