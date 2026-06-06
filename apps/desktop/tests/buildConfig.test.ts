import { describe, expect, it } from "vitest";
import desktopConfig from "../electron.vite.config";

describe("desktop renderer build config", () => {
  it("uses the shared renderer chunk split for packaged desktop builds", () => {
    const manualChunks = getRendererManualChunks(desktopConfig);

    expect(manualChunks("/repo/node_modules/react/index.js")).toBe("react-vendor");
    expect(manualChunks("/repo/node_modules/konva/lib/index.js")).toBe("editor-vendor");
    expect(manualChunks("/repo/node_modules/lucide-react/dist/esm/icons/printer.js")).toBe(
      "ui-vendor"
    );
    expect(manualChunks("/repo/apps/renderer/src/main.tsx")).toBeUndefined();
  });
});

function getRendererManualChunks(config: unknown): (id: string) => string | undefined {
  const output = (
    config as {
      renderer?: { build?: { rollupOptions?: { output?: BuildOutput } } };
    }
  ).renderer?.build?.rollupOptions?.output;
  expect(output).toBeDefined();
  expect(Array.isArray(output)).toBe(false);

  const manualChunks = output?.manualChunks;
  expect(typeof manualChunks).toBe("function");
  return manualChunks as (id: string) => string | undefined;
}

type BuildOutput = {
  manualChunks?: unknown;
};
