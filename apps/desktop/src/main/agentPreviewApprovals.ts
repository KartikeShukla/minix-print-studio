export type PendingAgentPreviewApproval = {
  previewId: string;
  approvalUrl: string;
  receivedAt: string;
};

export type AgentPreviewApprovalQueueOptions = {
  now?: () => Date;
};

export function parseAgentPreviewApprovalUrl(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }

  if (url.protocol !== "minixprint:") {
    return null;
  }
  if (url.hostname !== "approval") {
    return null;
  }

  let previewId: string;
  try {
    previewId = decodeURIComponent(url.pathname.replace(/^\/+/, "")).trim();
  } catch {
    return null;
  }
  return previewId.length > 0 ? previewId : null;
}

export class AgentPreviewApprovalQueue {
  private readonly now: () => Date;
  private readonly approvals = new Map<string, PendingAgentPreviewApproval>();

  constructor(options: AgentPreviewApprovalQueueOptions = {}) {
    this.now = options.now ?? (() => new Date());
  }

  enqueueUrl(url: string): PendingAgentPreviewApproval | null {
    const previewId = parseAgentPreviewApprovalUrl(url);
    if (!previewId) {
      return null;
    }

    const approval: PendingAgentPreviewApproval = {
      previewId,
      approvalUrl: `minixprint://approval/${encodeURIComponent(previewId)}`,
      receivedAt: this.now().toISOString(),
    };
    this.approvals.delete(previewId);
    this.approvals.set(previewId, approval);
    return approval;
  }

  list(): PendingAgentPreviewApproval[] {
    return Array.from(this.approvals.values()).reverse();
  }

  remove(previewId: string): void {
    this.approvals.delete(previewId);
  }
}
