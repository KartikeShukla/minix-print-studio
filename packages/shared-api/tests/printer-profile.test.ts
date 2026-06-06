import { describe, expect, it } from "vitest";
import {
  classifyDiscoveredPrinter,
  healthResponseSchema,
  printPlanResponseSchema,
  projectAssetResponseSchema,
  projectListResponseSchema,
  projectResponseSchema,
  printerCandidateSchema,
  printerProfileSchema,
  readOnlyVerificationSchema,
  seznikMiniXProfile
} from "../src/index";

describe("printer profile contracts", () => {
  it("validates the official Seznik MiniX profile", () => {
    const parsed = printerProfileSchema.parse(seznikMiniXProfile);

    expect(parsed.id).toBe("seznik-minix-s1-lyin48d-gy");
    expect(parsed.print.widthDots).toBe(384);
    expect(parsed.print.rowBytes).toBe(48);
    expect(parsed.ble.writeWithResponse).toBe(true);
    expect(parsed.print.longPrint.thermalPacing.baseInterBandDelayMs).toBe(125);
    expect(parsed.print.longPrint.thermalPacing.cooldownBandCoverage).toBe(0.35);
    expect(parsed.readOnly.modelCommandHex).toBe("10 ff 20 f0");
    expect(parsed.readOnly.firmwareCommandHex).toBe("10 ff 20 f1");
  });

  it("classifies a service/name match as detected but not trusted before model verification", () => {
    const support = classifyDiscoveredPrinter({
      name: "Seznik MiniX_0194_LE",
      serviceUuids: ["0000ff00-0000-1000-8000-00805f9b34fb"]
    });

    expect(support).toEqual({
      level: "detected_unverified",
      candidateProfileIds: ["seznik-minix-s1-lyin48d-gy"],
      reason: "Service UUID and name match; model query required."
    });
  });

  it("rejects generic FF00 support claims without a matching profile signal", () => {
    const support = classifyDiscoveredPrinter({
      name: "Generic Thermal",
      serviceUuids: ["0000ff00-0000-1000-8000-00805f9b34fb"]
    });

    expect(support.level).toBe("detected_unverified");
    expect(support.reason).toBe("Service UUID matches; model query required.");
  });
});

describe("print plan API contracts", () => {
  it("validates redacted thermal pacing metadata for planned bands", () => {
    const parsed = printPlanResponseSchema.parse({
      plan: {
        planId: "plan_job",
        jobId: "job",
        previewId: "prev",
        documentHash: "sha256:document",
        rasterHash: "sha256:raster",
        profileId: "seznik-minix-s1-lyin48d-gy",
        paperMode: "continuous",
        density: "medium",
        widthDots: 384,
        contentHeightDots: 300,
        tailBlankRowsDots: 160,
        transferHeightDots: 460,
        rowBytes: 48,
        totalRasterBytes: 22080,
        requiresLongPrintMode: false
      },
      totalBands: 2,
      bands: [
        {
          index: 0,
          startRow: 0,
          heightDots: 256,
          rasterByteOffset: 0,
          rasterByteLength: 12288,
          payloadBytes: 12296,
          blackDotCount: 49152,
          blackCoverage: 0.5,
          cooldownAfterMs: 575,
          sha256: "sha256:band"
        }
      ]
    });

    expect(parsed.bands[0].cooldownAfterMs).toBe(575);
    expect("raster" in parsed.bands[0]).toBe(false);
  });
});

describe("daemon health contract", () => {
  it("requires version, profile registry version, and mock mode", () => {
    const parsed = healthResponseSchema.parse({
      ok: true,
      version: "0.1.0",
      profileRegistryVersion: "2026.06.04",
      mock: true
    });

    expect(parsed.ok).toBe(true);
  });
});

describe("printer discovery API contracts", () => {
  it("validates a detected but untrusted printer candidate", () => {
    const parsed = printerCandidateSchema.parse({
      deviceId: "mock-minix-0194",
      name: "Seznik MiniX_0194_LE",
      serviceUuids: ["0000ff00-0000-1000-8000-00805f9b34fb"],
      rssi: -42,
      supportLevel: "detected_unverified",
      candidateProfileIds: ["seznik-minix-s1-lyin48d-gy"],
      printable: false,
      nextRequiredStage: "read_only_verification",
      reason: "Service UUID and name match; model query required."
    });

    expect(parsed.printable).toBe(false);
    expect(parsed.nextRequiredStage).toBe("read_only_verification");
  });

  it("validates read-only verification without granting print permission", () => {
    const parsed = readOnlyVerificationSchema.parse({
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
    });

    expect(parsed.printable).toBe(false);
    expect(parsed.profileSupportLevel).toBe("official");
  });
});

describe("project API contracts", () => {
  it("validates project records, summaries, and hash-addressed assets", () => {
    const project = projectResponseSchema.parse({
      projectId: "prj_123",
      name: "Kitchen checklist",
      document: {
        schemaVersion: 1,
        id: "doc_project",
        title: "Project fixture",
        target: {
          profileId: "seznik-minix-s1-lyin48d-gy",
          widthDots: 384,
          heightDots: 120,
          dpi: 203,
          paperMode: "continuous",
          density: "medium"
        },
        background: { color: "#ffffff" },
        elements: [],
        assets: [],
        metadata: {}
      },
      createdAt: "2026-06-05T00:00:00Z",
      updatedAt: "2026-06-05T00:00:00Z"
    });
    const list = projectListResponseSchema.parse({
      projects: [
        {
          projectId: project.projectId,
          name: project.name,
          documentId: "doc_project",
          updatedAt: project.updatedAt
        }
      ]
    });
    const asset = projectAssetResponseSchema.parse({
      assetId: "sha256-abc123",
      sha256: "abc123",
      fileName: "badge.png",
      mimeType: "image/png",
      byteLength: 18
    });

    expect(list.projects[0].documentId).toBe("doc_project");
    expect(asset.assetId).toBe("sha256-abc123");
    expect("path" in asset).toBe(false);
  });
});
