<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const hasToken = ref(false)
const error = ref('')
const success = ref('')

const form = reactive({
  botToken: '',
  chatId: '',
  enabled: false,
})

const canTest = computed(() => hasToken.value && Boolean(form.chatId.trim()))

onMounted(loadSettings)

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const settings = await api.telegram.getSettings()
    form.chatId = settings.chat_id
    form.enabled = settings.enabled
    form.botToken = ''
    hasToken.value = settings.has_token
  } catch (loadError) {
    error.value = loadError.message
  } finally {
    loading.value = false
  }
}

function clearMessage() {
  error.value = ''
  success.value = ''
}

async function saveSettings() {
  clearMessage()
  if (form.enabled && !hasToken.value && !form.botToken.trim()) {
    error.value = '启用通知前请填写 Bot Token'
    return
  }
  if (form.enabled && !form.chatId.trim()) {
    error.value = '启用通知前请填写 Chat ID'
    return
  }

  saving.value = true
  try {
    const payload = {
      chat_id: form.chatId.trim(),
      enabled: form.enabled,
    }
    if (form.botToken.trim()) payload.bot_token = form.botToken.trim()
    const settings = await api.telegram.updateSettings(payload)
    hasToken.value = settings.has_token
    form.botToken = ''
    form.chatId = settings.chat_id
    form.enabled = settings.enabled
    success.value = 'Telegram 设置已保存'
  } catch (saveError) {
    error.value = saveError.message
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  clearMessage()
  testing.value = true
  try {
    const result = await api.telegram.test()
    if (result.success) success.value = result.message
    else error.value = result.message
  } catch (testError) {
    error.value = testError.message
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <section class="telegram-view">
    <div class="telegram-heading">
      <div>
        <span class="eyebrow">消息通知</span>
        <h1>Telegram 设置</h1>
        <p>在 TCP 入口首次异常和恢复正常时接收一次通知。</p>
      </div>
      <span class="telegram-status" :class="{ enabled: form.enabled }">
        <i></i>{{ form.enabled ? '通知已启用' : '通知已关闭' }}
      </span>
    </div>

    <div v-if="loading" class="telegram-panel panel-state">
      <span class="boot-spinner small"></span>
      <p>正在加载设置…</p>
    </div>

    <div v-else class="telegram-layout">
      <form class="telegram-panel telegram-form" @submit.prevent="saveSettings">
        <div class="telegram-panel-heading">
          <div class="telegram-icon">
            <svg viewBox="0 0 24 24"><path d="m21 3-7.5 18-4-8-8-4L21 3Z" /><path d="m9.5 13 4-4" /></svg>
          </div>
          <div><h2>Bot 配置</h2><p>通过 Telegram Bot API 发送监控消息。</p></div>
        </div>

        <label class="form-field full">
          <span>Bot Token</span>
          <input
            v-model="form.botToken"
            type="password"
            maxlength="256"
            autocomplete="off"
            :placeholder="hasToken ? '已安全保存，留空则不修改' : '请输入 BotFather 提供的 Token'"
            @input="clearMessage"
          />
          <small class="telegram-field-note">
            {{ hasToken ? 'Token 已配置，页面不会读取或回显原值。' : 'Token 保存后不会在页面中明文回显。' }}
          </small>
        </label>

        <label class="form-field full">
          <span>Chat ID</span>
          <input v-model="form.chatId" maxlength="100" placeholder="例如：-1001234567890" @input="clearMessage" />
          <small class="telegram-field-note">支持个人、群组或频道的 Chat ID。</small>
        </label>

        <div class="telegram-toggle-row">
          <div><strong>启用 Telegram 通知</strong><small>仅 TCP 首次异常和恢复时发送，UDP 未知不会告警。</small></div>
          <button class="settings-switch" :class="{ on: form.enabled }" type="button" role="switch" :aria-checked="form.enabled" @click="form.enabled = !form.enabled; clearMessage()">
            <i></i>
          </button>
        </div>

        <div v-if="error" class="settings-message error" role="alert">{{ error }}</div>
        <div v-if="success" class="settings-message success" role="status">{{ success }}</div>

        <div class="telegram-actions">
          <button class="secondary-button test-button" type="button" :disabled="!canTest || testing || saving" @click="sendTest">
            <svg viewBox="0 0 24 24"><path d="m21 3-7.5 18-4-8-8-4L21 3Z" /><path d="m9.5 13 4-4" /></svg>
            {{ testing ? '正在发送…' : '发送测试消息' }}
          </button>
          <button class="primary-button compact" type="submit" :disabled="saving || testing">
            {{ saving ? '正在保存…' : '保存设置' }}
          </button>
        </div>
      </form>

      <aside class="notification-rules">
        <h2>通知规则</h2>
        <ul>
          <li><span class="rule-icon alert">!</span><div><strong>异常告警</strong><p>TCP 连续失败达到 3 次，首次进入异常时发送。</p></div></li>
          <li><span class="rule-icon recovery">✓</span><div><strong>恢复通知</strong><p>已告警入口恢复连接后发送一次。</p></div></li>
          <li><span class="rule-icon unknown">?</span><div><strong>UDP 未知</strong><p>无响应只标记未知，不发送故障告警。</p></div></li>
        </ul>
        <p class="rules-footnote">暂停和删除入口不会发送通知。持续异常不会重复提醒。</p>
      </aside>
    </div>
  </section>
</template>
