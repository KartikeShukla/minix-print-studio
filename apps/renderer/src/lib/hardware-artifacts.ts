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
  }
};

export const desktopHardwareReadinessProvider: HardwareReadinessProvider = {
  async check() {
    const checkHostBluetoothReadiness = window.minix?.checkHostBluetoothReadiness;
    if (!checkHostBluetoothReadiness) {
      throw new Error("Host Bluetooth readiness check is unavailable");
    }
    return checkHostBluetoothReadiness();
  }
};
