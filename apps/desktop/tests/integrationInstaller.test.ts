import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  installAgentIntegrationConfig,
  revertAgentIntegrationChange,
  uninstallAgentIntegrationConfig
} from "../src/main/integrationInstaller";

const codexContent = [
  "[mcp_servers.minix_print]",
  'command = "/Applications/MiniX/bin/minix-mcp"',
  "args = []",
  "[mcp_servers.minix_print.env]",
  'MINIX_DAEMON_RUNTIME_FILE = "/tmp/minix/runtime.json"',
  ""
].join("\n");

describe("agent integration config installer", () => {
  it("installs and uninstalls Codex config with backups and a managed block", () => {
    const root = makeTempRoot();
    const configPath = path.join(root.homeDir, ".codex", "config.toml");
    mkdirSync(path.dirname(configPath), { recursive: true });
    writeFileSync(configPath, 'model = "gpt-5"\n', "utf-8");

    const install = installAgentIntegrationConfig({
      targetId: "codex",
      configPath: "~/.codex/config.toml",
      content: codexContent,
      userDataPath: root.userDataPath,
      homeDir: root.homeDir,
      now: new Date("2026-06-05T00:00:00.000Z")
    });

    expect(install.targetPath).toBe(configPath);
    expect(install.existed).toBe(true);
    expect(existsSync(install.backupPath)).toBe(true);
    expect(readFileSync(install.backupPath, "utf-8")).toBe('model = "gpt-5"\n');
    expect(existsSync(install.manifestPath)).toBe(true);

    const installed = readFileSync(configPath, "utf-8");
    expect(installed).toContain('model = "gpt-5"');
    expect(installed).toContain("# BEGIN MiniX Print Studio MCP");
    expect(installed).toContain("MINIX_DAEMON_RUNTIME_FILE");
    expect(installed).not.toContain("MINIX_DAEMON_TOKEN");

    const uninstall = uninstallAgentIntegrationConfig({
      targetId: "codex",
      configPath: "~/.codex/config.toml",
      userDataPath: root.userDataPath,
      homeDir: root.homeDir,
      now: new Date("2026-06-05T00:01:00.000Z")
    });

    expect(readFileSync(configPath, "utf-8")).toBe('model = "gpt-5"\n');

    revertAgentIntegrationChange({ manifestPath: uninstall.manifestPath });

    expect(readFileSync(configPath, "utf-8")).toContain("# BEGIN MiniX Print Studio MCP");
  });

  it("merges and removes Claude Desktop JSON while preserving other servers", () => {
    const root = makeTempRoot();
    const configPath = path.join(
      root.homeDir,
      "Library",
      "Application Support",
      "Claude",
      "claude_desktop_config.json"
    );
    mkdirSync(path.dirname(configPath), { recursive: true });
    writeFileSync(
      configPath,
      JSON.stringify(
        {
          mcpServers: {
            "other-server": {
              type: "stdio",
              command: "/usr/local/bin/other",
              args: [],
              env: {}
            }
          }
        },
        null,
        2
      ),
      "utf-8"
    );

    installAgentIntegrationConfig({
      targetId: "claude-desktop",
      configPath: "~/Library/Application Support/Claude/claude_desktop_config.json",
      content: JSON.stringify({
        mcpServers: {
          "minix-print": {
            type: "stdio",
            command: "/Applications/MiniX/bin/minix-mcp",
            args: [],
            env: {
              MINIX_DAEMON_RUNTIME_FILE: "/tmp/minix/runtime.json"
            }
          }
        }
      }),
      userDataPath: root.userDataPath,
      homeDir: root.homeDir,
      now: new Date("2026-06-05T00:02:00.000Z")
    });

    const installed = JSON.parse(readFileSync(configPath, "utf-8")) as {
      mcpServers: Record<string, unknown>;
    };
    expect(Object.keys(installed.mcpServers).sort()).toEqual(["minix-print", "other-server"]);
    expect(JSON.stringify(installed)).not.toContain("MINIX_DAEMON_TOKEN");

    uninstallAgentIntegrationConfig({
      targetId: "claude-desktop",
      configPath: "~/Library/Application Support/Claude/claude_desktop_config.json",
      userDataPath: root.userDataPath,
      homeDir: root.homeDir,
      now: new Date("2026-06-05T00:03:00.000Z")
    });

    const uninstalled = JSON.parse(readFileSync(configPath, "utf-8")) as {
      mcpServers: Record<string, unknown>;
    };
    expect(Object.keys(uninstalled.mcpServers)).toEqual(["other-server"]);
  });
});

function makeTempRoot(): { homeDir: string; userDataPath: string } {
  const root = mkdtempSync(path.join(os.tmpdir(), "minix-installer-"));
  return {
    homeDir: path.join(root, "home"),
    userDataPath: path.join(root, "user-data")
  };
}
