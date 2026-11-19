<script setup>
import { computed, onMounted, ref } from 'vue'
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

const enabledCount = computed(() => targets.value.filter((target) => target.enabled).length)

onMounted(loadTargets)

async function loadTargets() {
  loading.value = true
  loadError.value = ''
  try {
    targets.value = await api.targets.list()
  } catch (error) {
    loadError.value = error.message
  } finally {
    loading.value = false
  }
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
      const updated = await api.targets.update(editingTarget.value.id, payload)
      const index = targets.value.findIndex((target) => target.id === updated.id)
      if (index !== -1) targets.value[index] = updated
    } else {
      const created = await api.targets.create(payload)
      targets.value.unshift(created)
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
    const updated = await api.targets.setEnabled(target.id, !target.enabled)
    const index = targets.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) targets.value[index] = updated
  } catch (error) {
    loadError.value = error.message
  } finally {
    togglingId.value = null
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
</script>

<template>
  <section class="targets-view">
    <div class="targets-heading">
      <div>
        <span class="eyebrow">入口管理</span>
        <h1>监控入口</h1>
        <p>维护需要监控的 TCP 和 UDP 网络入口。</p>
      </div>
      <button class="add-button" type="button" @click="openAdd">
        <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
        添加入口
      </button>
    </div>

    <div class="target-summary">
      <div><span class="summary-dot all"></span><strong>{{ targets.length }}</strong><small>全部入口</small></div>
      <div><span class="summary-dot enabled"></span><strong>{{ enabledCount }}</strong><small>已启用</small></div>
      <div><span class="summary-dot paused"></span><strong>{{ targets.length - enabledCount }}</strong><small>已暂停</small></div>
    </div>

    <div v-if="loadError" class="inline-alert">
      <span>{{ loadError }}</span>
      <button type="button" @click="loadTargets">重新加载</button>
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
        <p>添加第一个 TCP 或 UDP 入口，开始配置监控范围。</p>
        <button class="text-button" type="button" @click="openAdd">添加入口</button>
      </div>

      <template v-else>
        <div class="target-table-wrap">
          <table class="target-table">
            <thead>
              <tr><th>入口</th><th>地址</th><th>协议</th><th>状态</th><th class="actions-column">操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="target in targets" :key="target.id" :class="{ paused: !target.enabled }">
                <td>
                  <div class="target-name"><span class="target-avatar">{{ target.name.slice(0, 1) }}</span><div><strong>{{ target.name }}</strong><small>{{ target.note || '暂无备注' }}</small></div></div>
                </td>
                <td><code>{{ target.ip }}:{{ target.port }}</code></td>
                <td><span class="protocol-badge" :class="target.protocol.toLowerCase()">{{ target.protocol }}</span></td>
                <td>
                  <button class="switch-row" type="button" :disabled="togglingId !== null" @click="toggleTarget(target)">
                    <span class="switch" :class="{ on: target.enabled }"><i></i></span>
                    <span>{{ target.enabled ? '已启用' : '已暂停' }}</span>
                  </button>
                </td>
                <td>
                  <div class="row-actions">
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
            <header><div class="target-name"><span class="target-avatar">{{ target.name.slice(0, 1) }}</span><div><strong>{{ target.name }}</strong><small>{{ target.ip }}:{{ target.port }}</small></div></div><span class="protocol-badge" :class="target.protocol.toLowerCase()">{{ target.protocol }}</span></header>
            <p>{{ target.note || '暂无备注' }}</p>
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
