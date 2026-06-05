import path from "node:path";
import { describe, expect, it } from "vitest";
import { createDaemonLaunchConfig } from "../src/main/daemonSupervisor";

describe("daemon launch config", () => {
  it("launches the repo-local Python daemon in mock mode for development", () => {
    const repoRoot = path.join("/", "repo");

    const config = createDaemonLaunchConfig({
      repoRoot,
      port: 39281,
      token: "token_123",
      mock: true,
      dataDir: path.join("/", "user-data", "daemon")
    });

    expect(config.command).toBe(path.join(repoRoot, ".venv", "bin", "python"));
    expect(config.args).toEqual(["-m", "minixd"]);
    expect(config.env.MINIX_DAEMON_PORT).toBe("39281");
    expect(config.env.MINIX_DAEMON_TOKEN).toBe("token_123");
    expect(config.env.MINIX_DAEMON_MOCK).toBe("true");
    expect(config.env.MINIX_DAEMON_DATA_DIR).toBe(path.join("/", "user-data", "daemon"));
  });

  it("launches the packaged daemon sidecar without a repo-local Python dependency", () => {
    const resourcesPath = path.join("/", "Applications", "MiniX.app", "Contents", "Resources");

    const config = createDaemonLaunchConfig({
      repoRoot: resourcesPath,
      port: 39281,
      token: "token_123",
      mock: true,
      sidecarMode: "bundled",
      platform: "darwin"
    });

    expect(config.command).toBe(path.join(resourcesPath, "sidecars", "minixd"));
    expect(config.args).toEqual([]);
    expect(config.command).not.toContain(".venv");
    expect(config.env.MINIX_DAEMON_PORT).toBe("39281");
    expect(config.env.MINIX_DAEMON_TOKEN).toBe("token_123");
    expect(config.env.MINIX_DAEMON_MOCK).toBe("true");
  });
});
