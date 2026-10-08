"""Levels and the day's counters, derived only from finished work.

XP comes from outcomes Möbius records durably: completed turns, helpers that
came back done, apps a chat shipped. Busyness never counts. Every award has a
stable key stored beside the XP it granted (`progress.json`), so re-reading the
same history (a lost cursor, a retry, two open tabs) can never count twice.
Cursors and the seen-apps map (`ledger.json`) are only a reading optimization.
"""

import re
import time
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import store
from feed import FeedError
from office import parse_time

XP_TURN = 10
XP_HELPER = 5
XP_NEW_APP = 25
XP_APP_UPDATE = 5
BACKFILL = timedelta(days=7)
KEEP_KEYS = timedelta(days=30)
KEEP_DAYS = timedelta(days=60)

_COUNTER = {"turn": "turns", "helper": "helpers_done", "new_app": "apps", "app_update": "apps"}


def level_for(xp):
    """(level, xp into this level, xp this level needs); level n → n+1 costs 50 × n."""
    level, floor = 1, 0
    while xp >= floor + 50 * level:
        floor += 50 * level
        level += 1
    return level, xp - floor, 50 * level


def owner_zone(name):
    """The owner's IANA time zone (sent by the office), or None when unknown."""
    try:
        return ZoneInfo(name) if name else None
    except (ZoneInfoNotFoundError, ValueError):
        return None


def local_day(moment, tz=None):
    """The owner's calendar day for a moment. The server may run on UTC, so the
    office passes the browser's zone; without one, the server's zone is used."""
    zone = owner_zone(tz)
    return (moment.astimezone(zone) if zone else moment.astimezone()).date().isoformat()


def empty_day():
    return {"turns": 0, "helpers_done": 0, "helpers_failed": 0, "helpers_stopped": 0, "apps": 0, "level_ups": []}


def new_state():
    return {"version": 1, "office": {"xp": 0}, "chats": {}, "achievements": [], "days": {}, "awarded": {}}


def load_state(saved=None):
    state = new_state()
    state.update(store.read_json("progress.json", {}) if saved is None else saved)
    return state


def award(state, key, chat_id, xp, day, kind):
    """Grant `xp` to a chat once per `key`; returns False when already granted."""
    if key in state["awarded"]:
        return False
    state["awarded"][key] = day
    chat = state["chats"].setdefault(chat_id, {"xp": 0, "title": None, "day_xp": {}})
    before = level_for(chat["xp"])[0]
    chat["xp"] += xp
    chat["day_xp"][day] = chat["day_xp"].get(day, 0) + xp
    state["office"]["xp"] += xp
    counters = state["days"].setdefault(day, empty_day())
    counters[_COUNTER[kind]] += 1
    after = level_for(chat["xp"])[0]
    if after > before:
        counters["level_ups"].append({"chat_id": chat_id, "level": after})
    return True


def note(state, key, day, field):
    """Count an outcome that earns no XP (a helper that failed or was stopped), once per `key`."""
    if key in state["awarded"]:
        return False
    state["awarded"][key] = day
    counters = state["days"].setdefault(day, empty_day())
    counters[field] = counters.get(field, 0) + 1  # days saved before a counter existed lack it
    return True


def summary(state):
    office_xp = state["office"]["xp"]
    level, into, need = level_for(office_xp)
    chats = {}
    for chat_id, chat in state["chats"].items():
        chat_level, chat_into, chat_need = level_for(chat["xp"])
        chats[chat_id] = {"xp": chat["xp"], "level": chat_level,
                          "xp_progress": round(chat_into / chat_need, 3), "title": chat.get("title")}
    start = office_xp - into
    return {"office": {"level": level, "xp": office_xp, "level_start_xp": start, "next_level_xp": start + need}, "chats": chats}


def office_view(saved):
    """Read-only progress for the snapshot: office level plus each chat's level."""
    view = summary(load_state(saved))
    return {**view["office"], "chats": view["chats"]}


def _root_chat(chat_id, parent_of):
    seen = set()
    while chat_id in parent_of and chat_id not in seen:
        seen.add(chat_id)
        chat_id = parent_of[chat_id]
    return chat_id


def _prune(state, now, tz=None):
    oldest_key = local_day(now - KEEP_KEYS, tz)
    oldest_day = local_day(now - KEEP_DAYS, tz)
    state["awarded"] = {key: day for key, day in state["awarded"].items() if day >= oldest_key}
    state["days"] = {day: c for day, c in state["days"].items() if day >= oldest_day}
    for chat in state["chats"].values():
        chat["day_xp"] = {day: xp for day, xp in chat.get("day_xp", {}).items() if day >= oldest_day}


ACHIEVEMENTS = ("first_team", "shipped_it", "full_house", "clean_sweep", "on_a_roll")
FULL_HOUSE = 5
CLEAN_SWEEP_HELPERS = 3
ROLL_DAYS = 5
_NEW_APP_KEY = re.compile(r"^app:.+:created$")


def _helpers_overlapped(delegations, now):
    """True when two helpers of one chat were ever out at the same time."""
    spans_by_chat = {}
    for helper in delegations:
        start = parse_time(helper.get("started_at"))
        if start is not None:
            end = parse_time(helper.get("ended_at")) or now
            spans_by_chat.setdefault(helper.get("parent_chat_id"), []).append((start, end))
    for spans in spans_by_chat.values():
        spans.sort()
        latest_end = None
        for start, end in spans:
            if latest_end is not None and start < latest_end:
                return True
            latest_end = end if latest_end is None else max(latest_end, end)
    return False


def _clean_sweep(delegations):
    statuses_by_run = {}
    for helper in delegations:
        if helper.get("parent_root_run_id"):
            statuses_by_run.setdefault(helper["parent_root_run_id"], []).append(helper.get("status"))
    return any(len(statuses) >= CLEAN_SWEEP_HELPERS and all(s == "completed" for s in statuses)
               for statuses in statuses_by_run.values())


def _longest_streak(state):
    active = sorted(date.fromisoformat(day) for day, counters in state["days"].items() if counters.get("turns", 0) >= 1)
    best = streak = 1 if active else 0
    for previous, current in zip(active, active[1:]):
        streak = streak + 1 if current - previous == timedelta(days=1) else 1
        best = max(best, streak)
    return best


def check_achievements(state, *, delegations, working_now, now):
    """Unlock any achievement whose rule now holds; each unlocks exactly once."""
    rules = {
        "first_team": lambda: _helpers_overlapped(delegations, now),
        "shipped_it": lambda: any(_NEW_APP_KEY.match(key) for key in state["awarded"]),
        "full_house": lambda: working_now >= FULL_HOUSE,
        "clean_sweep": lambda: _clean_sweep(delegations),
        "on_a_roll": lambda: _longest_streak(state) >= ROLL_DAYS,
    }
    unlocked = {entry["id"] for entry in state["achievements"]}
    newly = [name for name in ACHIEVEMENTS if name not in unlocked and rules[name]()]
    state["achievements"].extend({"id": name, "at": now.isoformat()} for name in newly)
    return newly


def recap_for(state, day, tz=None):
    """One day's summary for the daily recap, or None when nothing happened that day."""
    counters = state["days"].get(day) or {}
    achievements = [entry["id"] for entry in state["achievements"]
                    if parse_time(entry.get("at")) and local_day(parse_time(entry["at"]), tz) == day]
    if not achievements and not any(counters.get(key) for key in (
            "turns", "helpers_done", "helpers_failed", "helpers_stopped", "apps", "level_ups")):
        return None
    busiest_id = max((chat_id for chat_id, chat in state["chats"].items() if chat.get("day_xp", {}).get(day)),
                     key=lambda chat_id: state["chats"][chat_id]["day_xp"][day], default=None)
    busiest = None
    if busiest_id is not None:
        chat = state["chats"][busiest_id]
        busiest = {"chat_id": busiest_id, "title": chat.get("title"), "xp": chat["day_xp"][day]}
    return {
        "turns": counters.get("turns", 0), "helpers_done": counters.get("helpers_done", 0),
        "helpers_failed": counters.get("helpers_failed", 0), "helpers_stopped": counters.get("helpers_stopped", 0),
        "apps": counters.get("apps", 0),
        "level_ups": list(counters.get("level_ups", [])), "achievements": achievements, "busiest": busiest,
    }


def catch_up(feed, now, working_now=0, tz=None, history_seconds=None, clock=time.monotonic):
    """Read new history, award outcomes once, save, and return the summary.

    Only history from 7 days before the office first ran (and never older than
    the 30 days award keys are kept) counts, so losing a cursor cannot turn old
    history into a sudden XP jump.

    History is read page by page until it is exhausted, a page fails to move
    forward, or `history_seconds` of reading have passed (counted from the first
    page, so slow list calls don't starve it). Whatever was read is saved, so a
    long first read finishes over several calls instead of never.
    """
    state = load_state()
    ledger = store.read_json("ledger.json", {})
    started = parse_time(ledger.get("initialized_at")) or now
    counts_from = max(started - BACKFILL, now - KEEP_KEYS)
    chats = feed.list_chats()
    app_chats = {c["id"] for c in chats if c.get("created_by_app_id") is not None}
    delegations = feed.list_delegations()
    apps = feed.list_apps()
    parent_of = {d["child_chat_id"]: d["parent_chat_id"] for d in delegations if d.get("child_chat_id")}
    cursors = ledger.setdefault("cursors", {"after_id": 0, "runs_after_id": 0})

    pages_read = 0
    deadline = None if history_seconds is None else clock() + history_seconds
    while True:
        try:
            page = feed.lifecycle(cursors["after_id"], cursors["runs_after_id"])
        except FeedError:
            if pages_read == 0:
                raise
            break  # keep the pages already read; the rest comes next time
        pages_read += 1
        before = (cursors["after_id"], cursors["runs_after_id"])
        for entry in page.get("runs") or []:
            when = parse_time(entry.get("ended_at")) or parse_time(entry.get("started_at")) or now
            if entry.get("status") == "completed" and when >= counts_from and entry.get("chat_id") not in app_chats:
                award(state, f"run:{entry['id']}", entry["chat_id"], XP_TURN, local_day(when, tz), "turn")
        for event in page.get("events") or []:
            if event.get("type") != "agent_terminal":
                continue
            when = parse_time(event.get("occurred_at")) or parse_time(event.get("observed_at")) or now
            chat_id = _root_chat(event.get("chat_id"), parent_of)
            if when < counts_from or not chat_id or chat_id in app_chats:
                continue
            key = f"helper:{event.get('agent_id')}:{event.get('agent_run_id')}"
            if event.get("state") == "done":
                award(state, key, chat_id, XP_HELPER, local_day(when, tz), "helper")
            elif event.get("state") == "failed":
                note(state, key, local_day(when, tz), "helpers_failed")
            elif event.get("state") == "stopped":
                note(state, key, local_day(when, tz), "helpers_stopped")
        cursors["after_id"] = page.get("next_after_id", cursors["after_id"])
        cursors["runs_after_id"] = page.get("next_runs_after_id", cursors["runs_after_id"])
        more = page.get("has_more") or page.get("runs_has_more")
        stuck = (cursors["after_id"], cursors["runs_after_id"]) == before
        if not more or stuck or (deadline is not None and clock() >= deadline):
            break

    apps_seen = ledger.setdefault("apps_seen", {})
    for app in apps:
        app_id, chat_id = str(app.get("id")), app.get("chat_id")
        created, updated = parse_time(app.get("created_at")), parse_time(app.get("updated_at"))
        seen = parse_time(apps_seen.get(app_id))
        apps_seen[app_id] = app.get("updated_at")
        if not chat_id or chat_id in app_chats:
            continue
        if seen is None and created and created >= counts_from:
            award(state, f"app:{app_id}:created", chat_id, XP_NEW_APP, local_day(created, tz), "new_app")
        elif updated and updated >= counts_from and (seen is None or updated > seen):
            award(state, f"app:{app_id}:{local_day(updated, tz)}", chat_id, XP_APP_UPDATE, local_day(updated, tz), "app_update")

    for chat in chats:
        if chat["id"] in state["chats"] and chat.get("title"):
            state["chats"][chat["id"]]["title"] = chat["title"]
    check_achievements(state, delegations=delegations, working_now=working_now, now=now)
    ledger.setdefault("initialized_at", now.isoformat())
    _prune(state, now, tz)
    # A chat that's gone keeps its XP but not its title once its recap days are over.
    present = {chat["id"] for chat in chats}
    for chat_id, kept in state["chats"].items():
        if chat_id not in present and not kept.get("day_xp"):
            kept["title"] = None
    # Progress (with its award keys) first: if the ledger write then fails, the
    # next run re-reads the same history and the keys stop any double count.
    store.write_json("progress.json", state)
    store.write_json("ledger.json", ledger)
    return {**summary(state), "achievements": list(state["achievements"]),
            "recap": recap_for(state, local_day(now - timedelta(days=1), tz), tz)}
