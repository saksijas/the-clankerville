from datetime import timedelta

from helpers import NOW, FakeFeed, app, d, fresh_state, iso, run, terminal
from progress import catch_up, check_achievements, recap_for
from service import dispatch


def test_first_team_needs_overlap():
    apart = [d("a", "c1", "completed", started=iso(NOW - timedelta(hours=2)), ended=iso(NOW - timedelta(hours=1))),
             d("b", "c1", "completed", started=iso(NOW - timedelta(minutes=30)), ended=iso(NOW))]
    assert "first_team" not in check_achievements(fresh_state(), delegations=apart, working_now=0, now=NOW)
    together = apart[:1] + [d("b", "c1", "running", started=iso(NOW - timedelta(hours=1, minutes=30)))]
    assert "first_team" in check_achievements(fresh_state(), delegations=together, working_now=0, now=NOW)


def test_full_house_and_once_only():
    state = fresh_state()
    assert check_achievements(state, delegations=[], working_now=5, now=NOW) == ["full_house"]
    assert check_achievements(state, delegations=[], working_now=6, now=NOW) == []


def test_clean_sweep():
    ok = [d(i, "c1", "completed", root="r1") for i in ("a", "b", "c")]
    assert "clean_sweep" in check_achievements(fresh_state(), delegations=ok, working_now=0, now=NOW)
    bad = ok[:2] + [d("c", "c1", "failed", root="r1")]
    assert "clean_sweep" not in check_achievements(fresh_state(), delegations=bad, working_now=0, now=NOW)


def test_on_a_roll_needs_five_days():
    state = fresh_state(days={f"2026-09-{n:02d}": {"turns": 1} for n in range(23, 28)})
    assert "on_a_roll" in check_achievements(state, delegations=[], working_now=0, now=NOW)
    four = fresh_state(days={f"2026-09-{n:02d}": {"turns": 1} for n in (23, 24, 26, 27)})
    assert "on_a_roll" not in check_achievements(four, delegations=[], working_now=0, now=NOW)


def test_recap_for_fixture_day():
    state = fresh_state(days={"2026-09-27": {"turns": 12, "helpers_done": 4, "helpers_failed": 1, "apps": 1,
                                            "level_ups": [{"chat_id": "c1", "level": 3}]}},
                        chats={"c1": {"xp": 160, "title": "Budget sheet", "day_xp": {"2026-09-27": 75}}},
                        achievements=[{"id": "shipped_it", "at": "2026-09-27T15:00:00-05:00"}])
    assert recap_for(state, "2026-09-27") == {"turns": 12, "helpers_done": 4, "helpers_failed": 1, "helpers_stopped": 0, "apps": 1,
        "level_ups": [{"chat_id": "c1", "level": 3}], "achievements": ["shipped_it"],
        "busiest": {"chat_id": "c1", "title": "Budget sheet", "xp": 75}}
    assert recap_for(state, "2026-09-26") is None


def test_shipped_it_unlocks_from_a_real_new_app_award():
    result = catch_up(FakeFeed(apps=[app(1, "c1", created=NOW - timedelta(hours=1))]), NOW)
    assert [a["id"] for a in result["achievements"]] == ["shipped_it"]


def test_progress_route_carries_achievements_and_yesterdays_recap():
    feed = FakeFeed(runs=[run("r1", "c1", "completed", ended=NOW - timedelta(days=1))])
    body = dispatch({"method": "GET", "path": "progress", "query": {"working_now": ["5"]}}, feed=feed, now=NOW)["body"]
    assert "full_house" in [a["id"] for a in body["achievements"]]
    assert body["recap"]["turns"] == 1 and body["recap"]["busiest"]["chat_id"] == "c1"


def test_stopped_helpers_are_counted_for_the_recap_without_xp():
    day_before = NOW - timedelta(days=1)
    feed = FakeFeed(helpers=[terminal("a1", "c1", "stopped", when=day_before), terminal("a2", "c1", "done", when=day_before)])
    result = catch_up(feed, NOW)
    assert (result["recap"]["helpers_stopped"], result["recap"]["helpers_done"]) == (1, 1)
    assert result["chats"]["c1"]["xp"] == 5


def test_a_day_saved_before_stopped_helpers_were_counted_still_counts_one():
    import store
    from progress import new_state
    old_day = {"turns": 1, "helpers_done": 0, "helpers_failed": 0, "apps": 0, "level_ups": []}
    store.write_json("progress.json", {**new_state(), "days": {"2026-09-27": old_day}})
    result = catch_up(FakeFeed(helpers=[terminal("a1", "c1", "stopped", when=NOW - timedelta(days=1))]), NOW)
    assert result["recap"]["helpers_stopped"] == 1 and result["recap"]["turns"] == 1
