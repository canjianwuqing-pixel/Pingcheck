async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail[0]?.msg?.replace(/^Value error,\s*/, '')
      : body.detail
    throw new Error(detail || '请求失败，请稍后重试')
  }
  return body
}

export const api = {
  login(password) {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
  },
  me() {
    return request('/api/auth/me')
  },
  logout() {
    return request('/api/auth/logout', { method: 'POST' })
  },
  health() {
    return request('/api/health')
  },
  targets: {
    list() {
      return request('/api/targets')
    },
    create(target) {
      return request('/api/targets', {
        method: 'POST',
        body: JSON.stringify(target),
      })
    },
    update(id, target) {
      return request(`/api/targets/${id}`, {
        method: 'PUT',
        body: JSON.stringify(target),
      })
    },
    setEnabled(id, enabled) {
      return request(`/api/targets/${id}/enabled`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      })
    },
    check(id) {
      return request(`/api/targets/${id}/check`, { method: 'POST' })
    },
    remove(id) {
      return request(`/api/targets/${id}`, { method: 'DELETE' })
    },
  },
  telegram: {
    getSettings() {
      return request('/api/telegram/settings')
    },
    updateSettings(settings) {
      return request('/api/telegram/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      })
    },
    test() {
      return request('/api/telegram/test', { method: 'POST' })
    },
  },
  history: {
    list(limit = 200) {
      return request(`/api/history?limit=${limit}`)
    },
  },
}
