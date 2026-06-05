import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";

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
  });
});
