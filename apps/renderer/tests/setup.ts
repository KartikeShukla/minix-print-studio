import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

type MockKonvaProps = {
  children?: React.ReactNode;
  id?: string;
  text?: string;
  onClick?: () => void;
  onTap?: () => void;
};

vi.mock("react-konva", async () => {
  const React = await import("react");

  function node(name: string) {
    return function MockKonvaNode({ children, id, text, onClick, onTap }: MockKonvaProps) {
      return React.createElement(
        "div",
        {
          "data-konva-node": name,
          "data-testid": id,
          onClick: onClick ?? onTap
        },
        text ?? children
      );
    };
  }

  return {
    Stage: node("Stage"),
    Layer: node("Layer"),
    Group: node("Group"),
    Rect: node("Rect"),
    Text: node("Text")
  };
});
