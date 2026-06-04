import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

type MockKonvaProps = {
  children?: React.ReactNode;
  id?: string;
  text?: string;
  onClick?: () => void;
  onTap?: () => void;
  onDblClick?: () => void;
  onDblTap?: () => void;
};

vi.mock("react-konva", async () => {
  const React = await import("react");

  function node(name: string) {
    return function MockKonvaNode({
      children,
      id,
      text,
      onClick,
      onTap,
      onDblClick,
      onDblTap
    }: MockKonvaProps) {
      return React.createElement(
        "div",
        {
          "data-konva-node": name,
          "data-testid": id,
          onClick: onClick ?? onTap,
          onDoubleClick: onDblClick ?? onDblTap
        },
        text ?? children
      );
    };
  }

  return {
    Stage: node("Stage"),
    Layer: node("Layer"),
    Group: node("Group"),
    Image: node("Image"),
    Rect: node("Rect"),
    Text: node("Text")
  };
});
