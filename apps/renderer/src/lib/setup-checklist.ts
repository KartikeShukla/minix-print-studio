export const SETUP_CHECKLIST_STORAGE_KEY = "minix.printStudio.setupChecklist.v1";

export type StoredSetupChecklist = {
  dismissed: boolean;
};

export function loadSetupChecklistDismissed(storage: Storage = window.localStorage): boolean {
  const raw = storage.getItem(SETUP_CHECKLIST_STORAGE_KEY);
  if (!raw) {
    return false;
  }

  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    return (value as { dismissed?: unknown }).dismissed === true;
  } catch {
    return false;
  }
}

export function saveSetupChecklistDismissed(
  dismissed: boolean,
  storage: Storage = window.localStorage
): void {
  storage.setItem(SETUP_CHECKLIST_STORAGE_KEY, JSON.stringify({ dismissed }));
}
