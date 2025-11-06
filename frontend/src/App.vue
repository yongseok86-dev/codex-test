<template>
  <div class="layout" :class="{ dark: isDark }">
    <aside class="sidebar">
      <div class="brand">NL2SQL</div>
      <div class="controls">
        <el-button type="primary" plain size="small" @click="newChat">새 채팅</el-button>
        <el-switch v-model="isDark" size="small" active-text="Dark" />
      </div>
      <div class="history">
        <div v-for="(item, i) in history" :key="i" class="history-item" @click="openChat(i)">
          {{ item.title }}
        </div>
      </div>
    </aside>
    <main class="content">
      <ChatView />
    </main>
  </div>
  <footer class="footer">Powered by FastAPI · BigQuery Semantic Layer (draft)</footer>
  </template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import ChatView from './views/ChatView.vue'

const history = ref<{ title: string }[]>([])
const isDark = ref<boolean>(() => localStorage.getItem('theme') === 'dark' as any)
function newChat() {
  // placeholder
}
function openChat(_i: number) {
  // placeholder
}

watch(isDark, (v) => {
  localStorage.setItem('theme', v ? 'dark' : 'light')
  document.documentElement.classList.toggle('dark', v)
}, { immediate: true })
</script>

<style scoped>
.layout { display: grid; grid-template-columns: 260px 1fr; height: 100vh; }
.sidebar { border-right: 1px solid #e5e7eb; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
.brand { font-weight: 700; font-size: 18px; }
.controls { display: flex; gap: 8px; align-items: center; }
.history { overflow: auto; flex: 1; }
.history-item { padding: 8px; border-radius: 6px; cursor: pointer; }
.history-item:hover { background: #f5f7fa; }
.content { display: flex; flex-direction: column; height: 100vh; }
.footer { border-top: 1px solid #e5e7eb; padding: 8px 12px; color: #6b7280; font-size: 12px; }
</style>

<style>
.dark body, .dark .content { background: #0b0f19; color: #e5e7eb; }
.dark .sidebar { border-right-color: #1f2937; }
.dark .history-item:hover { background: #111827; }
.dark .composer, .dark .result { background: #0b0f19; border-color: #1f2937; }
</style>
