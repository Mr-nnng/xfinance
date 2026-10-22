const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  constructor(message, status, code, details) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function api(path, { params, method = 'GET', body, signal } = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === '') continue
      url.searchParams.set(key, String(value))
    }
  }
  const options = { method, signal, headers: {} }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  let response
  try {
    response = await fetch(url.toString(), options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('网络请求失败，请确认后端正在运行', 0, 'network_error')
  }
  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }
  if (!response.ok) {
    const error = payload?.error
    throw new ApiError(
      error?.message || `请求失败 (${response.status})`,
      response.status,
      error?.code || 'http_error',
      error?.details,
    )
  }
  return payload
}

export function get(path, params, signal) {
  return api(path, { params, signal })
}

export function post(path, body, signal) {
  return api(path, { method: 'POST', body, signal })
}

export function del(path) {
  return api(path, { method: 'DELETE' })
}
