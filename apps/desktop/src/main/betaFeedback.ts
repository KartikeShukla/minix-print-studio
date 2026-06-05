import path from "node:path";

export type BetaFeedbackDraft = {
  targetUrl: string;
  title: string;
  body: string;
  createdAt: string;
};

type BuildBetaFeedbackDraftOptions = {
  appVersion: string;
  platform?: NodeJS.Platform;
  now?: Date;
  supportBundlePath?: string | null;
  repositoryUrl?: string;
};

const DEFAULT_REPOSITORY_URL = "https://github.com/minix-print-studio/minix-print-studio";

export function buildBetaFeedbackDraft({
  appVersion,
  platform = process.platform,
  now = new Date(),
  supportBundlePath,
  repositoryUrl = DEFAULT_REPOSITORY_URL
}: BuildBetaFeedbackDraftOptions): BetaFeedbackDraft {
  const createdAt = now.toISOString();
  const title = `Beta feedback: MiniX Print Studio ${appVersion} on ${platform}`;
  const body = buildBody({
    appVersion,
    platform,
    createdAt,
    supportBundleFileName: supportBundlePath ? path.basename(supportBundlePath) : null
  });
  const targetUrl = new URL(`${repositoryUrl.replace(/\/$/, "")}/issues/new`);
  targetUrl.searchParams.set("template", "beta_feedback.yml");
  targetUrl.searchParams.set("title", title);
  targetUrl.searchParams.set("body", body);

  return {
    targetUrl: targetUrl.toString(),
    title,
    body,
    createdAt
  };
}

function buildBody({
  appVersion,
  platform,
  createdAt,
  supportBundleFileName
}: {
  appVersion: string;
  platform: NodeJS.Platform;
  createdAt: string;
  supportBundleFileName: string | null;
}): string {
  return [
    "## Environment",
    `- App version: ${appVersion}`,
    `- Platform: ${platform}`,
    `- Created: ${createdAt}`,
    `- Support bundle: ${supportBundleFileName ?? "Not attached"}`,
    "",
    "## Feedback",
    "",
    "## What worked",
    "",
    "## What blocked you",
    "",
    "## Safety and privacy",
    "- [ ] I reviewed attachments for tokens, private paths, raw raster bytes, and unredacted diagnostics.",
    ""
  ].join("\n");
}
