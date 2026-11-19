<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const hasToken = ref(false)
const hasProxyPassword = ref(false)
const hasSsPassword = ref(false)
const error = ref('')
const success = ref('')

const form = reactive({
  botToken: '',
  chatId: '',
  enabled: false,
  proxyType: 'direct',
  proxyHost: '',
  proxyPort: '',
  proxyUsername: '',
  proxyPassword: '',
  ssServer: '',
  ssPort: '',
  ssMethod: 'aes-256-gcm',
  ssPassword: '',
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
    form.proxyType = settings.proxy_type
    form.proxyHost = settings.proxy_host
    form.proxyPort = settings.proxy_port ?? ''
    form.proxyUsername = settings.proxy_username
    form.proxyPassword = ''
    hasProxyPassword.value = settings.has_proxy_password
    form.ssServer = settings.ss_server
    form.ssPort = settings.ss_port ?? ''
    form.ssMethod = settings.ss_method
    form.ssPassword = ''
    hasSsPassword.value = settings.has_ss_password
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
  if (!['direct', 'ss'].includes(form.proxyType) && !form.proxyHost.trim()) {
    error.value = '使用代理时请填写代理地址'
    return
  }
  const proxyPort = Number(form.proxyPort)
  if (!['direct', 'ss'].includes(form.proxyType) && (!Number.isInteger(proxyPort) || proxyPort < 1 || proxyPort > 65535)) {
    error.value = '代理端口应为 1 到 65535 之间的整数'
    return
  }
  if (form.proxyType === 'ss' && !form.ssServer.trim()) {
    error.value = '使用 Shadowsocks 时请填写服务器地址'
    return
  }
  const ssPort = Number(form.ssPort)
  if (form.proxyType === 'ss' && (!Number.isInteger(ssPort) || ssPort < 1 || ssPort > 65535)) {
    error.value = 'SS 端口应为 1 到 65535 之间的整数'
    return
  }
  if (form.proxyType === 'ss' && !hasSsPassword.value && !form.ssPassword) {
    error.value = '使用 Shadowsocks 时请填写密码'
    return
  }

  saving.value = true
  try {
    const payload = {
      chat_id: form.chatId.trim(),
      enabled: form.enabled,
      proxy_type: form.proxyType,
      proxy_host: ['direct', 'ss'].includes(form.proxyType) ? '' : form.proxyHost.trim(),
      proxy_port: ['direct', 'ss'].includes(form.proxyType) ? null : proxyPort,
      proxy_username: ['direct', 'ss'].includes(form.proxyType) ? '' : form.proxyUsername.trim(),
      ss_server: form.ssServer.trim(),
      ss_port: form.ssPort === '' ? null : ssPort,
      ss_method: form.ssMethod,
    }
    if (form.botToken.trim()) payload.bot_token = form.botToken.trim()
    if (form.proxyPassword) payload.proxy_password = form.proxyPassword
    if (form.ssPassword) payload.ss_password = form.ssPassword
    const settings = await api.telegram.updateSettings(payload)
    hasToken.value = settings.has_token
    hasProxyPassword.value = settings.has_proxy_password
    hasSsPassword.value = settings.has_ss_password
    form.botToken = ''
    form.chatId = settings.chat_id
    form.enabled = settings.enabled
    form.proxyType = settings.proxy_type
    form.proxyHost = settings.proxy_host
    form.proxyPort = settings.proxy_port ?? ''
    form.proxyUsername = settings.proxy_username
    form.proxyPassword = ''
    form.ssServer = settings.ss_server
    form.ssPort = settings.ss_port ?? ''
    form.ssMethod = settings.ss_method
    form.ssPassword = ''
    success.value = form.proxyType === 'ss' ? '设置已保存，SS 客户端正在安全重载' : 'Telegram 设置已保存'
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
        <p>在 ICMP / TCP 入口首次异常和恢复正常时接收一次通知。</p>
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

        <div class="telegram-section-heading full">
          <div><strong>连接方式</strong><small>代理只用于 Telegram 通知，不影响 ICMP / TCP / UDP 检测。</small></div>
        </div>

        <label class="form-field full">
          <span>Telegram 连接</span>
          <select v-model="form.proxyType" @change="clearMessage">
            <option value="direct">直连</option>
            <option value="http">HTTP 代理</option>
            <option value="https">HTTPS 代理</option>
            <option value="socks5">SOCKS5 代理</option>
            <option value="ss">Shadowsocks（SS）</option>
          </select>
          <small v-if="form.proxyType === 'socks5'" class="telegram-field-note">
            使用 socks5h，由代理端解析 Telegram 域名；可连接本地 Shadowsocks 客户端提供的 SOCKS5 端口。
          </small>
        </label>

        <div v-if="!['direct', 'ss'].includes(form.proxyType)" class="proxy-fields full">
          <label class="form-field">
            <span>代理地址</span>
            <input v-model="form.proxyHost" maxlength="255" placeholder="例如：host.docker.internal" autocomplete="off" @input="clearMessage" />
          </label>
          <label class="form-field">
            <span>代理端口</span>
            <input v-model="form.proxyPort" type="number" min="1" max="65535" placeholder="例如：1080" inputmode="numeric" @input="clearMessage" />
          </label>
          <label class="form-field">
            <span>用户名（可选）</span>
            <input v-model="form.proxyUsername" maxlength="255" autocomplete="off" placeholder="代理用户名" @input="clearMessage" />
          </label>
          <label class="form-field">
            <span>密码（可选）</span>
            <input
              v-model="form.proxyPassword"
              type="password"
              maxlength="256"
              autocomplete="new-password"
              :placeholder="hasProxyPassword ? '已保存，留空则不修改' : '代理密码'"
              @input="clearMessage"
            />
            <small v-if="hasProxyPassword" class="telegram-field-note">密码已配置，页面不会读取或回显原值。</small>
          </label>
        </div>

        <div v-if="form.proxyType === 'ss'" class="proxy-fields full">
          <label class="form-field">
            <span>SS 服务器</span>
            <input v-model="form.ssServer" maxlength="255" autocomplete="off" placeholder="例如：ss.example.com" @input="clearMessage" />
          </label>
          <label class="form-field">
            <span>SS 端口</span>
            <input v-model="form.ssPort" type="number" min="1" max="65535" inputmode="numeric" placeholder="例如：8388" @input="clearMessage" />
          </label>
          <label class="form-field">
            <span>加密方式</span>
            <select v-model="form.ssMethod" @change="clearMessage">
              <option value="aes-128-gcm">aes-128-gcm</option>
              <option value="aes-256-gcm">aes-256-gcm</option>
              <option value="chacha20-ietf-poly1305">chacha20-ietf-poly1305</option>
            </select>
          </label>
          <label class="form-field">
            <span>SS 密码</span>
            <input
              v-model="form.ssPassword"
              type="password"
              maxlength="256"
              autocomplete="new-password"
              :placeholder="hasSsPassword ? '已保存，留空则不修改' : '请输入 SS 密码'"
              @input="clearMessage"
            />
            <small v-if="hasSsPassword" class="telegram-field-note">密码已配置，页面不会读取或回显原值。</small>
          </label>
          <small class="telegram-field-note full">节点保存后自动同步到内部 shadowsocks-rust 客户端，无需编辑配置文件或重建镜像。</small>
        </div>

        <label class="form-field full">
          <span>Chat ID</span>
          <input v-model="form.chatId" maxlength="100" placeholder="例如：-1001234567890" @input="clearMessage" />
          <small class="telegram-field-note">支持个人、群组或频道的 Chat ID。</small>
        </label>

        <div class="telegram-toggle-row">
          <div><strong>启用 Telegram 通知</strong><small>ICMP / TCP 首次异常和恢复时发送，UDP 未知不会告警。</small></div>
          <button class="settings-switch" :class="{ on: form.enabled }" type="button" role="switch" :aria-checked="form.enabled" @click="form.enabled = !form.enabled; clearMessage()">
            <i></i>
          </button>
        </div>

        <div v-if="error" class="settings-message error" role="alert">{{ error }}</div>
        <div v-if="success" class="settings-message success" role="status">{{ success }}</div>

        <div class="telegram-actions">
          <button class="secondary-button test-button" type="button" :disabled="!canTest || testing || saving" @click="sendTest">
            <svg viewBox="0 0 24 24"><path d="m21 3-7.5 18-4-8-8-4L21 3Z" /><path d="m9.5 13 4-4" /></svg>
            {{ testing ? '正在发送…' : '测试通知' }}
          </button>
          <button class="primary-button compact" type="submit" :disabled="saving || testing">
            {{ saving ? '正在保存…' : '保存设置' }}
          </button>
        </div>
      </form>

      <aside class="notification-rules">
        <h2>通知规则</h2>
        <ul>
          <li><span class="rule-icon alert">!</span><div><strong>异常告警</strong><p>ICMP / TCP 连续失败达到 3 次，首次进入异常时发送。</p></div></li>
          <li><span class="rule-icon recovery">✓</span><div><strong>恢复通知</strong><p>已告警入口恢复连接后发送一次。</p></div></li>
          <li><span class="rule-icon unknown">?</span><div><strong>UDP 未知</strong><p>无响应只标记未知，不发送故障告警。</p></div></li>
        </ul>
        <p class="rules-footnote">暂停和删除入口不会发送通知。持续异常不会重复提醒。</p>
      </aside>
    </div>
  </section>
</template>
