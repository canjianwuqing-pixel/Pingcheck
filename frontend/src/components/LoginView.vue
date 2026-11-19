<script setup>
import { ref } from 'vue'
import BrandMark from './BrandMark.vue'

const emit = defineEmits(['login'])
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!password.value || loading.value) return
  loading.value = true
  error.value = ''
  emit(
    'login',
    password.value,
    (message) => {
      error.value = message
    },
    () => {
      loading.value = false
    },
  )
}

function resetError() {
  if (error.value) {
    error.value = ''
  }
}
</script>

<template>
  <main class="login-page">
    <div class="login-glow login-glow-one"></div>
    <div class="login-glow login-glow-two"></div>
    <section class="login-card" aria-labelledby="login-title">
      <div class="login-brand">
        <BrandMark />
        <span>Pingcheck</span>
      </div>
      <div class="login-heading">
        <span class="eyebrow">网络检测管理平台</span>
        <h1 id="login-title">欢迎回来</h1>
        <p>输入管理密码，进入 Pingcheck 控制台。</p>
      </div>
      <form @submit.prevent="submit">
        <label for="password">管理密码</label>
        <div class="input-wrap" :class="{ invalid: error }">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="10" width="14" height="10" rx="2" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入管理密码"
            autofocus
            @input="resetError"
          />
        </div>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <button class="primary-button" type="submit" :disabled="!password || loading">
          <span>{{ loading ? '正在登录…' : '进入控制台' }}</span>
          <svg v-if="!loading" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      </form>
      <p class="login-footnote">Docker Compose · 一站式网络监控</p>
    </section>
  </main>
</template>
