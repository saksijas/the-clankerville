import pytest

from helpers import ANY_STR, QUESTION, msg, text, tool
from quick_reply import LATEST_MAX, full_chat_reason, latest_words, pending_question, thread_view


def test_latest_words_skip_tool_only_turns():
    messages = [msg("assistant", text("Earlier words.")), msg("user", text("go")), msg("assistant", tool("Bash"))]
    assert latest_words(messages) == {"text": "Earlier words.", "cut": False}


def test_latest_words_join_text_blocks_with_line_breaks():
    assert latest_words([msg("assistant", text("One."), tool("Read"), text("Two."))])["text"] == "One.\nTwo."


def test_latest_words_cut_at_a_word_boundary():
    out = latest_words([msg("assistant", text(" ".join(["word"] * 150)))])
    assert out["cut"] is True and out["text"].endswith("word…") and len(out["text"]) <= LATEST_MAX + 1


def test_latest_words_cut_a_long_unbroken_run():  # Review Focus 3
    assert latest_words([msg("assistant", text("x" * 600))]) == {"text": "x" * LATEST_MAX + "…", "cut": True}


def test_no_assistant_text_yet():
    assert latest_words([msg("user", text("hi"))]) is None


def test_pending_question_is_found_by_its_id():
    detail = {"pending_question_id": "q1", "messages": [msg("assistant", {**QUESTION, "question_id": "q1"})]}
    assert pending_question(detail)["question_id"] == "q1"
    assert pending_question({**detail, "pending_question_id": None}) is None


@pytest.mark.parametrize("change,reason", [
    ({"secure_input": {"fields": []}}, "secret"),
    ({"platform_action": {"type": "restart"}}, "restart"),
    ({"questions": [{**QUESTION["questions"][0], "id": "restart"}]}, "restart"),
    ({"questions": [{**QUESTION["questions"][0], "multiSelect": True}]}, "multi_pick"),
    ({"questions": [QUESTION["questions"][0], {"id": "free", "question": "Why?", "options": []}]}, "multi_pick"),
])
def test_cards_the_office_leaves_to_the_full_chat(change, reason):
    assert full_chat_reason({**QUESTION, **change}) == reason


def test_an_ordinary_question_can_be_answered_here():
    assert full_chat_reason(QUESTION) is None


def test_thread_view_for_a_waiting_chat():
    detail = {"pending_question_id": "q1", "pending_messages": [{"cid": "a"}],
              "messages": [msg("assistant", text("Merge now?"), {**QUESTION, "question_id": "q1"})]}
    view = thread_view(detail)
    assert view["latest"] == {"text": "Merge now?", "cut": False} and view["queued"] == 1
    assert view["full_chat_only"] is None and view["question"]["question_id"] == "q1"
    assert view["question"]["questions"][0]["options"][0] == {"id": "0", "label": "Both (Recommended)", "description": ANY_STR}


def test_waiting_but_the_card_is_out_of_reach():
    view = thread_view({"pending_question_id": "q9", "messages": [msg("assistant", text("…"))]})
    assert view["question"] is None and view["full_chat_only"] == "missing"


# --- Task 2: answering in Möbius's exact card format ---------------------------

from quick_reply import AnswerProblem, answer_body, check_answer  # noqa: E402

THREE = {
    "type": "question", "response_mode": "continuation", "question_id": "q-three",
    "questions": [
        {"id": qid, "header": f"Question {n}", "question": prompt,
         "options": [{"id": oid, "label": oid.upper(), "description": ""} for oid in ("a", "b", "c")]}
        for n, (qid, prompt) in enumerate((("q1", "First?"), ("q2", "Second?"), ("q3", "Third?")), 1)
    ],
}


def test_answer_body_matches_the_chat_card_exactly():
    assert answer_body(QUESTION, {"side_chat_approach": "0"}, None, "cid-1") == {
        "content": "- Which should I design?: Both (Recommended)", "hidden": True, "cid": "cid-1",
        "answers": {"Which should I design?": "Both (Recommended)"},
        "question_id": "88f4a3cb-6a0d-5570-a7cf-f89900b38fba",
        "selected_options": {"side_chat_approach": ["0"]}}


def test_a_typed_answer_has_no_selected_options():
    body = answer_body(QUESTION, {}, "Only the side pane", "cid-2")
    assert body["answers"] == {"Which should I design?": "Only the side pane"} and "selected_options" not in body
    assert body["content"] == "- Which should I design?: Only the side pane"


def test_multiline_typed_answers_are_indented_like_the_card():
    assert answer_body(QUESTION, {}, "line one\nline two", "c")["content"] == "- Which should I design?: line one\n  line two"


def test_three_questions_answer_together_in_card_order():
    body = answer_body(THREE, {"q3": "c", "q1": "a", "q2": "b"}, None, "c")
    assert body["content"].splitlines() == ["- First?: A", "- Second?: B", "- Third?: C"]
    assert body["selected_options"] == {"q1": ["a"], "q2": ["b"], "q3": ["c"]}


@pytest.mark.parametrize("block,picks,typed,code", [
    ("QUESTION", {"side_chat_approach": "9"}, None, "unknown_option"),
    ("QUESTION", {}, None, "incomplete"),
    ("QUESTION", {}, "   ", "incomplete"),
    ("QUESTION", {"side_chat_approach": "0"}, "also typed", "ambiguous"),
    ("THREE", {"q1": "a", "q2": "b"}, None, "incomplete"),
    ("THREE", {"q1": "a", "q2": "b", "q3": "c"}, "typed", "typed_not_allowed"),
])
def test_check_answer_refuses_what_the_card_would_not_accept(block, picks, typed, code):
    with pytest.raises(AnswerProblem) as problem:
        check_answer({"QUESTION": QUESTION, "THREE": THREE}[block], picks, typed)
    assert problem.value.code == code and str(problem.value)


def test_a_valid_pick_passes_the_check():
    check_answer(QUESTION, {"side_chat_approach": "2"}, None)
    check_answer(QUESTION, {}, "typed instead")
    check_answer(THREE, {"q1": "a", "q2": "b", "q3": "c"}, None)


def test_latest_words_drop_formatting_marks():
    out = latest_words([msg("assistant", text("**Making it multiplayer.** Run `npm test`, then __ship__."))])
    assert out["text"] == "Making it multiplayer. Run npm test, then ship."


# --- Final review fix pass --------------------------------------------------------

from helpers import SECRET_CARD  # noqa: E402


def test_a_pending_sealed_card_sends_the_owner_to_the_full_chat():
    view = thread_view({"pending_question_id": None,
                        "messages": [msg("assistant", text("Please paste your token."), SECRET_CARD)]})
    assert view["full_chat_only"] == "secret" and view["question"] is None


def test_a_finished_sealed_card_no_longer_blocks_the_card():
    view = thread_view({"pending_question_id": None,
                        "messages": [msg("assistant", {**SECRET_CARD, "status": "submitted"})]})
    assert view["full_chat_only"] is None
