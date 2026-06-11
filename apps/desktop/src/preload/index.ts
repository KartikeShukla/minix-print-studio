import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("minix", {
  getAppVersion: () => ipcRenderer.invoke("app:version"),
  getDaemonRuntime: () => ipcRenderer.invoke("daemon:runtime"),
  getAgentIntegrationPreview: () =>
    ipcRenderer.invoke("agent-integrations:preview"),
  listAgentPreviewApprovals: () =>
    ipcRenderer.invoke("agent-preview-approvals:list"),
  removeAgentPreviewApproval: (previewId: string) =>
    ipcRenderer.invoke("agent-preview-approvals:remove", previewId),
  onAgentPreviewApprovalsChanged: (
    callback: (approvals: unknown[]) => void,
  ) => {
    const listener = (_event: unknown, approvals: unknown[]) => {
      callback(approvals);
    };
    ipcRenderer.on("agent-preview-approvals:changed", listener);
    return () => {
      ipcRenderer.removeListener("agent-preview-approvals:changed", listener);
    };
  },
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
  setUpdateChannel: (channel: string) =>
    ipcRenderer.invoke("updates:set-channel", channel),
  checkHostBluetoothReadiness: () =>
    ipcRenderer.invoke("hardware-readiness:check"),
  inspectHardwareArtifact: () =>
    ipcRenderer.invoke("hardware-artifacts:inspect"),
  inspectTrustedPrinterRecord: () =>
    ipcRenderer.invoke("trusted-printer-records:inspect"),
  inspectStableSupportGate: () =>
    ipcRenderer.invoke("stable-support-gates:inspect"),
  inspectAgentDirectPolicyReview: () =>
    ipcRenderer.invoke("agent-direct-policy-reviews:inspect"),
  inspectAgentDirectUserOptIn: () =>
    ipcRenderer.invoke("agent-direct-user-opt-ins:inspect"),
});
