import { chmodSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { DaemonRuntime } from "./daemonSupervisor";

export type RuntimeHandoffPaths = {
  runtimeDir: string;
  runtimeFile: string;
  tokenFile: string;
};

export type RuntimeHandoffRecord = {
  version: 1;
  pid: number;
  baseUrl: string;
  tokenFile: string;
  startedAt: string;
  mock: boolean;
};

export type WrittenRuntimeHandoff = RuntimeHandoffPaths & {
  record: RuntimeHandoffRecord;
};

export function getRuntimeHandoffPaths(userDataPath: string): RuntimeHandoffPaths {
  const runtimeDir = path.join(userDataPath, "runtime");
  return {
    runtimeDir,
    runtimeFile: path.join(runtimeDir, "runtime.json"),
    tokenFile: path.join(runtimeDir, "token")
  };
}

export function writeDaemonRuntimeHandoff({
  runtime,
  userDataPath,
  pid,
  startedAt = new Date()
}: {
  runtime: DaemonRuntime;
  userDataPath: string;
  pid: number;
  startedAt?: Date;
}): WrittenRuntimeHandoff {
  const paths = getRuntimeHandoffPaths(userDataPath);
  const record: RuntimeHandoffRecord = {
    version: 1,
    pid,
    baseUrl: runtime.baseUrl,
    tokenFile: paths.tokenFile,
    startedAt: startedAt.toISOString(),
    mock: runtime.mock
  };

  mkdirSync(paths.runtimeDir, { recursive: true });
  writeFileSync(paths.tokenFile, runtime.token, { encoding: "utf-8", mode: 0o600 });
  chmodSync(paths.tokenFile, 0o600);
  writeFileSync(paths.runtimeFile, `${JSON.stringify(record, null, 2)}\n`, {
    encoding: "utf-8",
    mode: 0o600
  });
  chmodSync(paths.runtimeFile, 0o600);

  return { ...paths, record };
}
