import {
  existsSync,
  mkdirSync,
  readFileSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import os from "node:os";
import path from "node:path";
import type { AgentIntegrationTargetId } from "./agentIntegrations";

const CODEX_BLOCK_BEGIN = "# BEGIN MiniX Print Studio MCP";
const CODEX_BLOCK_END = "# END MiniX Print Studio MCP";
const MINIX_SERVER_ID = "minix-print";

export type AgentIntegrationInstallRequest = {
  targetId: AgentIntegrationTargetId;
  configPath: string;
  content: string;
  userDataPath: string;
  homeDir?: string;
  now?: Date;
};

export type AgentIntegrationUninstallRequest = Omit<AgentIntegrationInstallRequest, "content">;

export type AgentIntegrationBackupManifest = {
  version: 1;
  operation: "install" | "uninstall";
  targetId: AgentIntegrationTargetId;
  targetPath: string;
  backupPath: string;
  existed: boolean;
  createdAt: string;
};

export type AgentIntegrationInstallResult = AgentIntegrationBackupManifest & {
  manifestPath: string;
};

export function installAgentIntegrationConfig(
  request: AgentIntegrationInstallRequest
): AgentIntegrationInstallResult {
  assertInstallableTarget(request.targetId);
  const targetPath = resolveIntegrationConfigPath(request.configPath, request.homeDir);
  const backup = createBackupManifest({
    operation: "install",
    targetId: request.targetId,
    targetPath,
    userDataPath: request.userDataPath,
    ...(request.now ? { now: request.now } : {})
  });
  const existingContent = backup.existed ? readFileSync(backup.backupPath, "utf-8") : "";
  const nextContent = buildInstalledContent(request.targetId, existingContent, request.content);

  mkdirSync(path.dirname(targetPath), { recursive: true });
  writeFileSync(targetPath, nextContent, "utf-8");

  return backup;
}

export function uninstallAgentIntegrationConfig(
  request: AgentIntegrationUninstallRequest
): AgentIntegrationInstallResult {
  assertInstallableTarget(request.targetId);
  const targetPath = resolveIntegrationConfigPath(request.configPath, request.homeDir);
  const backup = createBackupManifest({
    operation: "uninstall",
    targetId: request.targetId,
    targetPath,
    userDataPath: request.userDataPath,
    ...(request.now ? { now: request.now } : {})
  });

  if (!backup.existed) {
    return backup;
  }

  const existingContent = readFileSync(backup.backupPath, "utf-8");
  const nextContent = buildUninstalledContent(request.targetId, existingContent);
  writeFileSync(targetPath, nextContent, "utf-8");

  return backup;
}

export function revertAgentIntegrationChange({
  manifestPath
}: {
  manifestPath: string;
}): AgentIntegrationBackupManifest {
  const manifest = parseBackupManifest(readFileSync(manifestPath, "utf-8"));

  if (manifest.existed) {
    mkdirSync(path.dirname(manifest.targetPath), { recursive: true });
    writeFileSync(manifest.targetPath, readFileSync(manifest.backupPath, "utf-8"), "utf-8");
  } else if (existsSync(manifest.targetPath)) {
    unlinkSync(manifest.targetPath);
  }

  return manifest;
}

function buildInstalledContent(
  targetId: AgentIntegrationTargetId,
  existingContent: string,
  installContent: string
): string {
  switch (targetId) {
    case "codex":
      return upsertCodexManagedBlock(existingContent, installContent);
    case "claude-desktop":
      return installClaudeDesktopConfig(existingContent, installContent);
    case "opencode":
      return installOpenCodeConfig(existingContent, installContent);
    case "claude-code":
    case "generic-stdio":
      throw new Error(`${targetId} does not support direct config file installation`);
  }
}

function buildUninstalledContent(targetId: AgentIntegrationTargetId, existingContent: string): string {
  switch (targetId) {
    case "codex":
      return removeCodexManagedBlock(existingContent);
    case "claude-desktop":
      return removeClaudeDesktopConfig(existingContent);
    case "opencode":
      return removeOpenCodeConfig(existingContent);
    case "claude-code":
    case "generic-stdio":
      throw new Error(`${targetId} does not support direct config file installation`);
  }
}

function assertInstallableTarget(targetId: AgentIntegrationTargetId): void {
  if (targetId !== "codex" && targetId !== "claude-desktop" && targetId !== "opencode") {
    throw new Error(`${targetId} does not support direct config file installation`);
  }
}

function resolveIntegrationConfigPath(configPath: string, homeDir = os.homedir()): string {
  if (configPath === "~") {
    return homeDir;
  }
  if (configPath.startsWith("~/")) {
    return path.join(homeDir, configPath.slice(2));
  }
  return path.resolve(configPath);
}

function createBackupManifest({
  operation,
  targetId,
  targetPath,
  userDataPath,
  now = new Date()
}: {
  operation: AgentIntegrationBackupManifest["operation"];
  targetId: AgentIntegrationTargetId;
  targetPath: string;
  userDataPath: string;
  now?: Date;
}): AgentIntegrationInstallResult {
  const createdAt = now.toISOString();
  const backupDir = path.join(userDataPath, "integration-backups");
  const backupBaseName = [
    sanitizeFileName(createdAt),
    operation,
    targetId,
    path.basename(targetPath) || "config"
  ].join("-");
  const backupPath = path.join(backupDir, `${backupBaseName}.bak`);
  const manifestPath = path.join(backupDir, `${backupBaseName}.json`);
  const existed = existsSync(targetPath);

  mkdirSync(backupDir, { recursive: true });
  writeFileSync(backupPath, existed ? readFileSync(targetPath, "utf-8") : "", "utf-8");

  const manifest: AgentIntegrationBackupManifest = {
    version: 1,
    operation,
    targetId,
    targetPath,
    backupPath,
    existed,
    createdAt
  };
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf-8");

  return { ...manifest, manifestPath };
}

function upsertCodexManagedBlock(existingContent: string, installContent: string): string {
  const withoutExistingBlock = removeCodexManagedBlock(existingContent).trimEnd();
  const block = `${CODEX_BLOCK_BEGIN}\n${installContent.trimEnd()}\n${CODEX_BLOCK_END}\n`;
  return withoutExistingBlock ? `${withoutExistingBlock}\n\n${block}` : block;
}

function removeCodexManagedBlock(existingContent: string): string {
  const blockPattern = new RegExp(
    `\\n?${escapeRegExp(CODEX_BLOCK_BEGIN)}[\\s\\S]*?${escapeRegExp(CODEX_BLOCK_END)}\\n?`,
    "g"
  );
  const withoutBlock = existingContent.replace(blockPattern, "\n").replace(/\n{3,}/g, "\n\n");
  return withoutBlock.trimEnd() ? `${withoutBlock.trimEnd()}\n` : "";
}

function installClaudeDesktopConfig(existingContent: string, installContent: string): string {
  const existingConfig = parseOptionalJsonObject(existingContent);
  const installConfig = parseJsonObject(installContent);
  const generatedServers = asRecord(installConfig.mcpServers);
  const minixServer = generatedServers?.[MINIX_SERVER_ID];
  if (!minixServer) {
    throw new Error("Claude Desktop config is missing minix-print MCP server");
  }
  const existingServers = asRecord(existingConfig.mcpServers) ?? {};
  return formatJson({
    ...existingConfig,
    mcpServers: {
      ...existingServers,
      [MINIX_SERVER_ID]: minixServer
    }
  });
}

function removeClaudeDesktopConfig(existingContent: string): string {
  const existingConfig = parseOptionalJsonObject(existingContent);
  const existingServers = { ...(asRecord(existingConfig.mcpServers) ?? {}) };
  delete existingServers[MINIX_SERVER_ID];
  return formatJson({
    ...existingConfig,
    mcpServers: existingServers
  });
}

function installOpenCodeConfig(existingContent: string, installContent: string): string {
  const existingConfig = parseOptionalJsonObject(existingContent);
  const installConfig = parseJsonObject(installContent);
  const generatedMcp = asRecord(installConfig.mcp);
  const minixServer = generatedMcp?.[MINIX_SERVER_ID];
  if (!minixServer) {
    throw new Error("OpenCode config is missing minix-print MCP server");
  }
  const existingMcp = asRecord(existingConfig.mcp) ?? {};
  return formatJson({
    ...existingConfig,
    $schema: existingConfig.$schema ?? installConfig.$schema,
    mcp: {
      ...existingMcp,
      [MINIX_SERVER_ID]: minixServer
    }
  });
}

function removeOpenCodeConfig(existingContent: string): string {
  const existingConfig = parseOptionalJsonObject(existingContent);
  const existingMcp = { ...(asRecord(existingConfig.mcp) ?? {}) };
  delete existingMcp[MINIX_SERVER_ID];
  return formatJson({
    ...existingConfig,
    mcp: existingMcp
  });
}

function parseOptionalJsonObject(content: string): Record<string, unknown> {
  return content.trim() ? parseJsonObject(content) : {};
}

function parseJsonObject(content: string): Record<string, unknown> {
  const parsed = JSON.parse(content) as unknown;
  if (!isRecord(parsed)) {
    throw new Error("Integration config must be a JSON object");
  }
  return parsed;
}

function parseBackupManifest(content: string): AgentIntegrationBackupManifest {
  const parsed = parseJsonObject(content);
  if (
    parsed.version !== 1 ||
    !isString(parsed.operation) ||
    !isString(parsed.targetId) ||
    !isString(parsed.targetPath) ||
    !isString(parsed.backupPath) ||
    typeof parsed.existed !== "boolean" ||
    !isString(parsed.createdAt)
  ) {
    throw new Error("Invalid integration backup manifest");
  }
  return parsed as AgentIntegrationBackupManifest;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function formatJson(value: Record<string, unknown>): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function sanitizeFileName(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]/g, "-");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
