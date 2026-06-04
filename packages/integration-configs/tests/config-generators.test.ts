import { describe, expect, it } from "vitest";
import {
  buildClaudeDesktopConfig,
  buildClaudeCodeAddJsonCommand,
  buildCodexConfigToml,
  buildGenericMcpConfig,
  buildOpenCodeConfig
} from "../src/index";

const shimPath = "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp";

describe("MCP integration config generators", () => {
  it("generates Codex TOML with a stable stdio shim command", () => {
    expect(buildCodexConfigToml(shimPath)).toContain(
      'command = "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp"'
    );
  });

  it("generates Claude Desktop JSON without raw BLE permissions", () => {
    const config = buildClaudeDesktopConfig(shimPath);

    expect(config.mcpServers["minix-print"]).toEqual({
      type: "stdio",
      command: shimPath,
      args: [],
      env: {}
    });
  });

  it("generates Claude Code add-json command with shell-safe JSON", () => {
    expect(buildClaudeCodeAddJsonCommand(shimPath)).toBe(
      "claude mcp add-json minix-print '{\"type\":\"stdio\",\"command\":\"/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp\",\"args\":[],\"env\":{}}'"
    );
  });

  it("generates OpenCode local MCP config", () => {
    expect(buildOpenCodeConfig(shimPath).mcp["minix-print"]).toEqual({
      type: "local",
      command: [shimPath],
      enabled: true,
      timeout: 15000,
      environment: {}
    });
  });

  it("generates a generic stdio config", () => {
    expect(buildGenericMcpConfig(shimPath)).toEqual({
      type: "stdio",
      command: shimPath,
      args: [],
      env: {}
    });
  });
});
