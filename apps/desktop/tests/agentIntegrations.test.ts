import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildAgentIntegrationPreview,
  testAgentIntegrationConnection
} from "../src/main/agentIntegrations";

describe("agent integration previews", () => {
  it("builds copyable MCP configs from the stable shim and runtime handoff paths", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));

    const preview = buildAgentIntegrationPreview({ userDataPath });

    expect(preview.shimPath).toBe(path.join(userDataPath, "bin", "minix-mcp"));
    expect(preview.runtimeFilePath).toBe(path.join(userDataPath, "runtime", "runtime.json"));
    expect(preview.targets.map((target) => target.id)).toEqual([
      "codex",
      "claude-desktop",
      "claude-code",
      "opencode",
      "generic-stdio"
    ]);
    expect(preview.targets.filter((target) => target.installable).map((target) => target.id)).toEqual([
      "codex",
      "claude-desktop",
      "opencode"
    ]);
    expect(preview.targets.find((target) => target.id === "claude-desktop")).toEqual(
      expect.objectContaining({
        exportable: true
      })
    );
    expect(preview.targets[0]).toEqual(
      expect.objectContaining({
        id: "codex",
        name: "Codex",
        configPath: "~/.codex/config.toml",
        format: "toml",
        content: expect.stringContaining("MINIX_DAEMON_RUNTIME_FILE")
      })
    );
    expect(JSON.stringify(preview)).not.toContain("token_");
    expect(JSON.stringify(preview)).not.toContain("MINIX_DAEMON_TOKEN");
  });

  it("checks connection prerequisites through the stable shim and runtime handoff", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const repoRoot = mkdtempSync(path.join(os.tmpdir(), "minix-repo-"));
    const runtimeDir = path.join(userDataPath, "runtime");
    mkdirSync(runtimeDir, { recursive: true });
    writeFileSync(
      path.join(runtimeDir, "runtime.json"),
      JSON.stringify({
        version: 1,
        pid: 123,
        baseUrl: "http://127.0.0.1:39281",
        tokenFile: path.join(runtimeDir, "token"),
        startedAt: "2026-06-05T00:00:00.000Z",
        mock: true
      }),
      "utf-8"
    );

    const result = testAgentIntegrationConnection({
      targetId: "codex",
      userDataPath,
      repoRoot,
      now: new Date("2026-06-05T00:01:00.000Z")
    });

    expect(result).toEqual(
      expect.objectContaining({
        ok: true,
        targetId: "codex",
        shimPath: path.join(userDataPath, "bin", "minix-mcp"),
        runtimeFilePath: path.join(runtimeDir, "runtime.json"),
        checkedAt: "2026-06-05T00:01:00.000Z"
      })
    );
  });
});
