export type AgentIntegrationTargetId =
  | "codex"
  | "claude-desktop"
  | "claude-code"
  | "opencode"
  | "generic-stdio";

export type AgentIntegrationPreviewTarget = {
  id: AgentIntegrationTargetId;
  name: string;
  configPath: string;
  format: "json" | "shell" | "toml";
  installable?: boolean;
  exportable?: boolean;
  content: string;
};

export type AgentIntegrationPreview = {
  shimPath: string;
  runtimeFilePath: string;
  targets: AgentIntegrationPreviewTarget[];
};

export type AgentIntegrationProvider = () => Promise<AgentIntegrationPreview | null>;

export type AgentIntegrationInstallResult = {
  version: 1;
  operation: "install" | "uninstall";
  targetId: AgentIntegrationTargetId;
  targetPath: string;
  backupPath: string;
  manifestPath: string;
  existed: boolean;
  createdAt: string;
};

export type AgentIntegrationConnectionTestResult = {
  ok: boolean;
  targetId: AgentIntegrationTargetId;
  shimPath: string;
  runtimeFilePath: string;
  checkedAt: string;
  message: string;
  missing: string[];
};

export type AgentIntegrationExportResult = {
  targetId: "claude-desktop";
  targetPath: string;
  createdAt: string;
  entries: string[];
};

export type AgentIntegrationInstaller = {
  install: (targetId: AgentIntegrationTargetId) => Promise<AgentIntegrationInstallResult>;
  uninstall: (targetId: AgentIntegrationTargetId) => Promise<AgentIntegrationInstallResult>;
  testConnection: (
    targetId: AgentIntegrationTargetId
  ) => Promise<AgentIntegrationConnectionTestResult>;
  exportBundle?: (
    targetId: AgentIntegrationTargetId
  ) => Promise<AgentIntegrationExportResult>;
};

export async function loadAgentIntegrationPreview(): Promise<AgentIntegrationPreview | null> {
  return window.minix?.getAgentIntegrationPreview?.() ?? null;
}

export const desktopAgentIntegrationInstaller: AgentIntegrationInstaller = {
  async install(targetId) {
    const install = window.minix?.installAgentIntegrationConfig;
    if (!install) {
      throw new Error("Agent integration install is unavailable");
    }
    return install(targetId);
  },
  async uninstall(targetId) {
    const uninstall = window.minix?.uninstallAgentIntegrationConfig;
    if (!uninstall) {
      throw new Error("Agent integration uninstall is unavailable");
    }
    return uninstall(targetId);
  },
  async testConnection(targetId) {
    const testConnection = window.minix?.testAgentIntegrationConnection;
    if (!testConnection) {
      throw new Error("Agent integration connection test is unavailable");
    }
    return testConnection(targetId);
  },
  async exportBundle(targetId) {
    const exportBundle = window.minix?.exportAgentIntegrationBundle;
    if (!exportBundle) {
      throw new Error("Agent integration export is unavailable");
    }
    return exportBundle(targetId);
  }
};
