export type EventCategory = 'camera' | 'action' | 'dialogue' | 'sound_effect' | 'unknown';

export type IssueSeverity = 'warning' | 'error';

export interface ParsingIssue {
  severity: IssueSeverity;
  code: string;
  message: string;
  line?: number | null;
  line_end?: number | null;
}

export interface Event {
  id: string;
  scene_id: string;
  category: EventCategory;
  original_label: string;
  speaker?: string | null;
  delivery_notes?: string | null;
  start_ms: number;
  end_ms: number;
  text: string;
  line_start: number;
  line_end: number;
}

export interface Scene {
  id: string;
  scene_label: string;
  heading: string;
  start_ms: number;
  end_ms: number;
  line_start: number;
  line_end: number;
}

export interface Episode {
  id: string;
  episode_number?: number | null;
  filename: string;
  logline?: string | null;
  continuity_notes?: string | null;
  duration_ms: number;
  scenes: Scene[];
  events: Event[];
  warnings: ParsingIssue[];
  content_hash: string;
  parser_version: string;
}

export interface IngestFileResult {
  filename: string;
  success: boolean;
  episode?: Episode | null;
  issues: ParsingIssue[];
}

export interface IngestPreviewResponse {
  episodes: Episode[];
  total_episodes: number;
  total_runtime_ms: number;
  total_events: number;
  total_issues: number;
  ignored_files_count: number;
  file_results: IngestFileResult[];
}

export interface HealthResponse {
  status: 'ok';
  version: string;
  database_connected: boolean;
}
