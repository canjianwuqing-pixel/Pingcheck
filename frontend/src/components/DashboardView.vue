<script setup>
import BrandMark from './BrandMark.vue'

defineProps({
  health: {
    type: Object,
    default: null,
  },
})

defineEmits(['logout'])

const modules = [
  {
    title: 'TCP / UDP 入口',
    description: '统一维护待检测的网络服务入口。',
    icon: 'network',
  },
  {
    title: '检测历史',
    description: '查看可用性、延迟和异常记录。',
    icon: 'history',
  },
  {
    title: 'Telegram 通知',
    description: '配置异常状态的消息提醒。',
    icon: 'send',
  },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <BrandMark />
        <span>Pingcheck</span>
      </div>
      <nav aria-label="主导航">
        <a class="nav-item active" href="#overview">
          <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></svg>
          <span>概览</span>
        </a>
        <span class="nav-item muted">
          <svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="m8 11 8-4M8 13l8 4" /></svg>
          <span>入口管理</span><small>待开发</small>
        </span>
        <span class="nav-item muted">
          <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>
          <span>检测历史</span><small>待开发</small>
        </span>
      </nav>
      <div class="sidebar-footer">
        <span class="stage-dot"></span>
        <div><strong>第一阶段</strong><small>基础框架已就绪</small></div>
      </div>
    </aside>

    <main class="dashboard" id="overview">
      <header class="topbar">
        <div class="mobile-brand"><BrandMark /><span>Pingcheck</span></div>
        <div class="admin-chip"><span class="avatar">管</span><span>管理员</span></div>
        <button class="logout-button" type="button" @click="$emit('logout')">
          <svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /></svg>
          退出
        </button>
      </header>

      <div class="dashboard-content">
        <section class="welcome-row">
          <div>
            <span class="eyebrow">控制台概览</span>
            <h1>下午好，管理员</h1>
            <p>基础服务已经就绪，监控能力将在后续阶段逐步接入。</p>
          </div>
          <div class="health-pill" :class="{ loading: !health }">
            <span></span>{{ health ? '系统运行正常' : '正在检查系统' }}
          </div>
        </section>

        <section class="status-grid" aria-label="系统状态">
          <article class="status-card featured">
            <div class="card-icon pulse-icon">
              <svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>
            </div>
            <div><small>后端服务</small><strong>{{ health ? '运行中' : '检查中' }}</strong></div>
            <span class="status-tag">v{{ health?.version || '0.1.0' }}</span>
          </article>
          <article class="status-card">
            <div class="card-icon db-icon">
              <svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></svg>
            </div>
            <div><small>SQLite 数据库</small><strong>{{ health?.database === 'ok' ? '连接正常' : '检查中' }}</strong></div>
          </article>
          <article class="status-card">
            <div class="card-icon shield-icon">
              <svg viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.6 2.9 8.4 7 10 4.1-1.6 7-5.4 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></svg>
            </div>
            <div><small>管理会话</small><strong>已登录</strong></div>
          </article>
        </section>

        <section class="section-block">
          <div class="section-heading">
            <div><h2>功能模块</h2><p>后续阶段将在这里开放监控管理能力。</p></div>
            <span>规划中</span>
          </div>
          <div class="module-grid">
            <article v-for="item in modules" :key="item.title" class="module-card">
              <div class="module-icon">
                <svg v-if="item.icon === 'network'" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /><path d="M10 7h4a3 3 0 0 1 3 3v4M7 10v4a3 3 0 0 0 3 3h4" /></svg>
                <svg v-else-if="item.icon === 'history'" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>
                <svg v-else viewBox="0 0 24 24"><path d="m21 3-7.5 18-4-8-8-4L21 3Z" /><path d="m9.5 13 4-4" /></svg>
              </div>
              <span class="soon-badge">即将开放</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
