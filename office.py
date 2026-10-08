"""What the office shows, decided from plain Möbius data.

Pure functions only: no I/O, no clock reads. `service.py` hands in the rows
`feed.py` fetched plus `now`, and gets back plain dicts for the snapshot.
"""

import hashlib
import os
import re
from datetime import UTC, datetime, timedelta

ACTIVE_WINDOW = timedelta(hours=24)
MAX_CHARACTERS = 30
BUBBLE_MAX = 28
FILE_MAX = 32

# spec §5.3. `{file}` is filled with a scrubbed, capped basename; nothing else
# from a tool's input ever reaches a label.
LABELS = {
    "Read": "Reading {file}",
    "Edit": "Editing {file}", "Write": "Editing {file}", "NotebookEdit": "Editing {file}",
    "Bash": "Running a command", "shell": "Running a command",
    "apply_patch": "Editing code",
    "Grep": "Searching the code", "Glob": "Searching the code",
    "WebSearch": "Searching the web",
    "WebFetch": "Reading a web page",
    "spawn_agent": "Briefing a helper",
    "message_agent": "Messaging a helper",
    "request_question": "Asking you something", "request_approval": "Asking you something",
    "request_restart": "Asking you something", "request_secret": "Asking you something",
    "apply_app": "Shipping an app",
    "screenshot": "Taking a screenshot",
    "memory_search": "Recalling memories", "memory_read": "Recalling memories",
    "checkpoint_chat": "Taking notes",
}

_MCP_PREFIX = re.compile(r"^mcp__[^_]+(?:_[^_]+)*?__")
_PATH = re.compile(r"/[^\s'\"`]+")
_KEY_PREFIX = re.compile(r"(?:sk|pk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{8,}")
_HEX_RUN = re.compile(r"[A-Fa-f0-9]{24,}")
_TOKENISH_RUN = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


def _looks_like_token(run):
    # Mixed letters and digits mark generated secrets; readable names like
    # "implementation-plan-for-agent-office-v2" have almost no digits.
    return sum(ch.isdigit() for ch in run) >= 4 and sum(ch.isalpha() for ch in run) >= 4


def scrub(text):
    """Remove anything that looks like a key, token, or long hex id."""
    text = _KEY_PREFIX.sub("", text)
    # Real hex ids and hashes contain digits; a run of only a–f letters
    # ("aaaa…", "deadbeef…") is a word, not a secret.
    text = _HEX_RUN.sub(lambda m: "" if any(ch.isdigit() for ch in m.group()) else m.group(), text)
    return _TOKENISH_RUN.sub(lambda m: "" if _looks_like_token(m.group()) else m.group(), text)


def _cap(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


_FILE_KEYS = ("file_path", "notebook_path", "path")
# Möbius summarizes most tool inputs as "key=value, key=value" (tool_summaries.py);
# file tools (Read, Edit, Write) arrive as the bare path.
_FILE_FIELD = re.compile(r"(?:^|,\s*)(?:file_path|notebook_path|path)=(/[^\s,'\"`]+)")


def _file_path(tool_input):
    """The file a tool works on: its own file field when it has one, else the first path."""
    if isinstance(tool_input, dict):
        for key in _FILE_KEYS:
            if isinstance(tool_input.get(key), str) and tool_input[key]:
                return tool_input[key]
    text = str(tool_input or "")
    field = _FILE_FIELD.search(text)
    if field:
        return field.group(1)
    match = _PATH.search(text)
    return match.group() if match else ""


def _file_name(tool_input):
    name = scrub(os.path.basename(_file_path(tool_input)))
    # Scrub before capping: a cap first could keep the head of a long secret.
    return _cap(name, FILE_MAX) if name.strip(". …") else "a file"


def step_label(blocks):
    """A friendly, privacy-safe bubble for what a chat is doing right now."""
    running = [b for b in blocks if b.get("type") == "tool" and b.get("status") == "running"]
    if running:
        block = running[-1]
        name = _MCP_PREFIX.sub("", str(block.get("tool") or ""))
        template = LABELS.get(name, "Working")
        label = template.format(file=_file_name(block.get("input"))) if "{file}" in template else template
    elif blocks and blocks[-1].get("type") == "text":
        label = "Writing a reply"
    else:
        label = "Thinking"
    return _cap(label, BUBBLE_MAX)

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def parse_time(value):
    """Parse a Möbius timestamp (naive UTC ISO, or aware ISO) to an aware UTC datetime."""
    if not value:
        return None
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def chat_state(chat):
    """One chat's office state; the first matching rule wins (spec §5.2).

    A turn parked on the owner's answer still reports `running`, so the
    owner-input check must come before the running check. There is no
    "gone home": the sword deletes a chat, so a struck chat leaves the office.
    """
    if chat.get("owner_input_kind") or chat.get("pending_question_id"):
        return "needs_you"
    if chat.get("has_unseen_failure"):
        return "error"
    if chat.get("running"):
        return "working"
    if chat.get("waiting"):
        return "watching"
    return "on_break"


HELPER_LINGER = timedelta(seconds=60)
HELPER_NAME_MAX = 24
_POSES = {
    "starting": "busy", "running": "busy", "resuming": "busy", "accepted": "busy", "retrying": "busy",
    "paused": "on_hold",
    "completed": "done",
    "failed": "failed", "needs_review": "failed", "interrupted": "failed",
}
_GONE_AT_ONCE = {"stopped", "cancelled"}


def _helper_pose(delegation, now):
    """The helper's pose, or None when it has already left the office."""
    status = delegation.get("status")
    if status in _GONE_AT_ONCE:
        return None
    pose = _POSES.get(status, "busy")
    if pose in ("done", "failed"):
        ended = parse_time(delegation.get("ended_at"))
        if ended is None or now - ended > HELPER_LINGER:
            return None
    return pose


def build_teams(delegations, chat_ids, now):
    """Each office chat's visible helpers, as `{lead chat_id: [helper, ...]}`.

    A helper's own helpers name its `child_chat_id` as their parent chat, which
    is how sub-teams are found; the tree is resolved over every delegation so a
    child stays on its team even after its parent helper has left.
    """
    by_child_chat = {d.get("child_chat_id"): d for d in delegations if d.get("child_chat_id")}
    teams = {}
    for delegation in delegations:
        parent_chat = delegation.get("parent_chat_id")
        if parent_chat in chat_ids:
            lead, depth, parent_id = parent_chat, 1, None
        else:
            parent = by_child_chat.get(parent_chat)
            if parent is None or parent.get("parent_chat_id") not in chat_ids:
                continue  # not in the office, or nested deeper than two levels
            lead, depth, parent_id = parent["parent_chat_id"], 2, parent["id"]
        pose = _helper_pose(delegation, now)
        if pose is None:
            continue
        name = scrub(str(delegation.get("task_key") or "")).strip() or "helper"
        order = (depth, delegation.get("created_at") or "")
        teams.setdefault(lead, []).append((order, {
            "id": delegation["id"],
            "name": _cap(name, HELPER_NAME_MAX),
            "pose": pose,
            "parent_id": parent_id,
            "depth": depth,
            "dismissable": pose in ("busy", "on_hold"),
        }))
    return {lead: [helper for _, helper in sorted(members, key=lambda pair: pair[0])]
            for lead, members in teams.items()}


def _in_office(chat, now):
    if chat.get("created_by_app_id") is not None:
        return False
    if chat_state(chat) != "on_break":
        return True
    activity = parse_time(chat.get("activity_at"))
    return activity is not None and now - activity <= ACTIVE_WINDOW


def select_chats(chats, now):
    """The owner's chats that belong in the office, busiest and most recent first, at most 30."""
    present = [chat for chat in chats if _in_office(chat, now)]
    present.sort(key=lambda chat: (
        chat_state(chat) == "on_break",
        -(parse_time(chat.get("activity_at")) or _EPOCH).timestamp(),
    ))
    return present[:MAX_CHARACTERS]


# --- The room: pods, looks, names (spec §6.1) ---------------------------------

ROOM_WIDTH = 13
POD_W = 4
POD_D = 3
PODS_PER_ROW = 3
COFFEE_SLOT = 8
LEAD_SLOT = (1.4, 0.2)
# Filled in this order: diagonal from the lead first, so bubbles and chips
# don't stack on one row (front-left, back-right, front-right, back-left, front-centre).
HELPER_SLOTS = [(0.1, 1.6), (2.7, 0.2), (2.7, 1.6), (0.1, 0.2), (1.4, 1.6)]
MAX_VISIBLE_HELPERS = 5
POD_MEMORY = timedelta(hours=24)
SHORT_NAME_MAX = 16

_HAIR = ["#3b2a20", "#d9a441", "#1f1f28", "#7a3e2b", "#2d2d2d", "#b05a2c"]
_SHIRT = ["#6d5dfc", "#2fb3a3", "#f08a5d", "#4c9be8", "#e85d75", "#9bc53d"]
_SKIN = ["#f2c9a0", "#e0ac7e", "#8d5a3b", "#f5d1b5", "#c68a62", "#e8b793"]


def pod_origin(slot):
    return (0.5 + (slot % PODS_PER_ROW) * POD_W, 0.5 + (slot // PODS_PER_ROW) * POD_D)


def floor_depth(max_slot):
    return max(9, POD_D * (max_slot // PODS_PER_ROW + 1))


SEEN_REFRESH = timedelta(minutes=10)


def _lowest_free_slot(taken):
    return next(slot for slot in range(10_000) if slot != COFFEE_SLOT and slot not in taken)


def assign_pods(chat_ids, previous, now):
    """Stable pod slots: a chat keeps its slot while it stays in the office.

    A chat that left keeps its slot for 24 h so it sits back at its own desk if
    it returns, but only while there is room: when a free desk would make the
    room bigger, a newcomer takes the lowest desk an absent chat was keeping.
    The coffee corner's slot is never handed out. `last_seen` is refreshed at
    most every 10 minutes, so an unchanged office leaves the map unchanged.
    """
    present = set(chat_ids)
    pods = {}
    for chat_id, entry in previous.items():
        seen = parse_time(entry.get("last_seen"))
        if chat_id in present or (seen is not None and now - seen <= POD_MEMORY):
            pods[chat_id] = dict(entry)
    for chat_id in chat_ids:
        if chat_id in pods:
            continue
        slot = _lowest_free_slot({entry["slot"] for entry in pods.values()})
        needed = floor_depth(max((pods[c]["slot"] for c in chat_ids if c in pods), default=0))
        if floor_depth(slot) > needed:
            kept_for_absent = sorted((entry["slot"], c) for c, entry in pods.items() if c not in present)
            if kept_for_absent and kept_for_absent[0][0] < slot:
                slot, absent = kept_for_absent[0]
                del pods[absent]
        pods[chat_id] = {"slot": slot}
    for chat_id in chat_ids:
        seen = parse_time(pods[chat_id].get("last_seen"))
        if seen is None or now - seen >= SEEN_REFRESH:
            pods[chat_id]["last_seen"] = now.isoformat()
    return pods


def assign_helper_desks(teams, pods):
    """Stable helper desks: a helper keeps its desk while it stays on the team.

    Up to MAX_VISIBLE_HELPERS desks per lead; a newcomer takes the lowest free
    one, in team order. Helpers without a desk count toward the lead's "+N".
    """
    for lead, entry in pods.items():
        helpers = teams.get(lead, [])
        if not helpers:
            entry.pop("helpers", None)
            continue
        present = {helper["id"] for helper in helpers}
        kept = {hid: slot for hid, slot in (entry.get("helpers") or {}).items()
                if hid in present and 0 <= slot < MAX_VISIBLE_HELPERS}
        free = [slot for slot in range(MAX_VISIBLE_HELPERS) if slot not in kept.values()]
        for helper in helpers:
            if helper["id"] not in kept and free:
                kept[helper["id"]] = free.pop(0)
        entry["helpers"] = kept
    return pods


def short_name(title):
    title = " ".join(str(title or "").split())
    if not title:
        return "Untitled chat"
    if len(title) <= SHORT_NAME_MAX:
        return title
    cut = title.rfind(" ", 0, SHORT_NAME_MAX + 1)
    # A word-boundary cut can leave "Review-loop:"; the tag reads cleaner without it.
    return title[:cut].rstrip(":;,.-–—") if cut > 0 else title[: SHORT_NAME_MAX - 1] + "…"


def look_for(character_id):
    digest = hashlib.sha256(str(character_id).encode()).digest()
    return {"hair": _HAIR[digest[0] % 6], "shirt": _SHIRT[digest[1] % 6], "skin": _SKIN[digest[2] % 6]}


def _desk(origin, offset):
    return {"x": round(origin[0] + offset[0], 2), "y": round(origin[1] + offset[1], 2)}


def _latest_blocks(detail):
    for message in reversed(detail.get("messages") or []):
        if message.get("role") == "assistant":
            return message.get("blocks") or []
    return []


# --- The snapshot (spec §8) -------------------------------------------------------

COUNT_KEYS = ("working", "needs_you", "error", "watching", "on_break")


def build_snapshot(chats, details, teams, pods, office_progress, now):
    """Assemble the office snapshot from already-selected chats and fetched rows.

    `details` holds chat details for `working` chats only; a working chat
    without one (vanished, or skipped under the time budget) shows "Working".
    `teams` comes from `build_teams`; `pods` from `assign_pods` plus
    `assign_helper_desks`, so every desk here is the persisted one.
    """
    chat_progress = office_progress.get("chats", {})
    counts = dict.fromkeys(COUNT_KEYS, 0)
    characters, team_rows = [], []
    for chat in chats:
        chat_id = chat["id"]
        state = chat_state(chat)
        counts[state] += 1
        origin = pod_origin(pods[chat_id]["slot"])
        progress = chat_progress.get(chat_id, {})
        character = {
            "id": chat_id, "kind": "chat", "chat_id": chat_id,
            "name": chat.get("title") or "Untitled chat", "short": short_name(chat.get("title")),
            "state": state, "level": progress.get("level", 1), "xp_progress": progress.get("xp_progress", 0.0),
            "queued": 0, "desk": _desk(origin, LEAD_SLOT), "look": look_for(chat_id),
            "dismissable": True,
            # What a strike would also cancel, whatever state is on show: an
            # armed timer can sit under "working", a question under "needs you".
            "waiting": bool(chat.get("waiting")),
            "asking": bool(chat.get("owner_input_kind") or chat.get("pending_question_id")),
        }
        chat_detail = details.get(chat_id)
        if state == "working":
            character["step"] = step_label(_latest_blocks(chat_detail)) if chat_detail else "Working"
        if state in ("working", "needs_you"):
            character["queued"] = len((chat_detail or {}).get("pending_messages") or [])
        helpers = teams.get(chat_id, [])
        helper_desks = pods[chat_id].get("helpers") or {}
        visible = [helper for helper in helpers if helper["id"] in helper_desks]
        if len(helpers) > len(visible):
            character["overflow"] = len(helpers) - len(visible)
        characters.append(character)
        for helper in visible:
            characters.append({
                "id": helper["id"], "kind": "helper", "chat_id": chat_id, "lead_id": chat_id,
                "parent_id": helper["parent_id"], "name": helper["name"], "short": helper["name"],
                "state": helper["pose"], "desk": _desk(origin, HELPER_SLOTS[helper_desks[helper["id"]]]),
                "look": look_for(helper["id"]), "dismissable": helper["dismissable"],
            })
        if visible:
            team_rows.append({"lead_id": chat_id, "member_ids": [helper["id"] for helper in visible]})
    max_slot = max((pods[chat["id"]]["slot"] for chat in chats), default=0)
    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "office": {key: office_progress[key] for key in ("level", "xp", "level_start_xp", "next_level_xp")},
        "counts": counts,
        "room": {"width": ROOM_WIDTH, "depth": floor_depth(max_slot)},
        "characters": characters,
        "teams": team_rows,
    }
