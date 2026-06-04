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
  Redo2,
  ScanSearch,
  ShieldCheck,
  Square,
  Type,
  Undo2,
  Wifi
} from "lucide-react";
import {
  appendElement,
  createDefaultDocument,
  createQrElement,
  createRectElement,
  createTextElement,
  moveElement,
  qrElementSchema,
  rectElementSchema,
  textElementSchema,
  updateElement,
  type PrintDocument,
  type QrElement,
  type RectElement,
  type TextElement
} from "@minix/design-model";
import * as QRCode from "qrcode";
import { Group, Layer, Rect, Stage, Text as KonvaText } from "react-konva";
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
import { loadStoredDocument, saveStoredDocument } from "@/lib/document-storage";
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

type CanvasElement =
  | { kind: "text"; element: TextElement }
  | { kind: "rect"; element: RectElement }
  | { kind: "qr"; element: QrElement };

export function App({ daemonClient }: AppProps) {
  const client = useMemo(() => daemonClient ?? createDaemonClient(), [daemonClient]);
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
  const [printerWorkflow, setPrinterWorkflow] = useState<PrinterWorkflow>({ status: "idle" });
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

  const undoDocumentChange = useCallback(() => {
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
  const canUndo = past.length > 0;
  const canRedo = future.length > 0;
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
                onSelect={selectElement}
                onMove={moveDocumentElement}
              />
            </div>
          </section>

          <aside className="min-h-0 overflow-auto border-l border-border bg-card">
            <PrinterPanel workflow={printerWorkflow} onVerify={runReadOnlyVerify} />
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

function ElementInspector({
  element,
  onUpdate
}: {
  element: DocumentElement | null;
  onUpdate: (elementId: string, updater: ElementUpdater) => void;
}) {
  const textElement = element ? textElementSchema.safeParse(element) : null;
  const rectElement = element ? rectElementSchema.safeParse(element) : null;
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
  onChange
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-xs font-medium text-muted-foreground" htmlFor={id}>
      {label}
      <input
        id={id}
        type="number"
        min={min}
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
            ) : element.type === "qr" ? (
              <QrCode className="size-4 text-primary" aria-hidden="true" />
            ) : (
              <Layers3 className="size-4 text-primary" aria-hidden="true" />
            )}
            {element.name}
          </div>
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {element.type === "text" && typeof element.text === "string"
              ? element.text
              : element.type === "rect"
                ? `${Math.round(element.width)} x ${Math.round(element.height)}`
              : element.type === "qr" && typeof element.payload === "string"
                ? element.payload
              : `${Math.round(element.x)}, ${Math.round(element.y)}`}
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
  onSelect,
  onMove
}: {
  document: PrintDocument;
  selectedElementId: string | null;
  previewReady: boolean;
  totalBands: number | null;
  onSelect: (elementId: string | null) => void;
  onMove: (elementId: string, x: number, y: number) => void;
}) {
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

    const qrElement = qrElementSchema.safeParse(element);
    if (qrElement.success) {
      items.push({ kind: "qr", element: qrElement.data });
      return items;
    }

    return items;
  }, []);

  return (
    <div className="receipt-artboard" aria-label="384 dot receipt artboard">
      <div className="border-b border-dashed border-safety/60 pb-3 text-center text-xs text-muted-foreground">
        {document.target.widthDots} dots
      </div>
      <div className="thermal-stage">
        <Stage width={document.target.widthDots} height={document.target.heightDots}>
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
                />
              ) : item.kind === "rect" ? (
                <CanvasRectElement
                  key={item.element.id}
                  element={item.element}
                  selected={selectedElementId === item.element.id}
                  onSelect={onSelect}
                  onMove={onMove}
                />
              ) : (
                <CanvasQrElement
                  key={item.element.id}
                  element={item.element}
                  selected={selectedElementId === item.element.id}
                  onSelect={onSelect}
                  onMove={onMove}
                />
              )
            )}
          </Layer>
        </Stage>
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

function CanvasTextElement({
  element,
  selected,
  onSelect,
  onMove
}: {
  element: TextElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
}) {
  const selectionProps = selected ? { stroke: "#0f766e", strokeWidth: 1 } : {};

  return (
    <KonvaText
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
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
    />
  );
}

function CanvasRectElement({
  element,
  selected,
  onSelect,
  onMove
}: {
  element: RectElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
}) {
  const selectionProps = selected ? { stroke: "#0f766e", strokeWidth: 2 } : {};

  return (
    <Rect
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
    />
  );
}

function CanvasQrElement({
  element,
  selected,
  onSelect,
  onMove
}: {
  element: QrElement;
  selected: boolean;
  onSelect: (elementId: string) => void;
  onMove: (elementId: string, x: number, y: number) => void;
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
      id={element.id}
      x={element.x}
      y={element.y}
      rotation={element.rotation}
      draggable={!element.locked}
      visible={element.visible}
      onClick={() => onSelect(element.id)}
      onTap={() => onSelect(element.id)}
      onDragEnd={(event) => {
        onMove(element.id, event.target.x(), event.target.y());
      }}
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
