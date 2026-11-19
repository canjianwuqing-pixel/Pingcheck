<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import ConfirmDialog from './ConfirmDialog.vue'
import TargetModal from './TargetModal.vue'

const targets = ref([])
const loading = ref(true)
const loadError = ref('')
const modalOpen = ref(false)
const editingTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const deletingTarget = ref(null)
const deleting = ref(false)
const deleteError = ref('')
const togglingId = ref(null)
const checkingId = ref(null)
let refreshTimer = null

const normalCount = computed(
  () => targets.value.filter((target) => target.enabled && target.status === 'normal').length,
)
const abnormalCount = computed(
  () => targets.value.filter((target) => target.enabled && target.status === 'abnormal').length,
)

onMounted(async () => {
  await loadTargets()
  refreshTimer = window.setInterval(() => loadTargets(true), 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) window.clearInterval(refreshTimer)
})

async function loadTargets(silent = false) {
  if (!silent) loading.value = true
  loadError.value = ''
  try {
    targets.value = await api.targets.list()
  } catch (error) {
    loadError.value = error.message
  } finally {
    if (!silent) loading.value = false
  }
}

function replaceTarget(updated) {
  const index = targets.value.findIndex((target) => target.id === updated.id)
  if (index !== -1) targets.value[index] = updated
}

function openAdd() {
  editingTarget.value = null
  saveError.value = ''
  modalOpen.value = true
}

function openEdit(target) {
  editingTarget.value = target
  saveError.value = ''
  modalOpen.value = true
}

async function saveTarget(payload) {
  saving.value = true
  saveError.value = ''
  try {
    if (editingTarget.value) {
      replaceTarget(await api.targets.update(editingTarget.value.id, payload))
    } else {
      targets.value.unshift(await api.targets.create(payload))
    }
    modalOpen.value = false
  } catch (error) {
    saveError.value = error.message
  } finally {
    saving.value = false
  }
}

async function toggleTarget(target) {
  if (togglingId.value !== null) return
  togglingId.value = target.id
  loadError.value = ''
  try {
    replaceTarget(await api.targets.setEnabled(target.id, !target.enabled))
  } catch (error) {
    loadError.value = error.message
  } finally {
    togglingId.value = null
  }
}

async function checkNow(target) {
  if (!target.enabled || checkingId.value !== null) return
  checkingId.value = target.id
  loadError.value = ''
  try {
    replaceTarget(await api.targets.check(target.id))
  } catch (error) {
    loadError.value = error.message
  } finally {
    checkingId.value = null
  }
}

function askDelete(target) {
  deletingTarget.value = target
  deleteError.value = ''
}

async function confirmDelete() {
  if (!deletingTarget.value) return
  deleting.value = true
  deleteError.value = ''
  try {
    await api.targets.remove(deletingTarget.value.id)
    targets.value = targets.value.filter((target) => target.id !== deletingTarget.value.id)
    deletingTarget.value = null
  } catch (error) {
    deleteError.value = error.message
  } finally {
    deleting.value = false
  }
}

function statusMeta(target) {
  const states = {
    pending: { label: '待检测', className: 'pending' },
    normal: { label: '正常', className: 'normal' },
    warning: { label: '待确认', className: 'warning' },
    abnormal: { label: '异常', className: 'abnormal' },
    unknown: { label: '未知', className: 'unknown' },
  }
  return states[target.status] || states.pending
}

function formatLatency(value) {
  return value === null || value === undefined ? '—' : `${Number(value).toFixed(1)} ms`
}

function formatEndpoint(target) {
  return target.protocol === 'ICMP' ? target.ip : `${target.ip}:${target.port}`
}

function formatCheckedAt(timestamp) {
  if (!timestamp) return '尚未检测'
  return new Intl.DateTimeFormat('zh-CN', {
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
  <section class="targets-view">
    <div class="targets-heading">
      <div>
        <span class="eyebrow">入口管理</span>
        <h1>网络监控</h1>
        <p>已启用入口每 60 秒自动检测，支持 ICMP Ping 和 TCP / UDP 端口。</p>
      </div>
      <button class="add-button" type="button" @click="openAdd">
        <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
        添加入口
      </button>
    </div>

    <div class="target-summary">
      <div><span class="summary-dot all"></span><strong>{{ targets.length }}</strong><small>全部入口</small></div>
      <div><span class="summary-dot enabled"></span><strong>{{ normalCount }}</strong><small>状态正常</small></div>
      <div><span class="summary-dot abnormal"></span><strong>{{ abnormalCount }}</strong><small>状态异常</small></div>
    </div>

    <div v-if="loadError" class="inline-alert">
      <span>{{ loadError }}</span>
      <button type="button" @click="loadTargets()">重新加载</button>
    </div>

    <div class="targets-panel">
      <div v-if="loading" class="panel-state">
        <span class="boot-spinner small"></span>
        <p>正在加载入口…</p>
      </div>

      <div v-else-if="targets.length === 0" class="panel-state empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="m8 11 8-4M8 13l8 4" /></svg>
        </div>
        <h2>还没有监控入口</h2>
        <p>添加第一个 ICMP、TCP 或 UDP 入口，开始网络监控。</p>
        <button class="text-button" type="button" @click="openAdd">添加入口</button>
      </div>

      <template v-else>
        <div class="target-table-wrap">
          <table class="target-table">
            <thead>
              <tr><th>入口</th><th>地址</th><th>检测状态</th><th>延迟 / 最近检测</th><th>监控</th><th class="actions-column">操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="target in targets" :key="target.id" :class="{ paused: !target.enabled }">
                <td>
                  <div class="target-name"><span class="target-avatar">{{ target.name.slice(0, 1) }}</span><div><strong>{{ target.name }}</strong><small>{{ target.note || '暂无备注' }}</small></div></div>
                </td>
                <td>
                  <div class="target-address"><code>{{ formatEndpoint(target) }}</code><span class="protocol-badge" :class="target.protocol.toLowerCase()">{{ target.protocol }}</span></div>
                </td>
                <td>
                  <div class="monitor-state">
                    <span class="monitor-badge" :class="statusMeta(target).className"><i></i>{{ statusMeta(target).label }}</span>
                    <small v-if="target.consecutive_failures">连续失败 {{ target.consecutive_failures }} 次</small>
                    <small v-else-if="target.status === 'unknown'">UDP 无响应不计失败</small>
                  </div>
                </td>
                <td><div class="monitor-metric"><strong>{{ formatLatency(target.last_latency_ms) }}</strong><small>{{ formatCheckedAt(target.last_checked_at) }}</small></div></td>
                <td>
                  <button class="switch-row" type="button" :disabled="togglingId !== null" @click="toggleTarget(target)">
                    <span class="switch" :class="{ on: target.enabled }"><i></i></span>
                    <span>{{ target.enabled ? '已启用' : '已暂停' }}</span>
                  </button>
                </td>
                <td>
                  <div class="row-actions monitor-actions">
                    <button class="check-now-button" type="button" :disabled="!target.enabled || checkingId !== null" @click="checkNow(target)">
                      <svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>
                      {{ checkingId === target.id ? '检测中' : '立即检测' }}
                    </button>
                    <button type="button" title="编辑" @click="openEdit(target)"><svg viewBox="0 0 24 24"><path d="m4 16-.7 4.7L8 20l11-11-4-4L4 16Z" /><path d="m13 7 4 4" /></svg></button>
                    <button class="delete" type="button" title="删除" @click="askDelete(target)"><svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" /></svg></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="target-mobile-list">
          <article v-for="target in targets" :key="target.id" class="target-mobile-card" :class="{ paused: !target.enabled }">
            <header>
              <div class="target-name"><span class="target-avatar">{{ target.name.slice(0, 1) }}</span><div><strong>{{ target.name }}</strong><small>{{ formatEndpoint(target) }} · {{ target.protocol }}</small></div></div>
              <span class="monitor-badge" :class="statusMeta(target).className"><i></i>{{ statusMeta(target).label }}</span>
            </header>
            <p>{{ target.note || '暂无备注' }}</p>
            <div class="mobile-monitor-metrics">
              <div><small>最近延迟</small><strong>{{ formatLatency(target.last_latency_ms) }}</strong></div>
              <div><small>最近检测</small><strong>{{ formatCheckedAt(target.last_checked_at) }}</strong></div>
              <div><small>连续失败</small><strong>{{ target.consecutive_failures }} 次</strong></div>
            </div>
            <button class="mobile-check-button" type="button" :disabled="!target.enabled || checkingId !== null" @click="checkNow(target)">
              <svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>
              {{ checkingId === target.id ? '正在检测…' : target.enabled ? '立即检测' : '入口已暂停' }}
            </button>
            <footer>
              <button class="switch-row" type="button" :disabled="togglingId !== null" @click="toggleTarget(target)"><span class="switch" :class="{ on: target.enabled }"><i></i></span><span>{{ target.enabled ? '已启用' : '已暂停' }}</span></button>
              <div class="row-actions"><button type="button" @click="openEdit(target)">编辑</button><button class="delete" type="button" @click="askDelete(target)">删除</button></div>
            </footer>
          </article>
        </div>
      </template>
    </div>

    <TargetModal :open="modalOpen" :target="editingTarget" :saving="saving" :error="saveError" @close="modalOpen = false" @save="saveTarget" />
    <ConfirmDialog :open="Boolean(deletingTarget)" :target-name="deletingTarget?.name" :deleting="deleting" :error="deleteError" @cancel="deletingTarget = null" @confirm="confirmDelete" />
  </section>
</template>
