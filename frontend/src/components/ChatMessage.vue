<template>
  <div class="msg" :class="role">
    <div class="bubble" v-html="rendered"></div>
  </div>
  </template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ role: 'user' | 'assistant' | 'system', content: string }>()

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'} as any)[c])
}

function renderSimpleMarkdown(src: string): string {
  // very small renderer: code fences + line breaks
  const parts = src.split(/```/)
  let html = ''
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      html += `<pre><code>${escapeHtml(parts[i])}</code></pre>`
    } else {
      html += escapeHtml(parts[i]).replace(/\n/g, '<br/>')
    }
  }
  return html
}

const rendered = computed(() => renderSimpleMarkdown(props.content))
</script>

<style scoped>
.msg { display: flex; margin: 6px 0; }
.msg.user { justify-content: flex-end; }
.msg.assistant, .msg.system { justify-content: flex-start; }
.bubble { max-width: 70%; padding: 10px 12px; border-radius: 10px; background: white; border: 1px solid #e5e7eb; }
.user .bubble { background: #dcfce7; border-color: #bbf7d0; }
.system .bubble { background: #f3f4f6; }
pre { background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; overflow: auto; }
</style>
