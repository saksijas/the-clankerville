"""Floors (spec 2026-10-08 §5): 8 desks a floor, the busiest by state on floor 1, stable desks."""

from datetime import timedelta

from helpers import NOW, chat
from office import DESKS_PER_FLOOR, FLOORS, MAX_CHARACTERS, assign_floors


def working(cid, minutes_ago=0):
    return chat(id=cid, running=True, activity_at=NOW - timedelta(minutes=minutes_ago))


def idle(cid, minutes_ago=0):
    return chat(id=cid, activity_at=NOW - timedelta(minutes=minutes_ago))


def asking(cid, minutes_ago=0):
    return chat(id=cid, running=True, pending_question_id="q", activity_at=NOW - timedelta(minutes=minutes_ago))


def floors_of(pods):
    out = {}
    for chat_id, entry in pods.items():
        out.setdefault(entry["floor"], set()).add(chat_id)
    return out


def test_a_building_is_4_floors_of_8_desks():
    assert (FLOORS, DESKS_PER_FLOOR, MAX_CHARACTERS) == (4, 8, 32)


def test_eight_per_floor_busiest_first():
    chats = ([idle(f"i{n}", minutes_ago=n) for n in range(4)] + [working(f"w{n}", minutes_ago=n) for n in range(6)]
             + [asking(f"a{n}", minutes_ago=30) for n in range(2)])
    by_floor = floors_of(assign_floors(chats, {}))
    assert by_floor[1] == {"a0", "a1", "w0", "w1", "w2", "w3", "w4", "w5"}
    assert by_floor[2] == {"i0", "i1", "i2", "i3"}


def test_equal_ranks_keep_their_floor_when_activity_reshuffles():
    chats = [working(f"w{n}", minutes_ago=n) for n in range(10)]
    first = assign_floors(chats, {})
    assert floors_of(first)[2] == {"w8", "w9"}
    reshuffled = [working(f"w{n}", minutes_ago=10 - n) for n in range(10)]  # w8 and w9 are now the most recent
    assert floors_of(assign_floors(reshuffled, first)) == floors_of(first)


def test_a_busier_newcomer_takes_floor_1_from_an_idle_one():
    chats = [working(f"w{n}") for n in range(7)] + [idle("lazy")]
    first = assign_floors(chats, {})
    lazy_slot = first["lazy"]["slot"]
    second = assign_floors(chats + [working("new")], first)
    assert second["new"] == {"floor": 1, "slot": lazy_slot}  # the freed desk
    assert second["lazy"]["floor"] == 2
    assert all(second[f"w{n}"] == first[f"w{n}"] for n in range(7))


def test_desks_are_stable_within_a_floor():
    chats = [working(f"w{n}") for n in range(5)]
    first = assign_floors(chats, {})
    assert assign_floors(chats, first) == first
    fewer = assign_floors([c for c in chats if c["id"] != "w0"], first)
    assert all(fewer[f"w{n}"] == first[f"w{n}"] for n in range(1, 5))


def test_helpers_desk_map_moves_with_a_lead_that_keeps_its_desk():
    first = assign_floors([working("lead")], {})
    first["lead"]["helpers"] = {"h1": 0}
    assert assign_floors([working("lead")], first)["lead"]["helpers"] == {"h1": 0}


def test_old_desks_json_upgrades():
    previous = {"a": {"slot": 0, "last_seen": "2026-09-28T16:00:00"}, "b": {"slot": 12}, "c": {"floor": 9, "slot": 1}}
    pods = assign_floors([working("a"), working("b"), working("c")], previous)
    assert all(entry["floor"] == 1 and 0 <= entry["slot"] < DESKS_PER_FLOOR for entry in pods.values())
    assert len({entry["slot"] for entry in pods.values()}) == 3


def test_never_more_than_8_per_floor_and_every_desk_is_real():
    pods = assign_floors([working(f"w{n}", minutes_ago=n) for n in range(MAX_CHARACTERS)], {})
    for floor, members in floors_of(pods).items():
        assert 1 <= floor <= FLOORS and len(members) == DESKS_PER_FLOOR
        assert sorted(pods[c]["slot"] for c in members) == list(range(DESKS_PER_FLOOR))  # never the corner (slot 8)


def test_a_damaged_helper_desk_map_is_dropped_not_crashing():  # final review, Oct 8
    previous = {"lead": {"floor": 1, "slot": 0, "helpers": {"h1": 0, "h2": "x", "h3": 9, "h4": True}}}
    pods = assign_floors([working("lead")], previous)
    assert pods["lead"]["helpers"] == {"h1": 0}
