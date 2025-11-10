<template>
  <div class="msg" :class="role">
    <div class="bubble" v-html="rendered"></div>
  </div>
  </template>

<script setup lang="ts">
import { computed, onMounted, onUpdated, nextTick } from 'vue'
import { marked, type MarkedOptions } from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import mermaid from 'mermaid'
import katex from 'katex'

const props = defineProps<{ role: 'user' | 'assistant' | 'system', content: string }>()

const renderer = new marked.Renderer()
renderer.code = (code, lang) => {
  if ((lang || '').toLowerCase() === 'mermaid') {
    const safe = code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `<div class="mermaid">${safe}</div>`
  }
  if ((lang || '').toLowerCase() === 'math') {
    try {
      return katex.renderToString(code, { displayMode: true, throwOnError: false })
    } catch {
      return `<pre><code>${code}</code></pre>`
    }
  }
  // default: code block with syntax highlight
  try {
    const html = lang && hljs.getLanguage(lang)
      ? hljs.highlight(code, { language: lang }).value
      : hljs.highlightAuto(code).value
    return `<pre><code class="hljs">${html}</code></pre>`
  } catch {
    return `<pre><code>${code}</code></pre>`
  }
}

const markedOptions: MarkedOptions & { headerIds?: boolean; mangle?: boolean } = {
  gfm: true,
  breaks: true,
  headerIds: false,
  mangle: false,
  renderer
}

marked.setOptions(markedOptions)

const rendered = computed(() => DOMPurify.sanitize(marked.parse(props.content)))

function renderDiagrams() {
  try {
    mermaid.initialize({ startOnLoad: false })
    // Render any new mermaid blocks within this component root
    const root = (document.currentScript as any)?.ownerDocument || document
    mermaid.run({ querySelector: '.mermaid' })
  } catch {}
}

onMounted(() => nextTick(renderDiagrams))
onUpdated(() => nextTick(renderDiagrams))
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
