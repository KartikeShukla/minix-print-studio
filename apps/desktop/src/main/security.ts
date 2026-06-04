import type { WebPreferences } from "electron";

export function buildSecureWebPreferences(preload: string): WebPreferences {
  return {
    preload,
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true
  };
}
