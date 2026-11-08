import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { EmptyState } from './components/EmptyState';
import { SummaryBar } from './components/SummaryBar';
import { EpisodeSidebar, EpisodeStatusInfo } from './components/EpisodeSidebar';
import { ScriptTimeline } from './components/ScriptTimeline';
import { PromoListView } from './components/PromoListView';
import { ShowWideRankingView } from './components/ShowWideRankingView';
import { EventDetailDrawer } from './components/EventDetailDrawer';
import { PromoDetailDrawer } from './components/PromoDetailDrawer';
import { PartialErrorAlert } from './components/PartialErrorAlert';
import { SavedRunsModal } from './components/SavedRunsModal';
import {
  Episode,
  Event,
  IngestPreviewResponse,
  PromoAnalysisResponse,
  PromoCandidate,
  RunDetail,
} from './types';
import {
  checkBackendHealth,
  initSession,
  uploadScriptsForPreview,
  analyzeEpisodePromos,
  createSavedRun,
  getSavedRun,
  analyzeRunEpisode,
  pauseSavedRun,
  resumeSavedRun,
  retryRunEpisode,
} from './lib/api';
import { exportShortlistCsv, exportRawAuditJson } from './lib/export';
import { FileText, Sparkles, AlertTriangle, Trophy } from 'lucide-react';

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
  const [activeView, setActiveView] = useState<'timeline' | 'promos' | 'show-ranking'>('timeline');
  const [selectedCandidate, setSelectedCandidate] = useState<PromoCandidate | null>(null);

  // Milestone 3 Persistence & Resumable Run States
  const [currentRun, setCurrentRun] = useState<RunDetail | null>(null);
  const [isSavedRunsModalOpen, setIsSavedRunsModalOpen] = useState(false);
  const [isSavingRun, setIsSavingRun] = useState(false);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [quotaExhaustedMsg, setQuotaExhaustedMsg] = useState<string | null>(null);

  // Ref to track latest selectedEpisodeId across async closures and prevent stale responses
  const selectedEpisodeIdRef = useRef<string | null>(null);
  const uploadEpochRef = useRef<number>(0);
  const batchCancelRef = useRef<boolean>(false);

  useEffect(() => {
    selectedEpisodeIdRef.current = selectedEpisodeId;
  }, [selectedEpisodeId]);

  // Establish HttpOnly session cookie and check backend health on initial render
  useEffect(() => {
    initSession().catch(() => {});
    checkBackendHealth()
      .then((res) => setIsBackendConnected(res.database_connected !== false))
      .catch(() => setIsBackendConnected(false));
  }, []);

  const handleFilesSelected = async (files: File[]) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const result = await uploadScriptsForPreview(files);
      uploadEpochRef.current += 1;
      setIngestResponse(result);
      setCurrentRun(null);
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
    setCurrentRun(null);
    setSelectedEpisodeId(null);
    setSelectedEvent(null);
    setErrorMessage(null);
    setPromoResults({});
    setSelectedCandidate(null);
    setPromoError(null);
  };

  // Save current preview to database
  const handleSaveCurrentRun = async () => {
    if (!ingestResponse || isSavingRun) return;
    setIsSavingRun(true);
    setPromoError(null);
    try {
      const run = await createSavedRun(
        ingestResponse.episodes,
        `Run: ${ingestResponse.episodes[0]?.filename?.replace(/\.[^/.]+$/, '') || 'Pack'}`
      );
      setCurrentRun(run);
    } catch (err: unknown) {
      if (err instanceof Error) setPromoError(err.message);
      else setPromoError('Failed to save run to Neon database.');
    } finally {
      setIsSavingRun(false);
    }
  };

  // Load an existing saved run from Neon
  const handleSelectSavedRun = async (runId: string) => {
    setIsLoading(true);
    setPromoError(null);
    try {
      const runDetail = await getSavedRun(runId);
      uploadEpochRef.current += 1;
      setCurrentRun(runDetail);

      // Reconstruct IngestPreviewResponse from persisted episode records
      const episodes: Episode[] = runDetail.episodes.map((ep) => ({
        id: ep.id,
        episode_number: ep.episode_number,
        filename: ep.filename,
        duration_ms: ep.duration_ms,
        content_hash: ep.content_hash,
        parser_version: '1.0.0',
        scenes: [],
        events: [],
        warnings: [],
      }));

      // Restore promo results keyed by content_hash
      const restoredPromos: Record<string, PromoAnalysisResponse> = {};
      for (const ep of runDetail.episodes) {
        if (ep.analysis_result) {
          restoredPromos[ep.content_hash] = ep.analysis_result;
        }
      }

      setIngestResponse({
        episodes,
        total_episodes: runDetail.total_episodes,
        total_runtime_ms: episodes.reduce((acc, e) => acc + e.duration_ms, 0),
        total_events: runDetail.episodes.reduce((acc, e) => acc + e.events_count, 0),
        total_issues: runDetail.episodes.reduce((acc, e) => acc + e.warnings_count, 0),
        ignored_files_count: 0,
        file_results: [],
      });

      setPromoResults(restoredPromos);

      if (episodes.length > 0) {
        setSelectedEpisodeId(episodes[0].id);
      }

      if (runDetail.show_ranking.length > 0) {
        setSelectedCandidate(runDetail.show_ranking[0]);
        setActiveView('show-ranking');
      } else {
        setActiveView('timeline');
      }
    } catch (err: unknown) {
      if (err instanceof Error) setPromoError(err.message);
      else setPromoError('Failed to load run from database.');
    } finally {
      setIsLoading(false);
    }
  };

  // Selected episode helper
  const selectedEpisode = ingestResponse?.episodes.find((e) => e.id === selectedEpisodeId) || null;
  const currentEpisodePromos = selectedEpisode ? promoResults[selectedEpisode.content_hash] : null;

  // Single episode analysis
  const handleFindPromos = async () => {
    if (!selectedEpisode || isAnalyzingPromos) return;
    const targetEpisode = selectedEpisode;
    const requestEpoch = uploadEpochRef.current;

    setIsAnalyzingPromos(true);
    setPromoError(null);

    try {
      let result: PromoAnalysisResponse;
      if (currentRun) {
        // Use per-episode persistence API
        result = await analyzeRunEpisode(currentRun.id, targetEpisode.id);
        // Refresh run state to update completed counts and rankings
        const updatedRun = await getSavedRun(currentRun.id);
        setCurrentRun(updatedRun);
      } else {
        result = await analyzeEpisodePromos(targetEpisode);
      }

      if (uploadEpochRef.current !== requestEpoch) return;

      setPromoResults((prev) => ({
        ...prev,
        [targetEpisode.content_hash]: result,
      }));

      if (selectedEpisodeIdRef.current === targetEpisode.id) {
        if (result.candidates.length > 0) {
          setSelectedCandidate(result.candidates[0]);
        } else {
          setSelectedCandidate(null);
        }
        setActiveView('promos');
      }
    } catch (err: unknown) {
      if (uploadEpochRef.current !== requestEpoch) return;
      if (err instanceof Error) setPromoError(err.message);
      else setPromoError('Failed to generate promo candidates.');
    } finally {
      setIsAnalyzingPromos(false);
    }
  };

  // Client-side sequential batch scheduler: React issues separate per-episode requests
  const runBatchScheduler = async (runId: string) => {
    batchCancelRef.current = false;
    setIsBatchRunning(true);
    setPromoError(null);
    setQuotaExhaustedMsg(null);

    try {
      while (!batchCancelRef.current) {
        const freshRun = await getSavedRun(runId);
        setCurrentRun(freshRun);

        // Update local promoResults for any newly completed episodes
        const currentPromos = { ...promoResults };
        for (const ep of freshRun.episodes) {
          if (ep.analysis_result && !currentPromos[ep.content_hash]) {
            currentPromos[ep.content_hash] = ep.analysis_result;
          }
        }
        setPromoResults(currentPromos);

        // Resume / analyze only pending episodes (skip completed and failed)
        const pendingEpisodes = freshRun.episodes.filter((e) => e.analysis_status === 'pending');
        if (pendingEpisodes.length === 0 || batchCancelRef.current) {
          break;
        }

        const nextEp = pendingEpisodes[0];
        try {
          const result = await analyzeRunEpisode(runId, nextEp.id);
          const matched = ingestResponse?.episodes.find((e) => e.id === nextEp.id);
          if (matched) {
            setPromoResults((prev) => ({ ...prev, [matched.content_hash]: result }));
          }
        } catch (err: unknown) {
          const isQuota =
            (err && typeof err === 'object' && 'isQuotaExceeded' in err && (err as any).isQuotaExceeded) ||
            (err instanceof Error && (err.message.includes('429') || err.message.toLowerCase().includes('quota')));

          if (isQuota) {
            setQuotaExhaustedMsg(
              'Gemini API quota exhausted. Batch execution paused. Completed episodes are safely preserved. You can resume when quota resets or retry this episode.'
            );
            await pauseSavedRun(runId).catch(() => {});
            const pausedRun = await getSavedRun(runId).catch(() => null);
            if (pausedRun) setCurrentRun(pausedRun);
            break;
          } else {
            if (err instanceof Error) {
              setPromoError(`Episode ${nextEp.episode_number ?? nextEp.filename} analysis failed: ${err.message}`);
            }
          }
        }
      }

      const finalRun = await getSavedRun(runId);
      setCurrentRun(finalRun);
      if (finalRun.show_ranking && finalRun.show_ranking.length > 0) {
        setSelectedCandidate(finalRun.show_ranking[0]);
      }
    } catch (err: unknown) {
      if (err instanceof Error) setPromoError(err.message);
    } finally {
      setIsBatchRunning(false);
    }
  };

  const handleAnalyzeAll = async () => {
    if (!currentRun || isBatchRunning) return;
    await runBatchScheduler(currentRun.id);
  };

  const handlePauseRun = async () => {
    if (!currentRun) return;
    batchCancelRef.current = true;
    try {
      const updated = await pauseSavedRun(currentRun.id);
      setCurrentRun(updated);
      setIsBatchRunning(false);
    } catch (err: unknown) {
      if (err instanceof Error) setPromoError(err.message);
    }
  };

  const handleResumeRun = async () => {
    if (!currentRun) return;
    try {
      await resumeSavedRun(currentRun.id);
      await runBatchScheduler(currentRun.id);
    } catch (err: unknown) {
      if (err instanceof Error) setPromoError(err.message);
    }
  };

  const handleRetryEpisode = async (episodeId: string) => {
    if (!currentRun) return;
    setPromoError(null);
    setQuotaExhaustedMsg(null);
    try {
      const result = await retryRunEpisode(currentRun.id, episodeId);
      const updated = await getSavedRun(currentRun.id);
      setCurrentRun(updated);
      const ep = ingestResponse?.episodes.find((e) => e.id === episodeId);
      if (ep) {
        setPromoResults((prev) => ({ ...prev, [ep.content_hash]: result }));
      }
    } catch (err: unknown) {
      const isQuota =
        (err && typeof err === 'object' && 'isQuotaExceeded' in err && (err as any).isQuotaExceeded) ||
        (err instanceof Error && (err.message.includes('429') || err.message.toLowerCase().includes('quota')));

      if (isQuota) {
        setQuotaExhaustedMsg(
          'Gemini API quota exhausted while retrying episode. You can retry again once your quota window resets.'
        );
      } else if (err instanceof Error) {
        setPromoError(err.message);
      }
    }
  };

  const handleExportCsv = () => {
    if (activeView === 'show-ranking' && currentRun && currentRun.show_ranking.length > 0) {
      exportShortlistCsv(currentRun.show_ranking, undefined);
    } else if (currentEpisodePromos && currentEpisodePromos.candidates.length > 0) {
      exportShortlistCsv(currentEpisodePromos.candidates, selectedEpisode?.episode_number);
    }
  };

  const handleExportJson = () => {
    if (activeView === 'show-ranking' && currentRun) {
      const blob = new Blob([JSON.stringify(currentRun, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `run_${currentRun.id}_audit.json`;
      link.click();
      URL.revokeObjectURL(url);
    } else if (currentEpisodePromos) {
      exportRawAuditJson(currentEpisodePromos);
    }
  };

  // Map per-episode status info for sidebar
  const episodeStatuses: Record<string, EpisodeStatusInfo> = {};
  if (currentRun) {
    for (const ep of currentRun.episodes) {
      episodeStatuses[ep.id] = {
        status: ep.analysis_status,
        retry_count: ep.retry_count,
        error: ep.error_message,
      };
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper-100 text-charcoal">
      <Header
        hasLoadedScripts={!!ingestResponse}
        selectedEpisodeNumber={selectedEpisode?.episode_number}
        onReset={handleReset}
        isBackendConnected={isBackendConnected}
        onFindPromos={handleFindPromos}
        isAnalyzingPromos={isAnalyzingPromos}
        hasPromoResults={
          (!!currentEpisodePromos && currentEpisodePromos.candidates.length > 0) ||
          (!!currentRun && currentRun.show_ranking.length > 0)
        }
        onExportCsv={handleExportCsv}
        onExportJson={handleExportJson}
        currentRunName={currentRun?.name}
        currentRunStatus={currentRun?.status}
        hasSavedRun={!!currentRun}
        onOpenSavedRuns={() => setIsSavedRunsModalOpen(true)}
        onSaveRun={handleSaveCurrentRun}
        isSavingRun={isSavingRun}
        onAnalyzeAll={handleAnalyzeAll}
        isBatchRunning={isBatchRunning}
        onPauseRun={handlePauseRun}
        onResumeRun={handleResumeRun}
      />

      <SavedRunsModal
        isOpen={isSavedRunsModalOpen}
        onClose={() => setIsSavedRunsModalOpen(false)}
        onSelectRun={handleSelectSavedRun}
        currentRunId={currentRun?.id}
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

          {/* Actionable Quota Exhaustion Banner */}
          {quotaExhaustedMsg && (
            <div className="bg-rose-50 border-b border-rose-300 px-6 py-3 flex items-center justify-between text-xs text-rose-950">
              <div className="flex items-center space-x-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-700 flex-shrink-0" />
                <div>
                  <span className="font-bold">Quota Limit Reached: </span>
                  <span>{quotaExhaustedMsg}</span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {currentRun && currentRun.status === 'paused' && (
                  <button
                    onClick={handleResumeRun}
                    className="px-2.5 py-1 rounded bg-rose-200 hover:bg-rose-300 text-rose-900 font-semibold text-[11px]"
                  >
                    Resume Batch
                  </button>
                )}
                <button
                  onClick={() => setQuotaExhaustedMsg(null)}
                  className="text-[11px] underline text-rose-800 hover:text-rose-950"
                >
                  Dismiss
                </button>
              </div>
            </div>
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

                const existingPromos = ep ? promoResults[ep.content_hash] : null;
                if (existingPromos && existingPromos.candidates.length > 0) {
                  setSelectedCandidate(existingPromos.candidates[0]);
                } else {
                  setSelectedCandidate(null);
                }
                if (activeView === 'show-ranking') {
                  setActiveView('timeline');
                }
              }}
              episodeStatuses={episodeStatuses}
              onRetryEpisode={handleRetryEpisode}
            />

            {/* Main Area: Navigation Tabs between Timeline, Promos, & Show Ranking */}
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

                  {currentRun && currentRun.show_ranking.length > 0 && (
                    <button
                      onClick={() => setActiveView('show-ranking')}
                      className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
                        activeView === 'show-ranking'
                          ? 'bg-amber-100 text-amber-900 font-semibold border border-amber-300'
                          : 'text-charcoal-muted hover:text-charcoal'
                      }`}
                    >
                      <Trophy className="w-3.5 h-3.5 text-amber-700" />
                      <span>
                        Show Top Promos ({currentRun.show_ranking.length})
                      </span>
                    </button>
                  )}
                </div>

                {/* Episode Identification Header */}
                <div className="flex items-center space-x-2 text-[11px] text-charcoal-subtle font-mono">
                  <span className="font-semibold text-charcoal">
                    {selectedEpisode?.episode_number !== null && selectedEpisode?.episode_number !== undefined
                      ? `Ep ${selectedEpisode?.episode_number}`
                      : 'Episode'}
                  </span>
                  <span>•</span>
                  <span className="truncate max-w-xs">{selectedEpisode?.filename}</span>
                </div>
              </div>

              {/* View Rendering */}
              {activeView === 'show-ranking' && currentRun ? (
                <ShowWideRankingView
                  runName={currentRun.name}
                  candidates={currentRun.show_ranking}
                  selectedCandidateId={selectedCandidate?.id || null}
                  onSelectCandidate={(cand) => setSelectedCandidate(cand)}
                  onExportCsv={handleExportCsv}
                  onExportJson={handleExportJson}
                  isProvisional={currentRun.is_provisional}
                  completedEpisodes={currentRun.completed_episodes}
                  totalEpisodes={currentRun.total_episodes}
                  coveragePercentage={currentRun.coverage_percentage}
                />
              ) : selectedEpisode ? (
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
