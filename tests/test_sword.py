from datetime import timedelta

import store
from feed import FeedError
from helpers import ANY_STR, NOW, FakeFeed, RaisingFeed, chat, iso, run_snapshot
from service import dispatch, record_swing

STOPPED = {"stopped": True, "cleared_pending_cids": ["m1"], "cancelled_delegations": ["d1", "d2"]}
NOT_STOPPED = {"stopped": False, "cleared_pending_cids": [], "cancelled_delegations": []}


def sword(kind, target, feed, now=NOW):
    return dispatch({"method": "POST", "path": "sword", "body": {"kind": kind, "id": target}}, feed=feed, now=now)["body"]


def logged():
    return [(entry["target"], entry["result"]) for entry in store.read_json("sword-log.json", [])]


def test_a_struck_chat_is_stopped_then_deleted():
    feed = FakeFeed(stop=STOPPED)
    body = sword("chat", "c1", feed)
    assert body == {"ok": True, "deleted": True, "cancelled_helpers": 2, "discarded_messages": 1}
    # Stop first: it clears the queue and reports what went with the chat.
    assert feed.actions == [("stop", "c1"), ("delete", "c1")]


def test_an_unconfirmed_stop_deletes_nothing():
    feed = FakeFeed(stop=NOT_STOPPED)
    body = sword("chat", "c2", feed)
    assert body == {"ok": False, "error": {"code": "stop_failed", "message": "Möbius didn't confirm the stop."}}
    assert feed.actions == [("stop", "c2")]


def test_a_delete_that_fails_after_the_stop_says_the_chat_was_only_stopped():
    busy = FeedError("conflict", "Möbius is still wrapping up that chat's work. Try again in a moment.")
    body = sword("chat", "c3", FakeFeed(stop=STOPPED, delete=busy))
    assert body == {"ok": False, "stopped": True, "error": {"code": "conflict", "message": str(busy)}}


def test_a_helper_is_dismissed_not_deleted():
    feed = FakeFeed(cancel={"id": "d9", "status": "cancelled", "cancelled_at": "2026-09-28T17:00:00"})
    body = sword("helper", "d9", feed)
    assert body == {"ok": True, "dismissed": True} and feed.actions == [("cancel", "d9")]


def test_a_helper_that_already_finished_is_not_reported_as_dismissed():
    body = sword("helper", "d9", FakeFeed(cancel={"id": "d9", "status": "completed", "cancelled_at": None}))
    assert body["ok"] is False and body["error"]["code"] == "stop_failed"


def test_mobius_errors_are_reported():
    body = sword("chat", "c4", RaisingFeed("key_rejected"))
    assert body["ok"] is False and body["error"]["code"] == "key_rejected"


def test_bad_request():
    assert sword("dragon", "x", FakeFeed())["error"]["code"] == "bad_request"
    assert dispatch({"method": "POST", "path": "sword", "body": None}, feed=FakeFeed(), now=NOW)["body"]["error"]["code"] == "bad_request"


def test_every_swing_is_logged_with_its_outcome():
    sword("chat", "c1", FakeFeed(stop=STOPPED))
    sword("chat", "c2", FakeFeed(stop=NOT_STOPPED))
    sword("chat", "c3", FakeFeed(stop=STOPPED, delete=FeedError("conflict", "later")))
    sword("helper", "d9", FakeFeed(cancel={"id": "d9", "status": "cancelled"}))
    assert logged() == [("c1", {"ok": True, "deleted": True}), ("c2", {"ok": False, "code": "stop_failed"}),
                        ("c3", {"ok": False, "stopped": True, "code": "conflict"}), ("d9", {"ok": True, "dismissed": True})]


def test_log_prunes_after_30_days():
    record_swing("chat", "old", {"ok": True, "deleted": True}, NOW - timedelta(days=31))
    record_swing("chat", "new", {"ok": True, "deleted": True}, NOW)
    assert [target for target, _ in logged()] == ["new"]


def test_chats_struck_by_the_old_stop_only_sword_show_their_real_state():
    store.write_json("sword-log.json", [{"at": iso(NOW - timedelta(minutes=5)), "kind": "chat", "target": "c1",
                                         "result": {"ok": True, "stopped": True}}])
    snap = run_snapshot(FakeFeed([chat(id="c1", activity_at=NOW - timedelta(minutes=6))]), NOW)
    assert snap["characters"][0]["state"] == "on_break" and "gone_home" not in snap["counts"]


def test_the_sword_gives_mobius_time_to_stop_a_stubborn_chat_within_the_15_s_limit(monkeypatch):
    import service
    made = []

    class RecordingFeed(FakeFeed):
        def __init__(self, **options):
            made.append(options)
            super().__init__(stop=STOPPED)

    monkeypatch.setattr(service, "OwnerFeed", RecordingFeed)
    started = service.time.monotonic()
    body = dispatch({"method": "POST", "path": "sword", "body": {"kind": "chat", "id": "c1"}}, now=NOW)["body"]
    assert body["ok"] is True
    # Möbius's stop can take 2 s graceful + 5 s forced; Möbius ends a service request at 15 s.
    assert made[0]["timeout"] >= 8 and made[0]["deadline"] - started <= 13.5


def test_a_stop_without_an_answer_in_time_is_reported_as_unconfirmed():
    slow = FeedError("mobius_unavailable", "Möbius didn't answer in time.")
    body = sword("chat", "c1", FakeFeed(stop=slow))
    assert body["ok"] is False and body["error"]["code"] == "unconfirmed" and "stopped" not in body


def test_a_delete_without_an_answer_in_time_is_reported_as_unconfirmed():
    slow = FeedError("mobius_unavailable", "Möbius didn't answer in time.")
    body = sword("chat", "c1", FakeFeed(stop=STOPPED, delete=slow))
    assert body == {"ok": False, "stopped": True, "error": {"code": "unconfirmed", "message": ANY_STR}}


def test_the_sword_refuses_a_chat_an_app_made():
    # Only the owner's own chats can be struck, as with quick reply (final review, Oct 7).
    from helpers import detail
    made = dict(detail("c9"), created_by_app_id=5)
    feed = FakeFeed(stop=STOPPED, details={"c9": made})
    body = sword("chat", "c9", feed)
    assert body["ok"] is False and body["error"]["code"] == "not_owner"
    assert feed.actions == []
