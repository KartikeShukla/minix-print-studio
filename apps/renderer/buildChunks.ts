const REACT_VENDOR_MODULES = [
  "/node_modules/react/",
  "/node_modules/react-dom/",
  "/node_modules/scheduler/"
];

const EDITOR_VENDOR_MODULES = [
  "/node_modules/konva/",
  "/node_modules/react-konva/",
  "/node_modules/qrcode/"
];

const UI_VENDOR_MODULES = [
  "/node_modules/@radix-ui/",
  "/node_modules/lucide-react/",
  "/node_modules/class-variance-authority/",
  "/node_modules/clsx/",
  "/node_modules/tailwind-merge/"
];

export function rendererManualChunks(id: string): string | undefined {
  const normalizedId = id.replace(/\\/g, "/");
  if (REACT_VENDOR_MODULES.some((modulePath) => normalizedId.includes(modulePath))) {
    return "react-vendor";
  }
  if (EDITOR_VENDOR_MODULES.some((modulePath) => normalizedId.includes(modulePath))) {
    return "editor-vendor";
  }
  if (UI_VENDOR_MODULES.some((modulePath) => normalizedId.includes(modulePath))) {
    return "ui-vendor";
  }
  return undefined;
}
