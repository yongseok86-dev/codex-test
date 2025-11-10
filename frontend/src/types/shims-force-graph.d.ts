declare module '3d-force-graph' {
  type ThreeObject = import('three').Object3D
  type ForceGraph3DInstance = {
    graphData: (data: any) => ForceGraph3DInstance
    backgroundColor: (color: string) => ForceGraph3DInstance
    nodeLabel: (fn: (node: any) => string) => ForceGraph3DInstance
    nodeColor: (fn: (node: any) => string) => ForceGraph3DInstance
    nodeVal: (fn: (node: any) => number) => ForceGraph3DInstance
    nodeRelSize: (size: number) => ForceGraph3DInstance
    nodeThreeObject: (fn: (node: any) => ThreeObject) => ForceGraph3DInstance
    nodeThreeObjectExtend: (extend: boolean) => ForceGraph3DInstance
    cooldownTime: (ms: number) => ForceGraph3DInstance
    linkOpacity: (val: number) => ForceGraph3DInstance
    linkWidth: (fn: (link: any) => number) => ForceGraph3DInstance
    linkColor: (fn: (link: any) => string) => ForceGraph3DInstance
    coolingTime: (ticks: number) => ForceGraph3DInstance
    cameraPosition: (
      position: { x?: number; y?: number; z?: number },
      lookAt?: { x: number; y: number; z: number }
    ) => ForceGraph3DInstance
    destroy?: () => void
  } & Record<string, any>

  export type { ForceGraph3DInstance }
  export default function ForceGraph3D(): (element: HTMLElement) => ForceGraph3DInstance
}
