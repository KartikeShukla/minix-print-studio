import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";

describe("MiniX Print Studio shell", () => {
  afterEach(() => {
    cleanup();
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
          planApprovedPreview: vi.fn()
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
          planApprovedPreview
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
  });
});
