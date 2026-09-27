<template>
  <section class="page" data-module="sludge-detail">
    <header class="page-head">
      <div>
        <h2>脱水机组详情</h2>
        <p class="page-desc">
          <RouterLink to="/sludge" class="link">← 返回污泥脱水列表</RouterLink>
        </p>
      </div>
      <div class="page-actions">
        <template v-if="entry && entry.available_actions?.length">
          <button
            v-for="action in entry.available_actions"
            :key="action"
            class="btn"
            :class="{ primary: action === '加药' }"
            type="button"
            @click="onAction(action)"
          >
            {{ action }}
          </button>
        </template>
        <span v-else-if="entry" class="tag readonly">已停机归档，仅供查询</span>
      </div>
    </header>

    <div v-if="entry" class="detail-grid">
      <div v-for="column in columns" :key="column" class="detail-item">
        <span>{{ column }}</span>
        <strong>{{ entry[column] ?? '—' }}</strong>
      </div>
    </div>
    <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <footer class="page-foot">
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="entry && errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <DosingDialog
      v-if="showDosing && entry"
      :entry="entry"
      @close="showDosing = false"
      @saved="onDosingSaved"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

import DosingDialog from './DosingDialog.vue'

type Entry = Record<string, string | number | null> & {
  id: string | number
  readonly?: boolean
  available_actions?: string[]
}

const columns = ["机组编号", "所属厂站", "机组类型", "进泥量", "出泥含水率", "絮凝剂用量", "运行功率", "机组状态"]

const route = useRoute()

const entry = ref<Entry | null>(null)
const errorMessage = ref('')
const noticeMessage = ref('')
const showDosing = ref(false)

function onAction(action: string) {
  if (action === '加药') {
    showDosing.value = true
    return
  }
  void postAction(action)
}

async function postAction(action: string) {
  if (!entry.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`/api/sludge/${entry.value.id}/actions`, {
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

async function onDosingSaved(message: string) {
  showDosing.value = false
  noticeMessage.value = message
  errorMessage.value = ''
  await reload()
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/sludge/${route.params.id}`)
    const result = await response.json()
    if (!response.ok) {
      throw new Error(result.detail ?? '脱水机组详情读取失败')
    }
    entry.value = result
  } catch (error) {
    entry.value = null
    errorMessage.value = error instanceof Error ? error.message : '脱水机组详情读取失败'
  }
}

onMounted(reload)
</script>
