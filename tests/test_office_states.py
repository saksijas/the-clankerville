from datetime import timedelta

from helpers import NOW, chat
from office import chat_state, select_chats


def test_parked_on_question_is_needs_you():  # Review Focus 1
    assert chat_state(chat(running=True, owner_input_kind="question", pending_question_id="q1")) == "needs_you"


def test_error_beats_working():
    assert chat_state(chat(running=True, has_unseen_failure=True)) == "error"


def test_waiting_is_watching():
    assert chat_state(chat(waiting=True)) == "watching"


def test_an_idle_chat_is_on_break():
    assert chat_state(chat(activity_at=NOW - timedelta(minutes=6))) == "on_break"


def test_selection_rules():
    rows = [chat(id="app", created_by_app_id=4, running=True),
            chat(id="old", activity_at=NOW - timedelta(hours=25)),
            chat(id="recent", activity_at=NOW - timedelta(hours=23)),
            chat(id="old-but-waiting", activity_at=NOW - timedelta(days=3), waiting=True)]
    assert [c["id"] for c in select_chats(rows, NOW)] == ["old-but-waiting", "recent"]


def test_cap_keeps_busy_first():
    rows = [chat(id=f"idle{i}", activity_at=NOW - timedelta(minutes=i)) for i in range(34)] + [chat(id="busy", running=True)]
    picked = select_chats(rows, NOW)
    assert len(picked) == 32 and picked[0]["id"] == "busy" and "idle33" not in [c["id"] for c in picked]  # 4 floors of 8
