import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("minix", {
  getAppVersion: () => ipcRenderer.invoke("app:version"),
  getDaemonRuntime: () => ipcRenderer.invoke("daemon:runtime"),
  getAgentIntegrationPreview: () => ipcRenderer.invoke("agent-integrations:preview"),
  installAgentIntegrationConfig: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:install", targetId),
  uninstallAgentIntegrationConfig: (targetId: string) =>
    ipcRenderer.invoke("agent-integrations:uninstall", targetId)
});
