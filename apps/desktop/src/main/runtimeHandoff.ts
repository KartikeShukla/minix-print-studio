import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync
} from "node:fs";
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
  agentDirectUserOptInFile?: string;
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
  const existingAgentDirectUserOptInFile = readExistingAgentDirectUserOptInFile(
    paths.runtimeFile
  );
  const record: RuntimeHandoffRecord = {
    version: 1,
    pid,
    baseUrl: runtime.baseUrl,
    tokenFile: paths.tokenFile,
    startedAt: startedAt.toISOString(),
    mock: runtime.mock,
    ...(existingAgentDirectUserOptInFile
      ? { agentDirectUserOptInFile: existingAgentDirectUserOptInFile }
      : {})
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

export type SelectedAgentDirectUserOptInGate = RuntimeHandoffPaths & {
  agentDirectUserOptInFile: string;
  record: RuntimeHandoffRecord;
};

export function selectAgentDirectUserOptInGate({
  userDataPath,
  recordPath
}: {
  userDataPath: string;
  recordPath: string;
}): SelectedAgentDirectUserOptInGate {
  const paths = getRuntimeHandoffPaths(userDataPath);
  const runtimeRecord = readRuntimeHandoffRecord(paths.runtimeFile);
  const agentDirectUserOptInFile = path.join(
    paths.runtimeDir,
    "agent-direct-user-opt-in.json"
  );

  mkdirSync(paths.runtimeDir, { recursive: true });
  copyFileSync(recordPath, agentDirectUserOptInFile);
  chmodSync(agentDirectUserOptInFile, 0o600);

  const record: RuntimeHandoffRecord = {
    ...runtimeRecord,
    agentDirectUserOptInFile
  };
  writeFileSync(paths.runtimeFile, `${JSON.stringify(record, null, 2)}\n`, {
    encoding: "utf-8",
    mode: 0o600
  });
  chmodSync(paths.runtimeFile, 0o600);

  return { ...paths, agentDirectUserOptInFile, record };
}

function readExistingAgentDirectUserOptInFile(
  runtimeFile: string
): string | undefined {
  if (!existsSync(runtimeFile)) {
    return undefined;
  }
  const record = readRuntimeHandoffRecord(runtimeFile);
  return record.agentDirectUserOptInFile && existsSync(record.agentDirectUserOptInFile)
    ? record.agentDirectUserOptInFile
    : undefined;
}

function readRuntimeHandoffRecord(runtimeFile: string): RuntimeHandoffRecord {
  const raw = JSON.parse(readFileSync(runtimeFile, "utf-8")) as unknown;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("daemon runtime handoff is invalid");
  }
  const record = raw as Partial<RuntimeHandoffRecord>;
  if (
    record.version !== 1 ||
    typeof record.pid !== "number" ||
    typeof record.baseUrl !== "string" ||
    typeof record.tokenFile !== "string" ||
    typeof record.startedAt !== "string" ||
    typeof record.mock !== "boolean"
  ) {
    throw new Error("daemon runtime handoff is incomplete");
  }
  if (
    record.agentDirectUserOptInFile !== undefined &&
    typeof record.agentDirectUserOptInFile !== "string"
  ) {
    throw new Error("daemon runtime handoff has invalid agent opt-in file");
  }
  return {
    version: 1,
    pid: record.pid,
    baseUrl: record.baseUrl,
    tokenFile: record.tokenFile,
    startedAt: record.startedAt,
    mock: record.mock,
    ...(record.agentDirectUserOptInFile
      ? { agentDirectUserOptInFile: record.agentDirectUserOptInFile }
      : {})
  };
}
