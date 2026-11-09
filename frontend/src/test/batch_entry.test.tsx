import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import App from '../App';
import * as api from '../lib/api';
import { Episode, IngestPreviewResponse, PromoAnalysisResponse, RunDetail } from '../types';

const mockEpisode1: Episode = {
  id: 'ep1',
  episode_number: 1,
  filename: 'ep1.txt',
  content_hash: 'hash_ep1',
  duration_ms: 30000,
  parser_version: '1.0.0',
  scenes: [
    {
      id: 's1',
      scene_label: 'SCENE 01',
      heading: 'INT. ROOM - DAY',
      start_ms: 0,
      end_ms: 30000,
      line_start: 1,
      line_end: 10,
    },
  ],
  events: [
    {
      id: 'e1',
      scene_id: 's1',
      category: 'action',
      original_label: '**ACTION:**',
      start_ms: 0,
      end_ms: 5000,
      text: 'Door opens.',
      line_start: 2,
      line_end: 3,
    },
  ],
  warnings: [],
};

const mockEpisode2: Episode = {
  id: 'ep2',
  episode_number: 2,
  filename: 'ep2.txt',
  content_hash: 'hash_ep2',
  duration_ms: 32000,
  parser_version: '1.0.0',
  scenes: [
    {
      id: 's2',
      scene_label: 'SCENE 01',
      heading: 'INT. OFFICE - NIGHT',
      start_ms: 0,
      end_ms: 32000,
      line_start: 1,
      line_end: 10,
    },
  ],
  events: [
    {
      id: 'e2',
      scene_id: 's2',
      category: 'dialogue',
      speaker: 'VILLAIN',
      original_label: '**VILLAIN:**',
      start_ms: 0,
      end_ms: 32000,
      text: '"Surrender."',
      line_start: 2,
      line_end: 5,
    },
  ],
  warnings: [],
};

const mockIngestResult: IngestPreviewResponse = {
  episodes: [mockEpisode1, mockEpisode2],
  total_episodes: 2,
  total_runtime_ms: 62000,
  total_events: 2,
  total_issues: 0,
  ignored_files_count: 0,
  file_results: [
    { filename: 'ep1.txt', success: true, episode: mockEpisode1, issues: [] },
    { filename: 'ep2.txt', success: true, episode: mockEpisode2, issues: [] },
  ],
};

const mockCandidateEp1 = {
  id: 'cand_ep1',
  rank: 1,
  editorial_title: 'Dramatic Entrance',
  episode_number: 1,
  filename: 'ep1.txt',
  source_content_hash: 'hash_ep1',
  segment: {
    episode_id: 'ep1',
    episode_number: 1,
    filename: 'ep1.txt',
    source_content_hash: 'hash_ep1',
    start_ms: 0,
    end_ms: 30000,
    start_timestamp: '00:00.00',
    end_timestamp: '00:30.00',
    duration_ms: 30000,
    duration_seconds: 30.0,
    event_ids: ['e1'],
    events: mockEpisode1.events,
  },
  hook_explanation: 'Strong visual opening hook.',
  hook_event_ids: ['e1'],
  cliffhanger_explanation: 'Sudden cut.',
  cliffhanger_event_ids: ['e1'],
  unresolved_question: 'Who entered through the door?',
  rationale: 'High momentum and viral hook potential.',
  standalone_assessment: 'Fully understandable alone.',
  editorial_risks: [],
  assessment_status: 'assessed' as const,
  rubric: {
    opening_strength: 5,
    standalone_clarity: 4,
    escalation_stakes: 4,
    unresolved_ending: 5,
    opening_reason: 'Dynamic hook',
    clarity_reason: 'Clear setup',
    stakes_reason: 'High stakes',
    ending_reason: 'Cliffhanger cut',
    overall_score: 4.6,
  },
  review_flags: [],
  mechanical_status: 'passed' as const,
};

const mockAnalysisEp1: PromoAnalysisResponse = {
  episode_id: 'ep1',
  episode_number: 1,
  filename: 'ep1.txt',
  source_content_hash: 'hash_ep1',
  parser_version: '1.0.0',
  prompt_version: '2.2.0',
  assessment_prompt_version: 'assessment_v1.0.0',
  model: 'gemini-3.5-flash-lite',
  cache_key: 'key_ep1',
  candidates: [mockCandidateEp1],
  rejected_proposals: [],
  suppressed_candidates: [],
  metadata: {},
  raw_generation_response: '{}',
};

const mockAnalysisEp2: PromoAnalysisResponse = {
  episode_id: 'ep2',
  episode_number: 2,
  filename: 'ep2.txt',
  source_content_hash: 'hash_ep2',
  parser_version: '1.0.0',
  prompt_version: '2.2.0',
  assessment_prompt_version: 'assessment_v1.0.0',
  model: 'gemini-3.5-flash-lite',
  cache_key: 'key_ep2',
  candidates: [],
  rejected_proposals: [],
  suppressed_candidates: [],
  metadata: {},
  raw_generation_response: '{}',
};

function buildRunDetail(id: string, ep1Status: 'pending' | 'completed', ep2Status: 'pending' | 'completed'): RunDetail {
  const completed = (ep1Status === 'completed' ? 1 : 0) + (ep2Status === 'completed' ? 1 : 0);
  return {
    id,
    name: 'Run: ep1',
    status: completed === 2 ? 'completed' : 'running',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    total_episodes: 2,
    completed_episodes: completed,
    failed_episodes: 0,
    is_provisional: completed < 2,
    coverage_percentage: Math.round((completed / 2) * 100),
    episodes: [
      {
        id: 'ep1',
        run_id: id,
        internal_id: 'ep1',
        episode_number: 1,
        filename: 'ep1.txt',
        content_hash: 'hash_ep1',
        duration_ms: 30000,
        analysis_status: ep1Status,
        analysis_result: ep1Status === 'completed' ? mockAnalysisEp1 : null,
        retry_count: 0,
        scenes_count: 1,
        events_count: 1,
        warnings_count: 0,
      },
      {
        id: 'ep2',
        run_id: id,
        internal_id: 'ep2',
        episode_number: 2,
        filename: 'ep2.txt',
        content_hash: 'hash_ep2',
        duration_ms: 32000,
        analysis_status: ep2Status,
        analysis_result: ep2Status === 'completed' ? mockAnalysisEp2 : null,
        retry_count: 0,
        scenes_count: 1,
        events_count: 1,
        warnings_count: 0,
      },
    ],
    show_ranking: completed > 0 ? [mockCandidateEp1] : [],
    metadata: {},
  };
}

describe('Frontend Workflow: One-Click Batch Discovery and Auto-Opening Show Ranking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api, 'checkBackendHealth').mockResolvedValue({
      status: 'ok',
      version: '0.1.0',
      database_connected: true,
    });
    vi.spyOn(api, 'initSession').mockResolvedValue({ active: true });
  });

  it('provides one-click batch discovery: auto-saves run, sequentially analyzes episodes, and auto-opens Show Top Promos', async () => {
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue(mockIngestResult);

    const savedRunId = 'run_test_123';
    const createRunSpy = vi.spyOn(api, 'createSavedRun').mockResolvedValue(
      buildRunDetail(savedRunId, 'pending', 'pending')
    );

    let getRunCalls = 0;
    vi.spyOn(api, 'getSavedRun').mockImplementation(async () => {
      getRunCalls++;
      if (getRunCalls === 1) {
        return buildRunDetail(savedRunId, 'pending', 'pending');
      } else if (getRunCalls === 2) {
        return buildRunDetail(savedRunId, 'completed', 'pending');
      } else {
        return buildRunDetail(savedRunId, 'completed', 'completed');
      }
    });

    const analyzeEpisodeSpy = vi.spyOn(api, 'analyzeRunEpisode').mockImplementation(async (_runId, epId) => {
      if (epId === 'ep1') return mockAnalysisEp1;
      return mockAnalysisEp2;
    });

    render(<App />);

    // 1. Upload 2-episode pack
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    const dummyFile = new File(['content'], 'pack.zip', { type: 'application/zip' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [dummyFile] } });
    });

    const inspectBtn = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectBtn);
    });

    // 2. Verify multi-episode primary action "Analyze All Episodes (2)" is displayed prominently
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /analyze all episodes \(2\)/i })).toBeInTheDocument();
    });

    // Verify "Find Promos" is secondary
    const findPromosBtn = screen.getByRole('button', { name: /find promos \(ep 1\)/i });
    expect(findPromosBtn).toBeInTheDocument();

    // 3. Click the primary "Analyze All Episodes (2)" button
    const analyzeAllBtn = screen.getByRole('button', { name: /analyze all episodes \(2\)/i });
    await act(async () => {
      fireEvent.click(analyzeAllBtn);
    });

    // Verify auto-save was called
    expect(createRunSpy).toHaveBeenCalledTimes(1);
    expect(createRunSpy).toHaveBeenCalledWith(mockIngestResult.episodes, expect.stringContaining('Run:'));

    // Wait for the sequential batch run to complete
    await waitFor(() => {
      expect(analyzeEpisodeSpy).toHaveBeenCalledWith(savedRunId, 'ep1');
      expect(analyzeEpisodeSpy).toHaveBeenCalledWith(savedRunId, 'ep2');
    });

    // 4. Verify batch completion automatically opens the Show Top Promos view
    await waitFor(() => {
      expect(screen.getByText(/show-wide top promos: run: ep1/i)).toBeInTheDocument();
      expect(screen.getAllByText('Dramatic Entrance').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/high momentum and viral hook potential/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('aborts batch if automatic save run fails and presents error banner without losing uploaded scripts', async () => {
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue(mockIngestResult);

    vi.spyOn(api, 'createSavedRun').mockRejectedValue(new Error('Neon database connection timeout'));
    const analyzeEpisodeSpy = vi.spyOn(api, 'analyzeRunEpisode');

    render(<App />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const dummyFile = new File(['content'], 'pack.zip', { type: 'application/zip' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [dummyFile] } });
    });

    const inspectBtn = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /analyze all episodes \(2\)/i })).toBeInTheDocument();
    });

    const analyzeAllBtn = screen.getByRole('button', { name: /analyze all episodes \(2\)/i });
    await act(async () => {
      fireEvent.click(analyzeAllBtn);
    });

    // Verify error is shown and batch does not execute
    await waitFor(() => {
      expect(screen.getByText('Neon database connection timeout')).toBeInTheDocument();
    });
    expect(analyzeEpisodeSpy).not.toHaveBeenCalled();

    // Verify episodes are still visible
    expect(screen.getByRole('button', { name: /episode 1/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /episode 2/i })).toBeInTheDocument();
  });

  it('preserves user timeline view if user deliberately navigates to inspect an episode during batch run', async () => {
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue(mockIngestResult);

    const savedRunId = 'run_test_nav';
    vi.spyOn(api, 'createSavedRun').mockResolvedValue(
      buildRunDetail(savedRunId, 'pending', 'pending')
    );

    let getRunCalls = 0;
    vi.spyOn(api, 'getSavedRun').mockImplementation(async () => {
      getRunCalls++;
      if (getRunCalls === 1) {
        return buildRunDetail(savedRunId, 'pending', 'pending');
      } else if (getRunCalls === 2) {
        return buildRunDetail(savedRunId, 'completed', 'pending');
      } else {
        return buildRunDetail(savedRunId, 'completed', 'completed');
      }
    });

    let resolveEp1Promise!: (val: PromoAnalysisResponse) => void;
    const ep1InFlight = new Promise<PromoAnalysisResponse>((res) => {
      resolveEp1Promise = res;
    });

    vi.spyOn(api, 'analyzeRunEpisode').mockImplementation(async (_runId, epId) => {
      if (epId === 'ep1') {
        return ep1InFlight;
      }
      return mockAnalysisEp2;
    });

    render(<App />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const dummyFile = new File(['content'], 'pack.zip', { type: 'application/zip' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [dummyFile] } });
    });

    const inspectBtn = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /analyze all episodes \(2\)/i })).toBeInTheDocument();
    });

    const analyzeAllBtn = screen.getByRole('button', { name: /analyze all episodes \(2\)/i });
    await act(async () => {
      fireEvent.click(analyzeAllBtn);
    });

    // While batch is running (Ep 1 analysis in flight), user clicks Episode 2 to inspect timeline
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /episode 2/i })).toBeInTheDocument();
    });

    const ep2SidebarBtn = screen.getByRole('button', { name: /episode 2/i });
    await act(async () => {
      fireEvent.click(ep2SidebarBtn);
    });

    // Now resolve in-flight analysis
    await act(async () => {
      resolveEp1Promise(mockAnalysisEp1);
    });

    // Verify batch completes, but user stays on their selected episode view rather than being forced to show-ranking
    await waitFor(() => {
      expect(screen.getByText('INT. OFFICE - NIGHT')).toBeInTheDocument();
      expect(screen.queryByText(/show-wide top promos: run: ep1/i)).not.toBeInTheDocument();
    });
  });
});
