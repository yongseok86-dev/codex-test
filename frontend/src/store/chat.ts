import { reactive, computed } from 'vue'

export type Role = 'user' | 'assistant' | 'system'
export interface Message { role: Role; content: string; ts: number }
export interface Result { sql: string; dry_run: boolean; rows?: Array<Record<string, any>>; metadata?: Record<string, any> }
export interface Conversation { id: string; title: string; messages: Message[]; lastResult?: Result | null }

function uid() { return Math.random().toString(36).slice(2, 10) }

const STORAGE_KEY = 'nl2sql_chats'

function load(): Conversation[] {
  try { const raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : [] } catch { return [] }
}
function save(data: Conversation[]) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch {} }

const state = reactive({
  conversations: load() as Conversation[],
  currentId: '' as string
})

if (!state.conversations.length) {
  const c: Conversation = { id: uid(), title: '새 대화', messages: [{ role: 'system', content: '질문을 입력하면 NL→SQL을 생성합니다.', ts: Date.now() }], lastResult: null }
  state.conversations.push(c)
  state.currentId = c.id
  save(state.conversations)
} else {
  state.currentId = state.conversations[0].id
}

export const useChatStore = () => {
  const current = computed(() => state.conversations.find(c => c.id === state.currentId)!)

  function newConversation() {
    const c: Conversation = { id: uid(), title: '새 대화', messages: [{ role: 'system', content: '새 채팅을 시작했습니다.', ts: Date.now() }], lastResult: null }
    state.conversations.unshift(c)
    state.currentId = c.id
    save(state.conversations)
  }

  function selectConversation(id: string) {
    state.currentId = id
  }

  function addMessage(role: Role, content: string) {
    const c = current.value
    c.messages.push({ role, content, ts: Date.now() })
    if (role === 'user' && c.title === '새 대화') {
      c.title = content.slice(0, 24)
    }
    save(state.conversations)
  }

  function setResult(res: Result | null) {
    current.value.lastResult = res
    save(state.conversations)
  }

  return {
    state,
    conversations: computed(() => state.conversations),
    current,
    newConversation,
    selectConversation,
    addMessage,
    setResult,
  }
}

