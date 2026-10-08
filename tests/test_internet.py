"""The Internet box (an IT Crowd joke, owner's idea, Oct 7): the black box with the red light in the
coffee corner. Turning it off pauses every agent that is working; turning it on again tells each of
them to continue. The screen asks for a second click before turning it off."""

import store
from feed import FeedError
from helpers import NOW, FakeFeed, RaisingFeed, chat, run_snapshot
from service import CONTINUE_TEXT, dispatch

STOPPED = {"stopped": True, "cleared_pending_cids": [], "cancelled_delegations": []}


def internet(on, feed, now=NOW):
    return dispatch({"method": "POST", "path": "internet", "body": {"on": on}}, feed=feed, now=now)["body"]


def saved():
    return store.read_json("internet.json", {})


def test_turning_it_off_stops_every_working_chat_and_remembers_them():
    chats = [chat(id="w1", running=True), chat(id="idle"), chat(id="ask", running=True, pending_question_id="q1"),
             chat(id="timer", waiting=True), chat(id="broken", running=True, has_unseen_failure=True),
             chat(id="w2", running=True), chat(id="made-by-an-app", running=True, created_by_app_id=7)]
    feed = FakeFeed(chats=chats, stop=STOPPED)
    body = internet(False, feed)
    assert body == {"ok": True, "off": True, "paused": 2, "unconfirmed": 0}
    # Only the owner's working chats: never one waiting on the owner's answer (a stop would withdraw
    # the question), on a timer, or showing an error (final review, Oct 7).
    assert sorted(feed.actions) == [("stop", "w1"), ("stop", "w2")]
    assert saved()["off"] is True and sorted(saved()["paused"]) == ["w1", "w2"]


def test_turning_it_back_on_tells_each_paused_chat_to_continue_then_forgets_them():
    feed = FakeFeed(chats=[chat(id="w1", running=True), chat(id="w2", running=True)], stop=STOPPED)
    internet(False, feed)
    feed.chats = [chat(id="w1"), chat(id="w2")]  # stopped, so no longer running
    body = internet(True, feed)
    assert body == {"ok": True, "off": False, "told": 2, "failed": 0, "failed_names": []}
    assert sorted(chat_id for chat_id, _ in feed.sent) == ["w1", "w2"]
    assert all(sent["content"] == CONTINUE_TEXT and sent["cid"] for _, sent in feed.sent)
    assert len({sent["cid"] for _, sent in feed.sent}) == 2  # each message is its own
    assert saved()["off"] is False and saved()["paused"] == []


def test_a_stop_möbius_did_not_confirm_is_still_told_to_continue_later():
    feed = FakeFeed(chats=[chat(id="w1", running=True)], stop={"stopped": False})
    assert internet(False, feed) == {"ok": True, "off": True, "paused": 0, "unconfirmed": 1}
    assert saved()["paused"] == ["w1"]
    feed = FakeFeed(chats=[chat(id="w2", running=True)], stop=FeedError("mobius_unavailable", "slow"))
    store.write_json("internet.json", {})
    assert internet(False, feed) == {"ok": True, "off": True, "paused": 0, "unconfirmed": 1}


def test_a_chat_that_cannot_take_the_message_does_not_keep_the_internet_off():
    feed = FakeFeed(chats=[chat(id="w1", title="Trip planner", running=True)], stop=STOPPED,
                    send=FeedError("conflict", "Möbius is still wrapping up that work."))
    internet(False, feed)
    feed.chats = [chat(id="w1", title="Trip planner")]
    # The chat is named, so the owner can tell it to continue himself (final review, Oct 7).
    assert internet(True, feed) == {"ok": True, "off": False, "told": 0, "failed": 1, "failed_names": ["Trip planner"]}
    assert saved()["off"] is False


def test_turning_it_off_again_adds_whoever_started_working_since():
    internet(False, FakeFeed(chats=[chat(id="w1", running=True)], stop=STOPPED))
    internet(False, FakeFeed(chats=[chat(id="w2", running=True)], stop=STOPPED))
    assert sorted(saved()["paused"]) == ["w1", "w2"]


def test_turning_it_on_when_it_is_already_on_tells_nobody():
    feed = FakeFeed()
    assert internet(True, feed) == {"ok": True, "off": False, "told": 0, "failed": 0, "failed_names": []}
    assert feed.sent == []


def test_key_trouble_leaves_the_internet_on():
    body = internet(False, RaisingFeed("key_rejected"))
    assert body["ok"] is False and body["error"]["code"] == "key_rejected"
    assert saved().get("off") is not True


def test_bad_request():
    for body in ({"on": "yes"}, {}, None):
        reply = dispatch({"method": "POST", "path": "internet", "body": body}, feed=FakeFeed(), now=NOW)["body"]
        assert reply["error"]["code"] == "bad_request"


def test_every_switch_is_logged_without_any_text():
    feed = FakeFeed(chats=[chat(id="w1", running=True)], stop=STOPPED)
    internet(False, feed)
    feed.chats = [chat(id="w1")]
    internet(True, feed)
    log = store.read_json("internet-log.json", [])
    assert [(entry["on"], entry["count"]) for entry in log] == [(False, 1), (True, 1)]


def test_the_snapshot_says_whether_the_internet_is_off():
    feed = FakeFeed(chats=[chat(id="w1", running=True)], stop=STOPPED)
    assert run_snapshot(FakeFeed(), NOW)["internet"] == {"off": False, "paused": 0}
    internet(False, feed)
    assert run_snapshot(FakeFeed(), NOW)["internet"] == {"off": True, "paused": 1}


def test_turning_it_on_leaves_alone_chats_working_again_or_deleted():
    feed = FakeFeed(chats=[chat(id=i, running=True) for i in ("w1", "w2", "w3")], stop=STOPPED)
    internet(False, feed)
    feed.chats = [chat(id="w1"), chat(id="w2", running=True)]  # w2 was restarted by hand; w3 was deleted
    body = internet(True, feed)
    assert body == {"ok": True, "off": False, "told": 1, "failed": 0, "failed_names": []}
    assert [chat_id for chat_id, _ in feed.sent] == ["w1"]


def test_if_mobius_cannot_list_chats_the_internet_stays_off_to_try_again():
    feed = FakeFeed(chats=[chat(id="w1", running=True)], stop=STOPPED)
    internet(False, feed)
    body = internet(True, RaisingFeed("mobius_unavailable"))
    assert body["ok"] is False and saved()["off"] is True and saved()["paused"] == ["w1"]
