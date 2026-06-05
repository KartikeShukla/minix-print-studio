import { spawn } from "node:child_process";
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

export type HardwareArtifactInspectionResult = {
  artifactPath: string;
  inspection: HardwareArtifactInspectionSummary;
  preflight: HardwareProtocolPreflight | null;
  visualCardPreflight: HardwareVisualCardPreflight | null;
};

export type CommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number;
};

export type CommandRunner = (
  command: string,
  args: string[],
  options: { cwd: string }
) => Promise<CommandResult>;

export async function inspectHardwareArtifact({
  artifactPath,
  repoRoot,
  runner = runCommand
}: {
  artifactPath: string;
  repoRoot: string;
  runner?: CommandRunner;
}): Promise<HardwareArtifactInspectionResult> {
  const inspection = await runHardwareCliJson<HardwareArtifactInspectionSummary>({
    artifactPath,
    repoRoot,
    commandName: "inspect-artifact",
    runner
  });
  const preflight =
    inspection.nextRequiredStage === "protocol_sanity_test"
      ? await runHardwareCliJson<HardwareProtocolPreflight>({
          artifactPath,
          repoRoot,
          commandName: "protocol-sanity-preflight",
          runner
        })
      : null;
  const visualCardPreflight =
    inspection.nextRequiredStage === "protocol_sanity_test"
      ? await runHardwareCliJson<HardwareVisualCardPreflight>({
          artifactPath,
          repoRoot,
          commandName: "tiny-visual-card-preflight",
          runner
        })
      : null;

  return {
    artifactPath,
    inspection,
    preflight,
    visualCardPreflight
  };
}

async function runHardwareCliJson<T>({
  artifactPath,
  repoRoot,
  commandName,
  runner
}: {
  artifactPath: string;
  repoRoot: string;
  commandName:
    | "inspect-artifact"
    | "protocol-sanity-preflight"
    | "tiny-visual-card-preflight";
  runner: CommandRunner;
}): Promise<T> {
  const result = await runner(
    path.join(repoRoot, ".venv", "bin", "python"),
    ["-m", "minixd.hardware_test_cli", commandName, artifactPath],
    { cwd: repoRoot }
  );

  if (result.exitCode !== 0) {
    throw new Error(result.stderr.trim() || `${commandName} failed`);
  }

  try {
    return JSON.parse(result.stdout) as T;
  } catch (error) {
    throw new Error(`${commandName} returned invalid JSON`, { cause: error });
  }
}

function runCommand(
  command: string,
  args: string[],
  options: { cwd: string }
): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      stdio: ["ignore", "pipe", "pipe"]
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
