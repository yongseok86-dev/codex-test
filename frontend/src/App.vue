<template>
  <div class="layout" :class="{ dark: isDark }">
    <aside class="sidebar">
      <div class="brand">NL2SQL</div>
      <div class="controls">
        <el-button type="primary" plain size="small" @click="newChat">새 채팅</el-button>
        <el-switch v-model="isDark" size="small" active-text="Dark" />
      </div>
      <div class="sections">
        <el-button
          v-for="view in views"
          :key="view.id"
          :type="activeView === view.id ? 'primary' : 'default'"
          plain
          size="small"
          @click="activeView = view.id"
        >
          {{ view.label }}
        </el-button>
      </div>
      <div class="history" v-if="activeView === 'chat'">
        <div v-for="(item, i) in history" :key="i" class="history-item" @click="openChat(i)">
          {{ item.title }}
        </div>
      </div>
    </aside>
    <main class="content">
      <section v-if="activeView === 'network'" class="insight-panel">
        <CustomerNetworkPanel />
      </section>
      <section v-else class="chat-shell">
        <ChatView />
      </section>
    </main>
  </div>
  <footer class="footer">Powered by FastAPI · BigQuery Semantic Layer (draft)</footer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ChatView from './views/ChatView.vue'
import CustomerNetworkPanel from './components/CustomerNetworkPanel.vue'
import { useChatStore } from './store/chat'

const { conversations, newConversation, selectConversation } = useChatStore()
const history = computed(() => conversations.value.map(c => ({ title: c.title })))
const preferredDark = typeof window !== 'undefined' && localStorage.getItem('theme') === 'dark'
const isDark = ref<boolean>(preferredDark)
const views = [
  { id: 'chat', label: '챗 보기' },
  { id: 'network', label: '고객 네트워크' }
] as const
const activeView = ref<(typeof views)[number]['id']>('chat')

function newChat() { newConversation() }
function openChat(i: number) { selectConversation(conversations.value[i].id) }

watch(isDark, (v) => {
  localStorage.setItem('theme', v ? 'dark' : 'light')
  document.documentElement.classList.toggle('dark', v)
}, { immediate: true })
</script>

<style scoped>
.layout { display: grid; grid-template-columns: 260px 1fr; height: 100%; overflow: hidden; flex: 1 1 auto; }
.sidebar { border-right: 1px solid #e5e7eb; padding: 12px; display: flex; flex-direction: column; gap: 12px; overflow: auto; min-height: 0; }
.brand { font-weight: 700; font-size: 18px; }
.controls { display: flex; gap: 8px; align-items: center; }
.sections { display: flex; flex-direction: column; gap: 6px; }
.history { overflow: auto; flex: 1; }
.history-item { padding: 8px; border-radius: 6px; cursor: pointer; }
.history-item:hover { background: #f5f7fa; }
.content { display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: auto; }
.chat-shell { flex: 1 1 auto; min-height: 0; }
.insight-panel {
  flex: 1 1 auto;
  min-height: 0;
}
.footer { border-top: 1px solid #e5e7eb; padding: 8px 12px; color: #6b7280; font-size: 12px; }
</style>

<style>
:global(html),
:global(body) {
  height: 100%;
  margin: 0;
  overflow: hidden;
}
:global(#app) {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.dark body, .dark .content { background: #0b0f19; color: #e5e7eb; }
.dark .sidebar { border-right-color: #1f2937; }
.dark .history-item:hover { background: #111827; }
.dark .composer, .dark .result { background: #0b0f19; border-color: #1f2937; }
</style>
