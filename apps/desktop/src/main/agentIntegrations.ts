import path from "node:path";
import {
  buildClaudeCodeAddJsonCommand,
  buildClaudeDesktopConfig,
  buildCodexConfigToml,
  buildGenericMcpConfig,
  buildOpenCodeConfig,
  type McpRuntimeHandoffOptions
} from "@minix/integration-configs";
import { getRuntimeHandoffPaths } from "./runtimeHandoff";

export type AgentIntegrationTargetId =
  | "codex"
  | "claude-desktop"
  | "claude-code"
  | "opencode"
  | "generic-stdio";

export type AgentIntegrationPreviewTarget = {
  id: AgentIntegrationTargetId;
  name: string;
  configPath: string;
  format: "json" | "shell" | "toml";
  installable: boolean;
  content: string;
};

export type AgentIntegrationPreview = {
  shimPath: string;
  runtimeFilePath: string;
  targets: AgentIntegrationPreviewTarget[];
};

export function getMcpShimPath(
  userDataPath: string,
  platform: NodeJS.Platform = process.platform
): string {
  return path.join(userDataPath, "bin", platform === "win32" ? "minix-mcp.exe" : "minix-mcp");
}

export function buildAgentIntegrationPreview({
  userDataPath,
  platform = process.platform
}: {
  userDataPath: string;
  platform?: NodeJS.Platform;
}): AgentIntegrationPreview {
  const shimPath = getMcpShimPath(userDataPath, platform);
  const runtimeFilePath = getRuntimeHandoffPaths(userDataPath).runtimeFile;
  const options: McpRuntimeHandoffOptions = { runtimeFilePath };

  return {
    shimPath,
    runtimeFilePath,
    targets: [
      {
        id: "codex",
        name: "Codex",
        configPath: "~/.codex/config.toml",
        format: "toml",
        installable: true,
        content: buildCodexConfigToml(shimPath, options)
      },
      {
        id: "claude-desktop",
        name: "Claude Desktop",
        configPath: getClaudeDesktopConfigPath(platform),
        format: "json",
        installable: true,
        content: JSON.stringify(buildClaudeDesktopConfig(shimPath, options), null, 2)
      },
      {
        id: "claude-code",
        name: "Claude Code",
        configPath: "claude mcp add-json",
        format: "shell",
        installable: false,
        content: buildClaudeCodeAddJsonCommand(shimPath, options)
      },
      {
        id: "opencode",
        name: "OpenCode",
        configPath: "~/.config/opencode/opencode.jsonc",
        format: "json",
        installable: true,
        content: JSON.stringify(buildOpenCodeConfig(shimPath, options), null, 2)
      },
      {
        id: "generic-stdio",
        name: "Generic stdio MCP",
        configPath: "Generic stdio MCP",
        format: "json",
        installable: false,
        content: JSON.stringify(buildGenericMcpConfig(shimPath, options), null, 2)
      }
    ]
  };
}

function getClaudeDesktopConfigPath(platform: NodeJS.Platform): string {
  if (platform === "win32") {
    return "%APPDATA%\\Claude\\claude_desktop_config.json";
  }
  if (platform === "darwin") {
    return "~/Library/Application Support/Claude/claude_desktop_config.json";
  }
  return "~/.config/Claude/claude_desktop_config.json";
}
