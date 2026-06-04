import type { PrintJobResponse } from "@minix/shared-api";

export const JOB_HISTORY_STORAGE_KEY = "minix.printStudio.jobHistory.v1";

export type StoredPrintJob = PrintJobResponse & {
  printedAt: string;
};

const MAX_STORED_JOBS = 20;

export function loadStoredJobHistory(storage: Storage = window.localStorage): StoredPrintJob[] {
  const raw = storage.getItem(JOB_HISTORY_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isStoredPrintJob);
  } catch {
    return [];
  }
}

export function saveStoredJobHistory(
  jobs: StoredPrintJob[],
  storage: Storage = window.localStorage
): void {
  storage.setItem(JOB_HISTORY_STORAGE_KEY, JSON.stringify(jobs.slice(0, MAX_STORED_JOBS)));
}

export function prependStoredPrintJob(
  history: StoredPrintJob[],
  job: PrintJobResponse,
  printedAt: string = new Date().toISOString()
): StoredPrintJob[] {
  return [{ ...job, printedAt }, ...history.filter((item) => item.jobId !== job.jobId)].slice(
    0,
    MAX_STORED_JOBS
  );
}

function isStoredPrintJob(value: unknown): value is StoredPrintJob {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<StoredPrintJob>;
  return (
    typeof candidate.jobId === "string" &&
    typeof candidate.previewId === "string" &&
    typeof candidate.planId === "string" &&
    typeof candidate.state === "string" &&
    typeof candidate.completionLevel === "string" &&
    typeof candidate.printedAt === "string"
  );
}
