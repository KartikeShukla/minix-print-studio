import { mkdtempSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildAgentIntegrationPreview } from "../src/main/agentIntegrations";

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
});
