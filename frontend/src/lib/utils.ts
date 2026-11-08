import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMsToTimestamp(ms: number): string {
  if (ms < 0) return '00:00.00';
  const totalSeconds = ms / 1000;
  const hours = Math.floor(totalSeconds / 3600);
  const remaining = totalSeconds % 3600;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;

  const pad = (n: number) => n.toString().padStart(2, '0');
  const secStr = seconds.toFixed(2).padStart(5, '0');

  if (hours > 0) {
    return `${pad(hours)}:${pad(minutes)}:${secStr}`;
  }
  return `${pad(minutes)}:${secStr}`;
}

export function formatDurationHuman(ms: number): string {
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

