import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("minix", {
  getAppVersion: () => ipcRenderer.invoke("app:version"),
  getDaemonRuntime: () => ipcRenderer.invoke("daemon:runtime"),
  getAgentIntegrationPreview: () => ipcRenderer.invoke("agent-integrations:preview")
});
