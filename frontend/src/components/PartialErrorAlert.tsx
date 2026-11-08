import React from 'react';
import { IngestFileResult } from '../types';
import { AlertCircle, AlertTriangle } from 'lucide-react';

interface PartialErrorAlertProps {
  fileResults: IngestFileResult[];
  onDismiss: () => void;
}

export const PartialErrorAlert: React.FC<PartialErrorAlertProps> = ({
  fileResults,
  onDismiss,
}) => {
  const failedFiles = fileResults.filter((f) => !f.success);
  const filesWithIssues = fileResults.filter((f) => f.success && f.issues.length > 0);

  if (failedFiles.length === 0 && filesWithIssues.length === 0) {
    return null;
  }

  return (
    <div className="bg-paper-50 border-b border-paper-300 px-6 py-3">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-start space-x-2.5">
          {failedFiles.length > 0 ? (
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          )}
          <div className="text-xs">
            <span className="font-semibold text-charcoal">
              {failedFiles.length > 0
                ? `${failedFiles.length} file(s) failed ingestion`
                : `Batch completed with ${filesWithIssues.length} file(s) reporting timeline diagnostics`}
            </span>
            <div className="text-[11px] text-charcoal-muted mt-0.5">
              {failedFiles.map((f) => `${f.filename}: ${f.issues.map((i) => i.message).join(', ')}`).join(' • ')}
              {failedFiles.length === 0 &&
                filesWithIssues.slice(0, 3).map((f) => `${f.filename} (${f.issues.length} warnings)`).join(', ')}
              {filesWithIssues.length > 3 && ` and ${filesWithIssues.length - 3} more.`}
            </div>
          </div>
        </div>

        <button
          onClick={onDismiss}
          className="text-[11px] font-medium text-charcoal-subtle hover:text-charcoal px-2 py-1 rounded hover:bg-paper-200 transition-colors self-end sm:self-center"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};
