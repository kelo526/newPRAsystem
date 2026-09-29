async function handle(res) {
  if (res.ok) {
    if (res.status === 204) return null
    return res.json()
  }
  let msg = res.statusText
  try {
    const body = await res.json()
    msg = body.detail || JSON.stringify(body)
  } catch { /* ignore */ }
  throw new Error(msg)
}

export const api = {
  get: (url) => fetch(url).then(handle),
  post: (url, body) =>
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(handle),
  put: (url, body) =>
    fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(handle),
  del: (url) => fetch(url, { method: 'DELETE' }).then(handle)
}
