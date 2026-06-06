import path from "node:path";
import { app, BrowserWindow, dialog, ipcMain, type OpenDialogOptions } from "electron";
import log from "electron-log";
import {
  buildAgentIntegrationPreview,
  testAgentIntegrationConnection,
  type AgentIntegrationTargetId
} from "./agentIntegrations";
import { buildBetaFeedbackDraft } from "./betaFeedback";
import { createDaemonLaunchConfig, createDaemonRuntime, startDaemon } from "./daemonSupervisor";
import {
  installAgentIntegrationConfig,
  uninstallAgentIntegrationConfig
} from "./integrationInstaller";
import { ensureMcpShim } from "./mcpShim";
import { exportClaudeDesktopMcpb } from "./mcpbExport";
import { checkHostBluetoothReadiness, inspectHardwareArtifact } from "./hardwareArtifacts";
import { getRepoRoot } from "./paths";
import { writeDaemonRuntimeHandoff } from "./runtimeHandoff";
import { buildSecureWebPreferences } from "./security";
import { exportSupportBundle } from "./supportBundle";
import { getUpdateChannelState, setUpdateChannel } from "./updateChannel";

let mainWindow: BrowserWindow | null = null;
const runtime = createDaemonRuntime({ mock: true });

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: "MiniX Print Studio",
    backgroundColor: "#f8f6f0",
    webPreferences: buildSecureWebPreferences(path.join(__dirname, "../preload/index.js"))
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
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
    sidecarMode
  });

  const child = startDaemon(config);
  try {
    writeDaemonRuntimeHandoff({
      runtime,
      userDataPath: app.getPath("userData"),
      pid: child.pid ?? process.pid
    });
    ensureMcpShim({
      userDataPath: app.getPath("userData"),
      repoRoot,
      sidecarMode
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
  token: runtime.token
}));
ipcMain.handle("agent-integrations:preview", () =>
  buildAgentIntegrationPreview({ userDataPath: app.getPath("userData") })
);
ipcMain.handle("agent-integrations:install", (_event, targetId: AgentIntegrationTargetId) => {
  const userDataPath = app.getPath("userData");
  const target = getAgentIntegrationTarget(targetId, userDataPath);
  return installAgentIntegrationConfig({
    targetId,
    configPath: target.configPath,
    content: target.content,
    userDataPath
  });
});
ipcMain.handle("agent-integrations:uninstall", (_event, targetId: AgentIntegrationTargetId) => {
  const userDataPath = app.getPath("userData");
  const target = getAgentIntegrationTarget(targetId, userDataPath);
  return uninstallAgentIntegrationConfig({
    targetId,
    configPath: target.configPath,
    userDataPath
  });
});
ipcMain.handle("agent-integrations:test", (_event, targetId: AgentIntegrationTargetId) =>
  testAgentIntegrationConnection({
    targetId,
    userDataPath: app.getPath("userData"),
    repoRoot: getRepoRoot(),
    sidecarMode: app.isPackaged ? "bundled" : "source"
  })
);
ipcMain.handle("agent-integrations:export-bundle", (_event, targetId: AgentIntegrationTargetId) => {
  if (targetId !== "claude-desktop") {
    throw new Error(`${targetId} does not support MCPB export`);
  }
  return exportClaudeDesktopMcpb({
    userDataPath: app.getPath("userData"),
    repoRoot: getRepoRoot(),
    sidecarMode: app.isPackaged ? "bundled" : "source"
  });
});
ipcMain.handle("support:export-bundle", () =>
  exportSupportBundle({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion(),
    platform: process.platform
  })
);
ipcMain.handle("support:create-feedback-draft", (_event, request?: { supportBundlePath?: string }) =>
  buildBetaFeedbackDraft({
    appVersion: app.getVersion(),
    platform: process.platform,
    supportBundlePath: request?.supportBundlePath ?? null
  })
);
ipcMain.handle("updates:get-state", () =>
  getUpdateChannelState({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion()
  })
);
ipcMain.handle("updates:set-channel", (_event, channel: string) =>
  setUpdateChannel({
    userDataPath: app.getPath("userData"),
    appVersion: app.getVersion(),
    channel
  })
);
ipcMain.handle("hardware-readiness:check", () =>
  checkHostBluetoothReadiness({
    repoRoot: getRepoRoot()
  })
);
ipcMain.handle("hardware-artifacts:inspect", async () => {
  const options: OpenDialogOptions = {
    title: "Inspect Stage A artifact",
    properties: ["openFile"],
    filters: [{ name: "Hardware-test ZIP", extensions: ["zip"] }]
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
    repoRoot: getRepoRoot()
  });
});

function getAgentIntegrationTarget(targetId: AgentIntegrationTargetId, userDataPath: string) {
  const preview = buildAgentIntegrationPreview({ userDataPath });
  const target = preview.targets.find((candidate) => candidate.id === targetId);
  if (!target) {
    throw new Error(`Unknown agent integration target: ${targetId}`);
  }
  return target;
}

app.whenReady().then(() => {
  startSidecar();
  createWindow();
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
