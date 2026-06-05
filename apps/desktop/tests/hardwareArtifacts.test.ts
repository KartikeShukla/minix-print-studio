import { describe, expect, it } from "vitest";
import { inspectHardwareArtifact } from "../src/main/hardwareArtifacts";

describe("hardware artifact inspection bridge", () => {
  it("runs the shared hardware-test CLI inspection and protocol preflight", async () => {
    const calls: Array<{ command: string; args: string[]; cwd: string }> = [];

    const result = await inspectHardwareArtifact({
      artifactPath: "/tmp/hardware-test-stage-a.zip",
      repoRoot: "/repo/minix",
      runner: async (command, args, options) => {
        calls.push({ command, args, cwd: options.cwd });
        if (args.includes("inspect-artifact")) {
          return {
            stdout: JSON.stringify({
              status: "valid_stage_a_artifact",
              deviceId: "mock-minix-0194",
              profileId: "seznik-minix-s1-lyin48d-gy",
              nextRequiredStage: "protocol_sanity_test"
            }),
            stderr: "",
            exitCode: 0
          };
        }
        return {
          stdout: JSON.stringify({
            status: "protocol_sanity_preflight_ready",
            stage: "protocol_sanity_test",
            deviceId: "mock-minix-0194",
            profileId: "seznik-minix-s1-lyin48d-gy",
            writeCharacteristic: "0000ff02-0000-1000-8000-00805f9b34fb",
            notifyCharacteristics: ["0000ff01-0000-1000-8000-00805f9b34fb"],
            density: "medium",
            paperMode: "continuous",
            printCommandsSent: false,
            rasterBytesIncluded: false,
            commands: [
              {
                index: 0,
                name: "wake",
                payloadBytes: 12,
                hex: "00 00 00 00 00 00 00 00 00 00 00 00"
              }
            ],
            safety: {
              requiresPhysicalPrinter: true,
              requiresUserConfirmation: true,
              sendsRaster: false,
              unlocksPrinting: false
            }
          }),
          stderr: "",
          exitCode: 0
        };
      }
    });

    expect(result).toEqual(
      expect.objectContaining({
        artifactPath: "/tmp/hardware-test-stage-a.zip",
        inspection: expect.objectContaining({
          status: "valid_stage_a_artifact",
          nextRequiredStage: "protocol_sanity_test"
        }),
        preflight: expect.objectContaining({
          status: "protocol_sanity_preflight_ready",
          printCommandsSent: false,
          rasterBytesIncluded: false
        })
      })
    );
    expect(calls).toEqual([
      {
        command: "/repo/minix/.venv/bin/python",
        args: [
          "-m",
          "minixd.hardware_test_cli",
          "inspect-artifact",
          "/tmp/hardware-test-stage-a.zip"
        ],
        cwd: "/repo/minix"
      },
      {
        command: "/repo/minix/.venv/bin/python",
        args: [
          "-m",
          "minixd.hardware_test_cli",
          "protocol-sanity-preflight",
          "/tmp/hardware-test-stage-a.zip"
        ],
        cwd: "/repo/minix"
      }
    ]);
  });

  it("surfaces unsafe artifact rejection from the shared CLI", async () => {
    await expect(
      inspectHardwareArtifact({
        artifactPath: "/tmp/unsafe.zip",
        repoRoot: "/repo/minix",
        runner: async () => ({
          stdout: "",
          stderr: "artifact is not read-only safe\n",
          exitCode: 2
        })
      })
    ).rejects.toThrow("artifact is not read-only safe");
  });
});
