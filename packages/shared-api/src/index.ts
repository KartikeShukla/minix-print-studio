import { z } from "zod";

const UUID_FF00 = "0000ff00-0000-1000-8000-00805f9b34fb";

export const supportLevelSchema = z.enum([
  "official",
  "community_verified",
  "experimental",
  "detected_unverified",
  "unsupported"
]);

export const printerDiscoveryStageSchema = z.enum([
  "read_only_verification",
  "protocol_sanity_test",
  "supported_printer_test",
  "unsupported"
]);

export const readOnlyVerificationStatusSchema = z.enum([
  "read_only_verified",
  "read_only_mismatch"
]);

export const bleTimingEventSchema = z.object({
  operation: z.string(),
  characteristic: z.string().nullable(),
  elapsedMs: z.number().nonnegative(),
  payloadBytes: z.number().int().nonnegative().nullable()
});

export const healthResponseSchema = z.object({
  ok: z.boolean(),
  version: z.string(),
  profileRegistryVersion: z.string(),
  mock: z.boolean()
});

export const renderSettingsSchema = z.record(z.unknown());

export const previewSafetySchema = z
  .object({
    allowed: z.boolean().optional(),
    warnings: z.array(z.unknown()).optional(),
    errors: z.array(z.unknown()).optional(),
    metrics: z.record(z.unknown()).optional()
  })
  .passthrough();

export const documentPreviewResponseSchema = z.object({
  previewId: z.string(),
  approvalToken: z.string(),
  documentHash: z.string(),
  renderSettingsHash: z.string(),
  rasterHash: z.string(),
  profileId: z.string(),
  widthDots: z.number().int().positive(),
  heightDots: z.number().int().positive(),
  safety: previewSafetySchema,
  createdAt: z.string(),
  expiresAt: z.string()
});

export const printPlanBandSchema = z.object({
  index: z.number().int().nonnegative(),
  startRow: z.number().int().nonnegative(),
  heightDots: z.number().int().positive(),
  rasterByteOffset: z.number().int().nonnegative(),
  rasterByteLength: z.number().int().nonnegative(),
  payloadBytes: z.number().int().nonnegative(),
  sha256: z.string()
});

export const printPlanSchema = z.object({
  planId: z.string(),
  jobId: z.string(),
  previewId: z.string(),
  documentHash: z.string(),
  rasterHash: z.string(),
  profileId: z.string(),
  paperMode: z.enum(["continuous", "gap_label", "black_mark"]),
  density: z.enum(["light", "medium", "dark"]),
  widthDots: z.number().int().positive(),
  contentHeightDots: z.number().int().positive(),
  tailBlankRowsDots: z.number().int().nonnegative(),
  transferHeightDots: z.number().int().positive(),
  rowBytes: z.number().int().positive(),
  totalRasterBytes: z.number().int().nonnegative(),
  requiresLongPrintMode: z.boolean()
});

export const printPlanResponseSchema = z.object({
  plan: printPlanSchema,
  totalBands: z.number().int().nonnegative(),
  bands: z.array(printPlanBandSchema)
});

export const printJobResponseSchema = z.object({
  jobId: z.string(),
  previewId: z.string(),
  planId: z.string(),
  state: z.string(),
  phase: z.string(),
  completionLevel: z.string(),
  completionConfidence: z.string(),
  requiresUserCheck: z.boolean(),
  source: z.string(),
  copies: z.number().int().positive(),
  bandsSent: z.number().int().nonnegative(),
  totalBands: z.number().int().nonnegative(),
  rowsSent: z.number().int().nonnegative(),
  totalRows: z.number().int().nonnegative(),
  bytesSent: z.number().int().nonnegative(),
  totalBytes: z.number().int().nonnegative(),
  tailBlankRowsDots: z.number().int().nonnegative(),
  safeActions: z.array(z.string())
});

export const diagnosticsExportResponseSchema = z
  .object({
    schemaVersion: z.number().int().positive(),
    createdAt: z.string(),
    redaction: z
      .object({
        projectContentIncluded: z.boolean(),
        rawImagesIncluded: z.boolean(),
        tokensIncluded: z.boolean()
      })
      .passthrough(),
    daemon: z
      .object({
        version: z.string(),
        profileRegistryVersion: z.string(),
        mock: z.boolean()
      })
      .passthrough(),
    profiles: z.array(z.record(z.unknown())),
    jobs: z.array(z.record(z.unknown())),
    recentErrors: z.array(z.unknown()),
    recentMcpCalls: z.array(z.unknown())
  })
  .passthrough();

export const printerCandidateSchema = z.object({
  deviceId: z.string(),
  name: z.string().nullable(),
  serviceUuids: z.array(z.string()),
  rssi: z.number().int().nullable(),
  supportLevel: supportLevelSchema,
  candidateProfileIds: z.array(z.string()),
  printable: z.boolean(),
  nextRequiredStage: printerDiscoveryStageSchema,
  reason: z.string()
});

export const printerScanResponseSchema = z.object({
  printers: z.array(printerCandidateSchema)
});

export const readOnlyVerificationSchema = z.object({
  status: readOnlyVerificationStatusSchema,
  deviceId: z.string(),
  profileId: z.string().nullable(),
  profileSupportLevel: supportLevelSchema.nullable(),
  modelResponse: z.string().nullable(),
  firmware: z.string().nullable(),
  printable: z.boolean(),
  nextRequiredStage: printerDiscoveryStageSchema,
  reason: z.string(),
  services: z.array(z.string()),
  writeCharacteristics: z.array(z.string()),
  notifyCharacteristics: z.array(z.string()),
  rawNotifications: z.array(z.string()),
  timingEvents: z.array(bleTimingEventSchema).default([])
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
  readOnly: z.object({
    modelCommandHex: z.string(),
    firmwareCommandHex: z.string(),
    responseEncoding: z.literal("ascii-substring")
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
export type RenderSettings = z.infer<typeof renderSettingsSchema>;
export type DocumentPreviewResponse = z.infer<typeof documentPreviewResponseSchema>;
export type PrintPlanResponse = z.infer<typeof printPlanResponseSchema>;
export type PrintJobResponse = z.infer<typeof printJobResponseSchema>;
export type DiagnosticsExportResponse = z.infer<typeof diagnosticsExportResponseSchema>;
export type PrinterCandidate = z.infer<typeof printerCandidateSchema>;
export type PrinterScanResponse = z.infer<typeof printerScanResponseSchema>;
export type ReadOnlyVerification = z.infer<typeof readOnlyVerificationSchema>;
export type SupportLevel = z.infer<typeof supportLevelSchema>;

export type PrintPlanRequest = {
  jobId: string;
  previewId: string;
  approvalToken: string;
  documentHash: string;
  renderSettingsHash: string;
  profileId: string;
  paperMode: "continuous" | "gap_label" | "black_mark";
  density: "light" | "medium" | "dark";
};

export type PrintPreviewRequest = Omit<PrintPlanRequest, "jobId"> & {
  copies: number;
  source: string;
};

export type DiagnosticsExportRequest = {
  includeProjectContent: boolean;
  includeRawImages: boolean;
};

export type HardwareTestExportRequest = {
  deviceId: string;
  stage: "read_only_verification";
  userConfirmation?: Record<string, unknown>;
};

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
  readOnly: {
    modelCommandHex: "10 ff 20 f0",
    firmwareCommandHex: "10 ff 20 f1",
    responseEncoding: "ascii-substring"
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
