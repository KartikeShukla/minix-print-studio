import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bluetooth,
  Boxes,
  CircleAlert,
  Copy,
  Download,
  FileSearch,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Layers3,
  MousePointer2,
  Printer,
  QrCode,
  Redo2,
  RotateCcw,
  Save,
  ScanSearch,
  ShieldCheck,
  Square,
  Trash2,
  Type,
  Undo2,
  Wifi,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import {
  appendElement,
  createDefaultDocument,
  createImageElement,
  createQrElement,
  createRectElement,
  createTextElement,
  imageElementSchema,
  moveElement,
  qrElementSchema,
  rectElementSchema,
  textElementSchema,
  updateElement,
  type ImageElement,
  type PrintDocument,
  type QrElement,
  type RectElement,
  type TextElement
} from "@minix/design-model";
import type Konva from "konva";
import * as QRCode from "qrcode";
import {
  Group,
  Image as KonvaImage,
  Layer,
  Rect,
  Stage,
  Text as KonvaText,
  Transformer
} from "react-konva";
import type {
  DiagnosticsExportResponse,
  DocumentPreviewResponse,
  HealthResponse,
  ProjectResponse,
  ProjectSummary,
  PrintJobResponse,
  PrintPlanResponse,
  PrinterCandidate,
  ReadOnlyVerification,
  RenderSettings
} from "@minix/shared-api";
import {
  desktopAgentIntegrationInstaller,
  loadAgentIntegrationPreview,
  type AgentIntegrationConnectionTestResult,
  type AgentIntegrationExportResult,
  type AgentIntegrationInstallResult,
  type AgentIntegrationInstaller,
  type AgentIntegrationPreview,
  type AgentIntegrationPreviewTarget,
  type AgentIntegrationProvider,
  type AgentIntegrationTargetId
} from "@/lib/agent-integrations";
import { createDaemonClient, type DaemonClient } from "@/lib/api-client";
import { loadStoredDocument, saveStoredDocument } from "@/lib/document-storage";
import {
  loadStoredJobHistory,
  prependStoredPrintJob,
  saveStoredJobHistory,
  type StoredPrintJob
} from "@/lib/job-history";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type AppDaemonClient = Pick<
  DaemonClient,
  | "getHealth"
  | "createDocumentPreview"
  | "planApprovedPreview"
  | "printApprovedPreview"
  | "scanPrinters"
  | "readOnlyVerify"
  | "exportDiagnostics"
  | "exportHardwareTest"
> &
  Partial<
    Pick<
      DaemonClient,
      | "listProjects"
      | "createProject"
      | "getProject"
      | "updateProject"
      | "deleteProject"
      | "uploadProjectAsset"
    >
>;

export type AppProps = {
  daemonClient?: AppDaemonClient;
  agentIntegrationProvider?: AgentIntegrationProvider;
  agentIntegrationInstaller?: AgentIntegrationInstaller;
};

const tools = [
  { label: "Select", icon: MousePointer2 },
  { label: "Text", icon: Type },
  { label: "Rectangle", icon: Square },
  { label: "Image", icon: ImageIcon },
  { label: "QR", icon: QrCode }
];

const DEFAULT_RENDER_SETTINGS = { threshold: 128, dither: "none" } satisfies RenderSettings;
const CANVAS_ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;
const DEFAULT_CANVAS_ZOOM_INDEX = 2;
const CANVAS_PAN_STEP = 48;

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

type DiagnosticsWorkflow =
  | { status: "idle" }
  | { status: "running" }
  | { status: "exported"; bundle: DiagnosticsExportResponse }
  | { status: "error"; message: string };

type HardwareArtifactWorkflow =
  | { status: "idle" }
  | { status: "running"; deviceId: string }
  | { status: "exported"; deviceId: string; sizeBytes: number }
  | { status: "error"; deviceId: string; message: string };

type AgentIntegrationWorkflow =
  | { status: "loading" }
  | { status: "ready"; preview: AgentIntegrationPreview }
  | { status: "unavailable" }
  | { status: "error"; message: string };

type AgentIntegrationMutationWorkflow =
  | { status: "idle" }
  | {
      status: "running";
      action: "install" | "uninstall" | "test" | "export";
      targetId: AgentIntegrationTargetId;
    }
  | {
      status: "success";
      action: "install" | "uninstall";
      targetId: AgentIntegrationTargetId;
      result: AgentIntegrationInstallResult;
    }
  | {
      status: "success";
      action: "test";
      targetId: AgentIntegrationTargetId;
      result: AgentIntegrationConnectionTestResult;
    }
  | {
      status: "success";
      action: "export";
      targetId: AgentIntegrationTargetId;
      result: AgentIntegrationExportResult;
    }
  | {
      status: "error";
      action: "install" | "uninstall" | "test" | "export";
      targetId: AgentIntegrationTargetId;
      message: string;
    };

type PrinterWorkflow =
  | { status: "idle" }
  | { status: "scanning" }
  | { status: "candidates"; candidates: PrinterCandidate[] }
  | { status: "verifying"; candidates: PrinterCandidate[]; deviceId: string }
  | { status: "verified"; candidates: PrinterCandidate[]; verification: ReadOnlyVerification }
  | { status: "error"; message: string };

type ProjectWorkflow =
  | { status: "idle"; projects: ProjectSummary[] }
  | { status: "loading"; projects: ProjectSummary[] }
  | { status: "ready"; projects: ProjectSummary[] }
  | { status: "saving"; projects: ProjectSummary[] }
  | { status: "saved"; projects: ProjectSummary[]; savedProjectId: string }
  | { status: "error"; projects: ProjectSummary[]; message: string };

type EditorState = {
  document: PrintDocument;
  past: PrintDocument[];
  future: PrintDocument[];
  selectedElementId: string | null;
};

type DocumentCommit = (document: PrintDocument) => {
  document: PrintDocument;
  selectedElementId?: string | null;
};

type DocumentElement = PrintDocument["elements"][number];
type ElementUpdater = (element: DocumentElement) => DocumentElement;
type NumericElementField = "x" | "y" | "width" | "height";
type ElementTransform = {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
};

type CanvasElement =
  | { kind: "text"; element: TextElement }
  | { kind: "rect"; element: RectElement }
  | { kind: "image"; element: ImageElement }
  | { kind: "qr"; element: QrElement };

export function App({
  daemonClient,
  agentIntegrationProvider,
  agentIntegrationInstaller
}: AppProps) {
  const client = useMemo(() => daemonClient ?? createDaemonClient(), [daemonClient]);
  const integrationProvider = useMemo(
    () => agentIntegrationProvider ?? loadAgentIntegrationPreview,
    [agentIntegrationProvider]
  );
  const integrationInstaller = useMemo(
    () => agentIntegrationInstaller ?? desktopAgentIntegrationInstaller,
    [agentIntegrationInstaller]
  );
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const [editorState, setEditorState] = useState<EditorState>(() => {
    const document = loadStoredDocument() ?? createDefaultDocument({ heightDots: 900 });
    return {
      document,
      past: [],
      future: [],
      selectedElementId: null
    };
  });
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [previewWorkflow, setPreviewWorkflow] = useState<PreviewWorkflow>({ status: "idle" });
  const [printWorkflow, setPrintWorkflow] = useState<PrintWorkflow>({ status: "idle" });
  const [jobHistory, setJobHistory] = useState<StoredPrintJob[]>(() => loadStoredJobHistory());
  const [projectWorkflow, setProjectWorkflow] = useState<ProjectWorkflow>({
    status: "idle",
    projects: []
  });
  const [diagnosticsWorkflow, setDiagnosticsWorkflow] = useState<DiagnosticsWorkflow>({
    status: "idle"
  });
  const [hardwareArtifactWorkflow, setHardwareArtifactWorkflow] =
    useState<HardwareArtifactWorkflow>({
      status: "idle"
    });
  const [agentIntegrationWorkflow, setAgentIntegrationWorkflow] =
    useState<AgentIntegrationWorkflow>({
      status: "loading"
    });
  const [copiedIntegrationId, setCopiedIntegrationId] =
    useState<AgentIntegrationTargetId | null>(null);
  const [agentIntegrationCopyError, setAgentIntegrationCopyError] = useState<string | null>(null);
  const [agentIntegrationMutation, setAgentIntegrationMutation] =
    useState<AgentIntegrationMutationWorkflow>({ status: "idle" });
  const [printerWorkflow, setPrinterWorkflow] = useState<PrinterWorkflow>({ status: "idle" });
  const [editingTextElementId, setEditingTextElementId] = useState<string | null>(null);
  const [canvasZoomIndex, setCanvasZoomIndex] = useState(DEFAULT_CANVAS_ZOOM_INDEX);
  const [canvasPan, setCanvasPan] = useState({ x: 0, y: 0 });
  const { document, past, future, selectedElementId } = editorState;

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

  useEffect(() => {
    saveStoredDocument(document);
  }, [document]);

  useEffect(() => {
    let cancelled = false;

    setAgentIntegrationWorkflow({ status: "loading" });
    setCopiedIntegrationId(null);
    setAgentIntegrationCopyError(null);
    setAgentIntegrationMutation({ status: "idle" });

    integrationProvider()
      .then((preview) => {
        if (cancelled) {
          return;
        }
        setAgentIntegrationWorkflow(preview ? { status: "ready", preview } : { status: "unavailable" });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setAgentIntegrationWorkflow({
            status: "error",
            message: error instanceof Error ? error.message : "Integration preview unavailable"
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [integrationProvider]);

  useEffect(() => {
    if (
      editingTextElementId &&
      !document.elements.some(
        (element) => element.id === editingTextElementId && element.type === "text"
      )
    ) {
      setEditingTextElementId(null);
    }
  }, [document.elements, editingTextElementId]);

  const invalidatePreview = useCallback(() => {
    setPreviewWorkflow({ status: "idle" });
    setPrintWorkflow({ status: "idle" });
  }, []);

  const commitDocument = useCallback(
    (commit: DocumentCommit) => {
      setEditorState((currentState) => {
        const next = commit(currentState.document);
        return {
          document: next.document,
          past: [...currentState.past, currentState.document].slice(-50),
          future: [],
          selectedElementId: next.selectedElementId ?? currentState.selectedElementId
        };
      });
      invalidatePreview();
    },
    [invalidatePreview]
  );

  const selectElement = useCallback((elementId: string | null) => {
    setEditorState((currentState) => ({ ...currentState, selectedElementId: elementId }));
  }, []);

  const startInlineTextEdit = useCallback(
    (elementId: string) => {
      selectElement(elementId);
      setEditingTextElementId(elementId);
    },
    [selectElement]
  );

  const addTextLayer = useCallback(() => {
    commitDocument((currentDocument) => {
      const textCount = currentDocument.elements.filter(
        (element) => element.type === "text"
      ).length;
      const element = createTextElement({
        name: `Text ${textCount + 1}`,
        text: "Double-click to edit",
        x: 24,
        y: 56 + textCount * 24,
        width: currentDocument.target.widthDots - 48,
        height: 80
      });
      return {
        document: appendElement(currentDocument, element),
        selectedElementId: element.id
      };
    });
  }, [commitDocument]);

  const addRectangleLayer = useCallback(() => {
    commitDocument((currentDocument) => {
      const rectCount = currentDocument.elements.filter(
        (element) => element.type === "rect"
      ).length;
      const element = createRectElement({
        name: `Rectangle ${rectCount + 1}`,
        x: 32,
        y: 144 + rectCount * 32,
        width: currentDocument.target.widthDots - 64,
        height: 72
      });
      return {
        document: appendElement(currentDocument, element),
        selectedElementId: element.id
      };
    });
  }, [commitDocument]);

  const addQrLayer = useCallback(() => {
    commitDocument((currentDocument) => {
      const qrCount = currentDocument.elements.filter((element) => element.type === "qr").length;
      const size = 128;
      const element = createQrElement({
        name: `QR ${qrCount + 1}`,
        payload: "https://example.com",
        x: Math.round((currentDocument.target.widthDots - size) / 2),
        y: 240 + qrCount * 32,
        size
      });
      return {
        document: appendElement(currentDocument, element),
        selectedElementId: element.id
      };
    });
  }, [commitDocument]);

  const importImageFile = useCallback(
    (file: File) => {
      if (!file.type.startsWith("image/")) {
        return;
      }
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        if (typeof reader.result !== "string") {
          return;
        }
        commitDocument((currentDocument) => {
          const imageCount = currentDocument.elements.filter(
            (element) => element.type === "image"
          ).length;
          const element = createImageElement({
            name: `Image ${imageCount + 1}`,
            dataUrl: reader.result as string,
            mimeType: file.type,
            x: 32,
            y: 280 + imageCount * 32,
            width: Math.min(256, currentDocument.target.widthDots - 64),
            height: 160
          });
          return {
            document: appendElement(currentDocument, element),
            selectedElementId: element.id
          };
        });
      });
      reader.readAsDataURL(file);
    },
    [commitDocument]
  );

  const handleImageFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.currentTarget.files?.[0];
      if (file) {
        importImageFile(file);
      }
      event.currentTarget.value = "";
    },
    [importImageFile]
  );

  const moveDocumentElement = useCallback(
    (elementId: string, x: number, y: number) => {
      commitDocument((currentDocument) => ({
        document: moveElement(currentDocument, elementId, { x, y }),
        selectedElementId: elementId
      }));
    },
    [commitDocument]
  );

  const updateDocumentElement = useCallback(
    (elementId: string, updater: ElementUpdater) => {
      commitDocument((currentDocument) => ({
        document: updateElement(currentDocument, elementId, updater),
        selectedElementId: elementId
      }));
    },
    [commitDocument]
  );

  const transformDocumentElement = useCallback(
    (elementId: string, transform: ElementTransform) => {
      updateDocumentElement(elementId, (currentElement) => ({
        ...currentElement,
        x: normalizeDotValue(transform.x, 0),
        y: normalizeDotValue(transform.y, 0),
        width: normalizeDotValue(transform.width, 1),
        height: normalizeDotValue(transform.height, 1),
        rotation: Math.round(transform.rotation)
      }));
    },
    [updateDocumentElement]
  );

  const commitInlineTextEdit = useCallback(
    (elementId: string, text: string) => {
      updateDocumentElement(elementId, (currentElement) => {
        const currentText = textElementSchema.safeParse(currentElement);
        return currentText.success ? { ...currentText.data, text } : currentElement;
      });
      setEditingTextElementId(null);
    },
    [updateDocumentElement]
  );

  const cancelInlineTextEdit = useCallback(() => {
    setEditingTextElementId(null);
  }, []);

  const zoomCanvasOut = useCallback(() => {
    setCanvasZoomIndex((currentIndex) => Math.max(0, currentIndex - 1));
  }, []);

  const zoomCanvasIn = useCallback(() => {
    setCanvasZoomIndex((currentIndex) =>
      Math.min(CANVAS_ZOOM_STEPS.length - 1, currentIndex + 1)
    );
  }, []);

  const resetCanvasZoom = useCallback(() => {
    setCanvasZoomIndex(DEFAULT_CANVAS_ZOOM_INDEX);
  }, []);

  const panCanvas = useCallback((x: number, y: number) => {
    setCanvasPan((currentPan) => ({
      x: currentPan.x + x,
      y: currentPan.y + y
    }));
  }, []);

  const resetCanvasPan = useCallback(() => {
    setCanvasPan({ x: 0, y: 0 });
  }, []);

  const undoDocumentChange = useCallback(() => {
    setEditingTextElementId(null);
    setEditorState((currentState) => {
      const previousDocument = currentState.past.at(-1);
      if (!previousDocument) {
        return currentState;
      }
      return {
        document: previousDocument,
        past: currentState.past.slice(0, -1),
        future: [currentState.document, ...currentState.future],
        selectedElementId: null
      };
    });
    invalidatePreview();
  }, [invalidatePreview]);

  const redoDocumentChange = useCallback(() => {
    setEditingTextElementId(null);
    setEditorState((currentState) => {
      const nextDocument = currentState.future[0];
      if (!nextDocument) {
        return currentState;
      }
      return {
        document: nextDocument,
        past: [...currentState.past, currentState.document].slice(-50),
        future: currentState.future.slice(1),
        selectedElementId: null
      };
    });
    invalidatePreview();
  }, [invalidatePreview]);

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

  const loadProjects = useCallback(async () => {
    if (!client.listProjects) {
      setProjectWorkflow((current) => ({
        status: "error",
        projects: current.projects,
        message: "Project API unavailable"
      }));
      return;
    }
    setProjectWorkflow((current) => ({ status: "loading", projects: current.projects }));
    try {
      const response = await client.listProjects();
      setProjectWorkflow({ status: "ready", projects: response.projects });
    } catch (error: unknown) {
      setProjectWorkflow((current) => ({
        status: "error",
        projects: current.projects,
        message: error instanceof Error ? error.message : "Project list failed"
      }));
    }
  }, [client]);

  const saveProject = useCallback(async () => {
    if (!client.createProject) {
      setProjectWorkflow((current) => ({
        status: "error",
        projects: current.projects,
        message: "Project API unavailable"
      }));
      return;
    }
    setProjectWorkflow((current) => ({ status: "saving", projects: current.projects }));
    try {
      const savedProject = await client.createProject({
        name: document.title,
        document
      });
      const summary = projectSummaryFromResponse(savedProject);
      setProjectWorkflow((current) => ({
        status: "saved",
        projects: upsertProjectSummary(current.projects, summary),
        savedProjectId: savedProject.projectId
      }));
    } catch (error: unknown) {
      setProjectWorkflow((current) => ({
        status: "error",
        projects: current.projects,
        message: error instanceof Error ? error.message : "Project save failed"
      }));
    }
  }, [client, document]);

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
      setJobHistory((currentHistory) => {
        const nextHistory = prependStoredPrintJob(currentHistory, job);
        saveStoredJobHistory(nextHistory);
        return nextHistory;
      });
      setPrintWorkflow({ status: "completed", job });
    } catch (error: unknown) {
      setPrintWorkflow({
        status: "error",
        message: error instanceof Error ? error.message : "Print failed"
      });
    }
  }, [client, document, previewWorkflow]);

  const runDiagnosticsExport = useCallback(async () => {
    if (!client.exportDiagnostics) {
      setDiagnosticsWorkflow({
        status: "error",
        message: "Diagnostics export unavailable"
      });
      return;
    }
    setDiagnosticsWorkflow({ status: "running" });
    try {
      const bundle = await client.exportDiagnostics({
        includeProjectContent: false,
        includeRawImages: false
      });
      setDiagnosticsWorkflow({ status: "exported", bundle });
    } catch (error: unknown) {
      setDiagnosticsWorkflow({
        status: "error",
        message: error instanceof Error ? error.message : "Diagnostics export failed"
      });
    }
  }, [client]);

  const runHardwareArtifactExport = useCallback(
    async (deviceId: string) => {
      if (!client.exportHardwareTest) {
        setHardwareArtifactWorkflow({
          status: "error",
          deviceId,
          message: "Hardware artifact export unavailable"
        });
        return;
      }
      setHardwareArtifactWorkflow({ status: "running", deviceId });
      try {
        const artifact = await client.exportHardwareTest(deviceId);
        downloadBlob(artifact, "hardware-test-read-only.zip");
        setHardwareArtifactWorkflow({
          status: "exported",
          deviceId,
          sizeBytes: artifact.size
        });
      } catch (error: unknown) {
        setHardwareArtifactWorkflow({
          status: "error",
          deviceId,
          message: error instanceof Error ? error.message : "Hardware artifact export failed"
        });
      }
    },
    [client]
  );

  const copyAgentIntegrationConfig = useCallback(async (target: AgentIntegrationPreviewTarget) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard unavailable");
      }
      await navigator.clipboard.writeText(target.content);
      setCopiedIntegrationId(target.id);
      setAgentIntegrationCopyError(null);
    } catch (error: unknown) {
      setCopiedIntegrationId(null);
      setAgentIntegrationCopyError(error instanceof Error ? error.message : "Copy failed");
    }
  }, []);

  const installAgentIntegrationTarget = useCallback(
    async (target: AgentIntegrationPreviewTarget) => {
      if (!target.installable) {
        return;
      }
      const confirmed = window.confirm(
        `Install ${target.name} MCP config?\n\nTarget file:\n${target.configPath}\n\nA backup will be created before modifying the file.`
      );
      if (!confirmed) {
        return;
      }
      setAgentIntegrationMutation({
        status: "running",
        action: "install",
        targetId: target.id
      });
      try {
        const result = await integrationInstaller.install(target.id);
        setAgentIntegrationMutation({
          status: "success",
          action: "install",
          targetId: target.id,
          result
        });
      } catch (error: unknown) {
        setAgentIntegrationMutation({
          status: "error",
          action: "install",
          targetId: target.id,
          message: error instanceof Error ? error.message : "Install failed"
        });
      }
    },
    [integrationInstaller]
  );

  const uninstallAgentIntegrationTarget = useCallback(
    async (target: AgentIntegrationPreviewTarget) => {
      if (!target.installable) {
        return;
      }
      const confirmed = window.confirm(
        `Uninstall ${target.name} MCP config?\n\nTarget file:\n${target.configPath}\n\nA backup will be created before modifying the file.`
      );
      if (!confirmed) {
        return;
      }
      setAgentIntegrationMutation({
        status: "running",
        action: "uninstall",
        targetId: target.id
      });
      try {
        const result = await integrationInstaller.uninstall(target.id);
        setAgentIntegrationMutation({
          status: "success",
          action: "uninstall",
          targetId: target.id,
          result
        });
      } catch (error: unknown) {
        setAgentIntegrationMutation({
          status: "error",
          action: "uninstall",
          targetId: target.id,
          message: error instanceof Error ? error.message : "Uninstall failed"
        });
      }
    },
    [integrationInstaller]
  );

  const testAgentIntegrationTarget = useCallback(
    async (target: AgentIntegrationPreviewTarget) => {
      setAgentIntegrationMutation({
        status: "running",
        action: "test",
        targetId: target.id
      });
      try {
        const result = await integrationInstaller.testConnection(target.id);
        setAgentIntegrationMutation({
          status: "success",
          action: "test",
          targetId: target.id,
          result
        });
      } catch (error: unknown) {
        setAgentIntegrationMutation({
          status: "error",
          action: "test",
          targetId: target.id,
          message: error instanceof Error ? error.message : "Connection test failed"
        });
      }
    },
    [integrationInstaller]
  );

  const exportAgentIntegrationTarget = useCallback(
    async (target: AgentIntegrationPreviewTarget) => {
      if (!target.exportable) {
        return;
      }
      setAgentIntegrationMutation({
        status: "running",
        action: "export",
        targetId: target.id
      });
      try {
        const exportBundle = integrationInstaller.exportBundle;
        if (!exportBundle) {
          throw new Error("Agent integration export is unavailable");
        }
        const result = await exportBundle(target.id);
        setAgentIntegrationMutation({
          status: "success",
          action: "export",
          targetId: target.id,
          result
        });
      } catch (error: unknown) {
        setAgentIntegrationMutation({
          status: "error",
          action: "export",
          targetId: target.id,
          message: error instanceof Error ? error.message : "Export failed"
        });
      }
    },
    [integrationInstaller]
  );

  const statusLabel = health
    ? health.mock
      ? "Mock daemon online"
      : "Daemon online"
    : healthError
      ? "Daemon offline"
      : "Checking daemon";
  const previewReady = previewWorkflow.status === "ready";
  const canUndo = past.length > 0;
  const canRedo = future.length > 0;
  const canvasZoom =
    CANVAS_ZOOM_STEPS[canvasZoomIndex] ?? CANVAS_ZOOM_STEPS[DEFAULT_CANVAS_ZOOM_INDEX];
  const canZoomOut = canvasZoomIndex > 0;
  const canZoomIn = canvasZoomIndex < CANVAS_ZOOM_STEPS.length - 1;
  const canResetPan = canvasPan.x !== 0 || canvasPan.y !== 0;
  const selectedElement = useMemo(
    () => document.elements.find((element) => element.id === selectedElementId) ?? null,
    [document.elements, selectedElementId]
  );

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
                {document.title} - {formatPaperMode(document.target.paperMode)}
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
              size="icon"
              title="Undo"
              aria-label="Undo"
              onClick={undoDocumentChange}
              disabled={!canUndo}
            >
              <Undo2 className="size-4" aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              title="Redo"
              aria-label="Redo"
              onClick={redoDocumentChange}
              disabled={!canRedo}
            >
              <Redo2 className="size-4" aria-hidden="true" />
            </Button>
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
                      onClick={
                        tool.label === "Text"
                          ? addTextLayer
                          : tool.label === "Rectangle"
                            ? addRectangleLayer
                            : tool.label === "Image"
                              ? () => imageInputRef.current?.click()
                            : tool.label === "QR"
                              ? addQrLayer
                            : undefined
                      }
                    >
                      <Icon className="size-4" aria-hidden="true" />
                    </Button>
                  );
                })}
              </div>
              <input
                ref={imageInputRef}
                type="file"
                aria-label="Import image"
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                onChange={handleImageFileChange}
              />
            </section>

            <section className="p-3">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-xs font-medium uppercase text-muted-foreground">Layers</div>
                <Layers3 className="size-4 text-muted-foreground" aria-hidden="true" />
              </div>
              <div className="space-y-2">
                <LayerList
                  document={document}
                  selectedElementId={selectedElementId}
                  onSelect={selectElement}
                />
              </div>
            </section>
          </aside>

          <section className="min-h-0 overflow-auto bg-workspace p-6">
            <div className="mx-auto flex min-h-full w-full max-w-4xl items-start justify-center">
              <DocumentCanvas
                document={document}
                selectedElementId={selectedElementId}
                previewReady={previewReady}
                totalBands={previewReady ? previewWorkflow.plan.totalBands : null}
                editingTextElementId={editingTextElementId}
                zoom={canvasZoom}
                pan={canvasPan}
                onSelect={selectElement}
                onMove={moveDocumentElement}
                onTransform={transformDocumentElement}
                onStartTextEdit={startInlineTextEdit}
                onCommitTextEdit={commitInlineTextEdit}
                onCancelTextEdit={cancelInlineTextEdit}
              />
            </div>
          </section>

          <aside className="min-h-0 overflow-auto border-l border-border bg-card">
            <ProjectsPanel
              workflow={projectWorkflow}
              canLoad={Boolean(client.listProjects)}
              canSave={Boolean(client.createProject)}
              onLoad={loadProjects}
              onSave={saveProject}
            />
            <PrinterPanel
              workflow={printerWorkflow}
              hardwareArtifactWorkflow={hardwareArtifactWorkflow}
              onVerify={runReadOnlyVerify}
              onExportHardwareArtifact={runHardwareArtifactExport}
            />
            <ElementInspector element={selectedElement} onUpdate={updateDocumentElement} />

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

            <AgentIntegrationsPanel
              workflow={agentIntegrationWorkflow}
              copiedTargetId={copiedIntegrationId}
              copyError={agentIntegrationCopyError}
              mutation={agentIntegrationMutation}
              onCopy={copyAgentIntegrationConfig}
              onInstall={installAgentIntegrationTarget}
              onUninstall={uninstallAgentIntegrationTarget}
              onTest={testAgentIntegrationTarget}
              onExport={exportAgentIntegrationTarget}
            />

            <RecentJobsPanel
              jobs={jobHistory}
              workflow={diagnosticsWorkflow}
              onExport={runDiagnosticsExport}
            />
          </aside>
        </main>

        <footer className="flex items-center justify-between border-t border-border bg-card px-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Zoom out"
              aria-label="Zoom out"
              onClick={zoomCanvasOut}
              disabled={!canZoomOut}
            >
              <ZoomOut className="size-3.5" aria-hidden="true" />
            </Button>
            <span className="w-20 text-center tabular-nums">{formatZoom(canvasZoom)}</span>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Zoom in"
              aria-label="Zoom in"
              onClick={zoomCanvasIn}
              disabled={!canZoomIn}
            >
              <ZoomIn className="size-3.5" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Reset zoom"
              aria-label="Reset zoom"
              onClick={resetCanvasZoom}
              disabled={canvasZoomIndex === DEFAULT_CANVAS_ZOOM_INDEX}
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
            </Button>
          </div>
          <div className="flex items-center gap-1 border-l border-border pl-3">
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Pan left"
              aria-label="Pan left"
              onClick={() => panCanvas(-CANVAS_PAN_STEP, 0)}
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Pan up"
              aria-label="Pan up"
              onClick={() => panCanvas(0, -CANVAS_PAN_STEP)}
            >
              <ArrowUp className="size-3.5" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Pan down"
              aria-label="Pan down"
              onClick={() => panCanvas(0, CANVAS_PAN_STEP)}
            >
              <ArrowDown className="size-3.5" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Pan right"
              aria-label="Pan right"
              onClick={() => panCanvas(CANVAS_PAN_STEP, 0)}
            >
              <ArrowRight className="size-3.5" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 rounded-sm"
              title="Reset pan"
              aria-label="Reset pan"
              onClick={resetCanvasPan}
              disabled={!canResetPan}
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
            </Button>
          </div>
          <span>{health ? `Daemon ${health.version}` : "No daemon health yet"}</span>
          <span>{formatQueueStatus(previewReady, printWorkflow)}</span>
        </footer>
      </div>
    </div>
  );
}

function ProjectsPanel({
  workflow,
  canLoad,
  canSave,
  onLoad,
  onSave
}: {
  workflow: ProjectWorkflow;
  canLoad: boolean;
  canSave: boolean;
  onLoad: () => void;
  onSave: () => void;
}) {
  return (
    <section className="border-b border-border p-4">
      <div className="mb-3 flex items-center gap-2">
        <FolderOpen className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">Projects</h2>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Load projects"
          onClick={onLoad}
          disabled={!canLoad || workflow.status === "loading"}
        >
          <FolderOpen className="size-4" aria-hidden="true" />
          {workflow.status === "loading" ? "Loading" : "Load"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Save project"
          onClick={onSave}
          disabled={!canSave || workflow.status === "saving"}
        >
          <Save className="size-4" aria-hidden="true" />
          {workflow.status === "saving" ? "Saving" : "Save"}
        </Button>
      </div>
      {workflow.status === "saved" ? (
        <div className="mt-3 rounded-md border border-success/30 bg-success/10 p-2 text-sm text-success">
          Saved project {workflow.savedProjectId}
        </div>
      ) : workflow.status === "error" ? (
        <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {workflow.message}
        </div>
      ) : null}
      {workflow.projects.length > 0 ? (
        <div className="mt-3 space-y-2">
          {workflow.projects.slice(0, 5).map((project) => (
            <div
              key={project.projectId}
              className="rounded-md border border-border bg-background p-2 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{project.name}</span>
                <Badge variant="muted">{project.documentId}</Badge>
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                {project.projectId}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function RecentJobsPanel({
  jobs,
  workflow,
  onExport
}: {
  jobs: StoredPrintJob[];
  workflow: DiagnosticsWorkflow;
  onExport: () => void;
}) {
  if (jobs.length === 0) {
    return null;
  }

  return (
    <section className="border-t border-border p-4">
      <div className="mb-3 flex items-center gap-2">
        <Boxes className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">Recent Jobs</h2>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mb-3 w-full"
        onClick={onExport}
        disabled={workflow.status === "running"}
      >
        <FileText className="size-4" aria-hidden="true" />
        {workflow.status === "running" ? "Exporting diagnostics" : "Export diagnostics"}
      </Button>
      {workflow.status === "exported" ? (
        <div className="mb-3 rounded-md border border-success/30 bg-success/10 p-2 text-sm text-success">
          <div className="font-medium">Diagnostics exported</div>
          <div className="text-xs">{formatDiagnosticsJobCount(workflow.bundle.jobs.length)}</div>
        </div>
      ) : workflow.status === "error" ? (
        <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {workflow.message}
        </div>
      ) : null}
      <div className="space-y-2">
        {jobs.slice(0, 5).map((job) => (
          <div key={job.jobId} className="rounded-md border border-border bg-background p-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium">{job.jobId}</span>
              <Badge variant={job.requiresUserCheck ? "warning" : "success"}>{job.state}</Badge>
            </div>
            <div className="mt-1 flex justify-between text-xs text-muted-foreground">
              <span>{job.completionLevel}</span>
              <span>
                {job.bandsSent}/{job.totalBands} bands
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AgentIntegrationsPanel({
  workflow,
  copiedTargetId,
  copyError,
  mutation,
  onCopy,
  onInstall,
  onUninstall,
  onTest,
  onExport
}: {
  workflow: AgentIntegrationWorkflow;
  copiedTargetId: AgentIntegrationTargetId | null;
  copyError: string | null;
  mutation: AgentIntegrationMutationWorkflow;
  onCopy: (target: AgentIntegrationPreviewTarget) => void;
  onInstall: (target: AgentIntegrationPreviewTarget) => void;
  onUninstall: (target: AgentIntegrationPreviewTarget) => void;
  onTest: (target: AgentIntegrationPreviewTarget) => void;
  onExport: (target: AgentIntegrationPreviewTarget) => void;
}) {
  return (
    <section className="border-t border-border p-4">
      <div className="mb-3 flex items-center gap-2">
        <Copy className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">Agent Integrations</h2>
      </div>

      {workflow.status === "loading" ? (
        <p className="text-sm leading-6 text-muted-foreground">Loading local MCP config previews.</p>
      ) : workflow.status === "unavailable" ? (
        <p className="text-sm leading-6 text-muted-foreground">
          Open the desktop app to generate local MCP config previews.
        </p>
      ) : workflow.status === "error" ? (
        <p className="text-sm leading-6 text-destructive">{workflow.message}</p>
      ) : (
        <div className="space-y-3">
          <div className="rounded-md border border-border bg-background p-2 text-xs text-muted-foreground">
            <div className="font-medium text-foreground">Runtime handoff</div>
            <div className="mt-1 break-all">{workflow.preview.runtimeFilePath}</div>
          </div>
          {copyError ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
              {copyError}
            </div>
          ) : null}
          {workflow.preview.targets.map((target) => (
            <article
              key={target.id}
              className="rounded-md border border-border bg-background p-3 text-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-medium">{target.name}</h3>
                  <div className="mt-1 break-all text-xs text-muted-foreground">
                    {target.configPath}
                  </div>
                </div>
                <Badge variant="muted">{target.format}</Badge>
              </div>
              <pre className="mt-3 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded-md border border-border bg-muted/40 p-2 text-[11px] leading-4 text-muted-foreground">{target.content}</pre>
              <div className="mt-2 grid grid-cols-1 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  aria-label={`Copy ${target.name} config`}
                  onClick={() => onCopy(target)}
                >
                  <Copy className="size-4" aria-hidden="true" />
                  Copy
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  aria-label={`Test ${target.name} connection`}
                  onClick={() => onTest(target)}
                  disabled={mutation.status === "running" && mutation.targetId === target.id}
                >
                  <Wifi className="size-4" aria-hidden="true" />
                  Test
                </Button>
                {target.exportable ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full"
                    aria-label={`Export ${target.name} .mcpb`}
                    onClick={() => onExport(target)}
                    disabled={mutation.status === "running" && mutation.targetId === target.id}
                  >
                    <Download className="size-4" aria-hidden="true" />
                    Export .mcpb
                  </Button>
                ) : null}
                {target.installable ? (
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Install ${target.name} config`}
                      onClick={() => onInstall(target)}
                      disabled={
                        mutation.status === "running" && mutation.targetId === target.id
                      }
                    >
                      <Download className="size-4" aria-hidden="true" />
                      Install
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Uninstall ${target.name} config`}
                      onClick={() => onUninstall(target)}
                      disabled={
                        mutation.status === "running" && mutation.targetId === target.id
                      }
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      Uninstall
                    </Button>
                  </div>
                ) : null}
              </div>
              {copiedTargetId === target.id ? (
                <div className="mt-2 text-xs font-medium text-success">
                  Copied {target.name} config
                </div>
              ) : null}
              {mutation.status === "success" && mutation.targetId === target.id ? (
                <div className="mt-2 text-xs font-medium text-success">
                  {mutation.action === "test"
                    ? mutation.result.message
                    : mutation.action === "export"
                      ? `Exported ${target.name} .mcpb`
                      : `${mutation.action === "install" ? "Installed" : "Uninstalled"} ${target.name} config`}
                  {mutation.action === "export" ? (
                    <div className="mt-1 break-all font-normal text-muted-foreground">
                      {mutation.result.targetPath}
                    </div>
                  ) : null}
                </div>
              ) : mutation.status === "error" && mutation.targetId === target.id ? (
                <div className="mt-2 text-xs font-medium text-destructive">
                  {mutation.message}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ElementInspector({
  element,
  onUpdate
}: {
  element: DocumentElement | null;
  onUpdate: (elementId: string, updater: ElementUpdater) => void;
}) {
  const textElement = element ? textElementSchema.safeParse(element) : null;
  const rectElement = element ? rectElementSchema.safeParse(element) : null;
  const imageElement = element ? imageElementSchema.safeParse(element) : null;
  const qrElement = element ? qrElementSchema.safeParse(element) : null;

  const updateTextField = (value: string) => {
    if (!element) {
      return;
    }
    onUpdate(element.id, (currentElement) => ({ ...currentElement, name: value }));
  };

  const updateBooleanField = (field: "locked" | "visible", value: boolean) => {
    if (!element) {
      return;
    }
    onUpdate(element.id, (currentElement) => ({ ...currentElement, [field]: value }));
  };

  const updateNumberField = (field: NumericElementField, value: number) => {
    if (!element) {
      return;
    }
    const minimum = field === "width" || field === "height" ? 1 : 0;
    onUpdate(element.id, (currentElement) => ({
      ...currentElement,
      [field]: normalizeDotValue(value, minimum)
    }));
  };

  return (
    <section className="border-b border-border p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Inspector</h2>
        {element ? <Badge variant="muted">{formatElementType(element.type)}</Badge> : null}
      </div>

      {element ? (
        <div className="space-y-4">
          <label className="block text-xs font-medium text-muted-foreground" htmlFor="inspector-name">
            Name
            <input
              id="inspector-name"
              className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
              value={element.name}
              onChange={(event) => updateTextField(event.currentTarget.value)}
            />
          </label>

          <div>
            <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">Geometry</div>
            <div className="grid grid-cols-2 gap-2">
              <InspectorNumberField
                id="inspector-x"
                label="X"
                value={element.x}
                min={0}
                onChange={(value) => updateNumberField("x", value)}
              />
              <InspectorNumberField
                id="inspector-y"
                label="Y"
                value={element.y}
                min={0}
                onChange={(value) => updateNumberField("y", value)}
              />
              <InspectorNumberField
                id="inspector-width"
                label="Width"
                value={element.width}
                min={1}
                onChange={(value) => updateNumberField("width", value)}
              />
              <InspectorNumberField
                id="inspector-height"
                label="Height"
                value={element.height}
                min={1}
                onChange={(value) => updateNumberField("height", value)}
              />
            </div>
          </div>

          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={element.visible}
                onChange={(event) => updateBooleanField("visible", event.currentTarget.checked)}
              />
              Visible
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={element.locked}
                onChange={(event) => updateBooleanField("locked", event.currentTarget.checked)}
              />
              Locked
            </label>
          </div>

          {rectElement?.success ? (
            <div>
              <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">Fill</div>
              <FillSwatches
                value={rectElement.data.fill}
                onChange={(fill) => {
                  onUpdate(element.id, (currentElement) => {
                    const currentRect = rectElementSchema.safeParse(currentElement);
                    return currentRect.success ? { ...currentRect.data, fill } : currentElement;
                  });
                }}
              />
            </div>
          ) : null}

          {textElement?.success ? (
            <div className="space-y-3">
              <label
                className="block text-xs font-medium text-muted-foreground"
                htmlFor="inspector-text-content"
              >
                Text content
                <textarea
                  id="inspector-text-content"
                  className="mt-1 min-h-20 w-full resize-none rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground"
                  value={textElement.data.text}
                  onChange={(event) => {
                    const text = event.currentTarget.value;
                    onUpdate(element.id, (currentElement) => {
                      const currentText = textElementSchema.safeParse(currentElement);
                      return currentText.success
                        ? { ...currentText.data, text }
                        : currentElement;
                    });
                  }}
                />
              </label>
              <div>
                <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                  Text Fill
                </div>
                <FillSwatches
                  value={textElement.data.style.fill}
                  onChange={(fill) => {
                    onUpdate(element.id, (currentElement) => {
                      const currentText = textElementSchema.safeParse(currentElement);
                      return currentText.success
                        ? {
                            ...currentText.data,
                            style: { ...currentText.data.style, fill }
                          }
                        : currentElement;
                    });
                  }}
                />
              </div>
            </div>
          ) : null}

          {imageElement?.success ? (
            <div className="space-y-3">
              <div>
                <div className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                  Source
                </div>
                <div className="truncate text-sm">{imageElement.data.source.mimeType}</div>
              </div>
              <label
                className="block text-xs font-medium text-muted-foreground"
                htmlFor="inspector-image-fit"
              >
                Fit
                <select
                  id="inspector-image-fit"
                  className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  value={imageElement.data.fit}
                  onChange={(event) => {
                    const fit = event.currentTarget.value as ImageElement["fit"];
                    onUpdate(element.id, (currentElement) => {
                      const currentImage = imageElementSchema.safeParse(currentElement);
                      return currentImage.success ? { ...currentImage.data, fit } : currentElement;
                    });
                  }}
                >
                  <option value="contain">Contain</option>
                  <option value="cover">Cover</option>
                  <option value="stretch">Stretch</option>
                </select>
              </label>
              <InspectorNumberField
                id="inspector-image-threshold"
                label="Threshold"
                value={imageElement.data.processing.threshold}
                min={0}
                max={255}
                onChange={(value) => {
                  onUpdate(element.id, (currentElement) => {
                    const currentImage = imageElementSchema.safeParse(currentElement);
                    return currentImage.success
                      ? {
                          ...currentImage.data,
                          processing: {
                            ...currentImage.data.processing,
                            threshold: Math.min(255, normalizeDotValue(value, 0))
                          }
                        }
                      : currentElement;
                  });
                }}
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 accent-primary"
                  checked={imageElement.data.processing.invert}
                  onChange={(event) => {
                    const invert = event.currentTarget.checked;
                    onUpdate(element.id, (currentElement) => {
                      const currentImage = imageElementSchema.safeParse(currentElement);
                      return currentImage.success
                        ? {
                            ...currentImage.data,
                            processing: {
                              ...currentImage.data.processing,
                              invert
                            }
                          }
                        : currentElement;
                    });
                  }}
                />
                Invert image
              </label>
            </div>
          ) : null}

          {qrElement?.success ? (
            <div className="space-y-3">
              <label
                className="block text-xs font-medium text-muted-foreground"
                htmlFor="inspector-qr-payload"
              >
                QR Payload
                <textarea
                  id="inspector-qr-payload"
                  className="mt-1 min-h-20 w-full resize-none rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground"
                  value={qrElement.data.payload}
                  onChange={(event) => {
                    const payload = event.currentTarget.value;
                    onUpdate(element.id, (currentElement) => {
                      const currentQr = qrElementSchema.safeParse(currentElement);
                      return currentQr.success
                        ? { ...currentQr.data, payload }
                        : currentElement;
                    });
                  }}
                />
              </label>
              <label
                className="block text-xs font-medium text-muted-foreground"
                htmlFor="inspector-qr-error-correction"
              >
                Error correction
                <select
                  id="inspector-qr-error-correction"
                  className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  value={qrElement.data.errorCorrectionLevel}
                  onChange={(event) => {
                    const errorCorrectionLevel = event.currentTarget
                      .value as QrElement["errorCorrectionLevel"];
                    onUpdate(element.id, (currentElement) => {
                      const currentQr = qrElementSchema.safeParse(currentElement);
                      return currentQr.success
                        ? { ...currentQr.data, errorCorrectionLevel }
                        : currentElement;
                    });
                  }}
                >
                  <option value="L">Low</option>
                  <option value="M">Medium</option>
                  <option value="Q">Quartile</option>
                  <option value="H">High</option>
                </select>
              </label>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No layer selected</p>
      )}
    </section>
  );
}

function InspectorNumberField({
  id,
  label,
  value,
  min,
  max,
  onChange
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-xs font-medium text-muted-foreground" htmlFor={id}>
      {label}
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={1}
        className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
        value={value}
        onChange={(event) => {
          const rawValue = event.currentTarget.value.trim();
          if (rawValue.length === 0) {
            return;
          }
          const nextValue = Number(rawValue);
          if (Number.isFinite(nextValue)) {
            onChange(nextValue);
          }
        }}
      />
    </label>
  );
}

function FillSwatches({
  value,
  onChange
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const fills = [
    { label: "Black fill", value: "#000000" },
    { label: "White fill", value: "#ffffff" }
  ];

  return (
    <div className="flex gap-2">
      {fills.map((fill) => (
        <Button
          key={fill.value}
          type="button"
          variant={value === fill.value ? "secondary" : "outline"}
          size="icon"
          className="size-8"
          title={fill.label}
          aria-label={fill.label}
          onClick={() => onChange(fill.value)}
        >
          <span
            aria-hidden="true"
            className="size-4 rounded-sm border border-border"
            style={{ backgroundColor: fill.value }}
          />
        </Button>
      ))}
    </div>
  );
}

function LayerList({
  document,
  selectedElementId,
  onSelect
}: {
  document: PrintDocument;
  selectedElementId: string | null;
  onSelect: (elementId: string | null) => void;
}) {
  const baseLayers = [
    {
      name: "Receipt artboard",
      detail: `${document.target.widthDots} x ${document.target.heightDots} dots`,
      icon: FileText
    },
    { name: "Protected tail margin", detail: "160 blank rows", icon: ShieldCheck }
  ];

  return (
    <>
      {baseLayers.map((layer) => {
        const Icon = layer.icon;
        return (
          <div key={layer.name} className="rounded-md border border-border bg-card p-2 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <Icon className="size-4 text-primary" aria-hidden="true" />
              {layer.name}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">{layer.detail}</div>
          </div>
        );
      })}
      {document.elements.map((element) => (
        <button
          key={element.id}
          type="button"
          className={`w-full rounded-md border p-2 text-left text-sm ${
            selectedElementId === element.id
              ? "border-primary bg-primary/5"
              : "border-border bg-card"
          }`}
          onClick={() => onSelect(element.id)}
        >
          <div className="flex items-center gap-2 font-medium">
            {element.type === "text" ? (
              <Type className="size-4 text-primary" aria-hidden="true" />
            ) : element.type === "rect" ? (
              <Square className="size-4 text-primary" aria-hidden="true" />
            ) : element.type === "image" ? (
              <ImageIcon className="size-4 text-primary" aria-hidden="true" />
            ) : element.type === "qr" ? (
              <QrCode className="size-4 text-primary" aria-hidden="true" />
            ) : (
              <Layers3 className="size-4 text-primary" aria-hidden="true" />
            )}
            {element.name}
          </div>
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {formatElementLayerDetail(element)}
          </div>
        </button>
      ))}
    </>
  );
}

function DocumentCanvas({
  document,
  selectedElementId,
  previewReady,
  totalBands,
  editingTextElementId,
  zoom,
  pan,
  onSelect,
  onMove,
  onTransform,
  onStartTextEdit,
  onCommitTextEdit,
  onCancelTextEdit
}: {
  document: PrintDocument;
  selectedElementId: string | null;
  previewReady: boolean;
  totalBands: number | null;
  editingTextElementId: string | null;
  zoom: number;
  pan: { x: number; y: number };
  onSelect: (elementId: string | null) => void;
  onMove: (elementId: string, x: number, y: number) => void;
  onTransform: (elementId: string, transform: ElementTransform) => void;
  onStartTextEdit: (elementId: string) => void;
  onCommitTextEdit: (elementId: string, text: string) => void;
  onCancelTextEdit: () => void;
}) {
  const selectedNodeRef = useRef<Konva.Node | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const canvasElements = document.elements.reduce<CanvasElement[]>((items, element) => {
    const textElement = textElementSchema.safeParse(element);
    if (textElement.success) {
      items.push({ kind: "text", element: textElement.data });
      return items;
    }

    const rectElement = rectElementSchema.safeParse(element);
    if (rectElement.success) {
      items.push({ kind: "rect", element: rectElement.data });
      return items;
    }

    const imageElement = imageElementSchema.safeParse(element);
    if (imageElement.success) {
      items.push({ kind: "image", element: imageElement.data });
      return items;
    }

    const qrElement = qrElementSchema.safeParse(element);
    if (qrElement.success) {
      items.push({ kind: "qr", element: qrElement.data });
      return items;
    }

    return items;
  }, []);
  const editingTextItem = canvasElements.find(
    (item) => item.kind === "text" && item.element.id === editingTextElementId
  );
  const editingTextElement = editingTextItem?.kind === "text" ? editingTextItem.element : null;
  const selectedCanvasElement = canvasElements.find(
    (item) => item.element.id === selectedElementId
  );
  const canTransformSelectedElement =
    Boolean(selectedCanvasElement) &&
    !selectedCanvasElement?.element.locked &&
    editingTextElementId !== selectedElementId;
  const stageWidth = Math.round(document.target.widthDots * zoom);
  const stageHeight = Math.round(document.target.heightDots * zoom);

  useEffect(() => {
    if (!transformerRef.current) {
      return;
    }
    transformerRef.current.nodes(
      canTransformSelectedElement && selectedNodeRef.current ? [selectedNodeRef.current] : []
    );
    transformerRef.current.getLayer()?.batchDraw();
  }, [canTransformSelectedElement, document.elements, selectedElementId]);

  const attachSelectedNode = useCallback((node: Konva.Node | null) => {
    selectedNodeRef.current = node;
  }, []);

  const transformSelectedElement = useCallback(
    (elementId: string) => {
      const node = selectedNodeRef.current;
      if (!node) {
        return;
      }
      const scaleX = node.scaleX();
      const scaleY = node.scaleY();
      const nextTransform = {
        x: node.x(),
        y: node.y(),
        width: node.width() * scaleX,
        height: node.height() * scaleY,
        rotation: node.rotation()
      };
      node.scaleX(1);
      node.scaleY(1);
      onTransform(elementId, nextTransform);
    },
    [onTransform]
  );

  return (
    <div
      className="receipt-artboard"
      aria-label="384 dot receipt artboard"
      style={{ width: stageWidth }}
    >
      <div className="border-b border-dashed border-safety/60 pb-3 text-center text-xs text-muted-foreground">
        {document.target.widthDots} dots
      </div>
      <div className="thermal-stage">
        <div
          className="relative"
          data-testid="canvas-pan-viewport"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px)`,
            transformOrigin: "top left"
          }}
        >
          <Stage width={stageWidth} height={stageHeight} scaleX={zoom} scaleY={zoom}>
            <Layer>
              <Rect
                x={0}
                y={0}
                width={document.target.widthDots}
                height={document.target.heightDots}
                fill={document.background.color}
              />
              {canvasElements.map((item) =>
                item.kind === "text" ? (
                  <CanvasTextElement
                    key={item.element.id}
                    element={item.element}
                    selected={selectedElementId === item.element.id}
                    onSelect={onSelect}
                    onMove={onMove}
                    onEdit={onStartTextEdit}
                    onTransformEnd={transformSelectedElement}
                    nodeRef={
                      canTransformSelectedElement && selectedElementId === item.element.id
                        ? attachSelectedNode
                        : undefined
                    }
                  />
                ) : item.kind === "rect" ? (
                  <CanvasRectElement
                    key={item.element.id}
                    element={item.element}
                    selected={selectedElementId === item.element.id}
                    onSelect={onSelect}
                    onMove={onMove}
                    onTransformEnd={transformSelectedElement}
                    nodeRef={
                      canTransformSelectedElement && selectedElementId === item.element.id
                        ? attachSelectedNode
                        : undefined
                    }
                  />
                ) : item.kind === "image" ? (
                  <CanvasImageElement
                    key={item.element.id}
                    element={item.element}
                    selected={selectedElementId === item.element.id}
                    onSelect={onSelect}
                    onMove={onMove}
                    onTransformEnd={transformSelectedElement}
                    nodeRef={
                      canTransformSelectedElement && selectedElementId === item.element.id
                        ? attachSelectedNode
                        : undefined
                    }
                  />
                ) : (
                  <CanvasQrElement
                    key={item.element.id}
                    element={item.element}
                    selected={selectedElementId === item.element.id}
                    onSelect={onSelect}
                    onMove={onMove}
                    onTransformEnd={transformSelectedElement}
                    nodeRef={
                      canTransformSelectedElement && selectedElementId === item.element.id
                        ? attachSelectedNode
                        : undefined
                    }
                  />
                )
              )}
              {canTransformSelectedElement ? (
                <Transformer
                  ref={transformerRef}
                  rotateEnabled
                  enabledAnchors={[
                    "top-left",
                    "top-center",
                    "top-right",
                    "middle-right",
                    "bottom-right",
                    "bottom-center",
                    "bottom-left",
                    "middle-left"
                  ]}
                  boundBoxFunc={(oldBox, newBox) =>
                    newBox.width < 8 || newBox.height < 8 ? oldBox : newBox
                  }
                />
              ) : null}
            </Layer>
          </Stage>
          {editingTextElement ? (
            <InlineTextEditor
              element={editingTextElement}
              zoom={zoom}
              onCommit={(text) => onCommitTextEdit(editingTextElement.id, text)}
              onCancel={onCancelTextEdit}
            />
          ) : null}
        </div>
        {document.elements.length === 0 ? (
          <div className="thermal-stage-empty">
            <Boxes className="mx-auto mb-3 size-9 text-muted-foreground" aria-hidden="true" />
            <div className="text-sm font-medium">Canvas editor bootstrap</div>
            <div className="mt-1 max-w-56 text-xs text-muted-foreground">
              {previewReady
                ? `${totalBands} print bands planned from approved preview.`
                : "Document model and canonical preview contracts are ready for the editor slice."}
            </div>
          </div>
        ) : null}
      </div>
      <div className="border-t border-dashed border-safety/60 pt-3 text-center text-xs text-safety">
        Protected tail margin
      </div>
    </div>
  );
}

function InlineTextEditor({
  element,
  zoom,
  onCommit,
  onCancel
}: {
  element: TextElement;
  zoom: number;
  onCommit: (text: string) => void;
  onCancel: () => void;
}) {
  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const [draft, setDraft] = useState(element.text);

  useEffect(() => {
    setDraft(element.text);
  }, [element.id, element.text]);

  useEffect(() => {
    editorRef.current?.focus();
    editorRef.current?.select();
  }, [element.id]);

  const finishEditing = useCallback(() => {
    if (draft === element.text) {
      onCancel();
      return;
    }
    onCommit(draft);
  }, [draft, element.text, onCancel, onCommit]);

  return (
    <textarea
      ref={editorRef}
      aria-label="Inline text"
      className="absolute z-10 resize-none rounded-sm border border-primary bg-background/95 p-1 text-sm text-foreground shadow-sm outline-none ring-2 ring-primary/20"
      value={draft}
      style={{
        left: element.x * zoom,
        top: element.y * zoom,
        width: element.width * zoom,
        minHeight: element.height * zoom,
        transform: `rotate(${element.rotation}deg)`,
        transformOrigin: "top left",
        fontFamily: element.style.fontFamily,
        fontSize: element.style.fontSize * zoom,
        fontWeight: element.style.fontWeight,
        lineHeight: element.style.lineHeight,
        color: element.style.fill,
        textAlign: element.style.align
      }}
      onChange={(event) => setDraft(event.currentTarget.value)}
      onBlur={finishEditing}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
          return;
        }
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          finishEditing();
        }
      }}
      onPointerDown={(event) => event.stopPropagation()}
    />
  );
}

function CanvasTextElement({
  element,
  selected,
  onSelect,
  onMove,
  onEdit,
  onTransformEnd,
  nodeRef
}: {
  element: TextElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
  onEdit: (elementId: string) => void;
  onTransformEnd: (elementId: string) => void;
  nodeRef?: ((node: Konva.Node | null) => void) | undefined;
}) {
  const selectionProps = selected ? { stroke: "#0f766e", strokeWidth: 1 } : {};

  return (
    <KonvaText
      ref={(node) => nodeRef?.(node)}
      id={element.id}
      x={element.x}
      y={element.y}
      width={element.width}
      height={element.height}
      rotation={element.rotation}
      text={element.text}
      fontFamily={element.style.fontFamily}
      fontSize={element.style.fontSize}
      fontStyle={String(element.style.fontWeight)}
      align={element.style.align}
      lineHeight={element.style.lineHeight}
      fill={element.style.fill}
      draggable={!element.locked}
      visible={element.visible}
      {...selectionProps}
      onClick={() => onSelect(element.id)}
      onTap={() => onSelect(element.id)}
      onDblClick={() => onEdit(element.id)}
      onDblTap={() => onEdit(element.id)}
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
      onTransformEnd={() => onTransformEnd(element.id)}
    />
  );
}

function CanvasRectElement({
  element,
  selected,
  onSelect,
  onMove,
  onTransformEnd,
  nodeRef
}: {
  element: RectElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
  onTransformEnd: (elementId: string) => void;
  nodeRef?: ((node: Konva.Node | null) => void) | undefined;
}) {
  const selectionProps = selected ? { stroke: "#0f766e", strokeWidth: 2 } : {};

  return (
    <Rect
      ref={(node) => nodeRef?.(node)}
      id={element.id}
      x={element.x}
      y={element.y}
      width={element.width}
      height={element.height}
      rotation={element.rotation}
      fill={element.fill}
      draggable={!element.locked}
      visible={element.visible}
      {...selectionProps}
      onClick={() => onSelect(element.id)}
      onTap={() => onSelect(element.id)}
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
      onTransformEnd={() => onTransformEnd(element.id)}
    />
  );
}

function CanvasImageElement({
  element,
  selected,
  onSelect,
  onMove,
  onTransformEnd,
  nodeRef
}: {
  element: ImageElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
  onTransformEnd: (elementId: string) => void;
  nodeRef?: ((node: Konva.Node | null) => void) | undefined;
}) {
  const image = useLoadedCanvasImage(element.source.dataUrl);
  const placement = image
    ? calculateImagePlacement({
        imageWidth: image.naturalWidth || image.width,
        imageHeight: image.naturalHeight || image.height,
        boxWidth: element.width,
        boxHeight: element.height,
        fit: element.fit
      })
    : null;

  return (
    <Group
      ref={(node) => nodeRef?.(node)}
      id={element.id}
      x={element.x}
      y={element.y}
      width={element.width}
      height={element.height}
      rotation={element.rotation}
      clipX={0}
      clipY={0}
      clipWidth={element.width}
      clipHeight={element.height}
      draggable={!element.locked}
      visible={element.visible}
      onClick={() => onSelect(element.id)}
      onTap={() => onSelect(element.id)}
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
      onTransformEnd={() => onTransformEnd(element.id)}
    >
      <Rect width={element.width} height={element.height} fill="#ffffff" />
      {image && placement ? (
        <KonvaImage
          image={image}
          x={placement.x}
          y={placement.y}
          width={placement.width}
          height={placement.height}
          listening={false}
        />
      ) : (
        <KonvaText
          width={element.width}
          height={element.height}
          align="center"
          verticalAlign="middle"
          text="Image"
          fill="#6b7280"
          fontSize={16}
          listening={false}
        />
      )}
      {selected ? (
        <Rect
          width={element.width}
          height={element.height}
          fill="transparent"
          stroke="#0f766e"
          strokeWidth={2}
          listening={false}
        />
      ) : null}
    </Group>
  );
}

function CanvasQrElement({
  element,
  selected,
  onSelect,
  onMove,
  onTransformEnd,
  nodeRef
}: {
  element: QrElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
  onTransformEnd: (elementId: string) => void;
  nodeRef?: ((node: Konva.Node | null) => void) | undefined;
}) {
  const matrix = useMemo(
    () => createQrMatrix(element.payload, element.errorCorrectionLevel),
    [element.errorCorrectionLevel, element.payload]
  );
  const availableSize = Math.max(1, Math.min(element.width, element.height));
  const moduleSize = Math.max(1, Math.floor(availableSize / matrix.size));
  const renderedSize = moduleSize * matrix.size;
  const offsetX = Math.max(0, Math.round((element.width - renderedSize) / 2));
  const offsetY = Math.max(0, Math.round((element.height - renderedSize) / 2));

  return (
    <Group
      ref={(node) => nodeRef?.(node)}
      id={element.id}
      x={element.x}
      y={element.y}
      width={element.width}
      height={element.height}
      rotation={element.rotation}
      draggable={!element.locked}
      visible={element.visible}
      onClick={() => onSelect(element.id)}
      onTap={() => onSelect(element.id)}
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
      onTransformEnd={() => onTransformEnd(element.id)}
    >
      <Rect width={element.width} height={element.height} fill="#ffffff" />
      {Array.from(matrix.data).map((active, index) => {
        if (!active) {
          return null;
        }
        const row = Math.floor(index / matrix.size);
        const column = index % matrix.size;
        return (
          <Rect
            key={`${row}-${column}`}
            x={offsetX + column * moduleSize}
            y={offsetY + row * moduleSize}
            width={moduleSize}
            height={moduleSize}
            fill="#000000"
            listening={false}
          />
        );
      })}
      {selected ? (
        <Rect
          width={element.width}
          height={element.height}
          fill="transparent"
          stroke="#0f766e"
          strokeWidth={2}
          listening={false}
        />
      ) : null}
    </Group>
  );
}

function PrinterPanel({
  workflow,
  hardwareArtifactWorkflow,
  onVerify,
  onExportHardwareArtifact
}: {
  workflow: PrinterWorkflow;
  hardwareArtifactWorkflow: HardwareArtifactWorkflow;
  onVerify: (deviceId: string, candidates: PrinterCandidate[]) => void;
  onExportHardwareArtifact: (deviceId: string) => void;
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
        hardwareArtifactWorkflow={hardwareArtifactWorkflow}
        onVerify={() => {
          if (primaryCandidate) {
            onVerify(primaryCandidate.deviceId, candidates);
          }
        }}
        onExportHardwareArtifact={() => {
          if (verification) {
            onExportHardwareArtifact(verification.deviceId);
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
  hardwareArtifactWorkflow,
  onVerify,
  onExportHardwareArtifact
}: {
  workflow: PrinterWorkflow;
  candidate: PrinterCandidate | undefined;
  verification: ReadOnlyVerification | null;
  hardwareArtifactWorkflow: HardwareArtifactWorkflow;
  onVerify: () => void;
  onExportHardwareArtifact: () => void;
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
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onExportHardwareArtifact}
            disabled={
              hardwareArtifactWorkflow.status === "running" &&
              hardwareArtifactWorkflow.deviceId === verification.deviceId
            }
          >
            <Download className="size-4" aria-hidden="true" />
            {hardwareArtifactWorkflow.status === "running" &&
            hardwareArtifactWorkflow.deviceId === verification.deviceId
              ? "Exporting artifact"
              : "Export read-only artifact"}
          </Button>
          {hardwareArtifactWorkflow.status === "exported" &&
          hardwareArtifactWorkflow.deviceId === verification.deviceId ? (
            <div className="rounded-md border border-success/30 bg-success/10 p-2 text-success">
              <div className="font-medium">Hardware artifact exported</div>
              <div className="text-xs">Ready for physical validation record</div>
            </div>
          ) : hardwareArtifactWorkflow.status === "error" &&
            hardwareArtifactWorkflow.deviceId === verification.deviceId ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-destructive">
              {hardwareArtifactWorkflow.message}
            </div>
          ) : null}
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

function useLoadedCanvasImage(dataUrl: string): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    let cancelled = false;
    const nextImage = new window.Image();
    nextImage.onload = () => {
      if (!cancelled) {
        setImage(nextImage);
      }
    };
    nextImage.onerror = () => {
      if (!cancelled) {
        setImage(null);
      }
    };
    nextImage.src = dataUrl;

    return () => {
      cancelled = true;
    };
  }, [dataUrl]);

  return image;
}

function calculateImagePlacement({
  imageWidth,
  imageHeight,
  boxWidth,
  boxHeight,
  fit
}: {
  imageWidth: number;
  imageHeight: number;
  boxWidth: number;
  boxHeight: number;
  fit: ImageElement["fit"];
}): { x: number; y: number; width: number; height: number } {
  if (fit === "stretch") {
    return { x: 0, y: 0, width: boxWidth, height: boxHeight };
  }

  const scale =
    fit === "cover"
      ? Math.max(boxWidth / imageWidth, boxHeight / imageHeight)
      : Math.min(boxWidth / imageWidth, boxHeight / imageHeight);
  const width = Math.max(1, Math.round(imageWidth * scale));
  const height = Math.max(1, Math.round(imageHeight * scale));
  return {
    x: Math.round((boxWidth - width) / 2),
    y: Math.round((boxHeight - height) / 2),
    width,
    height
  };
}

function formatElementLayerDetail(element: DocumentElement): string {
  if (element.type === "text" && typeof element.text === "string") {
    return element.text;
  }
  if (element.type === "rect") {
    return `${Math.round(element.width)} x ${Math.round(element.height)}`;
  }
  if (element.type === "image") {
    const imageElement = imageElementSchema.safeParse(element);
    return imageElement.success
      ? `${imageElement.data.source.mimeType} - ${imageElement.data.fit}`
      : "Embedded image";
  }
  if (element.type === "qr" && typeof element.payload === "string") {
    return element.payload;
  }
  return `${Math.round(element.x)}, ${Math.round(element.y)}`;
}

function formatBandCount(totalBands: number): string {
  return `${totalBands} ${totalBands === 1 ? "band" : "bands"}`;
}

function formatDiagnosticsJobCount(totalJobs: number): string {
  return `${totalJobs} ${totalJobs === 1 ? "job" : "jobs"} in bundle`;
}

function downloadBlob(blob: Blob, filename: string): void {
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
    return;
  }

  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

function createQrMatrix(
  payload: string,
  errorCorrectionLevel: QrElement["errorCorrectionLevel"]
): { size: number; data: Uint8Array } {
  const safePayload = payload.trim().length > 0 ? payload : " ";
  try {
    const qr = QRCode.create(safePayload, { errorCorrectionLevel });
    return {
      size: qr.modules.size,
      data: qr.modules.data
    };
  } catch {
    const fallbackQr = QRCode.create(" ", { errorCorrectionLevel: "M" });
    return {
      size: fallbackQr.modules.size,
      data: fallbackQr.modules.data
    };
  }
}

function projectSummaryFromResponse(project: ProjectResponse): ProjectSummary {
  const documentId = typeof project.document.id === "string" ? project.document.id : "";
  return {
    projectId: project.projectId,
    name: project.name,
    documentId,
    updatedAt: project.updatedAt
  };
}

function upsertProjectSummary(
  projects: ProjectSummary[],
  nextProject: ProjectSummary
): ProjectSummary[] {
  const remainingProjects = projects.filter(
    (project) => project.projectId !== nextProject.projectId
  );
  return [nextProject, ...remainingProjects];
}

function normalizeDotValue(value: number, minimum: number): number {
  return Math.max(minimum, Math.round(value));
}

function formatElementType(type: string): string {
  const labels: Record<string, string> = {
    text: "Text",
    image: "Image",
    rect: "Rectangle",
    line: "Line",
    path: "Path",
    qr: "QR",
    barcode: "Barcode",
    group: "Group"
  };
  return labels[type] ?? type;
}

function formatZoom(zoom: number): string {
  return `Zoom ${Math.round(zoom * 100)}%`;
}

function formatPaperMode(mode: string): string {
  const labels: Record<string, string> = {
    continuous: "continuous paper",
    gap_label: "gap label",
    black_mark: "black mark"
  };
  return labels[mode] ?? mode;
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
