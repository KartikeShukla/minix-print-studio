import { printDocumentSchema, type PrintDocument } from "@minix/design-model";

export const STORAGE_KEY = "minix.printStudio.currentDocument.v1";

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
