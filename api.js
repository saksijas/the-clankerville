/* The office's only network client: it talks to its own back room
   (/api/apps/<id>/service/...) with the app token, and never throws. */

export function createApi(appId, token, fetchImpl = (...args) => fetch(...args)) {
  async function call(path, init = {}) {
    try {
      const headers = { Authorization: `Bearer ${token}` }
      if (init.body) headers['Content-Type'] = 'application/json'
      const response = await fetchImpl(`/api/apps/${appId}/service/${path}`, { ...init, headers })
      if (!response.ok) return { ok: false, error: { code: 'offline', message: `The office's back room answered HTTP ${response.status}.` } }
      return await response.json()
    } catch (err) {
      return { ok: false, error: { code: 'offline', message: String(err?.message || err) } }
    }
  }
  return {
    snapshot: () => call('snapshot'),
    progress: (workingNow = 0, tz = '') => call(`progress?working_now=${Math.max(0, Math.floor(workingNow) || 0)}${tz ? `&tz=${encodeURIComponent(tz)}` : ''}`),
    sword: (kind, id) => call('sword', { method: 'POST', body: JSON.stringify({ kind, id }) }),
    internet: on => call('internet', { method: 'POST', body: JSON.stringify({ on }) }),
    hire: (title, text, cid) => call('hire', { method: 'POST', body: JSON.stringify({ title, text, cid }) }),
    thread: chatId => call(`thread?chat_id=${encodeURIComponent(chatId)}`),
    reply: (chatId, text, cid) => call('reply', { method: 'POST', body: JSON.stringify({ chat_id: chatId, text, cid }) }),
    answer: (chatId, questionId, picks, text, cid) => call('answer', {
      method: 'POST', body: JSON.stringify({ chat_id: chatId, question_id: questionId, picks, text, cid }),
    }),
    openBeside: chatId => call('open-beside', { method: 'POST', body: JSON.stringify({ chat_id: chatId }) }),
  }
}
