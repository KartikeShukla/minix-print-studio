export type SupportBundleExportResult = {
  targetPath: string;
  createdAt: string;
  entries: string[];
};

export type BetaFeedbackDraft = {
  targetUrl: string;
  title: string;
  body: string;
  createdAt: string;
};

export type BetaFeedbackDraftRequest = {
  supportBundlePath?: string;
};

export type SupportBundleExporter = {
  exportBundle: () => Promise<SupportBundleExportResult>;
  createFeedbackDraft?: (request?: BetaFeedbackDraftRequest) => Promise<BetaFeedbackDraft>;
};

export const desktopSupportBundleExporter: SupportBundleExporter = {
  async exportBundle() {
    const exportSupportBundle = window.minix?.exportSupportBundle;
    if (!exportSupportBundle) {
      throw new Error("Support bundle export is unavailable");
    }
    return exportSupportBundle();
  },
  async createFeedbackDraft(request) {
    const createBetaFeedbackDraft = window.minix?.createBetaFeedbackDraft;
    if (!createBetaFeedbackDraft) {
      throw new Error("Beta feedback draft is unavailable");
    }
    return createBetaFeedbackDraft(request);
  }
};
