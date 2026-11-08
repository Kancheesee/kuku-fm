import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { EmptyState } from './components/EmptyState';
import { SummaryBar } from './components/SummaryBar';
import { EpisodeSidebar } from './components/EpisodeSidebar';
import { ScriptTimeline } from './components/ScriptTimeline';
import { EventDetailDrawer } from './components/EventDetailDrawer';
import { PartialErrorAlert } from './components/PartialErrorAlert';
import { Event, IngestPreviewResponse } from './types';
import { checkBackendHealth, uploadScriptsForPreview } from './lib/api';

export const App: React.FC = () => {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [ingestResponse, setIngestResponse] = useState<IngestPreviewResponse | null>(null);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [showPartialAlert, setShowPartialAlert] = useState(true);

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
      setIngestResponse(result);
      if (result.episodes.length > 0) {
        setSelectedEpisodeId(result.episodes[0].id);
        setSelectedEvent(result.episodes[0].events[0] || null);
      } else {
        setSelectedEpisodeId(null);
        setSelectedEvent(null);
      }
      setShowPartialAlert(true);
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
    setIngestResponse(null);
    setSelectedEpisodeId(null);
    setSelectedEvent(null);
    setErrorMessage(null);
  };

  const selectedEpisode = ingestResponse?.episodes.find((e) => e.id === selectedEpisodeId) || null;

  return (
    <div className="min-h-screen flex flex-col bg-paper-100 text-charcoal">
      <Header
        hasLoadedScripts={!!ingestResponse}
        onReset={handleReset}
        isBackendConnected={isBackendConnected}
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

          <div className="flex-1 flex overflow-hidden">
            <EpisodeSidebar
              episodes={ingestResponse.episodes}
              selectedEpisodeId={selectedEpisodeId}
              onSelectEpisode={(id) => {
                setSelectedEpisodeId(id);
                const ep = ingestResponse.episodes.find((e) => e.id === id);
                setSelectedEvent(ep?.events[0] || null);
              }}
            />

            {selectedEpisode ? (
              <ScriptTimeline
                episode={selectedEpisode}
                selectedEventId={selectedEvent?.id || null}
                onSelectEvent={(event) => setSelectedEvent(event)}
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-xs text-charcoal-subtle">
                Select an episode to inspect screenplay events.
              </div>
            )}

            {selectedEvent && selectedEpisode && (
              <EventDetailDrawer
                event={selectedEvent}
                issues={selectedEpisode.warnings}
                onClose={() => setSelectedEvent(null)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default App;

