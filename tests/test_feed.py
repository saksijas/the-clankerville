import json
from urllib.error import URLError

import pytest

from feed import FeedError, OwnerFeed
from helpers import FakeClock, Recorder, fail_if_called, http_error, key, raiser


def test_missing_key_is_no_key(tmp_path):
    feed = OwnerFeed(base_url="http://x", key_path=tmp_path / "none", opener=fail_if_called)
    with pytest.raises(FeedError) as e:
        feed.list_chats()
    assert e.value.code == "no_key"


def test_bearer_header_and_json(tmp_path):
    rec = Recorder(json_body=[{"id": "c1"}])
    assert OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k-123"), opener=rec).list_chats() == [{"id": "c1"}]
    assert rec.last.get_header("Authorization") == "Bearer k-123"
    assert rec.last.full_url == "http://x/api/chats?limit=200"


def test_401_is_key_rejected_and_hides_key(tmp_path):
    feed = OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k-123"), opener=http_error(401))
    with pytest.raises(FeedError) as e:
        feed.list_chats()
    assert e.value.code == "key_rejected" and "k-123" not in str(e.value)


@pytest.mark.parametrize("opener", [raiser(TimeoutError()), http_error(502), raiser(URLError("down"))])
def test_unreachable_is_unavailable(tmp_path, opener):
    with pytest.raises(FeedError) as e:
        OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=opener).list_chats()
    assert e.value.code == "mobius_unavailable"


def test_404_is_not_found(tmp_path):
    with pytest.raises(FeedError) as e:
        OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=http_error(404)).chat_detail("gone")
    assert e.value.code == "not_found"


def test_stop_chat_posts_chat_id(tmp_path):
    rec = Recorder(json_body={"stopped": True, "cleared_pending_cids": [], "cancelled_delegations": []})
    OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).stop_chat("c1")
    assert rec.last.get_method() == "POST" and json.loads(rec.last.data) == {"chat_id": "c1"}


def test_delete_chat_sends_a_delete_for_that_chat(tmp_path):
    rec = Recorder(json_body={})
    OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).delete_chat("c/1")
    assert rec.last.get_method() == "DELETE" and rec.last.full_url == "http://x/api/chats/c%2F1"


def test_409_without_a_reason_still_says_to_try_again(tmp_path):
    with pytest.raises(FeedError) as e:
        OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=http_error(409)).delete_chat("c1")
    assert e.value.code == "conflict" and str(e.value) == "Möbius is still wrapping up that work. Try again in a moment."


def test_each_call_waits_at_most_4_seconds(tmp_path):
    rec = Recorder(json_body=[])
    OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).list_chats()
    assert rec.timeouts == [4.0]


def test_calls_share_one_deadline(tmp_path):
    clock = FakeClock()
    rec = Recorder(json_body=[])
    feed = OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec, deadline=clock() + 5.5, clock=clock)
    feed.list_chats()
    clock.advance(4.0)
    feed.list_chats()
    assert rec.timeouts == [4.0, 1.5]


def test_no_call_starts_once_the_deadline_has_passed(tmp_path):
    clock = FakeClock()
    feed = OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=fail_if_called, deadline=clock() + 1.0, clock=clock)
    clock.advance(1.0)
    with pytest.raises(FeedError) as e:
        feed.list_chats()
    assert e.value.code == "mobius_unavailable"


def test_list_delegations_returns_items(tmp_path):
    rec = Recorder(json_body={"items": [{"id": "d1"}]})
    assert OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).list_delegations() == [{"id": "d1"}]
    assert rec.last.full_url == "http://x/api/delegations?limit=200"


def feed(tmp_path, opener):
    return OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=opener)


def test_chat_thread_reads_the_last_8_messages(tmp_path):
    rec = Recorder({})
    feed(tmp_path, rec).chat_thread("c/1")
    assert rec.last.full_url == "http://x/api/chats/c%2F1?limit=8"


def test_send_message_posts_the_body(tmp_path):
    rec = Recorder({"status": "queued"})
    assert feed(tmp_path, rec).send_message("c1", {"content": "hi", "cid": "k"}) == {"status": "queued"}
    assert rec.last.get_method() == "POST" and rec.last.full_url == "http://x/api/chats/c1/messages"
    assert json.loads(rec.last.data) == {"content": "hi", "cid": "k"}


def test_open_beside_posts_an_open_item_event(tmp_path):
    rec = Recorder({})
    feed(tmp_path, rec).open_beside("c1", "11")
    assert rec.last.full_url == "http://x/api/notify" and json.loads(rec.last.data) == {
        "type": "open_item", "itemKind": "chat", "itemId": "c1", "sourceKind": "app", "sourceId": "11",
        "placement": "beside-source", "activation": "foreground"}


def test_409_carries_mobius_own_sentence(tmp_path):
    with pytest.raises(FeedError) as e:
        feed(tmp_path, http_error(409, {"detail": "The chat is starting another turn; please try again."})).send_message("c1", {})
    assert (e.value.code, str(e.value)) == ("conflict", "The chat is starting another turn; please try again.")


def test_409_with_a_structured_reason_uses_its_message(tmp_path):
    body = {"detail": {"code": "project_deleted", "message": "Recover this chat through its project."}}
    with pytest.raises(FeedError) as e:
        feed(tmp_path, http_error(409, body)).send_message("c1", {})
    assert str(e.value) == "Recover this chat through its project."


def test_410_means_the_question_changed(tmp_path):  # final review: important
    with pytest.raises(FeedError) as e:
        feed(tmp_path, http_error(410, {"detail": "The question is no longer accepting answers."})).send_message("c1", {})
    assert e.value.code == "question_changed" and str(e.value) == "This question changed. Take another look."


def test_create_chat_posts_its_id_and_title(tmp_path):  # the CR desk (spec 2026-10-08 §8)
    rec = Recorder(json_body={"id": "8d4f0b8e-6a8b-5c1e-9f1a-1c2d3e4f5a6b", "title": "Fix login"})
    OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).create_chat("8d4f0b8e-6a8b-5c1e-9f1a-1c2d3e4f5a6b", "Fix login")
    assert rec.last.get_method() == "POST" and rec.last.full_url == "http://x/api/chats"
    assert json.loads(rec.last.data) == {"id": "8d4f0b8e-6a8b-5c1e-9f1a-1c2d3e4f5a6b", "title": "Fix login"}


def test_rename_chat_patches_its_title(tmp_path):
    rec = Recorder(json_body={"id": "c1"})
    OwnerFeed(base_url="http://x", key_path=key(tmp_path, "k"), opener=rec).rename_chat("c1", "Fix login")
    assert rec.last.get_method() == "PATCH" and rec.last.full_url == "http://x/api/chats/c1"
    assert json.loads(rec.last.data) == {"title": "Fix login"}
