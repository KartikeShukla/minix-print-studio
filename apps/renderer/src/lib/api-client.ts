import type { PrintDocument } from "@minix/design-model";
import type {
  AgentIntegrationConnectionTestResult,
  AgentIntegrationExportResult,
  AgentIntegrationInstallResult,
  AgentIntegrationPreview,
  AgentIntegrationTargetId
} from "@/lib/agent-integrations";
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
  type HardwareTestExportRequest,
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
  exportHardwareTest?: (deviceId: string) => Promise<Blob>;
  scanPrinters: () => Promise<PrinterScanResponse>;
  readOnlyVerify: (deviceId: string) => Promise<ReadOnlyVerification>;
};

declare global {
  interface Window {
    minix?: {
      getDaemonRuntime: () => Promise<DaemonRuntime>;
      getAppVersion: () => Promise<string>;
      getAgentIntegrationPreview?: () => Promise<AgentIntegrationPreview>;
      installAgentIntegrationConfig?: (
        targetId: AgentIntegrationTargetId
      ) => Promise<AgentIntegrationInstallResult>;
      uninstallAgentIntegrationConfig?: (
        targetId: AgentIntegrationTargetId
      ) => Promise<AgentIntegrationInstallResult>;
      testAgentIntegrationConnection?: (
        targetId: AgentIntegrationTargetId
      ) => Promise<AgentIntegrationConnectionTestResult>;
      exportAgentIntegrationBundle?: (
        targetId: AgentIntegrationTargetId
      ) => Promise<AgentIntegrationExportResult>;
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
    async exportHardwareTest(deviceId) {
      const request: HardwareTestExportRequest = {
        deviceId,
        stage: "read_only_verification"
      };
      return requestDaemonBlob(
        "/v1/diagnostics/hardware-test",
        {
          method: "POST",
          body: request
        },
        "Daemon hardware-test export"
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

async function requestDaemonBlob(
  path: string,
  options: { method?: "GET" | "POST"; body?: object },
  label: string
): Promise<Blob> {
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

  return response.blob();
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
