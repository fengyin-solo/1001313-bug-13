<template>
  <section class="page" data-module="sludge-detail">
    <header class="page-head">
      <div>
        <h2>脱水机组运行明细</h2>
        <p class="page-desc">
          <RouterLink class="link" to="/sludge">返回污泥脱水台账</RouterLink>
        </p>
      </div>
      <span v-if="row" class="status-tag" :data-status="row.机组状态">{{ row.机组状态 }}</span>
    </header>

    <div v-if="loading" class="detail-loading">正在加载运行记录…</div>
    <div v-else-if="!row" class="detail-missing">
      <p class="error-text">{{ errorMessage || '记录不存在或已归档' }}</p>
      <RouterLink class="btn" to="/sludge">返回列表</RouterLink>
    </div>

    <template v-else>
      <div v-if="row.readonly" class="readonly-banner">
        该运行记录已停机归档，仅供查询，不能再执行任何动作；历史出泥含水率受保护。
      </div>

      <article class="detail-card">
        <dl class="detail-grid">
          <template v-for="field in fields" :key="field">
            <div class="detail-item">
              <dt>{{ field }}</dt>
              <dd>{{ display(row, field) }}</dd>
            </div>
          </template>
        </dl>
      </article>

      <article class="detail-card">
        <h3 class="detail-subtitle">运行操作</h3>
        <div v-if="actions.length" class="detail-actions">
          <button
            v-for="action in actions"
            :key="action"
            class="btn"
            :class="{ primary: action === ACTION_DOSE }"
            type="button"
            @click="onAction(action)"
          >
            {{ action }}
          </button>
        </div>
        <p v-else class="detail-muted">该记录已结束，没有可执行的动作。</p>
        <p v-if="actionMessage" class="error-text">{{ actionMessage }}</p>
      </article>
    </template>

    <DoseDialog :open="showDose" :entry-id="entryId" @close="showDose = false" @done="onDoseDone" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DoseDialog from './DoseDialog.vue'
import {
  ACTION_DOSE,
  ACTION_FEED,
  availableActions,
  fetchDetail,
  submitAction,
  type SludgeRow,
} from './sludge'

const route = useRoute()
const router = useRouter()

const entryId = computed(() => Number(route.params.id))
const row = ref<SludgeRow | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const actionMessage = ref('')
const showDose = ref(false)

// 详情页与列表页读同一份字段清单，避免两处展示/判断口径不一致。
const fields = ['机组编号', '所属厂站', '机组类型', '进泥量(t)', '出泥含水率', '絮凝剂用量(kg)', '运行功率(kW)', '开始时间', '结束时间']

const actions = computed(() => (row.value ? availableActions(row.value) : []))

function display(data: SludgeRow, label: string): string {
  if (label === '进泥量(t)') return data.进泥量 === null ? '—' : `${data.进泥量} t`
  if (label === '出泥含水率') return data.出泥含水率 === null ? '—' : `${data.出泥含水率}%`
  if (label === '絮凝剂用量(kg)') return data.絮凝剂用量 === null ? '—' : `${data.絮凝剂用量} kg`
  if (label === '运行功率(kW)') return data.运行功率 === null ? '—' : `${data.运行功率} kW`
  const key = label as keyof SludgeRow
  const value = data[key]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    row.value = await fetchDetail(entryId.value)
  } catch (error) {
    row.value = null
    errorMessage.value = error instanceof Error ? error.message : '脱水机组明细读取失败'
  } finally {
    loading.value = false
  }
}

function onAction(action: string) {
  actionMessage.value = ''
  if (action === ACTION_DOSE) {
    showDose.value = true
    return
  }
  void runSimpleAction(action)
}

async function runSimpleAction(action: string) {
  if (!row.value) return
  try {
    let values: Record<string, string> = {}
    if (action === ACTION_FEED && row.value.进泥量 === null) {
      const input = window.prompt('请输入本次运行进泥量(t)，整额登记到该条记录：')
      if (input === null) return
      if (input.trim() !== '' && Number.isNaN(Number(input))) {
        actionMessage.value = '进泥量必须是数值'
        return
      }
      if (input.trim()) values = { 进泥量: input.trim() }
    }
    const result = await submitAction(row.value.id, action, values)
    if (!result.ok) {
      actionMessage.value = result.message
    }
    await load()
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '操作失败，请稍后重试'
  }
}

function onDoseDone(updated: SludgeRow) {
  showDose.value = false
  row.value = updated
  void load()
}

watch(entryId, () => void load())
onMounted(load)

// 路由参数非法时回到列表，避免 Number(NaN) 发出无意义请求。
if (!Number.isInteger(entryId.value)) {
  void router.replace('/sludge')
}
</script>
