export type PendingAgentPreviewApproval = {
  previewId: string;
  approvalUrl: string;
  receivedAt: string;
};

export type AgentPreviewApprovalProvider = {
  list: () => Promise<PendingAgentPreviewApproval[]>;
  remove: (previewId: string) => Promise<void>;
  subscribe?: (
    callback: (approvals: PendingAgentPreviewApproval[]) => void,
  ) => (() => void) | undefined;
};

export const desktopAgentPreviewApprovalProvider: AgentPreviewApprovalProvider =
  {
    async list() {
      const list = window.minix?.listAgentPreviewApprovals;
      if (!list) {
        return [];
      }
      return normalizePendingApprovals(await list());
    },
    async remove(previewId) {
      await window.minix?.removeAgentPreviewApproval?.(previewId);
    },
    subscribe(callback) {
      return window.minix?.onAgentPreviewApprovalsChanged?.((approvals) => {
        callback(normalizePendingApprovals(approvals));
      });
    },
  };

function normalizePendingApprovals(
  value: unknown,
): PendingAgentPreviewApproval[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isPendingApproval);
}

function isPendingApproval(
  value: unknown,
): value is PendingAgentPreviewApproval {
  if (!value || typeof value !== "object") {
    return false;
  }
  const approval = value as Record<string, unknown>;
  return (
    typeof approval.previewId === "string" &&
    approval.previewId.length > 0 &&
    typeof approval.approvalUrl === "string" &&
    approval.approvalUrl.length > 0 &&
    typeof approval.receivedAt === "string" &&
    approval.receivedAt.length > 0
  );
}
