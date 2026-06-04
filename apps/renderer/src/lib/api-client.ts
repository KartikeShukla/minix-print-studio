import type { PrintDocument } from "@minix/design-model";
import type { AgentIntegrationPreview } from "@/lib/agent-integrations";
import {
  diagnosticsExportResponseSchema,
  documentPreviewResponseSchema,
  healthResponseSchema,
  printJobResponseSchema,
  printPlanResponseSchema,
  printerScanResponseSchema,
  readOnlyVerificationSchema,
  type DiagnosticsExportRequest,
  type DiagnosticsExportResponse,
  type DocumentPreviewResponse,
  type HealthResponse,
  type PrintJobResponse,
  type PrintPlanRequest,
  type PrintPlanResponse,
  type PrintPreviewRequest,
  type PrinterScanResponse,
  type ReadOnlyVerification,
  type RenderSettings
} from "@minix/shared-api";

export type DaemonRuntime = {
  baseUrl: string;
  token: string;
};

export type DaemonClient = {
  getHealth: () => Promise<HealthResponse>;
  createDocumentPreview: (
    document: PrintDocument,
    renderSettings: RenderSettings
  ) => Promise<DocumentPreviewResponse>;
  planApprovedPreview: (request: PrintPlanRequest) => Promise<PrintPlanResponse>;
  printApprovedPreview: (request: PrintPreviewRequest) => Promise<PrintJobResponse>;
  exportDiagnostics?: (request: DiagnosticsExportRequest) => Promise<DiagnosticsExportResponse>;
  scanPrinters: () => Promise<PrinterScanResponse>;
  readOnlyVerify: (deviceId: string) => Promise<ReadOnlyVerification>;
};

declare global {
  interface Window {
    minix?: {
      getDaemonRuntime: () => Promise<DaemonRuntime>;
      getAppVersion: () => Promise<string>;
      getAgentIntegrationPreview?: () => Promise<AgentIntegrationPreview>;
    };
  }
}

export function createDaemonClient(): DaemonClient {
  return {
    async getHealth() {
      return requestDaemon("/v1/health", {}, healthResponseSchema.parse, "Daemon health");
    },
    async createDocumentPreview(document, renderSettings) {
      return requestDaemon(
        "/v1/render/document-preview",
        {
          method: "POST",
          body: { document, renderSettings }
        },
        documentPreviewResponseSchema.parse,
        "Daemon document preview"
      );
    },
    async planApprovedPreview(request) {
      return requestDaemon(
        "/v1/jobs/plan",
        {
          method: "POST",
          body: request
        },
        printPlanResponseSchema.parse,
        "Daemon print plan"
      );
    },
    async printApprovedPreview(request) {
      return requestDaemon(
        "/v1/jobs/print",
        {
          method: "POST",
          body: request
        },
        printJobResponseSchema.parse,
        "Daemon print job"
      );
    },
    async exportDiagnostics(request) {
      return requestDaemon(
        "/v1/diagnostics/export",
        {
          method: "POST",
          body: request
        },
        diagnosticsExportResponseSchema.parse,
        "Daemon diagnostics export"
      );
    },
    async scanPrinters() {
      return requestDaemon(
        "/v1/printers/scan",
        {
          method: "POST"
        },
        printerScanResponseSchema.parse,
        "Daemon printer scan"
      );
    },
    async readOnlyVerify(deviceId) {
      return requestDaemon(
        "/v1/printers/read-only-verify",
        {
          method: "POST",
          body: { deviceId }
        },
        readOnlyVerificationSchema.parse,
        "Daemon read-only printer verification"
      );
    }
  };
}

async function requestDaemon<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: object },
  parse: (value: unknown) => T,
  label: string
): Promise<T> {
  const runtime = await getRuntime();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${runtime.token}`
  };
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers
  };

  if (options.body) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${runtime.baseUrl}${path}`, init);

  if (!response.ok) {
    throw new Error(`${label} failed with ${response.status}`);
  }

  return parse(await response.json());
}

async function getRuntime(): Promise<DaemonRuntime> {
  if (window.minix) {
    return window.minix.getDaemonRuntime();
  }

  return {
    baseUrl: "http://127.0.0.1:39281",
    token: "dev-token"
  };
}
