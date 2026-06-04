import path from "node:path";
import { app } from "electron";

export function getRepoRoot(): string {
  if (!app.isPackaged) {
    return path.resolve(app.getAppPath(), "../..");
  }

  return process.resourcesPath;
}
