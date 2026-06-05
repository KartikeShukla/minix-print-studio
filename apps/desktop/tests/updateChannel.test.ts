import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { getUpdateChannelState, setUpdateChannel } from "../src/main/updateChannel";

describe("desktop update channel", () => {
  it("persists beta channel selection while keeping unsigned auto-updates disabled", () => {
    const userDataPath = mkdtempSync(path.join(tmpdir(), "minix-update-channel-"));

    const initial = getUpdateChannelState({
      userDataPath,
      appVersion: "0.1.0",
      now: new Date("2026-06-05T00:10:00.000Z")
    });

    expect(initial.channel).toBe("stable");
    expect(initial.autoUpdate).toMatchObject({
      enabled: false,
      reason: "Auto-updates are disabled until signed release publishing is configured."
    });

    const beta = setUpdateChannel({
      userDataPath,
      channel: "beta",
      appVersion: "0.1.0",
      now: new Date("2026-06-05T00:11:00.000Z")
    });

    expect(beta.channel).toBe("beta");
    expect(beta.availableChannels).toEqual(["stable", "beta"]);
    expect(beta.updatedAt).toBe("2026-06-05T00:11:00.000Z");
    expect(beta.autoUpdate.enabled).toBe(false);
    expect(beta.autoUpdate.reason).toContain("signed release publishing");

    const persisted = JSON.parse(
      readFileSync(path.join(userDataPath, "settings", "update-channel.json"), "utf8")
    );
    expect(persisted).toEqual({
      channel: "beta",
      updatedAt: "2026-06-05T00:11:00.000Z"
    });
  });

  it("rejects unknown update channels", () => {
    const userDataPath = mkdtempSync(path.join(tmpdir(), "minix-update-channel-"));

    expect(() =>
      setUpdateChannel({
        userDataPath,
        channel: "nightly",
        appVersion: "0.1.0"
      })
    ).toThrow("Unsupported update channel: nightly");
  });
});
