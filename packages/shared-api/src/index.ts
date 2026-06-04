import { z } from "zod";

const UUID_FF00 = "0000ff00-0000-1000-8000-00805f9b34fb";

export const supportLevelSchema = z.enum([
  "official",
  "community_verified",
  "experimental",
  "detected_unverified",
  "unsupported"
]);

export const healthResponseSchema = z.object({
  ok: z.boolean(),
  version: z.string(),
  profileRegistryVersion: z.string(),
  mock: z.boolean()
});

export const printerProfileSchema = z.object({
  id: z.string(),
  displayName: z.string(),
  supportLevel: supportLevelSchema,
  profileVersion: z.string(),
  manufacturer: z.string(),
  modelResponse: z.string(),
  observedFirmware: z.array(z.string()),
  namePrefixes: z.array(z.string()),
  ble: z.object({
    serviceUuid: z.string(),
    writeCharUuid: z.string(),
    notifyCharUuids: z.array(z.string()),
    defaultChunkSize: z.number().int().positive(),
    minChunkSize: z.number().int().positive(),
    maxTestedChunkSize: z.number().int().positive(),
    writeWithResponse: z.boolean(),
    defaultInterChunkDelayMs: z.number().int().nonnegative(),
    flowControlNotifyCharUuid: z.string()
  }),
  print: z.object({
    protocol: z.literal("aiyin-gs-v0-wrapper"),
    widthDots: z.number().int().positive(),
    rowBytes: z.number().int().positive(),
    bitOrder: z.literal("msb-first"),
    blackBit: z.literal(1),
    defaultPaperMode: z.literal("continuous"),
    paperModes: z.array(z.enum(["continuous", "gap_label", "black_mark"])),
    densityModes: z.array(z.enum(["light", "medium", "dark"])),
    defaultDensity: z.enum(["light", "medium", "dark"]),
    longPrint: z.object({
      transferMode: z.literal("banded_gs_v0"),
      longPrintThresholdDots: z.number().int().positive(),
      defaultMaxBandHeightDots: z.number().int().positive(),
      appendTailBlankRowsContinuous: z.number().int().nonnegative(),
      finalAckPolicy: z.literal("required_for_confirmed_optional_for_unverified"),
      supportsResume: z.boolean(),
      pauseOnlyBetweenBands: z.boolean()
    })
  }),
  safety: z.object({
    maxHeightDotsManual: z.number().int().positive(),
    maxHeightDotsAgentDirect: z.number().int().positive(),
    maxCopiesAgentDirect: z.number().int().positive(),
    warnTotalBlackCoverage: z.number().min(0).max(1),
    blockAgentTotalBlackCoverage: z.number().min(0).max(1),
    blockBandCoverage: z.number().min(0).max(1),
    bandHeightDots: z.number().int().positive()
  })
});

export type PrinterProfile = z.infer<typeof printerProfileSchema>;
export type HealthResponse = z.infer<typeof healthResponseSchema>;
export type SupportLevel = z.infer<typeof supportLevelSchema>;

export type DiscoveredPrinter = {
  name: string | null;
  serviceUuids: string[];
};

export type PrinterSupport = {
  level: SupportLevel;
  candidateProfileIds: string[];
  reason: string;
};

export const seznikMiniXProfile = {
  id: "seznik-minix-s1-lyin48d-gy",
  displayName: "Seznik MiniX - S1_LYiN48D_GY",
  supportLevel: "official",
  profileVersion: "1.0.0",
  manufacturer: "unknown-or-confirm-after-user-input",
  modelResponse: "S1_LYiN48D_GY",
  observedFirmware: ["V1.9.11"],
  namePrefixes: ["Seznik MiniX"],
  ble: {
    serviceUuid: UUID_FF00,
    writeCharUuid: "0000ff02-0000-1000-8000-00805f9b34fb",
    notifyCharUuids: [
      "0000ff01-0000-1000-8000-00805f9b34fb",
      "0000ff03-0000-1000-8000-00805f9b34fb"
    ],
    defaultChunkSize: 90,
    minChunkSize: 20,
    maxTestedChunkSize: 90,
    writeWithResponse: true,
    defaultInterChunkDelayMs: 25,
    flowControlNotifyCharUuid: "0000ff03-0000-1000-8000-00805f9b34fb"
  },
  print: {
    protocol: "aiyin-gs-v0-wrapper",
    widthDots: 384,
    rowBytes: 48,
    bitOrder: "msb-first",
    blackBit: 1,
    defaultPaperMode: "continuous",
    paperModes: ["continuous", "gap_label", "black_mark"],
    densityModes: ["light", "medium", "dark"],
    defaultDensity: "medium",
    longPrint: {
      transferMode: "banded_gs_v0",
      longPrintThresholdDots: 1200,
      defaultMaxBandHeightDots: 256,
      appendTailBlankRowsContinuous: 160,
      finalAckPolicy: "required_for_confirmed_optional_for_unverified",
      supportsResume: false,
      pauseOnlyBetweenBands: true
    }
  },
  safety: {
    maxHeightDotsManual: 1600,
    maxHeightDotsAgentDirect: 1000,
    maxCopiesAgentDirect: 1,
    warnTotalBlackCoverage: 0.35,
    blockAgentTotalBlackCoverage: 0.45,
    blockBandCoverage: 0.7,
    bandHeightDots: 64
  }
} satisfies PrinterProfile;

export const knownPrinterProfiles = [seznikMiniXProfile] as const;

export function classifyDiscoveredPrinter(device: DiscoveredPrinter): PrinterSupport {
  const normalizedServices = device.serviceUuids.map((uuid) => uuid.toLowerCase());
  const profile = seznikMiniXProfile;

  if (!normalizedServices.includes(profile.ble.serviceUuid)) {
    return {
      level: "unsupported",
      candidateProfileIds: [],
      reason: "No known MiniX printer profile signal matched."
    };
  }

  const hasNameMatch = profile.namePrefixes.some((prefix) => device.name?.startsWith(prefix));

  return {
    level: "detected_unverified",
    candidateProfileIds: [profile.id],
    reason: hasNameMatch
      ? "Service UUID and name match; model query required."
      : "Service UUID matches; model query required."
  };
}
