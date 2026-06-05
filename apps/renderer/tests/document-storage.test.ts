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
});
