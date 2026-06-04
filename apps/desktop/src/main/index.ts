import path from "node:path";
import { app, BrowserWindow, ipcMain } from "electron";
import log from "electron-log";
import {
  buildAgentIntegrationPreview,
  testAgentIntegrationConnection,
  type AgentIntegrationTargetId
} from "./agentIntegrations";
import { createDaemonLaunchConfig, createDaemonRuntime, startDaemon } from "./daemonSupervisor";
import {
  installAgentIntegrationConfig,
  uninstallAgentIntegrationConfig
} from "./integrationInstaller";
import { ensureMcpShim } from "./mcpShim";
import { getRepoRoot } from "./paths";
import { writeDaemonRuntimeHandoff } from "./runtimeHandoff";
import { buildSecureWebPreferences } from "./security";

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
  const config = createDaemonLaunchConfig({
    repoRoot,
    port: runtime.port,
    token: runtime.token,
    mock: runtime.mock
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
      repoRoot
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
    repoRoot: getRepoRoot()
  })
);

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
