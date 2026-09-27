<template>
  <section class="page" data-module="sludge">
    <header class="page-head">
      <div>
        <h2>污泥脱水管理</h2>
        <p class="page-desc">
          一台机组同期只保留一条在办运行记录；加药登记后自动停机归档，历史记录可查不可改。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = true">登记脱水机组</button>
        <button class="btn" type="button" @click="exportRows">导出污泥脱水清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">运行中机组</span>
        <strong class="stat-value">{{ stats['运行中机组'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">在办记录</span>
        <strong class="stat-value">{{ stats['在办记录'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已停机历史记录</span>
        <strong class="stat-value">{{ stats['已停机记录'] ?? 0 }}</strong>
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
          <option v-for="status in STATUS_OPTIONS" :key="status" :value="status">{{ status }}</option>
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
        <tr v-for="row in rows" :key="row.id">
          <td>
            <RouterLink class="link" :to="`/sludge/${row.id}`">{{ row.机组编号 }}</RouterLink>
          </td>
          <td>{{ row.所属厂站 ?? '—' }}</td>
          <td>{{ row.机组类型 ?? '—' }}</td>
          <td>{{ formatNumber(row.进泥量) }}</td>
          <td>{{ formatNumber(row.出泥含水率, '%') }}</td>
          <td>{{ formatNumber(row.絮凝剂用量) }}</td>
          <td>{{ formatNumber(row.运行功率) }}</td>
          <td>
            <span class="status-tag" :data-status="row.机组状态">{{ row.机组状态 }}</span>
          </td>
          <td class="row-actions">
            <template v-for="action in availableActions(row)" :key="action">
              <button v-if="action === ACTION_DOSE" class="link" type="button" @click="openDose(row)">
                {{ action }}
              </button>
              <button v-else class="link" type="button" @click="runSimpleAction(action, row)">
                {{ action }}
              </button>
            </template>
            <span v-if="row.readonly" class="readonly-hint">已归档，仅查询</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的污泥脱水记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条运行记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <CreateDialog :open="showCreate" @close="showCreate = false" @created="onCreated" />
    <DoseDialog :open="showDose" :entry-id="doseId" @close="showDose = false" @done="onDoseDone" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import CreateDialog from './CreateDialog.vue'
import DoseDialog from './DoseDialog.vue'
import {
  ACTION_DOSE,
  ACTION_FEED,
  STATUS_OPTIONS,
  availableActions,
  fetchList,
  fetchStats,
  submitAction,
  type SludgeRow,
} from './sludge'

const columns = ['机组编号', '所属厂站', '机组类型', '进泥量(t)', '出泥含水率', '絮凝剂用量(kg)', '运行功率(kW)', '机组状态']

const router = useRouter()
const rows = ref<SludgeRow[]>([])
const total = ref(0)
const stats = ref<Record<string, number>>({})
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const showCreate = ref(false)
const showDose = ref(false)
const doseId = ref<number | null>(null)

function formatNumber(value: number | null, suffix = ''): string {
  if (value === null || value === undefined) return '—'
  return suffix ? `${value}${suffix}` : String(value)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open('/api/sludge/export', '_blank')
}

async function reload() {
  errorMessage.value = ''
  try {
    const [list, stat] = await Promise.all([
      fetchList({ keyword: keyword.value, status: statusFilter.value }),
      fetchStats(),
    ])
    rows.value = list.items
    total.value = list.total
    stats.value = stat
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥脱水列表读取失败'
  }
}

function onCreated(entry: SludgeRow) {
  showCreate.value = false
  void reload()
  void router.push(`/sludge/${entry.id}`)
}

function openDose(row: SludgeRow) {
  doseId.value = row.id
  showDose.value = true
}

function onDoseDone() {
  showDose.value = false
  void reload()
}

async function runSimpleAction(action: string, row: SludgeRow) {
  errorMessage.value = ''
  try {
    const values =
      action === ACTION_FEED && row.进泥量 === null
        ? promptFeedAmount()
        : {}
    if (values === null) return
    const result = await submitAction(row.id, action, values)
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥脱水操作失败'
  }
}

function promptFeedAmount(): Record<string, string> | null {
  // 待进料机组启动时补登本次进泥量；取消则放弃动作，不产生半截记录。
  const input = window.prompt('请输入本次运行进泥量(t)，整额登记到该条记录：')
  if (input === null) return null
  if (input.trim() !== '' && Number.isNaN(Number(input))) {
    errorMessage.value = '进泥量必须是数值'
    return null
  }
  return input.trim() ? { 进泥量: input.trim() } : {}
}

onMounted(reload)
</script>
