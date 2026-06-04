import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";

describe("MiniX Print Studio shell", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
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
    await screen.findByText("Preview ready");
    fireEvent.click(screen.getByRole("button", { name: "Print" }));

    expect(await screen.findByText("completed_unverified")).toBeInTheDocument();
    expect(screen.getByText("User check required")).toBeInTheDocument();
    expect(screen.getByText("Confirm complete")).toBeInTheDocument();
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
          readOnlyVerify
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

    expect(await screen.findAllByText("Double-click to edit")).toHaveLength(2);
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
});
