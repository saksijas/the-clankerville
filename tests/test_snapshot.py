from datetime import timedelta

from feed import FeedError
from helpers import ANY_STR, NOW, FakeClock, FakeFeed, RaisingFeed, chat, d, detail, run_snapshot
from service import dispatch


def test_caps_and_stable_desks():  # Review Focus 5
    chats = [chat(id=f"c{i}", running=True) for i in range(40)]
    helpers = [d(f"h{i}", "c0") for i in range(8)]
    snap1 = run_snapshot(FakeFeed(chats, helpers), NOW)
    snap2 = run_snapshot(FakeFeed(chats, helpers), NOW + timedelta(seconds=3))
    leads = [c for c in snap1["characters"] if c["kind"] == "chat"]
    assert len(leads) == 32  # 4 floors of 8
    assert next(c for c in leads if c["id"] == "c0")["overflow"] == 3
    assert len([c for c in snap1["characters"] if c["kind"] == "helper"]) == 5
    assert {c["id"]: c["desk"] for c in snap1["characters"]} == {c["id"]: c["desk"] for c in snap2["characters"]}


def test_snapshot_route_contract_and_feed_errors():
    body = dispatch({"method": "GET", "path": "snapshot"}, feed=FakeFeed([chat(id="c1", running=True)], []), now=NOW)["body"]
    assert body["ok"] is True and set(body["counts"]) == {"working", "needs_you", "error", "watching", "on_break"}
    assert body["room"] == {"width": 13, "depth": 11, "floors": 4}  # pods plus the lobby, 4 floors
    err = dispatch({"method": "GET", "path": "snapshot"}, feed=RaisingFeed("no_key"), now=NOW)
    assert err["status"] == 200 and err["body"] == {"ok": False, "error": {"code": "no_key", "message": ANY_STR}}


def test_working_chat_carries_step_and_queued_count():
    read_block = {"type": "tool", "tool": "Read", "input": "/x/theme.css", "status": "running", "tool_use_id": "t1"}
    feed = FakeFeed([chat(id="busy", running=True), chat(id="idle", waiting=True)], [],
                    details={"busy": detail("busy", [read_block], pending=1)})
    snap = run_snapshot(feed, NOW)
    by_id = {c["id"]: c for c in snap["characters"]}
    assert by_id["busy"]["step"] == "Reading theme.css" and by_id["busy"]["queued"] == 1
    assert by_id["idle"]["state"] == "watching" and by_id["idle"]["queued"] == 0 and "step" not in by_id["idle"]
    assert feed.detail_calls == ["busy"]
    assert snap["counts"] == {"working": 1, "needs_you": 0, "error": 0, "watching": 1, "on_break": 0}


def test_a_chat_that_vanished_does_not_break_the_snapshot():
    feed = FakeFeed([chat(id="gone", running=True), chat(id="here", running=True)], [],
                    details={"gone": FeedError("not_found", "gone")})
    snap = run_snapshot(feed, NOW)
    assert snap["ok"] is True
    assert {c["id"]: c["step"] for c in snap["characters"]} == {"gone": "Working", "here": "Thinking"}


def test_the_time_budget_covers_the_whole_snapshot(monkeypatch):
    import service
    clock = FakeClock()
    monkeypatch.setattr(service.time, "monotonic", clock)

    class SlowChatList(FakeFeed):
        def list_chats(self):
            clock.advance(service.SNAPSHOT_BUDGET_SECONDS)  # a slow Möbius used up the whole budget
            return super().list_chats()

    feed = SlowChatList([chat(id="busy", running=True)], [])
    snap = run_snapshot(feed, NOW)
    assert snap["ok"] is True and feed.detail_calls == [] and snap["characters"][0]["step"] == "Working"


def test_the_budget_leaves_room_under_the_8_second_ceiling():
    import service
    assert service.SNAPSHOT_BUDGET_SECONDS <= 7.5


def test_a_slow_step_lookup_shows_working_instead_of_failing_the_office():
    slow = FeedError("mobius_unavailable", "Möbius didn't answer in time.")
    feed = FakeFeed([chat(id="slow", running=True), chat(id="fine", running=True)], [], details={"slow": slow})
    snap = run_snapshot(feed, NOW)
    assert snap["ok"] is True and {c["id"]: c["step"] for c in snap["characters"]} == {"slow": "Working", "fine": "Thinking"}


def test_key_trouble_during_a_step_lookup_still_reaches_the_office():
    feed = FakeFeed([chat(id="c1", running=True)], [], details={"c1": FeedError("key_rejected", "rejected")})
    assert run_snapshot(feed, NOW)["error"]["code"] == "key_rejected"


def test_helpers_keep_their_desks_when_a_teammate_leaves():
    lead = [chat(id="lead", running=True)]
    team = [d(f"h{i}", "lead", created=f"2026-09-28T16:0{i}:00") for i in range(1, 4)]
    helper_desks = lambda snap: {c["id"]: c["desk"] for c in snap["characters"] if c["kind"] == "helper"}
    first = helper_desks(run_snapshot(FakeFeed(lead, team), NOW))
    second = helper_desks(run_snapshot(FakeFeed(lead, [team[0], team[2]]), NOW + timedelta(seconds=3)))
    assert second == {"h1": first["h1"], "h3": first["h3"]}
    third = helper_desks(run_snapshot(FakeFeed(lead, [team[0], team[2], d("h4", "lead", created="2026-09-28T16:09:00")]),
                                      NOW + timedelta(seconds=6)))
    assert third["h4"] == first["h2"]  # a newcomer takes the free desk


def test_the_desk_map_is_saved_only_when_it_changes(monkeypatch):
    import store
    writes = []
    real_write = store.write_json
    monkeypatch.setattr(store, "write_json", lambda name, data: (writes.append(name), real_write(name, data)))
    feed = FakeFeed([chat(id="c1", running=True)], [])
    run_snapshot(feed, NOW)
    run_snapshot(feed, NOW + timedelta(seconds=3))
    assert writes.count("desks.json") == 1


def test_characters_carry_the_timer_and_question_behind_their_state():
    feed = FakeFeed([chat(id="busy", running=True, waiting=True),
                     chat(id="ask", running=True, owner_input_kind="question", pending_question_id="q1")], [],
                    details={"ask": detail("ask", pending=2)})
    by_id = {c["id"]: c for c in run_snapshot(feed, NOW)["characters"]}
    assert by_id["busy"]["state"] == "working" and by_id["busy"]["waiting"] is True and by_id["busy"]["asking"] is False
    assert by_id["ask"]["state"] == "needs_you" and by_id["ask"]["asking"] is True and by_id["ask"]["queued"] == 2
    assert "step" not in by_id["ask"] and "ask" in feed.detail_calls


def test_snapshot_carries_floors_room_and_each_characters_floor():
    # Floors (spec 2026-10-08 §6): a character's floor, the room with its lobby, and each floor's egg and counts.
    chats = [chat(id=f"w{i}", running=True) for i in range(9)]
    team = [d("h1", "w0")]
    snap = run_snapshot(FakeFeed(chats, team), NOW)
    assert snap["room"] == {"width": 13, "depth": 11, "floors": 4}
    assert [f["floor"] for f in snap["floors"]] == [1, 2, 3, 4]
    assert [f["egg"] for f in snap["floors"]] == ["internet", "watercooler", "phone", "fire"]
    by_id = {c["id"]: c for c in snap["characters"]}
    assert all(1 <= c["floor"] <= 4 for c in snap["characters"])
    assert by_id["h1"]["floor"] == by_id["w0"]["floor"]
    leads_on = lambda n: [c for c in snap["characters"] if c["kind"] == "chat" and c["floor"] == n]
    assert len(leads_on(1)) == 8 and len(leads_on(2)) == 1
    assert snap["floors"][0]["counts"]["working"] == 8 and snap["floors"][1]["counts"]["working"] == 1
    assert sum(f["counts"]["working"] for f in snap["floors"]) == snap["counts"]["working"]
