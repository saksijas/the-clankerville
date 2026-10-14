"""Spend instead of XP (spec 2026-10-13): each chat's dollars and tokens from Möbius's turn records."""

from datetime import timedelta

import pytest

import spend
import store
from feed import FeedError
from helpers import NOW, FakeFeed, chat, iso, run, run_snapshot, usage_body, usage_run
from service import dispatch


def totals(*runs):
    return spend.chat_totals(usage_body("c1", *runs), NOW)


def office_chat(id, **kw):
    return chat(id=id, title=f"Chat {id}", **kw)


# --- Reading one chat's records -------------------------------------------------------------

def test_claude_readings_are_running_totals():
    # Found 2026-10-13: a Claude run's cost is the conversation's total so far (2.00, 2.21, 2.40 … 300.08).
    t = totals(usage_run("r1", 2.0, tokens=90, tally=100), usage_run("r2", 2.2, tokens=50, tally=150),
               usage_run("r3", 2.4, tokens=60, tally=210))
    assert t["usd"] == pytest.approx(2.4) and t["tokens"] == 210
    assert [turn[1] for turn in t["turns"]] == pytest.approx([2.0, 0.2, 0.2])
    assert [turn[2] for turn in t["turns"]] == [100, 50, 60]


def test_a_lower_reading_means_the_total_started_over():
    t = totals(usage_run("r1", 5.0, tally=500), usage_run("r2", 1.0, tally=100), usage_run("r3", 1.5, tally=150))
    assert t["usd"] == pytest.approx(6.5) and t["tokens"] == 650


def test_a_turn_without_a_reading_adds_nothing_and_the_next_reading_covers_it():
    t = totals(usage_run("r1", 1.0, tally=100), usage_run("r2", None, status="failed"),
               usage_run("r3", 3.0, tally=400))
    assert t["usd"] == pytest.approx(3.0) and t["tokens"] == 400
    assert [turn[1] for turn in t["turns"]] == pytest.approx([1.0, 2.0])


def test_each_conversation_keeps_its_own_running_total():
    t = totals(usage_run("r1", 1.0, tally=100, session="a"), usage_run("r2", 0.5, tally=50, session="b"),
               usage_run("r3", 2.0, tally=200, session="a"), usage_run("r4", 0.7, tally=70, session="b"))
    assert t["usd"] == pytest.approx(2.7) and t["tokens"] == 270


def test_other_providers_record_each_turn_on_its_own():
    # Möbius prices a Codex turn by itself from its rate card; an unpriced turn still used tokens.
    t = totals(usage_run("r1", 0.1, tokens=10, provider="codex"), usage_run("r2", 0.2, tokens=20, provider="codex"),
               usage_run("r3", None, tokens=30, provider="codex"))
    assert t["usd"] == pytest.approx(0.3) and t["tokens"] == 60


def test_without_a_model_tally_tokens_come_from_the_turns_own_counters():
    t = totals(usage_run("r1", 1.0, tokens=100), usage_run("r2", 2.0, tokens=50))
    assert t["usd"] == pytest.approx(2.0) and t["tokens"] == 150


def test_odd_readings_are_ignored_rather_than_trusted():
    t = totals(usage_run("r1", "lots", tokens=5), usage_run("r2", -3.0, tokens=5), usage_run("r3", 1.0, tokens=7))
    assert t["usd"] == pytest.approx(1.0) and t["tokens"] == 7


def test_only_the_last_eight_days_of_turns_are_kept_but_the_total_is_all_time():
    t = totals(usage_run("r1", 1.0, tally=10, ended=NOW - timedelta(days=9)),
               usage_run("r2", 3.0, tally=30, ended=NOW - timedelta(days=1)))
    assert t["usd"] == pytest.approx(3.0) and t["tokens"] == 30
    assert len(t["turns"]) == 1 and t["turns"][0][1] == pytest.approx(2.0)


# --- Days ---------------------------------------------------------------------------------

def test_today_and_yesterday_follow_the_owners_time_zone():
    # NOW is 2026-09-28 17:00 UTC; 02:00 UTC on the 28th is still the evening of the 27th in Chicago.
    late_evening = NOW.replace(hour=2)
    state = {"chats": {"c1": {"title": "Budget", "usd": 3.0, "tokens": 30,
                              "turns": [[iso(late_evening), 1.0, 10], [iso(NOW), 2.0, 20]]}}}
    entry = state["chats"]["c1"]
    assert spend.chat_view(entry, "2026-09-28", "America/Chicago") == {
        "usd": 3.0, "tokens": 30, "today_usd": 2.0, "today_tokens": 20}
    assert spend.chat_view(entry, "2026-09-28", "UTC")["today_usd"] == 3.0
    assert spend.day_summary(state, "2026-09-27", "America/Chicago") == {
        "usd": 1.0, "tokens": 10, "top": {"title": "Budget", "usd": 1.0}}
    assert spend.day_summary(state, "2026-09-26", "America/Chicago") is None


def test_the_biggest_spender_of_the_day_is_named():
    state = {"chats": {
        "a": {"title": "Small", "usd": 1, "tokens": 1, "turns": [[iso(NOW), 0.5, 5]]},
        "b": {"title": "Big", "usd": 9, "tokens": 9, "turns": [[iso(NOW), 2.0, 20], [iso(NOW), 1.0, 10]]},
    }}
    assert spend.day_summary(state, "2026-09-28", "UTC") == {"usd": 3.5, "tokens": 35, "top": {"title": "Big", "usd": 3.0}}


# --- Reading cheaply ----------------------------------------------------------------------

def test_a_chat_is_read_once_and_again_only_when_it_changes():
    feed = FakeFeed(usage={"c1": usage_body("c1", usage_run("r1", 1.0, tally=10))})
    state = spend.refresh(feed, [office_chat("c1")], {}, NOW)
    assert state["chats"]["c1"]["usd"] == 1.0 and feed.usage_calls == ["c1"]
    state = spend.refresh(feed, [office_chat("c1")], state, NOW + timedelta(seconds=3))
    assert feed.usage_calls == ["c1"]  # nothing changed, nothing read
    changed = [office_chat("c1", activity_at=NOW + timedelta(minutes=1))]
    spend.refresh(feed, changed, state, NOW + timedelta(minutes=1))
    assert feed.usage_calls == ["c1", "c1"]


def test_a_running_chat_is_read_at_most_once_a_minute():
    feed = FakeFeed()
    state = spend.refresh(feed, [office_chat("c1", running=True)], {}, NOW)
    for seconds in (3, 6, 30):
        busier = [office_chat("c1", running=True, activity_at=NOW + timedelta(seconds=seconds))]
        state = spend.refresh(feed, busier, state, NOW + timedelta(seconds=seconds))
    assert feed.usage_calls == ["c1"]
    later = [office_chat("c1", running=True, activity_at=NOW + timedelta(seconds=61))]
    spend.refresh(feed, later, state, NOW + timedelta(seconds=61))
    assert feed.usage_calls == ["c1", "c1"]


def test_an_unchanged_chat_is_read_again_after_six_hours():
    feed = FakeFeed()
    state = spend.refresh(feed, [office_chat("c1")], {}, NOW)
    spend.refresh(feed, [office_chat("c1")], state, NOW + timedelta(hours=6))
    assert feed.usage_calls == ["c1", "c1"]


def test_reads_are_capped_per_snapshot_and_unread_chats_go_first():
    feed = FakeFeed()
    chats = [office_chat(f"c{i}") for i in range(10)]
    state = spend.refresh(feed, chats, {}, NOW)
    first = list(feed.usage_calls)
    assert len(first) == spend.READS_PER_SNAPSHOT
    moved = [office_chat(c["id"], activity_at=NOW + timedelta(minutes=5)) for c in chats]  # everyone changed
    spend.refresh(feed, moved, state, NOW + timedelta(minutes=5))
    later = feed.usage_calls[len(first):]
    assert set(later[:4]) == {f"c{i}" for i in range(10)} - set(first)


def test_reading_stops_when_the_time_budget_runs_low():
    feed = FakeFeed()
    left = iter([True, True, False])
    spend.refresh(feed, [office_chat(f"c{i}") for i in range(5)], {}, NOW, budget_left=lambda: next(left))
    assert len(feed.usage_calls) == 2


def test_a_chat_whose_read_keeps_failing_does_not_block_the_others():
    # Review 2026-10-13: a never-read chat that always failed used to stay first in line and stop every read.
    feed = FakeFeed(usage={"c0": FeedError("mobius_unavailable", "slow"), "c1": FeedError("not_found", "gone")})
    chats = [office_chat(f"c{i}") for i in range(8)]
    state = spend.refresh(feed, chats, {}, NOW)
    assert feed.usage_calls == ["c0", "c1", "c2", "c3", "c4", "c5"]
    assert set(state["chats"]) == {"c2", "c3", "c4", "c5"} and set(state["failed"]) == {"c0", "c1"}
    state = spend.refresh(feed, chats, state, NOW + timedelta(seconds=3))
    assert feed.usage_calls[6:] == ["c6", "c7"]  # the failed two wait; the rest are read
    spend.refresh(feed, chats, state, NOW + spend.FAILED_BACKOFF)
    assert feed.usage_calls[8:] == ["c0", "c1"]  # tried again after the back-off


def test_key_trouble_stops_the_reading_without_blaming_the_chat():
    feed = FakeFeed(usage={"c0": FeedError("key_rejected", "revoked")})
    state = spend.refresh(feed, [office_chat("c0"), office_chat("c1")], {}, NOW)
    assert feed.usage_calls == ["c0"] and state["chats"] == {} and "failed" not in state


def test_a_chat_that_reads_again_is_no_longer_marked_failed():
    feed = FakeFeed(usage={"c0": FeedError("mobius_unavailable", "slow")})
    state = spend.refresh(feed, [office_chat("c0")], {}, NOW)
    feed.usage = {}
    state = spend.refresh(feed, [office_chat("c0")], state, NOW + spend.FAILED_BACKOFF)
    assert "c0" in state["chats"] and "failed" not in state


def test_a_restart_is_caught_even_when_the_new_reading_is_higher():
    # Review #2: a small chat at $0.20 restarts; its next turn alone costs $0.35. The tally shows the fresh start.
    t = totals(usage_run("r1", 0.20, tokens=1000, tally=1000), usage_run("r2", 0.35, tokens=1990, tally=2000))
    assert t["usd"] == pytest.approx(0.55) and t["tokens"] == 3000


def test_a_tally_that_drops_but_stays_large_is_not_a_restart():
    # Review #3: a reporting change (a model missing from the tally) must not re-add a $300 total.
    t = totals(usage_run("r1", 300.0, tokens=5_000_000, tally=800_000_000),
               usage_run("r2", 302.0, tokens=4_000_000, tally=700_000_000))
    assert t["usd"] == pytest.approx(302.0) and t["tokens"] == 804_000_000


def test_a_run_without_a_session_is_its_own_total_and_resets_nothing():
    # A sign-in failure records cost 0.0 with no session; the real session carries on around it.
    t = totals(usage_run("r1", 2.0, tally=100), usage_run("r2", 0.0, tokens=0, session=None),
               usage_run("r3", 2.5, tally=150))
    assert t["usd"] == pytest.approx(2.5) and t["tokens"] == 150


def test_a_damaged_spend_file_is_read_as_empty():
    store.write_json("spend.json", {"version": 1, "chats": {"c1": {"usd": "lots", "turns": [["not a time", 1.0, 5]]},
                                                            "c2": "nonsense"}, "failed": ["c3"]})
    snap = run_snapshot(FakeFeed([chat(id="c1")]), NOW)
    assert snap["ok"] is True and snap["characters"][0]["spend"]["usd"] == 0.0
    store.write_json("spend.json", ["not", "a", "dict"])
    assert run_snapshot(FakeFeed([chat(id="c1")]), NOW)["ok"] is True


def test_the_spend_file_is_written_only_when_something_changed(monkeypatch):
    writes = []
    real_write = store.write_json
    monkeypatch.setattr(store, "write_json", lambda name, value: (writes.append(name), real_write(name, value)))
    feed = FakeFeed([chat(id="c1")], usage={"c1": usage_body("c1", usage_run("r1", 1.0, tally=10))})
    run_snapshot(feed, NOW)
    run_snapshot(feed, NOW + timedelta(seconds=3))
    assert writes.count("spend.json") == 1


def test_the_recap_reads_chats_that_ran_while_the_office_was_closed():
    yesterday = NOW - timedelta(days=1)
    feed = FakeFeed([chat(id="c1", title="Night owl")],
                    usage={"c1": usage_body("c1", usage_run("r1", 2.0, tally=100, ended=yesterday))})
    body = dispatch({"method": "GET", "path": "progress", "query": {"tz": ["UTC"]}}, feed=feed, now=NOW)["body"]
    assert body["recap"]["spend"] == {"usd": 2.0, "tokens": 100, "top": {"title": "Night owl", "usd": 2.0}}


def test_a_chat_that_left_keeps_its_recent_turns_for_the_recap_then_goes():
    feed = FakeFeed(usage={"c1": usage_body("c1", usage_run("r1", 1.0, tally=10))})
    state = spend.refresh(feed, [office_chat("c1")], {}, NOW)
    state = spend.refresh(feed, [], state, NOW + timedelta(days=1))
    assert state["chats"]["c1"]["title"] == "Chat c1" and feed.usage_calls == ["c1"]
    state = spend.refresh(feed, [], state, NOW + timedelta(days=9))
    assert state["chats"] == {}


def test_a_renamed_chat_keeps_its_figures_under_the_new_name():
    feed = FakeFeed()
    state = spend.refresh(feed, [office_chat("c1")], {}, NOW)
    state = spend.refresh(feed, [chat(id="c1", title="New name")], state, NOW)
    assert state["chats"]["c1"]["title"] == "New name" and feed.usage_calls == ["c1"]


# --- Snapshot and recap -------------------------------------------------------------------

def test_the_snapshot_carries_each_chats_spend_and_todays_total():
    feed = FakeFeed([chat(id="c1", title="Budget"), chat(id="c2", title="New")],
                    usage={"c1": usage_body("c1", usage_run("r1", 2.0, tally=100, ended=NOW - timedelta(days=2)),
                                            usage_run("r2", 2.5, tally=150))})
    snap = dispatch({"method": "GET", "path": "snapshot", "query": {"tz": ["UTC"]}}, feed=feed, now=NOW)["body"]
    by_id = {c["id"]: c for c in snap["characters"]}
    assert by_id["c1"]["spend"] == {"usd": 2.5, "tokens": 150, "today_usd": 0.5, "today_tokens": 50}
    assert by_id["c2"]["spend"] == {"usd": 0.0, "tokens": 0, "today_usd": 0.0, "today_tokens": 0}
    assert snap["spend"] == {"today_usd": 0.5, "today_tokens": 50, "pending": 0}
    assert "office" not in snap and "level" not in by_id["c1"] and "xp_progress" not in by_id["c1"]
    assert store.read_json("spend.json", {})["chats"]["c1"]["usd"] == 2.5


def test_chats_not_read_yet_have_no_spend_and_are_counted_as_pending():
    snap = run_snapshot(FakeFeed([chat(id=f"c{i}") for i in range(8)]), NOW)
    unread = [c for c in snap["characters"] if c["spend"] is None]
    assert len(unread) == 8 - spend.READS_PER_SNAPSHOT and snap["spend"]["pending"] == len(unread)


def test_the_recap_counts_yesterdays_spend_and_its_biggest_spender():
    yesterday = NOW - timedelta(days=1)
    store.write_json("spend.json", {"version": 1, "chats": {
        "c1": {"title": "Budget", "usd": 9.0, "tokens": 900, "turns": [[iso(yesterday), 4.0, 400]]},
        "c2": {"title": "Trip", "usd": 2.0, "tokens": 200, "turns": [[iso(yesterday), 1.5, 150], [iso(NOW), 0.5, 50]]},
    }})
    feed = FakeFeed(runs=[run("r1", "c1", "completed", ended=yesterday)])
    body = dispatch({"method": "GET", "path": "progress", "query": {"tz": ["UTC"]}}, feed=feed, now=NOW)["body"]
    assert body["recap"]["turns"] == 1
    assert body["recap"]["spend"] == {"usd": 5.5, "tokens": 550, "top": {"title": "Budget", "usd": 4.0}}


def test_a_day_with_only_spend_still_gets_a_recap():
    yesterday = NOW - timedelta(days=1)
    store.write_json("spend.json", {"version": 1, "chats": {
        "c1": {"title": "Bot", "usd": 1.0, "tokens": 10, "turns": [[iso(yesterday), 1.0, 10]]}}})
    body = dispatch({"method": "GET", "path": "progress", "query": {"tz": ["UTC"]}}, feed=FakeFeed(), now=NOW)["body"]
    assert body["recap"]["turns"] == 0 and body["recap"]["spend"]["usd"] == 1.0
