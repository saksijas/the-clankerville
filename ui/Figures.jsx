import React from 'react'
import { crDeskSpot, declutter, elevatorSpan, wallTextTransform } from '../domain.js'

/* SVG pieces of the office, drawn in isometric space through a projection
   `P(x, y, z) -> [sx, sy]` that the Scene supplies. Art follows the approved
   mockup (docs/superpowers/specs/assets/2026-09-28-agent-office-mockup-office.jsx). */

export const SCREEN = {
  working: '#3fcf8e', needs_you: '#ffc53d', error: '#ff5c5c', watching: '#7fb2ff', on_break: '#3a4152',
  busy: '#3fcf8e', on_hold: '#9aa3b2', done: '#3fcf8e', failed: '#ff5c5c',
}
const TINT = { needs_you: '#ffe08a', error: '#ffd3d3' }
const DESK_W = 1.2
const DESK_D = 0.6

const pts = list => list.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(' ')

export function isoBox(P, x, y, dx, dy, h, z, [top, left, right]) {
  return [
    <polygon key="l" points={pts([P(x, y + dy, z), P(x + dx, y + dy, z), P(x + dx, y + dy, z + h), P(x, y + dy, z + h)])} fill={left} />,
    <polygon key="r" points={pts([P(x + dx, y, z), P(x + dx, y + dy, z), P(x + dx, y + dy, z + h), P(x + dx, y, z + h)])} fill={right} />,
    <polygon key="t" points={pts([P(x, y, z + h), P(x + dx, y, z + h), P(x + dx, y + dy, z + h), P(x, y + dy, z + h)])} fill={top} />,
  ]
}

export function floorQuad(P, x, y, dx, dy) {
  return pts([P(x, y), P(x + dx, y), P(x + dx, y + dy), P(x, y + dy)])
}

export function Desk({ P, desk, state, lead, f }) {
  const { x, y } = desk
  const mx = x + 0.35
  const my = y + 0.04
  const [sx, sy] = P(mx + 0.3, my, 30)
  const [fx, fy] = P(x + DESK_W - 0.1, y + 0.08, 14)
  return (
    <g>
      {isoBox(P, x, y, DESK_W, DESK_D, 14, 0, ['#b98457', '#9a6a44', '#855a39'])}
      <Keyboard P={P} x={x + 0.36} y={y + 0.3} />
      {isoBox(P, mx, my, 0.5, 0.11, 13, 14, ['#3a3f4f', '#262a35', '#1f2330'])}
      <polygon points={pts([P(mx + 0.05, my + 0.11, 16), P(mx + 0.45, my + 0.11, 16), P(mx + 0.45, my + 0.11, 25), P(mx + 0.05, my + 0.11, 25)])} fill={SCREEN[state] || SCREEN.on_break} />
      {(state === 'error' || state === 'failed') && (
        <>
          <circle cx={sx + (f % 2)} cy={sy - (f % 3) * 2} r="3.5" fill="#c7c9d2" opacity=".8" />
          <circle cx={sx + 5 - (f % 2)} cy={sy - 7 - (f % 2) * 2} r="2.5" fill="#d9dbe2" opacity=".7" />
        </>
      )}
      {lead && <><line x1={fx} y1={fy} x2={fx} y2={fy - 20} stroke="#6b5a4a" strokeWidth="1.5" /><polygon points={`${fx},${fy - 20} ${fx + 12},${fy - 16} ${fx},${fy - 12}`} fill="#ffd166" /></>}
    </g>
  )
}

// A keyboard on the desk top, in front of the monitor, where a seated agent's hands are.
function Keyboard({ P, x, y }) {
  const w = 0.44
  const d = 0.16
  const top = 15.4
  return (
    <g>
      {isoBox(P, x, y, w, d, 1.4, 14, ['#e4e6ee', '#b4b8c6', '#9da2b2'])}
      {[0.055, 0.105].map(row => {
        const [x1, y1] = P(x + 0.04, y + row, top)
        const [x2, y2] = P(x + w - 0.04, y + row, top)
        return <line key={row} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#9aa0b0" strokeWidth=".7" strokeDasharray="1.6 .9" />
      })}
    </g>
  )
}

export function Chair({ P, seat }) {
  const [cx, cy] = P(seat.x, seat.y)
  return <rect x={cx - 9} y={cy - 15} width="18" height="11" rx="3" fill="#3d4459" />
}

export function Person({ P, spot, look, pose, f, className, style }) {
  const [sx, sy] = P(spot.x, spot.y)
  const t = f % 2 ? 1 : -1
  const seated = pose === 'type' || pose === 'slump' || pose === 'sit'
  const slump = pose === 'slump' ? 3 : 0
  return (
    <g className={className} style={style}>
      <ellipse cx={sx} cy={sy} rx="10" ry="4.5" fill="rgba(30,20,60,.18)" />
      {seated ? (
        <>
          <rect x={sx - 9} y={sy - 15} width="18" height="11" rx="3" fill="#3d4459" />
          <rect x={sx - 8} y={sy - 28 + slump} width="16" height="17" rx="7" fill={look.shirt} />
          {pose === 'type' && <><circle cx={sx + 5} cy={sy - 27 + t} r="2.4" fill={look.skin} /><circle cx={sx + 9} cy={sy - 24 - t} r="2.4" fill={look.skin} /></>}
          <circle cx={sx} cy={sy - 34 + slump} r="7.5" fill={look.hair} />
        </>
      ) : (
        <>
          <rect x={sx - 6} y={sy - 13} width="5" height="13" rx="2" fill="#3a3f55" />
          <rect x={sx + 1} y={sy - 13} width="5" height="13" rx="2" fill="#3a3f55" />
          <rect x={sx - 8} y={sy - 31} width="16" height="20" rx="7" fill={look.shirt} />
          {pose === 'wave' && <><line x1={sx + 6} y1={sy - 27} x2={sx + 12 + t} y2={sy - 45} stroke={look.shirt} strokeWidth="4.5" strokeLinecap="round" /><circle cx={sx + 12 + t} cy={sy - 47} r="2.8" fill={look.skin} /></>}
          {pose === 'mug' && <><rect x={sx + 6} y={sy - 25} width="6" height="7" rx="1.5" fill="#fff" stroke="#c9c2dd" strokeWidth=".6" /><path d={`M ${sx + 9} ${sy - 28} q 2 -3 0 -6`} stroke="#fff" strokeWidth="1" fill="none" opacity={f % 2 ? 0.9 : 0.4} /></>}
          <circle cx={sx} cy={sy - 38} r="7.5" fill={look.skin} />
          <path d={`M ${sx - 7.5} ${sy - 39} A 7.5 7.5 0 0 1 ${sx + 7.5} ${sy - 39} Z`} fill={look.hair} />
          <circle cx={sx - 2.6} cy={sy - 36.5} r="1" fill="#1b1b24" /><circle cx={sx + 2.6} cy={sy - 36.5} r="1" fill="#1b1b24" />
        </>
      )}
    </g>
  )
}

// Where a character's head is on screen: anchors for bubbles, chips and badges.
export function headOf(P, spot, pose) {
  const [sx, sy] = P(spot.x, spot.y)
  const seated = pose === 'type' || pose === 'slump' || pose === 'sit'
  return [sx, seated ? sy - 42 : pose === 'wave' ? sy - 51 : sy - 46]
}

export function HelperChip({ head, state, f }) {
  const [hx, hy] = head
  return (
    <g>
      <rect x={hx + 4} y={hy - 12} width="22" height="11" rx="5.5" fill="#fff" stroke="#2a2340" strokeWidth=".8" />
      {state === 'busy' && [0, 1, 2].map(i => <circle key={i} cx={hx + 9.5 + i * 5.5} cy={hy - 6.5} r="1.6" fill="#2a2340" opacity={(f + i) % 3 === 0 ? 1 : 0.35} />)}
      {state === 'on_hold' && <><rect x={hx + 11} y={hy - 10} width="2.4" height="7" fill="#6b6488" /><rect x={hx + 16} y={hy - 10} width="2.4" height="7" fill="#6b6488" /></>}
      {state === 'done' && <path d={`M ${hx + 10} ${hy - 6.5} l 3 3 l 6 -6`} stroke="#1f9d61" strokeWidth="1.8" fill="none" strokeLinecap="round" />}
      {state === 'failed' && <text x={hx + 15} y={hy - 3.2} fontSize="9" fontWeight="800" textAnchor="middle" fill="#e5484d">!</text>}
    </g>
  )
}

// A little cloud where someone vanished; the inner group animates, so its CSS
// transform doesn't replace the placement transform.
export function Poof({ x, y, delay }) {
  return (
    <g transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`} pointerEvents="none">
      <g className="ao-poof" style={{ animationDelay: `${delay}ms` }}>
        <circle cx="-8" cy="1" r="6.5" fill="#f4f1fb" stroke="#c9c2dd" strokeWidth=".8" />
        <circle cx="6" cy="-2" r="7.5" fill="#fff" stroke="#c9c2dd" strokeWidth=".8" />
        <circle cx="-1" cy="-9" r="5.5" fill="#fff" stroke="#c9c2dd" strokeWidth=".8" />
        <circle cx="9" cy="6" r="4.5" fill="#f4f1fb" stroke="#c9c2dd" strokeWidth=".8" />
      </g>
    </g>
  )
}

export function Badge({ head, state, scale = 1 }) {
  const [hx, hy] = head
  const warn = state === 'needs_you'
  const s = Math.min(scale, 1.5) // a bigger "!" stays beside the head, not over it
  return (
    <g className={warn ? 'ao-pulse' : undefined}>
      <circle cx={hx - 13 * s} cy={hy + 8} r={6.5 * s} fill={warn ? '#ffc53d' : '#ff5c5c'} stroke="#fff" strokeWidth="1.2" />
      <text x={hx - 13 * s} y={hy + 8 + 3.2 * s} fontSize={9 * s} fontWeight="800" textAnchor="middle" fill={warn ? '#2a2340' : '#fff'}>!</text>
    </g>
  )
}

export function Bubbles({ items, width, obstacles, scale = 1 }) {
  const size = 8 * scale, h = 15 * scale
  return declutter(items, { charW: 4.4 * scale, pad: 6 * scale, h, width, obstacles }).map(b => {
    const left = b.cx - b.w / 2
    const tx = Math.min(Math.max(b.ax, left + 8 * scale), left + b.w - 8 * scale)
    return (
      <g key={`b-${b.id}`} fontSize={size} className={b.state === 'needs_you' ? 'ao-pulse' : undefined}>
        <line x1={tx} y1={b.top + h} x2={b.ax} y2={b.ay} stroke="#2a2340" strokeWidth="1" />
        <rect x={left} y={b.top} width={b.w} height={h} rx={7 * scale} fill={TINT[b.state] || '#fffdf7'} stroke="#2a2340" strokeWidth=".9" />
        <text x={b.cx} y={b.top + h / 2 + size * 0.36} textAnchor="middle" fill="#1d1a2b">{b.text}</text>
      </g>
    )
  })
}

// The coffee corner's black box with the red light is also the Internet (an IT Crowd
// joke): pressing it arms it, pressing again turns it off; while off, its light is dark.
export function CoffeeCorner({ P, origin, f, off = false, armed = false, onPress }) {
  const x = origin.x + 2.7
  const y = origin.y + 0.5
  const [lx, ly] = P(x + 0.35, y + 0.6, 18)
  const light = off ? '#3a2226' : armed ? '#ff3b3b' : f % 2 ? '#ff6b6b' : '#b83b3b'
  const press = event => { event.stopPropagation(); onPress?.() }
  return (
    <g className={onPress ? 'ao-internet' : undefined} role={onPress ? 'button' : undefined} tabIndex={onPress ? 0 : undefined}
      aria-label={onPress ? (off ? 'The Internet, turned off. Turn it back on' : 'The Internet') : undefined}
      onClick={onPress ? press : undefined} onPointerDown={onPress ? event => event.stopPropagation() : undefined}
      onKeyDown={onPress ? event => { if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) { event.preventDefault(); press(event) } } : undefined}>
      {isoBox(P, x, y, 0.7, 0.6, 26, 0, ['#5a6072', '#3b3f4c', '#30343f'])}
      <circle cx={lx} cy={ly} r="2" fill={light} />
      {armed && !off && <circle cx={lx} cy={ly} r="5.5" fill="none" stroke="#ff6b6b" strokeWidth="1.2" opacity=".8" />}
    </g>
  )
}

export function Plant({ P, x, y }) {
  const [a, b] = P(x + 0.17, y + 0.17, 16)
  return <g>{isoBox(P, x, y, 0.35, 0.35, 9, 0, ['#c9774a', '#b5653a', '#9c5431'])}<circle cx={a} cy={b} r="9" fill="#3fae5a" /><circle cx={a + 3} cy={b - 6} r="6" fill="#58c472" /></g>
}

// The elevator on the lobby's stretch of the left wall (spec 2026-10-08 §7.1): steel doors, the
// floor number lit above them, and a red dot when another floor needs you. Pressing it opens the
// floor picker, like walking into it.
export function Elevator({ P, room, floor, dot, onPress }) {
  const [e0, e1] = elevatorSpan(room)
  const mid = (e0 + e1) / 2
  const quad = (a, b, z0, z1) => [P(0, a, z0), P(0, b, z0), P(0, b, z1), P(0, a, z1)].map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const [lx, ly] = P(0, mid, 55)
  const press = event => { event.stopPropagation(); onPress?.() }
  return (
    <g className="ao-lift" role="button" tabIndex={0} aria-label={`Elevator. You're on floor ${floor}`}
      onClick={press} onPointerDown={event => event.stopPropagation()}
      onKeyDown={event => { if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) { event.preventDefault(); press(event) } }}>
      <polygon points={quad(e0, e1, 0, 50)} fill="#6f7688" />
      <polygon points={quad(e0 + 0.06, mid - 0.015, 2, 46)} fill="#c9ced9" />
      <polygon points={quad(mid + 0.015, e1 - 0.06, 2, 46)} fill="#bcc2cf" />
      <polygon points={quad(mid - 0.22, mid + 0.22, 51, 59)} fill="#1f2330" />
      <text x={lx} y={ly + 2.4} fontSize="7" fontWeight="700" fill="#3fcf8e" textAnchor="middle" transform={wallTextTransform('left', lx, ly)}>{floor}</text>
      {dot && <circle cx={P(0, e1 - 0.12, 56)[0]} cy={P(0, e1 - 0.12, 56)[1]} r="2.6" fill="#ff5c5c" stroke="#fff" strokeWidth=".8" />}
    </g>
  )
}

// Floors 2-4's corners (spec 2026-10-08 §7.3), where the floor's on-break agents hang out.
// Each one is a hidden button, like floor 1's Internet box; none of them touches a real agent.
function eggButton(label, onPress) {
  const press = event => { event.stopPropagation(); onPress?.() }
  return {
    className: 'ao-egg', role: 'button', tabIndex: 0, 'aria-label': label, onClick: press,
    onPointerDown: event => event.stopPropagation(),
    onKeyDown: event => { if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) { event.preventDefault(); press(event) } },
  }
}

export function Watercooler({ P, origin, active, onPress }) {
  const x = origin.x + 2.7
  const y = origin.y + 0.5
  const [bx, by] = P(x + 0.3, y + 0.3, 24)
  return (
    <g {...eggButton('Watercooler', onPress)}>
      {isoBox(P, x, y, 0.6, 0.6, 24, 0, ['#e9edf3', '#c9cfdb', '#b4bccb'])}
      <rect x={bx - 7} y={by - 22} width="14" height="20" rx="5" fill="#9fd3f5" stroke="#6fb6e6" strokeWidth=".8" />
      <rect x={bx - 3} y={by - 25} width="6" height="4" rx="1" fill="#6fb6e6" />
      {active && [0, 1, 2].map(i => (
        <circle key={i} className="ao-bubble-rise" cx={bx - 3 + i * 3} cy={by - 6} r="1.4" fill="#fff" style={{ animationDelay: `${i * 0.35}s` }} />
      ))}
    </g>
  )
}

export function PhoneCorner({ P, origin, ringing, onPress }) {
  const x = origin.x + 2.7
  const y = origin.y + 0.5
  const [hx, hy] = P(x + 0.35, y + 0.3, 18)
  return (
    <g {...eggButton('Phone', onPress)}>
      {isoBox(P, x, y, 0.7, 0.6, 14, 0, ['#b98457', '#9a6a44', '#855a39'])}
      <g className={ringing ? 'ao-ringing' : undefined}>
        {isoBox(P, x + 0.15, y + 0.15, 0.4, 0.3, 3, 14, ['#3a3f4f', '#262a35', '#1f2330'])}
        <rect x={hx - 6} y={hy - 3} width="12" height="3.4" rx="1.7" fill="#e5484d" />
        {ringing && <g fill="none" stroke="#e5484d" strokeWidth="1"><path d={`M ${hx + 8} ${hy - 8} q 3 3 0 6`} /><path d={`M ${hx - 8} ${hy - 8} q -3 3 0 6`} /></g>}
      </g>
    </g>
  )
}

const FLAME_SPOTS = [[-1.2, 1.0], [-0.4, 1.6], [0.4, 0.9]]
export function FireCorner({ P, origin, active, onPress }) {
  const x = origin.x + 2.7
  const y = origin.y + 0.5
  const [lx, ly] = P(x + 0.25, y + 0.4, 13)
  return (
    <g {...eggButton('In case of fire', onPress)}>
      {isoBox(P, x, y, 0.5, 0.4, 22, 0, ['#ff8a80', '#e5484d', '#c43a3f'])}
      <text x={lx} y={ly} fontSize="4.2" fontWeight="800" fill="#fff" textAnchor="middle">FIRE</text>
      {active && FLAME_SPOTS.map(([dx, dy], i) => {
        const [fx, fy] = P(x + dx, y + dy)
        return (
          <g key={i} className="ao-flicker" style={{ animationDelay: `${i * 0.15}s`, transformOrigin: `${fx}px ${fy}px` }}>
            <path d={`M ${fx - 7} ${fy} Q ${fx - 6} ${fy - 14} ${fx} ${fy - 22} Q ${fx + 6} ${fy - 14} ${fx + 7} ${fy} Z`} fill="#ff7a1a" />
            <path d={`M ${fx - 4} ${fy} Q ${fx - 3} ${fy - 8} ${fx} ${fy - 13} Q ${fx + 3} ${fy - 8} ${fx + 4} ${fy} Z`} fill="#ffd166" />
          </g>
        )
      })}
    </g>
  )
}

// The CR desk, Clanker Resources (spec 2026-10-08 §7.4): a reception desk in floor 1's lobby with a
// stack of applicants' papers and a quiet "Hire" label. Pressing it opens the hire form.
export function CRDesk({ P, room, onPress, scale: textScale = 1 }) {
  const scale = Math.min(textScale, 1.3) // grows for phones, but stays clear of the Former staff board beside it
  const { x, y } = crDeskSpot(room)
  const [sx, fy] = P(x + 0.65, y + 0.6, 0)
  const [tx, ty] = P(x + 0.95, y + 0.55, 15)
  // Just a quiet "Hire" under the desk; the form it opens is titled CR · Clanker Resources.
  return (
    <g {...eggButton('Hire a new clanker (CR · Clanker Resources)', onPress)}>
      {isoBox(P, x, y, 1.3, 0.6, 14, 0, ['#d6b48a', '#b8915f', '#a07a4c'])}
      {[0, 1, 2].map(i => <g key={i}>{isoBox(P, x + 0.7, y + 0.2, 0.42, 0.3, 1, 14 + i * 1.3, ['#fffdf7', '#e9e4d8', '#ddd6c6'])}</g>)}
      <text x={sx} y={fy + 8 * textScale} fontSize={7.5 * textScale} fontWeight="700" fill="#6d5dfc" stroke="#fff" strokeWidth={2.4 * textScale} paintOrder="stroke" strokeLinejoin="round" textAnchor="middle">Hire</text>
      <text x={tx} y={ty + 5 * scale} fontSize={4.2 * scale} fontWeight="700" fill="#2a2340" stroke="#fff" strokeWidth={1.2 * scale} paintOrder="stroke" textAnchor="middle">Applicants</text>
    </g>
  )
}

// Former staff (owner's idea, 2026-10-08): a freestanding corkboard in floor 1's lobby, beside the CR
// desk, with the deleted agents Möbius can still recover pinned up as little cards. In the lobby no
// agent or speech bubble stands in front of it. Pressing it opens the rehire list.
export const FORMER_BOARD = { x0: 7.0, x1: 9.8, y: 10.55 }
export function FormerBoard({ P, staff, onPress, scale = 1 }) {
  const { x0, x1, y } = FORMER_BOARD
  const z0 = 9
  const z1 = 42
  const quad = (a, b, za, zb) => [P(a, y, za), P(b, y, za), P(b, y, zb), P(a, y, zb)].map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(' ')
  const [hx, hy] = P((x0 + x1) / 2, y, z1 - 7)
  const leg = a => { const [lx0, ly0] = P(a, y, 0); const [lx1, ly1] = P(a, y, z0); return <line key={a} x1={lx0} y1={ly0} x2={lx1} y2={ly1} stroke="#6b4a33" strokeWidth="2" /> }
  const pinned = staff.slice(0, 4)
  const more = staff.length - pinned.length
  return (
    <g {...eggButton(`Former staff: ${staff.length} you can rehire`, onPress)}>
      {leg(x0 + 0.3)}{leg(x1 - 0.3)}
      <polygon points={quad(x0, x1, z0, z1)} fill="#8a6a52" />
      <polygon points={quad(x0 + 0.08, x1 - 0.08, z0 + 2, z1 - 2)} fill="#d9b382" />
      <text x={hx} y={hy + 2} fontSize={5.4 * Math.min(scale, 1.4)} fontWeight="800" fill="#5a3e2b" textAnchor="middle" transform={wallTextTransform('back', hx, hy)}>Former staff</text>
      {pinned.map((person, i) => {
        const v = x0 + 0.5 + i * 0.6
        const [cx, cy] = P(v, y, z0 + 13)
        const [px, py] = P(v, y, z0 + 20)
        return (
          <g key={person.id}>
            <polygon points={quad(v - 0.27, v + 0.27, z0 + 4, z0 + 21)} fill="#fffdf7" />
            <circle cx={cx} cy={cy + 1} r="3.4" fill={person.look.skin} />
            <path d={`M ${cx - 3.4} ${cy + 0.5} A 3.4 3.4 0 0 1 ${cx + 3.4} ${cy + 0.5} Z`} fill={person.look.hair} />
            <rect x={cx - 3.2} y={cy + 4.2} width="6.4" height="2.6" rx="1.2" fill={person.look.shirt} />
            <circle cx={px} cy={py} r="1.3" fill="#e5484d" />
          </g>
        )
      })}
      {more > 0 && (() => {
        const [mx, my] = P(x1 - 0.25, y, z0 + 9)
        return <text x={mx} y={my} fontSize="5" fontWeight="800" fill="#5a3e2b" textAnchor="middle" transform={wallTextTransform('back', mx, my)}>+{more}</text>
      })()}
    </g>
  )
}
