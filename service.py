"""Agent Office back room: the only part of the app that acts for the owner.

Möbius runs this file once per request. The request arrives on stdin as one
JSON envelope (``{"method", "path", "query", "body", ...}``); the reply is one
JSON object (``{"status", "body"}``) on stdout. Handlers are registered in
``ROUTES`` and receive the feed and clock explicitly so tests can inject fakes.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import office
import progress
import quick_reply
import store
from feed import FeedError, OwnerFeed

ROUTES = {}
# One budget for a whole snapshot, Möbius calls included (spec §8: 8 s ceiling,
# with room left for process start and the reply).
SNAPSHOT_BUDGET_SECONDS = 7.0
# Möbius ends a service request at 15 s. Progress reads history for at most
# 8 s (the rest is read on the next check) and never waits on Möbius past 12 s.
HISTORY_BUDGET_SECONDS = 8.0
PROGRESS_BUDGET_SECONDS = 12.0
# A strike needs longer calls: Möbius's stop allows 2 s to stop gracefully and
# up to 5 s more to force it, and a delete waits for helpers to cancel.
SWORD_CALL_SECONDS = 9.0
SWORD_BUDGET_SECONDS = 13.0
SWORD_LOG_KEEP = timedelta(days=30)


def route(method, path):
    def register(handler):
        ROUTES[(method, path)] = handler
        return handler
    return register


@route("GET", "ping")
def _ping(request, feed, now):
    return {"ok": True}


def _failure(exc):
    return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}


@route("GET", "snapshot")
def _snapshot(request, feed, now):
    deadline = time.monotonic() + SNAPSHOT_BUDGET_SECONDS
    feed = feed or OwnerFeed(deadline=deadline, clock=time.monotonic)
    now = now or datetime.now(UTC)
    try:
        chats = office.select_chats(feed.list_chats(), now)
        delegations = feed.list_delegations()
        details = {}
        for chat in chats:
            # Working chats need their step; a working or asking chat may hold queued messages.
            if office.chat_state(chat) not in ("working", "needs_you") or time.monotonic() >= deadline:
                continue
            try:
                details[chat["id"]] = feed.chat_detail(chat["id"])
            except FeedError as exc:
                # A vanished chat or a slow step lookup shows "Working"; key
                # trouble still reaches the office so it can explain it.
                if exc.code not in ("not_found", "mobius_unavailable"):
                    raise
    except FeedError as exc:
        return _failure(exc)
    chat_ids = [chat["id"] for chat in chats]
    teams = office.build_teams(delegations, set(chat_ids), now)
    previous = store.read_json("desks.json", {})
    pods = office.assign_helper_desks(teams, office.assign_pods(chat_ids, previous, now))
    if pods != previous:
        store.write_json("desks.json", pods)
    # Read-only here: only the progress route writes progress.json.
    office_progress = progress.office_view(store.read_json("progress.json", {}))
    snapshot = office.build_snapshot(chats, details, teams, pods, office_progress, now)
    snapshot["internet"] = internet_view()
    return snapshot


@route("GET", "progress")
def _progress(request, feed, now):
    started = time.monotonic()
    feed = feed or OwnerFeed(deadline=started + PROGRESS_BUDGET_SECONDS, clock=time.monotonic)
    now = now or datetime.now(UTC)
    query = request.get("query") or {}
    raw = (query.get("working_now") or ["0"])[0]
    working_now = max(0, int(raw)) if str(raw).isdigit() else 0
    zone = (query.get("tz") or [None])[0]
    tz = zone if progress.owner_zone(zone) else None
    try:
        return {"ok": True, **progress.catch_up(feed, now, working_now=working_now, tz=tz,
                                                 history_seconds=HISTORY_BUDGET_SECONDS, clock=time.monotonic)}
    except FeedError as exc:
        return _failure(exc)


def record_swing(kind, target, result, now):
    """Append one sword swing to the office's own audit log, keeping 30 days."""
    kept = [entry for entry in store.read_json("sword-log.json", [])
            if (office.parse_time(entry.get("at")) or now) >= now - SWORD_LOG_KEEP]
    outcome = {key: result[key] for key in ("ok", "deleted", "dismissed", "stopped") if key in result}
    if not result.get("ok"):
        outcome["code"] = (result.get("error") or {}).get("code")
    kept.append({"at": now.isoformat(), "kind": kind, "target": target, "result": outcome})
    store.write_json("sword-log.json", kept)


def _not_confirmed():
    return {"ok": False, "error": {"code": "stop_failed", "message": "Möbius didn't confirm the stop."}}


def _unconfirmed(exc):
    # No answer in time is not a refusal: Möbius may still finish the stop or delete.
    if exc.code == "mobius_unavailable":
        return {"ok": False, "error": {"code": "unconfirmed", "message": "Möbius didn't answer in time; it may still finish."}}
    return _failure(exc)


def _strike_chat(feed, chat_id):
    # Only the owner's own chats, as with quick reply: never one an app made.
    try:
        made_by_app = feed.chat_detail(chat_id).get("created_by_app_id") is not None
    except FeedError as exc:
        return _failure(exc)
    if made_by_app:
        return {"ok": False, "error": {"code": "not_owner", "message": "The sword only strikes your own chats."}}
    # Stop first: Möbius's owner Stop clears the owner's queued messages and
    # cancels the chat's helpers, and says how many. The delete then moves the
    # chat to Möbius's 7-day trash and sends the owner a Recover notification.
    try:
        reply = feed.stop_chat(chat_id) or {}
    except FeedError as exc:
        return _unconfirmed(exc)
    if reply.get("stopped") is not True:
        return _not_confirmed()
    try:
        feed.delete_chat(chat_id)
    except FeedError as exc:
        return {**_unconfirmed(exc), "stopped": True}
    return {"ok": True, "deleted": True,
            "cancelled_helpers": len(reply.get("cancelled_delegations") or []),
            "discarded_messages": len(reply.get("cleared_pending_cids") or [])}


def _dismiss_helper(feed, delegation_id):
    # A helper's own chat is hidden and holds the result its lead reads, so a
    # struck helper is only cancelled; its lead keeps working.
    try:
        reply = feed.cancel_helper(delegation_id) or {}
    except FeedError as exc:
        return _unconfirmed(exc)
    if reply.get("status") == "cancelled" or reply.get("cancelled_at"):
        return {"ok": True, "dismissed": True}
    return _not_confirmed()


@route("POST", "sword")
def _sword(request, feed, now):
    """A struck chat is stopped, then deleted; a struck helper is dismissed."""
    feed = feed or OwnerFeed(timeout=SWORD_CALL_SECONDS, deadline=time.monotonic() + SWORD_BUDGET_SECONDS,
                             clock=time.monotonic)
    now = now or datetime.now(UTC)
    body = request.get("body") if isinstance(request.get("body"), dict) else {}
    kind, target = body.get("kind"), body.get("id")
    if kind not in ("chat", "helper") or not isinstance(target, str) or not target:
        return {"ok": False, "error": {"code": "bad_request", "message": "Say who the sword is for: a chat or a helper, by id."}}
    result = _strike_chat(feed, target) if kind == "chat" else _dismiss_helper(feed, target)
    record_swing(kind, target, result, now)
    return result


# --- The Internet box: the coffee corner's black box with the red light ---------
# An IT Crowd joke (owner's idea, Oct 7). Turning it off stops every owner chat that
# is working right now and remembers them; turning it on tells each of them to
# continue. The screen asks for a second click before turning it off.

INTERNET_CALL_SECONDS = 9.0  # one stop: Möbius allows 2 s to stop gracefully, up to 5 s more to force
INTERNET_BUDGET_SECONDS = 13.0  # Möbius ends a service request at 15 s; all stops run at once
INTERNET_LOG_KEEP = timedelta(days=30)
CONTINUE_TEXT = "🌐 The Internet is back on. Please continue where you left off."


def _internet_state():
    state = store.read_json("internet.json", {})
    state = state if isinstance(state, dict) else {}
    paused = state.get("paused") if isinstance(state.get("paused"), list) else []
    titles = state.get("titles") if isinstance(state.get("titles"), dict) else {}
    return {"off": state.get("off") is True, "since": state.get("since"),
            "paused": [chat_id for chat_id in paused if _is_id(chat_id)],
            "titles": {k: v for k, v in titles.items() if _is_id(k) and isinstance(v, str)}}


def internet_view():
    """What the office shows: is the Internet off, and how many agents it paused."""
    state = _internet_state()
    return {"off": state["off"], "paused": len(state["paused"])}


def record_switch(on, count, now):
    """Log each switch (when, which way, how many chats) — never any text — keeping 30 days."""
    kept = [entry for entry in store.read_json("internet-log.json", [])
            if (office.parse_time(entry.get("at")) or now) >= now - INTERNET_LOG_KEEP]
    kept.append({"at": now.isoformat(), "on": on, "count": count})
    store.write_json("internet-log.json", kept)


def _each(work, items):
    """Run `work` on every item at once (stops can take seconds each), in order."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
        return list(pool.map(work, items))


def _pause_working_chats(feed):
    """Stop every owner chat that is working. Returns (confirmed ids, unconfirmed ids, titles).

    Only the office's "working" state counts: a chat waiting on the owner's answer still reports
    `running`, and stopping it would withdraw the question; timers and errors are left alone too.
    """
    rows = [c for c in feed.list_chats()
            if c.get("created_by_app_id") is None and _is_id(c.get("id")) and office.chat_state(c) == "working"]
    working = [c["id"] for c in rows]
    titles = {c["id"]: c["title"] for c in rows if isinstance(c.get("title"), str) and c["title"]}

    def stop(chat_id):
        try:
            return (feed.stop_chat(chat_id) or {}).get("stopped") is True
        except FeedError:
            return False  # not confirmed in time: it may still stop, so it still hears "continue"

    results = _each(stop, working)
    return ([c for c, ok in zip(working, results) if ok], [c for c, ok in zip(working, results) if not ok], titles)


def _tell_to_continue(feed, chat_ids):
    def tell(chat_id):
        try:
            feed.send_message(chat_id, {"content": CONTINUE_TEXT, "cid": f"internet-{uuid4().hex}"})
            return True
        except FeedError:
            return False

    return _each(tell, chat_ids)


@route("POST", "internet")
def _internet(request, feed, now):
    on = _body(request).get("on")
    if not isinstance(on, bool):
        return _problem("bad_request", "Say whether the Internet should be on or off.")
    now = now or datetime.now(UTC)
    feed = feed or OwnerFeed(timeout=INTERNET_CALL_SECONDS, deadline=time.monotonic() + INTERNET_BUDGET_SECONDS,
                             clock=time.monotonic)
    state = _internet_state()
    if not on:
        try:
            stopped, unconfirmed, titles = _pause_working_chats(feed)
        except FeedError as exc:
            return _failure(exc)
        paused = list(dict.fromkeys(state["paused"] + stopped + unconfirmed))
        store.write_json("internet.json", {"off": True, "since": state["since"] if state["off"] else now.isoformat(),
                                           "paused": paused, "titles": {**state["titles"], **titles}})
        record_switch(False, len(stopped) + len(unconfirmed), now)
        return {"ok": True, "off": True, "paused": len(stopped), "unconfirmed": len(unconfirmed)}
    # Back on: tell each stopped chat to continue, unless it's working again or waiting on the
    # owner (he restarted it meanwhile) or it was deleted. If Möbius can't list the chats, the
    # Internet stays off so another press can try again.
    try:
        present = {c.get("id"): c for c in feed.list_chats()} if state["paused"] else {}
    except FeedError as exc:
        return _failure(exc)
    to_tell = [chat_id for chat_id in state["paused"]
               if chat_id in present and office.chat_state(present[chat_id]) not in ("working", "needs_you")]
    results = _tell_to_continue(feed, to_tell)
    store.write_json("internet.json", {"off": False, "since": None, "paused": [], "titles": {}})
    told = sum(1 for ok in results if ok)
    failed = [chat_id for chat_id, ok in zip(to_tell, results) if not ok]
    record_switch(True, told, now)
    return {"ok": True, "off": False, "told": told, "failed": len(failed),
            "failed_names": [state["titles"].get(c) or present[c].get("title") or "A chat" for c in failed]}


# --- Quick reply: read a chat, reply, answer its question, open it beside -------

# Möbius ends a service request at 15 s; a read plus a send stay well inside it.
REPLY_BUDGET_SECONDS = 12.0
REPLY_LOG_KEEP = timedelta(days=30)
_ID_MAX = 200


def _problem(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}


def _is_id(value):
    return isinstance(value, str) and 0 < len(value) <= _ID_MAX


def _reply_feed(feed):
    return feed or OwnerFeed(deadline=time.monotonic() + REPLY_BUDGET_SECONDS, clock=time.monotonic)


def _body(request):
    return request.get("body") if isinstance(request.get("body"), dict) else {}


_SECRET_REFUSAL = ("full_chat_only", "It's asking for a secret. Those are typed only in the full chat's sealed card.")


def _owner_chat(feed, chat_id):
    """The chat's recent detail, or a refusal when it isn't one of the owner's chats."""
    detail = feed.chat_thread(chat_id)
    if detail.get("created_by_app_id") is not None:
        return None, _problem("not_owner", "The office only replies to your own chats.")
    return detail, None


def record_reply(kind, chat_id, result, now):
    """Log what the office sent — never the text — keeping 30 days."""
    kept = [entry for entry in store.read_json("reply-log.json", [])
            if (office.parse_time(entry.get("at")) or now) >= now - REPLY_LOG_KEEP]
    entry = {"at": now.isoformat(), "chat_id": chat_id, "kind": kind, "ok": bool(result.get("ok"))}
    if not result.get("ok"):
        entry["code"] = (result.get("error") or {}).get("code")
    kept.append(entry)
    store.write_json("reply-log.json", kept)


@route("GET", "thread")
def _thread(request, feed, now):
    chat_id = ((request.get("query") or {}).get("chat_id") or [None])[0]
    if not _is_id(chat_id):
        return _problem("bad_request", "Say which chat.")
    try:
        detail, refusal = _owner_chat(_reply_feed(feed), chat_id)
    except FeedError as exc:
        return _failure(exc)
    return refusal or {"ok": True, **quick_reply.thread_view(detail)}


@route("POST", "reply")
def _reply(request, feed, now):
    now = now or datetime.now(UTC)
    body = _body(request)
    chat_id, text, cid = body.get("chat_id"), body.get("text"), body.get("cid")
    text = text.strip() if isinstance(text, str) else ""
    if not (_is_id(chat_id) and _is_id(cid)) or not text:
        return _problem("bad_request", "Write a message first.")
    feed = _reply_feed(feed)
    try:
        detail, result = _owner_chat(feed, chat_id)
        if result is None and quick_reply.pending_secret(detail):
            result = _problem(*_SECRET_REFUSAL)  # never let a secret travel as a plain reply
        if result is None and detail.get("pending_question_id"):
            result = _problem("question_waiting", "It's waiting on a question. Answer that first.")
        if result is None:
            sent = feed.send_message(chat_id, {"content": text, "cid": cid}) or {}
            result = {"ok": True, "status": sent.get("status") or "started"}
    except FeedError as exc:
        result = _failure(exc)
    record_reply("reply", chat_id, result, now)
    return result


@route("POST", "answer")
def _answer(request, feed, now):
    now = now or datetime.now(UTC)
    body = _body(request)
    chat_id, question_id, cid = body.get("chat_id"), body.get("question_id"), body.get("cid")
    picks = body.get("picks") if isinstance(body.get("picks"), dict) else {}
    typed = body.get("text") if isinstance(body.get("text"), str) else None
    if not (_is_id(chat_id) and _is_id(question_id) and _is_id(cid)):
        return _problem("bad_request", "Say which chat and question.")
    feed = _reply_feed(feed)
    try:
        detail, result = _owner_chat(feed, chat_id)
        if result is None and quick_reply.pending_secret(detail):
            result = _problem(*_SECRET_REFUSAL)
        # Re-read before answering: never answer a question that changed after it was shown.
        block = quick_reply.pending_question(detail) if result is None else None
        if result is None and (detail.get("pending_question_id") != question_id or block is None):
            result = _problem("question_changed", "This question changed. Take another look.")
        if result is None and quick_reply.full_chat_reason(block):
            result = _problem("full_chat_only", "This one needs the full chat.")
        if result is None:
            quick_reply.check_answer(block, picks, typed)
            sent = feed.send_message(chat_id, quick_reply.answer_body(block, picks, typed, cid)) or {}
            result = {"ok": True, "answer_turn": sent.get("answer_turn")}
    except quick_reply.AnswerProblem as problem:
        # A pick the card no longer offers means the card changed (spec §5.2).
        result = (_problem("question_changed", "This question changed. Take another look.")
                  if problem.code == "unknown_option" else _problem(problem.code, str(problem)))
    except FeedError as exc:
        result = _failure(exc)
    record_reply("answer", chat_id, result, now)
    return result


@route("POST", "open-beside")
def _open_beside(request, feed, now):
    now = now or datetime.now(UTC)
    chat_id = _body(request).get("chat_id")
    if not _is_id(chat_id):
        return _problem("bad_request", "Say which chat.")
    feed = _reply_feed(feed)
    try:
        _, result = _owner_chat(feed, chat_id)
        if result is None:
            feed.open_beside(chat_id, os.environ.get("APP_ID", ""))
            result = {"ok": True}
    except FeedError as exc:
        result = _failure(exc)
    record_reply("open_beside", chat_id, result, now)
    return result


def dispatch(request, *, feed=None, now=None):
    method = str(request.get("method") or "").upper()
    path = str(request.get("path") or "").lstrip("/")
    handler = ROUTES.get((method, path))
    if handler is None:
        return {"status": 404, "body": {"detail": "Not found."}}
    return {"status": 200, "body": handler(request, feed, now)}


# Möbius may import this module once and fork each request from it, so module
# setup reads no per-request state (the owner key is read inside each call).
MOBIUS_PRELOAD = True

if __name__ == "__main__":
    envelope = json.loads(sys.stdin.read())
    print(json.dumps(dispatch(envelope), ensure_ascii=False, separators=(",", ":")))
