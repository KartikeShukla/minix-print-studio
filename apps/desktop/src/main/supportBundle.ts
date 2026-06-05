import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { buildStoredZip, type ZipEntry } from "./zip";

export type SupportBundleExportResult = {
  targetPath: string;
  createdAt: string;
  entries: string[];
};

type ExportSupportBundleOptions = {
  userDataPath: string;
  appVersion: string;
  platform?: NodeJS.Platform;
  now?: Date;
  logDir?: string;
  crashReportDir?: string;
};

const SUPPORT_BUNDLE_SCHEMA_VERSION = 1;
const SUPPORT_FILE_LIMIT_BYTES = 1024 * 1024;
const SUPPORT_FILE_EXTENSIONS = new Set([".json", ".log", ".txt"]);

export function exportSupportBundle({
  userDataPath,
  appVersion,
  platform = process.platform,
  now = new Date(),
  logDir = path.join(userDataPath, "logs"),
  crashReportDir = path.join(userDataPath, "crash-reports")
}: ExportSupportBundleOptions): SupportBundleExportResult {
  const createdAt = now.toISOString();
  const targetPath = path.join(
    userDataPath,
    "support",
    `minix-print-studio-support-${createdAt.replace(/[:.]/g, "-")}.zip`
  );
  const collectedEntries = [
    ...collectSupportFiles({
      directory: logDir,
      entryPrefix: "logs"
    }),
    ...collectSupportFiles({
      directory: crashReportDir,
      entryPrefix: "crash-reports"
    })
  ];
  const entries: ZipEntry[] = [
    {
      name: "support.json",
      content: Buffer.from(
        `${JSON.stringify(
          {
            schemaVersion: SUPPORT_BUNDLE_SCHEMA_VERSION,
            appVersion,
            platform,
            createdAt,
            redaction: {
              tokensIncluded: false,
              privatePathsIncluded: false
            }
          },
          null,
          2
        )}\n`,
        "utf-8"
      ),
      mode: 0o100644
    },
    ...collectedEntries,
    {
      name: "README.md",
      content: Buffer.from(buildReadme(createdAt), "utf-8"),
      mode: 0o100644
    }
  ];

  mkdirSync(path.dirname(targetPath), { recursive: true });
  writeFileSync(targetPath, buildStoredZip(entries, now));

  return {
    targetPath,
    createdAt,
    entries: entries.map((entry) => entry.name)
  };
}

function collectSupportFiles({
  directory,
  entryPrefix
}: {
  directory: string;
  entryPrefix: string;
}): ZipEntry[] {
  if (!existsSync(directory)) {
    return [];
  }
  return listSupportFiles(directory)
    .map((filePath) => ({
      name: toZipEntryName(entryPrefix, directory, filePath),
      content: Buffer.from(readRedactedSupportText(filePath), "utf-8"),
      mode: 0o100644
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

function listSupportFiles(directory: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...listSupportFiles(entryPath));
      continue;
    }
    if (!entry.isFile() || !SUPPORT_FILE_EXTENSIONS.has(path.extname(entry.name))) {
      continue;
    }
    if (statSync(entryPath).size > SUPPORT_FILE_LIMIT_BYTES) {
      continue;
    }
    files.push(entryPath);
  }
  return files;
}

function toZipEntryName(entryPrefix: string, directory: string, filePath: string): string {
  return `${entryPrefix}/${path.relative(directory, filePath).split(path.sep).join("/")}`;
}

function readRedactedSupportText(filePath: string): string {
  return redactSupportText(readFileSync(filePath, "utf-8"));
}

function redactSupportText(text: string): string {
  return text
    .replace(/\/Users\/[^\r\n"',)}\]]+/g, "<redacted-user-path>")
    .replace(/\/home\/[^\r\n"',)}\]]+/g, "<redacted-user-path>")
    .replace(/[A-Za-z]:\\Users\\[^\r\n"',)}\]]+/g, "<redacted-user-path>")
    .replace(/(Authorization:\s*Bearer\s+)[^\s\r\n]+/gi, "$1<redacted-token>")
    .replace(/(MINIX_[A-Z0-9_]*TOKEN\s*=\s*)[^\s\r\n]+/g, "$1<redacted-token>")
    .replace(/\btoken_[A-Za-z0-9._-]+\b/g, "<redacted-token>");
}

function buildReadme(createdAt: string): string {
  return [
    "# MiniX Print Studio Support Bundle",
    "",
    "This archive contains redacted desktop logs and crash metadata for troubleshooting.",
    "Daemon bearer tokens and private user paths are not intentionally included.",
    "Review the archive before sharing it in a public issue.",
    "",
    `Created: ${createdAt}`,
    ""
  ].join("\n");
}
