"""The CR desk (spec 2026-10-08 §7.4, §8): hiring starts a real chat with the owner's name and first message."""

import json
import uuid

import pytest

import store
from feed import FeedError
from helpers import NOW, FakeFeed
from service import dispatch

GOOD = {"title": "  Fix login  ", "text": "The login page answers 500. Find out why.", "cid": "hire-1"}


def hire(body, feed, now=NOW):
    return dispatch({"method": "POST", "path": "hire", "body": body}, feed=feed, now=now)["body"]


def test_hiring_creates_the_chat_locks_its_name_and_sends_the_first_message():
    feed = FakeFeed()
    body = hire(GOOD, feed)
    chat_id = body["chat_id"]
    assert body == {"ok": True, "chat_id": chat_id}
    # The rename locks the owner's name; otherwise Möbius renames a chat from its first message.
    assert feed.actions == [("create", chat_id, "Fix login"), ("rename", chat_id, "Fix login")]
    assert feed.sent == [(chat_id, {"content": GOOD["text"], "cid": "hire-1"})]


def test_a_retried_hire_lands_on_the_same_chat():
    first = hire(GOOD, FakeFeed())["chat_id"]
    again = hire(GOOD, FakeFeed())["chat_id"]
    other = hire({**GOOD, "cid": "hire-2"}, FakeFeed())["chat_id"]
    assert first == again != other and str(uuid.UUID(first)) == first


@pytest.mark.parametrize("change", [{"title": "   "}, {"title": "x" * 81}, {"text": ""}, {"text": "y" * 8001},
                                    {"cid": ""}, {"title": None}, {"text": 5}])
def test_bad_hires_are_refused_before_anything_happens(change):
    feed = FakeFeed()
    body = hire({**GOOD, **change}, feed)
    assert body["ok"] is False and body["error"]["code"] == "bad_request"
    assert feed.actions == [] and feed.sent == []


def test_a_first_message_that_fails_after_the_chat_exists_says_so():
    feed = FakeFeed(send=FeedError("conflict", "Möbius is still wrapping up that work."))
    body = hire(GOOD, feed)
    assert body == {"ok": False, "created": True, "chat_id": body["chat_id"],
                    "error": {"code": "conflict", "message": "Möbius is still wrapping up that work."}}


def test_a_create_that_fails_does_nothing_else():
    feed = FakeFeed(create=FeedError("key_rejected", "Möbius rejected the owner key."))
    body = hire(GOOD, feed)
    assert body["ok"] is False and body["error"]["code"] == "key_rejected" and "created" not in body
    assert [action[0] for action in feed.actions] == ["create"] and feed.sent == []


def test_hires_are_logged_without_any_text():
    chat_id = hire(GOOD, FakeFeed())["chat_id"]
    log = store.read_json("hire-log.json", [])
    assert log == [{"at": NOW.isoformat(), "chat_id": chat_id, "ok": True}]
    assert "login" not in json.dumps(log).lower()


# --- Final review, Oct 8 ----------------------------------------------------------------------

def test_a_rename_that_fails_once_is_retried():
    feed = FakeFeed(rename=[FeedError("mobius_unavailable", "slow")])
    body = hire(GOOD, feed)
    assert body == {"ok": True, "chat_id": body["chat_id"]}
    assert [action[0] for action in feed.actions] == ["create", "rename", "rename"]


def test_a_name_that_could_not_be_locked_is_reported():
    # Möbius would otherwise rename the chat from its first message, so the toast must say so.
    feed = FakeFeed(rename=[FeedError("conflict", "busy"), FeedError("conflict", "busy")])
    body = hire(GOOD, feed)
    assert body == {"ok": True, "chat_id": body["chat_id"], "name_locked": False}
    assert len(feed.sent) == 1  # the new hire still starts


def test_a_first_message_that_timed_out_is_unconfirmed_not_failed():
    # It may well have arrived; saying "didn't send" would invite the owner to send it twice.
    feed = FakeFeed(send=FeedError("mobius_unavailable", "Möbius didn't answer in time."))
    body = hire(GOOD, feed)
    assert body["ok"] is False and body["created"] is True and body["error"]["code"] == "unconfirmed"
