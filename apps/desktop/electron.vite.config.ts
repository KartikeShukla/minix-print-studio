import path from "node:path";
import { defineConfig, externalizeDepsPlugin } from "electron-vite";

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()]
  },
  preload: {
    plugins: [externalizeDepsPlugin()]
  },
  renderer: {
    root: path.resolve(__dirname, "../renderer"),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "../renderer/src"),
        "@minix/shared-api": path.resolve(__dirname, "../../packages/shared-api/src/index.ts"),
        "@minix/design-model": path.resolve(__dirname, "../../packages/design-model/src/index.ts")
      }
    },
    build: {
      rollupOptions: {
        input: path.resolve(__dirname, "../renderer/index.html")
      }
    }
  }
});
