import React, { useEffect, useRef, useState } from 'react'
import { COFFEE_CAPACITY, COFFEE_POD, COMPACT_TEXT_SCALE, COOLER_EMPTY, WALL_HEIGHT, bubbleText, crDeskSpot, gossipFor, doorSpan, doorSpot, elevatorSpot, insideRoom, onFloor, toFloorPoint, plateBox, plateText, poseFor, project, roomFrame, plateTeamSize, signLayout, signText, spotFor, swordWarnings, textScaleFor, walkOffset, wallTextTransform } from '../domain.js'
import { Badge, Bubbles, CRDesk, Chair, CoffeeCorner, Desk, Elevator, FORMER_BOARD, FireCorner, FormerBoard, HelperChip, Person, PhoneCorner, Plant, Poof, Walker, Watercooler, floorQuad, headOf } from './Figures.jsx'

/* The isometric office: walls, floor, team rugs, desks, characters, and the
   overlays (chips, badges, bubbles, name tags) drawn on top in screen space. */

const LEAD_SLOT = { x: 1.4, y: 0.2 } // office.py LEAD_SLOT: a lead's desk inside its pod
const NONE = new Set()
const seatOf = desk => ({ x: desk.x + 0.6, y: desk.y + 1.05 })

// A banner painted along a wall. Its band grows with the font, so a phone's bigger text still fits.
function WallSign({ P, plane, from, to, text, fill, fontSize = 7.5 }) {
  const Q = plane === 'left' ? (v, z) => P(0, v, z) : (v, z) => P(v, 0, z)
  const mid = 47
  const half = Math.max(7, fontSize * 0.95)
  const [cx, cy] = Q((from + to) / 2, mid)
  const pts = [Q(from, mid - half), Q(to, mid - half), Q(to, mid + half), Q(from, mid + half)].map(p => p.join(',')).join(' ')
  return (
    <g>
      <polygon points={pts} fill={fill} />
      <text x={cx} y={cy + fontSize * 0.35} fontSize={fontSize} fontWeight="700" fill="#fff" textAnchor="middle" transform={wallTextTransform(plane, cx, cy)}>{text}</text>
    </g>
  )
}

// The scene's on-screen width, so its text can stay readable when it shrinks.
function useRenderedWidth(ref) {
  const [renderedWidth, setRenderedWidth] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(entries => setRenderedWidth(entries[entries.length - 1].contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return renderedWidth
}

export default function Scene({ snap, f, selectedId, onSelect, onPress, onRelease, swordOn, hold, departed = {},
  internetOff = false, internetArmed = false, onInternet, viewFloor = 1, floorDot = false, onElevator,
  arrivals = NONE, ghosts = [], walker = null, onWalk, egg = null, onEgg, onHire, former = [], onFormer }) {
  const { width, depth } = snap.room
  const frame = roomFrame(width, depth)
  const svgRef = useRef(null)
  const textScale = textScaleFor(useRenderedWidth(svgRef), frame.viewW)
  const compact = textScale > COMPACT_TEXT_SCALE
  const P = (x, y, z = 0) => project(x, y, z, frame)
  const pts = list => list.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(' ')

  const door = doorSpot(snap.room)
  const lift = elevatorSpot(snap.room)
  // One floor at a time (spec 2026-10-08 §7.1); `ghosts` are agents who just moved off this floor.
  const shown = [...onFloor(snap, viewFloor), ...ghosts.map(ghost => ({ ...ghost, ghost: true }))]
  let breakQueue = 0
  const placed = shown.map(character => {
    // Someone walking to or from the elevator doesn't take a spot in the corner.
    const onTheMove = character.ghost || arrivals.has(character.id)
    const breakIndex = character.kind === 'chat' && character.state === 'on_break' && !onTheMove ? breakQueue++ : COFFEE_CAPACITY
    const spot = spotFor(character, breakIndex)
    const where = character.state === 'on_break' && breakIndex < COFFEE_CAPACITY ? 'coffee' : 'seat'
    const pose = poseFor(character, where)
    const away = character.kind === 'chat' && (character.state === 'needs_you' || where === 'coffee')
    // Spec §5.4: a helper that finished walks out of the door carrying its green check; an agent
    // that moved to another floor walks to the elevator (spec 2026-10-08 §7.1).
    const walk = character.ghost ? walkOffset(P, spot, lift)
      : character.kind === 'helper' && character.state === 'done' ? walkOffset(P, spot, door) : null
    const arrive = arrivals.has(character.id) ? walkOffset(P, spot, lift) : null
    return { character, spot, pose, away, walk, arrive, atCorner: where === 'coffee', head: headOf(P, spot, pose) }
  })
  // How a character moves: vanishing in its turn after the sword, walking out, or riding the elevator.
  const motionOf = ({ character, walk, arrive }) => {
    const gone = departed[character.id]
    if (gone) return { className: 'ao-leaving', style: { animationDelay: `${gone.delay || 0}ms` } }
    if (walk) return { className: character.ghost ? 'ao-to-lift' : 'ao-walking', style: { '--dx': `${walk[0]}px`, '--dy': `${walk[1]}px` } }
    if (arrive) return { className: 'ao-from-lift', style: { '--dx': `${arrive[0]}px`, '--dy': `${arrive[1]}px` } }
    return {}
  }

  const things = []
  for (const p of placed) {
    const { character, spot, pose, away } = p
    const lead = character.kind === 'chat' && snap.teams.some(team => team.lead_id === character.id)
    if (!character.ghost) things.push({ d: character.desk.x + character.desk.y + 0.9, el: <Desk key={`d-${character.id}`} P={P} desk={character.desk} state={character.state} lead={lead} f={f} /> })
    if (away) {
      const seat = seatOf(character.desk)
      things.push({ d: seat.x + seat.y - 0.01, el: <Chair key={`c-${character.id}`} P={P} seat={seat} /> })
    }
    things.push({ d: spot.x + spot.y, el: <Person key={`p-${character.id}`} P={P} spot={spot} look={character.look} pose={pose} f={f} {...motionOf(p)} /> })
  }
  // Each floor's corner (pod slot 8) holds its Easter egg; floor 1's is the coffee corner with the Internet.
  // Floor 1's lobby has the CR desk, Clanker Resources (spec 2026-10-08 §7.4).
  if (viewFloor === 1 && onHire) {
    const cr = crDeskSpot(snap.room)
    things.push({ d: cr.x + cr.y + 0.9, el: <CRDesk key="cr" P={P} room={snap.room} onPress={onHire} scale={textScale} /> })
  }
  // Beside it, the Former staff board: deleted agents you can still rehire.
  if (viewFloor === 1 && onFormer) {
    things.push({ d: (FORMER_BOARD.x0 + FORMER_BOARD.x1) / 2 + FORMER_BOARD.y, el: <FormerBoard key="former" P={P} staff={former} onPress={onFormer} scale={textScale} /> })
  }
  const eggKind = (snap.floors || []).find(fl => fl.floor === viewFloor)?.egg || (viewFloor === 1 ? 'internet' : null)
  const cornerDepth = COFFEE_POD.x + COFFEE_POD.y + 3.5
  if (eggKind === 'internet') things.push({ d: cornerDepth, el: <CoffeeCorner key="coffee" P={P} origin={COFFEE_POD} f={f} off={internetOff} armed={internetArmed} onPress={onInternet} /> })
  if (eggKind === 'watercooler') things.push({ d: cornerDepth, el: <Watercooler key="egg" P={P} origin={COFFEE_POD} active={Boolean(egg?.active)} onPress={onEgg} /> })
  if (eggKind === 'phone') things.push({ d: cornerDepth, el: <PhoneCorner key="egg" P={P} origin={COFFEE_POD} ringing={Boolean(egg?.active && egg.ringing)} onPress={onEgg} /> })
  if (eggKind === 'fire') things.push({ d: cornerDepth, el: <FireCorner key="egg" P={P} origin={COFFEE_POD} active={Boolean(egg?.active)} onPress={onEgg} /> })
  if (walker) things.push({ d: walker[0] + walker[1], el: <Walker key="you" P={P} spot={{ x: walker[0], y: walker[1] }} f={f} /> })
  things.push({ d: width - 0.6 + 0.3 + 0.3, el: <Plant key="plant-back" P={P} x={width - 0.7} y={0.2} /> })
  things.push({ d: width - 0.7 + depth - 0.7 + 0.3, el: <Plant key="plant-front" P={P} x={width - 0.7} y={depth - 0.7} /> })
  things.sort((a, b) => a.d - b.d)

  const floor = []
  for (let i = 0; i < width; i++) for (let j = 0; j < depth; j++) {
    const lobby = j >= depth - 2
    floor.push(<polygon key={`f${i}-${j}`} points={floorQuad(P, i, j, 1, 1)} fill={lobby ? ((i + j) % 2 ? '#f4f0fa' : '#ede8f6') : (i + j) % 2 ? '#ece7f6' : '#e3ddf1'} />)
  }
  const byId = Object.fromEntries(snap.characters.map(c => [c.id, c]))
  const teamSize = Object.fromEntries(snap.teams.map(team => [
    team.lead_id, plateTeamSize(team.member_ids.map(id => byId[id]).filter(Boolean), byId[team.lead_id]?.overflow || 0),
  ]))
  const selected = placed.find(p => p.character.id === selectedId && !p.walk) // no ring at a desk someone walked away from
  // While the watercooler is on, whoever hangs out in the corner gossips (spec 2026-10-08 §7.3).
  const gossiping = eggKind === 'watercooler' && egg?.active
  let gossipIndex = 0
  const bubbles = placed
    .filter(p => !departed[p.character.id] && !p.walk && !p.arrive) // no chatter while riding the elevator
    .map(p => ({ p, text: gossiping && p.atCorner ? gossipFor(gossipIndex++) : bubbleText(p.character) }))
    .filter(({ text }) => text)
    .map(({ p, text }) => ({ id: p.character.id, state: p.character.state, text, ax: p.head[0], ay: p.head[1] }))
  if (gossiping && !placed.some(p => p.atCorner)) {
    const [ax, ay] = P(COFFEE_POD.x + 3.0, COFFEE_POD.y + 0.8, 50)
    bubbles.push({ id: 'cooler', state: 'on_break', text: COOLER_EMPTY, ax, ay })
  }
  if (eggKind === 'phone' && egg?.active && egg.text) {
    const [ax, ay] = P(COFFEE_POD.x + 3.05, COFFEE_POD.y + 0.8, 24)
    bubbles.push({ id: 'phone', state: 'on_break', text: egg.text, ax, ay })
  }
  // What a bubble must not cover: every other character's head and upper body,
  // plus a helper's status chip to the right of its head.
  // A helper walking out of the door is on its way out: nothing to avoid or tap.
  const present = p => !departed[p.character.id] && !p.walk
  const figures = placed
    .filter(present)
    .map(({ character, head: [hx, hy] }) => ({ id: character.id, x0: hx - 12, x1: hx + (character.kind === 'helper' ? 27 : 10), y0: hy - 13, y1: hy + 16 }))
  // Name tags too: a bubble never covers someone else's name.
  const plates = placed
    .filter(p => present(p) && plateText(p.character))
    .map(({ character, spot }) => {
      const [sx, sy] = P(spot.x, spot.y)
      return plateBox(character.id, sx, sy, plateText(character, teamSize[character.id] || 0, compact), textScale)
    })
  const signLabel = signText(snap.office)
  const sign = signLayout(signLabel, textScale, depth)

  return (
    <svg ref={svgRef} viewBox={`0 0 ${frame.viewW} ${frame.viewH}`} className="ao-svg" role="group" aria-label="Office floor. Tap the floor to walk there."
      onClick={event => {
        // Tapping the floor walks you there (spec 2026-10-08 §7.2); taps on people and things stop before this.
        const svg = svgRef.current
        if (!onWalk || swordOn || !svg?.getScreenCTM) return
        const point = svg.createSVGPoint()
        point.x = event.clientX
        point.y = event.clientY
        const local = point.matrixTransform(svg.getScreenCTM().inverse())
        onWalk(insideRoom(toFloorPoint(local.x, local.y, frame), snap.room))
      }}>
      <polygon points={pts([P(0, 0), P(width, 0), P(width, 0, WALL_HEIGHT), P(0, 0, WALL_HEIGHT)])} fill="#d3cce8" />
      <polygon points={pts([P(0, 0), P(0, depth), P(0, depth, WALL_HEIGHT), P(0, 0, WALL_HEIGHT)])} fill="#c2bade" />
      {[[4.8, 6.6], [7.2, 9.0]].map(([a, b]) => <polygon key={a} points={pts([P(a, 0, 26), P(b, 0, 26), P(b, 0, 58), P(a, 0, 58)])} fill="#bfe6fa" stroke="#fff" strokeWidth="2" />)}
      <WallSign P={P} plane="left" from={sign.from} to={sign.to} text={signLabel} fill="#8f86b0" fontSize={sign.fontSize} />
      {(() => {
        const [d0, d1] = doorSpan(snap.room)
        return <>
          <polygon points={pts([P(0, d0), P(0, d1), P(0, d1, 46), P(0, d0, 46)])} fill="#8a6a52" />
          <circle cx={P(0, d0 + 0.18, 22)[0]} cy={P(0, d0 + 0.18, 22)[1]} r="1.8" fill="#e0b04b" />
        </>
      })()}
      <Elevator P={P} room={snap.room} floor={viewFloor} dot={floorDot} onPress={onElevator} />
      {floor}
      {snap.teams.filter(team => byId[team.lead_id]?.floor === viewFloor || (!byId[team.lead_id]?.floor && viewFloor === 1)).map(team => {
        const lead = byId[team.lead_id]
        const origin = { x: lead.desk.x - LEAD_SLOT.x, y: lead.desk.y - LEAD_SLOT.y }
        return <polygon key={`rug-${team.lead_id}`} points={floorQuad(P, origin.x - 0.1, origin.y - 0.1, 4, 3)} fill="#b9aaf2" opacity=".55" />
      })}
      {selected && (() => {
        const [sx, sy] = P(selected.spot.x, selected.spot.y)
        const danger = swordOn
        return (
          <g>
            <ellipse cx={sx} cy={sy} rx="18" ry="9" fill={danger ? 'rgba(229,72,77,.18)' : 'rgba(255,255,255,.55)'} stroke="#fff" strokeWidth="5" />
            <ellipse cx={sx} cy={sy} rx="18" ry="9" fill="none" stroke={danger ? '#e5484d' : '#6d5dfc'} strokeWidth="2.6" />
          </g>
        )
      })()}
      {things.map(t => t.el)}
      {placed.filter(p => !departed[p.character.id] && p.character.kind === 'helper').map(p => (
        <g key={`chip-${p.character.id}`} {...motionOf(p)}><HelperChip head={p.head} state={p.character.state} f={f} /></g>
      ))}
      {placed.filter(p => departed[p.character.id]).map(p => {
        const [sx, sy] = P(p.spot.x, p.spot.y)
        return <Poof key={`poof-${p.character.id}`} x={sx} y={sy - 22} delay={departed[p.character.id].delay || 0} />
      })}
      {placed.filter(p => !departed[p.character.id] && p.character.kind === 'chat' && (p.character.state === 'needs_you' || p.character.state === 'error')).map(p => <Badge key={`badge-${p.character.id}`} head={p.head} state={p.character.state} scale={textScale} />)}
      <Bubbles items={bubbles} width={frame.viewW} obstacles={[...figures, ...plates]} scale={textScale} />
      <g fontSize={7.5 * textScale} fontWeight="600" textAnchor="middle">
        {placed.filter(p => !departed[p.character.id] && plateText(p.character)).map(({ character, spot }) => {
          const [sx, sy] = P(spot.x, spot.y)
          const text = plateText(character, teamSize[character.id] || 0, compact)
          return <text key={`n-${character.id}`} x={sx} y={sy + 5 + 8 * textScale} fill="#2a2340" stroke="#fff" strokeWidth={2.4 * textScale} paintOrder="stroke" strokeLinejoin="round">{text}</text>
        })}
        {walker && (() => {
          const [sx, sy] = P(walker[0], walker[1])
          return <text x={sx} y={sy + 5 + 8 * textScale} fill="#6d5dfc" stroke="#fff" strokeWidth={2.4 * textScale} paintOrder="stroke" strokeLinejoin="round">You</text>
        })()}
      </g>
      {hold && (() => {
        const target = placed.find(p => p.character.id === hold.id)
        if (!target) return null
        const [sx, sy] = P(target.spot.x, target.spot.y)
        return <ellipse key={`hold-${hold.key}`} cx={sx} cy={sy} rx="21" ry="10.5" pathLength="100" style={{ '--ao-hold': `${hold.ms}ms` }} className={`ao-ring${swordWarnings(target.character).length ? ' ao-ring-warn' : ''}`} />
      })()}
      {placed.filter(present).map(({ character, spot }) => {
        const [sx, sy] = P(spot.x, spot.y)
        const label = `${character.kind === 'helper' ? character.name : character.short}: ${character.state.replace('_', ' ')}`
        return (
          <rect
            key={`hit-${character.id}`} x={sx - 14} y={sy - 58} width="28" height="64" fill="rgba(0,0,0,0)"
            role="button" tabIndex={0} aria-label={label} className="ao-hit"
            onClick={event => event.stopPropagation()}
            onPointerDown={event => { if (swordOn && onPress) { event.preventDefault(); onPress(character) } else onSelect(character.id) }}
            onPointerUp={() => onRelease?.()}
            onPointerLeave={() => onRelease?.()}
            onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(character.id) } }}
          />
        )
      })}
    </svg>
  )
}
