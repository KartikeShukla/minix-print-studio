import { createDefaultDocument } from "@minix/design-model";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createDaemonClient } from "../src/lib/api-client";

describe("daemon API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window, "minix");
  });

  it("posts daemon-rendered previews and approval-bound print plans with auth", async () => {
    const previewResponse = {
      previewId: "prev_api",
      approvalToken: "appr_api",
      documentHash: "sha256:document",
      renderSettingsHash: "sha256:settings",
      rasterHash: "sha256:raster",
      profileId: "seznik-minix-s1-lyin48d-gy",
      widthDots: 384,
      heightDots: 900,
      safety: { allowed: true, warnings: [], metrics: {} },
      createdAt: "2026-06-04T00:00:00.000Z",
      expiresAt: "2026-06-04T00:10:00.000Z"
    };
    const planResponse = {
      plan: {
        planId: "plan_job_api",
        jobId: "job_api",
        previewId: "prev_api",
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
      bands: [
        {
          index: 0,
          startRow: 0,
          heightDots: 256,
          rasterByteOffset: 0,
          rasterByteLength: 12288,
          payloadBytes: 12296,
          sha256: "sha256:band"
        }
      ]
    };
    const printResponse = {
      jobId: "job_api",
      previewId: "prev_api",
      planId: "plan_job_api",
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
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => previewResponse })
      .mockResolvedValueOnce({ ok: true, json: async () => planResponse })
      .mockResolvedValueOnce({ ok: true, json: async () => printResponse });
    vi.stubGlobal("fetch", fetchMock);
    window.minix = {
      getDaemonRuntime: async () => ({
        baseUrl: "http://127.0.0.1:39281",
        token: "secret-token"
      }),
      getAppVersion: async () => "0.1.0"
    };

    const client = createDaemonClient();
    const document = createDefaultDocument({
      title: "API fixture",
      now: new Date("2026-06-04T00:00:00.000Z")
    });
    const renderSettings = { threshold: 128, dither: "none" };

    await expect(client.createDocumentPreview(document, renderSettings)).resolves.toEqual(
      previewResponse
    );
    await expect(
      client.planApprovedPreview({
        jobId: "job_api",
        previewId: "prev_api",
        approvalToken: "appr_api",
        documentHash: "sha256:document",
        renderSettingsHash: "sha256:settings",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium"
      })
    ).resolves.toEqual(planResponse);
    await expect(
      client.printApprovedPreview({
        previewId: "prev_api",
        approvalToken: "appr_api",
        documentHash: "sha256:document",
        renderSettingsHash: "sha256:settings",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium",
        copies: 1,
        source: "ui"
      })
    ).resolves.toEqual(printResponse);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:39281/v1/render/document-preview", {
      method: "POST",
      headers: {
        Authorization: "Bearer secret-token",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ document, renderSettings })
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:39281/v1/jobs/plan", {
      method: "POST",
      headers: {
        Authorization: "Bearer secret-token",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        jobId: "job_api",
        previewId: "prev_api",
        approvalToken: "appr_api",
        documentHash: "sha256:document",
        renderSettingsHash: "sha256:settings",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium"
      })
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "http://127.0.0.1:39281/v1/jobs/print", {
      method: "POST",
      headers: {
        Authorization: "Bearer secret-token",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        previewId: "prev_api",
        approvalToken: "appr_api",
        documentHash: "sha256:document",
        renderSettingsHash: "sha256:settings",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium",
        copies: 1,
        source: "ui"
      })
    });
  });

  it("scans and read-only verifies printers through the daemon with auth", async () => {
    const scanResponse = {
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
    };
    const verificationResponse = {
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
      rawNotifications: [],
      timingEvents: []
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => scanResponse })
      .mockResolvedValueOnce({ ok: true, json: async () => verificationResponse });
    vi.stubGlobal("fetch", fetchMock);
    window.minix = {
      getDaemonRuntime: async () => ({
        baseUrl: "http://127.0.0.1:39281",
        token: "secret-token"
      }),
      getAppVersion: async () => "0.1.0"
    };

    const client = createDaemonClient();

    await expect(client.scanPrinters()).resolves.toEqual(scanResponse);
    await expect(client.readOnlyVerify("mock-minix-0194")).resolves.toEqual(verificationResponse);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:39281/v1/printers/scan", {
      method: "POST",
      headers: {
        Authorization: "Bearer secret-token"
      }
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:39281/v1/printers/read-only-verify",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer secret-token",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ deviceId: "mock-minix-0194" })
      }
    );
  });

  it("exports redacted diagnostics through the daemon with auth", async () => {
    const diagnosticsResponse = {
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
      jobs: [{ jobId: "job_api", segments: [] }],
      recentErrors: [],
      recentMcpCalls: []
    };
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => diagnosticsResponse });
    vi.stubGlobal("fetch", fetchMock);
    window.minix = {
      getDaemonRuntime: async () => ({
        baseUrl: "http://127.0.0.1:39281",
        token: "secret-token"
      }),
      getAppVersion: async () => "0.1.0"
    };

    const client = createDaemonClient();

    expect(client.exportDiagnostics).toBeDefined();
    await expect(
      client.exportDiagnostics!({ includeProjectContent: false, includeRawImages: false })
    ).resolves.toEqual(diagnosticsResponse);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:39281/v1/diagnostics/export", {
      method: "POST",
      headers: {
        Authorization: "Bearer secret-token",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ includeProjectContent: false, includeRawImages: false })
    });
  });

  it("exports a read-only hardware artifact through the daemon with auth", async () => {
    const artifact = new Blob(["zip-bytes"], { type: "application/zip" });
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, blob: async () => artifact });
    vi.stubGlobal("fetch", fetchMock);
    window.minix = {
      getDaemonRuntime: async () => ({
        baseUrl: "http://127.0.0.1:39281",
        token: "secret-token"
      }),
      getAppVersion: async () => "0.1.0"
    };

    const client = createDaemonClient();

    await expect(client.exportHardwareTest?.("mock-minix-0194")).resolves.toBe(artifact);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:39281/v1/diagnostics/hardware-test",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer secret-token",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          deviceId: "mock-minix-0194",
          stage: "read_only_verification"
        })
      }
    );
  });
});
