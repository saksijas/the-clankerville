"""What each chat has cost, in dollars and tokens, from Möbius's own turn records.

Möbius keeps a dollar figure and token counts for every finished turn
(`GET /api/chats/{id}/usage`). Two things about those records shape this module
(found 2026-10-13, spec 2026-10-13-clankerville-spend-design.md):

- A Claude turn's dollar figure is the conversation's running total so far, not
  that turn's cost: within one provider session the readings only climb, and a
  turn with no tokens repeats the reading before it. A turn's own cost is the
  rise from the previous reading in the same session; a lower reading means the
  total started over, so it counts in full. The model tally inside each reading
  (`usage.provider_model_usage`) is a running total too and also covers the
  background model calls the turn's own counters leave out, so tokens follow
  the same rule and match the dollars. Adding the readings up, as Möbius's own
  `totals.cost_usd` does, overstates a chat many times over.
- Codex and other providers record each turn on its own, so their readings add
  up as they are.

Dollars are at API list prices (Claude's CLI prices its own turns; Möbius
prices Codex turns from a rate card). On a subscription plan nobody is billed
this amount; it is what the work would cost through the API.

Reading is cheap on purpose: a chat's records are read again only when the chat
changed since the last read, at most once a minute while it runs, plus a fresh
read every six hours; and only a few reads happen per snapshot.
"""

import math
from datetime import timedelta

from feed import FeedError
from office import parse_time
from progress import local_day

KEEP = timedelta(days=8)  # turns kept for "today" and yesterday's recap, with room for any time zone
READS_PER_SNAPSHOT = 6
RUNNING_REREAD = timedelta(minutes=1)
STALE_REREAD = timedelta(hours=6)
FAILED_BACKOFF = timedelta(minutes=5)  # a chat whose read failed waits this long, so it can't block the rest
# A running tally that began with this turn holds the turn's own tokens plus its background
# model calls (about 1% in practice); this much headroom still tells it from a continuing one.
FRESH_SLACK = 50_000
_TALLY_FIELDS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0
    return max(0, int(value))


def _money(value):
    """A dollar reading, or None when there is none worth trusting."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _tally(run):
    """The provider's running token tally across every model, or None without one."""
    usage = run.get("usage")
    models = usage.get("provider_model_usage") if isinstance(usage, dict) else None
    if not isinstance(models, dict) or not models:
        return None
    if not all(isinstance(numbers, dict) for numbers in models.values()):
        return None
    return sum(_count(numbers.get(field)) for numbers in models.values() for field in _TALLY_FIELDS)


def _fresh(tally, own_tokens):
    """A tally holding little more than this turn's own tokens: a running total that began with this turn."""
    return tally is not None and tally <= own_tokens * 1.5 + FRESH_SLACK


def _claude_turn(before, cost, tally, own_tokens):
    """(dollars, tokens) for one Claude reading, given the session's previous (dollars, tally) or None.

    The total started over when the dollars went down, or when the tally rose by less than this
    turn's own tokens and holds little more than them (then even a reading above the old total is
    this turn's alone). A tally that dropped but stayed large is a reporting change, not a
    restart: the dollars' rise is trusted and the turn's own tokens are used.
    """
    previous_cost, previous_tally = before if before else (None, None)
    continuing = previous_tally is not None and tally is not None and tally - previous_tally >= own_tokens
    started_over = (before is None or cost < previous_cost
                    or (previous_tally is not None and tally is not None and not continuing
                        and _fresh(tally, own_tokens)))
    if not started_over:
        return cost - previous_cost, tally - previous_tally if continuing else own_tokens
    # A new total: its tally covers the same turns as its dollars (earlier unrecorded ones too).
    if continuing:
        tokens = tally - previous_tally  # only the dollars started over; the tally carried on
    elif tally is not None and tally >= own_tokens:
        tokens = tally
    else:
        tokens = own_tokens
    return cost, tokens


def turn_spend(runs):
    """Each turn's own (when, dollars, tokens), from runs in the order Möbius lists them (oldest first)."""
    last = {}  # Claude session -> (dollar reading, token tally) after its latest reading
    turns = []
    for run in runs:
        cost = _money(run.get("cost_usd"))
        own_tokens = _count(run.get("total_tokens"))
        when = parse_time(run.get("ended_at")) or parse_time(run.get("started_at"))
        if run.get("provider") != "claude":
            if cost is not None or own_tokens:
                turns.append((when, cost or 0.0, own_tokens))
            continue
        if cost is None:
            continue  # no reading; the next one's rise covers this turn
        # A run Möbius never tied to a session (e.g. a sign-in failure) is its own total.
        session = run.get("provider_session_id") or f"run:{run.get('id')}"
        tally = _tally(run)
        usd, tokens = _claude_turn(last.get(session), cost, tally, own_tokens)
        last[session] = (cost, tally)
        turns.append((when, usd, tokens))
    return turns


def chat_totals(body, now):
    """All-time dollars and tokens for one chat, plus its turns of the last `KEEP` days."""
    turns = turn_spend((body or {}).get("runs") or [])
    oldest = now - KEEP
    return {
        "usd": round(sum(usd for _, usd, _ in turns), 6),
        "tokens": sum(tokens for _, _, tokens in turns),
        "turns": [[when.isoformat(), round(usd, 6), tokens] for when, usd, tokens in turns
                  if when is not None and when >= oldest],
    }


def stamp(chat):
    """Changes whenever the chat does, so an unchanged chat is never read again."""
    return f"{chat.get('updated_at')}|{chat.get('activity_at')}"


def _due(entry, failed_at, chat, now):
    if failed_at is not None and now - failed_at < FAILED_BACKOFF:
        return False
    read_at = parse_time((entry or {}).get("read_at"))
    if read_at is None or now - read_at >= STALE_REREAD:
        return True
    if entry.get("stamp") == stamp(chat):
        return False
    return not (chat.get("running") and now - read_at < RUNNING_REREAD)


def _valid_turn(turn):
    if not (isinstance(turn, list) and len(turn) == 3 and isinstance(turn[0], str)):
        return False
    if isinstance(turn[2], bool) or not isinstance(turn[2], int):
        return False
    try:
        return parse_time(turn[0]) is not None and _money(turn[1]) is not None
    except ValueError:
        return False


def _clean(saved):
    """The saved state's well-formed parts only, so a damaged file can't break the office."""
    saved = saved if isinstance(saved, dict) else {}
    entries = saved.get("chats") if isinstance(saved.get("chats"), dict) else {}
    chats = {}
    for chat_id, entry in entries.items():
        if isinstance(entry, dict):
            turns = entry.get("turns") if isinstance(entry.get("turns"), list) else []
            chats[chat_id] = {**entry, "usd": _money(entry.get("usd")) or 0.0, "tokens": _count(entry.get("tokens")),
                              "turns": [turn for turn in turns if _valid_turn(turn)]}
    failed = saved.get("failed") if isinstance(saved.get("failed"), dict) else {}
    return chats, {chat_id: at for chat_id, at in failed.items() if isinstance(at, str)}


def refresh(feed, chats, saved, now, budget_left=lambda: True, limit=READS_PER_SNAPSHOT):
    """Re-read the chats that are due (never-read ones first), keep the rest, and prune.

    A chat whose read fails waits `FAILED_BACKOFF` before its next try, so it
    can't hold up the others; only key trouble or a spent budget stops the
    reading. A chat that left the office keeps its entry until its last kept
    turn is `KEEP` old, so yesterday's recap still counts it.
    """
    entries, failed = _clean(saved)

    def failed_at(chat_id):
        try:
            return parse_time(failed.get(chat_id))
        except ValueError:
            return None

    due = [chat for chat in chats if _due(entries.get(chat["id"]), failed_at(chat["id"]), chat, now)]
    due.sort(key=lambda chat: chat["id"] in entries)  # stable: never-read chats first
    for chat in due[:limit]:
        if not budget_left():
            break
        try:
            body = feed.chat_usage(chat["id"])
        except FeedError as exc:
            if exc.code in ("no_key", "key_rejected"):
                break  # nothing else can be read either
            failed[chat["id"]] = now.isoformat()
            continue
        failed.pop(chat["id"], None)
        entries[chat["id"]] = {"stamp": stamp(chat), "read_at": now.isoformat(), "title": chat.get("title"),
                               **chat_totals(body, now)}
    present = {chat["id"]: chat for chat in chats}
    oldest = now - KEEP
    kept = {}
    for chat_id, entry in entries.items():
        turns = [turn for turn in entry["turns"] if parse_time(turn[0]) > oldest]
        if chat_id in present or turns:
            title = present[chat_id].get("title") if chat_id in present else None
            kept[chat_id] = {**entry, "title": title or entry.get("title"), "turns": turns}
    state = {"version": 1, "chats": kept}
    still_failing = {chat_id: at for chat_id, at in failed.items() if chat_id in present}
    if still_failing:
        state["failed"] = still_failing
    return state


def _day_sums(entry, day, tz):
    usd = tokens = 0
    for at, turn_usd, turn_tokens in entry.get("turns") or []:
        moment = parse_time(at)
        if moment is not None and local_day(moment, tz) == day:
            usd += turn_usd
            tokens += turn_tokens
    return round(usd, 6), tokens


def chat_view(entry, today, tz):
    """One chat's figures for the screen, or None before its first read."""
    if entry is None:
        return None
    today_usd, today_tokens = _day_sums(entry, today, tz)
    return {"usd": round(entry.get("usd") or 0.0, 4), "tokens": entry.get("tokens") or 0,
            "today_usd": round(today_usd, 4), "today_tokens": today_tokens}


def office_view(state, chat_ids, today, tz):
    """Today's spend for the whole office (chats that left today included), and how many aren't read yet."""
    entries, _ = _clean(state)
    usd = tokens = 0
    for entry in entries.values():
        day_usd, day_tokens = _day_sums(entry, today, tz)
        usd += day_usd
        tokens += day_tokens
    return {"today_usd": round(usd, 4), "today_tokens": tokens,
            "pending": sum(1 for chat_id in chat_ids if chat_id not in entries)}


def day_summary(state, day, tz):
    """One day's spend and its biggest spender for the recap, or None when nothing was spent."""
    usd = tokens = 0
    top = None
    for entry in _clean(state)[0].values():
        day_usd, day_tokens = _day_sums(entry, day, tz)
        usd += day_usd
        tokens += day_tokens
        if day_usd > 0 and (top is None or day_usd > top["usd"]):
            top = {"title": entry.get("title"), "usd": round(day_usd, 4)}
    if not usd and not tokens:
        return None
    return {"usd": round(usd, 4), "tokens": tokens, "top": top}
