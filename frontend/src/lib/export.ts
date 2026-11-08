import { PromoAnalysisResponse, PromoCandidate } from '../types';

export function exportShortlistCsv(
  candidates: PromoCandidate[],
  episodeNumber?: number | null,
) {
  const headers = [
    'Rank',
    'Editorial Title',
    'Episode',
    'Filename',
    'Source Content Hash',
    'Start Timestamp',
    'End Timestamp',
    'Duration (s)',
    'Overall Score (1-5)',
    'Opening 3s Hook Score',
    'Opening 3s Hook Description',
    'Cliffhanger Score',
    'Cliffhanger Description',
    'Unresolved Question',
    'Rationale',
    'Standalone Assessment',
    'Editorial Risks',
    'Review Flags',
  ];

  const escapeCsv = (val: string | number | null | undefined) => {
    if (val === null || val === undefined) return '""';
    const s = String(val).replace(/"/g, '""');
    return `"${s}"`;
  };

  const rows = candidates.map((c) => [
    escapeCsv(c.rank),
    escapeCsv(c.editorial_title),
    escapeCsv(c.episode_number ?? c.segment.episode_number ?? episodeNumber ?? 'Unknown'),
    escapeCsv(c.filename || c.segment.filename || 'Unknown'),
    escapeCsv(c.source_content_hash || c.segment.source_content_hash || 'Unknown'),
    escapeCsv(c.segment.start_timestamp),
    escapeCsv(c.segment.end_timestamp),
    escapeCsv(c.segment.duration_seconds),
    escapeCsv(c.rubric ? c.rubric.overall_score : 'Unavailable'),
    escapeCsv(c.rubric ? c.rubric.opening_strength : 'Unavailable'),
    escapeCsv(c.hook_explanation),
    escapeCsv(c.rubric ? c.rubric.unresolved_ending : 'Unavailable'),
    escapeCsv(c.cliffhanger_explanation),
    escapeCsv(c.unresolved_question),
    escapeCsv(c.rationale),
    escapeCsv(c.standalone_assessment),
    escapeCsv(c.editorial_risks.join('; ')),
    escapeCsv(c.review_flags.join('; ')),
  ]);

  const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `episode_${episodeNumber ?? 'unknown'}_promo_shortlist.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function exportRawAuditJson(response: PromoAnalysisResponse) {
  const jsonContent = JSON.stringify(response, null, 2);
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `episode_${response.episode_number ?? 'unknown'}_raw_audit.json`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

