import { mkdtempSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { createDaemonRuntime } from "../src/main/daemonSupervisor";
import { getRuntimeHandoffPaths, writeDaemonRuntimeHandoff } from "../src/main/runtimeHandoff";

describe("daemon runtime handoff", () => {
  it("writes runtime metadata and a separate token file under Electron user data", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const runtime = createDaemonRuntime({
      baseUrl: "http://127.0.0.1:43210",
      port: 43210,
      token: "token_private",
      mock: true
    });

    const handoff = writeDaemonRuntimeHandoff({
      runtime,
      userDataPath,
      pid: 12345,
      startedAt: new Date("2026-06-04T10:00:00.000Z")
    });

    expect(handoff.runtimeFile).toBe(path.join(userDataPath, "runtime", "runtime.json"));
    expect(handoff.tokenFile).toBe(path.join(userDataPath, "runtime", "token"));
    expect(getRuntimeHandoffPaths(userDataPath)).toEqual({
      runtimeDir: path.join(userDataPath, "runtime"),
      runtimeFile: path.join(userDataPath, "runtime", "runtime.json"),
      tokenFile: path.join(userDataPath, "runtime", "token")
    });
    expect(readFileSync(handoff.tokenFile, "utf-8")).toBe("token_private");
    expect(JSON.parse(readFileSync(handoff.runtimeFile, "utf-8"))).toEqual({
      version: 1,
      pid: 12345,
      baseUrl: "http://127.0.0.1:43210",
      tokenFile: handoff.tokenFile,
      startedAt: "2026-06-04T10:00:00.000Z",
      mock: true
    });
    expect(readFileSync(handoff.runtimeFile, "utf-8")).not.toContain("token_private");
  });
});
