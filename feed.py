"""The Agent Office's only door into Möbius's owner API.

Everything the office learns about agents, and everything it changes (the
sword: stopping and deleting a chat, or dismissing a helper; quick reply:
sending a reply or an answer, and opening a chat beside the office), passes
through `OwnerFeed`. When Möbius gains a narrow
agent-presence permission, this module is the one to replace; nothing else
reads the owner key or calls owner routes.
"""

import json
import os
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote


class FeedError(Exception):
    """A Möbius call failed. `code` names a failure the office can explain.

    Messages are written here, never copied from the request, so they cannot
    carry the owner key.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _conflict_reason(exc):
    """Möbius's own sentence for a 409, when its body carries one."""
    try:
        detail = json.loads(exc.read() or b"{}").get("detail")
    except (ValueError, AttributeError, OSError):
        return None
    if isinstance(detail, dict):
        detail = detail.get("message")
    return detail.strip() if isinstance(detail, str) and detail.strip() else None


def _http_failure(status, reason=None):
    if status in (401, 403):
        return FeedError("key_rejected", "Möbius rejected the owner key.")
    if status == 404:
        return FeedError("not_found", "Möbius doesn't have that anymore.")
    if status == 410:
        # Möbius closed the question between the office's re-read and its answer.
        return FeedError("question_changed", "This question changed. Take another look.")
    if status == 409:
        return FeedError("conflict", reason or "Möbius is still wrapping up that work. Try again in a moment.")
    return FeedError("mobius_unavailable", f"Möbius couldn't answer (HTTP {status}).")


class OwnerFeed:
    """Each call waits at most `timeout` seconds. With a `deadline` (a `clock()`
    reading), calls also share one budget: a call waits only for the time left,
    and none starts once it is spent, so a whole request has a hard ceiling."""

    def __init__(self, base_url=None, key_path=None, opener=urllib.request.urlopen, timeout=4.0,
                 deadline=None, clock=time.monotonic):
        self.base_url = (base_url or os.environ.get("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.key_path = Path(key_path) if key_path else Path(os.environ.get("DATA_DIR", "/data")) / "service-token.txt"
        self.opener = opener
        self.timeout = timeout
        self.deadline = deadline
        self.clock = clock

    def list_chats(self):
        return self._call("GET", "/api/chats?limit=200")

    def chat_detail(self, chat_id):
        return self._call("GET", f"/api/chats/{quote(chat_id, safe='')}?limit=1")

    def list_delegations(self, limit=200):
        return self._call("GET", f"/api/delegations?limit={int(limit)}").get("items", [])

    def lifecycle(self, after_id, runs_after_id):
        return self._call(
            "GET",
            f"/api/chats/lifecycle-events?after_id={int(after_id)}&runs_after_id={int(runs_after_id)}"
            "&limit=500&run_limit=500",
        )

    def list_apps(self):
        body = self._call("GET", "/api/apps/")
        return body if isinstance(body, list) else body.get("apps") or body.get("items") or []

    def stop_chat(self, chat_id):
        return self._call("POST", "/api/chat/stop", {"chat_id": chat_id})

    def delete_chat(self, chat_id):
        # Möbius soft-deletes: the chat is recoverable for 7 days and the owner
        # gets a notification with a Recover action. Answers 204, no body.
        return self._call("DELETE", f"/api/chats/{quote(chat_id, safe='')}")

    def chat_thread(self, chat_id, limit=8):
        # The quick-reply card: the chat's last few messages and what it waits on.
        return self._call("GET", f"/api/chats/{quote(chat_id, safe='')}?limit={int(limit)}")

    def send_message(self, chat_id, body):
        # A reply or a question answer, exactly as the chat's own composer or card sends it.
        return self._call("POST", f"/api/chats/{quote(chat_id, safe='')}/messages", body)

    def open_beside(self, chat_id, app_id):
        # Ask every open Möbius window to show the chat in a pane beside this office.
        return self._call("POST", "/api/notify", {
            "type": "open_item", "itemKind": "chat", "itemId": chat_id,
            "sourceKind": "app", "sourceId": str(app_id),
            "placement": "beside-source", "activation": "foreground",
        })

    def cancel_helper(self, delegation_id):
        return self._call("POST", f"/api/delegations/{quote(delegation_id, safe='')}/cancel", {})

    def _key(self):
        # Read on every call: Möbius re-mints the key, and "sign out everywhere"
        # revokes it, so a cached copy would go stale silently.
        try:
            key = self.key_path.read_text().strip()
        except OSError:
            key = ""
        if not key:
            raise FeedError("no_key", "Möbius's owner key is missing.")
        return key

    def _wait_limit(self):
        if self.deadline is None:
            return self.timeout
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise FeedError("mobius_unavailable", "Möbius didn't answer in time.")
        return min(self.timeout, remaining)

    def _call(self, method, path, body=None):
        timeout = self._wait_limit()
        key = self._key()
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {key}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self.opener(request, timeout=timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise _http_failure(exc.code, _conflict_reason(exc) if exc.code == 409 else None) from None
        except (URLError, OSError):  # includes TimeoutError and refused connections
            raise FeedError("mobius_unavailable", "Möbius didn't answer in time.") from None
        try:
            return json.loads(raw) if raw else {}
        except ValueError:
            raise FeedError("mobius_unavailable", "Möbius sent an unreadable answer.") from None
