import { z } from "zod";

export const elementBaseSchema = z.object({
  id: z.string(),
  type: z.enum(["text", "image", "rect", "line", "path", "qr", "barcode", "group"]),
  name: z.string(),
  x: z.number(),
  y: z.number(),
  width: z.number().nonnegative(),
  height: z.number().nonnegative(),
  rotation: z.number(),
  locked: z.boolean(),
  visible: z.boolean()
});

export const textStyleSchema = z.object({
  fontFamily: z.string(),
  fontSize: z.number().positive(),
  fontWeight: z.number().int().positive(),
  align: z.enum(["left", "center", "right"]),
  lineHeight: z.number().positive(),
  fill: z.string()
});

export const textElementSchema = elementBaseSchema.extend({
  type: z.literal("text"),
  text: z.string(),
  style: textStyleSchema
});

export const rectElementSchema = elementBaseSchema.extend({
  type: z.literal("rect"),
  fill: z.string()
});

export const imageFitSchema = z.enum(["contain", "cover", "stretch"]);

export const projectImageAssetRefSchema = z.object({
  kind: z.literal("daemon_project_asset"),
  projectId: z.string(),
  assetId: z.string(),
  sha256: z.string(),
  fileName: z.string(),
  mimeType: z.enum(["image/png", "image/jpeg", "image/webp"]),
  byteLength: z.number().int().nonnegative()
});

export const embeddedImageSourceSchema = z.object({
  kind: z.literal("embedded_data_url"),
  dataUrl: z.string().startsWith("data:image/"),
  mimeType: z.string().startsWith("image/"),
  projectAsset: projectImageAssetRefSchema.optional()
});

export const imageProcessingSchema = z.object({
  threshold: z.number().int().min(0).max(255),
  invert: z.boolean()
});

export const imageElementSchema = elementBaseSchema.extend({
  type: z.literal("image"),
  source: embeddedImageSourceSchema,
  fit: imageFitSchema,
  processing: imageProcessingSchema
});

export const qrErrorCorrectionLevelSchema = z.enum(["L", "M", "Q", "H"]);

export const qrElementSchema = elementBaseSchema.extend({
  type: z.literal("qr"),
  payload: z.string(),
  errorCorrectionLevel: qrErrorCorrectionLevelSchema
});

export const printDocumentSchema = z.object({
  schemaVersion: z.literal(1),
  id: z.string(),
  title: z.string().min(1),
  createdAt: z.string(),
  updatedAt: z.string(),
  target: z.object({
    profileId: z.literal("seznik-minix-s1-lyin48d-gy"),
    widthDots: z.literal(384),
    heightDots: z.number().int().positive(),
    dpi: z.number().int().positive(),
    paperMode: z.enum(["continuous", "gap_label", "black_mark"]),
    density: z.enum(["light", "medium", "dark"])
  }),
  background: z.object({
    color: z.string()
  }),
  elements: z.array(elementBaseSchema.passthrough()),
  assets: z.array(z.unknown()),
  metadata: z.record(z.unknown())
});

export type PrintDocument = z.infer<typeof printDocumentSchema>;
export type TextElement = z.infer<typeof textElementSchema>;
export type RectElement = z.infer<typeof rectElementSchema>;
export type ImageElement = z.infer<typeof imageElementSchema>;
export type QrElement = z.infer<typeof qrElementSchema>;
export type ProjectImageAssetRef = z.infer<typeof projectImageAssetRefSchema>;

export type DefaultDocumentOptions = {
  title?: string;
  heightDots?: number;
  now?: Date;
};

export type CreateTextElementOptions = {
  id?: string;
  name: string;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CreateRectElementOptions = {
  id?: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fill?: string;
};

export type CreateImageElementOptions = {
  id?: string;
  name: string;
  dataUrl: string;
  mimeType: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fit?: ImageElement["fit"];
  threshold?: number;
  invert?: boolean;
  projectAsset?: ProjectImageAssetRef;
};

export type CreateQrElementOptions = {
  id?: string;
  name: string;
  payload: string;
  x: number;
  y: number;
  size: number;
  errorCorrectionLevel?: QrElement["errorCorrectionLevel"];
};

export type InsertLongPrintTestMarkersOptions = {
  heightDots?: number;
  now?: Date;
};

export const LONG_PRINT_TEST_DEFAULT_HEIGHT_DOTS = 8000;
export const LONG_PRINT_TEST_CHECKSUM = "7F3A";

export function createDefaultDocument(options: DefaultDocumentOptions = {}): PrintDocument {
  const now = (options.now ?? new Date()).toISOString();

  return {
    schemaVersion: 1,
    id: `doc_${crypto.randomUUID()}`,
    title: options.title ?? "Untitled print",
    createdAt: now,
    updatedAt: now,
    target: {
      profileId: "seznik-minix-s1-lyin48d-gy",
      widthDots: 384,
      heightDots: options.heightDots ?? 900,
      dpi: 203,
      paperMode: "continuous",
      density: "medium"
    },
    background: {
      color: "#ffffff"
    },
    elements: [],
    assets: [],
    metadata: {}
  };
}

export function createTextElement(options: CreateTextElementOptions): TextElement {
  return {
    id: options.id ?? `el_${crypto.randomUUID()}`,
    type: "text",
    name: options.name,
    x: options.x,
    y: options.y,
    width: options.width,
    height: options.height,
    rotation: 0,
    locked: false,
    visible: true,
    text: options.text,
    style: {
      fontFamily: "Inter",
      fontSize: 28,
      fontWeight: 700,
      align: "center",
      lineHeight: 1.1,
      fill: "#000000"
    }
  };
}

export function createRectElement(options: CreateRectElementOptions): RectElement {
  return {
    id: options.id ?? `el_${crypto.randomUUID()}`,
    type: "rect",
    name: options.name,
    x: options.x,
    y: options.y,
    width: options.width,
    height: options.height,
    rotation: 0,
    locked: false,
    visible: true,
    fill: options.fill ?? "#000000"
  };
}

export function createImageElement(options: CreateImageElementOptions): ImageElement {
  return {
    id: options.id ?? `el_${crypto.randomUUID()}`,
    type: "image",
    name: options.name,
    x: options.x,
    y: options.y,
    width: options.width,
    height: options.height,
    rotation: 0,
    locked: false,
    visible: true,
    source: {
      kind: "embedded_data_url",
      dataUrl: options.dataUrl,
      mimeType: options.mimeType,
      ...(options.projectAsset ? { projectAsset: options.projectAsset } : {})
    },
    fit: options.fit ?? "contain",
    processing: {
      threshold: options.threshold ?? 128,
      invert: options.invert ?? false
    }
  };
}

export function createQrElement(options: CreateQrElementOptions): QrElement {
  return {
    id: options.id ?? `el_${crypto.randomUUID()}`,
    type: "qr",
    name: options.name,
    x: options.x,
    y: options.y,
    width: options.size,
    height: options.size,
    rotation: 0,
    locked: false,
    visible: true,
    payload: options.payload,
    errorCorrectionLevel: options.errorCorrectionLevel ?? "M"
  };
}

export function appendElement(
  document: PrintDocument,
  element: PrintDocument["elements"][number],
  options: { now?: Date } = {}
): PrintDocument {
  return {
    ...document,
    updatedAt: (options.now ?? new Date()).toISOString(),
    elements: [...document.elements, element]
  };
}

export function moveElement(
  document: PrintDocument,
  elementId: string,
  options: { x: number; y: number; now?: Date }
): PrintDocument {
  return {
    ...document,
    updatedAt: (options.now ?? new Date()).toISOString(),
    elements: document.elements.map((element) =>
      element.id === elementId ? { ...element, x: options.x, y: options.y } : element
    )
  };
}

export function updateElement(
  document: PrintDocument,
  elementId: string,
  updater: (
    element: PrintDocument["elements"][number]
  ) => PrintDocument["elements"][number],
  options: { now?: Date } = {}
): PrintDocument {
  return {
    ...document,
    updatedAt: (options.now ?? new Date()).toISOString(),
    elements: document.elements.map((element) =>
      element.id === elementId ? updater(element) : element
    )
  };
}

export function insertLongPrintTestMarkers(
  document: PrintDocument,
  options: InsertLongPrintTestMarkersOptions = {}
): PrintDocument {
  const heightDots = Math.max(
    document.target.heightDots,
    options.heightDots ?? LONG_PRINT_TEST_DEFAULT_HEIGHT_DOTS
  );
  const markerRows = [
    { suffix: "start", text: "START LP-TEST job_fixture", y: 24 },
    { suffix: "25", text: "25% marker", y: Math.round(heightDots * 0.25) },
    { suffix: "50", text: "50% marker", y: Math.round(heightDots * 0.5) },
    { suffix: "75", text: "75% marker", y: Math.round(heightDots * 0.75) },
    {
      suffix: "end",
      text: `END LP-TEST checksum: ${LONG_PRINT_TEST_CHECKSUM}`,
      y: Math.max(24, heightDots - 96)
    }
  ];
  const markerElements = markerRows.flatMap(({ suffix, text, y }) => {
    const marker = createTextElement({
      id: `lp_test_marker_${suffix}`,
      name: `LP marker ${suffix}`,
      text,
      x: 24,
      y,
      width: document.target.widthDots - 48,
      height: 32
    });
    const rule = createRectElement({
      id: `lp_test_rule_${suffix}`,
      name: `LP rule ${suffix}`,
      x: 24,
      y: y + 36,
      width: document.target.widthDots - 48,
      height: 2
    });
    return [
      {
        ...marker,
        style: {
          ...marker.style,
          fontSize: 18,
          align: "left" as const,
          lineHeight: 1
        }
      },
      rule
    ];
  });

  return {
    ...document,
    updatedAt: (options.now ?? new Date()).toISOString(),
    target: {
      ...document.target,
      heightDots
    },
    elements: [
      ...document.elements.filter((element) => !element.id.startsWith("lp_test_")),
      ...markerElements
    ],
    metadata: {
      ...document.metadata,
      longPrintTest: {
        version: 1,
        heightDots,
        checksum: LONG_PRINT_TEST_CHECKSUM,
        markerRows: markerRows.map((marker) => marker.y)
      }
    }
  };
}
