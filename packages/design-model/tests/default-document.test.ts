import { describe, expect, it } from "vitest";
import {
  createDefaultDocument,
  createTextElement,
  moveElement,
  printDocumentSchema,
  textElementSchema
} from "../src/index";

describe("default print document", () => {
  it("creates a versioned continuous-paper document for the MiniX profile", () => {
    const document = printDocumentSchema.parse(
      createDefaultDocument({
        title: "Quick note"
      })
    );

    expect(document.schemaVersion).toBe(1);
    expect(document.title).toBe("Quick note");
    expect(document.target.profileId).toBe("seznik-minix-s1-lyin48d-gy");
    expect(document.target.widthDots).toBe(384);
    expect(document.target.heightDots).toBe(900);
    expect(document.target.paperMode).toBe("continuous");
    expect(document.elements).toEqual([]);
  });

  it("creates a typed thermal text element with stable defaults", () => {
    const element = textElementSchema.parse(
      createTextElement({
        id: "el_note",
        name: "Note",
        text: "Hello thermal world",
        x: 24,
        y: 56,
        width: 336,
        height: 80
      })
    );

    expect(element.type).toBe("text");
    expect(element.style.fontFamily).toBe("Inter");
    expect(element.style.fontSize).toBe(28);
    expect(element.style.align).toBe("center");
  });

  it("moves an element immutably and bumps updatedAt", () => {
    const document = createDefaultDocument({
      title: "Move fixture",
      now: new Date("2026-06-04T00:00:00.000Z")
    });
    const text = createTextElement({
      id: "el_move",
      name: "Move me",
      text: "Move me",
      x: 24,
      y: 56,
      width: 160,
      height: 48
    });
    const withElement = {
      ...document,
      elements: [text]
    };

    const moved = moveElement(withElement, "el_move", {
      x: 48,
      y: 96,
      now: new Date("2026-06-04T00:05:00.000Z")
    });

    expect(withElement.elements[0].x).toBe(24);
    expect(moved.elements[0].x).toBe(48);
    expect(moved.elements[0].y).toBe(96);
    expect(moved.updatedAt).toBe("2026-06-04T00:05:00.000Z");
  });
});
