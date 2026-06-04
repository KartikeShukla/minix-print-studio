import { createDefaultDocument } from "@minix/design-model";
import { describe, expect, it } from "vitest";
import {
  loadStoredDocument,
  saveStoredDocument,
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
});
