import { describe, expect, it } from "vitest";
import { buildBetaFeedbackDraft } from "../src/main/betaFeedback";

describe("desktop beta feedback draft", () => {
  it("builds a GitHub issue URL without leaking private support bundle paths", () => {
    const draft = buildBetaFeedbackDraft({
      appVersion: "0.1.0",
      platform: "darwin",
      now: new Date("2026-06-05T00:04:00.000Z"),
      supportBundlePath:
        "/Users/alice/Library/Application Support/MiniX Print Studio/support/minix-print-studio-support-2026-06-05T00-03-00-000Z.zip"
    });
    const targetUrl = new URL(draft.targetUrl);

    expect(targetUrl.origin).toBe("https://github.com");
    expect(targetUrl.pathname).toBe("/minix-print-studio/minix-print-studio/issues/new");
    expect(targetUrl.searchParams.get("template")).toBe("beta_feedback.yml");
    expect(targetUrl.searchParams.get("title")).toBe(
      "Beta feedback: MiniX Print Studio 0.1.0 on darwin"
    );
    expect(draft.body).toContain("App version: 0.1.0");
    expect(draft.body).toContain("Platform: darwin");
    expect(draft.body).toContain(
      "Support bundle: minix-print-studio-support-2026-06-05T00-03-00-000Z.zip"
    );
    expect(draft.body).not.toContain("/Users/alice");
    expect(targetUrl.searchParams.get("body")).toBe(draft.body);
  });
});
