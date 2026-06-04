export type StdioMcpConfig = {
  type: "stdio";
  command: string;
  args: string[];
  env: Record<string, string>;
};

export type ClaudeDesktopConfig = {
  mcpServers: {
    "minix-print": StdioMcpConfig;
  };
};

export type OpenCodeConfig = {
  $schema: string;
  mcp: {
    "minix-print": {
      type: "local";
      command: string[];
      enabled: true;
      timeout: 15000;
      environment: Record<string, string>;
    };
  };
};

function escapeTomlString(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}

export function buildGenericMcpConfig(shimPath: string): StdioMcpConfig {
  return {
    type: "stdio",
    command: shimPath,
    args: [],
    env: {}
  };
}

export function buildCodexConfigToml(shimPath: string): string {
  return [
    "[mcp_servers.minix_print]",
    `command = "${escapeTomlString(shimPath)}"`,
    "args = []",
    "startup_timeout_sec = 15.0",
    "tool_timeout_sec = 120.0",
    ""
  ].join("\n");
}

export function buildClaudeDesktopConfig(shimPath: string): ClaudeDesktopConfig {
  return {
    mcpServers: {
      "minix-print": buildGenericMcpConfig(shimPath)
    }
  };
}

export function buildClaudeCodeAddJsonCommand(shimPath: string): string {
  const config = JSON.stringify(buildGenericMcpConfig(shimPath));
  return `claude mcp add-json minix-print ${shellSingleQuote(config)}`;
}

export function buildOpenCodeConfig(shimPath: string): OpenCodeConfig {
  return {
    $schema: "https://opencode.ai/config.json",
    mcp: {
      "minix-print": {
        type: "local",
        command: [shimPath],
        enabled: true,
        timeout: 15000,
        environment: {}
      }
    }
  };
}
