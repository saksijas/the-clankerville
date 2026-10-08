"""What an office card shows about one chat, and how it answers a question.

Pure functions only: the back room hands in a chat detail (GET /api/chats/{id}
?limit=8) and gets back plain dicts. Answers are built exactly the way Möbius's
own question card sends them (QuestionCard.handleSubmit and ChatView in the
Möbius frontend), so an answer from the office is indistinguishable from one
given in the chat itself.
"""

import re

LATEST_MAX = 400
THREAD_LIMIT = 8

# The card shows plain text: emphasis and code marks are formatting, not words.
_MARKS = re.compile(r"\*\*|__|`")

# Question cards whose ids mark platform actions rather than a choice.
_RESTART_ID = "restart"


def latest_words(messages):
    """The newest assistant message that has words, trimmed for the card.

    Turns that only ran tools are skipped. Longer text is cut at the last space
    inside LATEST_MAX (or hard-cut when there is none) and marked with "…".
    """
    for message in reversed(messages or []):
        if message.get("role") != "assistant":
            continue
        parts = [_MARKS.sub("", str(block.get("content") or "")).strip() for block in message.get("blocks") or []
                 if block.get("type") == "text"]
        words = "\n".join(part for part in parts if part)
        if not words:
            continue
        if len(words) <= LATEST_MAX:
            return {"text": words, "cut": False}
        head = words[:LATEST_MAX]
        space = head.rfind(" ")
        return {"text": (head[:space] if space > 0 else head).rstrip() + "…", "cut": True}
    return None


def pending_question(detail):
    """The question block the chat is waiting on, or None."""
    wanted = detail.get("pending_question_id")
    if not wanted:
        return None
    for message in reversed(detail.get("messages") or []):
        for block in reversed(message.get("blocks") or []):
            if block.get("type") == "question" and block.get("question_id") == wanted:
                return block
    return None


def pending_secret(detail):
    """True while the chat waits on a sealed secret card.

    Möbius records a standalone sealed-input request as a `secure_input` block
    with status "pending" and no pending question id, so the question checks
    alone would miss it and offer a plain reply box.
    """
    return any(block.get("type") == "secure_input" and block.get("status") == "pending"
               for message in detail.get("messages") or [] for block in message.get("blocks") or [])


def full_chat_reason(block):
    """Why a waiting card must be answered in the full chat, or None.

    Secret cards are sealed; a restart card carries a platform action; a
    multi-pick question, or a two- or three-question card with a question that
    has no choices, needs the full chat's richer answer form.
    """
    if block.get("secure_input"):
        return "secret"
    questions = block.get("questions") or []
    if isinstance(block.get("platform_action"), dict) or any(q.get("id") == _RESTART_ID for q in questions):
        return "restart"
    if any(q.get("multiSelect") or q.get("multi_select") for q in questions):
        return "multi_pick"
    if len(questions) > 1 and any(not q.get("options") for q in questions):
        return "multi_pick"
    return None


def _public_question(question):
    return {
        "id": question.get("id"),
        "header": question.get("header"),
        "question": question.get("question"),
        "options": [{"id": option.get("id"), "label": option.get("label"), "description": option.get("description")}
                    for option in question.get("options") or []],
    }


def thread_view(detail):
    """Everything the card needs: latest words, the waiting question, and limits."""
    view = {
        "latest": latest_words(detail.get("messages")),
        "question": None,
        "full_chat_only": None,
        "queued": len(detail.get("pending_messages") or []),
    }
    if pending_secret(detail):
        view["full_chat_only"] = "secret"
        return view
    if not detail.get("pending_question_id"):
        return view
    block = pending_question(detail)
    if block is None:
        view["full_chat_only"] = "missing"
        return view
    reason = full_chat_reason(block)
    if reason:
        view["full_chat_only"] = reason
        return view
    view["question"] = {
        "question_id": block["question_id"],
        "questions": [_public_question(question) for question in block.get("questions") or []],
    }
    return view


# --- Answering ------------------------------------------------------------------

class AnswerProblem(Exception):
    """An answer the chat's own card would not accept; `code` says why."""

    MESSAGES = {
        "unknown_option": "That choice isn't on this question anymore.",
        "incomplete": "Pick an answer for each question.",
        "ambiguous": "Pick a choice or type an answer, not both.",
        "typed_not_allowed": "Typed answers work only when there's one question.",
    }

    def __init__(self, code):
        super().__init__(self.MESSAGES[code])
        self.code = code


def check_answer(block, picks, typed):
    """Refuse picks the card doesn't offer, missing picks, and mixed answers.

    `picks` maps question id to option id. A typed answer is allowed only on a
    single-question card, and there it replaces a pick (never both).
    """
    questions = block.get("questions") or []
    picks = picks or {}
    typed = (typed or "").strip()
    known = {question.get("id"): {option.get("id") for option in question.get("options") or []}
             for question in questions}
    if len(questions) != 1 and typed:
        raise AnswerProblem("typed_not_allowed")
    for question_id, option_id in picks.items():
        if question_id not in known or option_id not in known[question_id]:
            raise AnswerProblem("unknown_option")
    if len(questions) == 1:
        picked = picks.get(questions[0].get("id"))
        if picked and typed:
            raise AnswerProblem("ambiguous")
        if not picked and not typed:
            raise AnswerProblem("incomplete")
    elif any(picks.get(question.get("id")) is None for question in questions):
        raise AnswerProblem("incomplete")


def answer_body(block, picks, typed, cid):
    """The message Möbius's question card would send for these answers.

    One "- {question}: {answer}" line per question in card order (a typed
    answer's line breaks indented by two spaces), `answers` keyed by question
    text, and `selected_options` for picked options only. Assumes check_answer
    passed.
    """
    picks = picks or {}
    typed = (typed or "").strip()
    lines, answers, selected = [], {}, {}
    for question in block.get("questions") or []:
        picked = picks.get(question.get("id"))
        if picked is not None:
            value = next(option["label"] for option in question.get("options") or [] if option.get("id") == picked)
            selected[question["id"]] = [picked]
        else:
            value = typed
        answers[question["question"]] = value
        lines.append(f"- {question['question']}: " + value.replace("\n", "\n  "))
    body = {"content": "\n".join(lines), "hidden": True, "cid": cid, "answers": answers,
            "question_id": block["question_id"]}
    if selected:
        body["selected_options"] = selected
    return body
