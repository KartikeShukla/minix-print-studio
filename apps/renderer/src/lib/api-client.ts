import type { PrintDocument } from "@minix/design-model";
import type {
  AgentIntegrationConnectionTestResult,
  AgentIntegrationExportResult,
  AgentIntegrationInstallResult,
  AgentIntegrationPreview,
  AgentIntegrationTargetId,
} from "@/lib/agent-integrations";
import type { PendingAgentPreviewApproval } from "@/lib/agent-preview-approvals";
import type {
  AgentDirectPolicyReviewInspectionResult,
  AgentDirectUserOptInInspectionResult,
  HardwareArtifactInspectionResult,
  HardwareHostReadiness,
  StableSupportGateInspectionResult,
  TrustedPrinterRecordInspectionResult,
} from "@/lib/hardware-artifacts";
import type {
  BetaFeedbackDraft,
  BetaFeedbackDraftRequest,
  SupportBundleExportResult,
} from "@/lib/support-bundle";
import type { UpdateChannel, UpdateChannelState } from "@/lib/update-channel";
import {
  diagnosticsExportResponseSchema,
  documentPreviewResponseSchema,
  healthResponseSchema,
  projectAssetResponseSchema,
  projectListResponseSchema,
  projectResponseSchema,
  printJobResponseSchema,
  printPlanResponseSchema,
  printerScanResponseSchema,
  readOnlyVerificationSchema,
  storedPreviewMetadataResponseSchema,
  type DiagnosticsExportRequest,
  type DiagnosticsExportResponse,
  type DocumentPreviewResponse,
  type HardwareTestExportRequest,
  type HealthResponse,
  type OperatorConfirmationRequest,
  type ProjectAssetResponse,
  type ProjectAssetUploadRequest,
  type ProjectListResponse,
  type ProjectResponse,
  type PrintJobResponse,
  type PrintPlanRequest,
  type PrintPlanResponse,
  type PrintPreviewRequest,
  type PrintStoredPreviewRequest,
  type PrinterScanResponse,
  type ReadOnlyVerification,
  type RenderSettings,
  type StoredPreviewMetadataResponse,
} from "@minix/shared-api";

export type DaemonRuntime = {
  baseUrl: string;
  token: string;
};

export type DaemonClient = {
  getHealth: () => Promise<HealthResponse>;
  createDocumentPreview: (
    document: PrintDocument,
    renderSettings: RenderSettings,
  ) => Promise<DocumentPreviewResponse>;
  getStoredPreview: (
    previewId: string,
  ) => Promise<StoredPreviewMetadataResponse>;
  planApprovedPreview: (
    request: PrintPlanRequest,
  ) => Promise<PrintPlanResponse>;
  printApprovedPreview: (
    request: PrintPreviewRequest,
  ) => Promise<PrintJobResponse>;
  printStoredPreview: (
    request: PrintStoredPreviewRequest,
  ) => Promise<PrintJobResponse>;
  confirmJobOutput: (
    jobId: string,
    request: OperatorConfirmationRequest,
  ) => Promise<PrintJobResponse>;
  exportDiagnostics?: (
    request: DiagnosticsExportRequest,
  ) => Promise<DiagnosticsExportResponse>;
  exportHardwareTest?: (deviceId: string) => Promise<Blob>;
  scanPrinters: () => Promise<PrinterScanResponse>;
  readOnlyVerify: (deviceId: string) => Promise<ReadOnlyVerification>;
  listProjects: () => Promise<ProjectListResponse>;
  createProject: (request: ProjectMutationRequest) => Promise<ProjectResponse>;
  getProject: (projectId: string) => Promise<ProjectResponse>;
  updateProject: (
    projectId: string,
    request: ProjectMutationRequest,
  ) => Promise<ProjectResponse>;
  deleteProject: (projectId: string) => Promise<void>;
  uploadProjectAsset: (
    projectId: string,
    request: ProjectAssetUploadRequest,
  ) => Promise<ProjectAssetResponse>;
};

export type ProjectMutationRequest = {
  name: string;
  document: PrintDocument;
};

declare global {
  interface Window {
    minix?: {
      getDaemonRuntime: () => Promise<DaemonRuntime>;
      getAppVersion: () => Promise<string>;
      getAgentIntegrationPreview?: () => Promise<AgentIntegrationPreview>;
      listAgentPreviewApprovals?: () => Promise<PendingAgentPreviewApproval[]>;
      removeAgentPreviewApproval?: (previewId: string) => Promise<void>;
      onAgentPreviewApprovalsChanged?: (
        callback: (approvals: PendingAgentPreviewApproval[]) => void,
      ) => (() => void) | undefined;
      installAgentIntegrationConfig?: (
        targetId: AgentIntegrationTargetId,
      ) => Promise<AgentIntegrationInstallResult>;
      uninstallAgentIntegrationConfig?: (
        targetId: AgentIntegrationTargetId,
      ) => Promise<AgentIntegrationInstallResult>;
      testAgentIntegrationConnection?: (
        targetId: AgentIntegrationTargetId,
      ) => Promise<AgentIntegrationConnectionTestResult>;
      exportAgentIntegrationBundle?: (
        targetId: AgentIntegrationTargetId,
      ) => Promise<AgentIntegrationExportResult>;
      exportSupportBundle?: () => Promise<SupportBundleExportResult>;
      createBetaFeedbackDraft?: (
        request?: BetaFeedbackDraftRequest,
      ) => Promise<BetaFeedbackDraft>;
      getUpdateChannelState?: () => Promise<UpdateChannelState>;
      setUpdateChannel?: (
        channel: UpdateChannel,
      ) => Promise<UpdateChannelState>;
      checkHostBluetoothReadiness?: () => Promise<HardwareHostReadiness>;
      inspectHardwareArtifact?: () => Promise<HardwareArtifactInspectionResult | null>;
      inspectTrustedPrinterRecord?: () => Promise<TrustedPrinterRecordInspectionResult | null>;
      inspectStableSupportGate?: () => Promise<StableSupportGateInspectionResult | null>;
      inspectAgentDirectPolicyReview?: () => Promise<AgentDirectPolicyReviewInspectionResult | null>;
      inspectAgentDirectUserOptIn?: () => Promise<AgentDirectUserOptInInspectionResult | null>;
    };
  }
}

export function createDaemonClient(): DaemonClient {
  return {
    async getHealth() {
      return requestDaemon(
        "/v1/health",
        {},
        healthResponseSchema.parse,
        "Daemon health",
      );
    },
    async createDocumentPreview(document, renderSettings) {
      return requestDaemon(
        "/v1/render/document-preview",
        {
          method: "POST",
          body: { document, renderSettings },
        },
        documentPreviewResponseSchema.parse,
        "Daemon document preview",
      );
    },
    async getStoredPreview(previewId) {
      return requestDaemon(
        `/v1/render/previews/${encodeURIComponent(previewId)}`,
        {},
        storedPreviewMetadataResponseSchema.parse,
        "Daemon stored preview",
      );
    },
    async planApprovedPreview(request) {
      return requestDaemon(
        "/v1/jobs/plan",
        {
          method: "POST",
          body: request,
        },
        printPlanResponseSchema.parse,
        "Daemon print plan",
      );
    },
    async printApprovedPreview(request) {
      return requestDaemon(
        "/v1/jobs/print",
        {
          method: "POST",
          body: request,
        },
        printJobResponseSchema.parse,
        "Daemon print job",
      );
    },
    async printStoredPreview(request) {
      return requestDaemon(
        "/v1/jobs/print-stored-preview",
        {
          method: "POST",
          body: request,
        },
        printJobResponseSchema.parse,
        "Daemon stored preview print job",
      );
    },
    async confirmJobOutput(jobId, request) {
      return requestDaemon(
        `/v1/jobs/${encodeURIComponent(jobId)}/operator-confirmation`,
        {
          method: "POST",
          body: request,
        },
        printJobResponseSchema.parse,
        "Daemon operator confirmation",
      );
    },
    async exportDiagnostics(request) {
      return requestDaemon(
        "/v1/diagnostics/export",
        {
          method: "POST",
          body: request,
        },
        diagnosticsExportResponseSchema.parse,
        "Daemon diagnostics export",
      );
    },
    async exportHardwareTest(deviceId) {
      const request: HardwareTestExportRequest = {
        deviceId,
        stage: "read_only_verification",
      };
      return requestDaemonBlob(
        "/v1/diagnostics/hardware-test",
        {
          method: "POST",
          body: request,
        },
        "Daemon hardware-test export",
      );
    },
    async scanPrinters() {
      return requestDaemon(
        "/v1/printers/scan",
        {
          method: "POST",
        },
        printerScanResponseSchema.parse,
        "Daemon printer scan",
      );
    },
    async readOnlyVerify(deviceId) {
      return requestDaemon(
        "/v1/printers/read-only-verify",
        {
          method: "POST",
          body: { deviceId },
        },
        readOnlyVerificationSchema.parse,
        "Daemon read-only printer verification",
      );
    },
    async listProjects() {
      return requestDaemon(
        "/v1/projects",
        {},
        projectListResponseSchema.parse,
        "Daemon project list",
      );
    },
    async createProject(request) {
      return requestDaemon(
        "/v1/projects",
        {
          method: "POST",
          body: request,
        },
        projectResponseSchema.parse,
        "Daemon project create",
      );
    },
    async getProject(projectId) {
      return requestDaemon(
        `/v1/projects/${encodeURIComponent(projectId)}`,
        {},
        projectResponseSchema.parse,
        "Daemon project get",
      );
    },
    async updateProject(projectId, request) {
      return requestDaemon(
        `/v1/projects/${encodeURIComponent(projectId)}`,
        {
          method: "PUT",
          body: request,
        },
        projectResponseSchema.parse,
        "Daemon project update",
      );
    },
    async deleteProject(projectId) {
      return requestDaemonVoid(
        `/v1/projects/${encodeURIComponent(projectId)}`,
        {
          method: "DELETE",
        },
        "Daemon project delete",
      );
    },
    async uploadProjectAsset(projectId, request) {
      return requestDaemon(
        `/v1/projects/${encodeURIComponent(projectId)}/assets`,
        {
          method: "POST",
          body: request,
        },
        projectAssetResponseSchema.parse,
        "Daemon project asset upload",
      );
    },
  };
}

async function requestDaemon<T>(
  path: string,
  options: { method?: "GET" | "POST" | "PUT" | "DELETE"; body?: object },
  parse: (value: unknown) => T,
  label: string,
): Promise<T> {
  const runtime = await getRuntime();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${runtime.token}`,
  };
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers,
  };

  if (options.body) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${runtime.baseUrl}${path}`, init);

  if (!response.ok) {
    throw new Error(await formatDaemonError(response, label));
  }

  return parse(await response.json());
}

async function requestDaemonVoid(
  path: string,
  options: { method: "DELETE" },
  label: string,
): Promise<void> {
  const runtime = await getRuntime();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${runtime.token}`,
  };
  const response = await fetch(`${runtime.baseUrl}${path}`, {
    method: options.method,
    headers,
  });

  if (!response.ok) {
    throw new Error(await formatDaemonError(response, label));
  }
}

async function requestDaemonBlob(
  path: string,
  options: { method?: "GET" | "POST"; body?: object },
  label: string,
): Promise<Blob> {
  const runtime = await getRuntime();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${runtime.token}`,
  };
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers,
  };

  if (options.body) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${runtime.baseUrl}${path}`, init);

  if (!response.ok) {
    throw new Error(await formatDaemonError(response, label));
  }

  return response.blob();
}

async function formatDaemonError(
  response: Response,
  label: string,
): Promise<string> {
  const detail = await readDaemonErrorDetail(response);
  return `${label} failed with ${response.status}${detail ? `: ${detail}` : ""}`;
}

async function readDaemonErrorDetail(
  response: Response,
): Promise<string | null> {
  try {
    const body = await response.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
  } catch {
    return null;
  }
  return null;
}

async function getRuntime(): Promise<DaemonRuntime> {
  if (window.minix) {
    return window.minix.getDaemonRuntime();
  }

  return {
    baseUrl: "http://127.0.0.1:39281",
    token: "dev-token",
  };
}
