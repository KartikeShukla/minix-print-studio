import { describe, expect, it } from "vitest";
import {
  createDefaultDocument,
  createQrElement,
  createRectElement,
  createTextElement,
  moveElement,
  printDocumentSchema,
  qrElementSchema,
  rectElementSchema,
  textElementSchema,
  updateElement
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

  it("creates a typed thermal rectangle element with stable defaults", () => {
    const element = rectElementSchema.parse(
      createRectElement({
        id: "el_rule",
        name: "Rule",
        x: 24,
        y: 144,
        width: 336,
        height: 64
      })
    );

    expect(element.type).toBe("rect");
    expect(element.fill).toBe("#000000");
    expect(element.width).toBe(336);
    expect(element.height).toBe(64);
  });

  it("creates a typed thermal QR element with stable defaults", () => {
    const element = qrElementSchema.parse(
      createQrElement({
        id: "el_qr",
        name: "Support URL",
        payload: "https://example.com/support",
        x: 120,
        y: 220,
        size: 128
      })
    );

    expect(element.type).toBe("qr");
    expect(element.payload).toBe("https://example.com/support");
    expect(element.width).toBe(128);
    expect(element.height).toBe(128);
    expect(element.errorCorrectionLevel).toBe("M");
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

  it("updates an element immutably and bumps updatedAt", () => {
    const document = createDefaultDocument({
      title: "Inspector fixture",
      now: new Date("2026-06-04T00:00:00.000Z")
    });
    const rule = createRectElement({
      id: "el_rule",
      name: "Rule",
      x: 24,
      y: 144,
      width: 336,
      height: 64
    });
    const withElement = {
      ...document,
      elements: [rule]
    };

    const updated = updateElement(
      withElement,
      "el_rule",
      (element) => ({
        ...element,
        x: 40,
        width: 300,
        fill: "#ffffff"
      }),
      { now: new Date("2026-06-04T00:10:00.000Z") }
    );

    expect(withElement.elements[0]).toMatchObject({
      x: 24,
      width: 336,
      fill: "#000000"
    });
    expect(updated.elements[0]).toMatchObject({
      x: 40,
      width: 300,
      fill: "#ffffff"
    });
    expect(updated.updatedAt).toBe("2026-06-04T00:10:00.000Z");
  });
});
