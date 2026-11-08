import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, FolderArchive, ArrowRight, ShieldCheck, AlertTriangle } from 'lucide-react';

interface EmptyStateProps {
  onFilesSelected: (files: File[]) => void;
  isLoading: boolean;
  errorMessage: string | null;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  onFilesSelected,
  isLoading,
  errorMessage,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFileList, setSelectedFileList] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      setSelectedFileList(files);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      setSelectedFileList(files);
    }
  };

  const triggerFilePicker = () => {
    fileInputRef.current?.click();
  };

  const handleInspectClick = () => {
    if (selectedFileList.length > 0) {
      onFilesSelected(selectedFileList);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-12 px-6">
      {/* Intro section */}
      <div className="text-center mb-8">
        <span className="inline-block text-xs font-semibold tracking-wider uppercase text-burnt-700 bg-burnt-50 border border-burnt-200 px-2.5 py-1 rounded-full mb-3">
          Microdrama Promo Studio
        </span>
        <h2 className="text-3xl font-serif font-bold text-charcoal tracking-tight sm:text-4xl">
          Find the moments worth watching.
        </h2>
        <p className="mt-3 text-sm text-charcoal-muted max-w-xl mx-auto leading-relaxed">
          Kuku Promo Studio parses timestamped screenplays, checks timeline integrity across dialogue, camera, and action events, and prepares clean structural evidence for viral promo discovery.
        </p>
      </div>

      {errorMessage && (
        <div className="mb-6 p-4 rounded-lg bg-amber-50 border border-amber-200 flex items-start space-x-3 text-sm text-amber-900">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Unable to process upload</p>
            <p className="text-xs text-amber-800 mt-0.5">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Main Upload Dropzone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={triggerFilePicker}
        className={`relative border-2 border-dashed rounded-xl p-8 sm:p-12 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-burnt-600 bg-burnt-50/50 scale-[1.01]'
            : 'border-paper-400 bg-paper-50 hover:bg-paper-200/50 hover:border-charcoal-subtle'
        }`}
        tabIndex={0}
        role="button"
        aria-label="Upload screenplay files or ZIP archives"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            triggerFilePicker();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".txt,.zip"
          onChange={handleFileInputChange}
          className="hidden"
          id="screenplay-file-input"
        />

        <div className="w-14 h-14 mx-auto rounded-full bg-paper-200 flex items-center justify-center text-burnt-700 border border-paper-300 mb-4 shadow-sm">
          <UploadCloud className="w-7 h-7" />
        </div>

        <h3 className="text-base font-semibold text-charcoal mb-1">
          {selectedFileList.length > 0
            ? `${selectedFileList.length} file(s) queued for inspection`
            : 'Drag and drop screenplay files here'}
        </h3>
        <p className="text-xs text-charcoal-muted max-w-md mx-auto mb-4">
          Upload individual <code className="bg-paper-200 px-1 py-0.5 rounded text-charcoal">.txt</code> episodes, multiple scripts, or a full season <code className="bg-paper-200 px-1 py-0.5 rounded text-charcoal">.zip</code> pack.
        </p>

        {/* Selected files preview pill */}
        {selectedFileList.length > 0 ? (
          <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-md bg-paper-200 border border-paper-300 text-xs text-charcoal max-w-md truncate">
            {selectedFileList[0].name.endsWith('.zip') ? (
              <FolderArchive className="w-4 h-4 text-burnt-700 flex-shrink-0" />
            ) : (
              <FileText className="w-4 h-4 text-burnt-700 flex-shrink-0" />
            )}
            <span className="truncate font-medium">{selectedFileList[0].name}</span>
            {selectedFileList.length > 1 && (
              <span className="text-charcoal-muted font-normal">
                +{selectedFileList.length - 1} more
              </span>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              triggerFilePicker();
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-md bg-paper-200 hover:bg-paper-300 border border-paper-300 text-xs font-semibold text-charcoal transition-colors focus:ring-2 focus:ring-burnt-600 focus:outline-none"
          >
            <span>Choose files from disk</span>
          </button>
        )}
      </div>

      {/* Primary Action Button */}
      <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-charcoal-subtle flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>Safe decompression limits (50MB ZIP / 500 members). macOS metadata ignored.</span>
        </div>

        <button
          onClick={handleInspectClick}
          disabled={selectedFileList.length === 0 || isLoading}
          className={`w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-burnt-600 focus:ring-offset-2 ${
            selectedFileList.length === 0 || isLoading
              ? 'bg-paper-300 text-charcoal-subtle cursor-not-allowed border border-paper-400'
              : 'bg-burnt-700 hover:bg-burnt-800 text-white active:scale-[0.99]'
          }`}
        >
          {isLoading ? (
            <span>Parsing Screenplays...</span>
          ) : (
            <>
              <span>Inspect scripts</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>

      {/* Supported formats and expectations footer */}
      <div className="mt-12 pt-6 border-t border-paper-300 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-charcoal-muted">
        <div className="p-3 bg-paper-50 rounded border border-paper-300">
          <p className="font-semibold text-charcoal mb-0.5">Timestamp Standards</p>
          <p className="text-[11px] text-charcoal-subtle">
            Integer millisecond parsing for scene starts, ends, camera bounds, and speech durations.
          </p>
        </div>
        <div className="p-3 bg-paper-50 rounded border border-paper-300">
          <p className="font-semibold text-charcoal mb-0.5">Timeline Verification</p>
          <p className="text-[11px] text-charcoal-subtle">
            Flags out-of-bounds events, inverted timestamps, and malformed markers without data loss.
          </p>
        </div>
        <div className="p-3 bg-paper-50 rounded border border-paper-300">
          <p className="font-semibold text-charcoal mb-0.5">Safe Local Inspection</p>
          <p className="text-[11px] text-charcoal-subtle">
            Zero external AI or database dependencies required to preview and inspect scripts locally.
          </p>
        </div>
      </div>
    </div>
  );
};

