<template>
  <div v-if="open" class="modal-mask" @click.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>加药登记 · 机组 {{ row?.机组编号 ?? '' }}</h3>
        <button class="modal-close" type="button" @click="close">×</button>
      </header>
      <div v-if="loading" class="modal-tip">正在读取最新机组状态…</div>
      <template v-else-if="row">
        <p class="modal-tip">
          当前状态：<strong>{{ row.机组状态 }}</strong>。提交后机组转为「已停机」，
          絮凝剂用量随运行记录长期保留；已停机记录此后只读。
        </p>
        <div v-if="!eligibility.allowed" class="modal-block">
          <p class="error-text">{{ eligibility.reason }}</p>
          <button class="btn" type="button" @click="close">关闭</button>
        </div>
        <form v-else class="modal-form" @submit.prevent="submit">
          <label class="form-field">
            <span>絮凝剂用量(kg)<em>*</em></span>
            <input
              v-model="form.絮凝剂用量"
              inputmode="decimal"
              placeholder="本次运行絮凝剂总用量，整额登记"
            />
          </label>
          <label class="form-field">
            <span>出泥含水率(%)</span>
            <input
              v-if="!row.出泥含水率 && row.出泥含水率 !== 0"
              v-model="form.出泥含水率"
              inputmode="decimal"
              placeholder="停机前可补录，提交后不可修改"
            />
            <input v-else :value="`已记录 ${row.出泥含水率}%，不允许覆盖`" disabled />
          </label>
          <p v-if="error" class="error-text">{{ error }}</p>
          <footer class="modal-foot">
            <button class="btn" type="button" :disabled="submitting" @click="close">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '确认加药并停机' }}
            </button>
          </footer>
        </form>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import {
  ACTION_DOSE,
  doseEligibility,
  fetchDetail,
  isBlank,
  submitAction,
  type DoseForm,
  type SludgeRow,
} from './sludge'

const props = defineProps<{ open: boolean; entryId: number | null }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done', row: SludgeRow): void
}>()

const row = ref<SludgeRow | null>(null)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const form = reactive<DoseForm>({ 絮凝剂用量: '', 出泥含水率: '' })

const eligibility = computed(() =>
  row.value ? doseEligibility(row.value) : { allowed: false, reason: '' },
)

watch(
  () => props.open,
  async (open) => {
    if (!open || props.entryId == null) return
    error.value = ''
    form.絮凝剂用量 = ''
    form.出泥含水率 = ''
    row.value = null
    loading.value = true
    try {
      // 无论从列表还是详情进来，都重新拉一次服务端最新状态再判断，
      // 保证两个入口给出的结论完全一致。
      row.value = await fetchDetail(props.entryId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '机组明细读取失败'
    } finally {
      loading.value = false
    }
  },
)

function close() {
  if (submitting.value) return
  emit('close')
}

async function submit() {
  if (!row.value) return
  error.value = ''
  if (isBlank(form.絮凝剂用量)) {
    error.value = '请填写絮凝剂用量'
    return
  }
  if (Number.isNaN(Number(form.絮凝剂用量)) || Number(form.絮凝剂用量) < 0) {
    error.value = '絮凝剂用量必须是不小于 0 的数值'
    return
  }
  if (!isBlank(form.出泥含水率)) {
    const moisture = Number(form.出泥含水率)
    if (Number.isNaN(moisture) || moisture < 0 || moisture > 100) {
      error.value = '出泥含水率必须是 0~100 之间的数值'
      return
    }
  }
  submitting.value = true
  try {
    const values: Record<string, string> = { 絮凝剂用量: form.絮凝剂用量.trim() }
    if (!isBlank(form.出泥含水率)) values.出泥含水率 = form.出泥含水率.trim()
    const result = await submitAction(row.value.id, ACTION_DOSE, values)
    if (!result.ok || !result.entry) {
      error.value = result.message
      // 服务端可能已被别处先操作（如已停机），刷新状态保持口径一致。
      row.value = await fetchDetail(row.value.id)
      return
    }
    emit('done', result.entry)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加药登记失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
