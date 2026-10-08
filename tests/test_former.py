"""Former staff (owner's idea, Oct 8): deleted chats Möbius can still recover, with days left, and rehiring them."""

from datetime import timedelta

import pytest

import store
from feed import FeedError
from helpers import NOW, FakeFeed, iso
from office import former_staff, look_for
from service import dispatch


def gone(cid, title, hours_ago):
    return {"id": cid, "title": title, "deleted_at": iso(NOW - timedelta(hours=hours_ago)), "recency_at": None}


def test_days_left_count_down_from_7_and_the_soonest_comes_first():
    rows = [gone("a", "Weather", 2), gone("b", "Trip map", 30), gone("c", "Old one", 24 * 6 + 20), gone("d", "Too old", 24 * 7 + 1)]
    staff = former_staff(rows, NOW)
    assert [(s["id"], s["days_left"]) for s in staff] == [("c", 1), ("b", 6), ("a", 7)]  # "d" is past 7 days
    assert staff[2]["name"] == "Weather" and staff[2]["look"] == look_for("a") and staff[2]["short"] == "Weather"


def test_untitled_and_odd_rows_are_handled():
    staff = former_staff([{"id": "x", "title": None, "deleted_at": iso(NOW)}, {"id": "y", "title": "No date"}], NOW)
    assert [(s["id"], s["name"]) for s in staff] == [("x", "Untitled chat")]


def test_the_former_staff_route_lists_them():
    feed = FakeFeed(deleted=[gone("a", "Weather", 2)])
    body = dispatch({"method": "GET", "path": "former"}, feed=feed, now=NOW)["body"]
    assert body["ok"] is True and [s["id"] for s in body["items"]] == ["a"] and body["items"][0]["days_left"] == 7


def rehire(chat_id, feed):
    return dispatch({"method": "POST", "path": "rehire", "body": {"chat_id": chat_id}}, feed=feed, now=NOW)["body"]


def test_rehiring_recovers_the_chat_and_logs_it_without_text():
    feed = FakeFeed(deleted=[gone("a", "Weather", 2)])
    assert rehire("a", feed) == {"ok": True, "chat_id": "a"}
    assert feed.actions == [("recover", "a")]
    assert store.read_json("rehire-log.json", []) == [{"at": NOW.isoformat(), "chat_id": "a", "ok": True}]


def test_only_listed_agents_can_be_rehired():
    feed = FakeFeed(deleted=[gone("a", "Weather", 2)])
    body = rehire("someone-else", feed)
    assert body["ok"] is False and body["error"]["code"] == "not_found" and feed.actions == []


@pytest.mark.parametrize("bad", [None, "", 5])
def test_a_bad_rehire_is_refused(bad):
    assert rehire(bad, FakeFeed())["error"]["code"] == "bad_request"


def test_too_late_is_said_plainly():
    feed = FakeFeed(deleted=[gone("a", "Weather", 2)], recover=FeedError("too_late", "Too late: the 7 days are over."))
    body = rehire("a", feed)
    assert body["ok"] is False and body["error"]["code"] == "too_late"
