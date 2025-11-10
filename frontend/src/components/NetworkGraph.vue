<template>
  <div class="network-graph" ref="wrapperRef">
    <div class="graph-toolbar">
      <el-button-group>
        <el-button size="small" @click="zoomOut">-</el-button>
        <el-button size="small" @click="zoomIn">+</el-button>
        <el-button size="small" @click="resetView">Reset</el-button>
      </el-button-group>
      <span class="zoom-indicator">{{ zoomDisplay }}</span>
    </div>
    <div ref="graphRef" class="graph-canvas"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import ForceGraph3D, { type ForceGraph3DInstance } from '3d-force-graph'
import * as THREE from 'three'

interface GraphNode {
  id: string
  label: string
  value: number
}

interface GraphLink {
  source: string
  target: string
  value: number
}

const props = defineProps<{ nodes: GraphNode[]; links: GraphLink[] }>()

const truncateLabel = (label: string): string => {
  if (!label) return ''
  return label.length > 10 ? `${label.slice(0, 10)}…` : label
}

const createLabelSprite = (text: string, color = '#f8fafc') => {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = color
    ctx.font = '400 32px "Pretendard", "Noto Sans KR", sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, canvas.width / 2, canvas.height / 2)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.anisotropy = 4
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(40, 12, 1)
  sprite.position.y = 14
  return sprite
}

const wrapperRef = ref<HTMLDivElement | null>(null)
const graphRef = ref<HTMLDivElement | null>(null)
const fgInstance = shallowRef<ForceGraph3DInstance | null>(null)
const zoomValue = ref(1)
const zoomDisplay = computed(() => `${Math.round(zoomValue.value * 100)}%`)

type GraphData = {
  nodes: Array<GraphNode & { shortLabel: string; color: string }>
  links: Array<GraphLink>
}

const colorFromId = (id: string) => {
  let hash = 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash << 5) - hash + id.charCodeAt(i)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 80%, 60%)`
}

const graphData = computed<GraphData>(() => ({
  nodes: props.nodes.map((node) => ({
    ...node,
    shortLabel: truncateLabel(node.label || node.id),
    color: colorFromId(node.id)
  })),
  links: props.links.map((link) => ({ ...link }))
}))

const applyGraphData = () => {
  if (!fgInstance.value) return
  fgInstance.value.graphData(graphData.value)
}

const initializeGraph = () => {
  if (!graphRef.value) return
  const fg = ForceGraph3D()(graphRef.value)
  fg.backgroundColor('#040915')
    .cooldownTime(3000)
    .nodeLabel((node: GraphNode & { shortLabel?: string }) => `${node.label ?? node.id} · ${node.value ?? 0}`)
    .nodeColor((node: GraphNode & { color?: string }) => node.color ?? '#38bdf8')
    .nodeThreeObject((node: GraphNode & { shortLabel?: string; color?: string }) =>
      createLabelSprite(node.shortLabel ?? node.id, node.color)
    )
    .nodeThreeObjectExtend(true)
    .nodeVal((node: GraphNode) => Math.max(2, Math.sqrt(node.value || 1)))
    .nodeRelSize(6)
    .linkOpacity(0.35)
    .linkColor(() => 'rgba(148,163,184,0.7)')
    .linkWidth((link: GraphLink) => Math.max(0.4, Math.log1p(link.value || 1)))

  fg.cameraPosition({ z: 320 })
  fgInstance.value = fg
  applyGraphData()
}

const zoomIn = () => {
  if (!fgInstance.value) return
  zoomValue.value = Math.min(2.5, zoomValue.value + 0.1)
  fgInstance.value.cameraPosition({ z: 320 / zoomValue.value })
}

const zoomOut = () => {
  if (!fgInstance.value) return
  zoomValue.value = Math.max(0.3, zoomValue.value - 0.1)
  fgInstance.value.cameraPosition({ z: 320 / zoomValue.value })
}

const resetView = () => {
  zoomValue.value = 1
  fgInstance.value?.cameraPosition({ z: 320 })
}

onMounted(() => {
  initializeGraph()
})

onBeforeUnmount(() => {
  if (fgInstance.value?.destroy) {
    fgInstance.value.destroy()
  } else if (graphRef.value) {
    graphRef.value.innerHTML = ''
  }
})

watch(graphData, applyGraphData)
</script>

<style scoped>
.network-graph {
  width: 100%;
  height: 100%;
  position: relative;
  background: #020617;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.graph-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 2;
}
.zoom-indicator {
  color: #f8fafc;
  font-size: 12px;
}
.graph-canvas {
  width: 100%;
  height: 100%;
}
:global(.network-graph canvas) {
  outline: none;
}
</style>
