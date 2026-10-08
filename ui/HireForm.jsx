import React, { useEffect, useRef, useState } from 'react'
import { HIRE_TEXT_MAX, HIRE_TITLE_MAX, dialogKey, hireProblem } from '../domain.js'

// Clanker Resources (spec 2026-10-08 §7.4): name the new hire and say what they start on.
// Hire starts a real chat; Esc or Cancel closes the form.
export default function HireForm({ busy, onHire, onClose }) {
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const nameRef = useRef(null)
  useEffect(() => {
    const before = document.activeElement
    nameRef.current?.focus()
    return () => { if (before && typeof before.focus === 'function' && document.contains(before)) before.focus() }
  }, [])
  const problem = hireProblem(name, text)
  const close = () => { if (!busy) onClose() } // mid-hire, closing would throw away what was typed
  const onKeyDown = event => {
    if (dialogKey(event.key) === 'close') { event.stopPropagation(); event.nativeEvent?.stopImmediatePropagation?.(); close() }
  }
  return (
    <div className="ao-recap" role="dialog" aria-modal="true" aria-labelledby="ao-hire-title" onKeyDown={onKeyDown} onClick={close}>
      <form className="ao-card ao-hire-card" onClick={event => event.stopPropagation()}
        onSubmit={event => { event.preventDefault(); if (!problem && !busy) onHire(name.trim(), text.trim()) }}>
        <h2 id="ao-hire-title">CR · Clanker Resources</h2>
        <p className="ao-muted">Hire a new clanker: give them a name and what to start on.</p>
        <label className="ao-hire-field">Name
          <input ref={nameRef} value={name} maxLength={HIRE_TITLE_MAX} onChange={event => setName(event.target.value)} placeholder="Fix the login page" />
        </label>
        <label className="ao-hire-field">First message
          <textarea value={text} maxLength={HIRE_TEXT_MAX} rows={5} onChange={event => setText(event.target.value)} placeholder="What should they work on?" />
        </label>
        {problem && (name || text) && <p className="ao-hire-problem" role="status">{problem}</p>}
        <div className="ao-hire-actions">
          <button type="button" className="ao-btn" onClick={close} disabled={busy}>Cancel</button>
          <button type="submit" className="ao-btn ao-primary" disabled={Boolean(problem) || busy}>{busy ? 'Hiring…' : 'Hire'}</button>
        </div>
      </form>
    </div>
  )
}
