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
  content: string;
};

export type AgentIntegrationPreview = {
  shimPath: string;
  runtimeFilePath: string;
  targets: AgentIntegrationPreviewTarget[];
};

export type AgentIntegrationProvider = () => Promise<AgentIntegrationPreview | null>;

export async function loadAgentIntegrationPreview(): Promise<AgentIntegrationPreview | null> {
  return window.minix?.getAgentIntegrationPreview?.() ?? null;
}
