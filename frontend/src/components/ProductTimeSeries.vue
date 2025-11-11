<template>
  <section class="timeseries-panel">
    <header class="panel-header">
      <h3>상품 구매 추이</h3>
      <div class="controls">
        <el-input
          v-model="productId"
          size="small"
          placeholder="상품 ID (옵션)"
          class="control"
          clearable
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          unlink-panels
          size="small"
          class="control"
          start-placeholder="시작"
          end-placeholder="종료"
        />
        <el-select v-model="grain" size="small" class="control" placeholder="집계 단위">
          <el-option label="일간" value="day" />
          <el-option label="주간" value="week" />
          <el-option label="월간" value="month" />
        </el-select>
        <el-button size="small" type="primary" :loading="loading" @click="loadSeries">
          새로고침
        </el-button>
      </div>
    </header>
    <div class="chart-area" ref="chartRef">
      <div v-if="error" class="error">{{ error }}</div>
      <el-skeleton v-else-if="loading" :rows="3" animated />
      <div v-else-if="!series.length" class="empty">조건에 맞는 데이터가 없습니다.</div>
      <svg
        v-else
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="ts-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4" />
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.05" />
          </linearGradient>
        </defs>
        <g class="axes">
          <line :x1="padding" :y1="chartHeight - padding" :x2="chartWidth - padding" :y2="chartHeight - padding" />
          <line :x1="padding" :y1="padding" :x2="padding" :y2="chartHeight - padding" />
        </g>
        <path
          class="fill"
          :d="areaPath"
          fill="url(#ts-gradient)"
        />
        <path
          class="line"
          :d="linePath"
          stroke="#38bdf8"
          fill="none"
        />
        <g class="points">
          <circle
            v-for="p in scaledPoints"
            :key="p.bucket"
            :cx="p.x"
            :cy="p.y"
            r="3"
          >
            <title>{{ p.bucket }}: {{ p.value }}</title>
          </circle>
        </g>
      </svg>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface SeriesPoint {
  bucket: string
  total_quantity: number
}

const productId = ref<string>('')
const dateRange = ref<[Date, Date] | null>(createInitialRange())
const grain = ref<'day' | 'week' | 'month'>('day')
const loading = ref(false)
const error = ref<string | null>(null)
const series = ref<SeriesPoint[]>([])
const chartWidth = 720
const chartHeight = 280
const padding = 32
const base = (import.meta as any).env?.VITE_API_BASE || ''

function createInitialRange(): [Date, Date] {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 29)
  return [start, end]
}

function formatDate(date: Date) {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

async function loadSeries() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    error.value = '날짜 범위를 선택해 주세요.'
    return
  }
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams()
    params.set('start_date', formatDate(dateRange.value[0]))
    params.set('end_date', formatDate(dateRange.value[1]))
    params.set('grain', grain.value)
    if (productId.value.trim()) params.set('product_id', productId.value.trim())

    const resp = await fetch(`${base}/api/time-series/purchases?${params.toString()}`)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    series.value = data.series ?? []
  } catch (err: any) {
    error.value = err?.message || '시계열 데이터를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

const maxValue = computed(() => Math.max(1, ...series.value.map((p) => p.total_quantity)))

const scaledPoints = computed(() => {
  const n = series.value.length
  if (n === 0) return []
  return series.value.map((point, idx) => {
    const x = padding + (idx / Math.max(n - 1, 1)) * (chartWidth - padding * 2)
    const y = padding + (1 - point.total_quantity / maxValue.value) * (chartHeight - padding * 2)
    return { x, y, bucket: point.bucket, value: point.total_quantity }
  })
})

const linePath = computed(() => {
  if (!scaledPoints.value.length) return ''
  return scaledPoints.value
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'}${p.x},${p.y}`)
    .join(' ')
})

const areaPath = computed(() => {
  if (!scaledPoints.value.length) return ''
  const baselineY = chartHeight - padding
  const pathPoints = scaledPoints.value.map((p, idx) => `${idx === 0 ? 'M' : 'L'}${p.x},${p.y}`)
  const last = scaledPoints.value[scaledPoints.value.length - 1]
  const first = scaledPoints.value[0]
  return `${pathPoints.join(' ')} L${last.x},${baselineY} L${first.x},${baselineY} Z`
})

onMounted(() => {
  loadSeries()
})
</script>

<style scoped>
.timeseries-panel {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  padding: 16px;
  background: rgba(8, 15, 30, 0.8);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.panel-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel-header h3 {
  margin: 0;
  color: #f8fafc;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.control {
  min-width: 140px;
}
.chart-area {
  flex: 1;
  min-height: 280px;
}
.error {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.4);
  border: 1px solid #fca5a5;
  padding: 12px;
  border-radius: 8px;
}
.empty {
  color: #e2e8f0;
  padding: 12px;
}
svg {
  width: 100%;
  height: 280px;
}
.axes line {
  stroke: rgba(148, 163, 184, 0.3);
  stroke-width: 1;
}
.line {
  stroke-width: 2;
}
.points circle {
  fill: #f8fafc;
  stroke: #1d4ed8;
  stroke-width: 1;
}
</style>
