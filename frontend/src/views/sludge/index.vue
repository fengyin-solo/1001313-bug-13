<template>
  <section class="page" data-module="sludge">
    <header class="page-head">
      <div>
        <h2>污泥脱水管理</h2>
        <p class="page-desc">维护脱水机组：同一机组同期只留一条在办记录，加药完成后自动停机归档，归档记录仅供查询。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记脱水机组</button>
        <button class="btn" type="button" @click="exportRows">导出污泥脱水清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>机组编号</span>
        <input v-model="keyword" placeholder="按机组编号检索" />
      </label>
      <label class="filter-item">
        <span>机组状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" class="clickable" @click="openDetail(row)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '机组状态'" class="tag" :class="{ readonly: row.readonly }">
              {{ row[column] ?? '—' }}
            </span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions" @click.stop>
            <template v-if="row.available_actions?.length">
              <button
                v-for="action in row.available_actions"
                :key="action"
                class="link"
                type="button"
                @click="onAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="muted">已停机归档，仅供查询</span>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无污泥脱水数据，可先登记脱水机组</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条污泥脱水记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="dialog-mask" @click.self="closeCreate">
      <div class="dialog">
        <h3>登记脱水机组</h3>
        <form class="dialog-form" @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.name }}<template v-if="field.required">（必填）</template></span>
            <input v-model="createForm[field.name]" :placeholder="field.placeholder" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <div class="dialog-actions">
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="creating">
              {{ creating ? '提交中…' : '确认登记' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <DosingDialog
      v-if="dosingRow"
      :entry="dosingRow"
      @close="dosingRow = null"
      @saved="onDosingSaved"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

import DosingDialog from './DosingDialog.vue'

type Row = Record<string, string | number | null> & {
  id: string | number
  readonly?: boolean
  available_actions?: string[]
}

const ENDPOINT = '/api/sludge'
const columns = ["机组编号", "所属厂站", "机组类型", "进泥量", "出泥含水率", "絮凝剂用量", "运行功率", "机组状态"]
const statuses = ["待进料", "运行中", "冲洗中", "已停机"]
const createFields = [
  { name: '机组编号', required: true, placeholder: '如 SLUD-0004' },
  { name: '所属厂站', required: true, placeholder: '如 城东污水厂' },
  { name: '机组类型', required: true, placeholder: '如 离心脱水机' },
  { name: '进泥量', required: false, placeholder: '选填，单位 m³' },
  { name: '出泥含水率', required: false, placeholder: '选填，单位 %' },
  { name: '絮凝剂用量', required: false, placeholder: '选填，单位 kg' },
  { name: '运行功率', required: false, placeholder: '选填，单位 kW' },
]

const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '在办机组', value: 0 },
  { label: '运行中机组', value: 0 },
  { label: '已停机归档', value: 0 },
])
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref<Record<string, string>>({})
const dosingRow = ref<Row | null>(null)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

function openDetail(row: Row) {
  void router.push(`/sludge/${row.id}`)
}

function onAction(action: string, row: Row) {
  if (action === '加药') {
    dosingRow.value = row
    return
  }
  void postAction(action, row)
}

async function postAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? '污泥脱水动作未生效，请稍后重试')
    }
    noticeMessage.value = result.message ?? '操作已完成'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥脱水操作失败'
  }
}

async function submitCreate() {
  if (creating.value) return
  createError.value = ''
  creating.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? '脱水机组登记失败')
    }
    noticeMessage.value = result.message ?? '脱水机组已登记'
    closeCreate()
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '脱水机组登记失败'
  } finally {
    creating.value = false
  }
}

async function onDosingSaved(message: string) {
  dosingRow.value = null
  noticeMessage.value = message
  errorMessage.value = ''
  await reload()
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('脱水机组列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥脱水列表读取失败'
  }
  await loadStats()
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const items: Row[] = payload.items ?? []
    const archived = items.filter((item) => item.readonly).length
    const running = items.filter((item) => item['机组状态'] === '运行中').length
    stats.value = [
      { label: '在办机组', value: items.length - archived },
      { label: '运行中机组', value: running },
      { label: '已停机归档', value: archived },
    ]
  } catch {
    // 统计卡片读取失败不影响列表本身
  }
}

onMounted(reload)
</script>
