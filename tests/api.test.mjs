import test from 'node:test'
import assert from 'node:assert/strict'

import { createApi } from '../api.js'

function recordingFetch(reply) {
  const calls = []
  const fetchImpl = async (url, init) => {
    calls.push({ url, init })
    if (reply instanceof Error) throw reply
    return { ok: reply.status ? reply.status < 400 : true, status: reply.status || 200, json: async () => reply.body }
  }
  return { calls, fetchImpl }
}

test('snapshot calls its own service with the app token', async () => {
  const { calls, fetchImpl } = recordingFetch({ body: { ok: true, characters: [] } })
  const body = await createApi(11, 'app-tok', fetchImpl).snapshot()
  assert.deepEqual(body, { ok: true, characters: [] })
  assert.equal(calls[0].url, '/api/apps/11/service/snapshot')
  assert.equal(calls[0].init.headers.Authorization, 'Bearer app-tok')
})

test('progress passes the working count; the sword posts kind and id', async () => {
  const { calls, fetchImpl } = recordingFetch({ body: { ok: true } })
  const api = createApi(11, 't', fetchImpl)
  await api.progress(5, 'America/Chicago')
  await api.sword('chat', 'c1')
  assert.equal(calls[0].url, '/api/apps/11/service/progress?working_now=5&tz=America%2FChicago')
  assert.equal(calls[1].url, '/api/apps/11/service/sword')
  assert.equal(calls[1].init.method, 'POST')
  assert.deepEqual(JSON.parse(calls[1].init.body), { kind: 'chat', id: 'c1' })
})

test('a network failure resolves offline instead of throwing', async () => {
  const { fetchImpl } = recordingFetch(new TypeError('Failed to fetch'))
  const body = await createApi(11, 't', fetchImpl).snapshot()
  assert.equal(body.ok, false)
  assert.equal(body.error.code, 'offline')
})

test('an HTTP error from the service platform is reported, not parsed', async () => {
  const { fetchImpl } = recordingFetch({ status: 503, body: { detail: 'down' } })
  const body = await createApi(11, 't', fetchImpl).snapshot()
  assert.deepEqual(body.ok, false)
  assert.equal(body.error.code, 'offline')
})

test('quick reply calls its back room', async () => {
  const { calls, fetchImpl } = recordingFetch({ body: { ok: true } })
  const api = createApi(11, 't', fetchImpl)
  await api.thread('c 1')
  await api.reply('c1', 'hi', 'k1')
  await api.answer('c1', 'q1', { a: '0' }, null, 'k2')
  await api.openBeside('c1')
  assert.equal(calls[0].url, '/api/apps/11/service/thread?chat_id=c%201')
  assert.equal(calls[1].url, '/api/apps/11/service/reply')
  assert.deepEqual(JSON.parse(calls[1].init.body), { chat_id: 'c1', text: 'hi', cid: 'k1' })
  assert.deepEqual(JSON.parse(calls[2].init.body), { chat_id: 'c1', question_id: 'q1', picks: { a: '0' }, text: null, cid: 'k2' })
  assert.equal(calls[3].url, '/api/apps/11/service/open-beside')
  assert.deepEqual(JSON.parse(calls[3].init.body), { chat_id: 'c1' })
})
