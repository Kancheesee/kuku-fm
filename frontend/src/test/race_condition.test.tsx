import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import App from '../App';
import * as api from '../lib/api';
import { Episode, IngestPreviewResponse, PromoAnalysisResponse } from '../types';

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
      text: 'Door swings open forcefully.',
      line_start: 2,
      line_end: 3,
    },
    {
      id: 'e2',
      scene_id: 's1',
      category: 'dialogue',
      speaker: 'HERO',
      original_label: '**HERO:**',
      start_ms: 5000,
      end_ms: 30000,
      text: '"It is over."',
      line_start: 4,
      line_end: 6,
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
      id: 'e3',
      scene_id: 's2',
      category: 'dialogue',
      speaker: 'VILLAIN',
      original_label: '**VILLAIN:**',
      start_ms: 0,
      end_ms: 32000,
      text: '"You will never stop me."',
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
  total_events: 3,
  total_issues: 0,
  ignored_files_count: 0,
  file_results: [
    { filename: 'ep1.txt', success: true, episode: mockEpisode1, issues: [] },
    { filename: 'ep2.txt', success: true, episode: mockEpisode2, issues: [] },
  ],
};

const mockEp1PromoResponse: PromoAnalysisResponse = {
  episode_id: 'ep1',
  episode_number: 1,
  filename: 'ep1.txt',
  source_content_hash: 'hash_ep1',
  parser_version: '1.0.0',
  prompt_version: '2.2.0',
  assessment_prompt_version: 'assessment_v1.0.0',
  model: 'gemini-3.5-flash-lite',
  cache_key: 'hash_ep1__1.0.0__gemini-3.5-flash-lite__p2.2.0__aassessment_v1.0.0__c5',
  candidates: [
    {
      id: 'promo_cand_ep1',
      rank: 1,
      editorial_title: 'Episode 1 Dramatic Reveal',
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
        event_ids: ['e1', 'e2'],
        events: mockEpisode1.events,
      },
      hook_explanation: 'Forceful door entrance hooks immediate visual attention.',
      hook_event_ids: ['e1'],
      cliffhanger_explanation: 'Cuts sharply on declaration of finality.',
      cliffhanger_event_ids: ['e2'],
      unresolved_question: 'Is it truly over or just beginning?',
      rationale: 'High momentum and clear conflict.',
      standalone_assessment: 'Fully understandable alone.',
      editorial_risks: [],
      assessment_status: 'assessed',
      rubric: {
        opening_strength: 5,
        standalone_clarity: 4,
        escalation_stakes: 4,
        unresolved_ending: 5,
        opening_reason: 'Dynamic hook',
        clarity_reason: 'Clear setup',
        stakes_reason: 'High stakes',
        ending_reason: 'Abrupt cliffhanger',
        overall_score: 4.55,
      },
      review_flags: [],
      mechanical_status: 'passed',
    },
  ],
  rejected_proposals: [],
  suppressed_candidates: [],
  metadata: {
    total_proposals_generated: 1,
    latency_ms: 450,
  },
  raw_generation_response: '{"candidates": []}',
  raw_assessment_response: '{"assessments": []}',
};

describe('Frontend Regression: Delayed async response and episode switching', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api, 'checkBackendHealth').mockResolvedValue({
      status: 'ok',
      version: '0.1.0',
      database_connected: true,
    });
  });

  it('prevents stale responses from hijacking selected episode and preserves saved result', async () => {
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue(mockIngestResult);

    // Controllable delayed promise for analyzeEpisodePromos
    let resolveEp1Analysis!: (res: PromoAnalysisResponse) => void;
    const ep1AnalysisPromise = new Promise<PromoAnalysisResponse>((resolve) => {
      resolveEp1Analysis = resolve;
    });

    const analyzeSpy = vi.spyOn(api, 'analyzeEpisodePromos').mockImplementation((ep) => {
      if (ep.id === 'ep1') {
        return ep1AnalysisPromise;
      }
      return Promise.reject(new Error('Unexpected episode analyzed'));
    });

    render(<App />);

    // 1. Ingest files to display episodes
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    const dummyFile = new File(['content'], 'scripts.txt', { type: 'text/plain' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [dummyFile] } });
    });

    const inspectButton = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectButton);
    });

    // Verify Episode 1 is initially loaded
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /episode 1/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /episode 2/i })).toBeInTheDocument();
    });

    // 2. Start Episode 1 promo analysis
    const findPromosButton = screen.getByRole('button', { name: /find promos/i });
    await act(async () => {
      fireEvent.click(findPromosButton);
    });

    expect(analyzeSpy).toHaveBeenCalledWith(expect.objectContaining({ id: 'ep1' }));

    // 3. Switch to Episode 2 while Episode 1 analysis is in flight
    const ep2SidebarButton = screen.getByRole('button', { name: /episode 2/i });
    await act(async () => {
      fireEvent.click(ep2SidebarButton);
    });

    // Verify Episode 2 is now the active selected episode in the timeline header
    expect(screen.getByText('INT. OFFICE - NIGHT')).toBeInTheDocument();
    expect(screen.getAllByText('"You will never stop me."').length).toBeGreaterThan(0);

    // 4. Resolve Episode 1 analysis in the background
    await act(async () => {
      resolveEp1Analysis(mockEp1PromoResponse);
    });

    // 5. Verify Episode 2 remains active and selected; NO Episode 1 promo hijacks view
    expect(screen.getByText('INT. OFFICE - NIGHT')).toBeInTheDocument();
    expect(screen.getAllByText('"You will never stop me."').length).toBeGreaterThan(0);
    expect(screen.queryByText('Episode 1 Dramatic Reveal')).not.toBeInTheDocument();

    // 6. Switch back to Episode 1 in the sidebar
    const ep1SidebarButton = screen.getByRole('button', { name: /episode 1/i });
    await act(async () => {
      fireEvent.click(ep1SidebarButton);
    });

    // Switch to Promo Candidates tab for Episode 1
    const promosTabButton = screen.getByRole('button', { name: /promo candidates/i });
    await act(async () => {
      fireEvent.click(promosTabButton);
    });

    // Verify Episode 1's saved result is immediately displayed!
    expect(screen.getAllByText('Episode 1 Dramatic Reveal').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/4\.5 \/ 5\.0/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Forceful door entrance hooks immediate visual attention/).length).toBeGreaterThanOrEqual(1);
  });

  it('discards in-flight promo analysis results when upload is replaced', async () => {
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue(mockIngestResult);

    let resolveEp1Analysis!: (res: PromoAnalysisResponse) => void;
    const ep1AnalysisPromise = new Promise<PromoAnalysisResponse>((resolve) => {
      resolveEp1Analysis = resolve;
    });

    vi.spyOn(api, 'analyzeEpisodePromos').mockImplementation(() => ep1AnalysisPromise);

    render(<App />);

    // Ingest first pack
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const dummyFile1 = new File(['content 1'], 'pack1.txt', { type: 'text/plain' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [dummyFile1] } });
    });
    const inspectBtn1 = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectBtn1);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /episode 1/i })).toBeInTheDocument();
    });

    // Start promo discovery for Ep 1
    const findPromosButton = screen.getByRole('button', { name: /find promos/i });
    await act(async () => {
      fireEvent.click(findPromosButton);
    });

    // In-flight request is now pending. Now replace the upload by clicking "New Batch"
    const newBatchButton = screen.getByRole('button', { name: /new batch/i });
    await act(async () => {
      fireEvent.click(newBatchButton);
    });

    // Ingest a brand new episode pack
    const newEpisode: Episode = {
      id: 'ep_new',
      episode_number: 99,
      filename: 'ep99.txt',
      content_hash: 'hash_ep99',
      duration_ms: 25000,
      parser_version: '1.0.0',
      scenes: [],
      events: [],
      warnings: [],
    };
    vi.spyOn(api, 'uploadScriptsForPreview').mockResolvedValue({
      episodes: [newEpisode],
      total_episodes: 1,
      total_runtime_ms: 25000,
      total_events: 0,
      total_issues: 0,
      ignored_files_count: 0,
      file_results: [{ filename: 'ep99.txt', success: true, episode: newEpisode, issues: [] }],
    });

    const newFileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const dummyFile2 = new File(['content 2'], 'pack2.txt', { type: 'text/plain' });
    await act(async () => {
      fireEvent.change(newFileInput, { target: { files: [dummyFile2] } });
    });
    const inspectBtn2 = screen.getByRole('button', { name: /inspect scripts/i });
    await act(async () => {
      fireEvent.click(inspectBtn2);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /episode 99/i })).toBeInTheDocument();
    });

    // Now resolve the stale in-flight request from the old upload
    await act(async () => {
      resolveEp1Analysis(mockEp1PromoResponse);
    });

    // Verify Episode 99 remains active and the stale candidate is NEVER displayed
    expect(screen.getByRole('button', { name: /episode 99/i })).toBeInTheDocument();
    expect(screen.queryByText('Episode 1 Dramatic Reveal')).not.toBeInTheDocument();
  });
});
