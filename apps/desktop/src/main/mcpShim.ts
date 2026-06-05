import { chmodSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export type McpShimInstallResult = {
  shimPath: string;
  commandPath: string;
  sidecarMode: "source" | "bundled";
  pythonPath?: string;
  mcpSourcePath?: string;
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
  sidecarMode = "source",
  pythonPath = getSourcePythonPath(repoRoot, platform)
}: {
  userDataPath: string;
  repoRoot: string;
  platform?: NodeJS.Platform;
  sidecarMode?: "source" | "bundled";
  pythonPath?: string;
}): McpShimInstallResult {
  const shimPath = getMcpShimPath(userDataPath, platform);
  const mcpSourcePath = path.join(repoRoot, "mcp", "src");
  const bundledCommandPath = getBundledMcpPath(repoRoot, platform);

  mkdirSync(path.dirname(shimPath), { recursive: true });
  writeFileSync(
    shimPath,
    sidecarMode === "bundled"
      ? buildBundledShim({ platform, commandPath: bundledCommandPath })
      : platform === "win32"
        ? buildWindowsSourceShim({ pythonPath, mcpSourcePath })
        : buildPosixSourceShim({ pythonPath, mcpSourcePath }),
    {
      encoding: "utf-8",
      mode: 0o755
    }
  );
  chmodSync(shimPath, 0o755);

  return {
    shimPath,
    commandPath: sidecarMode === "bundled" ? bundledCommandPath : pythonPath,
    sidecarMode,
    ...(sidecarMode === "source" ? { pythonPath, mcpSourcePath } : {})
  };
}

function buildPosixSourceShim({
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

function buildWindowsSourceShim({
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

function buildBundledShim({
  platform,
  commandPath
}: {
  platform: NodeJS.Platform;
  commandPath: string;
}): string {
  if (platform === "win32") {
    return ["@echo off", "setlocal", `"${commandPath}" %*`, ""].join("\r\n");
  }
  return ["#!/bin/sh", "set -eu", `exec ${shellSingleQuote(commandPath)} "$@"`, ""].join("\n");
}

function getSourcePythonPath(repoRoot: string, platform: NodeJS.Platform): string {
  if (platform === "win32") {
    return path.join(repoRoot, ".venv", "Scripts", "python.exe");
  }
  return path.join(repoRoot, ".venv", "bin", "python");
}

function getBundledMcpPath(resourcesPath: string, platform: NodeJS.Platform): string {
  return path.join(resourcesPath, "sidecars", platform === "win32" ? "minix-mcp.exe" : "minix-mcp");
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}
