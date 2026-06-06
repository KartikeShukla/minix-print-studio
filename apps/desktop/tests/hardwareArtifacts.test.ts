import { describe, expect, it } from "vitest";
import {
  checkHostBluetoothReadiness,
  inspectHardwareArtifact
} from "../src/main/hardwareArtifacts";

describe("hardware artifact inspection bridge", () => {
  it("runs the shared hardware-test CLI host readiness diagnostic", async () => {
    const calls: Array<{ command: string; args: string[]; cwd: string }> = [];

    const result = await checkHostBluetoothReadiness({
      repoRoot: "/repo/minix",
      runner: async (command, args, options) => {
        calls.push({ command, args, cwd: options.cwd });
        return {
          stdout: JSON.stringify({
            status: "not_visible",
            platform: "Darwin",
            controllerVisible: false,
            canAttemptStageA: false,
            detail: "macOS did not report a Bluetooth controller to this process.",
            recommendedActions: [
              "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
              "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed local session with Bluetooth access."
            ],
            checks: [
              {
                name: "system_profiler SPBluetoothDataType",
                status: "not_visible",
                evidence: "controllerInfo == nil"
              }
            ]
          }),
          stderr: "",
          exitCode: 0
        };
      }
    });

    expect(result).toEqual({
      status: "not_visible",
      platform: "Darwin",
      controllerVisible: false,
      canAttemptStageA: false,
      detail: "macOS did not report a Bluetooth controller to this process.",
      recommendedActions: [
        "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
        "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed local session with Bluetooth access."
      ],
      checks: [
        {
          name: "system_profiler SPBluetoothDataType",
          status: "not_visible",
          evidence: "controllerInfo == nil"
        }
      ]
    });
    expect(calls).toEqual([
      {
        command: "/repo/minix/.venv/bin/python",
        args: ["-m", "minixd.hardware_test_cli", "host-readiness"],
        cwd: "/repo/minix"
      }
    ]);
  });

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
        if (args.includes("protocol-sanity-preflight")) {
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
        if (args.includes("evidence-summary")) {
          return {
            stdout: JSON.stringify({
              status: "shareable_stage_a_evidence_ready",
              shareable: true,
              artifactStatus: "valid_stage_a_artifact",
              profileId: "seznik-minix-s1-lyin48d-gy",
              nextRequiredStage: "protocol_sanity_test",
              device: {
                idRedacted: true,
                fingerprint: "sha256:3d90f3ac7a07147e"
              },
              redaction: {
                artifactPathIncluded: false,
                localPathsIncluded: false,
                rawCommandLogIncluded: false,
                rawNotificationLogIncluded: false,
                commandPayloadHexIncluded: false,
                rasterBytesIncluded: false,
                bearerTokensIncluded: false
              },
              certification: {
                stageAReadOnlyVerified: true,
                printingLocked: true,
                certificationComplete: false,
                requiresStageBProtocolSanity: true,
                requiresTinyVisualCard: true,
                requiresLongPrintReliability: true
              },
              preflights: {
                protocolSanity: {
                  status: "protocol_sanity_preflight_ready",
                  stage: "protocol_sanity_test",
                  commandCount: 3,
                  sendsRaster: false,
                  unlocksPrinting: false
                },
                tinyVisualCard: {
                  status: "tiny_visual_card_preflight_ready",
                  stage: "tiny_visual_test_card",
                  displayText: "MINIX TEST 7K4P",
                  heightDots: 160,
                  rawBytesIncluded: false,
                  contentSha256:
                    "d1f0cdbf2eb7b70262fbe7825ac39e47847d3eaccc8737f4ff61a1970a9beb31"
                }
              }
            }),
            stderr: "",
            exitCode: 0
          };
        }
        return {
          stdout: JSON.stringify({
            status: "tiny_visual_card_preflight_ready",
            stage: "tiny_visual_test_card",
            deviceId: "mock-minix-0194",
            profileId: "seznik-minix-s1-lyin48d-gy",
            requiredPriorStage: "protocol_sanity_test",
            displayText: "MINIX TEST 7K4P",
            widthDots: 384,
            heightDots: 160,
            rowBytes: 48,
            density: "medium",
            paperMode: "continuous",
            printCommandsSent: false,
            rasterBytesIncluded: false,
            plannedRaster: {
              commandName: "raster_test_card",
              payloadBytes: 7688,
              rasterBytes: 7680,
              rawBytesIncluded: false,
              contentSha256:
                "d1f0cdbf2eb7b70262fbe7825ac39e47847d3eaccc8737f4ff61a1970a9beb31"
            },
            confirmationChecklist: [
              "Text MINIX TEST 7K4P is readable.",
              "Left and right edge markers are visible.",
              "Output is not mirrored or upside down.",
              "Feed is smooth with no stall, overheat warning, disconnect, or fatal error."
            ],
            safety: {
              requiresPhysicalPrinter: true,
              requiresUserConfirmation: true,
              requiresPriorProtocolSanity: true,
              sendsRasterIfExecuted: true,
              unlocksPrinting: false,
              preflightOnly: true
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
        }),
        evidenceSummary: expect.objectContaining({
          status: "shareable_stage_a_evidence_ready",
          shareable: true,
          device: {
            idRedacted: true,
            fingerprint: "sha256:3d90f3ac7a07147e"
          },
          redaction: expect.objectContaining({
            artifactPathIncluded: false,
            commandPayloadHexIncluded: false,
            rasterBytesIncluded: false
          })
        }),
        visualCardPreflight: expect.objectContaining({
          status: "tiny_visual_card_preflight_ready",
          displayText: "MINIX TEST 7K4P",
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
      },
      {
        command: "/repo/minix/.venv/bin/python",
        args: [
          "-m",
          "minixd.hardware_test_cli",
          "tiny-visual-card-preflight",
          "/tmp/hardware-test-stage-a.zip"
        ],
        cwd: "/repo/minix"
      },
      {
        command: "/repo/minix/.venv/bin/python",
        args: [
          "-m",
          "minixd.hardware_test_cli",
          "evidence-summary",
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
