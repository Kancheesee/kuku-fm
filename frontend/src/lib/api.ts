import {
  Episode,
  HealthResponse,
  IngestPreviewResponse,
  PromoAnalysisResponse,
  RunDetail,
  RunSummary,
  ShowWideRankingResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

export class ApiError extends Error {
  status: number;
  isQuotaExceeded: boolean;
  isConflict: boolean;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.isQuotaExceeded = status === 429 || message.toLowerCase().includes('quota');
    this.isConflict = status === 409;
  }
}

export async function checkBackendHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/api/health`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Health check failed with HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function initSession(): Promise<{ active: boolean }> {
  const resp = await fetch(`${API_BASE}/api/session`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Session initialization failed with HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function uploadScriptsForPreview(files: File[]): Promise<IngestPreviewResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const resp = await fetch(`${API_BASE}/api/ingest/preview`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!resp.ok) {
    let errorDetail = `Ingestion failed with HTTP ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // fallback to status text
    }
    throw new ApiError(errorDetail, resp.status);
  }

  return resp.json();
}

export async function analyzeEpisodePromos(
  episode: Episode,
  maxCandidates: number = 5,
): Promise<PromoAnalysisResponse> {
  const resp = await fetch(`${API_BASE}/api/promos/analyze`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      episode,
      max_candidates: maxCandidates,
    }),
  });

  if (!resp.ok) {
    let errorDetail = `Promo discovery failed with HTTP ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, resp.status);
  }

  return resp.json();
}

// Milestone 3 Run Management & Persistence APIs
export async function createSavedRun(
  episodes: Episode[],
  name?: string,
): Promise<RunDetail> {
  const resp = await fetch(`${API_BASE}/api/runs`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      name,
      episodes,
      metadata: { client: 'web-frontend', created_at: new Date().toISOString() },
    }),
  });

  if (!resp.ok) {
    let detail = `Failed to create run: HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j && j.detail) detail = j.detail;
    } catch {}
    throw new ApiError(detail, resp.status);
  }
  return resp.json();
}

export async function listSavedRuns(): Promise<RunSummary[]> {
  const resp = await fetch(`${API_BASE}/api/runs`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Failed to list saved runs: HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function getSavedRun(runId: string): Promise<RunDetail> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Failed to fetch run ${runId}: HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function analyzeRunEpisode(
  runId: string,
  episodeId: string,
): Promise<PromoAnalysisResponse> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}/episodes/${episodeId}/analyze`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    let detail = `Failed to analyze episode: HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j && j.detail) detail = j.detail;
    } catch {}
    throw new ApiError(detail, resp.status);
  }
  return resp.json();
}

export async function pauseSavedRun(runId: string): Promise<RunDetail> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}/pause`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Failed to pause run: HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function resumeSavedRun(runId: string): Promise<RunDetail> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}/resume`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Failed to resume run: HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}

export async function retryRunEpisode(
  runId: string,
  episodeId: string,
): Promise<PromoAnalysisResponse> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}/episodes/${episodeId}/retry`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    let detail = `Failed to retry episode: HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j && j.detail) detail = j.detail;
    } catch {}
    throw new ApiError(detail, resp.status);
  }
  return resp.json();
}

export async function getRunShowRanking(runId: string): Promise<ShowWideRankingResponse> {
  const resp = await fetch(`${API_BASE}/api/runs/${runId}/ranking`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new ApiError(`Failed to fetch show rankings: HTTP ${resp.status}`, resp.status);
  }
  return resp.json();
}
