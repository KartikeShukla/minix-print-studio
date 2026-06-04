import type { PrintDocument } from "@minix/design-model";
import {
  documentPreviewResponseSchema,
  healthResponseSchema,
  printPlanResponseSchema,
  type DocumentPreviewResponse,
  type HealthResponse,
  type PrintPlanRequest,
  type PrintPlanResponse,
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
};

declare global {
  interface Window {
    minix?: {
      getDaemonRuntime: () => Promise<DaemonRuntime>;
      getAppVersion: () => Promise<string>;
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
