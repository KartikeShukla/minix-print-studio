import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { exportClaudeDesktopMcpb } from "../src/main/mcpbExport";

describe("Claude Desktop MCPB export", () => {
  it("writes a token-free MCPB zip with a Claude Desktop manifest and shim bridge", () => {
    const userDataPath = mkdtempSync(
      path.join(os.tmpdir(), "minix-user-data-"),
    );
    const repoRoot = mkdtempSync(path.join(os.tmpdir(), "minix-repo-"));

    const result = exportClaudeDesktopMcpb({
      userDataPath,
      repoRoot,
      platform: "darwin",
      now: new Date("2026-06-05T00:02:00.000Z"),
    });

    expect(result).toEqual({
      targetId: "claude-desktop",
      targetPath: path.join(
        userDataPath,
        "agent-integrations",
        "minix-print-studio-claude-desktop.mcpb",
      ),
      createdAt: "2026-06-05T00:02:00.000Z",
      entries: ["manifest.json", "server/minix-mcp-bridge", "README.md"],
    });
    expect(existsSync(result.targetPath)).toBe(true);

    const entries = readStoredZipEntries(readFileSync(result.targetPath));
    const manifest = JSON.parse(
      readRequiredEntry(entries, "manifest.json").toString("utf-8"),
    ) as {
      manifest_version: string;
      name: string;
      display_name: string;
      version: string;
      server: {
        type: string;
        entry_point: string;
        mcp_config: {
          command: string;
          args: string[];
          env: Record<string, string>;
        };
      };
      compatibility: { platforms: string[] };
      tools: Array<{ name: string }>;
    };

    expect(manifest).toMatchObject({
      manifest_version: "0.3",
      name: "minix-print-studio",
      display_name: "MiniX Print Studio",
      version: "0.1.0",
      server: {
        type: "binary",
        entry_point: "server/minix-mcp-bridge",
        mcp_config: {
          command: "${__dirname}/server/minix-mcp-bridge",
          args: [],
          env: {
            MINIX_DAEMON_RUNTIME_FILE: path.join(
              userDataPath,
              "runtime",
              "runtime.json",
            ),
          },
        },
      },
      compatibility: {
        platforms: ["darwin"],
      },
    });
    expect(JSON.stringify(manifest)).not.toContain("MINIX_DAEMON_TOKEN");
    expect(JSON.stringify(manifest)).not.toContain("token_");
    expect(manifest.tools.map((tool) => tool.name)).toEqual([
      "get_daemon_status",
      "get_job_status",
      "list_supported_profiles",
      "preview_document",
      "print_note",
    ]);

    const bridge = readRequiredEntry(
      entries,
      "server/minix-mcp-bridge",
    ).toString("utf-8");
    expect(bridge).toContain("#!/bin/sh");
    expect(bridge).toContain(
      `exec '${path.join(userDataPath, "bin", "minix-mcp")}' "$@"`,
    );
    expect(bridge).not.toContain("MINIX_DAEMON_TOKEN");

    expect(readRequiredEntry(entries, "README.md").toString("utf-8")).toContain(
      "MiniX Print Studio",
    );
  });
});

function readStoredZipEntries(buffer: Buffer): Record<string, Buffer> {
  const entries: Record<string, Buffer> = {};
  let offset = 0;
  while (
    offset < buffer.byteLength &&
    buffer.readUInt32LE(offset) === 0x04034b50
  ) {
    const compressionMethod = buffer.readUInt16LE(offset + 8);
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const fileNameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const nameStart = offset + 30;
    const dataStart = nameStart + fileNameLength + extraLength;
    const name = buffer
      .subarray(nameStart, nameStart + fileNameLength)
      .toString("utf-8");

    expect(compressionMethod).toBe(0);
    entries[name] = buffer.subarray(dataStart, dataStart + compressedSize);
    offset = dataStart + compressedSize;
  }
  return entries;
}

function readRequiredEntry(
  entries: Record<string, Buffer>,
  name: string,
): Buffer {
  const entry = entries[name];
  if (!entry) {
    throw new Error(`Missing ZIP entry: ${name}`);
  }
  return entry;
}
