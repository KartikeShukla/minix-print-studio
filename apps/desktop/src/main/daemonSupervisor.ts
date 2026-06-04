import { randomUUID } from "node:crypto";
import path from "node:path";
import { spawn, type ChildProcess } from "node:child_process";

export type DaemonRuntime = {
  baseUrl: string;
  token: string;
  port: number;
  mock: boolean;
};

export type DaemonLaunchOptions = {
  repoRoot: string;
  port: number;
  token: string;
  mock: boolean;
};

export type DaemonLaunchConfig = {
  command: string;
  args: string[];
  env: NodeJS.ProcessEnv;
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

export function createDaemonLaunchConfig(options: DaemonLaunchOptions): DaemonLaunchConfig {
  return {
    command: path.join(options.repoRoot, ".venv", "bin", "python"),
    args: ["-m", "minixd"],
    env: {
      ...process.env,
      MINIX_DAEMON_PORT: String(options.port),
      MINIX_DAEMON_TOKEN: options.token,
      MINIX_DAEMON_MOCK: options.mock ? "true" : "false"
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
