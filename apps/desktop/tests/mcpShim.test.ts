import { existsSync, mkdtempSync, readFileSync, statSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { ensureMcpShim } from "../src/main/mcpShim";

describe("MCP shim materialization", () => {
  it("writes an executable stable shim under app user data without embedding daemon tokens", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const repoRoot = mkdtempSync(path.join(os.tmpdir(), "minix-repo-"));

    const result = ensureMcpShim({ userDataPath, repoRoot, platform: "darwin" });

    expect(result.shimPath).toBe(path.join(userDataPath, "bin", "minix-mcp"));
    expect(existsSync(result.shimPath)).toBe(true);
    expect(statSync(result.shimPath).mode & 0o111).not.toBe(0);
    expect(readFileSync(result.shimPath, "utf-8")).toContain(path.join(repoRoot, "mcp", "src"));
    expect(readFileSync(result.shimPath, "utf-8")).not.toContain("MINIX_DAEMON_TOKEN");
  });

  it("writes a packaged shim that executes the bundled MCP sidecar", () => {
    const userDataPath = mkdtempSync(path.join(os.tmpdir(), "minix-user-data-"));
    const resourcesPath = mkdtempSync(path.join(os.tmpdir(), "minix-resources-"));

    const result = ensureMcpShim({
      userDataPath,
      repoRoot: resourcesPath,
      platform: "darwin",
      sidecarMode: "bundled"
    });

    const shimText = readFileSync(result.shimPath, "utf-8");
    expect(result.commandPath).toBe(path.join(resourcesPath, "sidecars", "minix-mcp"));
    expect(shimText).toContain(path.join(resourcesPath, "sidecars", "minix-mcp"));
    expect(shimText).not.toContain("PYTHONPATH");
    expect(shimText).not.toContain("mcp/src");
    expect(shimText).not.toContain("MINIX_DAEMON_TOKEN");
  });
});
