<template>
  <div class="panel">
    <div class="section">
      <div class="title">생성된 SQL</div>
      <pre><code class="sql">{{ result.sql }}</code></pre>
    </div>
    <div v-if="result.metadata" class="section meta">
      <div class="title">메타데이터</div>
      <div class="kv">
        <div v-for="(v, k) in result.metadata" :key="k" class="row"><b>{{ k }}</b><span>{{ v as any }}</span></div>
      </div>
    </div>
    <div v-if="hasRows" class="section">
      <div class="title">결과</div>
      <el-table :data="result.rows as any[]" stripe style="width: 100%">
        <el-table-column v-for="col in columns" :key="col" :prop="col" :label="col" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Result {
  sql: string
  dry_run: boolean
  rows?: Array<Record<string, any>>
  metadata?: Record<string, any>
}

const props = defineProps<{ result: Result }>()
const hasRows = computed(() => Array.isArray(props.result.rows) && props.result.rows!.length > 0)
const columns = computed(() => {
  if (!hasRows.value) return []
  return Object.keys(props.result.rows![0]!)
})
</script>

<style scoped>
.panel { background: var(--panel-bg, #fff); border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: grid; gap: 12px; }
.title { font-weight: 600; margin-bottom: 6px; }
pre { background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; overflow: auto; }
.kv .row { display: grid; grid-template-columns: 160px 1fr; gap: 8px; padding: 4px 0; }
.dark .panel { background: #0b0f19; border-color: #1f2937; }
.dark pre { background: #0a0e18; color: #e5e7eb; }
</style>

