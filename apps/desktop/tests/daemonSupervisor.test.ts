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
      mock: true
    });

    expect(config.command).toBe(path.join(repoRoot, ".venv", "bin", "python"));
    expect(config.args).toEqual(["-m", "minixd"]);
    expect(config.env.MINIX_DAEMON_PORT).toBe("39281");
    expect(config.env.MINIX_DAEMON_TOKEN).toBe("token_123");
    expect(config.env.MINIX_DAEMON_MOCK).toBe("true");
  });
});
