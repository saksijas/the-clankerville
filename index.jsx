import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createApi } from './api.js'
import { DEMO_SNAPSHOT } from './demo.js'
import { INTERNET_ARM_MS, createHold, createVisibilityGate, createVisiblePoller, departureDelays, holdMs, internetClick, internetToast, localDay, nextPollDelay, officeView, openMode, progressNews, shouldAutoOpenRecap, swordToast, watchReducedMotion } from './domain.js'
import { CSS } from './theme.js'
import DetailCard from './ui/DetailCard.jsx'
import Recap from './ui/Recap.jsx'
import Scene from './ui/Scene.jsx'
import StatusStrip from './ui/StatusStrip.jsx'

const POLL_MS = 3000
const SWORD_HINT_MS = 5000
const STALE_MS = 10000
const KEY_TROUBLE = {
  no_key: "Möbius's owner key is missing. Restarting Möbius makes a new one.",
  key_rejected: "Möbius's owner key was rejected. This happens after “sign out everywhere”; restarting Möbius makes a new one.",
}

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

// Follows the device's reduced-motion setting live, not only when the office opens.
function useReducedMotion() {
  const [reduced, setReduced] = useState(() => Boolean(window.matchMedia?.(REDUCED_MOTION).matches))
  useEffect(() => watchReducedMotion(window.matchMedia?.(REDUCED_MOTION) || null, setReduced), [])
  return reduced
}

// The idle animation's ~2.6 fps tick; paused under reduced motion.
function useTicker(ms, paused) {
  const [f, setF] = useState(0)
  useEffect(() => {
    if (paused) return undefined
    const id = setInterval(() => setF(n => n + 1), ms)
    return () => clearInterval(id)
  }, [ms, paused])
  return f
}

// Whether the office can be seen: its page is visible and its pane is on
// screen (a hidden workspace pane keeps a "visible" document).
function useOnScreen() {
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const gate = createVisibilityGate({
      doc: document, element: document.body, IntersectionObserverImpl: window.IntersectionObserver, onChange: setVisible,
    })
    setVisible(gate.isVisible())
    return gate.stop
  }, [])
  return visible
}

// Polls the back room every 3 s while the office can be seen; backs off on
// failure; keeps the last good snapshot and flags it stale after 10 s.
function useOffice(api, visible) {
  const [state, setState] = useState({ snap: null, error: null, stale: false })
  const visibleRef = useRef(visible)
  visibleRef.current = visible
  const wakeRef = useRef(null)
  useEffect(() => {
    let alive = true
    let timer = null
    let inFlight = false
    let failures = 0
    let lastOk = Date.now()
    let seenFrom = Date.now() // staleness only counts time the office could be seen
    const since = () => Date.now() - Math.max(lastOk, seenFrom)
    const schedule = ms => { if (alive && timer === null) timer = setTimeout(tick, ms) }
    async function tick() {
      timer = null
      if (!alive || inFlight || !visibleRef.current) return
      inFlight = true
      const body = await api.snapshot()
      inFlight = false
      if (!alive) return
      if (body?.ok) {
        failures = 0
        lastOk = Date.now()
        setState({ snap: body, error: null, stale: false })
        schedule(POLL_MS)
      } else {
        failures += 1
        setState(prev => ({ snap: prev.snap, error: body?.error || { code: 'offline' }, stale: since() > STALE_MS }))
        schedule(nextPollDelay(failures - 1))
      }
    }
    // Coming back into view catches up at once instead of waiting for a timer.
    wakeRef.current = () => { seenFrom = Date.now(); clearTimeout(timer); timer = null; tick() }
    const staleCheck = setInterval(() => {
      if (visibleRef.current && since() > STALE_MS) setState(prev => (prev.stale ? prev : { ...prev, stale: true }))
    }, 2000)
    tick()
    return () => {
      alive = false
      wakeRef.current = null
      clearTimeout(timer)
      clearInterval(staleCheck)
    }
  }, [api])
  useEffect(() => { if (visible) wakeRef.current?.() }, [visible])
  const refresh = useCallback(() => wakeRef.current?.(), [])
  return { ...state, refresh }
}

// Progress (levels, achievements, recap) is caught up on open and every
// minute while the office can be seen; the working count feeds "Full house".
function useProgress(api, workingNow, enabled, visible) {
  const [progress, setProgress] = useState(null)
  const workingRef = useRef(workingNow)
  workingRef.current = workingNow
  const visibleRef = useRef(visible)
  visibleRef.current = visible
  const pollerRef = useRef(null)
  useEffect(() => {
    if (!enabled) return undefined
    let alive = true
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
    const load = async () => {
      const body = await api.progress(workingRef.current, zone)
      if (alive && body?.ok) setProgress(body)
    }
    const poller = createVisiblePoller({ load, intervalMs: 60000, isVisible: () => visibleRef.current })
    pollerRef.current = poller
    poller.start()
    return () => { alive = false; pollerRef.current = null; poller.stop() }
  }, [api, enabled])
  useEffect(() => { if (visible) pollerRef.current?.onVisible() }, [visible])
  return progress
}

// The demo flag lives in app storage (ui.json), so it survives reloads and
// can be switched on from outside the app for visual checks.
function useUiPrefs() {
  const [prefs, setPrefs] = useState({})
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    const store = window.mobius?.storage
    if (!store) { setLoaded(true); return undefined }
    // The subscription fires at once with the current value (null when missing).
    return store.subscribe('ui.json', value => { setPrefs(value || {}); setLoaded(true) })
  }, [])
  const update = async change => {
    setPrefs(prev => ({ ...prev, ...change }))
    const store = window.mobius?.storage
    if (!store) return
    try {
      const prev = (await store.get('ui.json')) || {}
      await store.set('ui.json', { ...prev, ...change })
    } catch (err) {
      window.mobius?.signal?.('error', { message: String(err?.message || err), source: 'ui-prefs' })
    }
  }
  return [prefs, update, loaded]
}

const SWORD_SVG = "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><path d='M4 4 L20 20' stroke='#eef2f6' stroke-width='4.5' stroke-linecap='round'/><path d='M4 4 L20 20' stroke='#8d9aa8' stroke-width='1.2'/><path d='M15.5 24.5 L24.5 15.5' stroke='#c8962f' stroke-width='3.5' stroke-linecap='round'/><path d='M21 21 L27.5 27.5' stroke='#6b4a2b' stroke-width='3.5' stroke-linecap='round'/><circle cx='28.3' cy='28.3' r='2.2' fill='#e0b04b'/></svg>"
const SWORD_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(SWORD_SVG)}") 4 4, crosshair`

export default function App({ appId, token }) {
  const api = useMemo(() => createApi(appId, token), [appId, token])
  const onScreen = useOnScreen()
  const { snap, stale, error, refresh } = useOffice(api, onScreen)
  const [prefs, updatePrefs, prefsLoaded] = useUiPrefs()
  const reducedMotion = useReducedMotion()
  const f = useTicker(380, reducedMotion)
  const [selectedId, setSelectedId] = useState(null)
  const [swordOn, setSwordOn] = useState(false)
  const [hold, setHold] = useState(null)
  const [departed, setDeparted] = useState({})
  const [toast, setToast] = useState(null)
  const [recapOpen, setRecapOpen] = useState(false)
  // The sword's how-to shows for a few seconds after it's drawn, then clears the
  // top of the room (on a phone it covers the back row's bubbles); the red
  // "Sword on" button keeps saying the sword is out.
  const [swordHint, setSwordHint] = useState(false)
  useEffect(() => {
    if (!swordOn) { setSwordHint(false); return undefined }
    setSwordHint(true)
    const id = setTimeout(() => setSwordHint(false), SWORD_HINT_MS)
    return () => clearTimeout(id)
  }, [swordOn])
  const readySignalled = useRef(false)
  const demo = Boolean(prefs.demo)
  const shown = demo ? DEMO_SNAPSHOT : snap
  const shownRef = useRef(shown)
  shownRef.current = shown

  const say = text => {
    const id = Date.now()
    setToast({ id, text })
    setTimeout(() => setToast(current => (current && current.id === id ? null : current)), 6500)
  }

  // The Internet box (the coffee corner's black box), a hidden switch: the first press arms it
  // silently, a deliberate second press turns it off; one more press turns it back on.
  const [internetArmed, setInternetArmed] = useState(null) // { at, until } after the first press
  const [internetBusy, setInternetBusy] = useState(false)
  const [internetLocal, setInternetLocal] = useState(null) // the last switch, until a snapshot agrees
  useEffect(() => {
    if (!internetArmed) return undefined
    const t = setTimeout(() => setInternetArmed(null), Math.max(0, internetArmed.until - Date.now()))
    return () => clearTimeout(t)
  }, [internetArmed])
  useEffect(() => { setInternetLocal(null) }, [demo])
  useEffect(() => {
    if (!demo && internetLocal && snap?.internet && snap.internet.off === internetLocal.off) setInternetLocal(null)
  }, [snap, internetLocal, demo])

  const workingNow = snap ? snap.characters.filter(c => c.state === 'working' || c.state === 'busy').length : 0
  const progress = useProgress(api, workingNow, Boolean(snap) && !demo, onScreen)
  const previousProgress = useRef(null)
  useEffect(() => {
    if (!progress) return
    const news = progressNews(previousProgress.current, progress)
    previousProgress.current = progress
    if (news.length) say(news.join(' · '))
  }, [progress])

  // Its own effect, so a recap that arrived before the saved preferences
  // still opens (once) as soon as they load.
  useEffect(() => {
    if (!progress) return
    const today = localDay(new Date())
    if (shouldAutoOpenRecap(progress.recap, prefs.lastRecapDay, today, prefsLoaded)) {
      setRecapOpen(true)
      updatePrefs({ lastRecapDay: today })
    }
  }, [progress, prefsLoaded, prefs.lastRecapDay])

  // A fresher snapshot is the truth: once one was generated after a departure,
  // it no longer carries the deleted chat or the dismissed helper.
  useEffect(() => {
    if (!snap) return
    const generated = Date.parse(snap.generated_at)
    setDeparted(current => {
      const kept = Object.fromEntries(Object.entries(current).filter(([, gone]) => gone.at >= generated))
      return Object.keys(kept).length === Object.keys(current).length ? current : kept
    })
  }, [snap])

  const holdRef = useRef(null)
  if (holdRef.current === null) holdRef.current = createHold()
  async function finishHold(id) {
    setHold(null)
    const office = shownRef.current
    const character = office?.characters.find(c => c.id === id)
    if (!character) return
    const kind = character.kind === 'helper' ? 'helper' : 'chat'
    const team = kind === 'chat' ? (office.teams.find(t => t.lead_id === id)?.member_ids || []) : []
    const demoResult = kind === 'chat'
      ? { ok: true, deleted: true, cancelled_helpers: team.length, discarded_messages: character.queued || 0 }
      : { ok: true, dismissed: true }
    const result = office === DEMO_SNAPSHOT ? demoResult : await api.sword(kind, id)
    if (result.ok) {
      const at = Date.now()
      const delays = departureDelays([id, ...team])
      setDeparted(current => ({ ...current, ...Object.fromEntries(Object.entries(delays).map(([key, delay]) => [key, { at, delay }])) }))
    }
    say(swordToast(character, result) + (office === DEMO_SNAPSHOT && result.ok ? ' (Demo: nothing real happened.)' : ''))
    window.mobius?.signal?.('sword_swing', { kind, ok: Boolean(result.ok) })
  }
  const startHold = character => {
    if (!character.dismissable || departed[character.id]) return
    const ms = holdMs(character)
    setSelectedId(character.id)
    setHold({ id: character.id, ms, key: Date.now() })
    holdRef.current.start(character.id, ms, finishHold)
  }
  const cancelHold = () => {
    if (holdRef.current.activeId() === null) return
    holdRef.current.cancel()
    setHold(null)
  }

  useEffect(() => {
    const onKey = event => { if (event.key === 'Escape') { cancelHold(); setSwordOn(false) } }
    const onUp = () => cancelHold()
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      holdRef.current?.cancel()
    }
  }, [])

  useEffect(() => {
    if (snap && !readySignalled.current) {
      readySignalled.current = true
      window.mobius?.signal?.('app_ready', { item_count: snap.characters.length })
    }
  }, [snap])

  const view = officeView(snap, error, demo)
  if (view !== 'office') {
    const trouble = view === 'key_trouble' ? KEY_TROUBLE[error.code] : null
    return (
      <div className="ao-root">
        <style>{CSS}</style>
        <div className="ao-screen">
          <div className="ao-card" role="status" style={{ maxWidth: 440 }}>
            <h2>{trouble ? "Can't see your agents right now" : 'Opening the office…'}</h2>
            {trouble && <p>{trouble}</p>}
            {trouble && <button type="button" className="ao-btn" onClick={() => updatePrefs({ demo: true })}>Show demo</button>}
          </div>
        </div>
      </div>
    )
  }

  const internet = internetLocal || shown.internet || { off: false, paused: 0 }
  const pressInternet = async () => {
    const now = Date.now()
    const action = internetClick({ off: internet.off, armedAt: internetArmed?.at, armedUntil: internetArmed?.until, busy: internetBusy }, now)
    if (!action) return
    if (action === 'arm') { setInternetArmed({ at: now, until: now + INTERNET_ARM_MS }); return }
    setInternetArmed(null)
    const turningOn = action === 'turn_on'
    if (demo) {
      setInternetLocal({ off: !turningOn, paused: 0 })
      say(`${turningOn ? 'The Internet is back on.' : 'You turned off the Internet.'} (Demo: nothing real happened.)`)
      return
    }
    setInternetBusy(true)
    const result = await api.internet(turningOn)
    setInternetBusy(false)
    if (result.ok) setInternetLocal({ off: result.off, paused: turningOn ? 0 : (result.paused || 0) + (result.unconfirmed || 0) })
    say(internetToast(result, turningOn))
    refresh()
    window.mobius?.signal?.('internet_switch', { on: turningOn, ok: Boolean(result.ok) })
  }
  const empty = !demo && shown.characters.length === 0
  const recapShown = recapOpen && !demo && Boolean(progress?.recap)
  const selected = shown.characters.find(c => c.id === selectedId) || null
  const leadId = selected ? (selected.kind === 'helper' ? selected.lead_id : selected.id) : null
  const lead = shown.characters.find(c => c.id === leadId)
  const teamRow = shown.teams.find(t => t.lead_id === leadId)
  const team = selected && selected.kind === 'chat' && teamRow ? teamRow.member_ids.map(id => shown.characters.find(c => c.id === id)).filter(Boolean) : []
  const toggleSword = () => { cancelHold(); setSwordOn(on => !on) }
  // On a computer the full chat opens in a pane beside the office; on a phone,
  // or if Möbius can't place it, it switches to the chat as before. The device's
  // screen decides, not the office's frame: in Builder mode the office pane can
  // be narrower than 920 px on a wide computer screen.
  const besideScreen = openMode(window.screen?.width || window.innerWidth) === 'beside'
  const openChat = async chatId => {
    if (demo) { say('In your real office, this opens the chat.'); return }
    if (besideScreen) {
      const result = await api.openBeside(chatId)
      if (result?.ok) return
    }
    window.parent.postMessage({ type: 'moebius:open-chat', chatId }, '*')
  }

  return (
    <div className="ao-root">
      <style>{CSS}</style>
      {demo && (
        <div className="ao-banner" role="status">
          <span>Demo, not your agents</span>
          <button type="button" className="ao-btn" onClick={() => updatePrefs({ demo: false })}>Exit demo</button>
        </div>
      )}
      <div className="ao-layout" inert={recapShown ? true : undefined}>
        <section className="ao-main">
          <StatusStrip office={shown.office} counts={shown.counts} stale={stale && !demo} swordOn={swordOn} onSword={toggleSword}
            onRecap={!demo && progress?.recap ? () => setRecapOpen(true) : undefined} />
          <div className="ao-scene" style={swordOn ? { cursor: SWORD_CURSOR } : undefined}>
            <Scene snap={shown} f={f} selectedId={selectedId} onSelect={setSelectedId} onPress={startHold} onRelease={cancelHold}
              swordOn={swordOn} hold={hold} departed={departed}
              internetOff={internet.off} internetArmed={Boolean(internetArmed)} onInternet={pressInternet} />
            {swordOn && swordHint && <div className="ao-hint">Hold on someone: a chat is deleted, a helper dismissed · Tap Sword or press Esc to put it away</div>}
            {internetBusy && <div className="ao-hint">{internet.off ? 'Turning the Internet back on…' : 'Turning the Internet off…'}</div>}
            {internet.off && !internetBusy && (
              <div className="ao-internet-off" role="status">
                <b>📴 You turned off the Internet</b>
                <span>{internet.paused ? `${internet.paused} chat${internet.paused === 1 ? '' : 's'} stopped · ` : ''}press the black box again to turn it back on</span>
              </div>
            )}
            {empty && (
              <div className="ao-empty">
                <span>Everyone's gone home. Start a chat and someone will show up.</span>
                <button type="button" className="ao-btn" onClick={() => updatePrefs({ demo: true })}>Show demo</button>
              </div>
            )}
            <div className="ao-toast-wrap" aria-live="polite">{toast && <div className="ao-toast">{toast.text}</div>}</div>
          </div>
        </section>
        <DetailCard character={selected} team={team} overflow={selected?.kind === 'chat' ? selected.overflow || 0 : 0}
          leadName={lead?.short || 'lead'} onOpenChat={openChat} onHoldStart={startHold} onHoldCancel={cancelHold}
          holding={hold && selected && hold.id === selected.id ? hold : null}
          api={api} demo={demo} openLabel={besideScreen ? 'Open chat' : 'Open full chat'} />
      </div>
      {recapShown && <Recap recap={progress.recap} chats={progress.chats} onClose={() => setRecapOpen(false)} />}
    </div>
  )
}
