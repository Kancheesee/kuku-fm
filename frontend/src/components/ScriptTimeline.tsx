import React, { useState, useMemo } from 'react';
import { Episode, Event, EventCategory } from '../types';
import { formatMsToTimestamp, formatDurationHuman } from '../lib/utils';
import {
  Search,
  Filter,
  Video,
  Clapperboard,
  Mic,
  Volume2,
  HelpCircle,
  AlertTriangle,
  Layers,
} from 'lucide-react';

interface ScriptTimelineProps {
  episode: Episode;
  selectedEventId: string | null;
  onSelectEvent: (event: Event) => void;
}

export const ScriptTimeline: React.FC<ScriptTimelineProps> = ({
  episode,
  selectedEventId,
  onSelectEvent,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<EventCategory | 'all'>('all');
  const [selectedSceneFilter, setSelectedSceneFilter] = useState<string>('all');

  // Filter events based on category, search text, and scene filter
  const filteredEvents = useMemo(() => {
    return episode.events.filter((ev) => {
      if (categoryFilter !== 'all' && ev.category !== categoryFilter) {
        return false;
      }
      if (selectedSceneFilter !== 'all' && ev.scene_id !== selectedSceneFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const textMatch = ev.text.toLowerCase().includes(q);
        const speakerMatch = ev.speaker ? ev.speaker.toLowerCase().includes(q) : false;
        const labelMatch = ev.original_label.toLowerCase().includes(q);
        return textMatch || speakerMatch || labelMatch;
      }
      return true;
    });
  }, [episode.events, categoryFilter, selectedSceneFilter, searchQuery]);

  // Group filtered events by scene for structured screenplay reading
  const sceneMap = useMemo(() => {
    const map = new Map<string, { scene: typeof episode.scenes[0] | undefined; events: Event[] }>();
    for (const sc of episode.scenes) {
      map.set(sc.id, { scene: sc, events: [] });
    }
    for (const ev of filteredEvents) {
      const entry = map.get(ev.scene_id);
      if (entry) {
        entry.events.push(ev);
      } else {
        // Orphan event without explicit scene
        map.set(ev.scene_id, { scene: undefined, events: [ev] });
      }
    }
    return map;
  }, [episode.scenes, filteredEvents]);

  const getCategoryBadge = (cat: EventCategory) => {
    switch (cat) {
      case 'camera':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-stone-200 text-stone-800 border border-stone-300">
            <Video className="w-3 h-3 text-stone-600" />
            <span>CAMERA</span>
          </span>
        );
      case 'action':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
            <Clapperboard className="w-3 h-3 text-emerald-700" />
            <span>ACTION</span>
          </span>
        );
      case 'dialogue':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-burnt-100 text-burnt-800 border border-burnt-200">
            <Mic className="w-3 h-3 text-burnt-700" />
            <span>DIALOGUE</span>
          </span>
        );
      case 'sound_effect':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-indigo-100 text-indigo-800 border border-indigo-200">
            <Volume2 className="w-3 h-3 text-indigo-700" />
            <span>SOUND FX</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800 border border-amber-200">
            <HelpCircle className="w-3 h-3 text-amber-700" />
            <span>UNKNOWN</span>
          </span>
        );
    }
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-101px)] bg-paper-100 overflow-hidden">
      {/* Episode Header & Editorial Metadata */}
      <div className="p-5 border-b border-paper-300 bg-paper-50">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
          <div className="flex items-center space-x-3">
            <h2 className="text-xl font-bold font-serif text-charcoal tracking-tight">
              {episode.episode_number !== null ? `Episode ${episode.episode_number}` : 'Untitled Episode'}
            </h2>
            <span className="text-xs font-mono text-charcoal-muted bg-paper-200 border border-paper-300 px-2 py-0.5 rounded">
              {formatDurationHuman(episode.duration_ms)} ({formatMsToTimestamp(episode.duration_ms)})
            </span>
          </div>
          <span className="text-xs text-charcoal-subtle font-mono">
            {episode.filename}
          </span>
        </div>

        {/* Logline & Continuity notes */}
        {episode.logline && (
          <div className="mt-2 text-xs text-charcoal-muted leading-relaxed">
            <span className="font-semibold text-charcoal">Logline: </span>
            {episode.logline}
          </div>
        )}

        {episode.continuity_notes && (
          <div className="mt-1 text-[11px] text-charcoal-subtle leading-relaxed">
            <span className="font-semibold text-charcoal">Continuity: </span>
            {episode.continuity_notes}
          </div>
        )}

        {/* Episode warnings alert banner if any */}
        {episode.warnings.length > 0 && (
          <div className="mt-3 p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold">{episode.warnings.length} parsing warning(s) in this script: </span>
              <span className="text-[11px] text-amber-800">
                {episode.warnings.map(w => `${w.code} (L${w.line || '?'}): ${w.message}`).join(' • ')}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="px-5 py-3 border-b border-paper-300 bg-paper-50 flex flex-wrap items-center justify-between gap-3">
        {/* Category Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-xs font-semibold text-charcoal-subtle mr-1 flex items-center space-x-1">
            <Filter className="w-3 h-3" />
            <span>Filter:</span>
          </span>

          {(
            [
              ['all', 'All Events'],
              ['dialogue', 'Dialogue'],
              ['action', 'Action'],
              ['camera', 'Camera'],
              ['sound_effect', 'Sound'],
            ] as const
          ).map(([catKey, label]) => (
            <button
              key={catKey}
              onClick={() => setCategoryFilter(catKey)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-burnt-600 ${
                categoryFilter === catKey
                  ? 'bg-burnt-700 text-white shadow-xs'
                  : 'bg-paper-200 text-charcoal-muted hover:bg-paper-300 hover:text-charcoal border border-paper-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Scene Jump & In-Episode Search */}
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          {episode.scenes.length > 1 && (
            <div className="relative">
              <select
                value={selectedSceneFilter}
                onChange={(e) => setSelectedSceneFilter(e.target.value)}
                aria-label="Filter or jump to scene"
                className="text-xs bg-paper-200 border border-paper-300 rounded px-2.5 py-1.5 text-charcoal focus:outline-none focus:ring-1 focus:ring-burnt-600"
              >
                <option value="all">All Scenes ({episode.scenes.length})</option>
                {episode.scenes.map((sc, idx) => (
                  <option key={sc.id} value={sc.id}>
                    Scene {idx + 1}: {sc.heading.slice(0, 24)}...
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="relative flex-1 sm:w-48">
            <Search className="w-3.5 h-3.5 text-charcoal-subtle absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search in script..."
              className="w-full pl-8 pr-2.5 py-1.5 text-xs bg-paper-200 border border-paper-300 rounded focus:outline-none focus:ring-1 focus:ring-burnt-600 focus:bg-paper-50 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Screenplay Event Timeline */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {filteredEvents.length === 0 ? (
          <div className="py-12 text-center text-xs text-charcoal-subtle">
            No events found matching your current filters.
          </div>
        ) : (
          Array.from(sceneMap.entries()).map(([sceneId, { scene, events }]) => {
            if (events.length === 0) return null;

            return (
              <div key={sceneId} className="space-y-3">
                {/* Scene Header Card */}
                {scene && (
                  <div className="bg-paper-200/80 border border-paper-300 rounded-md p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-xs">
                    <div className="flex items-center space-x-2">
                      <Layers className="w-4 h-4 text-charcoal-subtle" />
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-charcoal">
                          {scene.scene_label}
                        </span>
                        <h4 className="text-xs font-semibold text-charcoal tracking-wide">
                          {scene.heading}
                        </h4>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 text-xs font-mono text-charcoal-muted">
                      <span>{formatMsToTimestamp(scene.start_ms)} – {formatMsToTimestamp(scene.end_ms)}</span>
                      <span className="text-charcoal-subtle">({formatDurationHuman(scene.end_ms - scene.start_ms)})</span>
                      <span className="text-[10px] text-charcoal-subtle bg-paper-300 px-1 py-0.5 rounded">
                        L{scene.line_start}–{scene.line_end}
                      </span>
                    </div>
                  </div>
                )}

                {/* Event Cards inside this scene */}
                <div className="space-y-2 pl-1 sm:pl-3 border-l-2 border-paper-300">
                  {events.map((ev) => {
                    const isSelected = ev.id === selectedEventId;
                    const durationMs = ev.end_ms - ev.start_ms;

                    return (
                      <div
                        key={ev.id}
                        onClick={() => onSelectEvent(ev)}
                        className={`group relative p-3.5 rounded-lg border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-paper-50 border-burnt-700 shadow-sm ring-1 ring-burnt-700'
                            : 'bg-paper-50/70 hover:bg-paper-50 border-paper-300 hover:border-charcoal-subtle'
                        }`}
                      >
                        {/* Event Metadata Row */}
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                          <div className="flex items-center space-x-2">
                            {getCategoryBadge(ev.category)}
                            {ev.speaker && (
                              <span className="text-xs font-bold text-charcoal tracking-wide">
                                {ev.speaker}
                                {ev.delivery_notes && (
                                  <span className="font-normal italic text-charcoal-muted ml-1">
                                    ({ev.delivery_notes})
                                  </span>
                                )}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center space-x-2 text-[11px] font-mono text-charcoal-muted">
                            <span className="bg-paper-200 px-1.5 py-0.5 rounded border border-paper-300">
                              {formatMsToTimestamp(ev.start_ms)} – {formatMsToTimestamp(ev.end_ms)}
                            </span>
                            <span className="text-charcoal-subtle">
                              {(durationMs / 1000).toFixed(2)}s
                            </span>
                            <span className="text-[10px] text-charcoal-subtle">
                              L{ev.line_start}
                            </span>
                          </div>
                        </div>

                        {/* Event Text Description / Line */}
                        <div className="text-xs font-serif text-charcoal leading-relaxed whitespace-pre-wrap pl-0.5">
                          {ev.text || (
                            <span className="italic text-charcoal-subtle text-[11px]">
                              {ev.original_label}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
