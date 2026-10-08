import React, { useEffect, useRef, useState } from 'react'
import { answerStatus, canSendAnswers, createSendGuard, fullChatText, isLongLatest, problemText, replyStatus, splitRecommended } from '../domain.js'

/* Quick reply (spec 2026-09-29, layout A): a chat's latest words, the question
   it waits on, and a reply box, inside its character card. Nothing is sent
   without a tap. One message id per draft or answer attempt, kept on "Try
   again", so Möbius never receives the same message twice.
   Layout (2026-10-07): two columns on a wide card, what it last said beside
   what it's asking; one column on a phone. */

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" stroke="currentColor" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// The reply box grows with its text, up to about five lines.
function grow(event) {
  const box = event.target
  box.style.height = 'auto'
  box.style.height = `${Math.min(box.scrollHeight, 140)}px`
}

const newCid = () => (globalThis.crypto?.randomUUID
  ? globalThis.crypto.randomUUID()
  : `cid-${Date.now()}-${Math.random().toString(36).slice(2)}`)

export default function QuickReply({ character, api, demo, refreshKey }) {
  const chatId = character.chat_id
  const [view, setView] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [draft, setDraft] = useState('')
  const [picks, setPicks] = useState({})
  const [status, setStatus] = useState(null)
  const [sending, setSending] = useState(false)
  const [reloads, setReloads] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const cidRef = useRef(newCid())
  const guardRef = useRef(createSendGuard())

  useEffect(() => {
    setView(null)
    setLoadError(null)
    setDraft('')
    setPicks({})
    setStatus(null)
    setExpanded(false)
    cidRef.current = newCid()
  }, [chatId])

  // Read when the card opens, when the character's state changes, and after a send.
  useEffect(() => {
    if (demo) return undefined
    let alive = true
    api.thread(chatId).then(body => {
      if (!alive) return
      if (body?.ok) {
        setView(body)
        setLoadError(null)
      } else {
        setLoadError(body?.error || { code: 'offline' })
      }
    })
    return () => { alive = false }
  }, [api, chatId, refreshKey, reloads, demo])

  if (demo) {
    return <div className="ao-qr"><p className="ao-muted">Quick reply works on your real chats.</p></div>
  }

  const question = view?.question || null
  const single = Boolean(question && question.questions.length === 1)

  const finish = (result, okText) => {
    guardRef.current.end()
    setSending(false)
    if (result?.ok) {
      setStatus({ ok: true, text: okText })
      setDraft('')
      setPicks({})
      cidRef.current = newCid()
      setReloads(n => n + 1)
      return
    }
    setStatus({ ok: false, text: problemText(result?.error) })
    if (result?.error?.code === 'question_changed') {
      setPicks({})
      setReloads(n => n + 1)
    }
  }

  const sendAnswer = async (nextPicks, typed) => {
    if (!guardRef.current.begin()) return
    setSending(true)
    setStatus(null)
    const result = await api.answer(chatId, question.question_id, nextPicks, typed || null, cidRef.current)
    finish(result, answerStatus(result))
  }

  const pick = (questionId, optionId) => {
    if (sending) return
    const next = { ...picks, [questionId]: optionId }
    setPicks(next)
    if (single) sendAnswer(next, null) // one question: a tap is the answer
  }

  const sendDraft = async () => {
    const text = draft.trim()
    if (!text) return
    if (question) {
      if (single) await sendAnswer({}, text)
      return
    }
    if (!guardRef.current.begin()) return
    setSending(true)
    setStatus(null)
    const result = await api.reply(chatId, text, cidRef.current)
    finish(result, replyStatus(result))
  }

  if (!view) {
    return (
      <div className="ao-qr" aria-live="polite">
        <p className="ao-muted">{loadError ? problemText(loadError) : 'Reading the chat…'}</p>
      </div>
    )
  }

  const showBox = !view.full_chat_only && (!question || single)
  const latest = view.latest ? view.latest.text : ''
  const long = isLongLatest(latest)
  return (
    <div className="ao-qr">
      <div className="ao-qr-cols">
        <div className="ao-qr-said">
          <div className="ao-qr-label">What it last said</div>
          {/* The clamp sits on an inner block: on the padded bubble itself, part of line 7 peeks out. */}
          <div className="ao-qr-bubble"><div className={long && !expanded ? 'ao-clamped' : undefined}>{latest || 'No reply yet.'}</div></div>
          {long && (
            <button type="button" className="ao-linkbtn" aria-expanded={expanded} onClick={() => setExpanded(open => !open)}>
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
        <div className="ao-qr-ask">
          {view.full_chat_only && <div className="ao-warn"><p>{fullChatText(view.full_chat_only)}</p></div>}
          {question && (
            <div className="ao-qr-questions">
              <div className="ao-qr-label">It's asking you</div>
              {question.questions.map(q => (
                <fieldset key={q.id} className="ao-qr-q" disabled={sending}>
                  <legend>{q.question}</legend>
                  <div className="ao-qr-opts">
                    {q.options.map(option => {
                      const { text, recommended } = splitRecommended(option.label)
                      return (
                        <button key={option.id} type="button" className={`ao-qr-opt${recommended ? ' ao-qr-rec' : ''}`}
                          aria-pressed={picks[q.id] === option.id} onClick={() => pick(q.id, option.id)}>
                          <b>{text}{recommended && <em className="ao-qr-badge">Recommended</em>}</b>
                          {option.description ? <span>{option.description}</span> : null}
                        </button>
                      )
                    })}
                  </div>
                </fieldset>
              ))}
              {!single && (
                <button type="button" className="ao-btn ao-qr-primary" disabled={sending || !canSendAnswers(question, picks, '')}
                  onClick={() => sendAnswer(picks, null)}>Send answers</button>
              )}
            </div>
          )}
          {!question && !view.full_chat_only && <div className="ao-qr-label">Send a message</div>}
          {showBox && (
            <div className="ao-composer">
              <textarea value={draft} rows={1} disabled={sending}
                onChange={event => { setDraft(event.target.value); grow(event) }}
                placeholder={question ? 'Or type your own answer…' : `Message ${character.short}…`}
                aria-label={question ? 'Your own answer' : `Message ${character.name}`} />
              <button type="button" className="ao-send" disabled={sending || !draft.trim()} onClick={sendDraft}
                aria-label={question ? 'Send your answer' : 'Send'}><SendIcon /></button>
            </div>
          )}
          <div aria-live="polite">
            {status && <p className={status.ok ? 'ao-qr-done' : 'ao-qr-problem'}>{status.text}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
