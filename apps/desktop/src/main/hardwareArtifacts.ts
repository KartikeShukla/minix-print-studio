import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";

export type HardwareArtifactInspectionSummary = {
  status: string;
  deviceId: string;
  profileId: string;
  nextRequiredStage: string;
};

export type HardwareProtocolCommand = {
  index: number;
  name: string;
  payloadBytes: number;
  hex: string;
};

export type HardwareProtocolPreflight = {
  status: string;
  stage: string;
  deviceId: string;
  profileId: string;
  writeCharacteristic: string;
  notifyCharacteristics: string[];
  density: string;
  paperMode: string;
  printCommandsSent: boolean;
  rasterBytesIncluded: boolean;
  commands: HardwareProtocolCommand[];
  safety: {
    requiresPhysicalPrinter: boolean;
    requiresUserConfirmation: boolean;
    sendsRaster: boolean;
    unlocksPrinting: boolean;
  };
};

export type HardwareVisualCardPreflight = {
  status: string;
  stage: string;
  deviceId: string;
  profileId: string;
  requiredPriorStage: string;
  displayText: string;
  widthDots: number;
  heightDots: number;
  rowBytes: number;
  density: string;
  paperMode: string;
  printCommandsSent: boolean;
  rasterBytesIncluded: boolean;
  plannedRaster: {
    commandName: string;
    payloadBytes: number;
    rasterBytes: number;
    rawBytesIncluded: boolean;
    contentSha256: string;
  };
  confirmationChecklist: string[];
  safety: {
    requiresPhysicalPrinter: boolean;
    requiresUserConfirmation: boolean;
    requiresPriorProtocolSanity: boolean;
    sendsRasterIfExecuted: boolean;
    unlocksPrinting: boolean;
    preflightOnly: boolean;
  };
};

export type HardwareEvidenceSummary = {
  status: string;
  shareable: boolean;
  artifactStatus: string;
  profileId: string;
  nextRequiredStage: string;
  device: {
    idRedacted: boolean;
    fingerprint: string;
  };
  redaction: {
    artifactPathIncluded: boolean;
    localPathsIncluded: boolean;
    rawCommandLogIncluded: boolean;
    rawNotificationLogIncluded: boolean;
    commandPayloadHexIncluded: boolean;
    rasterBytesIncluded: boolean;
    bearerTokensIncluded: boolean;
  };
  certification: {
    stageAReadOnlyVerified: boolean;
    printingLocked: boolean;
    certificationComplete: boolean;
    requiresStageBProtocolSanity: boolean;
    requiresTinyVisualCard: boolean;
    requiresLongPrintReliability: boolean;
  };
  preflights: {
    protocolSanity: {
      status: string;
      stage: string;
      commandCount: number;
      sendsRaster: boolean;
      unlocksPrinting: boolean;
    };
    tinyVisualCard: {
      status: string;
      stage: string;
      displayText: string;
      heightDots: number;
      rawBytesIncluded: boolean;
      contentSha256: string;
    };
  };
};

export type HardwareArtifactInspectionResult = {
  artifactPath: string;
  inspection: HardwareArtifactInspectionSummary;
  preflight: HardwareProtocolPreflight | null;
  visualCardPreflight: HardwareVisualCardPreflight | null;
  evidenceSummary: HardwareEvidenceSummary | null;
};

export type TrustedPrinterRecordSummary = {
  status: string;
  profileId: string;
  device: {
    idRedacted: boolean;
    fingerprint: string;
  };
  trustedFor: string[];
  operatorNoteIncluded: boolean;
  hardwareEvidence: {
    stageA: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    protocolSanity: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    tinyVisualCard: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
  };
  safety: {
    manualContinuousPrintingEnabled: boolean;
    longPrintReliabilityRequired: boolean;
    longPrintPrintingEnabled: boolean;
    agentDirectPrintingEnabled: boolean;
    stableSupportClaimEnabled: boolean;
  };
  nextRequiredStage: string;
};

export type TrustedPrinterRecordInspectionResult = {
  recordPath: string;
  summary: TrustedPrinterRecordSummary;
};

export type StableSupportGateSummary = {
  status: string;
  profileId: string;
  device: {
    idRedacted: boolean;
    fingerprint: string;
  };
  trustedFor: string[];
  operatorNoteIncluded: boolean;
  rasterBytesIncluded: boolean;
  hardwareEvidence: {
    stageA: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    protocolSanity: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    tinyVisualCard: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    trustedPrinter: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
    longPrintReliability: {
      stage: string;
      status: string;
      artifactSha256Included: boolean;
    };
  };
  safety: {
    manualContinuousPrintingEnabled: boolean;
    longPrintReliabilityPassed: boolean;
    longPrintPrintingEnabled: boolean;
    stableSupportClaimEnabled: boolean;
    agentDirectPrintingEnabled: boolean;
    agentDirectPrintingDefault: string;
  };
  nextRequiredStage: string;
};

export type StableSupportGateInspectionResult = {
  recordPath: string;
  summary: StableSupportGateSummary;
};

export type AgentDirectPolicyReviewSummary = {
  status: string;
  sourceGate: {
    stage: string;
    status: string;
    localRecordValidated: boolean;
  };
  agentRules: {
    directPrintEnabled: boolean;
    directPrintDefault: string;
    approvalRequiredByDefault: boolean;
    longDirectPrintRequiresApproval: boolean;
    overLimitBehavior: string;
    noAutomaticRetryAfterPrintableBytes: boolean;
    rawBleWritesAllowed: boolean;
    unsafeResumeAllowed: boolean;
    requiresTrustedPrinter: boolean;
    requiresStableSupportGate: boolean;
  };
  limits: {
    maxHeightDots: number;
    warnTotalBlackCoverage: number;
    blockTotalBlackCoverage: number;
    blockBandCoverage: number;
    maxCopies: number;
    jobsPerMinute: number;
  };
  safety: {
    stableSupportClaimEnabled: boolean;
    longPrintPrintingEnabled: boolean;
    agentDirectPrintingEnabled: boolean;
    agentDirectPrintingDefault: string;
  };
  nextRequiredStage: string;
};

export type AgentDirectPolicyReviewInspectionResult = {
  recordPath: string;
  summary: AgentDirectPolicyReviewSummary;
};

export type HardwareHostReadiness = {
  status: string;
  platform: string;
  controllerVisible: boolean | null;
  canAttemptStageA: boolean;
  detail: string;
  recommendedActions: string[];
  checks: Array<{
    name: string;
    status: string;
    evidence: string;
  }>;
};

export type CommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number;
};

export type CommandRunner = (
  command: string,
  args: string[],
  options: { cwd: string },
) => Promise<CommandResult>;

export async function inspectHardwareArtifact({
  artifactPath,
  repoRoot,
  runner = runCommand,
}: {
  artifactPath: string;
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<HardwareArtifactInspectionResult> {
  const inspection =
    await runHardwareCliJson<HardwareArtifactInspectionSummary>({
      artifactPath,
      repoRoot,
      commandName: "inspect-artifact",
      runner,
    });
  const preflight =
    inspection.nextRequiredStage === "protocol_sanity_test"
      ? await runHardwareCliJson<HardwareProtocolPreflight>({
          artifactPath,
          repoRoot,
          commandName: "protocol-sanity-preflight",
          runner,
        })
      : null;
  const visualCardPreflight =
    inspection.nextRequiredStage === "protocol_sanity_test"
      ? await runHardwareCliJson<HardwareVisualCardPreflight>({
          artifactPath,
          repoRoot,
          commandName: "tiny-visual-card-preflight",
          runner,
        })
      : null;
  const evidenceSummary =
    inspection.nextRequiredStage === "protocol_sanity_test"
      ? await runHardwareCliJson<HardwareEvidenceSummary>({
          artifactPath,
          repoRoot,
          commandName: "evidence-summary",
          runner,
        })
      : null;

  return {
    artifactPath,
    inspection,
    preflight,
    visualCardPreflight,
    evidenceSummary,
  };
}

export async function inspectTrustedPrinterRecord({
  recordPath,
  repoRoot,
  runner = runCommand,
}: {
  recordPath: string;
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<TrustedPrinterRecordInspectionResult> {
  try {
    await runHardwareCli({
      artifactPath: recordPath,
      repoRoot,
      commandName: "inspect-trusted-printer-record",
      runner,
    });
    const decoded = JSON.parse(await readFile(recordPath, "utf-8")) as unknown;

    return {
      recordPath,
      summary: summarizeTrustedPrinterRecord(decoded),
    };
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("trusted-printer record is invalid JSON", {
        cause: error,
      });
    }
    throw error;
  }
}

export async function inspectStableSupportGate({
  recordPath,
  repoRoot,
  runner = runCommand,
}: {
  recordPath: string;
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<StableSupportGateInspectionResult> {
  try {
    await runHardwareCli({
      artifactPath: recordPath,
      repoRoot,
      commandName: "inspect-stable-support-gate",
      runner,
    });
    const decoded = JSON.parse(await readFile(recordPath, "utf-8")) as unknown;

    return {
      recordPath,
      summary: summarizeStableSupportGate(decoded),
    };
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("stable-support gate is invalid JSON", { cause: error });
    }
    throw error;
  }
}

export async function inspectAgentDirectPolicyReview({
  recordPath,
  repoRoot,
  runner = runCommand,
}: {
  recordPath: string;
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<AgentDirectPolicyReviewInspectionResult> {
  try {
    await runHardwareCli({
      artifactPath: recordPath,
      repoRoot,
      commandName: "inspect-agent-direct-policy-review",
      runner,
    });
    const decoded = JSON.parse(await readFile(recordPath, "utf-8")) as unknown;

    return {
      recordPath,
      summary: summarizeAgentDirectPolicyReview(decoded),
    };
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("agent-direct policy review is invalid JSON", {
        cause: error,
      });
    }
    throw error;
  }
}

function summarizeTrustedPrinterRecord(
  decoded: unknown,
): TrustedPrinterRecordSummary {
  const record = jsonObject(decoded, "trusted-printer record");
  if ("deviceId" in record || "rawDeviceId" in record) {
    throw new Error("trusted-printer record exposes raw device id");
  }
  const device = requiredJsonObject(record, "device", "trusted-printer record");
  const safety = requiredJsonObject(record, "safety", "trusted-printer record");
  const hardwareEvidence = requiredJsonObject(
    record,
    "hardwareEvidence",
    "trusted-printer record",
  );
  if ("deviceId" in device || "rawDeviceId" in device) {
    throw new Error("trusted-printer record exposes raw device id");
  }
  if (
    requiredJsonString(record, "status", "trusted-printer record") !==
    "trusted_for_manual_continuous_printing"
  ) {
    throw new Error("trusted-printer record has wrong status");
  }
  if (
    !requiredJsonBoolean(device, "idRedacted", "trusted-printer record.device")
  ) {
    throw new Error("trusted-printer record exposes raw device id");
  }
  const fingerprint = requiredJsonString(
    device,
    "fingerprint",
    "trusted-printer record.device",
  );
  if (!fingerprint.startsWith("sha256:")) {
    throw new Error("trusted-printer record has invalid device fingerprint");
  }
  const trustedFor = requiredJsonStringArray(
    record,
    "trustedFor",
    "trusted-printer record",
  );
  if (!trustedFor.includes("manual_continuous_printing")) {
    throw new Error("trusted-printer record does not trust manual printing");
  }
  const operatorNoteIncluded = requiredJsonBoolean(
    record,
    "operatorNoteIncluded",
    "trusted-printer record",
  );
  if (operatorNoteIncluded) {
    throw new Error("trusted-printer record includes operator free text");
  }
  if (
    !requiredJsonBoolean(
      safety,
      "manualContinuousPrintingEnabled",
      "trusted-printer record.safety",
    )
  ) {
    throw new Error("trusted-printer record does not enable manual printing");
  }
  if (
    !requiredJsonBoolean(
      safety,
      "longPrintReliabilityRequired",
      "trusted-printer record.safety",
    )
  ) {
    throw new Error("trusted-printer record skips long-print reliability");
  }
  for (const field of [
    "longPrintPrintingEnabled",
    "agentDirectPrintingEnabled",
    "stableSupportClaimEnabled",
  ]) {
    if (requiredJsonBoolean(safety, field, "trusted-printer record.safety")) {
      throw new Error("trusted-printer record unlocks later-stage support");
    }
  }
  const nextRequiredStage = requiredJsonString(
    record,
    "nextRequiredStage",
    "trusted-printer record",
  );
  if (nextRequiredStage !== "long_print_reliability") {
    throw new Error("trusted-printer record has wrong next stage");
  }

  return {
    status: "trusted_for_manual_continuous_printing",
    profileId: requiredJsonString(
      record,
      "profileId",
      "trusted-printer record",
    ),
    device: {
      idRedacted: true,
      fingerprint,
    },
    trustedFor,
    operatorNoteIncluded: false,
    hardwareEvidence: {
      stageA: summarizeTrustedEvidenceStage(hardwareEvidence, "stageA", {
        expectedStage: "read_only_verification",
      }),
      protocolSanity: summarizeTrustedEvidenceStage(
        hardwareEvidence,
        "protocolSanity",
        {
          expectedStage: "protocol_sanity_test",
        },
      ),
      tinyVisualCard: summarizeTrustedEvidenceStage(
        hardwareEvidence,
        "tinyVisualCard",
        {
          expectedStage: "tiny_visual_test_card",
        },
      ),
    },
    safety: {
      manualContinuousPrintingEnabled: true,
      longPrintReliabilityRequired: true,
      longPrintPrintingEnabled: false,
      agentDirectPrintingEnabled: false,
      stableSupportClaimEnabled: false,
    },
    nextRequiredStage,
  };
}

function summarizeStableSupportGate(
  decoded: unknown,
): StableSupportGateSummary {
  const record = jsonObject(decoded, "stable-support gate");
  if ("deviceId" in record || "rawDeviceId" in record) {
    throw new Error("stable-support gate exposes raw device id");
  }
  const device = requiredJsonObject(record, "device", "stable-support gate");
  const safety = requiredJsonObject(record, "safety", "stable-support gate");
  const hardwareEvidence = requiredJsonObject(
    record,
    "hardwareEvidence",
    "stable-support gate",
  );
  if ("deviceId" in device || "rawDeviceId" in device) {
    throw new Error("stable-support gate exposes raw device id");
  }
  if (
    requiredJsonString(record, "status", "stable-support gate") !==
    "stable_support_claims_enabled"
  ) {
    throw new Error("stable-support gate has wrong status");
  }
  if (
    !requiredJsonBoolean(device, "idRedacted", "stable-support gate.device")
  ) {
    throw new Error("stable-support gate exposes raw device id");
  }
  const fingerprint = requiredJsonString(
    device,
    "fingerprint",
    "stable-support gate.device",
  );
  if (!fingerprint.startsWith("sha256:")) {
    throw new Error("stable-support gate has invalid device fingerprint");
  }
  const trustedFor = requiredJsonStringArray(
    record,
    "trustedFor",
    "stable-support gate",
  );
  for (const trust of [
    "manual_continuous_printing",
    "long_print_continuous_printing",
    "stable_support_claims",
  ]) {
    if (!trustedFor.includes(trust)) {
      throw new Error("stable-support gate does not include required trust");
    }
  }
  if (
    requiredJsonBoolean(record, "operatorNoteIncluded", "stable-support gate")
  ) {
    throw new Error("stable-support gate includes operator free text");
  }
  if (
    requiredJsonBoolean(record, "rasterBytesIncluded", "stable-support gate")
  ) {
    throw new Error("stable-support gate includes raster bytes");
  }
  for (const field of [
    "manualContinuousPrintingEnabled",
    "longPrintReliabilityPassed",
    "longPrintPrintingEnabled",
    "stableSupportClaimEnabled",
  ]) {
    if (!requiredJsonBoolean(safety, field, "stable-support gate.safety")) {
      throw new Error("stable-support gate is missing enabled support");
    }
  }
  if (
    requiredJsonBoolean(
      safety,
      "agentDirectPrintingEnabled",
      "stable-support gate.safety",
    )
  ) {
    throw new Error("stable-support gate enables agent direct printing");
  }
  const agentDirectPrintingDefault = requiredJsonString(
    safety,
    "agentDirectPrintingDefault",
    "stable-support gate.safety",
  );
  if (agentDirectPrintingDefault !== "approval_required") {
    throw new Error("stable-support gate has wrong agent direct default");
  }
  const nextRequiredStage = requiredJsonString(
    record,
    "nextRequiredStage",
    "stable-support gate",
  );
  if (nextRequiredStage !== "agent_direct_printing_policy_review") {
    throw new Error("stable-support gate has wrong next stage");
  }

  return {
    status: "stable_support_claims_enabled",
    profileId: requiredJsonString(record, "profileId", "stable-support gate"),
    device: {
      idRedacted: true,
      fingerprint,
    },
    trustedFor,
    operatorNoteIncluded: false,
    rasterBytesIncluded: false,
    hardwareEvidence: {
      stageA: summarizeStableSupportGateEvidenceStage(
        hardwareEvidence,
        "stageA",
        {
          expectedStage: "read_only_verification",
        },
      ),
      protocolSanity: summarizeStableSupportGateEvidenceStage(
        hardwareEvidence,
        "protocolSanity",
        {
          expectedStage: "protocol_sanity_test",
        },
      ),
      tinyVisualCard: summarizeStableSupportGateEvidenceStage(
        hardwareEvidence,
        "tinyVisualCard",
        {
          expectedStage: "tiny_visual_test_card",
        },
      ),
      trustedPrinter: summarizeStableSupportGateEvidenceStage(
        hardwareEvidence,
        "trustedPrinter",
        {
          expectedStage: "trusted_printer_record",
        },
      ),
      longPrintReliability: summarizeStableSupportGateEvidenceStage(
        hardwareEvidence,
        "longPrintReliability",
        {
          expectedStage: "long_print_reliability",
        },
      ),
    },
    safety: {
      manualContinuousPrintingEnabled: true,
      longPrintReliabilityPassed: true,
      longPrintPrintingEnabled: true,
      stableSupportClaimEnabled: true,
      agentDirectPrintingEnabled: false,
      agentDirectPrintingDefault,
    },
    nextRequiredStage,
  };
}

function summarizeStableSupportGateEvidenceStage(
  hardwareEvidence: Record<string, unknown>,
  field: string,
  { expectedStage }: { expectedStage: string },
) {
  const evidence = requiredJsonObject(
    hardwareEvidence,
    field,
    "stable-support gate.hardwareEvidence",
  );
  const stage = requiredJsonString(
    evidence,
    "stage",
    `stable-support gate.hardwareEvidence.${field}`,
  );
  if (stage !== expectedStage) {
    throw new Error("stable-support gate evidence stage mismatch");
  }
  const artifactSha256 = requiredJsonString(
    evidence,
    "artifactSha256",
    `stable-support gate.hardwareEvidence.${field}`,
  );
  if (artifactSha256.length !== 64) {
    throw new Error("stable-support gate evidence digest is invalid");
  }
  return {
    stage,
    status: requiredJsonString(
      evidence,
      "status",
      `stable-support gate.hardwareEvidence.${field}`,
    ),
    artifactSha256Included: true,
  };
}

function summarizeAgentDirectPolicyReview(
  decoded: unknown,
): AgentDirectPolicyReviewSummary {
  const record = jsonObject(decoded, "agent-direct policy review");
  if (
    "deviceId" in record ||
    "rawDeviceId" in record ||
    "device" in record ||
    "profileId" in record ||
    "deviceFingerprint" in record ||
    "fingerprint" in record
  ) {
    throw new Error("agent-direct policy review exposes raw device id");
  }
  const sourceGate = requiredJsonObject(
    record,
    "sourceGate",
    "agent-direct policy review",
  );
  const agentRules = requiredJsonObject(
    record,
    "agentRules",
    "agent-direct policy review",
  );
  const limits = requiredJsonObject(
    record,
    "limits",
    "agent-direct policy review",
  );
  const safety = requiredJsonObject(
    record,
    "safety",
    "agent-direct policy review",
  );
  if (
    requiredJsonString(record, "status", "agent-direct policy review") !==
    "agent_direct_policy_reviewed"
  ) {
    throw new Error("agent-direct policy review has wrong status");
  }
  if (
    requiredJsonString(
      sourceGate,
      "stage",
      "agent-direct policy review.sourceGate",
    ) !== "stable_support_gate"
  ) {
    throw new Error("agent-direct policy review has wrong source gate");
  }
  if (
    requiredJsonString(
      sourceGate,
      "status",
      "agent-direct policy review.sourceGate",
    ) !== "stable_support_claims_enabled"
  ) {
    throw new Error("agent-direct policy review has wrong source status");
  }
  if (
    !requiredJsonBoolean(
      sourceGate,
      "localRecordValidated",
      "agent-direct policy review.sourceGate",
    )
  ) {
    throw new Error("agent-direct policy review source is not validated");
  }

  for (const field of [
    "approvalRequiredByDefault",
    "longDirectPrintRequiresApproval",
    "noAutomaticRetryAfterPrintableBytes",
    "requiresTrustedPrinter",
    "requiresStableSupportGate",
  ]) {
    if (
      !requiredJsonBoolean(
        agentRules,
        field,
        "agent-direct policy review.agentRules",
      )
    ) {
      throw new Error("agent-direct policy review weakens approval policy");
    }
  }
  for (const field of [
    "directPrintEnabled",
    "rawBleWritesAllowed",
    "unsafeResumeAllowed",
  ]) {
    if (
      requiredJsonBoolean(
        agentRules,
        field,
        "agent-direct policy review.agentRules",
      )
    ) {
      throw new Error(
        "agent-direct policy review enables unsafe direct printing",
      );
    }
  }
  const directPrintDefault = requiredJsonString(
    agentRules,
    "directPrintDefault",
    "agent-direct policy review.agentRules",
  );
  if (directPrintDefault !== "disabled") {
    throw new Error("agent-direct policy review has wrong direct default");
  }
  const overLimitBehavior = requiredJsonString(
    agentRules,
    "overLimitBehavior",
    "agent-direct policy review.agentRules",
  );
  if (overLimitBehavior !== "preview_and_ask") {
    throw new Error("agent-direct policy review has wrong over-limit behavior");
  }

  const expectedLimits = {
    maxHeightDots: 1000,
    warnTotalBlackCoverage: 0.3,
    blockTotalBlackCoverage: 0.45,
    blockBandCoverage: 0.7,
    maxCopies: 1,
    jobsPerMinute: 3,
  };
  for (const [field, expected] of Object.entries(expectedLimits)) {
    if (
      requiredJsonNumber(limits, field, "agent-direct policy review.limits") !==
      expected
    ) {
      throw new Error("agent-direct policy review has wrong safety limits");
    }
  }

  for (const field of [
    "stableSupportClaimEnabled",
    "longPrintPrintingEnabled",
  ]) {
    if (
      !requiredJsonBoolean(safety, field, "agent-direct policy review.safety")
    ) {
      throw new Error("agent-direct policy review lacks stable support");
    }
  }
  if (
    requiredJsonBoolean(
      safety,
      "agentDirectPrintingEnabled",
      "agent-direct policy review.safety",
    )
  ) {
    throw new Error("agent-direct policy review enables direct printing");
  }
  const agentDirectPrintingDefault = requiredJsonString(
    safety,
    "agentDirectPrintingDefault",
    "agent-direct policy review.safety",
  );
  if (agentDirectPrintingDefault !== "approval_required") {
    throw new Error("agent-direct policy review has wrong approval default");
  }
  const nextRequiredStage = requiredJsonString(
    record,
    "nextRequiredStage",
    "agent-direct policy review",
  );
  if (nextRequiredStage !== "explicit_user_opt_in_for_agent_direct_printing") {
    throw new Error("agent-direct policy review has wrong next stage");
  }

  return {
    status: "agent_direct_policy_reviewed",
    sourceGate: {
      stage: "stable_support_gate",
      status: "stable_support_claims_enabled",
      localRecordValidated: true,
    },
    agentRules: {
      directPrintEnabled: false,
      directPrintDefault,
      approvalRequiredByDefault: true,
      longDirectPrintRequiresApproval: true,
      overLimitBehavior,
      noAutomaticRetryAfterPrintableBytes: true,
      rawBleWritesAllowed: false,
      unsafeResumeAllowed: false,
      requiresTrustedPrinter: true,
      requiresStableSupportGate: true,
    },
    limits: expectedLimits,
    safety: {
      stableSupportClaimEnabled: true,
      longPrintPrintingEnabled: true,
      agentDirectPrintingEnabled: false,
      agentDirectPrintingDefault,
    },
    nextRequiredStage,
  };
}

function summarizeTrustedEvidenceStage(
  hardwareEvidence: Record<string, unknown>,
  field: string,
  { expectedStage }: { expectedStage: string },
) {
  const evidence = requiredJsonObject(
    hardwareEvidence,
    field,
    "trusted-printer record.hardwareEvidence",
  );
  const stage = requiredJsonString(
    evidence,
    "stage",
    `trusted-printer record.hardwareEvidence.${field}`,
  );
  if (stage !== expectedStage) {
    throw new Error("trusted-printer record evidence stage mismatch");
  }
  const artifactSha256 = requiredJsonString(
    evidence,
    "artifactSha256",
    `trusted-printer record.hardwareEvidence.${field}`,
  );
  if (artifactSha256.length !== 64) {
    throw new Error("trusted-printer record evidence digest is invalid");
  }
  return {
    stage,
    status: requiredJsonString(
      evidence,
      "status",
      `trusted-printer record.hardwareEvidence.${field}`,
    ),
    artifactSha256Included: true,
  };
}

function jsonObject(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} is not a JSON object`);
  }
  return value as Record<string, unknown>;
}

function requiredJsonObject(
  parent: Record<string, unknown>,
  field: string,
  label: string,
): Record<string, unknown> {
  return jsonObject(parent[field], `${label}.${field}`);
}

function requiredJsonString(
  parent: Record<string, unknown>,
  field: string,
  label: string,
) {
  const value = parent[field];
  if (typeof value !== "string" || !value) {
    throw new Error(`${label}.${field} is missing`);
  }
  return value;
}

function requiredJsonBoolean(
  parent: Record<string, unknown>,
  field: string,
  label: string,
) {
  const value = parent[field];
  if (typeof value !== "boolean") {
    throw new Error(`${label}.${field} is missing`);
  }
  return value;
}

function requiredJsonNumber(
  parent: Record<string, unknown>,
  field: string,
  label: string,
) {
  const value = parent[field];
  if (typeof value !== "number") {
    throw new Error(`${label}.${field} is missing`);
  }
  return value;
}

function requiredJsonStringArray(
  parent: Record<string, unknown>,
  field: string,
  label: string,
) {
  const value = parent[field];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`${label}.${field} is missing`);
  }
  return value as string[];
}

export async function checkHostBluetoothReadiness({
  repoRoot,
  runner = runCommand,
}: {
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<HardwareHostReadiness> {
  return runHardwareCliJson<HardwareHostReadiness>({
    repoRoot,
    commandName: "host-readiness",
    runner,
  });
}

async function runHardwareCliJson<T>({
  artifactPath,
  repoRoot,
  commandName,
  runner,
}: {
  artifactPath?: string;
  repoRoot: string;
  commandName:
    | "host-readiness"
    | "inspect-artifact"
    | "inspect-trusted-printer-record"
    | "inspect-stable-support-gate"
    | "inspect-agent-direct-policy-review"
    | "protocol-sanity-preflight"
    | "tiny-visual-card-preflight"
    | "evidence-summary";
  runner: CommandRunner;
}): Promise<T> {
  const result = await runHardwareCli({
    ...(artifactPath ? { artifactPath } : {}),
    repoRoot,
    commandName,
    runner,
  });

  try {
    return JSON.parse(result.stdout) as T;
  } catch (error) {
    throw new Error(`${commandName} returned invalid JSON`, { cause: error });
  }
}

async function runHardwareCli({
  artifactPath,
  repoRoot,
  commandName,
  extraArgs = [],
  runner,
}: {
  artifactPath?: string;
  repoRoot: string;
  commandName:
    | "host-readiness"
    | "inspect-artifact"
    | "inspect-trusted-printer-record"
    | "inspect-stable-support-gate"
    | "inspect-agent-direct-policy-review"
    | "protocol-sanity-preflight"
    | "tiny-visual-card-preflight"
    | "evidence-summary";
  extraArgs?: string[];
  runner: CommandRunner;
}): Promise<CommandResult> {
  const result = await runner(
    path.join(repoRoot, ".venv", "bin", "python"),
    [
      "-m",
      "minixd.hardware_test_cli",
      commandName,
      ...(artifactPath ? [artifactPath] : []),
      ...extraArgs,
    ],
    { cwd: repoRoot },
  );

  if (result.exitCode !== 0) {
    throw new Error(result.stderr.trim() || `${commandName} failed`);
  }

  return result;
}

function runCommand(
  command: string,
  args: string[],
  options: { cwd: string },
): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";

    child.stdout.setEncoding("utf-8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.setEncoding("utf-8");
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.once("error", reject);
    child.once("close", (exitCode) => {
      resolve({ stdout, stderr, exitCode: exitCode ?? 1 });
    });
  });
}
