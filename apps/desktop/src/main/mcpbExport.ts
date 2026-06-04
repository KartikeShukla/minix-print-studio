import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { ensureMcpShim } from "./mcpShim";
import { getRuntimeHandoffPaths } from "./runtimeHandoff";

export type ClaudeDesktopMcpbExportResult = {
  targetId: "claude-desktop";
  targetPath: string;
  createdAt: string;
  entries: string[];
};

type ZipEntry = {
  name: string;
  content: Buffer;
  mode: number;
};

const MCPB_FILE_NAME = "minix-print-studio-claude-desktop.mcpb";
const ZIP_LOCAL_FILE_HEADER = 0x04034b50;
const ZIP_CENTRAL_DIRECTORY_HEADER = 0x02014b50;
const ZIP_END_OF_CENTRAL_DIRECTORY = 0x06054b50;

let crcTable: Uint32Array | null = null;

export function exportClaudeDesktopMcpb({
  userDataPath,
  repoRoot,
  platform = process.platform,
  now = new Date(),
}: {
  userDataPath: string;
  repoRoot: string;
  platform?: NodeJS.Platform;
  now?: Date;
}): ClaudeDesktopMcpbExportResult {
  const shim = ensureMcpShim({ userDataPath, repoRoot, platform });
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

function buildStoredZip(entries: ZipEntry[], date: Date): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  const localOffsets: number[] = [];
  let offset = 0;
  const dosDateTime = toDosDateTime(date);

  for (const entry of entries) {
    const name = Buffer.from(entry.name, "utf-8");
    const crc = crc32(entry.content);
    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(ZIP_LOCAL_FILE_HEADER, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0, 6);
    localHeader.writeUInt16LE(0, 8);
    localHeader.writeUInt16LE(dosDateTime.time, 10);
    localHeader.writeUInt16LE(dosDateTime.date, 12);
    localHeader.writeUInt32LE(crc, 14);
    localHeader.writeUInt32LE(entry.content.byteLength, 18);
    localHeader.writeUInt32LE(entry.content.byteLength, 22);
    localHeader.writeUInt16LE(name.byteLength, 26);
    localHeader.writeUInt16LE(0, 28);

    localOffsets.push(offset);
    localParts.push(localHeader, name, entry.content);
    offset +=
      localHeader.byteLength + name.byteLength + entry.content.byteLength;

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(ZIP_CENTRAL_DIRECTORY_HEADER, 0);
    centralHeader.writeUInt16LE(0x0314, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt16LE(0, 8);
    centralHeader.writeUInt16LE(0, 10);
    centralHeader.writeUInt16LE(dosDateTime.time, 12);
    centralHeader.writeUInt16LE(dosDateTime.date, 14);
    centralHeader.writeUInt32LE(crc, 16);
    centralHeader.writeUInt32LE(entry.content.byteLength, 20);
    centralHeader.writeUInt32LE(entry.content.byteLength, 24);
    centralHeader.writeUInt16LE(name.byteLength, 28);
    centralHeader.writeUInt16LE(0, 30);
    centralHeader.writeUInt16LE(0, 32);
    centralHeader.writeUInt16LE(0, 34);
    centralHeader.writeUInt16LE(0, 36);
    centralHeader.writeUInt32LE((entry.mode << 16) >>> 0, 38);
    centralHeader.writeUInt32LE(localOffsets.at(-1) ?? 0, 42);
    centralParts.push(centralHeader, name);
  }

  const centralDirectory = Buffer.concat(centralParts);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(ZIP_END_OF_CENTRAL_DIRECTORY, 0);
  end.writeUInt16LE(0, 4);
  end.writeUInt16LE(0, 6);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralDirectory.byteLength, 12);
  end.writeUInt32LE(offset, 16);
  end.writeUInt16LE(0, 20);

  return Buffer.concat([...localParts, centralDirectory, end]);
}

function toDosDateTime(date: Date): { date: number; time: number } {
  const year = Math.min(Math.max(date.getFullYear(), 1980), 2107);
  return {
    date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    time:
      (date.getHours() << 11) |
      (date.getMinutes() << 5) |
      Math.floor(date.getSeconds() / 2),
  };
}

function crc32(data: Buffer): number {
  const table = getCrcTable();
  let crc = 0xffffffff;
  for (const byte of data) {
    crc = (crc >>> 8) ^ (table[(crc ^ byte) & 0xff] ?? 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function getCrcTable(): Uint32Array {
  if (crcTable) {
    return crcTable;
  }
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  crcTable = table;
  return table;
}

function shellSingleQuote(value: string): string {
  return `'${value.replaceAll("'", "'\"'\"'")}'`;
}
