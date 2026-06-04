import path from "node:path";
import { app, BrowserWindow, ipcMain } from "electron";
import log from "electron-log";
import { createDaemonLaunchConfig, createDaemonRuntime, startDaemon } from "./daemonSupervisor";
import { getRepoRoot } from "./paths";
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
  const config = createDaemonLaunchConfig({
    repoRoot: getRepoRoot(),
    port: runtime.port,
    token: runtime.token,
    mock: runtime.mock
  });

  const child = startDaemon(config);
  child.once("error", (error) => {
    log.warn("Unable to start daemon sidecar", error);
  });
}

ipcMain.handle("app:version", () => app.getVersion());
ipcMain.handle("daemon:runtime", () => ({
  baseUrl: runtime.baseUrl,
  token: runtime.token
}));

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
