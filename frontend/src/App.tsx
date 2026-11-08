import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { EmptyState } from './components/EmptyState';
import { SummaryBar } from './components/SummaryBar';
import { EpisodeSidebar } from './components/EpisodeSidebar';
import { ScriptTimeline } from './components/ScriptTimeline';
import { PromoListView } from './components/PromoListView';
import { EventDetailDrawer } from './components/EventDetailDrawer';
import { PromoDetailDrawer } from './components/PromoDetailDrawer';
import { PartialErrorAlert } from './components/PartialErrorAlert';
import { Event, IngestPreviewResponse, PromoAnalysisResponse, PromoCandidate } from './types';
import { checkBackendHealth, uploadScriptsForPreview, analyzeEpisodePromos } from './lib/api';
import { exportShortlistCsv, exportRawAuditJson } from './lib/export';
import { FileText, Sparkles, AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [ingestResponse, setIngestResponse] = useState<IngestPreviewResponse | null>(null);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [showPartialAlert, setShowPartialAlert] = useState(true);

  // Milestone 2 Promo Analysis States: Keyed strictly by source content_hash
  const [promoResults, setPromoResults] = useState<Record<string, PromoAnalysisResponse>>({});
  const [isAnalyzingPromos, setIsAnalyzingPromos] = useState(false);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'timeline' | 'promos'>('timeline');
  const [selectedCandidate, setSelectedCandidate] = useState<PromoCandidate | null>(null);

  // Ref to track latest selectedEpisodeId across async closures and prevent stale responses
  const selectedEpisodeIdRef = useRef<string | null>(null);
  const uploadEpochRef = useRef<number>(0);
  useEffect(() => {
    selectedEpisodeIdRef.current = selectedEpisodeId;
  }, [selectedEpisodeId]);

  // Check backend health on initial render
  useEffect(() => {
    checkBackendHealth()
      .then(() => setIsBackendConnected(true))
      .catch(() => setIsBackendConnected(false));
  }, []);

  const handleFilesSelected = async (files: File[]) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const result = await uploadScriptsForPreview(files);
      uploadEpochRef.current += 1;
      setIngestResponse(result);
      if (result.episodes.length > 0) {
        const firstEp = result.episodes[0];
        setSelectedEpisodeId(firstEp.id);
        setSelectedEvent(firstEp.events[0] || null);
      } else {
        setSelectedEpisodeId(null);
        setSelectedEvent(null);
      }
      setShowPartialAlert(true);
      setPromoResults({});
      setActiveView('timeline');
      setSelectedCandidate(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('An unexpected error occurred during screenplay parsing.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    uploadEpochRef.current += 1;
    setIngestResponse(null);
    setSelectedEpisodeId(null);
    setSelectedEvent(null);
    setErrorMessage(null);
    setPromoResults({});
    setSelectedCandidate(null);
    setPromoError(null);
  };

  const selectedEpisode = ingestResponse?.episodes.find((e) => e.id === selectedEpisodeId) || null;
  // Key results strictly by the selected episode's content_hash
  const currentEpisodePromos = selectedEpisode ? promoResults[selectedEpisode.content_hash] : null;

  const handleFindPromos = async () => {
    if (!selectedEpisode || isAnalyzingPromos) return;
    const targetEpisode = selectedEpisode;
    const requestEpoch = uploadEpochRef.current;

    setIsAnalyzingPromos(true);
    setPromoError(null);

    try {
      const result = await analyzeEpisodePromos(targetEpisode);
      
      // If upload was replaced during the in-flight request, discard stale response
      if (uploadEpochRef.current !== requestEpoch) {
        return;
      }

      // Store result keyed by the target episode's content hash
      setPromoResults((prev) => ({
        ...prev,
        [targetEpisode.content_hash]: result,
      }));

      // Guard against stale response: only switch views if user is still on targetEpisode
      if (selectedEpisodeIdRef.current === targetEpisode.id) {
        if (result.candidates.length > 0) {
          setSelectedCandidate(result.candidates[0]);
        } else {
          setSelectedCandidate(null);
        }
        setActiveView('promos');
      }
    } catch (err: unknown) {
      if (uploadEpochRef.current !== requestEpoch) {
        return;
      }
      if (err instanceof Error) {
        setPromoError(err.message);
      } else {
        setPromoError('Failed to generate promo candidates with Gemini.');
      }
    } finally {
      setIsAnalyzingPromos(false);
    }
  };

  const handleExportCsv = () => {
    if (currentEpisodePromos && currentEpisodePromos.candidates.length > 0) {
      exportShortlistCsv(
        currentEpisodePromos.candidates,
        selectedEpisode?.episode_number
      );
    }
  };

  const handleExportJson = () => {
    if (currentEpisodePromos) {
      exportRawAuditJson(currentEpisodePromos);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-paper-100 text-charcoal">
      <Header
        hasLoadedScripts={!!ingestResponse}
        selectedEpisodeNumber={selectedEpisode?.episode_number}
        onReset={handleReset}
        isBackendConnected={isBackendConnected}
        onFindPromos={handleFindPromos}
        isAnalyzingPromos={isAnalyzingPromos}
        hasPromoResults={!!currentEpisodePromos && currentEpisodePromos.candidates.length > 0}
        onExportCsv={handleExportCsv}
        onExportJson={handleExportJson}
      />

      {!ingestResponse ? (
        <main className="flex-1 flex items-center justify-center">
          <EmptyState
            onFilesSelected={handleFilesSelected}
            isLoading={isLoading}
            errorMessage={errorMessage}
          />
        </main>
      ) : (
        <div className="flex-1 flex flex-col overflow-hidden">
          <SummaryBar
            totalEpisodes={ingestResponse.total_episodes}
            totalRuntimeMs={ingestResponse.total_runtime_ms}
            totalEvents={ingestResponse.total_events}
            totalIssues={ingestResponse.total_issues}
            ignoredCount={ingestResponse.ignored_files_count}
          />

          {showPartialAlert && (
            <PartialErrorAlert
              fileResults={ingestResponse.file_results}
              onDismiss={() => setShowPartialAlert(false)}
            />
          )}

          {/* Promo Analysis Error Banner */}
          {promoError && (
            <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex items-center justify-between text-xs text-amber-900">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0" />
                <span className="font-semibold">{promoError}</span>
              </div>
              <button
                onClick={() => setPromoError(null)}
                className="text-[11px] underline text-amber-800 hover:text-amber-900"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="flex-1 flex overflow-hidden">
            <EpisodeSidebar
              episodes={ingestResponse.episodes}
              selectedEpisodeId={selectedEpisodeId}
              onSelectEpisode={(id) => {
                setSelectedEpisodeId(id);
                const ep = ingestResponse.episodes.find((e) => e.id === id);
                setSelectedEvent(ep?.events[0] || null);
                
                // Lookup promo results strictly by content hash
                const existingPromos = ep ? promoResults[ep.content_hash] : null;
                if (existingPromos && existingPromos.candidates.length > 0) {
                  setSelectedCandidate(existingPromos.candidates[0]);
                } else {
                  setSelectedCandidate(null);
                }
              }}
            />

            {/* Main Area: Navigation Tabs between Timeline & Promos */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* View Switcher Bar */}
              <div className="bg-paper-50 border-b border-paper-300 px-5 py-2 flex items-center justify-between">
                <div className="flex items-center space-x-1 text-xs">
                  <button
                    onClick={() => setActiveView('timeline')}
                    className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
                      activeView === 'timeline'
                        ? 'bg-paper-200 text-charcoal font-semibold border border-paper-300'
                        : 'text-charcoal-muted hover:text-charcoal'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 text-charcoal-subtle" />
                    <span>Screenplay Events</span>
                  </button>

                  <button
                    onClick={() => setActiveView('promos')}
                    className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
                      activeView === 'promos'
                        ? 'bg-burnt-100 text-burnt-900 font-semibold border border-burnt-300'
                        : 'text-charcoal-muted hover:text-charcoal'
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5 text-burnt-700" />
                    <span>
                      Promo Candidates
                      {currentEpisodePromos && ` (${currentEpisodePromos.candidates.length})`}
                    </span>
                  </button>
                </div>

                {/* Explicit Episode Identification Header */}
                <div className="flex items-center space-x-2 text-[11px] text-charcoal-subtle font-mono">
                  <span className="font-semibold text-charcoal">
                    {selectedEpisode?.episode_number !== null && selectedEpisode?.episode_number !== undefined
                      ? `Ep ${selectedEpisode?.episode_number}`
                      : 'Episode'}
                  </span>
                  <span>•</span>
                  <span className="truncate max-w-xs">{selectedEpisode?.filename}</span>
                  <span>•</span>
                  <span className="bg-paper-200 px-1.5 py-0.5 rounded text-[10px]">
                    {selectedEpisode?.content_hash?.slice(0, 8)}
                  </span>
                </div>
              </div>

              {/* View Rendering */}
              {selectedEpisode ? (
                activeView === 'timeline' ? (
                  <ScriptTimeline
                    episode={selectedEpisode}
                    selectedEventId={selectedEvent?.id || null}
                    onSelectEvent={(event) => {
                      setSelectedEvent(event);
                      setSelectedCandidate(null);
                    }}
                    activePromo={selectedCandidate}
                  />
                ) : currentEpisodePromos ? (
                  <PromoListView
                    response={currentEpisodePromos}
                    selectedCandidateId={selectedCandidate?.id || null}
                    onSelectCandidate={(candidate) => {
                      setSelectedCandidate(candidate);
                      setSelectedEvent(null);
                    }}
                  />
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                    <div className="w-12 h-12 rounded-full bg-burnt-100 flex items-center justify-center text-burnt-700 mb-3">
                      <Sparkles className="w-6 h-6" />
                    </div>
                    <h3 className="text-sm font-bold text-charcoal mb-1">
                      No Promo Candidates Generated Yet
                    </h3>
                    <p className="text-xs text-charcoal-muted max-w-sm mb-4 leading-relaxed">
                      Click the "Find Promos" button above to send Episode {selectedEpisode.episode_number ?? ''} ({selectedEpisode.filename}) to Gemini, validate timeline boundaries, and score editorial quality.
                    </p>
                    <button
                      onClick={handleFindPromos}
                      disabled={isAnalyzingPromos}
                      className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-burnt-700 hover:bg-burnt-800 text-white shadow-xs transition-colors"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Find Promos (Ep {selectedEpisode.episode_number ?? ''})</span>
                    </button>
                  </div>
                )
              ) : (
                <div className="flex-1 flex items-center justify-center text-xs text-charcoal-subtle">
                  Select an episode to inspect screenplay events or generate promos.
                </div>
              )}
            </div>

            {/* Right Side Inspector: Promo Candidate Drawer OR Event Drawer */}
            {selectedCandidate ? (
              <PromoDetailDrawer
                candidate={selectedCandidate}
                onClose={() => setSelectedCandidate(null)}
              />
            ) : selectedEvent && selectedEpisode ? (
              <EventDetailDrawer
                event={selectedEvent}
                issues={selectedEpisode.warnings}
                onClose={() => setSelectedEvent(null)}
              />
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
