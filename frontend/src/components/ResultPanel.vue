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
      <div class="title">결과
        <el-button size="small" class="ml" @click="downloadCsv">CSV 다운로드</el-button>
      </div>
      <el-table :data="paged" stripe style="width: 100%">
        <el-table-column v-for="col in columns" :key="col" :prop="col" :label="col" />
      </el-table>
      <div class="pager">
        <el-pagination
          layout="prev, pager, next, sizes, total"
          :page-size="pageSize"
          :page-sizes="[10,20,50,100]"
          :current-page="page"
          :total="total"
          @size-change="(s:number)=>pageSize=s"
          @current-change="(p:number)=>page=p"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

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
const page = ref(1)
const pageSize = ref(20)
const total = computed(() => props.result.rows?.length || 0)
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return (props.result.rows || []).slice(start, start + pageSize.value)
})

function toCsv(rows: any[]): string {
  if (!rows.length) return ''
  const cols = Object.keys(rows[0])
  const esc = (v: any) => '"' + String(v ?? '').replace(/"/g, '""') + '"'
  const lines = [cols.join(',')]
  for (const r of rows) lines.push(cols.map(c => esc(r[c])).join(','))
  return lines.join('\n')
}
function downloadCsv() {
  const csv = toCsv(props.result.rows || [])
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'result.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<style scoped>
.panel { background: var(--panel-bg, #fff); border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: grid; gap: 12px; }
.title { font-weight: 600; margin-bottom: 6px; }
pre { background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; overflow: auto; }
.kv .row { display: grid; grid-template-columns: 160px 1fr; gap: 8px; padding: 4px 0; }
.dark .panel { background: #0b0f19; border-color: #1f2937; }
.dark pre { background: #0a0e18; color: #e5e7eb; }
.pager { display:flex; justify-content: flex-end; margin-top: 8px; }
.ml { margin-left: 8px; }
</style>
