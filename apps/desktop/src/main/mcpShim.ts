import { chmodSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export type McpShimInstallResult = {
  shimPath: string;
  pythonPath: string;
  mcpSourcePath: string;
};

export function getMcpShimPath(
  userDataPath: string,
  platform: NodeJS.Platform = process.platform
): string {
  return path.join(userDataPath, "bin", platform === "win32" ? "minix-mcp.cmd" : "minix-mcp");
}

export function ensureMcpShim({
  userDataPath,
  repoRoot,
  platform = process.platform,
  pythonPath = path.join(repoRoot, ".venv", "bin", "python")
}: {
  userDataPath: string;
  repoRoot: string;
  platform?: NodeJS.Platform;
  pythonPath?: string;
}): McpShimInstallResult {
  const shimPath = getMcpShimPath(userDataPath, platform);
  const mcpSourcePath = path.join(repoRoot, "mcp", "src");

  mkdirSync(path.dirname(shimPath), { recursive: true });
  writeFileSync(
    shimPath,
    platform === "win32"
      ? buildWindowsShim({ pythonPath, mcpSourcePath })
      : buildPosixShim({ pythonPath, mcpSourcePath }),
    {
      encoding: "utf-8",
      mode: 0o755
    }
  );
  chmodSync(shimPath, 0o755);

  return {
    shimPath,
    pythonPath,
    mcpSourcePath
  };
}

function buildPosixShim({
  pythonPath,
  mcpSourcePath
}: {
  pythonPath: string;
  mcpSourcePath: string;
}): string {
  return [
    "#!/bin/sh",
    "set -eu",
    `DEFAULT_PYTHON=${shellSingleQuote(pythonPath)}`,
    `DEFAULT_MCP_SOURCE=${shellSingleQuote(mcpSourcePath)}`,
    'PYTHON_BIN="${MINIX_MCP_PYTHON:-$DEFAULT_PYTHON}"',
    'MCP_SOURCE="${MINIX_MCP_PYTHONPATH:-$DEFAULT_MCP_SOURCE}"',
    'export PYTHONPATH="${MCP_SOURCE}${PYTHONPATH:+:$PYTHONPATH}"',
    'exec "$PYTHON_BIN" -m minix_mcp "$@"',
    ""
  ].join("\n");
}

function buildWindowsShim({
  pythonPath,
  mcpSourcePath
}: {
  pythonPath: string;
  mcpSourcePath: string;
}): string {
  return [
    "@echo off",
    "setlocal",
    `set "DEFAULT_PYTHON=${pythonPath}"`,
    `set "DEFAULT_MCP_SOURCE=${mcpSourcePath}"`,
    'if "%MINIX_MCP_PYTHON%"=="" (set "PYTHON_BIN=%DEFAULT_PYTHON%") else (set "PYTHON_BIN=%MINIX_MCP_PYTHON%")',
    'if "%MINIX_MCP_PYTHONPATH%"=="" (set "MCP_SOURCE=%DEFAULT_MCP_SOURCE%") else (set "MCP_SOURCE=%MINIX_MCP_PYTHONPATH%")',
    'set "PYTHONPATH=%MCP_SOURCE%;%PYTHONPATH%"',
    '"%PYTHON_BIN%" -m minix_mcp %*',
    ""
  ].join("\r\n");
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}
