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
    throw new Error(body.detail || '请求失败，请稍后重试')
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
}
