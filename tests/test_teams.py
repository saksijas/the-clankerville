from datetime import timedelta

from helpers import NOW, d, iso
from office import build_teams


def test_membership_and_nesting():
    teams = build_teams([d("h1", "c1"), d("h2", "cc-h1"), d("x", "not-in-office")], {"c1"}, NOW)
    assert [(h["id"], h["depth"], h["parent_id"]) for h in teams["c1"]] == [("h1", 1, None), ("h2", 2, "h1")]


def test_terminal_linger_and_exit():
    fresh, stale = iso(NOW - timedelta(seconds=30)), iso(NOW - timedelta(seconds=90))
    teams = build_teams([d("a", "c1", "completed", ended=fresh), d("b", "c1", "completed", ended=stale),
                         d("c", "c1", "cancelled", ended=fresh), d("e", "c1", "needs_review", ended=fresh)], {"c1"}, NOW)
    assert {h["id"]: h["pose"] for h in teams["c1"]} == {"a": "done", "e": "failed"}


def test_names_are_scrubbed_and_capped():
    h = build_teams([d("h1", "c1", task="implement-task-7-with-a-very-long-name")], {"c1"}, NOW)["c1"][0]
    assert len(h["name"]) <= 24 and h["dismissable"] is True


def test_third_level_helpers_are_dropped_and_paused_is_on_hold():
    teams = build_teams([d("h1", "c1", "paused"), d("h2", "cc-h1"), d("h3", "cc-h2")], {"c1"}, NOW)
    assert [(h["id"], h["pose"]) for h in teams["c1"]] == [("h1", "on_hold"), ("h2", "busy")]
