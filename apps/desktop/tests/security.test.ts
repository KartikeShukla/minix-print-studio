import { describe, expect, it } from "vitest";
import { buildSecureWebPreferences } from "../src/main/security";

describe("Electron security defaults", () => {
  it("disables Node access and enables isolation for the renderer", () => {
    expect(buildSecureWebPreferences("/tmp/preload.js")).toMatchObject({
      preload: "/tmp/preload.js",
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true
    });
  });
});
