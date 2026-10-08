import json

import store
from feed import FeedError
from helpers import NOW, FakeFeed, thread
from service import dispatch


def call(method, path, body=None, query=None, feed=None):
    return dispatch({"method": method, "path": path, "body": body, "query": query or {}}, feed=feed, now=NOW)["body"]


def test_thread_route_returns_the_card_view():
    body = call("GET", "thread", query={"chat_id": ["c1"]}, feed=FakeFeed(threads={"c1": thread(question="q1")}))
    assert body["ok"] is True and body["question"]["question_id"] == "q1"
    assert body["latest"] == {"text": "Merge now?", "cut": False} and body["full_chat_only"] is None


def test_app_created_chats_are_refused():  # Review Focus 5
    feed = FakeFeed(threads={"bg": thread(chat_id="bg", created_by_app_id=4)})
    for path, payload in (("reply", {"chat_id": "bg", "text": "hi", "cid": "k"}),
                          ("answer", {"chat_id": "bg", "question_id": "q1", "picks": {}, "cid": "k"}),
                          ("open-beside", {"chat_id": "bg"})):
        assert call("POST", path, payload, feed=feed)["error"]["code"] == "not_owner"
    assert call("GET", "thread", query={"chat_id": ["bg"]}, feed=feed)["error"]["code"] == "not_owner"
    assert feed.sent == [] and feed.beside == []


def test_reply_sends_text_and_reports_a_queued_message():  # Review Focus 4
    feed = FakeFeed(threads={"c1": thread()}, send={"status": "queued"})
    assert call("POST", "reply", {"chat_id": "c1", "text": "  carry on  ", "cid": "k1"}, feed=feed) == {"ok": True, "status": "queued"}
    assert feed.sent == [("c1", {"content": "carry on", "cid": "k1"})]


def test_reply_refuses_blank_text_and_waiting_questions():
    assert call("POST", "reply", {"chat_id": "c1", "text": " ", "cid": "k"}, feed=FakeFeed(threads={"c1": thread()}))["error"]["code"] == "bad_request"
    waiting = FakeFeed(threads={"c1": thread(question="q1")})
    assert call("POST", "reply", {"chat_id": "c1", "text": "hi", "cid": "k"}, feed=waiting)["error"]["code"] == "question_waiting"
    assert waiting.sent == []


def test_answer_rechecks_the_question_and_sends_the_card_body():
    feed = FakeFeed(threads={"c1": thread(question="q1")}, send={"status": "answered", "answer_turn": "same"})
    body = call("POST", "answer", {"chat_id": "c1", "question_id": "q1", "picks": {"side_chat_approach": "0"}, "cid": "k2"}, feed=feed)
    assert body == {"ok": True, "answer_turn": "same"}
    assert feed.sent == [("c1", {
        "content": "- Which should I design?: Both (Recommended)", "hidden": True, "cid": "k2",
        "answers": {"Which should I design?": "Both (Recommended)"}, "question_id": "q1",
        "selected_options": {"side_chat_approach": ["0"]}})]


def test_a_changed_question_is_never_answered():  # Review Focus 1
    feed = FakeFeed(threads={"c1": thread(question="q2")})
    body = call("POST", "answer", {"chat_id": "c1", "question_id": "q1", "picks": {"side_chat_approach": "0"}, "cid": "k"}, feed=feed)
    assert body["error"]["code"] == "question_changed" and feed.sent == []


def test_an_answer_the_card_would_refuse_is_not_sent():
    feed = FakeFeed(threads={"c1": thread(question="q1")})
    body = call("POST", "answer", {"chat_id": "c1", "question_id": "q1", "picks": {"side_chat_approach": "9"}, "cid": "k"}, feed=feed)
    assert body["error"] == {"code": "question_changed", "message": "This question changed. Take another look."}
    assert feed.sent == []


def test_secret_and_restart_cards_are_never_answered():
    for extra in ({"secure_input": {"fields": []}}, {"platform_action": {"type": "restart"}}):
        feed = FakeFeed(threads={"c1": thread(question="q1", block_extra=extra)})
        body = call("POST", "answer", {"chat_id": "c1", "question_id": "q1", "picks": {"side_chat_approach": "0"}, "cid": "k"}, feed=feed)
        assert body["error"]["code"] == "full_chat_only" and feed.sent == []


def test_answer_and_reply_pass_the_draft_cid_through():  # Review Focus 2
    feed = FakeFeed(threads={"c1": thread()}, send={"status": "started"})
    call("POST", "reply", {"chat_id": "c1", "text": "hi", "cid": "same"}, feed=feed)
    call("POST", "reply", {"chat_id": "c1", "text": "hi", "cid": "same"}, feed=feed)
    assert [body["cid"] for _, body in feed.sent] == ["same", "same"]


def test_a_deleted_chat_is_reported_gone():
    feed = FakeFeed(threads={"c1": FeedError("not_found", "Möbius doesn't have that anymore.")})
    assert call("GET", "thread", query={"chat_id": ["c1"]}, feed=feed)["error"]["code"] == "not_found"


def test_open_beside_names_the_office_as_the_source(monkeypatch):
    monkeypatch.setenv("APP_ID", "11")
    feed = FakeFeed(threads={"c1": thread()})
    assert call("POST", "open-beside", {"chat_id": "c1"}, feed=feed) == {"ok": True}
    assert feed.beside == [("c1", "11")]


def test_the_reply_log_never_holds_text():
    feed = FakeFeed(threads={"c1": thread()}, send={"status": "started"})
    call("POST", "reply", {"chat_id": "c1", "text": "my secret plans", "cid": "k"}, feed=feed)
    log = store.read_json("reply-log.json", [])
    assert [(entry["chat_id"], entry["kind"], entry["ok"]) for entry in log] == [("c1", "reply", True)]
    assert "secret plans" not in json.dumps(log)


def test_conflicts_keep_mobius_sentence():
    feed = FakeFeed(threads={"c1": thread()}, send=FeedError("conflict", "The chat is starting another turn; please try again."))
    assert call("POST", "reply", {"chat_id": "c1", "text": "hi", "cid": "k"}, feed=feed)["error"] == {
        "code": "conflict", "message": "The chat is starting another turn; please try again."}


def test_routes_stay_inside_the_service_limit(monkeypatch):
    import service
    made = []

    class RecordingFeed(FakeFeed):
        def __init__(self, **options):
            made.append(options)
            super().__init__(threads={"c1": thread()}, send={"status": "started"})

    monkeypatch.setattr(service, "OwnerFeed", RecordingFeed)
    started = service.time.monotonic()
    dispatch({"method": "POST", "path": "reply", "body": {"chat_id": "c1", "text": "hi", "cid": "k"}}, now=NOW)
    assert made[0]["deadline"] - started <= 12.5


def test_replies_are_refused_while_a_sealed_card_waits():  # final review: critical
    from helpers import SECRET_CARD
    detail = thread()
    detail["messages"][-1]["blocks"].append(SECRET_CARD)
    feed = FakeFeed(threads={"c1": detail})
    body = call("POST", "reply", {"chat_id": "c1", "text": "sk-live-1234567890", "cid": "k"}, feed=feed)
    assert body["error"]["code"] == "full_chat_only" and feed.sent == []
