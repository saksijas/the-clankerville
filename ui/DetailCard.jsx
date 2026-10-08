import React from 'react'
import { plateTeamSize, swordNote, swordWarnings } from '../domain.js'
import QuickReply from './QuickReply.jsx'
import { SwordIcon } from './StatusStrip.jsx'

/* The selected character's card, below the office at full width: a header row
   (who it is and how it's doing), what it last said and what it's asking, then
   the actions. Quick reply (spec 2026-09-29) lives inside it. */

const DOT = {
  working: '#3fcf8e', needs_you: '#ffc53d', error: '#ff5c5c', watching: '#7fb2ff', on_break: '#9aa3b2',
  busy: '#3fcf8e', on_hold: '#9aa3b2', done: '#3fcf8e', failed: '#ff5c5c',
}
const LABEL = {
  working: 'Working', needs_you: 'Needs your answer', error: 'Hit an error', watching: 'Waiting on a timer',
  on_break: 'On a break', busy: 'Busy', on_hold: 'On hold', done: 'Done, heading out', failed: 'Failed',
}

export default function DetailCard({
  character, team, overflow, leadName, onOpenChat, onHoldStart, onHoldCancel, holding, api, demo, openLabel,
}) {
  if (!character) {
    return <div className="ao-hintbar" role="note">Tap someone in the office to see what they're doing and reply.</div>
  }
  const isHelper = character.kind === 'helper'
  const helpers = plateTeamSize(team, overflow) // same count as the lead's name tag
  const role = isHelper
    ? `Helper on the ${leadName} team`
    : helpers > 0 ? `Team lead · ${helpers} helper${helpers === 1 ? '' : 's'}` : 'Solo chat'
  const canStrike = character.dismissable
  const warnings = canStrike ? swordWarnings(character) : []
  const share = Math.max(0, Math.min(1, character.xp_progress || 0))
  return (
    <section className="ao-card ao-detail" aria-label={character.name}>
      <header className="ao-dhead">
        <span className="ao-avatar" aria-hidden="true"
          style={{ background: character.look?.shirt || '#6d5dfc', borderColor: character.look?.hair || '#2a2340' }} />
        <div className="ao-dtitle">
          <div className="ao-role">{role}</div>
          <h2>{character.name}</h2>
        </div>
        <span className={`ao-pill${character.state === 'needs_you' ? ' ao-pill-ask' : ''}`}>
          <span className="ao-dot" style={{ background: DOT[character.state] }} />{LABEL[character.state] || character.state}
        </span>
        {!isHelper && (
          <span className="ao-dlevel" title={`${Math.round(share * 100)}% to Lv ${character.level + 1}`}>
            <b>Lv {character.level}</b>
            <span className="ao-xp" aria-hidden="true"><span style={{ width: `${share * 100}%` }} /></span>
          </span>
        )}
      </header>
      {character.step && <p className="ao-now"><span className="ao-muted">Right now · </span>{character.step}</p>}
      {team.length > 0 && (
        <div className="ao-team">
          <span className="ao-muted">Team</span>
          {team.map(helper => (
            <span key={helper.id} className="ao-pill ao-pill-small"><span className="ao-dot" style={{ background: DOT[helper.state] }} />{helper.name}</span>
          ))}
          {overflow > 0 && <span className="ao-muted">+{overflow} more</span>}
        </div>
      )}
      {/* One QuickReply per chat: a send that finishes after a switch can't touch another chat's card. */}
      {!isHelper && <QuickReply key={character.chat_id} character={character} api={api} demo={demo} refreshKey={character.state} />}
      {warnings.length > 0 && (
        <div className="ao-warn">
          {warnings.map(warning => <p key={warning}>{warning}</p>)}
        </div>
      )}
      <footer className="ao-actions">
        <button type="button" className="ao-btn" onClick={() => onOpenChat(character.chat_id)}>{isHelper ? "Open the lead's chat" : openLabel}</button>
        {canStrike && (
          <button
            type="button"
            className="ao-btn ao-danger"
            onPointerDown={event => { event.preventDefault(); onHoldStart(character) }}
            onPointerUp={onHoldCancel}
            onPointerLeave={onHoldCancel}
            onKeyDown={event => { if ((event.key === ' ' || event.key === 'Enter') && !event.repeat) { event.preventDefault(); onHoldStart(character) } }}
            onKeyUp={event => { if (event.key === ' ' || event.key === 'Enter') onHoldCancel() }}
          >
            {holding && <span key={holding.key} className="ao-holdfill" style={{ animationDuration: `${holding.ms}ms` }} />}
            <SwordIcon /> {isHelper ? 'Hold to dismiss' : 'Hold to delete chat'}
          </button>
        )}
        {canStrike && <p className="ao-muted ao-small-note">{swordNote(character)}</p>}
      </footer>
    </section>
  )
}
