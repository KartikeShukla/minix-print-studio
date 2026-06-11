export const VERIFIED_PRINTER_STORAGE_KEY = "minix.printStudio.verifiedPrinter.v1";

export type StoredVerifiedPrinter = {
  deviceId: string;
  name: string | null;
  profileId: string | null;
  modelResponse: string | null;
  firmware: string | null;
  verifiedAt: string;
};

export function loadStoredVerifiedPrinter(
  storage: Storage = window.localStorage
): StoredVerifiedPrinter | null {
  const raw = storage.getItem(VERIFIED_PRINTER_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    const candidate = value as Partial<Record<keyof StoredVerifiedPrinter, unknown>>;
    if (
      typeof candidate.deviceId !== "string" ||
      candidate.deviceId.length === 0 ||
      typeof candidate.verifiedAt !== "string" ||
      candidate.verifiedAt.length === 0
    ) {
      return null;
    }
    return {
      deviceId: candidate.deviceId,
      name: nullableString(candidate.name),
      profileId: nullableString(candidate.profileId),
      modelResponse: nullableString(candidate.modelResponse),
      firmware: nullableString(candidate.firmware),
      verifiedAt: candidate.verifiedAt
    };
  } catch {
    return null;
  }
}

export function saveStoredVerifiedPrinter(
  printer: StoredVerifiedPrinter,
  storage: Storage = window.localStorage
): void {
  storage.setItem(VERIFIED_PRINTER_STORAGE_KEY, JSON.stringify(printer));
}

export function clearStoredVerifiedPrinter(storage: Storage = window.localStorage): void {
  storage.removeItem(VERIFIED_PRINTER_STORAGE_KEY);
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}
