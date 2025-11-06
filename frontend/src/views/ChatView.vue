<template>
  <div class="chat">
    <div class="toolbar">
      <el-switch v-model="dryRun" active-text="Dry Run" inactive-text="Execute" />
      <el-switch v-model="streaming" active-text="Streaming" />
      <el-input-number v-model="limit" :min="1" :max="5000" :step="50" size="small" />
      <el-button size="small" @click="clear">지우기</el-button>
    </div>
    <div class="messages" ref="scrollEl">
      <ChatMessage v-for="(m, i) in messages" :key="i" :role="m.role" :content="m.content" />
    </div>
    <div class="composer">
      <ChatInput :loading="loading" @send="onSend" />
    </div>
    <div v-if="lastResult" class="result">
      <ResultPanel :result="lastResult" />
    </div>
  </div>
  </template>

<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'
import ResultPanel from '../components/ResultPanel.vue'
import { useChatStore } from '../store/chat'

const { current, addMessage, setResult } = useChatStore()
type Msg = { role: 'user' | 'assistant' | 'system', content: string }
const messages = computed(() => current.value.messages.map(m => ({ role: m.role, content: m.content })))
const loading = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const dryRun = ref(true)
const limit = ref(100)
const lastResult = computed(() => current.value.lastResult)
const streaming = ref(true)

function scrollToBottom() {
  nextTick(() => {
    scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
  })
}

async function onSend(text: string) {
  if (!text.trim()) return
  addMessage('user', text)
  loading.value = true
  scrollToBottom()
  try {
    const base = (import.meta as any).env?.VITE_API_BASE || ''
    if (streaming.value) {
      const url = new URL(`${base}/api/query/stream`, window.location.origin)
      url.searchParams.set('q', text)
      url.searchParams.set('limit', String(limit.value))
      url.searchParams.set('dry_run', String(dryRun.value))
      const es = new EventSource(url.toString())
      es.addEventListener('nlu', (ev: MessageEvent) => {
        const data = JSON.parse(ev.data)
        addMessage('assistant', `NLU 의도: ${data.intent}`)
      })
      es.addEventListener('plan', (ev: MessageEvent) => {
        addMessage('assistant', '플랜 생성 완료')
      })
      es.addEventListener('sql', (ev: MessageEvent) => {
        const data = JSON.parse(ev.data)
        addMessage('assistant', 'SQL 생성 완료')
      })
      es.addEventListener('validated', (ev: MessageEvent) => {
        const data = JSON.parse(ev.data)
        if (!data.ok) addMessage('assistant', `검증 실패: ${data.error}`)
        else addMessage('assistant', '검증 통과')
      })
      es.addEventListener('result', (ev: MessageEvent) => {
        const data = JSON.parse(ev.data)
        setResult(data)
        addMessage('assistant', '실행 완료')
        es.close()
      })
      es.addEventListener('error', (ev: MessageEvent) => {
        try { addMessage('assistant', `오류: ${JSON.parse((ev as any).data).message}`) } catch {}
        es.close()
      })
    } else {
      const r = await fetch(`${base}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: text, dry_run: dryRun.value, limit: limit.value })
      })
      if (!r.ok) throw new Error(await r.text())
      const body = await r.json()
      addMessage('assistant', 'SQL이 생성되었습니다. 아래 결과 패널을 확인하세요.')
      setResult(body)
    }
  } catch (e: any) {
    addMessage('assistant', `오류: ${e?.message || e}`)
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function clear() {
  // advise user to start a new chat in sidebar
  addMessage('system', '대화를 초기화하려면 좌측의 새 채팅을 눌러주세요.')
}
</script>

<style scoped>
.chat { display: grid; grid-template-rows: auto 1fr auto auto; height: 100%; }
.toolbar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }
.messages { padding: 16px; overflow: auto; background: #f9fafb; }
.composer { border-top: 1px solid #e5e7eb; padding: 12px; background: white; }
.result { padding: 12px; border-top: 1px solid #e5e7eb; background: #fff; }
</style>
