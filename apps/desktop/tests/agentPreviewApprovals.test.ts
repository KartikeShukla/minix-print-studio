import { describe, expect, it } from "vitest";
import {
  AgentPreviewApprovalQueue,
  parseAgentPreviewApprovalUrl,
} from "../src/main/agentPreviewApprovals";

describe("agent preview approval deep links", () => {
  it("parses minixprint approval URLs and rejects unrelated inputs", () => {
    expect(
      parseAgentPreviewApprovalUrl("minixprint://approval/prev_agent"),
    ).toBe("prev_agent");
    expect(
      parseAgentPreviewApprovalUrl("minixprint://approval/prev_agent%2Fone"),
    ).toBe("prev_agent/one");

    expect(parseAgentPreviewApprovalUrl("prev_agent")).toBeNull();
    expect(
      parseAgentPreviewApprovalUrl("https://approval/prev_agent"),
    ).toBeNull();
    expect(
      parseAgentPreviewApprovalUrl("minixprint://print/prev_agent"),
    ).toBeNull();
    expect(parseAgentPreviewApprovalUrl("minixprint://approval/")).toBeNull();
    expect(
      parseAgentPreviewApprovalUrl("minixprint://approval/%E0%A4%A"),
    ).toBeNull();
  });

  it("queues unique pending approvals in newest-first order", () => {
    const queue = new AgentPreviewApprovalQueue({
      now: () => new Date("2026-06-11T10:00:00.000Z"),
    });

    expect(queue.enqueueUrl("https://approval/prev_agent")).toBeNull();
    expect(queue.enqueueUrl("minixprint://approval/prev_old")).toEqual({
      previewId: "prev_old",
      approvalUrl: "minixprint://approval/prev_old",
      receivedAt: "2026-06-11T10:00:00.000Z",
    });
    expect(queue.enqueueUrl("minixprint://approval/prev_new")).toEqual({
      previewId: "prev_new",
      approvalUrl: "minixprint://approval/prev_new",
      receivedAt: "2026-06-11T10:00:00.000Z",
    });
    queue.enqueueUrl("minixprint://approval/prev_old");

    expect(queue.list()).toEqual([
      {
        previewId: "prev_old",
        approvalUrl: "minixprint://approval/prev_old",
        receivedAt: "2026-06-11T10:00:00.000Z",
      },
      {
        previewId: "prev_new",
        approvalUrl: "minixprint://approval/prev_new",
        receivedAt: "2026-06-11T10:00:00.000Z",
      },
    ]);

    queue.remove("prev_old");

    expect(queue.list()).toEqual([
      {
        previewId: "prev_new",
        approvalUrl: "minixprint://approval/prev_new",
        receivedAt: "2026-06-11T10:00:00.000Z",
      },
    ]);
  });
});
