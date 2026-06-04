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
