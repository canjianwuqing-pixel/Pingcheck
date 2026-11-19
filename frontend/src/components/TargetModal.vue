<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  open: Boolean,
  target: {
    type: Object,
    default: null,
  },
  saving: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'save'])

const form = reactive({
  name: '',
  ip: '',
  port: '',
  protocol: 'ICMP',
  note: '',
  enabled: true,
})
const fieldError = reactive({ name: '', ip: '', port: '' })
const editing = computed(() => Boolean(props.target))

watch(
  () => [props.open, props.target],
  () => {
    if (!props.open) return
    form.name = props.target?.name || ''
    form.ip = props.target?.ip || ''
    form.port = props.target?.port ?? ''
    form.protocol = props.target?.protocol || 'ICMP'
    form.note = props.target?.note || ''
    form.enabled = props.target?.enabled ?? true
    clearErrors()
  },
  { immediate: true },
)

function clearErrors() {
  fieldError.name = ''
  fieldError.ip = ''
  fieldError.port = ''
}

function isPossibleIp(value) {
  const text = value.trim()
  if (text.includes(':')) return /^[0-9a-f:]+$/i.test(text)
  const parts = text.split('.')
  return (
    parts.length === 4 &&
    parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
  )
}

function submit() {
  clearErrors()
  if (!form.name.trim()) fieldError.name = '请输入入口名称'
  if (!isPossibleIp(form.ip)) fieldError.ip = '请输入正确的 IP 地址'
  const port = form.protocol === 'ICMP' ? null : Number(form.port)
  if (form.protocol !== 'ICMP' && (!Number.isInteger(port) || port < 1 || port > 65535)) {
    fieldError.port = '端口范围为 1–65535'
  }
  if (fieldError.name || fieldError.ip || fieldError.port) return

  emit('save', {
    name: form.name.trim(),
    ip: form.ip.trim(),
    port,
    protocol: form.protocol,
    note: form.note.trim(),
    enabled: form.enabled,
  })
}

function chooseProtocol(protocol) {
  form.protocol = protocol
  fieldError.port = ''
  if (protocol !== 'ICMP' && !form.port) form.port = 80
}

function close() {
  if (!props.saving) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-backdrop" @mousedown.self="close">
        <section class="modal-card" role="dialog" aria-modal="true" :aria-labelledby="editing ? 'edit-target-title' : 'add-target-title'">
          <header class="modal-header">
            <div>
              <span class="eyebrow">入口配置</span>
              <h2 :id="editing ? 'edit-target-title' : 'add-target-title'">
                {{ editing ? '编辑监控入口' : '添加监控入口' }}
              </h2>
            </div>
            <button class="icon-button" type="button" aria-label="关闭" :disabled="saving" @click="close">
              <svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" /></svg>
            </button>
          </header>

          <form class="target-form" @submit.prevent="submit">
            <label class="form-field full">
              <span>名称 <b>*</b></span>
              <input v-model="form.name" maxlength="80" placeholder="例如：主机 Ping" @input="fieldError.name = ''" />
              <small v-if="fieldError.name" class="field-error">{{ fieldError.name }}</small>
            </label>

            <label class="form-field" :class="{ full: form.protocol === 'ICMP' }">
              <span>IP 地址 <b>*</b></span>
              <input v-model="form.ip" maxlength="45" placeholder="例如：192.0.2.10" @input="fieldError.ip = ''" />
              <small v-if="fieldError.ip" class="field-error">{{ fieldError.ip }}</small>
            </label>

            <label v-if="form.protocol !== 'ICMP'" class="form-field">
              <span>端口 <b>*</b></span>
              <input v-model.number="form.port" type="number" min="1" max="65535" placeholder="443" @input="fieldError.port = ''" />
              <small v-if="fieldError.port" class="field-error">{{ fieldError.port }}</small>
            </label>

            <fieldset class="form-field full protocol-field">
              <legend>协议 <b>*</b></legend>
              <div class="protocol-options">
                <button type="button" :class="{ active: form.protocol === 'ICMP' }" @click="chooseProtocol('ICMP')">
                  <span>ICMP</span><small>主机 Ping</small>
                </button>
                <button type="button" :class="{ active: form.protocol === 'TCP' }" @click="chooseProtocol('TCP')">
                  <span>TCP</span><small>可靠连接</small>
                </button>
                <button type="button" :class="{ active: form.protocol === 'UDP' }" @click="chooseProtocol('UDP')">
                  <span>UDP</span><small>数据报</small>
                </button>
              </div>
            </fieldset>

            <label class="form-field full">
              <span>备注</span>
              <textarea v-model="form.note" maxlength="300" rows="3" placeholder="可选，记录入口用途或说明"></textarea>
              <small class="character-count">{{ form.note.length }}/300</small>
            </label>

            <p v-if="error" class="modal-error" role="alert">{{ error }}</p>

            <footer class="modal-actions full">
              <button class="secondary-button" type="button" :disabled="saving" @click="close">取消</button>
              <button class="primary-button compact" type="submit" :disabled="saving">
                {{ saving ? '正在保存…' : editing ? '保存修改' : '添加入口' }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
