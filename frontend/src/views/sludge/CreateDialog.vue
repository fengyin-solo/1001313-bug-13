<template>
  <div v-if="open" class="modal-mask" @click.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>登记脱水机组运行记录</h3>
        <button class="modal-close" type="button" @click="close">×</button>
      </header>
      <p class="modal-tip">
        同一台机组同一时期只允许一条在办记录；进泥量与运行功率按本次运行整额登记，不会拆分。
      </p>
      <form class="modal-form" @submit.prevent="submit">
        <label v-for="field in fields" :key="field.key" class="form-field">
          <span>{{ field.label }}<em v-if="field.required">*</em></span>
          <input
            v-model="form[field.key]"
            :inputmode="field.numeric ? 'decimal' : undefined"
            :placeholder="`请填写${field.label}`"
          />
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <footer class="modal-foot">
          <button class="btn" type="button" :disabled="submitting" @click="close">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '提交登记' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { createEntry, isBlank, type CreateForm, type SludgeRow } from './sludge'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created', entry: SludgeRow): void
}>()

interface FieldDef {
  key: keyof CreateForm
  label: string
  required: boolean
  numeric: boolean
}

const fields: FieldDef[] = [
  { key: '机组编号', label: '机组编号', required: true, numeric: false },
  { key: '所属厂站', label: '所属厂站', required: true, numeric: false },
  { key: '机组类型', label: '机组类型', required: true, numeric: false },
  { key: '运行功率', label: '运行功率(kW)', required: true, numeric: true },
  { key: '进泥量', label: '进泥量(t)', required: false, numeric: true },
]

function emptyForm(): CreateForm {
  return { 机组编号: '', 所属厂站: '', 机组类型: '', 运行功率: '', 进泥量: '' }
}

const form = reactive<CreateForm>(emptyForm())
const error = ref('')
const submitting = ref(false)

watch(
  () => props.open,
  (open) => {
    if (open) {
      Object.assign(form, emptyForm())
      error.value = ''
      submitting.value = false
    }
  },
)

function close() {
  if (submitting.value) return
  emit('close')
}

async function submit() {
  error.value = ''
  if (isBlank(form.机组编号) || isBlank(form.所属厂站) || isBlank(form.机组类型) || isBlank(form.运行功率)) {
    error.value = '请补全带 * 的必填字段'
    return
  }
  const numericLabels: Array<[keyof CreateForm, string]> = [
    ['运行功率', '运行功率'],
    ['进泥量', '进泥量'],
  ]
  for (const [key, label] of numericLabels) {
    if (!isBlank(form[key]) && Number.isNaN(Number(form[key]))) {
      error.value = `字段「${label}」必须是数值`
      return
    }
  }
  submitting.value = true
  try {
    const payload: Partial<CreateForm> = {}
    for (const field of fields) {
      if (!isBlank(form[field.key])) payload[field.key] = form[field.key].trim()
    }
    const result = await createEntry(payload)
    if (!result.ok || !result.entry) {
      error.value = result.message
      return
    }
    emit('created', result.entry)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登记失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
