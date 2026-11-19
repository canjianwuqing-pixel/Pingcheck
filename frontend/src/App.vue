<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'
import DashboardView from './components/DashboardView.vue'
import LoginView from './components/LoginView.vue'

const checking = ref(true)
const authenticated = ref(false)
const health = ref(null)

onMounted(async () => {
  try {
    await api.me()
    authenticated.value = true
    await loadHealth()
  } catch {
    authenticated.value = false
  } finally {
    checking.value = false
  }
})

async function loadHealth() {
  try {
    health.value = await api.health()
  } catch {
    health.value = null
  }
}

async function login(password, reportError, finish) {
  try {
    await api.login(password)
    authenticated.value = true
    await loadHealth()
  } catch (error) {
    reportError(error.message)
  } finally {
    finish()
  }
}

async function logout() {
  try {
    await api.logout()
  } finally {
    authenticated.value = false
    health.value = null
  }
}
</script>

<template>
  <div v-if="checking" class="boot-screen" aria-label="正在加载">
    <span class="boot-spinner"></span>
  </div>
  <DashboardView v-else-if="authenticated" :health="health" @logout="logout" />
  <LoginView v-else @login="login" />
</template>
