import React from 'react';
import { Event, ParsingIssue } from '../types';
import { formatMsToTimestamp } from '../lib/utils';
import { X, Mic, FileCode, AlertTriangle, Video, Clapperboard, Volume2, HelpCircle } from 'lucide-react';

interface EventDetailDrawerProps {
  event: Event | null;
  onClose: () => void;
  issues: ParsingIssue[];
}

export const EventDetailDrawer: React.FC<EventDetailDrawerProps> = ({
  event,
  onClose,
  issues,
}) => {
  if (!event) return null;

  // Filter issues associated with this event's line numbers
  const eventIssues = issues.filter((iss) => {
    if (!iss.line) return false;
    return iss.line >= event.line_start && iss.line <= event.line_end;
  });

  const durationMs = event.end_ms - event.start_ms;
  const durationSec = (durationMs / 1000).toFixed(2);

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'camera':
        return <Video className="w-3.5 h-3.5 text-stone-700" />;
      case 'action':
        return <Clapperboard className="w-3.5 h-3.5 text-emerald-800" />;
      case 'dialogue':
        return <Mic className="w-3.5 h-3.5 text-burnt-800" />;
      case 'sound_effect':
        return <Volume2 className="w-3.5 h-3.5 text-indigo-800" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-amber-800" />;
    }
  };

  return (
    <aside className="w-80 lg:w-96 flex-shrink-0 border-l border-paper-300 bg-paper-50 flex flex-col h-[calc(100vh-101px)] shadow-md overflow-hidden">
      {/* Drawer Header */}
      <div className="p-4 border-b border-paper-300 flex items-center justify-between bg-paper-100">
        <div className="flex items-center space-x-2">
          {getCategoryIcon(event.category)}
          <span className="text-xs font-semibold text-charcoal uppercase tracking-wider">
            {event.category.replace('_', ' ')} Inspector
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-paper-200 text-charcoal-muted hover:text-charcoal transition-colors focus:outline-none focus:ring-1 focus:ring-burnt-600"
          aria-label="Close inspector drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Source Label & Category */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Original Screenplay Label
          </label>
          <div className="p-2.5 bg-paper-200 rounded border border-paper-300 font-mono text-xs text-charcoal select-all">
            {event.original_label}
          </div>
        </div>

        {/* Timestamps & Duration */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Timeline Coordinates
          </label>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">Start</span>
              <span className="font-mono text-xs font-semibold text-charcoal">
                {formatMsToTimestamp(event.start_ms)}
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{event.start_ms}ms</span>
            </div>
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">End</span>
              <span className="font-mono text-xs font-semibold text-charcoal">
                {formatMsToTimestamp(event.end_ms)}
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{event.end_ms}ms</span>
            </div>
            <div className="p-2 bg-paper-200 rounded border border-paper-300">
              <span className="text-[10px] text-charcoal-subtle block">Duration</span>
              <span className="font-mono text-xs font-semibold text-burnt-800">
                {durationSec}s
              </span>
              <span className="text-[9px] text-charcoal-subtle block font-mono">{durationMs}ms</span>
            </div>
          </div>
        </div>

        {/* Speaker & Delivery Breakdown (for dialogue) */}
        {event.category === 'dialogue' && (
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
              Dialogue Structure
            </label>
            <div className="space-y-2 p-3 bg-paper-200/60 rounded border border-paper-300 text-xs">
              <div>
                <span className="text-[10px] text-charcoal-subtle block">Character / Speaker:</span>
                <span className="font-semibold text-charcoal">{event.speaker || 'Unspecified'}</span>
              </div>
              {event.delivery_notes && (
                <div>
                  <span className="text-[10px] text-charcoal-subtle block">Delivery / Subtext Notes:</span>
                  <span className="italic text-charcoal">{event.delivery_notes}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Source Line References */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Source Line Range
          </label>
          <div className="flex items-center space-x-2 text-xs text-charcoal-muted p-2 bg-paper-200 rounded border border-paper-300">
            <FileCode className="w-3.5 h-3.5 text-charcoal-subtle" />
            <span>Lines {event.line_start} to {event.line_end}</span>
          </div>
        </div>

        {/* Exact Screenplay Text */}
        <div>
          <label className="text-[10px] uppercase font-bold tracking-wider text-charcoal-subtle block mb-1">
            Verbatim Event Text
          </label>
          <div className="p-3 bg-paper-100 rounded-lg border border-paper-300 text-xs text-charcoal font-serif leading-relaxed whitespace-pre-wrap select-text">
            {event.text || <span className="italic text-charcoal-subtle">No text description</span>}
          </div>
        </div>

        {/* Parsing Issues on this Event */}
        {eventIssues.length > 0 && (
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-amber-800 block mb-1">
              Event Validation Warnings ({eventIssues.length})
            </label>
            <div className="space-y-2">
              {eventIssues.map((iss, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded bg-amber-50 border border-amber-200 text-xs text-amber-900"
                >
                  <div className="flex items-center space-x-1 font-semibold text-[11px] mb-0.5">
                    <AlertTriangle className="w-3 h-3 text-amber-700" />
                    <span>{iss.code}</span>
                  </div>
                  <p className="text-[11px] leading-tight text-amber-800">{iss.message}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-paper-300 bg-paper-100 text-[11px] text-charcoal-subtle flex justify-between">
        <span>ID: <code className="font-mono text-[10px]">{event.id}</code></span>
        <span>Scene: <code className="font-mono text-[10px]">{event.scene_id}</code></span>
      </div>
    </aside>
  );
};
