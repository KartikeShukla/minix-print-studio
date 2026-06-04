import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

type MockKonvaState = {
  height: number;
  rotation: number;
  scaleX: number;
  scaleY: number;
  width: number;
  x: number;
  y: number;
  nodes: MockKonvaNode[];
};

type MockKonvaNode = {
  getLayer: () => { batchDraw: () => void };
  height: (value?: number) => number;
  nodes: (value?: MockKonvaNode[]) => MockKonvaNode[];
  rotation: (value?: number) => number;
  scaleX: (value?: number) => number;
  scaleY: (value?: number) => number;
  width: (value?: number) => number;
  x: (value?: number) => number;
  y: (value?: number) => number;
};

type MockKonvaProps = {
  children?: React.ReactNode;
  enabledAnchors?: string[];
  height?: number;
  id?: string;
  rotation?: number;
  rotateEnabled?: boolean;
  scaleX?: number;
  scaleY?: number;
  text?: string;
  width?: number;
  x?: number;
  y?: number;
  onClick?: () => void;
  onTap?: () => void;
  onDblClick?: () => void;
  onDblTap?: () => void;
  onTransformEnd?: (event: { target: MockKonvaNode }) => void;
};

vi.mock("react-konva", async () => {
  const React = await import("react");

  function node(name: string) {
    return React.forwardRef<MockKonvaNode, MockKonvaProps>(function MockKonvaNode({
      children,
      enabledAnchors,
      height,
      id,
      rotation,
      rotateEnabled,
      scaleX,
      scaleY,
      text,
      width,
      x,
      y,
      onClick,
      onTap,
      onDblClick,
      onDblTap,
      onTransformEnd
    }: MockKonvaProps, ref) {
      const elementRef = React.useRef<HTMLDivElement | null>(null);
      const stateRef = React.useRef<MockKonvaState>({
        height: height ?? 0,
        rotation: rotation ?? 0,
        scaleX: scaleX ?? 1,
        scaleY: scaleY ?? 1,
        width: width ?? 0,
        x: x ?? 0,
        y: y ?? 0,
        nodes: []
      });
      stateRef.current = {
        ...stateRef.current,
        height: height ?? stateRef.current.height,
        rotation: rotation ?? stateRef.current.rotation,
        scaleX: scaleX ?? stateRef.current.scaleX,
        scaleY: scaleY ?? stateRef.current.scaleY,
        width: width ?? stateRef.current.width,
        x: x ?? stateRef.current.x,
        y: y ?? stateRef.current.y
      };
      const konvaNode = React.useMemo<MockKonvaNode>(
        () => ({
          getLayer: () => ({ batchDraw: vi.fn() }),
          height: (value?: number) => readWriteNodeValue(stateRef.current, "height", value),
          nodes: (value?: MockKonvaNode[]) => {
            if (value) {
              stateRef.current.nodes = value;
            }
            return stateRef.current.nodes;
          },
          rotation: (value?: number) => readWriteNodeValue(stateRef.current, "rotation", value),
          scaleX: (value?: number) => readWriteNodeValue(stateRef.current, "scaleX", value),
          scaleY: (value?: number) => readWriteNodeValue(stateRef.current, "scaleY", value),
          width: (value?: number) => readWriteNodeValue(stateRef.current, "width", value),
          x: (value?: number) => readWriteNodeValue(stateRef.current, "x", value),
          y: (value?: number) => readWriteNodeValue(stateRef.current, "y", value)
        }),
        []
      );
      React.useImperativeHandle(ref, () => konvaNode, [konvaNode]);
      React.useEffect(() => {
        const element = elementRef.current;
        if (!element || !onTransformEnd) {
          return;
        }
        const handleTransformEnd = (event: Event) => {
          const detail = (event as CustomEvent<Partial<MockKonvaState>>).detail ?? {};
          stateRef.current = { ...stateRef.current, ...detail };
          onTransformEnd({ target: konvaNode });
        };
        element.addEventListener("konva-transform-end", handleTransformEnd);
        return () => element.removeEventListener("konva-transform-end", handleTransformEnd);
      }, [konvaNode, onTransformEnd]);

      return React.createElement(
        "div",
        {
          ref: elementRef,
          "data-enabled-anchors": enabledAnchors?.join(","),
          "data-konva-node": name,
          "data-testid": id,
          "data-height": height,
          "data-rotate-enabled": rotateEnabled,
          "data-rotation": rotation,
          "data-scale-x": scaleX,
          "data-scale-y": scaleY,
          "data-width": width,
          "data-x": x,
          "data-y": y,
          onClick: onClick ?? onTap,
          onDoubleClick: onDblClick ?? onDblTap
        },
        text ?? children
      );
    });
  }

  function readWriteNodeValue(
    state: MockKonvaState,
    key: Exclude<keyof MockKonvaState, "nodes">,
    value?: number
  ): number {
    if (typeof value === "number") {
      state[key] = value;
    }
    return state[key];
  }

  return {
    Stage: node("Stage"),
    Layer: node("Layer"),
    Group: node("Group"),
    Image: node("Image"),
    Rect: node("Rect"),
    Text: node("Text"),
    Transformer: node("Transformer")
  };
});
