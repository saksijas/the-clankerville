import test from 'node:test'
import assert from 'node:assert/strict'

import { bubbleText, countChips, createHold, declutter, holdMs, nextPollDelay, plateText, poseFor, project, roomFrame, spotFor, swordNote, swordToast, swordWarnings, progressNews, shouldAutoOpenRecap, recapLines, dialogKey, departureDelays, doorSpot, walkOffset, watchReducedMotion, createVisibilityGate, textScaleFor, plateTeamSize, openMode, canSendAnswers, createSendGuard, replyStatus, answerStatus, problemText, fullChatText, localDay, levelShare, officeView, createVisiblePoller, INTERNET_ARM_MS, INTERNET_MIN_GAP_MS, internetClick, internetToast } from '../domain.js'

function fakeTimers() {
  const q = []
  return { set: (fn, ms) => (q.push({ fn, ms }), q.length), clear: id => { q[id - 1] = null }, run: () => q.forEach(t => t && t.fn()), q }
}

test('hold completes on the timer, not animation', () => {
  const t = fakeTimers(); const done = []
  const hold = createHold({ setTimer: t.set, clearTimer: t.clear })
  hold.start('c1', 900, id => done.push(id)); assert.equal(t.q[0].ms, 900); t.run(); assert.deepEqual(done, ['c1'])
})

test('cancel prevents completion', () => {
  const t = fakeTimers(); const done = []
  const hold = createHold({ setTimer: t.set, clearTimer: t.clear })
  hold.start('c1', 900, id => done.push(id)); hold.cancel(); t.run(); assert.deepEqual(done, []); assert.equal(hold.activeId(), null)
})

test('a hold finishes with the action it was started with, not an older one', () => {
  const t = fakeTimers(); const first = []; const latest = []
  const hold = createHold({ setTimer: t.set, clearTimer: t.clear })
  hold.start('c1', 900, id => first.push(id))
  hold.start('c2', 900, id => latest.push(id))
  t.run()
  assert.deepEqual(first, [])
  assert.deepEqual(latest, ['c2'])
})

test('deleting a chat takes a longer hold than dismissing a helper', () => {
  assert.equal(holdMs({ kind: 'chat', state: 'working', queued: 0 }), 1600)
  assert.equal(holdMs({ kind: 'chat', state: 'on_break', queued: 0 }), 1600)
  assert.equal(holdMs({ kind: 'helper', state: 'busy' }), 900)
})

test('the card says what the sword does to whom', () => {
  assert.equal(swordNote({ kind: 'chat' }), "Deletes the chat and dismisses its helpers. You can restore it for 7 days from Möbius's notification.")
  assert.equal(swordNote({ kind: 'helper' }), 'Dismisses this helper. Its lead keeps working.')
})

test('sword warnings name what a restore will not bring back', () => {
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'working', queued: 0 }), [])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'working', queued: 1 }), ['Your 1 queued message in this chat is discarded.'])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'working', queued: 3 }), ['Your 3 queued messages in this chat are discarded.'])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'watching', queued: 0 }),
    ['Its timer to check back is cancelled for good, even if you restore the chat.'])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'needs_you', queued: 0 }),
    ['Its question to you is withdrawn for good, even if you restore the chat.'])
  assert.deepEqual(swordWarnings({ kind: 'helper', state: 'busy' }), [])
})

test('backoff', () => { assert.deepEqual([0, 1, 2, 3, 4, 5].map(nextPollDelay), [3000, 6000, 12000, 24000, 30000, 30000]) })

test('chips', () => {
  assert.deepEqual(countChips({ working: 2, needs_you: 1, error: 0, watching: 0, on_break: 1 }),
    [['working', 'working', 2], ['needs_you', 'needs you', 1], ['on_break', 'on break', 1]])
})

test('declutter leaves no overlaps', () => {
  const placed = declutter(['a', 'b', 'c'].map(id => ({ id, text: 'Running tests', ax: 100, ay: 100 })), { charW: 4.4, pad: 6, h: 15, width: 560 })
  for (const p of placed) for (const q of placed) if (p !== q) assert.ok(p.top + 15 <= q.top || q.top + 15 <= p.top)
})

test('isometric projection matches the mockup grid', () => {
  assert.deepEqual(project(0, 0), [236, 92])
  assert.deepEqual(project(1, 0), [260, 104])
  assert.deepEqual(project(0, 1, 10), [212, 94])
})

test('room frame reproduces the approved 13x9 mockup geometry and grows with depth', () => {
  assert.deepEqual(roomFrame(13, 9), { ox: 236, oy: 92, viewW: 568, viewH: 396 })
  assert.deepEqual(roomFrame(13, 12), { ox: 308, oy: 92, viewW: 640, viewH: 432 })
})

test('bubbles only for working, needs-you, error, and watching chats', () => {
  const chat = (state, step) => ({ kind: 'chat', state, step })
  assert.equal(bubbleText(chat('working', 'Reading theme.css')), 'Reading theme.css')
  assert.equal(bubbleText(chat('needs_you')), 'Needs your answer')
  assert.equal(bubbleText(chat('error')), 'Hit an error')
  assert.equal(bubbleText(chat('watching')), 'Waiting on a timer')
  assert.equal(bubbleText(chat('on_break')), null)
  assert.equal(bubbleText({ kind: 'helper', state: 'busy', step: 'x' }), null)
})

test('where each character stands', () => {
  const desk = { x: 1.9, y: 0.7 }
  assert.deepEqual(spotFor({ kind: 'chat', state: 'working', desk }, 0), { x: 2.5, y: 1.75 })
  assert.deepEqual(spotFor({ kind: 'chat', state: 'needs_you', desk }, 0), { x: 3.35, y: 1.0 })
  assert.deepEqual(spotFor({ kind: 'chat', state: 'on_break', desk }, 0), { x: 9.5, y: 7.7 })
  assert.deepEqual(spotFor({ kind: 'chat', state: 'on_break', desk }, 6), { x: 2.5, y: 1.75 })
  assert.deepEqual(spotFor({ kind: 'helper', state: 'busy', desk }, 0), { x: 2.5, y: 1.75 })
})

test('name tags: chats show short name and level; helpers show none', () => {
  assert.equal(plateText({ kind: 'chat', state: 'working', short: 'Brainstorm', level: 3 }), 'Brainstorm · Lv 3')
  assert.equal(plateText({ kind: 'helper', state: 'busy', short: 'pixel-sketcher' }), null)
})

test('the name tag of a lead carries its team size', () => {
  assert.equal(plateText({ kind: 'chat', state: 'working', short: 'Brainstorm', level: 3 }, 2), 'Brainstorm · Lv 3 · 2 helpers')
  assert.equal(plateText({ kind: 'chat', state: 'working', short: 'Brainstorm', level: 3 }, 1), 'Brainstorm · Lv 3 · 1 helper')
})

test('each state has its pose', () => {
  const pose = (kind, state, spot) => poseFor({ kind, state }, spot)
  assert.equal(pose('chat', 'working'), 'type')
  assert.equal(pose('helper', 'busy'), 'type')
  assert.equal(pose('chat', 'error'), 'slump')
  assert.equal(pose('helper', 'failed'), 'slump')
  assert.equal(pose('chat', 'needs_you'), 'wave')
  assert.equal(pose('chat', 'on_break', 'coffee'), 'mug')
  assert.equal(pose('chat', 'on_break', 'seat'), 'sit')
  assert.equal(pose('chat', 'watching'), 'sit')
  assert.equal(pose('helper', 'done'), 'stand')
})

test('sword toasts report what Möbius actually did', () => {
  const restore = " You can restore it for 7 days from Möbius's notification."
  const lead = { kind: 'chat', short: 'Brainstorm', state: 'working' }
  assert.equal(swordToast(lead, { ok: true, deleted: true, cancelled_helpers: 2, discarded_messages: 0 }),
    `Deleted Brainstorm and dismissed its 2 helpers.${restore}`)
  const solo = { kind: 'chat', short: 'Tasks app', state: 'working' }
  assert.equal(swordToast(solo, { ok: true, deleted: true, cancelled_helpers: 0, discarded_messages: 1 }),
    `Deleted Tasks app. Your 1 queued message was discarded.${restore}`)
  assert.equal(swordToast(solo, { ok: true, deleted: true, cancelled_helpers: 1, discarded_messages: 2 }),
    `Deleted Tasks app and dismissed its 1 helper. Your 2 queued messages were discarded.${restore}`)
  assert.equal(swordToast({ kind: 'chat', short: 'Railway', state: 'watching' }, { ok: true, deleted: true }),
    `Deleted Railway. Its timer was cancelled.${restore}`)
  assert.equal(swordToast({ kind: 'chat', short: 'Tasks app', state: 'needs_you' }, { ok: true, deleted: true }),
    `Deleted Tasks app. Its question to you was withdrawn.${restore}`)
  assert.equal(swordToast(solo, { ok: false, stopped: true, error: { code: 'busy', message: 'Try again in a moment.' } }),
    "Stopped Tasks app, but couldn't delete it: Try again in a moment.")
  assert.equal(swordToast(solo, { ok: false, error: { code: 'stop_failed', message: "Möbius didn't confirm the stop." } }),
    "Couldn't delete Tasks app: Möbius didn't confirm the stop.")
  const helper = { kind: 'helper', name: 'pixel-sketcher', state: 'busy' }
  assert.equal(swordToast(helper, { ok: true, dismissed: true }), 'Dismissed pixel-sketcher. Its lead keeps working.')
  assert.equal(swordToast(helper, { ok: false, error: { code: 'offline', message: 'The network dropped.' } }),
    "Couldn't dismiss pixel-sketcher: The network dropped.")
})

test('progress news: office and chat level-ups and new achievements, never on first load', () => {
  const prev = { office: { level: 3 }, chats: { c1: { level: 2, title: 'Budget sheet' } }, achievements: [{ id: 'shipped_it' }] }
  const next = { office: { level: 4 }, chats: { c1: { level: 3, title: 'Budget sheet' }, c2: { level: 1, title: 'New chat' } },
    achievements: [{ id: 'shipped_it' }, { id: 'first_team' }] }
  assert.deepEqual(progressNews(prev, next), ['The office reached Lv 4', 'Budget sheet reached Lv 3', 'New achievement: First team assembled'])
  assert.deepEqual(progressNews(null, next), [])
})

test('the recap opens by itself once per day', () => {
  assert.equal(shouldAutoOpenRecap({ turns: 1 }, '2026-09-27', '2026-09-28', true), true)
  assert.equal(shouldAutoOpenRecap({ turns: 1 }, '2026-09-28', '2026-09-28', true), false)
  assert.equal(shouldAutoOpenRecap(null, undefined, '2026-09-28', true), false)
})

test('the recap waits for your saved preferences before opening by itself', () => {
  assert.equal(shouldAutoOpenRecap({ turns: 1 }, undefined, '2026-09-28', false), false)
  assert.equal(shouldAutoOpenRecap({ turns: 1 }, undefined, '2026-09-28', true), true)
})

test('the recap counts stopped helpers', () => {
  const day = { turns: 0, helpers_done: 4, helpers_failed: 1, helpers_stopped: 2, apps: 0, level_ups: [], achievements: [], busiest: null }
  assert.deepEqual(recapLines(day, {}), ['4 helpers came back, 1 failed, 2 stopped'])
  assert.deepEqual(recapLines({ ...day, helpers_done: 0, helpers_failed: 0, helpers_stopped: 1 }, {}), ['Helpers: 1 stopped'])
})

test('the recap dialog keeps the keyboard inside it', () => {
  assert.equal(dialogKey('Escape'), 'close')
  assert.equal(dialogKey('Tab'), 'stay')
  assert.equal(dialogKey('Enter'), null)
})

test('recap lines read like a summary', () => {
  const recap = { turns: 12, helpers_done: 4, helpers_failed: 1, apps: 1, level_ups: [{ chat_id: 'c1', level: 3 }],
    achievements: ['shipped_it'], busiest: { chat_id: 'c1', title: 'Budget sheet', xp: 75 } }
  assert.deepEqual(recapLines(recap, { c1: { title: 'Budget sheet' } }), [
    '12 turns finished', '4 helpers came back, 1 failed', '1 app shipped', 'Budget sheet reached Lv 3',
    'New achievement: Shipped it', 'Busiest: Budget sheet (+75 XP)'])
  assert.deepEqual(recapLines({ turns: 1, helpers_done: 0, helpers_failed: 0, apps: 0, level_ups: [], achievements: [], busiest: null }, {}),
    ['1 turn finished'])
})

test('localDay is the browser-local calendar day', () => {
  assert.equal(localDay(new Date(2026, 8, 28, 23, 30)), '2026-09-28')
})

test('the level bar measures progress within the current level', () => {
  assert.equal(levelShare({ xp: 215, level_start_xp: 150, next_level_xp: 300 }), 65 / 150)
  assert.equal(levelShare({ xp: 0, level_start_xp: 0, next_level_xp: 50 }), 0)
})

test('key trouble replaces the office even when an older snapshot exists', () => {
  const snap = { characters: [] }
  assert.equal(officeView(snap, { code: 'key_rejected' }, false), 'key_trouble')
  assert.equal(officeView(null, { code: 'no_key' }, false), 'key_trouble')
  assert.equal(officeView(snap, { code: 'offline' }, false), 'office')
  assert.equal(officeView(null, { code: 'offline' }, false), 'loading')
  assert.equal(officeView(null, { code: 'key_rejected' }, true), 'office')
})

test('progress is only fetched while the office is visible', () => {
  const t = fakeTimers(); let visible = true; let loads = 0
  const poller = createVisiblePoller({ load: () => { loads += 1 }, intervalMs: 60000, isVisible: () => visible, setTimer: t.set, clearTimer: t.clear })
  poller.start()
  assert.equal(loads, 1)
  visible = false
  t.q.at(-1).fn()
  assert.equal(loads, 1)
  visible = true
  poller.onVisible()
  assert.equal(loads, 2)
  poller.stop()
})

test('a lead leaves first, then its helpers poof one after another', () => {
  assert.deepEqual(departureDelays(['lead', 'h1', 'h2']), { lead: 0, h1: 140, h2: 280 })
  assert.deepEqual(departureDelays(['solo']), { solo: 0 })
})

test('finished helpers walk to the door on the left wall', () => {
  assert.deepEqual(doorSpot({ width: 13, depth: 9 }), { x: 0.35, y: 7.45 })
  assert.deepEqual(doorSpot({ width: 13, depth: 12 }), { x: 0.35, y: 10.45 })
  const frame = roomFrame(13, 9)
  const P = (x, y, z = 0) => project(x, y, z, frame)
  assert.deepEqual(walkOffset(P, { x: 2, y: 1 }, { x: 1, y: 1 }), [-24, -12])
})

test('reduced motion is followed live, not only at open', () => {
  const listeners = []
  const media = { matches: false, addEventListener: (type, fn) => listeners.push([type, fn]), removeEventListener: (type, fn) => { listeners.splice(listeners.findIndex(l => l[1] === fn), 1) } }
  const seen = []
  const stop = watchReducedMotion(media, value => seen.push(value))
  media.matches = true
  listeners.forEach(([type, fn]) => type === 'change' && fn())
  assert.deepEqual(seen, [false, true])
  stop()
  assert.equal(listeners.length, 0)
  assert.doesNotThrow(() => watchReducedMotion(null, value => seen.push(value))())
})

test('a bubble climbs over a character standing behind instead of covering it', () => {
  const obstacles = [{ id: 'behind', x0: 90, x1: 110, y0: 60, y1: 90 }]
  const [bubble] = declutter([{ id: 'front', text: 'Running tests', ax: 100, ay: 100 }], { charW: 4.4, pad: 6, h: 15, width: 560, obstacles })
  assert.ok(bubble.top + 15 <= 60, `the bubble's bottom (${bubble.top + 15}) must clear the head at 60`)
})

test('a bubble never has to avoid its own character', () => {
  const obstacles = [{ id: 'front', x0: 90, x1: 110, y0: 60, y1: 100 }]
  const [bubble] = declutter([{ id: 'front', text: 'Running tests', ax: 100, ay: 100 }], { charW: 4.4, pad: 6, h: 15, width: 560, obstacles })
  assert.equal(bubble.top, 100 - 6 - 15)
})

test('a bubble pushed to the top edge stays inside the room', () => {
  const obstacles = [{ id: 'tall', x0: 0, x1: 200, y0: 0, y1: 90 }]
  const [bubble] = declutter([{ id: 'front', text: 'Running tests', ax: 100, ay: 100 }], { charW: 4.4, pad: 6, h: 15, width: 560, obstacles })
  assert.equal(bubble.top, 2)
})

function fakeDocument() {
  const listeners = {}
  return {
    visibilityState: 'visible', listeners,
    addEventListener: (type, fn) => { listeners[type] = fn },
    removeEventListener: type => { delete listeners[type] },
  }
}

test('the office is visible only when its page is visible and its pane is on screen', () => {
  const doc = fakeDocument()
  let observe = null
  let disconnected = false
  class FakeObserver { constructor(callback) { observe = callback } observe() {} disconnect() { disconnected = true } }
  const changes = []
  const gate = createVisibilityGate({ doc, element: {}, IntersectionObserverImpl: FakeObserver, onChange: v => changes.push(v) })
  assert.equal(gate.isVisible(), true)
  observe([{ isIntersecting: false }]) // the shell kept the office loaded but hid its pane
  assert.equal(gate.isVisible(), false)
  observe([{ isIntersecting: true }])
  doc.visibilityState = 'hidden'
  doc.listeners.visibilitychange()
  assert.deepEqual(changes, [false, true, false])
  gate.stop()
  assert.ok(disconnected && !doc.listeners.visibilitychange)
})

test('without an on-screen observer, page visibility alone decides', () => {
  const doc = fakeDocument()
  const gate = createVisibilityGate({ doc, element: {}, IntersectionObserverImpl: undefined, onChange: () => {} })
  assert.equal(gate.isVisible(), true)
  doc.visibilityState = 'hidden'
  assert.equal(gate.isVisible(), false)
})

test('scene text grows on narrow screens so it stays about 9 px tall', () => {
  assert.equal(textScaleFor(1060, 568), 1) // desktop: the scene is drawn larger than its own units
  assert.equal(Math.round(textScaleFor(378, 568) * 100) / 100, 1.69) // a phone: 8-unit text would be 5 px
  assert.equal(textScaleFor(150, 568), 2) // capped
  assert.equal(textScaleFor(0, 568), 1) // not measured yet
})

test('compact name tags keep just the short name', () => {
  const chat = { kind: 'chat', state: 'working', short: 'Brainstorm', level: 3 }
  assert.equal(plateText(chat, 2, true), 'Brainstorm')
  assert.equal(plateText(chat, 2, false), 'Brainstorm · Lv 3 · 2 helpers')
})

test('warnings follow the timer and question behind the state on show', () => {
  const timer = 'Its timer to check back is cancelled for good, even if you restore the chat.'
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'working', queued: 0, waiting: true, asking: false }), [timer])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'error', queued: 1, waiting: true, asking: false }),
    ['Your 1 queued message in this chat is discarded.', timer])
  assert.deepEqual(swordWarnings({ kind: 'chat', state: 'needs_you', queued: 0, waiting: false, asking: true }),
    ['Its question to you is withdrawn for good, even if you restore the chat.'])
  assert.equal(swordToast({ kind: 'chat', short: 'Deploy', state: 'working', waiting: true, asking: false }, { ok: true, deleted: true }),
    "Deleted Deploy. Its timer was cancelled. You can restore it for 7 days from Möbius's notification.")
})

test('a strike Möbius has not confirmed yet says it may still finish', () => {
  const solo = { kind: 'chat', short: 'Tasks app', state: 'working' }
  const unconfirmed = { code: 'unconfirmed', message: 'no answer in time' }
  assert.equal(swordToast(solo, { ok: false, error: unconfirmed }),
    "Möbius hasn't confirmed deleting Tasks app yet. It may still finish: check again in a moment.")
  assert.equal(swordToast(solo, { ok: false, stopped: true, error: unconfirmed }),
    "Stopped Tasks app. Möbius hasn't confirmed the delete yet: watch for its notification.")
  assert.equal(swordToast({ kind: 'helper', name: 'pixel-sketcher', state: 'busy' }, { ok: false, error: unconfirmed }),
    "Möbius hasn't confirmed dismissing pixel-sketcher yet. It may still finish.")
})

test("a helper walking out no longer counts on its lead's tag", () => {
  assert.equal(plateTeamSize([{ state: 'busy' }, { state: 'done' }, { state: 'failed' }], 0), 2)
  assert.equal(plateTeamSize([{ state: 'busy' }], 3), 4)
})

// --- Quick reply rules ---------------------------------------------------------

test('Open chat goes beside the office only on wide layouts', () => {
  assert.deepEqual([1280, 921, 920, 402].map(openMode), ['beside', 'beside', 'navigate', 'navigate'])
})

test('several questions need a pick each; one question takes a pick or typed text', () => {
  const three = { questions: ['a', 'b', 'c'].map(id => ({ id, options: [{ id: '0' }] })) }
  const one = { questions: [{ id: 'a', options: [{ id: '0' }] }] }
  assert.equal(canSendAnswers(three, { a: '0', b: '0' }, ''), false)
  assert.equal(canSendAnswers(three, { a: '0', b: '0', c: '0' }, ''), true)
  assert.equal(canSendAnswers(one, {}, '  '), false)
  assert.equal(canSendAnswers(one, {}, 'typed'), true)
  assert.equal(canSendAnswers(one, { a: '0' }, ''), true)
})

test('the answer button is busy while sending', () => { // Review Focus 2
  const guard = createSendGuard()
  assert.equal(guard.begin(), true)
  assert.equal(guard.begin(), false)
  guard.end()
  assert.equal(guard.begin(), true)
})

test('status and problem sentences come from the spec', () => {
  const busy = "It's busy, so your message waits until its current step ends."
  const retry = "Couldn't send. Try again."
  assert.equal(replyStatus({ ok: true, status: 'queued' }), busy)
  assert.equal(replyStatus({ ok: true, status: 'started' }), 'Sent.')
  assert.equal(answerStatus({ ok: true, answer_turn: 'none' }), 'Answered.')
  assert.equal(answerStatus({ ok: true, answer_turn: 'same' }), "Answered. It's back at work.")
  assert.equal(problemText({ code: 'question_changed' }), 'This question changed. Take another look.')
  for (const code of ['mobius_unavailable', 'unconfirmed', 'offline']) assert.equal(problemText({ code }), retry)
  assert.equal(problemText({ code: 'not_found' }), 'This chat is gone.')
  assert.equal(problemText({ code: 'conflict', message: 'The chat is starting another turn; please try again.' }),
    'The chat is starting another turn; please try again.')
  assert.equal(fullChatText('secret'), "It's asking for a secret. Those are typed only in the full chat's sealed card.")
  assert.equal(fullChatText('restart'), "It's asking to restart Möbius. Answer in the full chat.")
  assert.equal(fullChatText('multi_pick'), 'This one needs the full chat.')
  assert.equal(fullChatText('missing'), "It's waiting on you. Open the full chat to answer.")
})

test('any other problem shows the back room’s own sentence, else a retry hint', () => {
  assert.equal(problemText({ code: 'not_owner', message: 'The office only replies to your own chats.' }), 'The office only replies to your own chats.')
  assert.equal(problemText({ code: 'something_new' }), "Couldn't send. Try again.")
  assert.equal(problemText(null), "Couldn't send. Try again.")
})

// --- Polish 2026-10-07: wall sign, name tags vs bubbles, the reply card ----------------------
import { signText, signLayout, plateBox, splitRecommended, isLongLatest, wallTextTransform } from '../domain.js'

test('the wall sign reads Night shift, the title the owner liked', () => {
  assert.equal(signText({ level: 6 }), 'Night shift')
  assert.equal(signText(null), 'Night shift')
})

test('wall text is painted on the wall: letters stay upright and follow the wall, never rotated', () => {
  // The left wall runs up-right on screen at half a tile up per tile across (iso slope 1:2).
  const left = wallTextTransform('left', 100, 50)
  assert.match(left, /skewY\(-26\.565\d*\)/)
  assert.doesNotMatch(left, /rotate/)
  assert.match(wallTextTransform('back', 100, 50), /skewY\(26\.565\d*\)/)
  // It skews about the text's own centre, so the text stays where the banner is.
  assert.match(left, /^translate\(100 50\) skewY\([^)]*\) translate\(-100 -50\)$/)
})

test('the sign grows with the text scale but stays on the wall before the door', () => {
  const small = signLayout('Agent Office · Lv 6', 1, 10)
  assert.equal(small.fontSize, 7.5)
  assert.ok(small.from >= 0.4 && small.to <= 7.6 && small.from < small.to)
  const phone = signLayout('Agent Office · Lv 6', 2, 10)
  assert.ok(phone.fontSize > small.fontSize * 1.8, 'readable on a phone')
  assert.ok(phone.to - phone.from > small.to - small.from, 'the banner widens with the text')
  assert.ok(phone.from >= 0.4 && phone.to <= 7.6, 'it never runs over the door')
  const long = signLayout('Agent Office · Lv 1234', 2, 10)
  assert.ok(long.to - long.from <= 7.2 + 1e-9, 'a long label shrinks to fit')
  assert.ok(long.fontSize < 15)
})

test('a name tag has a box that bubbles can step around', () => {
  const box = plateBox('c1', 100, 200, 'Agent office · Lv 4', 1)
  assert.equal(box.id, 'c1')
  assert.ok(box.x0 < 100 && box.x1 > 100 && box.y0 < 213 && box.y1 > 213)
  const big = plateBox('c1', 100, 200, 'Agent office · Lv 4', 2)
  assert.ok(big.x1 - big.x0 > (box.x1 - box.x0) * 1.8)
})

test('a bubble never covers another character’s name tag', () => {
  const tag = plateBox('other', 120, 100, 'Agent office · Lv 4', 1)
  const items = [{ id: 'me', state: 'needs_you', text: 'Needs your answer', ax: 120, ay: tag.y1 + 14 }]
  const [bubble] = declutter(items, { charW: 4.4, pad: 6, h: 15, width: 400, obstacles: [tag] })
  const overlaps = bubble.cx + bubble.w / 2 > tag.x0 && bubble.cx - bubble.w / 2 < tag.x1 && bubble.top < tag.y1 && bubble.top + 15 > tag.y0
  assert.equal(overlaps, false)
})

test('the recommended option is marked, and its label shows without the suffix', () => {
  assert.deepEqual(splitRecommended('No-guess boards (Recommended)'), { text: 'No-guess boards', recommended: true })
  assert.deepEqual(splitRecommended('Leave it as it is'), { text: 'Leave it as it is', recommended: false })
})

test('only long latest words get a Show more toggle', () => {
  assert.equal(isLongLatest('Short and sweet.'), false)
  assert.equal(isLongLatest('x '.repeat(160)), true)
  assert.equal(isLongLatest('a\nb\nc\nd\ne\nf\ng'), true)
})

// --- The Internet box (IT Crowd): click, click again to turn it off; click to turn it on ---

test('the Internet box asks for a deliberate second press before turning off', () => {
  assert.equal(internetClick({ off: false }, 1000), 'arm')
  const armed = { off: false, armedAt: 1000, armedUntil: 1000 + INTERNET_ARM_MS }
  // A double-click or double-tap lands within a few ms: it is ignored, the box stays armed (final review).
  assert.equal(internetClick(armed, 1000 + 50), null)
  assert.equal(internetClick(armed, 1000 + INTERNET_MIN_GAP_MS), 'turn_off')
  assert.equal(internetClick(armed, 1000 + INTERNET_ARM_MS + 1), 'arm') // too late: arms again
  assert.equal(internetClick({ off: true }, 5000), 'turn_on') // one press brings it back
  assert.equal(internetClick({ ...armed, busy: true }, 1700), null)
})

test('the Internet box says what happened', () => {
  assert.equal(internetToast({ ok: true, off: true, paused: 2, unconfirmed: 1 }, false), 'You turned off the Internet. 3 agents stopped.')
  assert.equal(internetToast({ ok: true, off: true, paused: 1, unconfirmed: 0 }, false), 'You turned off the Internet. 1 agent stopped.')
  assert.equal(internetToast({ ok: true, off: true, paused: 0, unconfirmed: 0 }, false), 'You turned off the Internet. Nobody was working, so nobody noticed.')
  assert.equal(internetToast({ ok: true, off: false, told: 2, failed: 0, failed_names: [] }, true), 'The Internet is back on. Told 2 agents to continue.')
  assert.equal(internetToast({ ok: true, off: false, told: 1, failed: 1, failed_names: ['Trip planner'] }, true),
    "The Internet is back on. Told 1 agent to continue. Trip planner didn't get the message: tell it yourself.")
  assert.equal(internetToast({ ok: true, off: false, told: 0, failed: 2, failed_names: ['A', 'B'] }, true),
    "The Internet is back on. A and B didn't get the message: tell them yourself.")
  assert.equal(internetToast({ ok: true, off: false, told: 0, failed: 0, failed_names: [] }, true), 'The Internet is back on.')
  assert.equal(internetToast({ ok: false, error: { message: 'Möbius rejected the owner key.' } }, false), "The Internet didn't switch: Möbius rejected the owner key.")
})

// --- Floors, the lobby and the elevator (spec 2026-10-08) --------------------------------------

import { DEMO_SNAPSHOT } from '../demo.js'
import { doorSpan, elevatorSpan, elevatorSpot, crDeskSpot, onFloor, floorBadges, floorLabel } from '../domain.js'

test('the lobby wall holds the door, then the elevator, with the sign before both', () => {
  const room = { width: 13, depth: 11, floors: 4 }
  const [d0, d1] = doorSpan(room)
  const [e0, e1] = elevatorSpan(room)
  assert.deepEqual([d0, d1, e0, e1], [9, 9.9, 10, 10.9])
  assert.ok(d1 <= e0, 'door and elevator overlap')
  const spot = elevatorSpot(room)
  assert.ok(spot.y > e0 && spot.y < e1 && spot.x < 1)
  assert.ok(signLayout('Night shift', 1, room.depth).to < d0, 'the sign runs into the door')
  assert.ok(crDeskSpot(room).y >= 9 && crDeskSpot(room).x >= 1.5) // in the lobby, clear of the wall
})

test('each floor shows its own agents, helpers with their lead', () => {
  const one = onFloor(DEMO_SNAPSHOT, 1)
  const two = onFloor(DEMO_SNAPSHOT, 2)
  assert.equal(one.filter(c => c.kind === 'chat').length, 8)
  assert.equal(one.filter(c => c.kind === 'helper').length, 3)
  assert.deepEqual(two.map(c => c.id).sort(), ['demo-beats', 'demo-maps', 'demo-recipes', 'demo-weather'])
  assert.deepEqual(onFloor(DEMO_SNAPSHOT, 3), [])
})

test('floors where someone needs you get a dot, and the strip names the floor', () => {
  assert.deepEqual([...floorBadges(DEMO_SNAPSHOT)], [1])
  assert.deepEqual([...floorBadges({ floors: [] })], [])
  assert.equal(floorLabel(2, 4), 'Floor 2 of 4')
})

import { floorSummary, floorMoves } from '../domain.js'

test('the elevator says who is on each floor', () => {
  assert.equal(floorSummary({ working: 3, needs_you: 1, error: 0, watching: 0, on_break: 2 }), '1 needs you · 3 working · 2 on break')
  assert.equal(floorSummary({ working: 0, needs_you: 0, error: 1, watching: 1, on_break: 0 }), '1 error · 1 watching')
  assert.equal(floorSummary({ working: 0, needs_you: 0, error: 0, watching: 0, on_break: 0 }), 'Nobody here yet')
  assert.equal(floorSummary(undefined), 'Nobody here yet')
})

test('agents who changed floors walk in from, or out to, the elevator on the floor you watch', () => {
  const before = { a: 1, b: 2, c: 1 }
  const now = [{ id: 'a', floor: 2 }, { id: 'b', floor: 1 }, { id: 'c', floor: 1 }, { id: 'd', floor: 1 }]
  const moves = floorMoves(before, now, 1)
  assert.deepEqual([...moves.arrivals], ['b']) // d is new to the office, not an elevator arrival
  assert.deepEqual(moves.departures, ['a'])
  assert.deepEqual(floorMoves(before, now, 2).departures, ['b'])
  assert.deepEqual([...floorMoves({}, now, 1).arrivals], [])
})

// --- The walking man (spec 2026-10-08 §7.2) -----------------------------------------------------

import { WALKER_SPEED, walkerAt, walkerTarget, nearElevator, toFloorPoint, keysFree } from '../domain.js'

const ROOM = { width: 13, depth: 11, floors: 4 }

test('the walking man walks straight at 2.5 tiles a second', () => {
  assert.equal(WALKER_SPEED, 2.5)
  const walk = { from: [1, 1], to: [6, 1], at: 1000 }
  assert.deepEqual(walkerAt(walk, 1000), [1, 1])
  assert.deepEqual(walkerAt(walk, 2000), [3.5, 1])
  assert.deepEqual(walkerAt(walk, 9000), [6, 1])
})

test('arrow keys aim far in a screen direction, inside the room', () => {
  assert.deepEqual(walkerTarget([3, 3], 'ArrowUp', ROOM), [0.45, 0.45])
  assert.deepEqual(walkerTarget([3, 3], 'ArrowDown', ROOM), [12.55, 10.55])
  assert.equal(walkerTarget([3, 3], 'a', ROOM), null)
})

test('the elevator opens when he walks within half a tile of it', () => {
  assert.equal(nearElevator([0.6, 10.3], ROOM), true)
  assert.equal(nearElevator([1.5, 10.45], ROOM), false)
})

test('a tap on the floor maps back to the tile under it', () => {
  const frame = roomFrame(ROOM.width, ROOM.depth)
  const [sx, sy] = project(4.25, 7.5, 0, frame)
  const [x, y] = toFloorPoint(sx, sy, frame)
  assert.ok(Math.abs(x - 4.25) < 1e-9 && Math.abs(y - 7.5) < 1e-9)
})

test('arrow keys move him only when nothing else needs the keys', () => {
  assert.equal(keysFree({ dialogOpen: false, focusTag: 'BODY' }), true)
  assert.equal(keysFree({ dialogOpen: true, focusTag: 'BODY' }), false)
  assert.equal(keysFree({ dialogOpen: false, focusTag: 'INPUT' }), false)
  assert.equal(keysFree({ dialogOpen: false, focusTag: 'TEXTAREA' }), false)
})

// --- Easter eggs on floors 2-4 (spec 2026-10-08 §7.3) -------------------------------------------

import { eggMoment, gossipFor, GOSSIP, PHONE_LINES, FIRE_TEXT, COOLER_EMPTY } from '../domain.js'

test('the IT phone rings, then asks the question, then checks the plug', () => {
  assert.deepEqual(eggMoment('phone', 1000, 1500), { active: true, ringing: true, text: null })
  assert.deepEqual(eggMoment('phone', 1000, 3000), { active: true, ringing: false, text: 'Hello, IT. Have you tried turning it off and on again?' })
  assert.deepEqual(eggMoment('phone', 1000, 6000), { active: true, ringing: false, text: 'Is it definitely plugged in?' })
  assert.equal(eggMoment('phone', 1000, 8000).active, false)
  assert.deepEqual(PHONE_LINES.length, 2)
})

test('the fire burns for 6 seconds with the emergency number', () => {
  assert.equal(FIRE_TEXT, '🔥 Fire! Call 0118 999 881 999 119 725… 3')
  assert.deepEqual(eggMoment('fire', 0, 1000), { active: true, text: FIRE_TEXT })
  assert.equal(eggMoment('fire', 0, 6000).active, false)
})

test('the watercooler gossips for 8 seconds, each agent its own line', () => {
  assert.equal(eggMoment('watercooler', 0, 7999).active, true)
  assert.equal(eggMoment('watercooler', 0, 8000).active, false)
  assert.equal(eggMoment('watercooler', 0, -1).active, false) // a clock step back doesn't start it
  assert.equal(eggMoment('watercooler', null, 10).active, false)
  assert.equal(gossipFor(0), GOSSIP[0])
  assert.equal(gossipFor(GOSSIP.length + 1), GOSSIP[1])
  assert.equal(COOLER_EMPTY, "Nobody's on break. Back to work!")
})

// --- The CR desk (spec 2026-10-08 §7.4) ---------------------------------------------------------

import { hireProblem, hireToast } from '../domain.js'

test('the hire form needs a name and a first message', () => {
  assert.equal(hireProblem('', 'Do it'), 'Give your new hire a name.')
  assert.equal(hireProblem('a'.repeat(81), 'Do it'), 'Names can be up to 80 characters.')
  assert.equal(hireProblem('Fix login', '   '), 'Write what they should start on.')
  assert.equal(hireProblem('Fix login', 'y'.repeat(8001)), 'The first message can be up to 8,000 characters.')
  assert.equal(hireProblem('  Fix login ', 'Do it'), null)
})

test('hiring says what happened', () => {
  assert.equal(hireToast({ ok: true, chat_id: 'c1' }, 'Fix login'), "Hired Fix login. They're heading to a desk.")
  assert.equal(hireToast({ ok: false, created: true, chat_id: 'c1', error: { message: 'busy' } }, 'Fix login'),
    "Fix login is hired, but their first message didn't send. Open the chat to send it.")
  assert.equal(hireToast({ ok: false, error: { message: 'Möbius rejected the owner key.' } }, 'Fix login'),
    "Couldn't hire Fix login: Möbius rejected the owner key.")
})

// --- Final review, Oct 8 ------------------------------------------------------------------------

import { arrowStop, toastMs } from '../domain.js'

test('a short arrow press still moves him one tile', () => {
  const [x, y] = arrowStop([3, 3], [3.1, 3.1], 'ArrowDown', ROOM)
  assert.ok(Math.abs(x - (3 + Math.SQRT1_2)) < 1e-9 && Math.abs(y - (3 + Math.SQRT1_2)) < 1e-9)
  assert.deepEqual(arrowStop([3, 3], [5, 5], 'ArrowDown', ROOM), [5, 5]) // a long press stops where he is
  assert.deepEqual(arrowStop([0.5, 0.5], [0.5, 0.5], 'ArrowUp', ROOM), [0.45, 0.45]) // still inside the room
})

test('hiring explains a name Möbius may change, and a first message it did not confirm', () => {
  assert.equal(hireToast({ ok: true, chat_id: 'c1', name_locked: false }, 'Fix login'),
    "Hired Fix login. They're heading to a desk, though Möbius may rename the chat from its first message.")
  assert.equal(hireToast({ ok: false, created: true, chat_id: 'c1', error: { code: 'unconfirmed', message: 'x' } }, 'Fix login'),
    "Fix login is hired, but Möbius didn't confirm their first message. Check the chat before sending it again.")
})

test('a toast with an action stays long enough to use it', () => {
  assert.equal(toastMs(null), 6500)
  assert.equal(toastMs({ label: 'Open chat' }), 15000)
})

// --- Former staff (owner's idea, Oct 8) ---------------------------------------------------------

import { daysLeftText, rehireToast } from '../domain.js'

test('the board counts down 7, 6, 5 days and then says it is the last day', () => {
  assert.equal(daysLeftText(7), '7 days left')
  assert.equal(daysLeftText(2), '2 days left')
  assert.equal(daysLeftText(1), 'Last day')
})

test('rehiring says what happened', () => {
  assert.equal(rehireToast({ ok: true }, 'Weather'), "Rehired Weather. They're back in your chats.")
  assert.equal(rehireToast({ ok: false, error: { code: 'too_late', message: 'x' } }, 'Weather'), 'Too late to rehire Weather: their 7 days are over.')
  assert.equal(rehireToast({ ok: false, error: { code: 'key_rejected', message: 'Möbius rejected the owner key.' } }, 'Weather'),
    "Couldn't rehire Weather: Möbius rejected the owner key.")
})
