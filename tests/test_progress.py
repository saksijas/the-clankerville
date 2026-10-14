from datetime import timedelta

import pytest

import store
from feed import FeedError
from helpers import NOW, FakeClock, FakeFeed, app, chat, run, terminal
from progress import catch_up
from service import dispatch


def counted(field="turns"):
    """How many outcomes of one kind progress.json holds, across its days."""
    return sum(day.get(field, 0) for day in store.read_json("progress.json", {}).get("days", {}).values())


def test_outcomes_only():
    feed = FakeFeed(runs=[run("r1", "c1", "completed"), run("r2", "c1", "failed"), run("r3", "c1", "stopped")],
                    helpers=[terminal("a1", "c1", "done"), terminal("a2", "c1", "failed")],
                    apps=[app(1, "c1", created=NOW - timedelta(hours=1))])
    catch_up(feed, NOW)
    assert [counted(f) for f in ("turns", "helpers_done", "helpers_failed", "apps")] == [1, 1, 1, 1]


def test_replay_is_idempotent():  # Review Focus 4
    feed = FakeFeed(runs=[run("r1", "c1", "completed")])
    first = catch_up(feed, NOW)
    ledger = store.read_json("ledger.json", {})
    ledger["cursors"] = {"after_id": 0, "runs_after_id": 0}
    store.write_json("ledger.json", ledger)  # simulates a lost cursor write or a second tab
    catch_up(feed, NOW)
    assert counted() == 1 and first["recap"] is None


def test_app_update_once_per_day():
    feed = FakeFeed(apps=[app(1, "c1", created=NOW - timedelta(days=30), updated=NOW - timedelta(minutes=5))])
    catch_up(feed, NOW)
    feed.touch_app(1, NOW - timedelta(minutes=1))
    catch_up(feed, NOW)
    assert counted("apps") == 1


def test_backfill_window():
    feed = FakeFeed(runs=[run("old", "c1", "completed", ended=NOW - timedelta(days=8)),
                          run("new", "c1", "completed", ended=NOW - timedelta(days=6))])
    catch_up(feed, NOW)
    assert counted() == 1


def test_route_shape():
    body = dispatch({"method": "GET", "path": "progress"}, feed=FakeFeed(), now=NOW)["body"]
    assert body == {"ok": True, "achievements": [], "recap": None}


def test_paging_follows_has_more():
    feed = FakeFeed(runs=[run(f"r{i}", "c1", "completed") for i in range(3)], page_size=1)
    catch_up(feed, NOW)
    assert counted() == 3 and feed.lifecycle_calls == 3


def test_chats_run_by_apps_are_not_counted():
    feed = FakeFeed(chats=[chat(id="bg", created_by_app_id=4)], runs=[run("r1", "bg", "completed")])
    catch_up(feed, NOW)
    assert counted() == 0


def test_lost_cursor_never_counts_history_from_before_the_office():
    feed = FakeFeed(runs=[run("ancient", "c1", "completed", ended=NOW - timedelta(days=20))])
    catch_up(feed, NOW)
    ledger = store.read_json("ledger.json", {})
    ledger["cursors"] = {"after_id": 0, "runs_after_id": 0}
    store.write_json("ledger.json", ledger)
    catch_up(feed, NOW + timedelta(days=1))
    assert counted() == 0


def test_days_follow_the_owners_time_zone():
    evening_in_chicago = NOW.replace(hour=2) - timedelta(days=0)  # 2026-09-28 02:00 UTC = 21:00 on the 27th in Chicago
    feed = FakeFeed(runs=[run("r1", "c1", "completed", ended=evening_in_chicago)])
    result = catch_up(feed, NOW, tz="America/Chicago")
    assert "2026-09-27" in store.read_json("progress.json", {})["days"]
    assert result["recap"]["turns"] == 1


def test_a_page_that_does_not_move_forward_ends_the_reading():
    class StuckFeed(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            page = super().lifecycle(after_id, runs_after_id)
            return {**page, "next_after_id": after_id, "next_runs_after_id": runs_after_id, "has_more": True}

    feed = StuckFeed(runs=[run("r1", "c1", "completed")])
    catch_up(feed, NOW)
    assert feed.lifecycle_calls == 1


def test_reading_stops_at_the_time_budget_and_resumes_next_time():
    clock = FakeClock()

    class SlowPages(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            clock.advance(1.0)
            return super().lifecycle(after_id, runs_after_id)

    feed = SlowPages(runs=[run(f"r{i}", "c1", "completed") for i in range(5)], page_size=1)
    catch_up(feed, NOW, history_seconds=2.5, clock=clock)
    assert counted() == 3  # three pages fit the budget
    catch_up(feed, NOW, history_seconds=10, clock=clock)
    assert counted() == 5  # the rest, once, from the saved cursors


def test_a_page_that_fails_later_keeps_what_was_read():
    class FailsOnSecondPage(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            if self.lifecycle_calls >= 1:
                self.lifecycle_calls += 1
                raise FeedError("mobius_unavailable", "Möbius didn't answer in time.")
            return super().lifecycle(after_id, runs_after_id)

    feed = FailsOnSecondPage(runs=[run(f"r{i}", "c1", "completed") for i in range(3)], page_size=1)
    catch_up(feed, NOW)
    assert counted() == 1
    assert store.read_json("ledger.json", {})["cursors"]["runs_after_id"] == 1


def test_a_first_page_failure_is_still_reported():
    class Down(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            raise FeedError("mobius_unavailable", "down")

    with pytest.raises(FeedError):
        catch_up(Down(runs=[run("r1", "c1", "completed")]), NOW)


def test_the_progress_route_reads_history_within_its_budget(monkeypatch):
    import service
    clock = FakeClock()
    monkeypatch.setattr(service.time, "monotonic", clock)

    class SlowPages(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            clock.advance(3.0)
            return super().lifecycle(after_id, runs_after_id)

    feed = SlowPages(runs=[run(f"r{i}", "c1", "completed") for i in range(10)], page_size=1)
    body = dispatch({"method": "GET", "path": "progress"}, feed=feed, now=NOW)["body"]
    assert body["ok"] is True and feed.lifecycle_calls == 3  # 8 s of history reading at 3 s a page
    assert service.PROGRESS_BUDGET_SECONDS < 15  # Möbius ends a service request at 15 s


def test_the_history_budget_starts_when_reading_starts(monkeypatch):
    import service
    clock = FakeClock()
    monkeypatch.setattr(service.time, "monotonic", clock)

    class SlowLists(FakeFeed):
        def list_apps(self):
            clock.advance(6.0)  # slow lists must not starve the history reading
            return super().list_apps()

        def lifecycle(self, after_id, runs_after_id):
            clock.advance(1.0)
            return super().lifecycle(after_id, runs_after_id)

    feed = SlowLists(runs=[run(f"r{i}", "c1", "completed") for i in range(20)], page_size=1)
    dispatch({"method": "GET", "path": "progress"}, feed=feed, now=NOW)
    assert feed.lifecycle_calls == 8


def test_an_office_saved_with_xp_drops_it_and_keeps_its_count_keys():
    # XP and levels left on 2026-10-13. Their old file still stops a recount, and no titles stay on disk.
    store.write_json("progress.json", {
        "version": 1, "office": {"xp": 220}, "achievements": [], "days": {},
        "chats": {"c1": {"xp": 10, "title": "Secret project", "day_xp": {"2026-09-28": 10}}},
        "awarded": {"run:r1": "2026-09-28"},
    })
    feed = FakeFeed(chats=[chat(id="c1", title="Secret project")], runs=[run("r1", "c1", "completed")])
    catch_up(feed, NOW)
    saved = store.read_json("progress.json", {})
    assert set(saved) == {"version", "achievements", "days", "counted"}
    assert saved["counted"] == {"run:r1": "2026-09-28"} and counted() == 0
