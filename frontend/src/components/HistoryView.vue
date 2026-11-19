<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'

const records = ref([])
const loading = ref(true)
const error = ref('')
let refreshTimer = null

const successCount = computed(
  () => records.value.filter((record) => record.status === 'success').length,
)
const failureCount = computed(
  () => records.value.filter((record) => record.status === 'failure').length,
)
const unknownCount = computed(
  () => records.value.filter((record) => record.status === 'unknown').length,
)

onMounted(async () => {
  await loadHistory()
  refreshTimer = window.setInterval(() => loadHistory(true), 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) window.clearInterval(refreshTimer)
})

async function loadHistory(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    records.value = await api.history.list()
  } catch (loadError) {
    error.value = loadError.message
  } finally {
    if (!silent) loading.value = false
  }
}

function statusMeta(status) {
  return {
    success: { label: '成功', className: 'normal' },
    failure: { label: '失败', className: 'abnormal' },
    unknown: { label: '未知', className: 'unknown' },
  }[status]
}

function formatLatency(value) {
  return value === null || value === undefined ? '—' : `${Number(value).toFixed(1)} ms`
}

function formatTime(timestamp) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(timestamp * 1000))
}
</script>

<template>
  <section class="history-view">
    <div class="history-heading">
      <div>
        <span class="eyebrow">检测记录</span>
        <h1>最近历史</h1>
        <p>显示最近 200 条检测结果，记录默认保留 30 天。</p>
      </div>
      <button class="refresh-button" type="button" :disabled="loading" @click="loadHistory()">
        <svg viewBox="0 0 24 24"><path d="M20 6v5h-5M4 18v-5h5" /><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11M5.5 15A7 7 0 0 0 18 17.5l2-4.5" /></svg>
        刷新
      </button>
    </div>

    <div class="history-summary">
      <div><span class="summary-dot all"></span><strong>{{ records.length }}</strong><small>当前显示</small></div>
      <div><span class="summary-dot enabled"></span><strong>{{ successCount }}</strong><small>成功</small></div>
      <div><span class="summary-dot abnormal"></span><strong>{{ failureCount }}</strong><small>失败</small></div>
      <div><span class="summary-dot unknown"></span><strong>{{ unknownCount }}</strong><small>未知</small></div>
    </div>

    <div v-if="error" class="inline-alert">
      <span>{{ error }}</span><button type="button" @click="loadHistory()">重新加载</button>
    </div>

    <div class="history-panel">
      <div v-if="loading" class="panel-state">
        <span class="boot-spinner small"></span><p>正在加载历史…</p>
      </div>
      <div v-else-if="records.length === 0" class="panel-state empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg></div>
        <h2>暂无检测记录</h2><p>启用入口后，系统会每 60 秒自动生成检测记录。</p>
      </div>
      <template v-else>
        <div class="history-table-wrap">
          <table class="history-table">
            <thead><tr><th>检测时间</th><th>入口</th><th>地址</th><th>结果</th><th>延迟</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td class="history-time">{{ formatTime(record.checked_at) }}</td>
                <td><strong>{{ record.target_name }}</strong></td>
                <td><div class="target-address"><code>{{ record.ip }}:{{ record.port }}</code><span class="protocol-badge" :class="record.protocol.toLowerCase()">{{ record.protocol }}</span></div></td>
                <td><span class="monitor-badge" :class="statusMeta(record.status).className"><i></i>{{ statusMeta(record.status).label }}</span></td>
                <td class="history-latency">{{ formatLatency(record.latency_ms) }}</td>
                <td class="history-message">{{ record.error_message || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="history-mobile-list">
          <article v-for="record in records" :key="record.id" class="history-mobile-card">
            <header><div><strong>{{ record.target_name }}</strong><small>{{ record.ip }}:{{ record.port }} · {{ record.protocol }}</small></div><span class="monitor-badge" :class="statusMeta(record.status).className"><i></i>{{ statusMeta(record.status).label }}</span></header>
            <div class="history-mobile-meta"><span>{{ formatTime(record.checked_at) }}</span><strong>{{ formatLatency(record.latency_ms) }}</strong></div>
            <p>{{ record.error_message || '检测完成' }}</p>
          </article>
        </div>
      </template>
    </div>
  </section>
</template>
