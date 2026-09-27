<template>
  <div class="dialog-mask" @click.self="emit('close')">
    <div class="dialog">
      <h3>加药登记 · {{ entry['机组编号'] }}</h3>
      <p class="muted dialog-tip">加药完成后机组随即停机归档，絮凝剂用量保留在该条运行记录上。</p>
      <form class="dialog-form" @submit.prevent="submit">
        <label class="form-item">
          <span>絮凝剂用量（kg，必填）</span>
          <input v-model="dose" placeholder="如 3.2" />
        </label>
        <label class="form-item">
          <span>出泥含水率（%，选填）</span>
          <input v-model="moisture" placeholder="如 78.5" />
        </label>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        <div class="dialog-actions">
          <button class="btn ghost" type="button" @click="emit('close')">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认加药' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { request } from '@/api/client'

type Entry = Record<string, string | number | null> & { id: string | number }

const props = defineProps<{ entry: Entry }>()
const emit = defineEmits<{ close: []; saved: [message: string] }>()

const dose = ref('')
const moisture = ref('')
const submitting = ref(false)
const errorMessage = ref('')

async function submit() {
  if (submitting.value) return
  errorMessage.value = ''
  if (!dose.value.trim()) {
    errorMessage.value = '请填写絮凝剂用量'
    return
  }
  submitting.value = true
  try {
    const values: Record<string, unknown> = { action: '加药', 絮凝剂用量: dose.value.trim() }
    if (moisture.value.trim()) {
      values['出泥含水率'] = moisture.value.trim()
    }
    const response = await request(`/api/sludge/${props.entry.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? '加药登记未生效，请稍后重试')
    }
    emit('saved', result.message ?? '加药完成')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加药登记失败'
  } finally {
    submitting.value = false
  }
}
</script>
