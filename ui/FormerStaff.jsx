import React, { useEffect, useRef } from 'react'
import { daysLeftText, dialogKey } from '../domain.js'

// Former staff (owner's idea, 2026-10-08): deleted agents Möbius can still recover, soonest to go
// first, each with its days left and a Rehire button. Esc or Close shuts it.
export default function FormerStaff({ staff, loaded, busyId, onRehire, onClose }) {
  const closeRef = useRef(null)
  useEffect(() => {
    const before = document.activeElement
    closeRef.current?.focus()
    return () => { if (before && typeof before.focus === 'function' && document.contains(before)) before.focus() }
  }, [])
  const onKeyDown = event => {
    if (dialogKey(event.key) === 'close') { event.stopPropagation(); event.nativeEvent?.stopImmediatePropagation?.(); onClose() }
  }
  return (
    <div className="ao-recap" role="dialog" aria-modal="true" aria-labelledby="ao-former-title" onKeyDown={onKeyDown} onClick={onClose}>
      <div className="ao-card ao-former-card" onClick={event => event.stopPropagation()}>
        <h2 id="ao-former-title">Former staff</h2>
        <p className="ao-muted">Agents you deleted can be rehired for 7 days. After that, Möbius lets them go for good.</p>
        {!loaded && <p className="ao-muted">Checking the files…</p>}
        {loaded && staff.length === 0 && <p className="ao-muted">Nobody here. Everyone still works for you.</p>}
        {staff.length > 0 && (
          <ul className="ao-former-list">
            {staff.map(person => (
              <li key={person.id}>
                <span className="ao-dot" style={{ background: person.look.shirt, borderColor: person.look.hair }} aria-hidden="true" />
                <span className="ao-former-name">{person.name}</span>
                <span className={`ao-daysleft${person.days_left <= 1 ? ' ao-lastday' : ''}`}>{daysLeftText(person.days_left)}</span>
                <button type="button" className="ao-btn" disabled={Boolean(busyId)} onClick={() => onRehire(person)}
                  aria-label={`Rehire ${person.name}, ${daysLeftText(person.days_left)}`}>
                  {busyId === person.id ? 'Rehiring…' : 'Rehire'}
                </button>
              </li>
            ))}
          </ul>
        )}
        <button ref={closeRef} type="button" className="ao-btn" onClick={onClose}>Close</button>
      </div>
    </div>
  )
}
