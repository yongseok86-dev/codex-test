<template>
  <el-input
    v-model="text"
    type="textarea"
    :autosize="{ minRows: 2, maxRows: 6 }"
    placeholder="무엇이 궁금하신가요? 예) 지난 7일 주문 추이"
    @keydown.enter.exact.prevent="emitSend"
  />
  <div class="actions">
    <el-button type="primary" :loading="loading" @click="emitSend">보내기</el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue'

const props = defineProps<{ loading?: boolean }>()
const emit = defineEmits<{ (e: 'send', text: string): void }>()
const text = ref('')

function emitSend() {
  if (!text.value.trim() || props.loading) return
  emit('send', text.value)
  text.value = ''
}

watchEffect(() => {
  // could handle keyboard or focus mgmt
})
</script>

<style scoped>
.actions { display: flex; justify-content: flex-end; margin-top: 8px; }
</style>

