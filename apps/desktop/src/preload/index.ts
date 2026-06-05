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
  inspectHardwareArtifact: () => ipcRenderer.invoke("hardware-artifacts:inspect")
});
