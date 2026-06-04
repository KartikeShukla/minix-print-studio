import { describe, expect, it } from "vitest";
import {
  classifyDiscoveredPrinter,
  healthResponseSchema,
  printerProfileSchema,
  seznikMiniXProfile
} from "../src/index";

describe("printer profile contracts", () => {
  it("validates the official Seznik MiniX profile", () => {
    const parsed = printerProfileSchema.parse(seznikMiniXProfile);

    expect(parsed.id).toBe("seznik-minix-s1-lyin48d-gy");
    expect(parsed.print.widthDots).toBe(384);
    expect(parsed.print.rowBytes).toBe(48);
    expect(parsed.ble.writeWithResponse).toBe(true);
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
