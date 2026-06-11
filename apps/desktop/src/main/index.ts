import path from "node:path";
import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  type OpenDialogOptions,
} from "electron";
import log from "electron-log";
import { AgentPreviewApprovalQueue } from "./agentPreviewApprovals";
import {
  buildAgentIntegrationPreview,
  testAgentIntegrationConnection,
  type AgentIntegrationTargetId,
} from "./agentIntegrations";
import { buildBetaFeedbackDraft } from "./betaFeedback";
import {
  createDaemonLaunchConfig,
  createDaemonRuntime,
  resolveDaemonMockMode,
  startDaemon,
} from "./daemonSupervisor";
import {
  installAgentIntegrationConfig,
  uninstallAgentIntegrationConfig,
} from "./integrationInstaller";
import { ensureMcpShim } from "./mcpShim";
import { exportClaudeDesktopMcpb } from "./mcpbExport";
import {
  checkHostBluetoothReadiness,
  inspectAgentDirectPolicyReview,
  inspectAgentDirectUserOptIn,
  inspectHardwareArtifact,
  inspectStableSupportGate,
  inspectTrustedPrinterRecord,
} from "./hardwareArtifacts";
import { getRepoRoot } from "./paths";
import {
  selectAgentDirectUserOptInGate,
  writeDaemonRuntimeHandoff,
} from "./runtimeHandoff";
import { buildSecureWebPreferences } from "./security";
import { exportSupportBundle } from "./supportBundle";
import { getUpdateChannelState, setUpdateChannel } from "./updateChannel";

let mainWindow: BrowserWindow | null = null;
const runtime = createDaemonRuntime({ mock: resolveDaemonMockMode() });
const agentPreviewApprovalQueue = new AgentPreviewApprovalQueue();
const hasSingleInstanceLock = app.requestSingleInstanceLock();

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: "MiniX Print Studio",
    backgroundColor: "#f8f6f0",
    webPreferences: buildSecureWebPreferences(
      path.join(__dirname, "../preload/index.js"),
    ),
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

function publishAgentPreviewApprovals(): void {
  mainWindow?.webContents.send(
    "agent-preview-approvals:changed",
    agentPreviewApprovalQueue.list(),
  );
}

function enqueueAgentPreviewApprovalUrl(url: string): void {
  const approval = agentPreviewApprovalQueue.enqueueUrl(url);
  if (!approval) {
    return;
  }
  publishAgentPreviewApprovals();
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
  }
}

function enqueueAgentPreviewApprovalArgs(argv: string[]): void {
  for (const arg of argv) {
    enqueueAgentPreviewApprovalUrl(arg);
  }
}

function startSidecar(): void {
  const repoRoot = getRepoRoot();
  const sidecarMode = app.isPackaged ? "bundled" : "source";
  const config = createDaemonLaunchConfig({
    repoRoot,
    port: runtime.port,
    token: runtime.token,
    mock: runtime.mock,
    dataDir: path.join(app.getPath("userData"), "daemon"),
    sidecarMode,
  });

  const child = startDaemon(config);
  try {
    writeDaemonRuntimeHandoff({
      runtime,
      userDataPath: app.getPath("userData"),
      pid: child.pid ?? process.pid,
    });
    ensureMcpShim({
      userDataPath: app.getPath("userData"),
      repoRoot,
      sidecarMode,
    });
  } catch (error) {
    log.warn("Unable to write daemon runtime handoff or MCP shim", error);
  }
  child.once("error", (error) => {
    log.warn("Unable to start daemon sidecar", error);
  });
}

ipcMain.handle("app:version", () => app.getVersion());
ipcMain.handle("daemon:runtime", () => ({
  baseUrl: runtime.baseUrl,
  token: runtime.token,
}));
ipcMain.handle("agent-integrations:preview", () =>
  buildAgentIntegrationPreview({ userDataPath: app.getPath("userData") }),
);
ipcMain.handle("agent-preview-approvals:list", () =>
  agentPreviewApprovalQueue.list(),
);
ipcMain.handle(
  "agent-preview-approvals:remove",
  (_event, previewId: string) => {
    agentPreviewApprovalQueue.remove(previewId);
    publishAgentPreviewApprovals();
  },
);
ipcMain.handle(
  "agent-integrations:install",
  (_event, targetId: AgentIntegrationTargetId) => {
    const userDataPath = app.getPath("userData");
    const target = getAgentIntegrationTarget(targetId, userDataPath);
    return installAgentIntegrationConfig({
      targetId,
      configPath: target.configPath,
      content: target.content,
      userDataPath,
    });
  },
);
ipcMain.handle(
  "agent-integrations:uninstall",
  (_event, targetId: AgentIntegrationTargetId) => {
    const userDataPath = app.getPath("userData");
    const target = getAgentIntegrationTarget(targetId, userDataPath);
    return uninstallAgentIntegrationConfig({
      targetId,
      configPath: target.configPath,
      userDataPath,
    });
  },
);
ipcMain.handle(
  "agent-integrations:test",
  (_event, targetId: AgentIntegrationTargetId) =>
    testAgentIntegrationConnection({
      targetId,
      userDataPath: app.getPath("userData"),
      repoRoot: getRepoRoot(),
      sidecarMode: app.isPackaged ? "bundled" : "source",
    }),
);
ipcMain.handle(
  "agent-integrations:export-bundle",
  (_event, targetId: AgentIntegrationTargetId) => {
    if (targetId !== "claude-desktop") {
      throw new Error(`${targetId} does not support MCPB export`);
    }
    return exportClaudeDesktopMcpb({
      userDataPath: app.getPath("userData"),
      repoRoot: getRepoRoot(),
      sidecarMode: app.isPackaged ? "bundled" : "source",
    });
  },
);
ipcMain.handle("support:export-bundle", () =>
  exportSupportBundle({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion(),
    platform: process.platform,
  }),
);
ipcMain.handle(
  "support:create-feedback-draft",
  (_event, request?: { supportBundlePath?: string }) =>
    buildBetaFeedbackDraft({
      appVersion: app.getVersion(),
      platform: process.platform,
      supportBundlePath: request?.supportBundlePath ?? null,
    }),
);
ipcMain.handle("updates:get-state", () =>
  getUpdateChannelState({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion(),
  }),
);
ipcMain.handle("updates:set-channel", (_event, channel: string) =>
  setUpdateChannel({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion(),
    channel,
  }),
);
ipcMain.handle("hardware-readiness:check", () =>
  checkHostBluetoothReadiness({
    repoRoot: getRepoRoot(),
  }),
);
ipcMain.handle("hardware-artifacts:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect Stage A artifact",
    properties: ["openFile"],
    filters: [{ name: "Hardware-test ZIP", extensions: ["zip"] }],
  };
  const selection = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  const artifactPath = selection.filePaths[0];
  if (selection.canceled || !artifactPath) {
    return null;
  }
  return inspectHardwareArtifact({
    artifactPath,
    repoRoot: getRepoRoot(),
  });
});
ipcMain.handle("trusted-printer-records:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect trusted-printer record",
    properties: ["openFile"],
    filters: [{ name: "Trusted-printer JSON", extensions: ["json"] }],
  };
  const selection = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  const recordPath = selection.filePaths[0];
  if (selection.canceled || !recordPath) {
    return null;
  }
  return inspectTrustedPrinterRecord({
    recordPath,
    repoRoot: getRepoRoot(),
  });
});
ipcMain.handle("stable-support-gates:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect stable-support gate",
    properties: ["openFile"],
    filters: [{ name: "Stable-support gate JSON", extensions: ["json"] }],
  };
  const selection = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  const recordPath = selection.filePaths[0];
  if (selection.canceled || !recordPath) {
    return null;
  }
  return inspectStableSupportGate({
    recordPath,
    repoRoot: getRepoRoot(),
  });
});
ipcMain.handle("agent-direct-policy-reviews:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect agent-direct policy review",
    properties: ["openFile"],
    filters: [{ name: "Agent-direct policy JSON", extensions: ["json"] }],
  };
  const selection = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  const recordPath = selection.filePaths[0];
  if (selection.canceled || !recordPath) {
    return null;
  }
  return inspectAgentDirectPolicyReview({
    recordPath,
    repoRoot: getRepoRoot(),
  });
});
ipcMain.handle("agent-direct-user-opt-ins:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect agent-direct user opt-in",
    properties: ["openFile"],
    filters: [{ name: "Agent-direct opt-in JSON", extensions: ["json"] }],
  };
  const selection = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  const recordPath = selection.filePaths[0];
  if (selection.canceled || !recordPath) {
    return null;
  }
  const inspection = await inspectAgentDirectUserOptIn({
    recordPath,
    repoRoot: getRepoRoot(),
  });
  selectAgentDirectUserOptInGate({
    userDataPath: app.getPath("userData"),
    recordPath,
  });
  return inspection;
});

function getAgentIntegrationTarget(
  targetId: AgentIntegrationTargetId,
  userDataPath: string,
) {
  const preview = buildAgentIntegrationPreview({ userDataPath });
  const target = preview.targets.find((candidate) => candidate.id === targetId);
  if (!target) {
    throw new Error(`Unknown agent integration target: ${targetId}`);
  }
  return target;
}

app.whenReady().then(() => {
  if (!hasSingleInstanceLock) {
    app.quit();
    return;
  }
  app.setAsDefaultProtocolClient("minixprint");
  enqueueAgentPreviewApprovalArgs(process.argv);
  startSidecar();
  createWindow();
});

app.on("open-url", (event, url) => {
  event.preventDefault();
  enqueueAgentPreviewApprovalUrl(url);
});

app.on("second-instance", (_event, argv) => {
  enqueueAgentPreviewApprovalArgs(argv);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
