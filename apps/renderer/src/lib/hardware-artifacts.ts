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
  hardwareEvidence: TrustedPrinterRecordSummary["hardwareEvidence"] & {
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

export type HardwareArtifactInspector = {
  inspect: () => Promise<HardwareArtifactInspectionResult | null>;
};

export type TrustedPrinterRecordInspector = {
  inspect: () => Promise<TrustedPrinterRecordInspectionResult | null>;
};

export type StableSupportGateInspector = {
  inspect: () => Promise<StableSupportGateInspectionResult | null>;
};

export type HardwareReadinessProvider = {
  check: () => Promise<HardwareHostReadiness>;
};

export const desktopHardwareArtifactInspector: HardwareArtifactInspector = {
  async inspect() {
    const inspectHardwareArtifact = window.minix?.inspectHardwareArtifact;
    if (!inspectHardwareArtifact) {
      throw new Error("Hardware artifact inspection is unavailable");
    }
    return inspectHardwareArtifact();
  },
};

export const desktopTrustedPrinterRecordInspector: TrustedPrinterRecordInspector =
  {
    async inspect() {
      const inspectTrustedPrinterRecord =
        window.minix?.inspectTrustedPrinterRecord;
      if (!inspectTrustedPrinterRecord) {
        throw new Error("Trusted-printer record inspection is unavailable");
      }
      return inspectTrustedPrinterRecord();
    },
  };

export const desktopStableSupportGateInspector: StableSupportGateInspector = {
  async inspect() {
    const inspectStableSupportGate = window.minix?.inspectStableSupportGate;
    if (!inspectStableSupportGate) {
      throw new Error("Stable-support gate inspection is unavailable");
    }
    return inspectStableSupportGate();
  },
};

export const desktopHardwareReadinessProvider: HardwareReadinessProvider = {
  async check() {
    const checkHostBluetoothReadiness =
      window.minix?.checkHostBluetoothReadiness;
    if (!checkHostBluetoothReadiness) {
      throw new Error("Host Bluetooth readiness check is unavailable");
    }
    return checkHostBluetoothReadiness();
  },
};
