import { useEffect, useMemo, useState } from "react";
import {
  Bluetooth,
  Boxes,
  CircleAlert,
  FileText,
  Image,
  Layers3,
  MousePointer2,
  Printer,
  QrCode,
  ScanSearch,
  ShieldCheck,
  Square,
  Type,
  Wifi
} from "lucide-react";
import type { HealthResponse } from "@minix/shared-api";
import { createDaemonClient, type DaemonClient } from "@/lib/api-client";
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

const layers = [
  { name: "Receipt artboard", detail: "384 x 900 dots", icon: FileText },
  { name: "Protected tail margin", detail: "160 blank rows", icon: ShieldCheck }
];

export function App({ daemonClient }: AppProps) {
  const client = useMemo(() => daemonClient ?? createDaemonClient(), [daemonClient]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

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

  const statusLabel = health
    ? health.mock
      ? "Mock daemon online"
      : "Daemon online"
    : healthError
      ? "Daemon offline"
      : "Checking daemon";

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
                Untitled print - continuous paper
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant={health ? "success" : healthError ? "destructive" : "muted"}>
              <Wifi className="size-3.5" aria-hidden="true" />
              {statusLabel}
            </Badge>
            <Button variant="outline" size="sm">
              <ScanSearch className="size-4" aria-hidden="true" />
              Scan printers
            </Button>
            <Button variant="outline" size="sm">
              Preview
            </Button>
            <Button size="sm" disabled>
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
                {layers.map((layer) => {
                  const Icon = layer.icon;
                  return (
                    <div
                      key={layer.name}
                      className="rounded-md border border-border bg-card p-2 text-sm"
                    >
                      <div className="flex items-center gap-2 font-medium">
                        <Icon className="size-4 text-primary" aria-hidden="true" />
                        {layer.name}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{layer.detail}</div>
                    </div>
                  );
                })}
              </div>
            </section>
          </aside>

          <section className="min-h-0 overflow-auto bg-workspace p-6">
            <div className="mx-auto flex min-h-full w-full max-w-4xl items-start justify-center">
              <div className="receipt-artboard" aria-label="384 dot receipt artboard">
                <div className="border-b border-dashed border-safety/60 pb-3 text-center text-xs text-muted-foreground">
                  384 dots
                </div>
                <div className="flex flex-1 items-center justify-center text-center">
                  <div>
                    <Boxes className="mx-auto mb-3 size-9 text-muted-foreground" aria-hidden="true" />
                    <div className="text-sm font-medium">Canvas editor bootstrap</div>
                    <div className="mt-1 max-w-56 text-xs text-muted-foreground">
                      Document model and canonical preview contracts are ready for the editor slice.
                    </div>
                  </div>
                </div>
                <div className="border-t border-dashed border-safety/60 pt-3 text-center text-xs text-safety">
                  Protected tail margin
                </div>
              </div>
            </div>
          </section>

          <aside className="min-h-0 border-l border-border bg-card">
            <section className="border-b border-border p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Printer</h2>
                <Badge variant="muted">
                  <Bluetooth className="size-3.5" aria-hidden="true" />
                  Untrusted
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
            </section>

            <section className="border-b border-border p-4">
              <div className="mb-3 flex items-center gap-2">
                <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Safety</h2>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Coverage</span>
                  <span>0%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Agent direct print</span>
                  <span>Off</span>
                </div>
              </div>
            </section>

            <section className="p-4">
              <div className="mb-3 flex items-center gap-2">
                <CircleAlert className="size-4 text-warning" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Preview Binding</h2>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                Printing will require a daemon-generated preview hash before physical output.
              </p>
            </section>
          </aside>
        </main>

        <footer className="flex items-center justify-between border-t border-border bg-card px-4 text-xs text-muted-foreground">
          <span>Zoom 100%</span>
          <span>{health ? `Daemon ${health.version}` : "No daemon health yet"}</span>
          <span>Queue idle</span>
        </footer>
      </div>
    </div>
  );
}
