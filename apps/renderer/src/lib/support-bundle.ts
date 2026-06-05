export type SupportBundleExportResult = {
  targetPath: string;
  createdAt: string;
  entries: string[];
};

export type SupportBundleExporter = {
  exportBundle: () => Promise<SupportBundleExportResult>;
};

export const desktopSupportBundleExporter: SupportBundleExporter = {
  async exportBundle() {
    const exportSupportBundle = window.minix?.exportSupportBundle;
    if (!exportSupportBundle) {
      throw new Error("Support bundle export is unavailable");
    }
    return exportSupportBundle();
  },
};
