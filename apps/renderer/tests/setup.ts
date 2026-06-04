import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

type MockKonvaProps = {
  children?: React.ReactNode;
  height?: number;
  id?: string;
  scaleX?: number;
  scaleY?: number;
  text?: string;
  width?: number;
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
      height,
      id,
      scaleX,
      scaleY,
      text,
      width,
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
          "data-height": height,
          "data-scale-x": scaleX,
          "data-scale-y": scaleY,
          "data-width": width,
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
