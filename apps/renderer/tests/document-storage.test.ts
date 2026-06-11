import { createDefaultDocument } from "@minix/design-model";
import { describe, expect, it } from "vitest";
import {
  clearStoredProjectSession,
  loadStoredProjectSession,
  loadStoredDocument,
  PROJECT_SESSION_STORAGE_KEY,
  saveStoredDocument,
  saveStoredProjectSession,
  STORAGE_KEY
} from "../src/lib/document-storage";
import {
  loadSetupChecklistDismissed,
  saveSetupChecklistDismissed,
  SETUP_CHECKLIST_STORAGE_KEY
} from "../src/lib/setup-checklist";
import {
  clearStoredVerifiedPrinter,
  loadStoredVerifiedPrinter,
  saveStoredVerifiedPrinter,
  VERIFIED_PRINTER_STORAGE_KEY
} from "../src/lib/printer-selection";

describe("document storage", () => {
  it("round-trips a valid document through localStorage", () => {
    const document = createDefaultDocument({
      title: "Stored note",
      now: new Date("2026-06-04T00:00:00.000Z")
    });
    localStorage.clear();

    saveStoredDocument(document);

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}").title).toBe("Stored note");
    expect(loadStoredDocument()).toEqual(document);
  });

  it("ignores invalid stored JSON instead of hydrating a corrupt document", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 999 }));

    expect(loadStoredDocument()).toBeNull();
  });

  it("round-trips the remembered daemon project session", () => {
    localStorage.clear();

    saveStoredProjectSession("prj_saved");

    expect(JSON.parse(localStorage.getItem(PROJECT_SESSION_STORAGE_KEY) ?? "{}")).toEqual({
      activeProjectId: "prj_saved"
    });
    expect(loadStoredProjectSession()).toEqual({ activeProjectId: "prj_saved" });
  });

  it("ignores invalid project sessions and can clear the remembered project", () => {
    localStorage.setItem(PROJECT_SESSION_STORAGE_KEY, JSON.stringify({ activeProjectId: "" }));

    expect(loadStoredProjectSession()).toBeNull();

    saveStoredProjectSession("prj_clear");
    clearStoredProjectSession();

    expect(localStorage.getItem(PROJECT_SESSION_STORAGE_KEY)).toBeNull();
  });

  it("round-trips setup checklist dismissal", () => {
    localStorage.clear();

    expect(loadSetupChecklistDismissed()).toBe(false);

    saveSetupChecklistDismissed(true);

    expect(JSON.parse(localStorage.getItem(SETUP_CHECKLIST_STORAGE_KEY) ?? "{}")).toEqual({
      dismissed: true
    });
    expect(loadSetupChecklistDismissed()).toBe(true);

    localStorage.setItem(SETUP_CHECKLIST_STORAGE_KEY, "{");
    expect(loadSetupChecklistDismissed()).toBe(false);
  });

  it("round-trips the remembered verified printer selection", () => {
    localStorage.clear();

    saveStoredVerifiedPrinter({
      deviceId: "mock-minix-0194",
      name: "Seznik MiniX_0194_LE",
      profileId: "seznik-minix-s1-lyin48d-gy",
      modelResponse: "S1_LYiN48D_GY",
      firmware: "V1.9.11",
      verifiedAt: "2026-06-11T10:00:00.000Z"
    });

    expect(JSON.parse(localStorage.getItem(VERIFIED_PRINTER_STORAGE_KEY) ?? "{}")).toEqual({
      deviceId: "mock-minix-0194",
      name: "Seznik MiniX_0194_LE",
      profileId: "seznik-minix-s1-lyin48d-gy",
      modelResponse: "S1_LYiN48D_GY",
      firmware: "V1.9.11",
      verifiedAt: "2026-06-11T10:00:00.000Z"
    });
    expect(loadStoredVerifiedPrinter()).toEqual({
      deviceId: "mock-minix-0194",
      name: "Seznik MiniX_0194_LE",
      profileId: "seznik-minix-s1-lyin48d-gy",
      modelResponse: "S1_LYiN48D_GY",
      firmware: "V1.9.11",
      verifiedAt: "2026-06-11T10:00:00.000Z"
    });
  });

  it("ignores invalid verified printer selections and can clear them", () => {
    localStorage.setItem(VERIFIED_PRINTER_STORAGE_KEY, JSON.stringify({ deviceId: "" }));

    expect(loadStoredVerifiedPrinter()).toBeNull();

    saveStoredVerifiedPrinter({
      deviceId: "mock-minix-0194",
      name: null,
      profileId: null,
      modelResponse: null,
      firmware: null,
      verifiedAt: "2026-06-11T10:00:00.000Z"
    });
    clearStoredVerifiedPrinter();

    expect(localStorage.getItem(VERIFIED_PRINTER_STORAGE_KEY)).toBeNull();
  });
});
