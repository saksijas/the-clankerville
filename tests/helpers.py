"""Shared fakes for the Agent Office back-room tests.

Fake `opener`s stand in for urllib.request.urlopen: they receive the real
Request object the feed builds, so tests assert on the exact URL, method,
headers and body that would reach Möbius.
"""

import io
import json
from datetime import UTC, datetime
from urllib.error import HTTPError

NOW = datetime(2026, 9, 28, 17, 0, tzinfo=UTC)


def iso(dt):
    """A naive-UTC ISO string, the format Möbius's API returns."""
    return dt.astimezone(UTC).replace(tzinfo=None).isoformat()


def chat(**kw):
    """One `/api/chats` row with every field the real list returns.

    Datetime overrides are converted to the API's string format.
    """
    row = {
        "id": "c1", "title": "Chat", "updated_at": iso(NOW), "activity_at": iso(NOW),
        "pinned_at": None, "has_messages": True, "created_by_app_id": None, "project": None,
        "running": False, "waiting": False, "pending_question_id": None,
        "owner_input_kind": None, "has_unseen_failure": False, "unseen_failure_version": None,
    }
    row.update({k: iso(v) if isinstance(v, datetime) else v for k, v in kw.items()})
    return row



def d(id, parent, status="running", child=None, task="task", ended=None, started=None, root=None, created=None):
    """One `/api/delegations` item with every field the real list returns."""
    return {
        "id": id, "app_id": None, "parent_chat_id": parent, "parent_chat_title": "Chat",
        "parent_root_run_id": root, "task_key": task, "child_chat_id": child or f"cc-{id}",
        "provider": "claude", "model": "claude-sonnet", "effort": None, "scope": "write",
        "cwd": "/data", "observation_mode": None, "status": status, "physical_run_id": None,
        "provider_session_id": None, "started_at": started, "ended_at": ended,
        "created_at": created, "cancelled_at": ended if status == "cancelled" else None,
        "usage": None,
    }


def detail(chat_id, blocks=(), pending=0, running=True):
    """One `GET /api/chats/{id}?limit=1` body with the real top-level fields."""
    return {
        "id": chat_id, "title": "Chat", "updated_at": iso(NOW),
        "messages": [{"role": "user", "content": "hi", "id": "m0", "ts": iso(NOW)},
                     {"role": "assistant", "content": "", "blocks": list(blocks), "id": "m1", "ts": iso(NOW)}],
        "pending_messages": [{"cid": f"q{i}", "content": "queued"} for i in range(pending)],
        "total": 2, "offset": 0, "running": running, "run_id": "r1", "run_status": "running" if running else "completed",
        "runtime_revision": 1, "active_assistant_message_id": "m1", "recovery_run_id": None,
        "active_goal_objective": None, "goal": None, "pending_question_id": None, "session_id": "s1",
        "provider": "claude", "created_by_app_id": None, "provider_switch_locked": False,
        "auto_resume_on_limit": False, "agent_settings_json": None, "effective_agent_settings": {},
        "has_assistant_turns": True, "project": None,
    }



def run(id, chat_id, status, ended=None):
    """One `runs[]` entry of GET /api/chats/lifecycle-events."""
    return {"id": id, "physical_run_id": f"p-{id}", "chat_id": chat_id, "provider": "claude",
            "status": status, "started_at": None, "ended_at": iso(ended) if ended else None}


def terminal(agent_id, chat_id, state, when=None):
    """One helper `agent_terminal` event of GET /api/chats/lifecycle-events."""
    moment = iso(when) if when else None
    return {"event_key": f"k-{agent_id}", "chat_id": chat_id, "chat_run_id": "r-parent", "provider": "claude",
            "provider_session_id": "s", "agent_id": agent_id, "agent_run_id": agent_id + "-1",
            "provider_agent_id": agent_id, "parent_agent_id": None, "parent_agent_run_id": None,
            "parent_kind": "main", "parent_source_id": None, "type": "agent_terminal", "state": state,
            "agent_type": "delegation", "summary": "task", "occurred_at": moment, "observed_at": moment}


def app(id, chat_id, created, updated=None):
    """One GET /api/apps/ row (the fields progress reads, plus identity)."""
    return {"id": id, "name": f"App {id}", "slug": f"app-{id}", "chat_id": chat_id,
            "created_at": iso(created), "updated_at": iso(updated or created)}


def fresh_state(days=None, chats=None, achievements=None):
    """An empty progress state (as progress.json holds it) with the given parts."""
    from progress import new_state
    state = new_state()
    state["days"] = dict(days or {})
    state["chats"] = dict(chats or {})
    state["achievements"] = list(achievements or [])
    return state

class FakeFeed:
    """Answers like Möbius's owner API from memory; records the actions taken."""

    def __init__(self, chats=(), delegations=(), details=None, stop=None, cancel=None, delete=None,
                 runs=(), helpers=(), apps=(), page_size=500, threads=None, send=None, create=None, rename=(),
                 deleted=(), recover=None):
        self.runs = [dict(r, update_id=i + 1) for i, r in enumerate(runs)]
        self.helpers = [dict(e, id=i + 1) for i, e in enumerate(helpers)]
        self.apps = [dict(a) for a in apps]
        self.page_size = page_size
        self.lifecycle_calls = 0
        self.chats = list(chats)
        self.delegations = list(delegations)
        self.details = dict(details or {})
        self.stop_reply = stop
        self.cancel_reply = cancel
        self.delete_failure = delete  # a FeedError to raise, or None for Möbius's empty 204
        self.actions = []  # ("stop" | "delete" | "cancel", id), in call order
        self.detail_calls = []
        self.threads = dict(threads or {})  # chat_id -> chat detail, or a FeedError to raise
        self.send_reply = send  # Möbius's reply to a sent message, or a FeedError to raise
        self.create_failure = create  # a FeedError for create_chat to raise, or None
        self.rename_failures = list(rename)  # FeedErrors for successive rename_chat calls to raise
        self.deleted = list(deleted)  # chat-logs rows of recoverable deleted chats
        self.recover_failure = recover  # a FeedError for recover_chat to raise, or None
        self.sent = []  # (chat_id, body) for every message sent
        self.beside = []  # (chat_id, app_id) for every open-beside request

    def list_chats(self):
        return list(self.chats)

    def list_delegations(self, limit=200):
        return list(self.delegations)[:limit]

    def chat_detail(self, chat_id):
        self.detail_calls.append(chat_id)
        found = self.details.get(chat_id)
        if isinstance(found, Exception):
            raise found
        return found if found is not None else detail(chat_id)

    def stop_chat(self, chat_id):
        self.actions.append(("stop", chat_id))
        if isinstance(self.stop_reply, Exception):
            raise self.stop_reply
        return self.stop_reply

    def delete_chat(self, chat_id):
        self.actions.append(("delete", chat_id))
        if self.delete_failure is not None:
            raise self.delete_failure
        return {}

    def cancel_helper(self, delegation_id):
        self.actions.append(("cancel", delegation_id))
        return self.cancel_reply

    def lifecycle(self, after_id, runs_after_id):
        """Pages like GET /api/chats/lifecycle-events: independent event and run cursors."""
        self.lifecycle_calls += 1
        events = [e for e in self.helpers if e["id"] > after_id]
        runs = [r for r in self.runs if r["update_id"] > runs_after_id]
        page_events, page_runs = events[: self.page_size], runs[: self.page_size]
        return {
            "events": page_events, "runs": page_runs,
            "next_after_id": page_events[-1]["id"] if page_events else after_id,
            "next_runs_after_id": page_runs[-1]["update_id"] if page_runs else runs_after_id,
            "has_more": len(events) > self.page_size, "runs_has_more": len(runs) > self.page_size,
        }

    def list_apps(self):
        return [dict(a) for a in self.apps]

    def chat_thread(self, chat_id):
        from feed import FeedError
        found = self.threads.get(chat_id)
        if isinstance(found, Exception):
            raise found
        if found is None:
            raise FeedError("not_found", "Möbius doesn't have that anymore.")
        return found

    def send_message(self, chat_id, body):
        self.sent.append((chat_id, body))
        if isinstance(self.send_reply, Exception):
            raise self.send_reply
        return self.send_reply if self.send_reply is not None else {"status": "started"}

    def create_chat(self, chat_id, title):
        self.actions.append(("create", chat_id, title))
        if self.create_failure is not None:
            raise self.create_failure
        return {"id": chat_id, "title": title}

    def rename_chat(self, chat_id, title):
        self.actions.append(("rename", chat_id, title))
        if self.rename_failures:
            raise self.rename_failures.pop(0)
        return {"id": chat_id, "title": title}

    def list_deleted_chats(self):
        return [dict(row) for row in self.deleted]

    def recover_chat(self, chat_id):
        self.actions.append(("recover", chat_id))
        if self.recover_failure is not None:
            raise self.recover_failure
        return {}

    def open_beside(self, chat_id, app_id):
        self.beside.append((chat_id, app_id))
        return {}

    def touch_app(self, app_id, when):
        for a in self.apps:
            if a["id"] == app_id:
                a["updated_at"] = iso(when)


class RaisingFeed:
    """Every Möbius call fails with the given FeedError code."""

    def __init__(self, code):
        self.code = code

    def __getattr__(self, name):
        from feed import FeedError

        def fail(*args, **kwargs):
            raise FeedError(self.code, "Möbius call failed in a test.")
        return fail


class _AnyString:
    def __eq__(self, other):
        return isinstance(other, str)

    def __repr__(self):
        return "ANY_STR"


ANY_STR = _AnyString()


def run_snapshot(feed, now):
    from service import dispatch
    return dispatch({"method": "GET", "path": "snapshot"}, feed=feed, now=now)["body"]

class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class Recorder:
    """An opener that records each Request and answers with `json_body`."""

    def __init__(self, json_body):
        self.json_body = json_body
        self.requests = []
        self.timeouts = []

    @property
    def last(self):
        return self.requests[-1]

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return _Response(json.dumps(self.json_body).encode())


class FakeClock:
    """A monotonic clock that only moves when a test advances it."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def key(tmp_path, text):
    path = tmp_path / "service-token.txt"
    path.write_text(text + "\n")
    return path


def http_error(code, body=None):
    def opener(request, timeout=None):
        raise HTTPError(request.full_url, code, f"HTTP {code}", {}, io.BytesIO(json.dumps(body or {}).encode()))
    return opener


def raiser(exc):
    def opener(request, timeout=None):
        raise exc
    return opener


def fail_if_called(request, timeout=None):
    raise AssertionError("the feed must not call Möbius without a key")


# --- Quick reply: chat detail building blocks --------------------------------

def msg(role, *blocks):
    """One message of GET /api/chats/{id} with its content blocks."""
    return {"role": role, "blocks": list(blocks)}


def text(value):
    """A text block exactly as Möbius stores it: the words are under "content"."""
    return {"type": "text", "content": value}


def tool(name):
    return {"type": "tool", "tool": name, "input": "", "status": "done"}


# The real question block this instance saved for the owner's
# "Which should I design?" card on 2026-09-28 (its recorded answer removed).
QUESTION = {
    "type": "question",
    "questions": [{
        "id": "side_chat_approach",
        "header": "Chat on the side",
        "question": "Which should I design?",
        "options": [
            {"label": "Both (Recommended)",
             "description": "On a computer, Open chat puts the full chat in a pane beside the office. On your phone, a character's card gets a quick-reply panel: its latest message or question, tap-to-answer, and a reply box, without leaving the office. I'll show a short design and a phone mockup before building.",
             "id": "0"},
            {"label": "Just the computer side pane",
             "description": "Small change: Open chat opens the full chat beside the office on wide screens. On your phone, Open chat still switches you to the chat (the office stays open as a tab).",
             "id": "1"},
            {"label": "Just the phone quick reply",
             "description": "The in-office reply panel on every device (latest message or question, answers, reply box); Open chat keeps working as it does today.",
             "id": "2"},
        ],
    }],
    "response_mode": "continuation",
    "question_id": "88f4a3cb-6a0d-5570-a7cf-f89900b38fba",
}


def thread(question=None, created_by_app_id=None, block_extra=None, pending=0, chat_id="c1"):
    """A GET /api/chats/{id}?limit=8 body whose last assistant message reads "Merge now?".

    With `question`, that message also carries the real QUESTION block under that
    id, and the chat is waiting on it.
    """
    blocks = [text("Merge now?")]
    if question:
        blocks.append({**QUESTION, **(block_extra or {}), "question_id": question})
    body = detail(chat_id, blocks, pending=pending, running=False)
    body.update(pending_question_id=question, created_by_app_id=created_by_app_id)
    return body


# A standalone sealed-input card exactly as Möbius records it (backend events.py
# secure_input_request): the chat waits on it without any pending question id.
SECRET_CARD = {
    "type": "secure_input", "request_id": "r1", "mode": "sealed", "title": "Deploy key", "description": "",
    "fields": [{"name": "key", "label": "Key", "type": "password", "autocomplete": "off"}],
    "status": "pending",
}
