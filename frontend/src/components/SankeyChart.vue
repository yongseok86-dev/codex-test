<template>
  <div class="sankey-chart" ref="chartRef">
    <svg ref="svgRef"></svg>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as d3 from 'd3'
import { sankey, sankeyLinkHorizontal, type SankeyGraph, type SankeyNodeMinimal, type SankeyLinkMinimal } from 'd3-sankey'

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
const chartRef = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
let observer: ResizeObserver | null = null
let raf: number | null = null

const MAX_LINKS = 200

const sankeyData = computed(() => {
  const sortedLinks = [...props.links]
    .sort((a, b) => (b.value || 0) - (a.value || 0))
    .slice(0, MAX_LINKS)

  const adjacency = new Map<string, Set<string>>()

  const hasPath = (start: string, goal: string) => {
    if (start === goal) return true
    const visited = new Set<string>()
    const queue: string[] = [start]
    while (queue.length) {
      const current = queue.shift()!
      if (current === goal) return true
      if (visited.has(current)) continue
      visited.add(current)
      const neighbors = adjacency.get(current)
      if (!neighbors) continue
      for (const next of neighbors) {
        if (!visited.has(next)) queue.push(next)
      }
    }
    return false
  }

  const acyclicLinks: GraphLink[] = []
  for (const link of sortedLinks) {
    const source = link.source
    const target = link.target
    if (!source || !target) continue
    if (source === target) continue
    if (hasPath(target, source)) continue
    acyclicLinks.push(link)
    if (!adjacency.has(source)) adjacency.set(source, new Set())
    adjacency.get(source)!.add(target)
  }

  const nodeIds = new Set(acyclicLinks.flatMap((l) => [l.source, l.target]))
  const filteredNodes = props.nodes.filter((node) => nodeIds.has(node.id))

  return { nodes: filteredNodes, links: acyclicLinks }
})

const colorFromId = (id: string) => {
  let hash = 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash << 5) - hash + id.charCodeAt(i)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 80%, 60%)`
}

type SankeyNode = SankeyNodeMinimal<GraphNode, GraphLink>
type SankeyLink = SankeyLinkMinimal<GraphNode, GraphLink>

const getNodeId = (node: any) => (node?.id as string) ?? ''
const getNodeLabel = (node: any) => (node?.label as string) ?? getNodeId(node)

const scheduleRender = () => {
  if (raf) cancelAnimationFrame(raf)
  raf = requestAnimationFrame(render)
}

const render = () => {
  if (!svgRef.value || !chartRef.value) return
  const width = chartRef.value.clientWidth || 800
  const dynamicHeight = Math.max(480, sankeyData.value.nodes.length * 18)
  const height = dynamicHeight + 40

  const svg = d3.select(svgRef.value)
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const sankeyLayout = sankey<SankeyNode, SankeyLink>()
    .nodeId((d) => (d as GraphNode).id)
    .iterations(6)
    .nodeWidth(20)
    .nodePadding(18)
    .extent([
      [0, 10],
      [width, height - 10]
    ])

  const graph: SankeyGraph<SankeyNode, SankeyLink> = sankeyLayout({
    nodes: sankeyData.value.nodes.map((node) => ({ ...node })),
    links: sankeyData.value.links.map((link) => ({ ...link }))
  })

  const link = svg.append('g')
    .attr('fill', 'none')
    .attr('stroke-opacity', 0.25)
    .selectAll('path')
    .data(graph.links)
    .enter()
    .append('path')
    .attr('d', sankeyLinkHorizontal())
    .attr('stroke', (d) => colorFromId(getNodeId(d.source)))
    .attr('stroke-width', (d) => Math.max(1, d.width ?? 1))

  link.append('title').text((d) => `${(d.source as GraphNode).label} → ${(d.target as GraphNode).label}\n${d.value}`)

  const node = svg.append('g')
    .attr('font-family', 'Pretendard, "Noto Sans KR", sans-serif')
    .attr('font-size', 12)
    .selectAll('g')
    .data(graph.nodes)
    .enter()
    .append('g')

  node.append('rect')
    .attr('x', (d) => d.x0 ?? 0)
    .attr('y', (d) => d.y0 ?? 0)
    .attr('height', (d) => Math.max(1, (d.y1 ?? 0) - (d.y0 ?? 0)))
    .attr('width', (d) => Math.max(4, (d.x1 ?? 0) - (d.x0 ?? 0)))
    .attr('fill', (d) => colorFromId(getNodeId(d)))
    .attr('stroke', '#0f172a')

  node.append('text')
    .attr('x', (d) => (d.x0 ?? 0) - 6)
    .attr('y', (d) => ((d.y1 ?? 0) + (d.y0 ?? 0)) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'end')
    .attr('fill', '#f8fafc')
    .text((d) => getNodeLabel(d).slice(0, 12))
    .filter((d) => (d.x0 ?? 0) < width / 2)
    .attr('x', (d) => (d.x1 ?? 0) + 6)
    .attr('text-anchor', 'start')
}

onMounted(() => {
  observer = new ResizeObserver(() => {
    scheduleRender()
  })
  if (chartRef.value && observer) observer.observe(chartRef.value)
  scheduleRender()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  if (raf) cancelAnimationFrame(raf)
})

watch(() => [props.nodes, props.links], () => {
  scheduleRender()
})
</script>

<style scoped>
.sankey-chart {
  width: 100%;
  height: 100%;
}
svg {
  width: 100%;
  height: 100%;
}
</style>
