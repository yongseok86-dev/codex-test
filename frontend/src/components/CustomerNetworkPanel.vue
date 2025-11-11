<template>
  <section class="network-panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">Behavior Insights</p>
        <h2>고객 행동 네트워크</h2>
        <p class="subtitle">선택한 고객군이 어떤 경로로 이동하는지 빠르게 확인하세요.</p>
      </div>
      <div class="panel-controls">
        <el-select v-model="selectedSegment" size="small" class="control" placeholder="고객군" @change="onSegmentChange">
          <el-option v-for="option in segments" :key="option.id" :label="option.label" :value="option.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          unlink-panels
          size="small"
          class="control"
          start-placeholder="시작"
          end-placeholder="종료"
        />
        <el-input-number v-model="limit" :min="5" :max="200" :step="5" size="small" class="control" />
        <el-input-number v-model="minEdge" :min="1" :max="100" :step="1" size="small" class="control" />
        <el-button type="primary" size="small" :loading="loading" @click="fetchGraph">새로고침</el-button>
      </div>
      <div class="view-toggle">
        <el-button-group>
          <el-button
            size="small"
            :type="chartView === 'network' ? 'primary' : 'default'"
            @click="chartView = 'network'"
          >
            3D Network
          </el-button>
          <el-button
            size="small"
            :type="chartView === 'sankey' ? 'primary' : 'default'"
            @click="chartView = 'sankey'"
          >
            Sankey
          </el-button>
        </el-button-group>
      </div>
    </div>

    <div class="panel-body">
      <div v-if="error" class="error-banner">{{ error }}</div>
      <el-skeleton v-else-if="loading" :rows="3" animated />
      <template v-else>
        <div v-if="hasGraph" class="graph-stack">
          <div class="graph-row">
            <NetworkGraph
              v-if="chartView === 'network'"
              :nodes="graph?.nodes || []"
              :links="graph?.links || []"
            />
            <SankeyChart
              v-else
              :nodes="graph?.nodes || []"
              :links="graph?.links || []"
            />
          </div>
          <div class="insight-grid">
            <div class="summary-card">
              <h3>{{ graph?.segment.label }}</h3>
              <p class="muted">{{ graph?.segment.description }}</p>
              <div class="summary-grid">
                <div>
                  <span>기간</span>
                  <strong>{{ graph?.filters.start_date }} ~ {{ graph?.filters.end_date }}</strong>
                </div>
                <div>
                  <span>총 전환 수</span>
                  <strong>{{ graph?.summary.total_transitions }}</strong>
                </div>
                <div>
                  <span>노드 수</span>
                  <strong>{{ graph?.summary.node_count }}</strong>
                </div>
                <div>
                  <span>연결 수</span>
                  <strong>{{ graph?.summary.edge_count }}</strong>
                </div>
              </div>
              <div class="source">
                <span>데이터 소스</span>
                <code>{{ graph?.data_source.events_table }}</code>
              </div>
            </div>
            <ProductTimeSeries class="timeseries-card" />
          </div>
        </div>
        <el-empty v-else description="조건에 맞는 데이터가 없습니다." />
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import NetworkGraph from './NetworkGraph.vue'
import SankeyChart from './SankeyChart.vue'
import ProductTimeSeries from './ProductTimeSeries.vue'

interface SegmentOption {
  id: string
  label: string
  description: string
  default?: boolean
}

interface GraphNode { id: string; label: string; value: number }
interface GraphLink { source: string; target: string; value: number }
interface GraphResponse {
  segment: { id: string; label: string; description: string }
  filters: { start_date: string; end_date: string; limit: number; min_edge_count: number }
  nodes: GraphNode[]
  links: GraphLink[]
  summary: { total_transitions: number; edge_count: number; node_count: number }
  data_source: { events_table: string; orders_table?: string; users_table?: string }
}

const segments = ref<SegmentOption[]>([])
const selectedSegment = ref('')
const dateRange = ref<[Date, Date] | null>(createInitialRange())
const limit = ref(25)
const minEdge = ref(3)
const loading = ref(false)
const chartView = ref<'network' | 'sankey'>('network')
const error = ref<string | null>(null)
const graph = ref<GraphResponse | null>(null)
const base = (import.meta as any).env?.VITE_API_BASE || ''

const hasGraph = computed(() => {
  const data = graph.value
  if (!data || !Array.isArray(data.links)) return false
  return data.links.length > 0
})

function createInitialRange(): [Date, Date] {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 13)
  return [start, end]
}

function toISO(value: Date): string {
  const year = value.getFullYear()
  const month = `${value.getMonth() + 1}`.padStart(2, '0')
  const day = `${value.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function loadSegments() {
  try {
    const res = await fetch(`${base}/api/network/customer-flow/segments`)
    if (!res.ok) throw new Error(await res.text())
    const data: SegmentOption[] = await res.json()
    segments.value = data
    const defaultSegment = data.find(item => item.default) ?? data[0]
    if (defaultSegment) {
      selectedSegment.value = defaultSegment.id
      await fetchGraph()
    }
  } catch (err: any) {
    error.value = err?.message || '세그먼트 정보를 가져오지 못했습니다.'
  }
}

async function fetchGraph() {
  if (!selectedSegment.value) return
  loading.value = true
  error.value = null
  try {
    const payload: Record<string, any> = {
      segment: selectedSegment.value,
      limit: limit.value,
      min_edge_count: minEdge.value,
    }
    if (dateRange.value && dateRange.value.length === 2) {
      payload.start_date = toISO(dateRange.value[0])
      payload.end_date = toISO(dateRange.value[1])
    }
    const res = await fetch(`${base}/api/network/customer-flow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error(await res.text())
    graph.value = await res.json()
  } catch (err: any) {
    error.value = err?.message || '네트워크 정보를 가져오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function onSegmentChange() {
  fetchGraph()
}

onMounted(() => {
  loadSegments()
})
</script>

<style scoped>
.network-panel {
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  padding: 16px;
  background: #020617;
  color: #f8fafc;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.eyebrow {
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #cbd5f5;
  margin: 0;
}
.subtitle { color: #e2e8f0; margin-top: 4px; }
.panel-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.view-toggle {
  display: flex;
  align-items: center;
  color: #f8fafc;
}
.control {
  min-width: 140px;
}
.panel-body {
  margin-top: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.graph-stack {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.graph-row {
  flex: 1;
  min-height: 0;
  border-radius: 12px;
}
.graph-row > * {
  min-height: 100%;
}
.graph-row :deep(.network-graph),
.graph-row :deep(.sankey-chart) {
  min-height: 100%;
  height: 100%;
}
.insight-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}
.summary-card {
  flex: 0 0 auto;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(6px);
  color: #f8fafc;
}
.timeseries-card {
  min-height: 320px;
}
.muted {
  color: #cbd5f5;
  margin-bottom: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.summary-grid span {
  display: block;
  color: #e2e8f0;
  font-size: 12px;
}
.summary-grid strong {
  font-size: 18px;
  color: #fef3c7;
}
.source {
  font-size: 12px;
  color: #cbd5f5;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.source code {
  background: #0f172a;
  color: #f8fafc;
  padding: 4px 6px;
  border-radius: 6px;
  font-size: 11px;
}
.error-banner {
  border: 1px solid #fca5a5;
  background: #7f1d1d;
  color: #fecaca;
  padding: 12px;
  border-radius: 6px;
}
.panel-controls :deep(.el-input__wrapper),
.panel-controls :deep(.el-date-editor.el-range-editor.el-input__inner) {
  background: #0f172a;
  border-color: rgba(148, 163, 184, 0.4);
  color: #f8fafc;
}
.panel-controls :deep(.el-input__inner),
.panel-controls :deep(.el-range-input) {
  color: #f8fafc;
}
.panel-controls :deep(.el-select__placeholder),
.panel-controls :deep(.el-range-input::placeholder) {
  color: rgba(226, 232, 240, 0.7);
}
@media (max-width: 1024px) {
  .graph-stack {
    grid-template-rows: minmax(300px, 1fr) auto;
  }
}
</style>
