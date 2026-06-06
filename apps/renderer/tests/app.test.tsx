import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createDefaultDocument } from "@minix/design-model";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";
import type { ProjectMutationRequest } from "../src/lib/api-client";
import type { UpdateChannelProvider } from "../src/lib/update-channel";

describe("MiniX Print Studio shell", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("shows the workspace and daemon health from the local API", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "MiniX Print Studio" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan printers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print" })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByText("Mock daemon online")).toBeInTheDocument();
    });
  });

  it("shows a dismissible first-run setup checklist", async () => {
    const { unmount } = render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    expect(await screen.findByText("Setup")).toBeInTheDocument();
    expect(screen.getByText("Daemon")).toBeInTheDocument();
    expect(screen.getByText("Printer verification")).toBeInTheDocument();
    expect(screen.getByText("Agent integrations")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Dismiss setup checklist" }));

    expect(screen.queryByText("Setup")).not.toBeInTheDocument();
    expect(localStorage.getItem("minix.printStudio.setupChecklist.v1")).toBe(
      JSON.stringify({ dismissed: true })
    );

    unmount();
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    expect(screen.queryByText("Setup")).not.toBeInTheDocument();
  });

  it("shows update channel status and allows selecting the beta channel", async () => {
    const setChannel = vi.fn().mockResolvedValue({
      channel: "beta",
      availableChannels: ["stable", "beta"],
      updatedAt: "2026-06-05T00:11:00.000Z",
      appVersion: "0.1.0",
      autoUpdate: {
        enabled: false,
        reason: "Auto-updates are disabled until signed release publishing is configured."
      }
    });
    const updateChannelProvider: UpdateChannelProvider = {
      getState: async () => ({
        channel: "stable",
        availableChannels: ["stable", "beta"],
        updatedAt: "2026-06-05T00:10:00.000Z",
        appVersion: "0.1.0",
        autoUpdate: {
          enabled: false,
          reason: "Auto-updates are disabled until signed release publishing is configured."
        }
      }),
      setChannel
    };

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        updateChannelProvider={updateChannelProvider}
      />
    );

    expect(await screen.findByText("Updates")).toBeInTheDocument();
    expect(screen.getByText("Stable")).toBeInTheDocument();
    expect(screen.getByText(/Auto-updates are disabled/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Use beta update channel" }));

    await waitFor(() => {
      expect(setChannel).toHaveBeenCalledWith("beta");
    });
    expect(await screen.findByText("Beta channel selected")).toBeInTheDocument();
  });

  it("shows copyable agent integration config previews without exposing daemon tokens", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        agentIntegrationProvider={async () => ({
          shimPath:
            "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp",
          runtimeFilePath:
            "/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
          targets: [
            {
              id: "codex",
              name: "Codex",
              configPath: "~/.codex/config.toml",
              format: "toml",
              content:
                "[mcp_servers.minix_print]\ncommand = \"/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp\"\n[mcp_servers.minix_print.env]\nMINIX_DAEMON_RUNTIME_FILE = \"/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json\"\n"
            }
          ]
        })}
      />
    );

    expect(await screen.findByText("Agent Integrations")).toBeInTheDocument();
    expect(screen.getByText("Codex")).toBeInTheDocument();
    expect(screen.getByText("~/.codex/config.toml")).toBeInTheDocument();
    expect(screen.getByText(/MINIX_DAEMON_RUNTIME_FILE/)).toBeInTheDocument();
    expect(screen.queryByText(/secret-token|token_123/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Copy Codex config" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("MINIX_DAEMON_RUNTIME_FILE"));
    });
    expect(await screen.findByText("Copied Codex config")).toBeInTheDocument();
  });

  it("requires confirmation before installing an agent integration config", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const install = vi.fn().mockResolvedValue({
      version: 1,
      operation: "install",
      targetId: "codex",
      targetPath: "/Users/example/.codex/config.toml",
      backupPath: "/Users/example/Library/Application Support/MiniX Print Studio/backups/codex.bak",
      manifestPath:
        "/Users/example/Library/Application Support/MiniX Print Studio/backups/codex.json",
      existed: true,
      createdAt: "2026-06-05T00:00:00.000Z"
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        agentIntegrationProvider={async () => ({
          shimPath: "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp",
          runtimeFilePath:
            "/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
          targets: [
            {
              id: "codex",
              name: "Codex",
              configPath: "~/.codex/config.toml",
              format: "toml",
              installable: true,
              content:
                "[mcp_servers.minix_print]\ncommand = \"/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp\"\n"
            }
          ]
        })}
        agentIntegrationInstaller={{
          install,
          uninstall: vi.fn(),
          testConnection: vi.fn()
        }}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Install Codex config" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("~/.codex/config.toml"));
    await waitFor(() => {
      expect(install).toHaveBeenCalledWith("codex");
    });
    expect(await screen.findByText("Installed Codex config")).toBeInTheDocument();

    confirm.mockRestore();
  });

  it("runs an agent integration connection test from the target card", async () => {
    const testConnection = vi.fn().mockResolvedValue({
      ok: true,
      targetId: "codex",
      shimPath: "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp",
      runtimeFilePath:
        "/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
      checkedAt: "2026-06-05T00:00:00.000Z",
      message: "Codex integration prerequisites are ready",
      missing: []
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        agentIntegrationProvider={async () => ({
          shimPath: "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp",
          runtimeFilePath:
            "/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
          targets: [
            {
              id: "codex",
              name: "Codex",
              configPath: "~/.codex/config.toml",
              format: "toml",
              installable: true,
              content:
                "[mcp_servers.minix_print]\ncommand = \"/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp\"\n"
            }
          ]
        })}
        agentIntegrationInstaller={{
          install: vi.fn(),
          uninstall: vi.fn(),
          testConnection
        }}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Test Codex connection" }));

    await waitFor(() => {
      expect(testConnection).toHaveBeenCalledWith("codex");
    });
    expect(await screen.findByText("Codex integration prerequisites are ready")).toBeInTheDocument();
  });

  it("exports a Claude Desktop MCPB bundle from the target card", async () => {
    const exportBundle = vi.fn().mockResolvedValue({
      targetId: "claude-desktop",
      targetPath:
        "/Users/example/Library/Application Support/MiniX Print Studio/agent-integrations/minix-print-studio-claude-desktop.mcpb",
      createdAt: "2026-06-05T00:02:00.000Z",
      entries: ["manifest.json", "server/minix-mcp-bridge", "README.md"]
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        agentIntegrationProvider={async () => ({
          shimPath: "/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp",
          runtimeFilePath:
            "/Users/example/Library/Application Support/MiniX Print Studio/runtime/runtime.json",
          targets: [
            {
              id: "claude-desktop",
              name: "Claude Desktop",
              configPath:
                "~/Library/Application Support/Claude/claude_desktop_config.json",
              format: "json",
              installable: true,
              exportable: true,
              content:
                '{"mcpServers":{"minix-print":{"command":"/Users/example/Library/Application Support/MiniX Print Studio/bin/minix-mcp"}}}'
            }
          ]
        })}
        agentIntegrationInstaller={{
          install: vi.fn(),
          uninstall: vi.fn(),
          testConnection: vi.fn(),
          exportBundle
        }}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Export Claude Desktop .mcpb" }));

    await waitFor(() => {
      expect(exportBundle).toHaveBeenCalledWith("claude-desktop");
    });
    expect(await screen.findByText("Exported Claude Desktop .mcpb")).toBeInTheDocument();
    expect(screen.getByText(/minix-print-studio-claude-desktop\.mcpb/)).toBeInTheDocument();
  });

  it("exports a redacted desktop support bundle from the sidebar", async () => {
    const exportBundle = vi.fn().mockResolvedValue({
      targetPath:
        "/Users/example/Library/Application Support/MiniX Print Studio/support/minix-print-studio-support-2026-06-05T00-03-00-000Z.zip",
      createdAt: "2026-06-05T00:03:00.000Z",
      entries: ["support.json", "logs/main.log", "crash-reports/last-crash.json", "README.md"]
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        supportBundleExporter={{ exportBundle }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Export support bundle" }));

    await waitFor(() => {
      expect(exportBundle).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Support bundle exported")).toBeInTheDocument();
    expect(screen.getByText("4 files in bundle")).toBeInTheDocument();
    expect(
      screen.getByText(/minix-print-studio-support-2026-06-05T00-03-00-000Z\.zip/)
    ).toBeInTheDocument();
  });

  it("copies a beta feedback issue draft from the support sidebar", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });
    const createFeedbackDraft = vi.fn().mockResolvedValue({
      targetUrl:
        "https://github.com/minix-print-studio/minix-print-studio/issues/new?template=beta_feedback.yml",
      title: "Beta feedback: MiniX Print Studio 0.1.0 on darwin",
      body: "## Environment\n- App version: 0.1.0\n",
      createdAt: "2026-06-05T00:04:00.000Z"
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        supportBundleExporter={{
          exportBundle: vi.fn(),
          createFeedbackDraft
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy beta feedback link" }));

    await waitFor(() => {
      expect(createFeedbackDraft).toHaveBeenCalledTimes(1);
    });
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("beta_feedback.yml"));
    expect(await screen.findByText("Beta feedback link copied")).toBeInTheDocument();
  });

  it("requests a daemon preview and print plan before enabling print", async () => {
    const createDocumentPreview = vi.fn().mockResolvedValue({
      previewId: "prev_ready",
      approvalToken: "appr_ready",
      documentHash: "sha256:document",
      renderSettingsHash: "sha256:settings",
      rasterHash: "sha256:raster",
      profileId: "seznik-minix-s1-lyin48d-gy",
      widthDots: 384,
      heightDots: 900,
      safety: { allowed: true, warnings: [], metrics: { totalBlackCoverage: 0 } },
      createdAt: "2026-06-04T00:00:00.000Z",
      expiresAt: "2026-06-04T00:10:00.000Z"
    });
    const planApprovedPreview = vi.fn().mockResolvedValue({
      plan: {
        planId: "plan_job_preview",
        jobId: "job_preview",
        previewId: "prev_ready",
        documentHash: "sha256:document",
        rasterHash: "sha256:raster",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium",
        widthDots: 384,
        contentHeightDots: 900,
        tailBlankRowsDots: 160,
        transferHeightDots: 1060,
        rowBytes: 48,
        totalRasterBytes: 50880,
        requiresLongPrintMode: false
      },
      totalBands: 5,
      bands: []
    });
    const printApprovedPreview = vi.fn();

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview,
          planApprovedPreview,
          printApprovedPreview,
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("Preview ready")).toBeInTheDocument();
    expect(screen.getByText("prev_ready")).toBeInTheDocument();
    expect(screen.getByText("5 bands")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print" })).toBeEnabled();
    expect(createDocumentPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Untitled print",
        target: expect.objectContaining({
          profileId: "seznik-minix-s1-lyin48d-gy",
          paperMode: "continuous",
          density: "medium"
        })
      }),
      { threshold: 128, dither: "none" }
    );
    expect(planApprovedPreview).toHaveBeenCalledWith({
      jobId: "job_preview",
      previewId: "prev_ready",
      approvalToken: "appr_ready",
      documentHash: "sha256:document",
      renderSettingsHash: "sha256:settings",
      profileId: "seznik-minix-s1-lyin48d-gy",
      paperMode: "continuous",
      density: "medium"
    });
    expect(printApprovedPreview).not.toHaveBeenCalled();
  });

  it("shows blocked preview safety details without enabling print", async () => {
    const createDocumentPreview = vi.fn().mockResolvedValue({
      previewId: "prev_blocked",
      approvalToken: "appr_blocked",
      documentHash: "sha256:dense-document",
      renderSettingsHash: "sha256:settings",
      rasterHash: "sha256:dense-raster",
      profileId: "seznik-minix-s1-lyin48d-gy",
      widthDots: 384,
      heightDots: 64,
      safety: {
        allowed: false,
        warnings: [
          {
            code: "total_black_coverage_high",
            message: "Total black coverage is 91%, above the 35% warning limit."
          }
        ],
        errors: [
          {
            code: "band_coverage_blocked",
            message: "A 64-dot band is 100% black, above the 70% thermal safety limit."
          }
        ],
        metrics: { totalBlackCoverage: 0.91, maxBandCoverage64: 1 }
      },
      createdAt: "2026-06-04T00:00:00.000Z",
      expiresAt: "2026-06-04T00:10:00.000Z"
    });
    const planApprovedPreview = vi
      .fn()
      .mockRejectedValue(new Error("preview safety blocked printing: band_coverage_blocked"));

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview,
          planApprovedPreview,
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("Preview blocked by safety")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(
      screen.getByText("Total black coverage is 91%, above the 35% warning limit.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("A 64-dot band is 100% black, above the 70% thermal safety limit.")
    ).toBeInTheDocument();
    expect(screen.getByText("prev_blocked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print" })).toBeDisabled();
  });

  it("prints an approved preview through the mock queue and shows user-check state", async () => {
    const createDocumentPreview = vi.fn().mockResolvedValue({
      previewId: "prev_print",
      approvalToken: "appr_print",
      documentHash: "sha256:document",
      renderSettingsHash: "sha256:settings",
      rasterHash: "sha256:raster",
      profileId: "seznik-minix-s1-lyin48d-gy",
      widthDots: 384,
      heightDots: 900,
      safety: { allowed: true, warnings: [], metrics: { totalBlackCoverage: 0 } },
      createdAt: "2026-06-04T00:00:00.000Z",
      expiresAt: "2026-06-04T00:10:00.000Z"
    });
    const planApprovedPreview = vi.fn().mockResolvedValue({
      plan: {
        planId: "plan_job_preview",
        jobId: "job_preview",
        previewId: "prev_print",
        documentHash: "sha256:document",
        rasterHash: "sha256:raster",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium",
        widthDots: 384,
        contentHeightDots: 900,
        tailBlankRowsDots: 160,
        transferHeightDots: 1060,
        rowBytes: 48,
        totalRasterBytes: 50880,
        requiresLongPrintMode: false
      },
      totalBands: 5,
      bands: []
    });
    const printApprovedPreview = vi.fn().mockResolvedValue({
      jobId: "job_print",
      previewId: "prev_print",
      planId: "plan_job_print",
      state: "completed_unverified",
      phase: "waiting_for_final_status",
      completionLevel: "unverified",
      completionConfidence: "mock_data_sent_final_ack_missing",
      requiresUserCheck: true,
      source: "ui",
      copies: 1,
      bandsSent: 5,
      totalBands: 5,
      rowsSent: 1060,
      totalRows: 1060,
      bytesSent: 50880,
      totalBytes: 50880,
      tailBlankRowsDots: 160,
      safeActions: ["confirm_complete", "feed_paper", "reprint_from_start"]
    });
    const exportDiagnostics = vi.fn().mockResolvedValue({
      schemaVersion: 1,
      createdAt: "2026-06-04T00:00:00.000Z",
      redaction: {
        projectContentIncluded: false,
        rawImagesIncluded: false,
        tokensIncluded: false
      },
      daemon: {
        version: "0.1.0",
        profileRegistryVersion: "2026.06.04",
        mock: true,
        os: "Darwin",
        python: "3.13.12"
      },
      profiles: [{ id: "seznik-minix-s1-lyin48d-gy" }],
      jobs: [{ jobId: "job_print", segments: [] }],
      recentErrors: [],
      recentMcpCalls: []
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview,
          planApprovedPreview,
          printApprovedPreview,
          exportDiagnostics,
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText("Preview ready");
    fireEvent.click(screen.getByRole("button", { name: "Print" }));

    expect(await screen.findAllByText("completed_unverified")).toHaveLength(2);
    expect(screen.getByText("User check required")).toBeInTheDocument();
    expect(screen.getByText("Confirm complete")).toBeInTheDocument();
    expect(screen.getByText("Recent Jobs")).toBeInTheDocument();
    expect(screen.getByText("job_print")).toBeInTheDocument();
    expect(printApprovedPreview).toHaveBeenCalledWith({
      previewId: "prev_print",
      approvalToken: "appr_print",
      documentHash: "sha256:document",
      renderSettingsHash: "sha256:settings",
      profileId: "seznik-minix-s1-lyin48d-gy",
      paperMode: "continuous",
      density: "medium",
      copies: 1,
      source: "ui"
    });
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem("minix.printStudio.jobHistory.v1") ?? "[]");
      expect(stored).toEqual([
        expect.objectContaining({
          jobId: "job_print",
          state: "completed_unverified",
          completionLevel: "unverified",
          source: "ui",
          totalBands: 5,
          printedAt: expect.any(String)
        })
      ]);
    });

    fireEvent.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(await screen.findByText("Diagnostics exported")).toBeInTheDocument();
    expect(screen.getByText("1 job in bundle")).toBeInTheDocument();
    expect(exportDiagnostics).toHaveBeenCalledWith({
      includeProjectContent: false,
      includeRawImages: false
    });
  });

  it("scans and read-only verifies a printer without enabling trusted print", async () => {
    const scanPrinters = vi.fn().mockResolvedValue({
      printers: [
        {
          deviceId: "mock-minix-0194",
          name: "Seznik MiniX_0194_LE",
          serviceUuids: ["0000ff00-0000-1000-8000-00805f9b34fb"],
          rssi: -42,
          supportLevel: "detected_unverified",
          candidateProfileIds: ["seznik-minix-s1-lyin48d-gy"],
          printable: false,
          nextRequiredStage: "read_only_verification",
          reason: "Service UUID and name match; model query required."
        }
      ]
    });
    const readOnlyVerify = vi.fn().mockResolvedValue({
      status: "read_only_verified",
      deviceId: "mock-minix-0194",
      profileId: "seznik-minix-s1-lyin48d-gy",
      profileSupportLevel: "official",
      modelResponse: "S1_LYiN48D_GY",
      firmware: "V1.9.11",
      printable: false,
      nextRequiredStage: "protocol_sanity_test",
      reason: "Model and firmware match profile; protocol sanity test required.",
      services: ["0000ff00-0000-1000-8000-00805f9b34fb"],
      writeCharacteristics: ["0000ff02-0000-1000-8000-00805f9b34fb"],
      notifyCharacteristics: [
        "0000ff01-0000-1000-8000-00805f9b34fb",
        "0000ff03-0000-1000-8000-00805f9b34fb"
      ],
      rawNotifications: []
    });
    const exportHardwareTest = vi
      .fn()
      .mockResolvedValue(new Blob(["hardware-test"], { type: "application/zip" }));
    const createObjectURL = vi.fn(() => "blob:hardware-test");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const clickDownload = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters,
          readOnlyVerify,
          exportHardwareTest
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Scan printers" }));

    expect(await screen.findByText("Seznik MiniX_0194_LE")).toBeInTheDocument();
    expect(screen.getByText("Read-only verification required")).toBeInTheDocument();
    expect(scanPrinters).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Verify printer identity" }));

    expect(await screen.findByText("Read-only verified")).toBeInTheDocument();
    expect(screen.getByText("S1_LYiN48D_GY")).toBeInTheDocument();
    expect(screen.getByText("Protocol sanity test required")).toBeInTheDocument();
    expect(screen.getByText("Printing still locked")).toBeInTheDocument();
    expect(readOnlyVerify).toHaveBeenCalledWith("mock-minix-0194");

    fireEvent.click(screen.getByRole("button", { name: "Export read-only artifact" }));

    expect(await screen.findByText("Hardware artifact exported")).toBeInTheDocument();
    expect(screen.getByText("Ready for physical validation record")).toBeInTheDocument();
    expect(exportHardwareTest).toHaveBeenCalledWith("mock-minix-0194");
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(clickDownload).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:hardware-test");
  });

  it("checks host Bluetooth readiness before Stage A scan", async () => {
    const check = vi.fn().mockResolvedValue({
      status: "not_visible",
      platform: "Darwin",
      controllerVisible: false,
      canAttemptStageA: false,
      detail: "macOS did not report a Bluetooth controller to this process.",
      recommendedActions: [
        "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
        "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed local session with Bluetooth access."
      ],
      checks: [
        {
          name: "system_profiler SPBluetoothDataType",
          status: "not_visible",
          evidence: "controllerInfo == nil"
        }
      ]
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        hardwareReadinessProvider={{ check }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Check host Bluetooth" }));

    await waitFor(() => {
      expect(check).toHaveBeenCalledOnce();
    });
    expect(await screen.findByText("Host Bluetooth not visible")).toBeInTheDocument();
    expect(
      screen.getByText("macOS did not report a Bluetooth controller to this process.")
    ).toBeInTheDocument();
    expect(screen.getByText("controllerInfo == nil")).toBeInTheDocument();
    expect(screen.getByText("Recommended actions")).toBeInTheDocument();
    expect(
      screen.getByText("Open macOS System Settings > Bluetooth and confirm Bluetooth is on.")
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed local session with Bluetooth access."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Stage A unavailable from this host")).toBeInTheDocument();
  });

  it("inspects an exported Stage A artifact and shows the protocol sanity preflight", async () => {
    const inspect = vi.fn().mockResolvedValue({
      artifactPath: "/tmp/hardware-test-stage-a.zip",
      inspection: {
        status: "valid_stage_a_artifact",
        deviceId: "mock-minix-0194",
        profileId: "seznik-minix-s1-lyin48d-gy",
        nextRequiredStage: "protocol_sanity_test"
      },
      preflight: {
        status: "protocol_sanity_preflight_ready",
        stage: "protocol_sanity_test",
        deviceId: "mock-minix-0194",
        profileId: "seznik-minix-s1-lyin48d-gy",
        writeCharacteristic: "0000ff02-0000-1000-8000-00805f9b34fb",
        notifyCharacteristics: ["0000ff01-0000-1000-8000-00805f9b34fb"],
        density: "medium",
        paperMode: "continuous",
        printCommandsSent: false,
        rasterBytesIncluded: false,
        commands: [
          {
            index: 0,
            name: "wake",
            payloadBytes: 12,
            hex: "00 00 00 00 00 00 00 00 00 00 00 00"
          },
          {
            index: 1,
            name: "set_density",
            payloadBytes: 5,
            hex: "10 ff 10 00 01"
          }
        ],
        safety: {
          requiresPhysicalPrinter: true,
          requiresUserConfirmation: true,
          sendsRaster: false,
          unlocksPrinting: false
        }
      },
      evidenceSummary: {
        status: "shareable_stage_a_evidence_ready",
        shareable: true,
        artifactStatus: "valid_stage_a_artifact",
        profileId: "seznik-minix-s1-lyin48d-gy",
        nextRequiredStage: "protocol_sanity_test",
        device: {
          idRedacted: true,
          fingerprint: "sha256:3d90f3ac7a07147e"
        },
        redaction: {
          artifactPathIncluded: false,
          localPathsIncluded: false,
          rawCommandLogIncluded: false,
          rawNotificationLogIncluded: false,
          commandPayloadHexIncluded: false,
          rasterBytesIncluded: false,
          bearerTokensIncluded: false
        },
        certification: {
          stageAReadOnlyVerified: true,
          printingLocked: true,
          certificationComplete: false,
          requiresStageBProtocolSanity: true,
          requiresTinyVisualCard: true,
          requiresLongPrintReliability: true
        },
        preflights: {
          protocolSanity: {
            status: "protocol_sanity_preflight_ready",
            stage: "protocol_sanity_test",
            commandCount: 3,
            sendsRaster: false,
            unlocksPrinting: false
          },
          tinyVisualCard: {
            status: "tiny_visual_card_preflight_ready",
            stage: "tiny_visual_test_card",
            displayText: "MINIX TEST 7K4P",
            heightDots: 160,
            rawBytesIncluded: false,
            contentSha256:
              "d1f0cdbf2eb7b70262fbe7825ac39e47847d3eaccc8737f4ff61a1970a9beb31"
          }
        }
      },
      visualCardPreflight: {
        status: "tiny_visual_card_preflight_ready",
        stage: "tiny_visual_test_card",
        deviceId: "mock-minix-0194",
        profileId: "seznik-minix-s1-lyin48d-gy",
        requiredPriorStage: "protocol_sanity_test",
        displayText: "MINIX TEST 7K4P",
        widthDots: 384,
        heightDots: 160,
        rowBytes: 48,
        density: "medium",
        paperMode: "continuous",
        printCommandsSent: false,
        rasterBytesIncluded: false,
        plannedRaster: {
          commandName: "raster_test_card",
          payloadBytes: 7688,
          rasterBytes: 7680,
          rawBytesIncluded: false,
          contentSha256:
            "d1f0cdbf2eb7b70262fbe7825ac39e47847d3eaccc8737f4ff61a1970a9beb31"
        },
        confirmationChecklist: [
          "Text MINIX TEST 7K4P is readable.",
          "Left and right edge markers are visible.",
          "Output is not mirrored or upside down.",
          "Feed is smooth with no stall, overheat warning, disconnect, or fatal error."
        ],
        safety: {
          requiresPhysicalPrinter: true,
          requiresUserConfirmation: true,
          requiresPriorProtocolSanity: true,
          sendsRasterIfExecuted: true,
          unlocksPrinting: false,
          preflightOnly: true
        }
      }
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
        hardwareArtifactInspector={{ inspect }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Inspect Stage A artifact" }));

    await waitFor(() => {
      expect(inspect).toHaveBeenCalledOnce();
    });
    expect(await screen.findByText("Protocol sanity preflight ready")).toBeInTheDocument();
    expect(screen.getByText("mock-minix-0194")).toBeInTheDocument();
    expect(screen.getByText("wake")).toBeInTheDocument();
    expect(screen.getByText("10 ff 10 00 01")).toBeInTheDocument();
    expect(screen.getByText("Tiny visual card preflight ready")).toBeInTheDocument();
    expect(screen.getByText("MINIX TEST 7K4P")).toBeInTheDocument();
    expect(screen.getByText("160 dots")).toBeInTheDocument();
    expect(
      screen.getByText("Visual card still requires Stage B pass")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Text MINIX TEST 7K4P is readable.")
    ).toBeInTheDocument();
    expect(screen.getByText("Shareable evidence summary ready")).toBeInTheDocument();
    expect(screen.getByText("sha256:3d90f3ac7a07147e")).toBeInTheDocument();
    expect(screen.getByText("3 commands planned")).toBeInTheDocument();
    expect(screen.getByText("Raw bytes omitted")).toBeInTheDocument();
    expect(screen.getByText("Local paths omitted")).toBeInTheDocument();
    expect(screen.getByText("Printing remains locked")).toBeInTheDocument();
  });

  it("adds a text layer from the canvas tool and persists the document", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Text" }));

    expect(await screen.findAllByText("Double-click to edit")).toHaveLength(3);
    expect(screen.getByText("Text 1")).toBeInTheDocument();

    const stored = JSON.parse(
      localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
    );
    expect(stored.elements).toEqual([
      expect.objectContaining({
        type: "text",
        name: "Text 1",
        text: "Double-click to edit",
        x: 24,
        y: 56
      })
    ]);
  });

  it("edits text inline from the canvas overlay and keeps undo history", async () => {
    const { container } = render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Text" }));

    await screen.findAllByText("Double-click to edit");
    const canvasText = container.querySelector('[data-konva-node="Text"][data-testid^="el_"]');
    expect(canvasText).toBeInstanceOf(HTMLElement);

    fireEvent.doubleClick(canvasText as HTMLElement);

    const inlineEditor = await screen.findByRole("textbox", { name: "Inline text" });
    fireEvent.change(inlineEditor, { target: { value: "Fresh thermal label" } });
    fireEvent.blur(inlineEditor);

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "text",
          name: "Text 1",
          text: "Fresh thermal label"
        })
      ]);
    });
    expect(screen.queryByRole("textbox", { name: "Inline text" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "text",
          name: "Text 1",
          text: "Double-click to edit"
        })
      ]);
    });
  });

  it("zooms the canvas from footer controls without changing the print document", async () => {
    const { container } = render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    await screen.findAllByText("Double-click to edit");

    const initialStored = localStorage.getItem("minix.printStudio.currentDocument.v1");
    expect(initialStored).toBeTruthy();
    expect(screen.getByText("Zoom 100%")).toBeInTheDocument();

    let stage = container.querySelector('[data-konva-node="Stage"]');
    expect(stage).toHaveAttribute("data-scale-x", "1");
    expect(stage).toHaveAttribute("data-scale-y", "1");
    expect(stage).toHaveAttribute("data-width", "384");

    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));

    expect(screen.getByText("Zoom 125%")).toBeInTheDocument();
    stage = container.querySelector('[data-konva-node="Stage"]');
    expect(stage).toHaveAttribute("data-scale-x", "1.25");
    expect(stage).toHaveAttribute("data-scale-y", "1.25");
    expect(stage).toHaveAttribute("data-width", "480");
    expect(localStorage.getItem("minix.printStudio.currentDocument.v1")).toBe(initialStored);

    fireEvent.click(screen.getByRole("button", { name: "Reset zoom" }));
    expect(screen.getByText("Zoom 100%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(screen.getByText("Zoom 75%")).toBeInTheDocument();
    stage = container.querySelector('[data-konva-node="Stage"]');
    expect(stage).toHaveAttribute("data-scale-x", "0.75");
    expect(stage).toHaveAttribute("data-width", "288");
    expect(localStorage.getItem("minix.printStudio.currentDocument.v1")).toBe(initialStored);
  });

  it("pans the canvas viewport from footer controls without changing the print document", async () => {
    const { container } = render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    await screen.findAllByText("Double-click to edit");

    const initialStored = localStorage.getItem("minix.printStudio.currentDocument.v1");
    expect(initialStored).toBeTruthy();

    const viewport = container.querySelector('[data-testid="canvas-pan-viewport"]');
    expect(viewport).toHaveStyle({ transform: "translate(0px, 0px)" });

    fireEvent.click(screen.getByRole("button", { name: "Pan right" }));
    expect(viewport).toHaveStyle({ transform: "translate(48px, 0px)" });

    fireEvent.click(screen.getByRole("button", { name: "Pan down" }));
    expect(viewport).toHaveStyle({ transform: "translate(48px, 48px)" });
    expect(localStorage.getItem("minix.printStudio.currentDocument.v1")).toBe(initialStored);

    fireEvent.click(screen.getByRole("button", { name: "Reset pan" }));
    expect(viewport).toHaveStyle({ transform: "translate(0px, 0px)" });
    expect(localStorage.getItem("minix.printStudio.currentDocument.v1")).toBe(initialStored);
  });

  it("shows transformer handles for a selected layer and persists resize rotate edits", async () => {
    const { container } = render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Rectangle" }));
    expect(await screen.findByText("Rectangle 1")).toBeInTheDocument();

    const transformer = container.querySelector('[data-konva-node="Transformer"]');
    expect(transformer).toBeInstanceOf(HTMLElement);
    expect(transformer).toHaveAttribute("data-rotate-enabled", "true");
    expect(transformer?.getAttribute("data-enabled-anchors")).toContain("bottom-right");

    const rectNode = container.querySelector('[data-konva-node="Rect"][data-testid^="el_"]');
    expect(rectNode).toBeInstanceOf(HTMLElement);
    rectNode?.dispatchEvent(
      new CustomEvent("konva-transform-end", {
        bubbles: true,
        detail: {
          x: 48,
          y: 176,
          width: 280,
          height: 96,
          rotation: 15,
          scaleX: 1,
          scaleY: 1
        }
      })
    );

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "rect",
          name: "Rectangle 1",
          x: 48,
          y: 176,
          width: 280,
          height: 96,
          rotation: 15
        })
      ]);
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "rect",
          name: "Rectangle 1",
          x: 32,
          y: 144,
          width: 320,
          height: 72,
          rotation: 0
        })
      ]);
    });
  });

  it("edits the selected rectangle through the inspector and persists the document", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Rectangle" }));

    expect(await screen.findByRole("heading", { name: "Inspector" })).toBeInTheDocument();
    expect(screen.getAllByText("Rectangle 1")).not.toHaveLength(0);

    fireEvent.change(screen.getByRole("spinbutton", { name: "X" }), {
      target: { value: "48" }
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Width" }), {
      target: { value: "280" }
    });
    fireEvent.click(screen.getByRole("button", { name: "White fill" }));

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "rect",
          name: "Rectangle 1",
          x: 48,
          width: 280,
          fill: "#ffffff"
        })
      ]);
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();
  });

  it("adds a QR layer from the canvas tool and edits payload through the inspector", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "QR" }));

    expect(await screen.findByText("QR 1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inspector" })).toBeInTheDocument();
    expect(screen.getByText("QR")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "QR Payload" }), {
      target: { value: "https://minix.local/setup" }
    });

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "qr",
          name: "QR 1",
          payload: "https://minix.local/setup",
          width: 128,
          height: 128,
          errorCorrectionLevel: "M"
        })
      ]);
    });
  });

  it("imports an image file as an embedded image layer and persists preprocessing defaults", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    const pngBase64 =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";
    const imageFile = new File(
      [Uint8Array.from(atob(pngBase64), (character) => character.charCodeAt(0))],
      "logo.png",
      { type: "image/png" }
    );

    fireEvent.change(screen.getByLabelText("Import image"), {
      target: { files: [imageFile] }
    });

    expect(await screen.findByText("Image 1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inspector" })).toBeInTheDocument();
    expect(screen.getAllByText("Image")).not.toHaveLength(0);

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "image",
          name: "Image 1",
          width: 256,
          height: 160,
          fit: "contain",
          processing: {
            threshold: 128,
            invert: false
          },
          source: expect.objectContaining({
            kind: "embedded_data_url",
            mimeType: "image/png",
            dataUrl: expect.stringMatching(new RegExp("^data:image/png;base64,"))
          })
        })
      ]);
    });
  });

  it("adds a rectangle layer and keeps undo redo history persisted", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    const undo = screen.getByRole("button", { name: "Undo" });
    const redo = screen.getByRole("button", { name: "Redo" });
    expect(undo).toBeDisabled();
    expect(redo).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Rectangle" }));

    expect(await screen.findByText("Rectangle 1")).toBeInTheDocument();
    expect(undo).toBeEnabled();
    expect(redo).toBeDisabled();

    let stored = JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}");
    expect(stored.elements).toEqual([
      expect.objectContaining({
        type: "rect",
        name: "Rectangle 1",
        x: 32,
        y: 144,
        width: 320,
        height: 72
      })
    ]);

    fireEvent.click(undo);

    await waitFor(() => {
      expect(screen.queryByText("Rectangle 1")).not.toBeInTheDocument();
    });
    expect(undo).toBeDisabled();
    expect(redo).toBeEnabled();
    stored = JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}");
    expect(stored.elements).toEqual([]);

    fireEvent.click(redo);

    expect(await screen.findByText("Rectangle 1")).toBeInTheDocument();
    expect(undo).toBeEnabled();
    expect(redo).toBeDisabled();
  });

  it("inserts long-print test markers from the canvas tool and keeps undo history", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn()
        }}
      />
    );

    const undo = screen.getByRole("button", { name: "Undo" });
    expect(undo).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Insert long-print test markers" }));

    expect(await screen.findAllByText("END LP-TEST checksum: 7F3A")).not.toHaveLength(0);
    expect(screen.getAllByText("25% marker")).not.toHaveLength(0);
    expect(undo).toBeEnabled();

    let stored = JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}");
    expect(stored.target.heightDots).toBe(8000);
    expect(stored.elements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "lp_test_marker_start",
          type: "text",
          text: "START LP-TEST job_fixture"
        }),
        expect.objectContaining({
          id: "lp_test_marker_end",
          type: "text",
          text: "END LP-TEST checksum: 7F3A",
          y: 7904
        })
      ])
    );

    fireEvent.click(undo);

    await waitFor(() => {
      stored = JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}");
      expect(stored.target.heightDots).toBe(900);
      expect(stored.elements).toEqual([]);
    });
  });

  it("loads and saves projects through the daemon project API", async () => {
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_saved",
          name: "Saved checklist",
          documentId: "doc_saved",
          updatedAt: "2026-06-05T00:00:00Z"
        }
      ]
    });
    const createProject = vi.fn().mockResolvedValue({
      projectId: "prj_new",
      name: "Untitled print",
      document: {
        id: "doc_new"
      },
      createdAt: "2026-06-05T00:01:00Z",
      updatedAt: "2026-06-05T00:01:00Z"
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          createProject
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));

    expect(await screen.findByText("Saved checklist")).toBeInTheDocument();
    expect(listProjects).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Save project" }));

    await waitFor(() => {
      expect(createProject).toHaveBeenCalledWith({
        name: "Untitled print",
        document: expect.objectContaining({
          title: "Untitled print",
          target: expect.objectContaining({
            profileId: "seznik-minix-s1-lyin48d-gy"
          })
        })
      });
    });
    expect(await screen.findByText("Saved project prj_new")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("minix.printStudio.projectSession.v1") ?? "{}")).toEqual(
      { activeProjectId: "prj_new" }
    );
  });

  it("opens a saved daemon project into the editor", async () => {
    const loadedDocument = createDefaultDocument({
      title: "Loaded checklist",
      now: new Date("2026-06-05T00:02:00.000Z")
    });
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_loaded",
          name: "Loaded checklist",
          documentId: loadedDocument.id,
          updatedAt: "2026-06-05T00:02:00Z"
        }
      ]
    });
    const getProject = vi.fn().mockResolvedValue({
      projectId: "prj_loaded",
      name: "Loaded checklist",
      document: loadedDocument,
      createdAt: "2026-06-05T00:02:00Z",
      updatedAt: "2026-06-05T00:02:00Z"
    });

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          getProject
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));
    expect(await screen.findByText("Loaded checklist")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open Loaded checklist project" }));

    await waitFor(() => {
      expect(getProject).toHaveBeenCalledWith("prj_loaded");
    });
    expect(await screen.findByText("Opened project prj_loaded")).toBeInTheDocument();
    expect(screen.getByText("Loaded checklist - continuous paper")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}")).toEqual(
      loadedDocument
    );
    expect(JSON.parse(localStorage.getItem("minix.printStudio.projectSession.v1") ?? "{}")).toEqual(
      { activeProjectId: "prj_loaded" }
    );
  });

  it("restores the last opened daemon project before using the local document cache", async () => {
    const staleLocalDocument = createDefaultDocument({
      title: "Stale local draft",
      now: new Date("2026-06-05T00:02:30.000Z")
    });
    const daemonDocument = createDefaultDocument({
      title: "Daemon session",
      now: new Date("2026-06-05T00:02:31.000Z")
    });
    const getProject = vi.fn().mockResolvedValue({
      projectId: "prj_session",
      name: "Daemon session",
      document: daemonDocument,
      createdAt: "2026-06-05T00:02:31Z",
      updatedAt: "2026-06-05T00:02:31Z"
    });
    localStorage.setItem(
      "minix.printStudio.currentDocument.v1",
      JSON.stringify(staleLocalDocument)
    );
    localStorage.setItem(
      "minix.printStudio.projectSession.v1",
      JSON.stringify({ activeProjectId: "prj_session" })
    );

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          getProject
        }}
      />
    );

    await waitFor(() => {
      expect(getProject).toHaveBeenCalledWith("prj_session");
    });
    expect(await screen.findByText("Opened project prj_session")).toBeInTheDocument();
    expect(screen.getByText("Daemon session - continuous paper")).toBeInTheDocument();
    expect(screen.queryByText("Stale local draft - continuous paper")).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}")).toEqual(
      daemonDocument
    );
  });

  it("updates the opened daemon project when saving document changes", async () => {
    const loadedDocument = createDefaultDocument({
      title: "Loaded checklist",
      now: new Date("2026-06-05T00:03:00.000Z")
    });
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_loaded",
          name: "Loaded checklist",
          documentId: loadedDocument.id,
          updatedAt: "2026-06-05T00:03:00Z"
        }
      ]
    });
    const getProject = vi.fn().mockResolvedValue({
      projectId: "prj_loaded",
      name: "Loaded checklist",
      document: loadedDocument,
      createdAt: "2026-06-05T00:03:00Z",
      updatedAt: "2026-06-05T00:03:00Z"
    });
    const createProject = vi.fn().mockResolvedValue({
      projectId: "prj_duplicate",
      name: "Loaded checklist",
      document: loadedDocument,
      createdAt: "2026-06-05T00:04:00Z",
      updatedAt: "2026-06-05T00:04:00Z"
    });
    const updateProject = vi.fn(
      async (_projectId: string, request: ProjectMutationRequest) => ({
        projectId: "prj_loaded",
        name: request.name,
        document: request.document as unknown as Record<string, unknown>,
        createdAt: "2026-06-05T00:03:00Z",
        updatedAt: "2026-06-05T00:05:00Z"
      })
    );

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          createProject,
          getProject,
          updateProject
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));
    expect(await screen.findByText("Loaded checklist")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Loaded checklist project" }));
    expect(await screen.findByText("Opened project prj_loaded")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Rectangle" }));
    expect(await screen.findByText("Rectangle 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));

    await waitFor(() => {
      expect(updateProject).toHaveBeenCalledWith(
        "prj_loaded",
        expect.objectContaining({
          name: "Loaded checklist",
          document: expect.objectContaining({
            title: "Loaded checklist",
            elements: expect.arrayContaining([
              expect.objectContaining({ name: "Rectangle 1", type: "rect" })
            ])
          })
        })
      );
    });
    expect(createProject).not.toHaveBeenCalled();
    expect(await screen.findByText("Saved project prj_loaded")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("minix.printStudio.projectSession.v1") ?? "{}")).toEqual(
      { activeProjectId: "prj_loaded" }
    );
  });

  it("confirms and deletes a saved daemon project from the project list", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_delete",
          name: "Delete checklist",
          documentId: "doc_delete",
          updatedAt: "2026-06-05T00:06:00Z"
        }
      ]
    });
    const deleteProject = vi.fn().mockResolvedValue(undefined);

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          deleteProject
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));
    expect(await screen.findByText("Delete checklist")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete Delete checklist project" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Delete checklist"));
    await waitFor(() => {
      expect(deleteProject).toHaveBeenCalledWith("prj_delete");
    });
    expect(await screen.findByText("Deleted project prj_delete")).toBeInTheDocument();
    expect(screen.queryByText("Delete checklist")).not.toBeInTheDocument();

    confirm.mockRestore();
  });

  it("clears the remembered daemon project session after deleting the opened project", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const openedDocument = createDefaultDocument({
      title: "Session cleanup",
      now: new Date("2026-06-05T00:06:30.000Z")
    });
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_cleanup",
          name: "Session cleanup",
          documentId: openedDocument.id,
          updatedAt: "2026-06-05T00:06:30Z"
        }
      ]
    });
    const getProject = vi.fn().mockResolvedValue({
      projectId: "prj_cleanup",
      name: "Session cleanup",
      document: openedDocument,
      createdAt: "2026-06-05T00:06:30Z",
      updatedAt: "2026-06-05T00:06:30Z"
    });
    const deleteProject = vi.fn().mockResolvedValue(undefined);

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          getProject,
          deleteProject
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));
    expect(await screen.findByText("Session cleanup")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Session cleanup project" }));
    expect(await screen.findByText("Opened project prj_cleanup")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete Session cleanup project" }));

    await waitFor(() => {
      expect(deleteProject).toHaveBeenCalledWith("prj_cleanup");
    });
    expect(localStorage.getItem("minix.printStudio.projectSession.v1")).toBeNull();

    confirm.mockRestore();
  });

  it("uploads imported images to the opened daemon project asset store", async () => {
    const loadedDocument = createDefaultDocument({
      title: "Asset-backed checklist",
      now: new Date("2026-06-05T00:07:00.000Z")
    });
    const listProjects = vi.fn().mockResolvedValue({
      projects: [
        {
          projectId: "prj_assets",
          name: "Asset-backed checklist",
          documentId: loadedDocument.id,
          updatedAt: "2026-06-05T00:07:00Z"
        }
      ]
    });
    const getProject = vi.fn().mockResolvedValue({
      projectId: "prj_assets",
      name: "Asset-backed checklist",
      document: loadedDocument,
      createdAt: "2026-06-05T00:07:00Z",
      updatedAt: "2026-06-05T00:07:00Z"
    });
    const uploadProjectAsset = vi.fn().mockResolvedValue({
      assetId: "sha256-uploaded",
      sha256: "uploaded",
      fileName: "logo.png",
      mimeType: "image/png",
      byteLength: 68
    });
    const pngBase64 =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";
    const imageFile = new File(
      [Uint8Array.from(atob(pngBase64), (character) => character.charCodeAt(0))],
      "logo.png",
      { type: "image/png" }
    );

    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          }),
          createDocumentPreview: vi.fn(),
          planApprovedPreview: vi.fn(),
          printApprovedPreview: vi.fn(),
          scanPrinters: vi.fn(),
          readOnlyVerify: vi.fn(),
          listProjects,
          getProject,
          uploadProjectAsset
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Load projects" }));
    expect(await screen.findByText("Asset-backed checklist")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Asset-backed checklist project" }));
    expect(await screen.findByText("Opened project prj_assets")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Import image"), {
      target: { files: [imageFile] }
    });

    await waitFor(() => {
      expect(uploadProjectAsset).toHaveBeenCalledWith("prj_assets", {
        fileName: "logo.png",
        mimeType: "image/png",
        dataBase64: pngBase64
      });
    });
    expect(await screen.findByText("Image 1")).toBeInTheDocument();

    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("minix.printStudio.currentDocument.v1") ?? "{}"
      );
      expect(stored.assets).toEqual([
        expect.objectContaining({
          kind: "daemon_project_asset",
          projectId: "prj_assets",
          assetId: "sha256-uploaded",
          fileName: "logo.png",
          mimeType: "image/png",
          byteLength: 68
        })
      ]);
      expect(stored.elements).toEqual([
        expect.objectContaining({
          type: "image",
          source: expect.objectContaining({
            projectAsset: expect.objectContaining({
              projectId: "prj_assets",
              assetId: "sha256-uploaded"
            })
          })
        })
      ]);
    });
  });
});
