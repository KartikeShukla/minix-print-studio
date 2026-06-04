import { describe, expect, it } from "vitest";
import { createDefaultDocument, printDocumentSchema } from "../src/index";

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
});
