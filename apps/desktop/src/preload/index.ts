import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("minix", {
  getAppVersion: () => ipcRenderer.invoke("app:version"),
  getDaemonRuntime: () => ipcRenderer.invoke("daemon:runtime"),
  getAgentIntegrationPreview: () => ipcRenderer.invoke("agent-integrations:preview"),
  installAgentIntegrationConfig: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:install", targetId),
  uninstallAgentIntegrationConfig: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:uninstall", targetId),
  testAgentIntegrationConnection: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:test", targetId),
  exportAgentIntegrationBundle: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:export-bundle", targetId),
  exportSupportBundle: () => ipcRenderer.invoke("support:export-bundle"),
  createBetaFeedbackDraft: (request?: { supportBundlePath?: string }) =>
    ipcRenderer.invoke("support:create-feedback-draft", request),
  getUpdateChannelState: () => ipcRenderer.invoke("updates:get-state"),
  setUpdateChannel: (channel: string) => ipcRenderer.invoke("updates:set-channel", channel),
  inspectHardwareArtifact: () => ipcRenderer.invoke("hardware-artifacts:inspect")
});
