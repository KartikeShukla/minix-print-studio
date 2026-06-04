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

export type McpRuntimeHandoffOptions = {
  runtimeFilePath?: string;
};

function escapeTomlString(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}

function buildMcpEnvironment(options: McpRuntimeHandoffOptions = {}): Record<string, string> {
  return options.runtimeFilePath
    ? {
        MINIX_DAEMON_RUNTIME_FILE: options.runtimeFilePath
      }
    : {};
}

export function buildGenericMcpConfig(
  shimPath: string,
  options: McpRuntimeHandoffOptions = {}
): StdioMcpConfig {
  return {
    type: "stdio",
    command: shimPath,
    args: [],
    env: buildMcpEnvironment(options)
  };
}

export function buildCodexConfigToml(
  shimPath: string,
  options: McpRuntimeHandoffOptions = {}
): string {
  const lines = [
    "[mcp_servers.minix_print]",
    `command = "${escapeTomlString(shimPath)}"`,
    "args = []",
    "startup_timeout_sec = 15.0",
    "tool_timeout_sec = 120.0",
    ""
  ];
  if (options.runtimeFilePath) {
    lines.push(
      "[mcp_servers.minix_print.env]",
      `MINIX_DAEMON_RUNTIME_FILE = "${escapeTomlString(options.runtimeFilePath)}"`,
      ""
    );
  }
  return lines.join("\n");
}

export function buildClaudeDesktopConfig(
  shimPath: string,
  options: McpRuntimeHandoffOptions = {}
): ClaudeDesktopConfig {
  return {
    mcpServers: {
      "minix-print": buildGenericMcpConfig(shimPath, options)
    }
  };
}

export function buildClaudeCodeAddJsonCommand(
  shimPath: string,
  options: McpRuntimeHandoffOptions = {}
): string {
  const config = JSON.stringify(buildGenericMcpConfig(shimPath, options));
  return `claude mcp add-json minix-print ${shellSingleQuote(config)}`;
}

export function buildOpenCodeConfig(
  shimPath: string,
  options: McpRuntimeHandoffOptions = {}
): OpenCodeConfig {
  return {
    $schema: "https://opencode.ai/config.json",
    mcp: {
      "minix-print": {
        type: "local",
        command: [shimPath],
        enabled: true,
        timeout: 15000,
        environment: buildMcpEnvironment(options)
      }
    }
  };
}
