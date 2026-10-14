import React from 'react'
import { countChips, stripSpend } from '../domain.js'

const DOT = { working: '#3fcf8e', needs_you: '#ffc53d', error: '#ff5c5c', watching: '#7fb2ff', on_break: '#9aa3b2' }

export function SwordIcon() {
  return (
    <svg viewBox="0 0 32 32" width="18" height="18" aria-hidden="true">
      <path d="M4 4 L20 20" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M15.5 24.5 L24.5 15.5" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M21 21 L27.5 27.5" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  )
}

export default function StatusStrip({ spend, counts, stale, swordOn, onSword, onRecap, floorName, floorDot, onElevator }) {
  const today = stripSpend(spend)
  return (
    <div className="ao-strip">
      {today && (
        <div className="ao-spend" title={today.title}>
          <strong>{today.text}</strong>
          {today.note && <span className="ao-sr"> ({today.note})</span>}
          <span className="ao-muted ao-spend-detail">{today.detail}</span>
        </div>
      )}
      <div className="ao-counts" aria-label="Who's doing what">
        {countChips(counts).map(([state, label, n]) => (
          <span key={state} className="ao-chip"><span className="ao-dot" style={{ background: DOT[state] }} /><b>{n}</b> {label}</span>
        ))}
        {stale && <span className="ao-chip ao-stale" role="status">Reconnecting…</span>}
      </div>
      <div className="ao-tools">
        {onElevator && (
          <button type="button" className="ao-btn ao-floorbtn" onClick={onElevator}
            aria-label={`${floorName}.${floorDot ? ' Someone needs you on another floor.' : ''} Open the elevator`}>
            {floorName}{floorDot && <span className="ao-floordot" aria-hidden="true" />}
          </button>
        )}
        {onRecap && <button type="button" className="ao-btn" onClick={onRecap}>Recap</button>}
        {onSword && (
          <button type="button" className="ao-btn ao-swordbtn" aria-pressed={swordOn} onClick={onSword}>
            <SwordIcon /> {swordOn ? 'Sword on' : 'Sword'}
          </button>
        )}
      </div>
    </div>
  )
}
