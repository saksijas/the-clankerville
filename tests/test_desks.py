from datetime import timedelta

from helpers import NOW, iso
from office import COFFEE_SLOT, assign_pods, floor_depth, look_for, short_name


def test_coffee_slot_is_never_assigned():
    pods = assign_pods([f"c{i}" for i in range(10)], {}, NOW)
    assert COFFEE_SLOT not in {p["slot"] for p in pods.values()}


def test_floor_grows_by_pod_rows():
    assert floor_depth(7) == 9 and floor_depth(9) == 12


def test_look_is_deterministic():
    assert look_for("abc") == look_for("abc")
    assert set(look_for("abc")) == {"hair", "shirt", "skin"}


def test_pods_are_freed_after_a_day_unseen():
    previous = {"old": {"slot": 0, "last_seen": iso(NOW - timedelta(hours=25))},
                "recent": {"slot": 1, "last_seen": iso(NOW - timedelta(hours=2))}}
    pods = assign_pods(["new"], previous, NOW)
    assert pods["new"]["slot"] == 0 and pods["recent"]["slot"] == 1 and "old" not in pods


def test_short_name_cuts_on_a_word_boundary():
    assert short_name("Agent office gamification brainstorm") == "Agent office"
    assert short_name("Supercalifragilisticexpialidocious") == "Supercalifragil…"
    assert short_name("   ") == "Untitled chat" and short_name(None) == "Untitled chat"


def test_short_name_drops_trailing_punctuation():
    assert short_name("Review-loop: Slack-triggered PR review") == "Review-loop"
    assert short_name("Fix: tap highlight") == "Fix: tap"


def test_a_new_chat_reuses_an_absent_chats_desk_instead_of_growing_the_room():
    previous = {f"away{i}": {"slot": slot, "last_seen": iso(NOW - timedelta(hours=1))}
                for i, slot in enumerate([0, 1, 2, 3, 4, 5, 6, 7])}
    pods = assign_pods(["new1", "new2"], previous, NOW)
    assert (pods["new1"]["slot"], pods["new2"]["slot"]) == (0, 1)
    assert floor_depth(max(pods[c]["slot"] for c in ("new1", "new2"))) == 9


def test_an_absent_chat_keeps_its_desk_while_there_is_room():
    previous = {"c0": {"slot": 0, "last_seen": iso(NOW)}, "c1": {"slot": 1, "last_seen": iso(NOW)},
                "away": {"slot": 2, "last_seen": iso(NOW - timedelta(hours=1))}}
    pods = assign_pods(["c0", "c1", "new"], previous, NOW)
    assert pods["away"]["slot"] == 2 and pods["new"]["slot"] == 3


def test_last_seen_is_refreshed_every_ten_minutes_not_every_check():
    first = assign_pods(["c1"], {}, NOW)
    assert assign_pods(["c1"], first, NOW + timedelta(seconds=3)) == first
    later = assign_pods(["c1"], first, NOW + timedelta(minutes=11))
    assert later["c1"]["last_seen"] == (NOW + timedelta(minutes=11)).isoformat()
