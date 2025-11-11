<template>
  <section class="bubble-panel">
    <header class="panel-header">
      <h3>시간대별 상품 구매량</h3>
      <el-button size="small" :loading="loading" @click="loadData">새로고침</el-button>
    </header>
    <div class="chart-area">
      <div v-if="error" class="error">{{ error }}</div>
      <el-skeleton v-else-if="loading" :rows="3" animated />
      <el-empty v-else-if="!points.length" description="데이터가 없습니다." />
      <svg v-else :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none">
        <g class="axes">
          <line :x1="padding" :y1="height - padding" :x2="width - padding" :y2="height - padding" />
          <line :x1="padding" :y1="padding" :x2="padding" :y2="height - padding" />
          <text :x="width - padding" :y="height - padding + 20" class="axis-label">시간</text>
          <text :x="padding - 12" :y="padding - 8" class="axis-label">수량</text>
        </g>
        <g class="bubbles">
          <circle
            v-for="p in scaled"
            :key="p.key"
            :cx="p.x"
            :cy="p.y"
            :r="p.r"
            :fill="p.color"
          >
            <title>{{ p.time }} · {{ p.product }}: {{ p.value }}</title>
          </circle>
        </g>
      </svg>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

interface BubblePoint {
  time_bucket: string
  product_name: string
  total_quantity: number
}

const width = 720
const height = 300
const padding = 40

const loading = ref(false)
const error = ref<string | null>(null)
const points = ref<BubblePoint[]>([])
const base = (import.meta as any).env?.VITE_API_BASE || ''

const parseTimeToMinutes = (bucket: string) => {
  const [h, m] = bucket.split(':').map(Number)
  return h * 60 + m
}

const maxValue = computed(() => Math.max(1, ...points.value.map((p) => p.total_quantity)))

const colorFromName = (name: string) => {
  let hash = 0
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash << 5) - hash + name.charCodeAt(i)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsla(${hue}, 70%, 60%, 0.75)`
}

const scaled = computed(() => {
  if (!points.value.length) return []
  const minTime = Math.min(...points.value.map((p) => parseTimeToMinutes(p.time_bucket)))
  const maxTime = Math.max(...points.value.map((p) => parseTimeToMinutes(p.time_bucket)))
  const timeRange = Math.max(1, maxTime - minTime)
  return points.value.map((p) => {
    const minutes = parseTimeToMinutes(p.time_bucket)
    const x = padding + ((minutes - minTime) / timeRange) * (width - padding * 2)
    const y = padding + (1 - p.total_quantity / maxValue.value) * (height - padding * 2)
    const r = 6 + (p.total_quantity / maxValue.value) * 18
    return {
      key: `${p.time_bucket}-${p.product_name}`,
      x,
      y,
      r,
      time: p.time_bucket,
      product: p.product_name,
      value: p.total_quantity,
      color: colorFromName(p.product_name)
    }
  })
})

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const resp = await fetch(`${base}/api/time-series/purchases/bubbles`)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    points.value = data.series ?? []
  } catch (err: any) {
    error.value = err?.message || '버블 데이터를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.bubble-panel {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  padding: 16px;
  background: rgba(8, 15, 30, 0.8);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #f8fafc;
}
.chart-area {
  min-height: 300px;
}
.error {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.4);
  border: 1px solid #fca5a5;
  padding: 12px;
  border-radius: 8px;
}
svg {
  width: 100%;
  height: 300px;
}
.axes line {
  stroke: rgba(148, 163, 184, 0.4);
  stroke-width: 1;
}
.axis-label {
  fill: #cbd5f5;
  font-size: 12px;
}
.bubbles circle {
  stroke: rgba(15, 23, 42, 0.6);
  stroke-width: 1;
}
</style>
