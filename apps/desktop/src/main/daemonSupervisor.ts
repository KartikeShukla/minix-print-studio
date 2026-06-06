import { randomUUID } from "node:crypto";
import path from "node:path";
import { spawn, type ChildProcess } from "node:child_process";

export type DaemonRuntime = {
  baseUrl: string;
  token: string;
  port: number;
  mock: boolean;
};

export type SidecarMode = "source" | "bundled";

export type DaemonLaunchOptions = {
  repoRoot: string;
  port: number;
  token: string;
  mock: boolean;
  dataDir?: string;
  sidecarMode?: SidecarMode;
  platform?: NodeJS.Platform;
};

export type DaemonLaunchConfig = {
  command: string;
  args: string[];
  env: NodeJS.ProcessEnv;
};

export type DaemonMockEnv = {
  MINIX_DAEMON_MOCK?: string;
};

export function createDaemonRuntime(options: Partial<DaemonRuntime> = {}): DaemonRuntime {
  const port = options.port ?? 39281;
  const token = options.token ?? `token_${randomUUID()}`;
  const mock = options.mock ?? true;

  return {
    baseUrl: options.baseUrl ?? `http://127.0.0.1:${port}`,
    token,
    port,
    mock
  };
}

export function resolveDaemonMockMode(
  env: DaemonMockEnv = process.env
): boolean {
  return env.MINIX_DAEMON_MOCK?.toLowerCase() === "true";
}

export function createDaemonLaunchConfig(options: DaemonLaunchOptions): DaemonLaunchConfig {
  const platform = options.platform ?? process.platform;
  const sidecarMode = options.sidecarMode ?? "source";
  return {
    command:
      sidecarMode === "bundled"
        ? getBundledDaemonPath(options.repoRoot, platform)
        : getSourcePythonPath(options.repoRoot, platform),
    args: sidecarMode === "bundled" ? [] : ["-m", "minixd"],
    env: {
      ...process.env,
      MINIX_DAEMON_PORT: String(options.port),
      MINIX_DAEMON_TOKEN: options.token,
      MINIX_DAEMON_MOCK: options.mock ? "true" : "false",
      ...(options.dataDir ? { MINIX_DAEMON_DATA_DIR: options.dataDir } : {})
    }
  };
}

export function startDaemon(config: DaemonLaunchConfig): ChildProcess {
  return spawn(config.command, config.args, {
    env: config.env,
    stdio: "ignore",
    detached: false
  });
}

function getSourcePythonPath(repoRoot: string, platform: NodeJS.Platform): string {
  if (platform === "win32") {
    return path.join(repoRoot, ".venv", "Scripts", "python.exe");
  }
  return path.join(repoRoot, ".venv", "bin", "python");
}

function getBundledDaemonPath(resourcesPath: string, platform: NodeJS.Platform): string {
  return path.join(resourcesPath, "sidecars", platform === "win32" ? "minixd.exe" : "minixd");
}
