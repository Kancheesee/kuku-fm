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

// Milestone 2 Promo Discovery Schemas
export interface PromoSegment {
  episode_id: string;
  episode_number?: number | null;
  filename: string;
  source_content_hash: string;
  start_ms: number;
  end_ms: number;
  start_timestamp: string;
  end_timestamp: string;
  duration_ms: number;
  duration_seconds: number;
  event_ids: string[];
  events: Event[];
}

export interface EditorialRubricScore {
  opening_strength: number;
  standalone_clarity: number;
  escalation_stakes: number;
  unresolved_ending: number;
  opening_reason: string;
  clarity_reason: string;
  stakes_reason: string;
  ending_reason: string;
  grounded_unresolved_question?: string | null;
  uncertainty_or_weakness?: string | null;
  overall_score: number;
}

export interface PromoCandidate {
  id: string;
  rank: number;
  editorial_title: string;
  episode_number?: number | null;
  filename: string;
  source_content_hash: string;
  segment: PromoSegment;
  hook_explanation: string;
  hook_event_ids: string[];
  cliffhanger_explanation: string;
  cliffhanger_event_ids: string[];
  unresolved_question: string;
  rationale: string;
  standalone_assessment: string;
  editorial_risks: string[];
  assessment_status?: 'assessed' | 'unavailable';
  rubric?: EditorialRubricScore | null;
  review_flags: string[];
  mechanical_status: 'passed' | 'warning';
}

export interface RawCandidateProposal {
  editorial_title: string;
  start_event_id: string;
  end_event_id: string;
  hook_explanation: string;
  hook_event_ids: string[];
  cliffhanger_explanation: string;
  cliffhanger_event_ids: string[];
  unresolved_question: string;
  rationale: string;
  standalone_assessment: string;
  editorial_risks: string[];
}

export interface RejectedProposal {
  proposal: RawCandidateProposal;
  rejection_reasons: string[];
  rejection_codes: string[];
}

export interface PromoAnalysisResponse {
  episode_id: string;
  episode_number?: number | null;
  filename: string;
  source_content_hash: string;
  parser_version: string;
  prompt_version: string;
  assessment_prompt_version: string;
  model: string;
  cache_key: string;
  candidates: PromoCandidate[];
  rejected_proposals: RejectedProposal[];
  suppressed_candidates: PromoCandidate[];
  metadata: Record<string, any>;
  raw_generation_response: string;
  raw_assessment_response?: string | null;
  raw_model_response?: string;
}
