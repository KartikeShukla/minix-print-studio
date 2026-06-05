import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { ensureMcpShim } from "./mcpShim";
import { getRuntimeHandoffPaths } from "./runtimeHandoff";
import type { SidecarMode } from "./daemonSupervisor";
import { buildStoredZip, type ZipEntry } from "./zip";

export type ClaudeDesktopMcpbExportResult = {
  targetId: "claude-desktop";
  targetPath: string;
  createdAt: string;
  entries: string[];
};

const MCPB_FILE_NAME = "minix-print-studio-claude-desktop.mcpb";

export function exportClaudeDesktopMcpb({
  userDataPath,
  repoRoot,
  platform = process.platform,
  sidecarMode = "source",
  now = new Date(),
}: {
  userDataPath: string;
  repoRoot: string;
  platform?: NodeJS.Platform;
  sidecarMode?: SidecarMode;
  now?: Date;
}): ClaudeDesktopMcpbExportResult {
  const shim = ensureMcpShim({ userDataPath, repoRoot, platform, sidecarMode });
  const runtimeFilePath = getRuntimeHandoffPaths(userDataPath).runtimeFile;
  const targetPath = path.join(
    userDataPath,
    "agent-integrations",
    MCPB_FILE_NAME,
  );
  const bridgeEntryName = getBridgeEntryName(platform);
  const entries: ZipEntry[] = [
    {
      name: "manifest.json",
      content: Buffer.from(
        `${JSON.stringify(buildManifest({ platform, runtimeFilePath, bridgeEntryName }), null, 2)}\n`,
        "utf-8",
      ),
      mode: 0o100644,
    },
    {
      name: bridgeEntryName,
      content: Buffer.from(
        buildBridgeScript({ platform, shimPath: shim.shimPath }),
        "utf-8",
      ),
      mode: platform === "win32" ? 0o100644 : 0o100755,
    },
    {
      name: "README.md",
      content: Buffer.from(
        buildReadme({ createdAt: now.toISOString() }),
        "utf-8",
      ),
      mode: 0o100644,
    },
  ];

  mkdirSync(path.dirname(targetPath), { recursive: true });
  writeFileSync(targetPath, buildStoredZip(entries, now));

  return {
    targetId: "claude-desktop",
    targetPath,
    createdAt: now.toISOString(),
    entries: entries.map((entry) => entry.name),
  };
}

function buildManifest({
  platform,
  runtimeFilePath,
  bridgeEntryName,
}: {
  platform: NodeJS.Platform;
  runtimeFilePath: string;
  bridgeEntryName: string;
}) {
  return {
    manifest_version: "0.3",
    name: "minix-print-studio",
    display_name: "MiniX Print Studio",
    version: "0.1.0",
    description:
      "Connects Claude Desktop to the local MiniX Print Studio app for safe thermal print previews.",
    long_description:
      "MiniX Print Studio runs locally and keeps printer access behind the desktop app. Claude can request daemon status and approval-required print previews through the local MCP server.",
    author: {
      name: "MiniX Print Studio",
    },
    license: "MIT",
    keywords: ["mcp", "thermal-printer", "minix", "printing"],
    server: {
      type: "binary",
      entry_point: bridgeEntryName,
      mcp_config: {
        command: getBridgeCommand(platform, bridgeEntryName),
        args: [],
        env: {
          MINIX_DAEMON_RUNTIME_FILE: runtimeFilePath,
        },
      },
    },
    tools: [
      {
        name: "get_daemon_status",
        description:
          "Check whether the local MiniX Print Studio daemon is reachable.",
      },
      {
        name: "preview_document",
        description:
          "Create a daemon-canonical print preview that requires user approval.",
      },
      {
        name: "print_note",
        description:
          "Create a print preview for a short note without directly printing.",
      },
    ],
    compatibility: {
      platforms: [platform],
    },
  };
}

function getBridgeEntryName(platform: NodeJS.Platform): string {
  return platform === "win32"
    ? "server/minix-mcp-bridge.cmd"
    : "server/minix-mcp-bridge";
}

function getBridgeCommand(
  platform: NodeJS.Platform,
  bridgeEntryName: string,
): string {
  if (platform === "win32") {
    return "${__dirname}\\server\\minix-mcp-bridge.cmd";
  }
  return `\${__dirname}/${bridgeEntryName}`;
}

function buildBridgeScript({
  platform,
  shimPath,
}: {
  platform: NodeJS.Platform;
  shimPath: string;
}): string {
  if (platform === "win32") {
    return ["@echo off", `call "${shimPath}" %*`, ""].join("\r\n");
  }
  return [
    "#!/bin/sh",
    "set -eu",
    `exec ${shellSingleQuote(shimPath)} "$@"`,
    "",
  ].join("\n");
}

function buildReadme({ createdAt }: { createdAt: string }): string {
  return [
    "# MiniX Print Studio Claude Desktop Extension",
    "",
    "This MCPB connects Claude Desktop to the local MiniX Print Studio app through the app-managed MCP shim.",
    "Keep MiniX Print Studio running while using the extension. The bundle does not contain daemon bearer tokens.",
    "",
    `Created: ${createdAt}`,
    "",
  ].join("\n");
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}
