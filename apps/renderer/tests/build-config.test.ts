// @vitest-environment node

import { describe, expect, it } from "vitest";
import rendererConfig from "../vite.config";

describe("renderer build config", () => {
  it("splits heavyweight runtime and editor dependencies into stable chunks", () => {
    const manualChunks = getManualChunks(rendererConfig);

    expect(manualChunks("/repo/node_modules/react/index.js")).toBe("react-vendor");
    expect(manualChunks("/repo/node_modules/react-dom/client.js")).toBe("react-vendor");
    expect(manualChunks("/repo/node_modules/konva/lib/index.js")).toBe("editor-vendor");
    expect(manualChunks("/repo/node_modules/react-konva/lib/ReactKonva.js")).toBe(
      "editor-vendor"
    );
    expect(manualChunks("/repo/node_modules/qrcode/lib/browser.js")).toBe("editor-vendor");
    expect(manualChunks("/repo/node_modules/@radix-ui/react-slot/dist/index.mjs")).toBe(
      "ui-vendor"
    );
    expect(manualChunks("/repo/apps/renderer/src/app/App.tsx")).toBeUndefined();
  });
});

function getManualChunks(config: unknown): (id: string) => string | undefined {
  const output = (config as { build?: { rollupOptions?: { output?: BuildOutput } } }).build
    ?.rollupOptions?.output;
  expect(output).toBeDefined();
  expect(Array.isArray(output)).toBe(false);

  const manualChunks = output?.manualChunks;
  expect(typeof manualChunks).toBe("function");
  return manualChunks as (id: string) => string | undefined;
}

type BuildOutput = {
  manualChunks?: unknown;
};
