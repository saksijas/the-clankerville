import React, { useEffect, useRef } from 'react'
import { dialogKey, recapLines } from '../domain.js'

// Yesterday in the office: shown by itself once a day, and again from the Recap button.
// A modal dialog: focus moves in on open, stays on its one button, and returns on close.
export default function Recap({ recap, chats, onClose }) {
  const closeRef = useRef(null)
  useEffect(() => {
    const before = document.activeElement
    closeRef.current?.focus()
    return () => { if (before && typeof before.focus === 'function' && document.contains(before)) before.focus() }
  }, [])
  const onKeyDown = event => {
    const action = dialogKey(event.key)
    // Esc here closes the recap only; it must not also put the sword away.
    if (action === 'close') { event.stopPropagation(); event.nativeEvent?.stopImmediatePropagation?.(); onClose() }
    if (action === 'stay') { event.preventDefault(); closeRef.current?.focus() }
  }
  const lines = recapLines(recap, chats)
  return (
    <div className="ao-recap" role="dialog" aria-modal="true" aria-labelledby="ao-recap-title" onKeyDown={onKeyDown}>
      <div className="ao-card ao-recap-card">
        <h2 id="ao-recap-title">Yesterday in the office</h2>
        <ul className="ao-recap-list">
          {lines.map(line => <li key={line}>{line}</li>)}
        </ul>
        <button ref={closeRef} type="button" className="ao-btn" onClick={onClose}>Back to work</button>
      </div>
    </div>
  )
}
