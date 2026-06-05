import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { exportSupportBundle } from "../src/main/supportBundle";

describe("desktop support bundle export", () => {
  it("writes a redacted support zip with logs and crash metadata", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const logDir = path.join(userDataPath, "logs");
    const runtimeDir = path.join(userDataPath, "runtime");
    const crashDir = path.join(userDataPath, "crash-reports");
    mkdirSync(logDir, { recursive: true });
    mkdirSync(runtimeDir, { recursive: true });
    mkdirSync(crashDir, { recursive: true });
    const logPath = path.join(logDir, "main.log");
    const crashPath = path.join(crashDir, "last-crash.json");
    writeFileSync(
      logPath,
      [
        "starting MiniX",
        "private path /Users/alice/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
        "Authorization: Bearer token_private",
        "MINIX_DAEMON_TOKEN=token_private",
        ""
      ].join("\n"),
      "utf-8"
    );
    writeFileSync(path.join(runtimeDir, "token"), "token_private", "utf-8");
    writeFileSync(
      crashPath,
      JSON.stringify({
        reason: "renderer-crash",
        path: "/Users/alice/crashes/crash.dmp"
      }),
      "utf-8"
    );

    const result = exportSupportBundle({
      userDataPath,
      appVersion: "0.1.0",
      platform: "darwin",
      now: new Date("2026-06-05T00:03:00.000Z")
    });

    expect(result).toEqual({
      targetPath: path.join(
        userDataPath,
        "support",
        "minix-print-studio-support-2026-06-05T00-03-00-000Z.zip"
      ),
      createdAt: "2026-06-05T00:03:00.000Z",
      entries: ["support.json", "logs/main.log", "crash-reports/last-crash.json", "README.md"]
    });
    expect(existsSync(result.targetPath)).toBe(true);

    const entries = readStoredZipEntries(readFileSync(result.targetPath));
    const support = JSON.parse(readRequiredEntry(entries, "support.json").toString("utf-8"));
    expect(support).toMatchObject({
      schemaVersion: 1,
      appVersion: "0.1.0",
      platform: "darwin",
      redaction: {
        tokensIncluded: false,
        privatePathsIncluded: false
      }
    });

    const zipText = Object.values(entries)
      .map((entry) => entry.toString("utf-8"))
      .join("\n");
    expect(zipText).toContain("starting MiniX");
    expect(zipText).toContain("<redacted-user-path>");
    expect(zipText).toContain("<redacted-token>");
    expect(zipText).toContain("renderer-crash");
    expect(zipText).not.toContain("/Users/alice");
    expect(zipText).not.toContain("Application Support/MiniX Print Studio");
    expect(zipText).not.toContain("Support/MiniX Print Studio");
    expect(zipText).not.toContain("token_private");
    expect(Object.keys(entries)).not.toContain("runtime/token");
  });
});

function readStoredZipEntries(buffer: Buffer): Record<string, Buffer> {
  const entries: Record<string, Buffer> = {};
  let offset = 0;
  while (offset < buffer.byteLength && buffer.readUInt32LE(offset) === 0x04034b50) {
    const compressionMethod = buffer.readUInt16LE(offset + 8);
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const fileNameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const nameStart = offset + 30;
    const dataStart = nameStart + fileNameLength + extraLength;
    const name = buffer.subarray(nameStart, nameStart + fileNameLength).toString("utf-8");

    expect(compressionMethod).toBe(0);
    entries[name] = buffer.subarray(dataStart, dataStart + compressedSize);
    offset = dataStart + compressedSize;
  }
  return entries;
}

function readRequiredEntry(entries: Record<string, Buffer>, name: string): Buffer {
  const entry = entries[name];
  if (!entry) {
    throw new Error(`Missing ZIP entry: ${name}`);
  }
  return entry;
}
