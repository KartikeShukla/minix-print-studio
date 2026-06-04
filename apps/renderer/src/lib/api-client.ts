import { healthResponseSchema, type HealthResponse } from "@minix/shared-api";

export type DaemonRuntime = {
  baseUrl: string;
  token: string;
};

export type DaemonClient = {
  getHealth: () => Promise<HealthResponse>;
};

declare global {
  interface Window {
    minix?: {
      getDaemonRuntime: () => Promise<DaemonRuntime>;
      getAppVersion: () => Promise<string>;
    };
  }
}

export function createDaemonClient(): DaemonClient {
  return {
    async getHealth() {
      const runtime = await getRuntime();
      const response = await fetch(`${runtime.baseUrl}/v1/health`, {
        headers: {
          Authorization: `Bearer ${runtime.token}`
        }
      });

      if (!response.ok) {
        throw new Error(`Daemon health failed with ${response.status}`);
      }

      return healthResponseSchema.parse(await response.json());
    }
  };
}

async function getRuntime(): Promise<DaemonRuntime> {
  if (window.minix) {
    return window.minix.getDaemonRuntime();
  }

  return {
    baseUrl: "http://127.0.0.1:39281",
    token: "dev-token"
  };
}
