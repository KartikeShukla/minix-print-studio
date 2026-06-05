import { printDocumentSchema, type PrintDocument } from "@minix/design-model";

export const STORAGE_KEY = "minix.printStudio.currentDocument.v1";
export const PROJECT_SESSION_STORAGE_KEY = "minix.printStudio.projectSession.v1";

export type StoredProjectSession = {
  activeProjectId: string;
};

export function loadStoredDocument(storage: Storage = window.localStorage): PrintDocument | null {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return printDocumentSchema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveStoredDocument(
  document: PrintDocument,
  storage: Storage = window.localStorage
): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(document));
}

export function loadStoredProjectSession(
  storage: Storage = window.localStorage
): StoredProjectSession | null {
  const raw = storage.getItem(PROJECT_SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    const activeProjectId = (value as { activeProjectId?: unknown }).activeProjectId;
    if (typeof activeProjectId !== "string" || activeProjectId.length === 0) {
      return null;
    }
    return { activeProjectId };
  } catch {
    return null;
  }
}

export function saveStoredProjectSession(
  activeProjectId: string,
  storage: Storage = window.localStorage
): void {
  storage.setItem(PROJECT_SESSION_STORAGE_KEY, JSON.stringify({ activeProjectId }));
}

export function clearStoredProjectSession(storage: Storage = window.localStorage): void {
  storage.removeItem(PROJECT_SESSION_STORAGE_KEY);
}
