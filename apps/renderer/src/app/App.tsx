import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bluetooth,
  Boxes,
  CircleAlert,
  FileSearch,
  FileText,
  Image,
  Layers3,
  MousePointer2,
  Printer,
  QrCode,
  ScanSearch,
  ShieldCheck,
  Square,
  Type,
  Wifi
} from "lucide-react";
import { createDefaultDocument } from "@minix/design-model";
import type {
  DocumentPreviewResponse,
  HealthResponse,
  PrintJobResponse,
  PrintPlanResponse,
  PrinterCandidate,
  ReadOnlyVerification,
  RenderSettings
} from "@minix/shared-api";
import { createDaemonClient, type DaemonClient } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type AppProps = {
  daemonClient?: DaemonClient;
};

const tools = [
  { label: "Select", icon: MousePointer2 },
  { label: "Text", icon: Type },
  { label: "Rectangle", icon: Square },
  { label: "Image", icon: Image },
  { label: "QR", icon: QrCode }
];

const layers = [
  { name: "Receipt artboard", detail: "384 x 900 dots", icon: FileText },
  { name: "Protected tail margin", detail: "160 blank rows", icon: ShieldCheck }
];

const DEFAULT_RENDER_SETTINGS = { threshold: 128, dither: "none" } satisfies RenderSettings;

type PreviewWorkflow =
  | { status: "idle" }
  | { status: "running" }
  | { status: "ready"; preview: DocumentPreviewResponse; plan: PrintPlanResponse }
  | { status: "error"; message: string };

type PrintWorkflow =
  | { status: "idle" }
  | { status: "running" }
  | { status: "completed"; job: PrintJobResponse }
  | { status: "error"; message: string };

type PrinterWorkflow =
  | { status: "idle" }
  | { status: "scanning" }
  | { status: "candidates"; candidates: PrinterCandidate[] }
  | { status: "verifying"; candidates: PrinterCandidate[]; deviceId: string }
  | { status: "verified"; candidates: PrinterCandidate[]; verification: ReadOnlyVerification }
  | { status: "error"; message: string };

export function App({ daemonClient }: AppProps) {
  const client = useMemo(() => daemonClient ?? createDaemonClient(), [daemonClient]);
  const [document] = useState(() => createDefaultDocument({ heightDots: 900 }));
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [previewWorkflow, setPreviewWorkflow] = useState<PreviewWorkflow>({ status: "idle" });
  const [printWorkflow, setPrintWorkflow] = useState<PrintWorkflow>({ status: "idle" });
  const [printerWorkflow, setPrinterWorkflow] = useState<PrinterWorkflow>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;

    client
      .getHealth()
      .then((response) => {
        if (!cancelled) {
          setHealth(response);
          setHealthError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHealth(null);
          setHealthError(error instanceof Error ? error.message : "Daemon unavailable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client]);

  const runPreview = useCallback(async () => {
    setPreviewWorkflow({ status: "running" });
    setPrintWorkflow({ status: "idle" });
    try {
      const preview = await client.createDocumentPreview(document, DEFAULT_RENDER_SETTINGS);
      const plan = await client.planApprovedPreview({
        jobId: "job_preview",
        previewId: preview.previewId,
        approvalToken: preview.approvalToken,
        documentHash: preview.documentHash,
        renderSettingsHash: preview.renderSettingsHash,
        profileId: document.target.profileId,
        paperMode: document.target.paperMode,
        density: document.target.density
      });
      setPreviewWorkflow({ status: "ready", preview, plan });
    } catch (error: unknown) {
      setPreviewWorkflow({
        status: "error",
        message: error instanceof Error ? error.message : "Preview failed"
      });
    }
  }, [client, document]);

  const runPrinterScan = useCallback(async () => {
    setPrinterWorkflow({ status: "scanning" });
    try {
      const response = await client.scanPrinters();
      setPrinterWorkflow({ status: "candidates", candidates: response.printers });
    } catch (error: unknown) {
      setPrinterWorkflow({
        status: "error",
        message: error instanceof Error ? error.message : "Printer scan failed"
      });
    }
  }, [client]);

  const runReadOnlyVerify = useCallback(
    async (deviceId: string, candidates: PrinterCandidate[]) => {
      setPrinterWorkflow({ status: "verifying", candidates, deviceId });
      try {
        const verification = await client.readOnlyVerify(deviceId);
        setPrinterWorkflow({ status: "verified", candidates, verification });
      } catch (error: unknown) {
        setPrinterWorkflow({
          status: "error",
          message: error instanceof Error ? error.message : "Read-only verification failed"
        });
      }
    },
    [client]
  );

  const runPrint = useCallback(async () => {
    if (previewWorkflow.status !== "ready") {
      return;
    }
    setPrintWorkflow({ status: "running" });
    try {
      const job = await client.printApprovedPreview({
        previewId: previewWorkflow.preview.previewId,
        approvalToken: previewWorkflow.preview.approvalToken,
        documentHash: previewWorkflow.preview.documentHash,
        renderSettingsHash: previewWorkflow.preview.renderSettingsHash,
        profileId: document.target.profileId,
        paperMode: document.target.paperMode,
        density: document.target.density,
        copies: 1,
        source: "ui"
      });
      setPrintWorkflow({ status: "completed", job });
    } catch (error: unknown) {
      setPrintWorkflow({
        status: "error",
        message: error instanceof Error ? error.message : "Print failed"
      });
    }
  }, [client, document, previewWorkflow]);

  const statusLabel = health
    ? health.mock
      ? "Mock daemon online"
      : "Daemon online"
    : healthError
      ? "Daemon offline"
      : "Checking daemon";
  const previewReady = previewWorkflow.status === "ready";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="grid h-screen grid-rows-[56px_minmax(0,1fr)_32px] overflow-hidden">
        <header className="flex items-center justify-between border-b border-border bg-card px-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Printer className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold">MiniX Print Studio</h1>
              <p className="truncate text-xs text-muted-foreground">
                Untitled print - continuous paper
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant={health ? "success" : healthError ? "destructive" : "muted"}>
              <Wifi className="size-3.5" aria-hidden="true" />
              {statusLabel}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={runPrinterScan}
              disabled={printerWorkflow.status === "scanning"}
            >
              <ScanSearch className="size-4" aria-hidden="true" />
              {printerWorkflow.status === "scanning" ? "Scanning" : "Scan printers"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={runPreview}
              disabled={previewWorkflow.status === "running"}
            >
              <FileSearch className="size-4" aria-hidden="true" />
              Preview
            </Button>
            <Button
              size="sm"
              disabled={!previewReady || printWorkflow.status === "running"}
              onClick={runPrint}
            >
              <Printer className="size-4" aria-hidden="true" />
              Print
            </Button>
          </div>
        </header>

        <main className="grid min-h-0 grid-cols-[248px_minmax(420px,1fr)_320px]">
          <aside className="min-h-0 border-r border-border bg-muted/30">
            <section className="border-b border-border p-3">
              <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">Tools</div>
              <div className="grid grid-cols-5 gap-1">
                {tools.map((tool) => {
                  const Icon = tool.icon;
                  return (
                    <Button
                      key={tool.label}
                      variant={tool.label === "Select" ? "secondary" : "ghost"}
                      size="icon"
                      title={tool.label}
                      aria-label={tool.label}
                    >
                      <Icon className="size-4" aria-hidden="true" />
                    </Button>
                  );
                })}
              </div>
            </section>

            <section className="p-3">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-xs font-medium uppercase text-muted-foreground">Layers</div>
                <Layers3 className="size-4 text-muted-foreground" aria-hidden="true" />
              </div>
              <div className="space-y-2">
                {layers.map((layer) => {
                  const Icon = layer.icon;
                  return (
                    <div
                      key={layer.name}
                      className="rounded-md border border-border bg-card p-2 text-sm"
                    >
                      <div className="flex items-center gap-2 font-medium">
                        <Icon className="size-4 text-primary" aria-hidden="true" />
                        {layer.name}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{layer.detail}</div>
                    </div>
                  );
                })}
              </div>
            </section>
          </aside>

          <section className="min-h-0 overflow-auto bg-workspace p-6">
            <div className="mx-auto flex min-h-full w-full max-w-4xl items-start justify-center">
              <div className="receipt-artboard" aria-label="384 dot receipt artboard">
                <div className="border-b border-dashed border-safety/60 pb-3 text-center text-xs text-muted-foreground">
                  384 dots
                </div>
                <div className="flex flex-1 items-center justify-center text-center">
                  <div>
                    <Boxes
                      className="mx-auto mb-3 size-9 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <div className="text-sm font-medium">Canvas editor bootstrap</div>
                    <div className="mt-1 max-w-56 text-xs text-muted-foreground">
                      {previewReady
                        ? `${previewWorkflow.plan.totalBands} print bands planned from approved preview.`
                        : "Document model and canonical preview contracts are ready for the editor slice."}
                    </div>
                  </div>
                </div>
                <div className="border-t border-dashed border-safety/60 pt-3 text-center text-xs text-safety">
                  Protected tail margin
                </div>
              </div>
            </div>
          </section>

          <aside className="min-h-0 border-l border-border bg-card">
            <PrinterPanel workflow={printerWorkflow} onVerify={runReadOnlyVerify} />

            <section className="border-b border-border p-4">
              <div className="mb-3 flex items-center gap-2">
                <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Safety</h2>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Coverage</span>
                  <span>{previewReady ? formatCoverage(previewWorkflow.preview) : "0%"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Agent direct print</span>
                  <span>Off</span>
                </div>
              </div>
            </section>

            <section className="p-4">
              <div className="mb-3 flex items-center gap-2">
                <CircleAlert
                  className={`size-4 ${previewReady ? "text-success" : "text-warning"}`}
                  aria-hidden="true"
                />
                <h2 className="text-sm font-semibold">Preview Binding</h2>
              </div>
              {previewWorkflow.status === "ready" ? (
                <div>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Status</span>
                      <Badge variant="success">Preview ready</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Preview</span>
                      <span>{previewWorkflow.preview.previewId}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Plan</span>
                      <span>{formatBandCount(previewWorkflow.plan.totalBands)}</span>
                    </div>
                  </div>
                  <PrintStatus workflow={printWorkflow} />
                </div>
              ) : previewWorkflow.status === "running" ? (
                <p className="text-sm leading-6 text-muted-foreground">
                  Requesting daemon preview and print plan.
                </p>
              ) : previewWorkflow.status === "error" ? (
                <p className="text-sm leading-6 text-destructive">{previewWorkflow.message}</p>
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">
                  Printing will require a daemon-generated preview hash before physical output.
                </p>
              )}
            </section>
          </aside>
        </main>

        <footer className="flex items-center justify-between border-t border-border bg-card px-4 text-xs text-muted-foreground">
          <span>Zoom 100%</span>
          <span>{health ? `Daemon ${health.version}` : "No daemon health yet"}</span>
          <span>{formatQueueStatus(previewReady, printWorkflow)}</span>
        </footer>
      </div>
    </div>
  );
}

function PrinterPanel({
  workflow,
  onVerify
}: {
  workflow: PrinterWorkflow;
  onVerify: (deviceId: string, candidates: PrinterCandidate[]) => void;
}) {
  const candidates = "candidates" in workflow ? workflow.candidates : [];
  const primaryCandidate = candidates[0];
  const verification = workflow.status === "verified" ? workflow.verification : null;

  return (
    <section className="border-b border-border p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Printer</h2>
        <Badge variant={verification ? "warning" : "muted"}>
          <Bluetooth className="size-3.5" aria-hidden="true" />
          {verification ? "Read-only verified" : "Untrusted"}
        </Badge>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Profile</span>
          <span>Seznik MiniX S1</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Paper</span>
          <span>Continuous</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Width</span>
          <span>384 dots</span>
        </div>
      </div>

      <PrinterDiscoveryStatus
        workflow={workflow}
        candidate={primaryCandidate}
        verification={verification}
        onVerify={() => {
          if (primaryCandidate) {
            onVerify(primaryCandidate.deviceId, candidates);
          }
        }}
      />
    </section>
  );
}

function PrinterDiscoveryStatus({
  workflow,
  candidate,
  verification,
  onVerify
}: {
  workflow: PrinterWorkflow;
  candidate: PrinterCandidate | undefined;
  verification: ReadOnlyVerification | null;
  onVerify: () => void;
}) {
  if (workflow.status === "scanning") {
    return <div className="mt-4 text-sm text-muted-foreground">Scanning</div>;
  }

  if (workflow.status === "error") {
    return <div className="mt-4 text-sm text-destructive">{workflow.message}</div>;
  }

  if (!candidate) {
    return null;
  }

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="min-w-0 truncate font-medium">{candidate.name ?? candidate.deviceId}</span>
        <Badge variant="warning">{formatSupportLevel(candidate.supportLevel)}</Badge>
      </div>
      <div className="space-y-2">
        <div className="flex justify-between gap-3">
          <span className="text-muted-foreground">Stage</span>
          <span className="text-right">{formatDiscoveryStage(candidate.nextRequiredStage)}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-muted-foreground">RSSI</span>
          <span>{candidate.rssi ?? "Unknown"}</span>
        </div>
      </div>
      {workflow.status === "verifying" ? (
        <div className="text-muted-foreground">Verifying printer identity</div>
      ) : verification ? (
        <div className="space-y-2 border-t border-border pt-3">
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Model</span>
            <span>{verification.modelResponse ?? "Unknown"}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Firmware</span>
            <span>{verification.firmware ?? "Unknown"}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Next</span>
            <span className="text-right">
              {formatDiscoveryStage(verification.nextRequiredStage)}
            </span>
          </div>
          <Badge variant="warning">Printing still locked</Badge>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onVerify}
          disabled={candidate.nextRequiredStage !== "read_only_verification"}
        >
          <ShieldCheck className="size-4" aria-hidden="true" />
          Verify printer identity
        </Button>
      )}
    </div>
  );
}

function PrintStatus({ workflow }: { workflow: PrintWorkflow }) {
  if (workflow.status === "running") {
    return (
      <div className="mt-4 border-t border-border pt-4 text-sm text-muted-foreground">
        Sending approved preview to mock queue.
      </div>
    );
  }

  if (workflow.status === "error") {
    return (
      <div className="mt-4 border-t border-border pt-4 text-sm text-destructive">
        {workflow.message}
      </div>
    );
  }

  if (workflow.status !== "completed") {
    return null;
  }

  return (
    <div className="mt-4 space-y-2 border-t border-border pt-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium">Job Status</span>
        <Badge variant={workflow.job.requiresUserCheck ? "warning" : "success"}>
          {workflow.job.state}
        </Badge>
      </div>
      {workflow.job.requiresUserCheck ? (
        <div className="text-warning">User check required</div>
      ) : null}
      <div className="flex justify-between">
        <span className="text-muted-foreground">Progress</span>
        <span>
          {workflow.job.bandsSent}/{workflow.job.totalBands} bands
        </span>
      </div>
      <div className="flex flex-wrap gap-2 pt-1">
        {workflow.job.safeActions.map((action) => (
          <Badge key={action} variant="muted">
            {formatSafeAction(action)}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function formatBandCount(totalBands: number): string {
  return `${totalBands} ${totalBands === 1 ? "band" : "bands"}`;
}

function formatSupportLevel(level: string): string {
  const labels: Record<string, string> = {
    detected_unverified: "Detected",
    official: "Official",
    community_verified: "Community verified",
    experimental: "Experimental",
    unsupported: "Unsupported"
  };
  return labels[level] ?? level;
}

function formatDiscoveryStage(stage: string): string {
  const labels: Record<string, string> = {
    read_only_verification: "Read-only verification required",
    protocol_sanity_test: "Protocol sanity test required",
    supported_printer_test: "Supported-printer test required",
    unsupported: "Unsupported"
  };
  return labels[stage] ?? stage;
}

function formatCoverage(preview: DocumentPreviewResponse): string {
  const value = preview.safety.metrics?.totalBlackCoverage;
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "0%";
}

function formatQueueStatus(previewReady: boolean, workflow: PrintWorkflow): string {
  if (workflow.status === "completed") {
    return workflow.job.requiresUserCheck ? "Job completed, check paper" : "Job complete";
  }
  if (workflow.status === "running") {
    return "Print in progress";
  }
  return previewReady ? "Preview approved for planning" : "Queue idle";
}

function formatSafeAction(action: string): string {
  const labels: Record<string, string> = {
    confirm_complete: "Confirm complete",
    feed_paper: "Feed paper",
    reprint_from_start: "Reprint from start"
  };
  return labels[action] ?? action;
}
