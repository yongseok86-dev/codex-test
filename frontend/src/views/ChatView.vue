<template>
  <div class="chat">
    <div class="toolbar">
      <el-switch v-model="dryRun" active-text="Dry Run" inactive-text="Execute" />
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
import { ref, nextTick } from 'vue'
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
    const r = await fetch(`${base}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: text, dry_run: dryRun.value, limit: limit.value })
    })
    if (!r.ok) throw new Error(await r.text())
    const body = await r.json()
    addMessage('assistant', 'SQL이 생성되었습니다. 아래 결과 패널을 확인하세요.')
    setResult(body)
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
