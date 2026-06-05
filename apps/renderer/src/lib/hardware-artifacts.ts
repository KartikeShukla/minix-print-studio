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

export type HardwareArtifactInspectionResult = {
  artifactPath: string;
  inspection: HardwareArtifactInspectionSummary;
  preflight: HardwareProtocolPreflight | null;
};

export type HardwareArtifactInspector = {
  inspect: () => Promise<HardwareArtifactInspectionResult | null>;
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
