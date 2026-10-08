from service import dispatch


def test_ping():
    assert dispatch({"method": "GET", "path": "ping"}) == {"status": 200, "body": {"ok": True}}


def test_leading_slash_is_ignored():
    assert dispatch({"method": "GET", "path": "/ping"})["status"] == 200


def test_unknown_route_is_404():
    assert dispatch({"method": "GET", "path": "nope"})["status"] == 404


def test_wrong_method_is_404():
    assert dispatch({"method": "POST", "path": "ping"})["status"] == 404
