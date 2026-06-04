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

export type DefaultDocumentOptions = {
  title?: string;
  heightDots?: number;
  now?: Date;
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
