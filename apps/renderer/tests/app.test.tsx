import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/app/App";

describe("MiniX Print Studio shell", () => {
  it("shows the workspace and daemon health from the local API", async () => {
    render(
      <App
        daemonClient={{
          getHealth: async () => ({
            ok: true,
            version: "0.1.0",
            profileRegistryVersion: "2026.06.04",
            mock: true
          })
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "MiniX Print Studio" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan printers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print" })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByText("Mock daemon online")).toBeInTheDocument();
    });
  });
});
