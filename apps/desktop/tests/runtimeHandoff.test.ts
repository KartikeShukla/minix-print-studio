import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { createDaemonRuntime } from "../src/main/daemonSupervisor";
import {
  getRuntimeHandoffPaths,
  selectAgentDirectUserOptInGate,
  writeDaemonRuntimeHandoff
} from "../src/main/runtimeHandoff";

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

  it("stores the selected agent-direct opt-in gate beside the runtime handoff", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const runtime = createDaemonRuntime({
      baseUrl: "http://127.0.0.1:43210",
      port: 43210,
      token: "token_private",
      mock: false
    });
    const sourceGatePath = path.join(userDataPath, "agent-direct-user-opt-in-source.json");
    const gate = {
      status: "agent_direct_user_opt_in_recorded",
      sourcePolicyReview: {
        stage: "agent_direct_policy_review",
        status: "agent_direct_policy_reviewed",
        localRecordValidated: true
      },
      optIn: {
        explicitUserOptIn: true,
        recordedVia: "local_cli_confirmation",
        directPrintDefault: "approval_required",
        unattendedPrintingAllowed: false
      },
      nextRequiredStage: "runtime_approval_enforcement"
    };
    writeFileSync(sourceGatePath, `${JSON.stringify(gate)}\n`, "utf-8");

    const handoff = writeDaemonRuntimeHandoff({
      runtime,
      userDataPath,
      pid: 12345,
      startedAt: new Date("2026-06-04T10:00:00.000Z")
    });
    const selected = selectAgentDirectUserOptInGate({
      userDataPath,
      recordPath: sourceGatePath
    });

    expect(selected.agentDirectUserOptInFile).toBe(
      path.join(userDataPath, "runtime", "agent-direct-user-opt-in.json")
    );
    expect(JSON.parse(readFileSync(selected.agentDirectUserOptInFile, "utf-8"))).toEqual(gate);
    const updatedRuntime = JSON.parse(readFileSync(handoff.runtimeFile, "utf-8"));
    expect(updatedRuntime).toEqual({
      version: 1,
      pid: 12345,
      baseUrl: "http://127.0.0.1:43210",
      tokenFile: handoff.tokenFile,
      startedAt: "2026-06-04T10:00:00.000Z",
      mock: false,
      agentDirectUserOptInFile: selected.agentDirectUserOptInFile
    });
    expect(readFileSync(handoff.runtimeFile, "utf-8")).not.toContain(
      "agent_direct_user_opt_in_recorded"
    );

    const rewritten = writeDaemonRuntimeHandoff({
      runtime,
      userDataPath,
      pid: 12346,
      startedAt: new Date("2026-06-04T10:05:00.000Z")
    });
    expect(rewritten.record.agentDirectUserOptInFile).toBe(selected.agentDirectUserOptInFile);
  });
});
