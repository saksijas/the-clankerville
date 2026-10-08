/* Pure frontend logic for the office: geometry, bubble layout, the sword's
   hold timing, status-bar chips, and polling backoff. No React, no I/O. */

export const TILE = 24

// Isometric projection: +x runs right-down, +y runs left-down, z lifts up.
export function project(x, y, z = 0, origin = { ox: 236, oy: 92 }) {
  return [origin.ox + (x - y) * TILE, origin.oy + (x + y) * (TILE / 2) - z]
}

// Speech bubbles nudged upward until none overlap each other or cover another
// character (`obstacles`: screen boxes {id, x0, x1, y0, y1} of heads and chips).
// Lowest bubbles are placed first, so a higher bubble climbs above the ones
// beneath it rather than jumping below; none rises past the top edge.
const TOP_EDGE = 2
export function declutter(items, { charW, pad, h, width, obstacles = [] }) {
  const boxes = items
    .map(item => {
      const w = item.text.length * charW + pad * 2
      return { ...item, w, cx: Math.min(Math.max(item.ax, w / 2 + 2), width - w / 2 - 2), top: item.ay - 6 - h }
    })
    .sort((a, b) => b.top - a.top)
  const placed = []
  for (const box of boxes) {
    const others = obstacles.filter(o => o.id !== box.id)
    for (let guard = 0; guard < 24 && box.top > TOP_EDGE; guard++) {
      const bubble = placed.find(q => Math.abs(box.cx - q.cx) < (box.w + q.w) / 2 + 2 && box.top < q.top + h + 2 && box.top + h + 2 > q.top)
      const figure = bubble ? null : others.find(o => box.cx + box.w / 2 > o.x0 && box.cx - box.w / 2 < o.x1 && box.top < o.y1 && box.top + h > o.y0)
      if (!bubble && !figure) break
      box.top = bubble ? bubble.top - h - 3 : figure.y0 - h - 3
    }
    box.top = Math.max(box.top, TOP_EDGE)
    placed.push(box)
  }
  return placed
}

// The sword's press-and-hold. A timer decides completion; the ring animation
// is only feedback, because animation events don't fire in background frames.
// Each hold carries its own `onDone`, so it finishes with the office's current
// connection rather than one captured when the hold machinery was created.
export function createHold({ setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  let timer = null
  let active = null
  return {
    start(id, ms, onDone) {
      if (timer !== null) clearTimer(timer)
      active = id
      timer = setTimer(() => {
        const done = active
        timer = null
        active = null
        onDone(done)
      }, ms)
    },
    cancel() {
      if (timer !== null) clearTimer(timer)
      timer = null
      active = null
    },
    activeId() {
      return active
    },
  }
}

// The sword deletes a struck chat (Möbius keeps it restorable for 7 days and
// sends a Recover notification) and dismisses a struck helper.
export function swordNote(character) {
  return character.kind === 'chat'
    ? "Deletes the chat and dismisses its helpers. You can restore it for 7 days from Möbius's notification."
    : 'Dismisses this helper. Its lead keeps working.'
}

// What a restore won't bring back: Möbius discards the queued messages, cancels
// an armed timer, and withdraws a pending question when the chat is struck.
export function swordWarnings(character) {
  if (character.kind !== 'chat') return []
  const warnings = []
  const queued = character.queued || 0
  if (queued > 0) warnings.push(`Your ${queued} queued message${queued === 1 ? ' in this chat is' : 's in this chat are'} discarded.`)
  if (hasTimer(character)) warnings.push('Its timer to check back is cancelled for good, even if you restore the chat.')
  if (hasQuestion(character)) warnings.push('Its question to you is withdrawn for good, even if you restore the chat.')
  return warnings
}

// The back room reports the timer and question behind any state (an armed
// timer can sit under "working"); the demo's characters only have a state.
const hasTimer = character => character.waiting ?? character.state === 'watching'
const hasQuestion = character => character.asking ?? character.state === 'needs_you'

// Deleting a chat takes a longer hold than dismissing a helper.
export function holdMs(character) {
  return character.kind === 'chat' ? 1600 : 900
}

const CHIP_ORDER = ['working', 'needs_you', 'error', 'watching', 'on_break']
const CHIP_LABEL = {
  working: () => 'working',
  needs_you: n => (n === 1 ? 'needs you' : 'need you'),
  error: n => (n === 1 ? 'error' : 'errors'),
  watching: () => 'watching',
  on_break: () => 'on break',
}

export function countChips(counts) {
  return CHIP_ORDER.filter(state => (counts[state] || 0) > 0).map(state => [state, CHIP_LABEL[state](counts[state]), counts[state]])
}

export function nextPollDelay(failures) {
  return Math.min(3000 * 2 ** failures, 30000)
}

// --- The room -----------------------------------------------------------------

export const WALL_HEIGHT = 72
const MARGIN = 20
const LABEL_ROOM = 40

// The SVG frame for a floor of `width` × `depth` tiles: origin plus view size.
export function roomFrame(width, depth) {
  const ox = depth * TILE + MARGIN
  const oy = WALL_HEIGHT + MARGIN
  return { ox, oy, viewW: (width + depth) * TILE + 2 * MARGIN, viewH: oy + (width + depth) * (TILE / 2) + LABEL_ROOM }
}

const BUBBLES = { needs_you: 'Needs your answer', error: 'Hit an error', watching: 'Waiting on a timer' }

// Text bubbles belong to chats that are doing or asking something; helpers only get a chip.
export function bubbleText(character) {
  if (character.kind !== 'chat') return null
  if (character.state === 'working') return character.step || 'Working'
  return BUBBLES[character.state] || null
}

// The coffee corner's pod origin: office.py pod_origin(COFFEE_SLOT).
export const COFFEE_POD = { x: 8.5, y: 6.5 }
const COFFEE_SPOTS = [[1.0, 1.2], [1.9, 1.5], [0.4, 2.2], [1.4, 2.5], [2.5, 2.3], [0.2, 1.0]]
export const COFFEE_CAPACITY = COFFEE_SPOTS.length
const SEAT = [0.6, 1.05]
const BESIDE_DESK = [1.45, 0.3]
const round = v => Math.round(v * 100) / 100

// Where a character stands on the floor; `breakIndex` is its place in the coffee queue.
export function spotFor(character, breakIndex) {
  const { desk, state } = character
  if (character.kind === 'chat' && state === 'on_break' && breakIndex < COFFEE_SPOTS.length) {
    const [dx, dy] = COFFEE_SPOTS[breakIndex]
    return { x: round(COFFEE_POD.x + dx), y: round(COFFEE_POD.y + dy) }
  }
  const [dx, dy] = character.kind === 'chat' && state === 'needs_you' ? BESIDE_DESK : SEAT
  return { x: round(desk.x + dx), y: round(desk.y + dy) }
}

// The team size on a lead's tag: helpers still at work or on hold (a finished
// one is walking out), plus those without a desk ("+N").
export function plateTeamSize(members, overflow = 0) {
  return members.filter(member => member.state !== 'done').length + overflow
}

// Chats carry name and level (a lead also its team size); helpers show no tag.
// Compact tags (narrow screens) keep just the short name; the card has the rest.
export function plateText(character, helperCount = 0, compact = false) {
  if (character.kind !== 'chat') return null
  if (compact) return character.short
  const base = `${character.short} · Lv ${character.level}`
  return helperCount > 0 ? `${base} · ${helperCount} helper${helperCount === 1 ? '' : 's'}` : base
}

// --- Polish 2026-10-07 --------------------------------------------------------------------

// The sign on the left wall. The owner liked the "Night shift" title (2026-10-07),
// so it stays; the "· later" placeholder note is gone.
export function signText() {
  return 'Night shift'
}

// Text painted on a wall: the letters stay upright (vertical strokes vertical) and the
// baseline follows the wall's iso slope of 1:2. A rotation would tilt the letters off
// the wall; a vertical skew keeps them on it. Skews about the text's centre (cx, cy).
const WALL_SLOPE_DEG = Math.atan(0.5) * 180 / Math.PI // 26.565…
export function wallTextTransform(plane, cx, cy) {
  const angle = plane === 'left' ? -WALL_SLOPE_DEG : WALL_SLOPE_DEG
  return `translate(${cx} ${cy}) skewY(${angle}) translate(${-cx} ${-cy})`
}

// Where the sign sits along the left wall (in tiles from the back corner) and its font size.
// It grows with the scene's text scale, so it's readable on a phone; it stays between the
// back corner and the door, and shrinks a long label to fit.
const SIGN_TILE_PX = Math.hypot(TILE, TILE / 2) // one tile along the left wall, on screen
const CHAR_W = 0.56 // average glyph width as a share of the font size
export function signLayout(text, scale, depth) {
  const lo = 0.4
  const hi = depth - 2.4 // the door starts at depth - 2 (doorSpan), so the sign ends before it
  const room = hi - lo
  let fontSize = 7.5 * scale
  const lengthFor = size => (text.length * size * CHAR_W + 14 * (size / 7.5)) / SIGN_TILE_PX
  if (lengthFor(fontSize) > room) fontSize *= room / lengthFor(fontSize)
  const length = Math.min(room, lengthFor(fontSize))
  const center = Math.min(Math.max(4.5, lo + length / 2), hi - length / 2)
  return { from: center - length / 2, to: center + length / 2, fontSize }
}

// The screen box of a name tag drawn at the feet of a character standing at (sx, sy),
// matching Scene's tag text (font 7.5 × scale, baseline sy + 5 + 8 × scale).
export function plateBox(id, sx, sy, text, scale) {
  const size = 7.5 * scale
  const w = text.length * size * CHAR_W + 4 * scale
  const baseline = sy + 5 + 8 * scale
  return { id, x0: sx - w / 2, x1: sx + w / 2, y0: baseline - size, y1: baseline + 2 * scale }
}

// An option label ending in "(Recommended)" is shown with a badge instead of the suffix.
// Only the display changes: answers send the option id, so the chat sees its own label.
export function splitRecommended(label) {
  const match = /\s*\(recommended\)\s*$/i.exec(label || '')
  return match ? { text: label.slice(0, match.index), recommended: true } : { text: label || '', recommended: false }
}

// Latest words longer than about six lines get a "Show more" toggle.
export function isLongLatest(text) {
  return (text || '').length > 260 || (text || '').split('\n').length > 6
}

// How a character looks: `where` says whether an on-break chat made it to the
// coffee corner ('coffee') or stayed at its desk because the corner was full.
export function poseFor(character, where = 'seat') {
  const { state } = character
  if (state === 'working' || state === 'busy') return 'type'
  if (state === 'error' || state === 'failed') return 'slump'
  if (state === 'needs_you') return 'wave'
  if (state === 'done') return 'stand'
  if (state === 'on_break' && where === 'coffee') return 'mug'
  return 'sit'
}

// What the sword did, in words, using Möbius's own counts (spec §5.5).
export function swordToast(character, result) {
  const name = character.kind === 'helper' ? character.name : character.short
  if (!result.ok) {
    if (result.error?.code === 'unconfirmed') {
      // No answer in time isn't a refusal: Möbius may still finish.
      if (character.kind === 'helper') return `Möbius hasn't confirmed dismissing ${name} yet. It may still finish.`
      return result.stopped
        ? `Stopped ${name}. Möbius hasn't confirmed the delete yet: watch for its notification.`
        : `Möbius hasn't confirmed deleting ${name} yet. It may still finish: check again in a moment.`
    }
    const reason = result.error?.message || 'Something went wrong.'
    if (character.kind === 'helper') return `Couldn't dismiss ${name}: ${reason}`
    return result.stopped ? `Stopped ${name}, but couldn't delete it: ${reason}` : `Couldn't delete ${name}: ${reason}`
  }
  if (character.kind === 'helper') return `Dismissed ${name}. Its lead keeps working.`
  const helpers = result.cancelled_helpers || 0
  let text = `Deleted ${name}${helpers > 0 ? ` and dismissed its ${helpers} helper${helpers === 1 ? '' : 's'}` : ''}.`
  if (hasTimer(character)) text += ' Its timer was cancelled.'
  if (hasQuestion(character)) text += ' Its question to you was withdrawn.'
  const discarded = result.discarded_messages || 0
  if (discarded > 0) text += ` Your ${discarded} queued message${discarded === 1 ? ' was' : 's were'} discarded.`
  return `${text} You can restore it for 7 days from Möbius's notification.`
}

// --- Progress: news, recap ------------------------------------------------------

export const ACHIEVEMENT_NAMES = {
  first_team: 'First team assembled', shipped_it: 'Shipped it', full_house: 'Full house',
  clean_sweep: 'Clean sweep', on_a_roll: 'On a roll',
}
const achievementName = id => ACHIEVEMENT_NAMES[id] || id

// What changed between two progress readings; the first reading is never news.
export function progressNews(prev, next) {
  if (!prev) return []
  const news = []
  if (next.office.level > prev.office.level) news.push(`The office reached Lv ${next.office.level}`)
  for (const [chatId, chat] of Object.entries(next.chats)) {
    const before = prev.chats[chatId]?.level || 1
    if (chat.level > before) news.push(`${chat.title || 'A chat'} reached Lv ${chat.level}`)
  }
  const had = new Set(prev.achievements.map(a => a.id))
  for (const achievement of next.achievements) {
    if (!had.has(achievement.id)) news.push(`New achievement: ${achievementName(achievement.id)}`)
  }
  return news
}

// Opens by itself once a day; until the saved preferences have loaded, the
// day it last opened is unknown, so it waits rather than risk a second opening.
export function shouldAutoOpenRecap(recap, lastRecapDay, today, prefsLoaded) {
  return Boolean(recap) && prefsLoaded && lastRecapDay !== today
}

// The recap dialog has one control: Escape closes it, Tab stays on it.
export function dialogKey(key) {
  if (key === 'Escape') return 'close'
  if (key === 'Tab') return 'stay'
  return null
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

export function recapLines(recap, chats) {
  const lines = []
  if (recap.turns) lines.push(`${plural(recap.turns, 'turn', 'turns')} finished`)
  const done = recap.helpers_done || 0
  const failed = recap.helpers_failed || 0
  const stopped = recap.helpers_stopped || 0
  if (done || failed || stopped) {
    const others = [failed ? `${failed} failed` : '', stopped ? `${stopped} stopped` : ''].filter(Boolean)
    lines.push(done
      ? `${plural(done, 'helper', 'helpers')} came back${others.length ? `, ${others.join(', ')}` : ''}`
      : `Helpers: ${others.join(', ')}`)
  }
  if (recap.apps) lines.push(`${plural(recap.apps, 'app', 'apps')} shipped`)
  for (const up of recap.level_ups) lines.push(`${chats[up.chat_id]?.title || 'A chat'} reached Lv ${up.level}`)
  for (const id of recap.achievements) lines.push(`New achievement: ${achievementName(id)}`)
  if (recap.busiest) lines.push(`Busiest: ${recap.busiest.title || 'a chat'} (+${recap.busiest.xp} XP)`)
  return lines
}

export function localDay(date) {
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// --- Review fixes: level bar, screens, visibility-gated polling ---

// Share of the current level completed (the bar starts at the level's floor, not 0 XP).
export function levelShare(office) {
  const span = office.next_level_xp - office.level_start_xp
  return span > 0 ? Math.min(1, Math.max(0, (office.xp - office.level_start_xp) / span)) : 0
}

const KEY_CODES = new Set(['no_key', 'key_rejected'])

// Which screen to show: key trouble outranks an older scene; a slow Möbius keeps it.
export function officeView(snap, error, demo) {
  if (demo) return 'office'
  if (error && KEY_CODES.has(error.code)) return 'key_trouble'
  return snap ? 'office' : 'loading'
}

// Runs `load` now and every `intervalMs`, but only while the office is visible;
// `onVisible` catches up immediately when the office comes back into view.
export function createVisiblePoller({ load, intervalMs, isVisible, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let timer = null
  const schedule = () => { timer = setTimer(tick, intervalMs) }
  function tick() {
    if (isVisible()) load()
    schedule()
  }
  return {
    start() { if (isVisible()) load(); schedule() },
    onVisible() { if (isVisible()) load() },
    stop() { if (timer !== null) clearTimer(timer); timer = null },
  }
}

// --- Motion: staggered departures, the walk to the door, reduced motion -------

export const DEPARTURE_STAGGER_MS = 140

// Spec §6.5: a lead takes its whole team with a staggered poof, lead first.
export function departureDelays(ids) {
  return Object.fromEntries(ids.map((id, index) => [id, index * DEPARTURE_STAGGER_MS]))
}

// Where the door meets the floor: the middle of doorSpan, on the left wall by the lobby
// (y = depth - 2 to depth - 1.1; the elevator follows it).
export function doorSpot(room) {
  return { x: 0.35, y: round(room.depth - 1.55) }
}

// The on-screen distance from one floor spot to another, for a CSS walk.
export function walkOffset(P, from, to) {
  const [ax, ay] = P(from.x, from.y)
  const [bx, by] = P(to.x, to.y)
  return [round(bx - ax), round(by - ay)]
}

// Reports the reduced-motion preference now and whenever it changes.
export function watchReducedMotion(media, onChange) {
  if (!media) {
    onChange(false)
    return () => {}
  }
  const report = () => onChange(Boolean(media.matches))
  report()
  media.addEventListener('change', report)
  return () => media.removeEventListener('change', report)
}

// --- Visibility: pause work while the office can't be seen -------------------

// The office counts as visible only when its page is visible AND it is on
// screen. The shell can keep an app loaded in a hidden pane whose document
// still reports "visible"; an IntersectionObserver notices the frame has no
// on-screen area there (checked with a sandboxed frame like Möbius's).
export function createVisibilityGate({ doc, element, IntersectionObserverImpl, onChange }) {
  let onScreen = true
  const isVisible = () => doc.visibilityState !== 'hidden' && onScreen
  let last = isVisible()
  const report = () => {
    const now = isVisible()
    if (now !== last) {
      last = now
      onChange(now)
    }
  }
  const observer = IntersectionObserverImpl && element
    ? new IntersectionObserverImpl(entries => {
      onScreen = entries[entries.length - 1].isIntersecting
      report()
    })
    : null
  observer?.observe(element)
  doc.addEventListener('visibilitychange', report)
  return {
    isVisible,
    stop() {
      observer?.disconnect()
      doc.removeEventListener('visibilitychange', report)
    },
  }
}

// --- Readable text on narrow screens --------------------------------------------

// The scene shrinks to fit its width, so on a phone 8-unit text lands near 5 px.
// Text grows to stay about 9 px on screen, never shrinks, and at most doubles.
export const COMPACT_TEXT_SCALE = 1.3
export function textScaleFor(renderedWidth, viewW, { minPx = 9, basePx = 8, max = 2 } = {}) {
  if (!renderedWidth || !viewW) return 1
  return Math.min(max, Math.max(1, minPx / (basePx * (renderedWidth / viewW))))
}

// --- Quick reply (spec 2026-09-29) --------------------------------------------

// On a screen wider than 920 px, Open chat can put the full chat in a pane beside
// the office. Narrower, it navigates. (Since 2026-10-07 the card itself always sits
// below the office.)
export function openMode(windowWidth) {
  return windowWidth > 920 ? 'beside' : 'navigate'
}

// One question: a pick or typed text. Two or three: a pick for each.
export function canSendAnswers(question, picks, typed) {
  const questions = question?.questions || []
  if (questions.length === 1) return Boolean(picks?.[questions[0].id]) || Boolean((typed || '').trim())
  return questions.length > 0 && questions.every(q => Boolean(picks?.[q.id]))
}

// A double tap sends once: begin() is false while a send is in flight.
export function createSendGuard() {
  let busy = false
  return {
    begin() {
      if (busy) return false
      busy = true
      return true
    },
    end() { busy = false },
  }
}

export function replyStatus(result) {
  return result?.status === 'queued' ? "It's busy, so your message waits until its current step ends." : 'Sent.'
}

export function answerStatus(result) {
  return result?.answer_turn === 'none' ? 'Answered.' : "Answered. It's back at work."
}

const RETRY = "Couldn't send. Try again."
const PROBLEMS = {
  question_changed: 'This question changed. Take another look.',
  mobius_unavailable: RETRY,
  unconfirmed: RETRY,
  offline: RETRY,
  not_found: 'This chat is gone.',
}

// The spec's sentence for known problems; otherwise the back room's own words.
export function problemText(error) {
  return PROBLEMS[error?.code] || error?.message || RETRY
}

const FULL_CHAT = {
  secret: "It's asking for a secret. Those are typed only in the full chat's sealed card.",
  restart: "It's asking to restart Möbius. Answer in the full chat.",
  multi_pick: 'This one needs the full chat.',
  missing: "It's waiting on you. Open the full chat to answer.",
}

export function fullChatText(reason) {
  return FULL_CHAT[reason] || FULL_CHAT.multi_pick
}

// --- The Internet box: the coffee corner's black box with the red light ----------
// An IT Crowd joke (owner's idea, Oct 7). A hidden switch: the first press arms it
// silently, a deliberate second press within a few seconds turns it off and stops every
// working chat; while it's off, one press turns it back on and tells them to continue.

export const INTERNET_ARM_MS = 6000
export const INTERNET_MIN_GAP_MS = 600 // a double-click, double-tap or held key is not a second press

export function internetClick({ off, armedAt = 0, armedUntil = 0, busy = false }, now) {
  if (busy) return null
  if (off) return 'turn_on'
  if (now >= armedUntil) return 'arm'
  return now - armedAt >= INTERNET_MIN_GAP_MS ? 'turn_off' : null
}

const agents = n => `${n} agent${n === 1 ? '' : 's'}`
const andList = items => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`)

export function internetToast(result, turningOn) {
  if (!result?.ok) return `The Internet didn't switch: ${result?.error?.message || 'something went wrong.'}`
  if (turningOn) {
    const missed = result.failed_names || []
    const told = result.told ? ` Told ${agents(result.told)} to continue.` : ''
    const left = missed.length ? ` ${andList(missed)} didn't get the message: tell ${missed.length === 1 ? 'it' : 'them'} yourself.` : ''
    return `The Internet is back on.${told}${left}`
  }
  const stopped = (result.paused || 0) + (result.unconfirmed || 0)
  return stopped ? `You turned off the Internet. ${agents(stopped)} stopped.` : 'You turned off the Internet. Nobody was working, so nobody noticed.'
}

// --- The building: floors, the lobby and the elevator (spec 2026-10-08) ------
// Every floor is the same room: pods, plus a 2-tile lobby along the front. On the lobby's
// stretch of the left wall the door comes first, then the elevator.

export const doorSpan = room => [room.depth - 2, round(room.depth - 1.1)]
export const elevatorSpan = room => [room.depth - 1, round(room.depth - 0.1)]
export const elevatorSpot = room => ({ x: 0.4, y: round(room.depth - 0.55) })
export const crDeskSpot = room => ({ x: 3.2, y: round(room.depth - 1.1) }) // floor 1's lobby, near the door

export function onFloor(snap, floor) {
  return (snap?.characters || []).filter(c => (c.floor || 1) === floor)
}

export function floorBadges(snap) {
  return new Set((snap?.floors || []).filter(f => (f.counts?.needs_you || 0) > 0).map(f => f.floor))
}

export const floorLabel = (floor, floors) => `Floor ${floor} of ${floors}`

const SUMMARY = [['needs_you', 'needs you'], ['working', 'working'], ['error', 'error'], ['watching', 'watching'], ['on_break', 'on break']]

export function floorSummary(counts) {
  const parts = SUMMARY.filter(([key]) => (counts?.[key] || 0) > 0).map(([key, label]) => `${counts[key]} ${label}`)
  return parts.length ? parts.join(' · ') : 'Nobody here yet'
}

// Who changed floors since the last snapshot, as seen from `viewFloor`: arrivals walk in from the
// elevator, departures walk out to it. Agents new to the office (no previous floor) just appear.
export function floorMoves(previousFloors, characters, viewFloor) {
  const arrivals = new Set()
  const departures = []
  for (const character of characters) {
    const before = previousFloors[character.id]
    if (before === undefined || before === character.floor) continue
    if (character.floor === viewFloor) arrivals.add(character.id)
    else if (before === viewFloor) departures.push(character.id)
  }
  return { arrivals, departures }
}

// --- The walking man (spec 2026-10-08 §7.2) ----------------------------------
// The owner's own character: tap the floor or hold an arrow key to walk; walking into the
// elevator opens the floor list. His position lives on this screen only.

export const WALKER_SPEED = 2.5 // tiles a second, as in Break Room

export function walkerAt(walk, nowMs) {
  const [fx, fy] = walk.from
  const [tx, ty] = walk.to
  const dist = Math.hypot(tx - fx, ty - fy)
  const done = ((nowMs - walk.at) / 1000) * WALKER_SPEED
  if (dist === 0 || done >= dist) return [tx, ty]
  const share = Math.max(0, done) / dist
  return [fx + (tx - fx) * share, fy + (ty - fy) * share]
}

const within = (v, lo, hi) => Math.min(hi, Math.max(lo, v))
export const insideRoom = ([x, y], room) => [within(x, 0.45, room.width - 0.45), within(y, 0.45, room.depth - 0.45)]

// Arrow keys walk in screen directions; holding one aims far, and letting go stops him.
const SCREEN_DIRECTIONS = { ArrowUp: [-1, -1], ArrowDown: [1, 1], ArrowLeft: [-1, 1], ArrowRight: [1, -1] }
export function walkerTarget([x, y], key, room) {
  const dir = SCREEN_DIRECTIONS[key]
  return dir ? insideRoom([x + dir[0] * 20, y + dir[1] * 20], room) : null
}

export function nearElevator([x, y], room) {
  const lift = elevatorSpot(room)
  return Math.hypot(x - lift.x, y - lift.y) <= 0.5
}

// The floor tile under a point of the scene (the inverse of `project` at z = 0).
export function toFloorPoint(sx, sy, frame) {
  const a = (sx - frame.ox) / TILE // x - y
  const b = (2 * (sy - frame.oy)) / TILE // x + y
  return [(a + b) / 2, (b - a) / 2]
}

export const keysFree = ({ dialogOpen, focusTag }) => !dialogOpen && !['INPUT', 'TEXTAREA', 'SELECT'].includes(focusTag)

// --- Easter eggs on floors 2-4 (spec 2026-10-08 §7.3) -------------------------
// Screen-only fun: tap the floor's corner object. None of them touches a real agent.

export const GOSSIP = [
  'Did you hear about the merge?',
  'Who broke the build?',
  'Floor 1 has the Internet back.',
  'The sword is out again…',
  'Apparently there is cake on 3.',
  'Have you met the new hire?',
]
export const COOLER_EMPTY = "Nobody's on break. Back to work!"
export const PHONE_LINES = ['Hello, IT. Have you tried turning it off and on again?', 'Is it definitely plugged in?']
export const FIRE_TEXT = '🔥 Fire! Call 0118 999 881 999 119 725… 3'
const EGG_MS = { watercooler: 8000, phone: 6500, fire: 6000 }

export function eggMoment(egg, startedAt, now) {
  const t = startedAt == null ? -1 : now - startedAt
  if (t < 0 || t >= (EGG_MS[egg] || 0)) return { active: false }
  if (egg === 'phone') return t < 1500 ? { active: true, ringing: true, text: null } : { active: true, ringing: false, text: PHONE_LINES[t < 4000 ? 0 : 1] }
  if (egg === 'fire') return { active: true, text: FIRE_TEXT }
  return { active: true, text: null }
}

export const gossipFor = index => GOSSIP[index % GOSSIP.length]

// --- The CR desk (spec 2026-10-08 §7.4) ---------------------------------------
// Clanker Resources: the applicants' papers open a form, and Hire starts a real chat.

export const HIRE_TITLE_MAX = 80
export const HIRE_TEXT_MAX = 8000

export function hireProblem(title, text) {
  const name = (title || '').trim()
  const first = (text || '').trim()
  if (!name) return 'Give your new hire a name.'
  if (name.length > HIRE_TITLE_MAX) return 'Names can be up to 80 characters.'
  if (!first) return 'Write what they should start on.'
  if (first.length > HIRE_TEXT_MAX) return 'The first message can be up to 8,000 characters.'
  return null
}

export function hireToast(result, name) {
  if (result?.ok && result.name_locked === false) return `Hired ${name}. They're heading to a desk, though Möbius may rename the chat from its first message.`
  if (result?.ok) return `Hired ${name}. They're heading to a desk.`
  if (result?.created && result.error?.code === 'unconfirmed') return `${name} is hired, but Möbius didn't confirm their first message. Check the chat before sending it again.`
  if (result?.created) return `${name} is hired, but their first message didn't send. Open the chat to send it.`
  return `Couldn't hire ${name}: ${result?.error?.message || 'something went wrong.'}`
}

// A short arrow press still moves him a whole tile (spec 2026-10-08 §7.2): he stops at whichever is
// further along, where he is now or one tile from where the press started.
export function arrowStop(start, here, key, room) {
  const dir = SCREEN_DIRECTIONS[key]
  if (!dir) return here
  if (Math.hypot(here[0] - start[0], here[1] - start[1]) >= 1) return here
  const len = Math.hypot(dir[0], dir[1])
  return insideRoom([start[0] + dir[0] / len, start[1] + dir[1] / len], room)
}

// A toast with a button (Open chat) stays up long enough to press it.
export const toastMs = action => (action ? 15000 : 6500)
