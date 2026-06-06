import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { rendererManualChunks } from "./buildChunks";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@minix/shared-api": path.resolve(__dirname, "../../packages/shared-api/src/index.ts"),
      "@minix/design-model": path.resolve(__dirname, "../../packages/design-model/src/index.ts")
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: rendererManualChunks
      }
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.tsx", "tests/**/*.test.ts"]
  }
});
