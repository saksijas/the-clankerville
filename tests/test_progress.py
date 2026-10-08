from datetime import timedelta

import pytest

import store
from feed import FeedError
from helpers import NOW, FakeClock, FakeFeed, app, chat, run, terminal
from progress import catch_up, level_for
from service import dispatch


@pytest.mark.parametrize("xp,expected", [(0, (1, 0, 50)), (49, (1, 49, 50)), (50, (2, 0, 100)),
                                         (150, (3, 0, 150)), (300, (4, 0, 200)), (500, (5, 0, 250))])
def test_level_curve(xp, expected):
    assert level_for(xp) == expected


def test_outcomes_only():
    feed = FakeFeed(runs=[run("r1", "c1", "completed"), run("r2", "c1", "failed"), run("r3", "c1", "stopped")],
                    helpers=[terminal("a1", "c1", "done"), terminal("a2", "c1", "failed")],
                    apps=[app(1, "c1", created=NOW - timedelta(hours=1))])
    p = catch_up(feed, NOW)
    assert p["chats"]["c1"]["xp"] == 10 + 5 + 25


def test_replay_is_idempotent():  # Review Focus 4
    feed = FakeFeed(runs=[run("r1", "c1", "completed")])
    first = catch_up(feed, NOW)
    ledger = store.read_json("ledger.json", {})
    ledger["cursors"] = {"after_id": 0, "runs_after_id": 0}
    store.write_json("ledger.json", ledger)  # simulates a lost cursor write or a second tab
    assert catch_up(feed, NOW)["chats"]["c1"]["xp"] == first["chats"]["c1"]["xp"] == 10


def test_app_update_once_per_day():
    feed = FakeFeed(apps=[app(1, "c1", created=NOW - timedelta(days=30), updated=NOW - timedelta(minutes=5))])
    catch_up(feed, NOW)
    feed.touch_app(1, NOW - timedelta(minutes=1))
    assert catch_up(feed, NOW)["chats"]["c1"]["xp"] == 5


def test_backfill_window():
    feed = FakeFeed(runs=[run("old", "c1", "completed", ended=NOW - timedelta(days=8)),
                          run("new", "c1", "completed", ended=NOW - timedelta(days=6))])
    assert catch_up(feed, NOW)["chats"]["c1"]["xp"] == 10


def test_route_shape():
    body = dispatch({"method": "GET", "path": "progress"}, feed=FakeFeed(), now=NOW)["body"]
    assert body["ok"] is True and body["office"] == {"level": 1, "xp": 0, "level_start_xp": 0, "next_level_xp": 50}


def test_paging_follows_has_more():
    feed = FakeFeed(runs=[run(f"r{i}", "c1", "completed") for i in range(3)], page_size=1)
    assert catch_up(feed, NOW)["chats"]["c1"]["xp"] == 30 and feed.lifecycle_calls == 3


def test_chats_run_by_apps_earn_no_xp():
    feed = FakeFeed(chats=[chat(id="bg", created_by_app_id=4)], runs=[run("r1", "bg", "completed")])
    assert "bg" not in catch_up(feed, NOW)["chats"]


def test_lost_cursor_never_counts_history_from_before_the_office():
    feed = FakeFeed(runs=[run("ancient", "c1", "completed", ended=NOW - timedelta(days=20))])
    catch_up(feed, NOW)
    ledger = store.read_json("ledger.json", {})
    ledger["cursors"] = {"after_id": 0, "runs_after_id": 0}
    store.write_json("ledger.json", ledger)
    assert "c1" not in catch_up(feed, NOW + timedelta(days=1))["chats"]


def test_level_up_is_recorded_for_the_day():
    feed = FakeFeed(runs=[run(f"r{i}", "c1", "completed") for i in range(5)])
    catch_up(feed, NOW)
    days = store.read_json("progress.json", {})["days"]
    assert [lu for day in days.values() for lu in day["level_ups"]] == [{"chat_id": "c1", "level": 2}]


def test_days_follow_the_owners_time_zone():
    evening_in_chicago = NOW.replace(hour=2) - timedelta(days=0)  # 2026-09-28 02:00 UTC = 21:00 on the 27th in Chicago
    feed = FakeFeed(runs=[run("r1", "c1", "completed", ended=evening_in_chicago)])
    result = catch_up(feed, NOW, tz="America/Chicago")
    assert "2026-09-27" in store.read_json("progress.json", {})["days"]
    assert result["recap"]["turns"] == 1


def test_office_level_bar_starts_at_the_level_floor():
    feed = FakeFeed(runs=[run(f"r{i}", "c1", "completed") for i in range(22)])  # 220 XP: Lv 3 spans 150..300
    office = catch_up(feed, NOW)["office"]
    assert office == {"level": 3, "xp": 220, "level_start_xp": 150, "next_level_xp": 300}


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
    first = catch_up(feed, NOW, history_seconds=2.5, clock=clock)
    assert first["chats"]["c1"]["xp"] == 30  # three pages fit the budget
    second = catch_up(feed, NOW, history_seconds=10, clock=clock)
    assert second["chats"]["c1"]["xp"] == 50  # the rest, once, from the saved cursors


def test_a_page_that_fails_later_keeps_what_was_read():
    class FailsOnSecondPage(FakeFeed):
        def lifecycle(self, after_id, runs_after_id):
            if self.lifecycle_calls >= 1:
                self.lifecycle_calls += 1
                raise FeedError("mobius_unavailable", "Möbius didn't answer in time.")
            return super().lifecycle(after_id, runs_after_id)

    feed = FailsOnSecondPage(runs=[run(f"r{i}", "c1", "completed") for i in range(3)], page_size=1)
    assert catch_up(feed, NOW)["chats"]["c1"]["xp"] == 10
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


def test_a_gone_chats_title_is_forgotten_once_its_recap_days_are_over():
    # Titles of deleted chats must not stay on disk forever (final review, Oct 7).
    feed = FakeFeed(chats=[chat(id="c1", title="Secret project")], runs=[run("r1", "c1", "completed")])
    catch_up(feed, NOW)
    assert store.read_json("progress.json", {})["chats"]["c1"]["title"] == "Secret project"
    feed.chats = []  # the chat was deleted
    catch_up(feed, NOW + timedelta(days=1))
    assert store.read_json("progress.json", {})["chats"]["c1"]["title"] == "Secret project"  # yesterday's recap
    catch_up(feed, NOW + timedelta(days=61))
    kept = store.read_json("progress.json", {})["chats"]["c1"]
    assert kept["title"] is None and kept["xp"] == 10
