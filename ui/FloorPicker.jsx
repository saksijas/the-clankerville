import React, { useEffect, useRef } from 'react'
import { dialogKey, floorSummary } from '../domain.js'

// The elevator's floor list (spec 2026-10-08 §7.1): each floor with who's there, a dot where
// someone needs you, and "You're here" on the current one. Esc closes it.
export default function FloorPicker({ floors, current, badges, onPick, onClose }) {
  const firstRef = useRef(null)
  useEffect(() => {
    const before = document.activeElement
    firstRef.current?.focus()
    return () => { if (before && typeof before.focus === 'function' && document.contains(before)) before.focus() }
  }, [])
  const onKeyDown = event => {
    if (dialogKey(event.key) === 'close') { event.stopPropagation(); event.nativeEvent?.stopImmediatePropagation?.(); onClose() }
  }
  return (
    <div className="ao-recap" role="dialog" aria-modal="true" aria-labelledby="ao-lift-title" onKeyDown={onKeyDown} onClick={onClose}>
      <div className="ao-card ao-lift-card" onClick={event => event.stopPropagation()}>
        <h2 id="ao-lift-title">Elevator</h2>
        <div className="ao-lift-list">
          {floors.map(({ floor, counts }, index) => (
            <button key={floor} ref={index === 0 ? firstRef : undefined} type="button" className="ao-lift-floor"
              aria-current={floor === current ? 'true' : undefined} onClick={() => onPick(floor)}>
              <b>Floor {floor}{badges.has(floor) && <span className="ao-floordot" aria-hidden="true" />}</b>
              <span>{floor === current ? "You're here · " : ''}{floorSummary(counts)}</span>
            </button>
          ))}
        </div>
        <button type="button" className="ao-btn" onClick={onClose}>Stay here</button>
      </div>
    </div>
  )
}
