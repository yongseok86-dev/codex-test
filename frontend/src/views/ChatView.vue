<template>
  <div class="chat">
    <div class="messages" ref="scrollEl">
      <ChatMessage v-for="(m, i) in messages" :key="i" :role="m.role" :content="m.content" />
    </div>
    <div class="composer">
      <ChatInput :loading="loading" @send="onSend" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'

type Msg = { role: 'user' | 'assistant' | 'system', content: string }
const messages = ref<Msg[]>([
  { role: 'system', content: '질문을 입력하면 NL→SQL 생성 후 결과를 보여줍니다.' }
])
const loading = ref(false)
const scrollEl = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
  })
}

async function onSend(text: string) {
  if (!text.trim()) return
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  scrollToBottom()
  try {
    const base = (import.meta as any).env?.VITE_API_BASE || ''
    const r = await fetch(`${base}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: text })
    })
    if (!r.ok) throw new Error(await r.text())
    const body = await r.json()
    const reply = `SQL\n\n\`\`\`sql\n${body.sql}\n\`\`\`\n\nDry run: ${body.dry_run}`
    messages.value.push({ role: 'assistant', content: reply })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `오류: ${e?.message || e}` })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.chat { display: grid; grid-template-rows: 1fr auto; height: 100%; }
.messages { padding: 16px; overflow: auto; background: #f9fafb; }
.composer { border-top: 1px solid #e5e7eb; padding: 12px; background: white; }
</style>

