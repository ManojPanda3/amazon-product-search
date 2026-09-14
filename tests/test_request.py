"""Network boundary: session.get mocked (no live calls)."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests


def test_success_returns_text(amazon):
    resp = MagicMock(status_code=200, text="<html>ok</html>")
    amazon.session.get = MagicMock(return_value=resp)
    out = amazon._Amazon__amazon_request("https://www.amazon.com/s?k=x")
    assert out == "<html>ok</html>"
    _, kwargs = amazon.session.get.call_args
    assert kwargs["timeout"] == 10


def test_non_200_returns_empty(amazon):
    resp = MagicMock(status_code=503, content=b"blocked")
    amazon.session.get = MagicMock(return_value=resp)
    assert amazon._Amazon__amazon_request("https://example.test") == ""


def test_request_exception_returns_empty(amazon):
    def boom(*a, **k):
        raise requests.RequestException("down")

    amazon.session.get = boom
    assert amazon._Amazon__amazon_request("https://example.test") == ""


def test_session_headers_and_lifecycle():
    from amazon_product_search import Amazon

    a = Amazon(workers=1)
    assert "User-Agent" in a.session.headers
    assert "Mozilla" in a.session.headers["User-Agent"]
    with Amazon(workers=1) as b:
        assert b.session is not None
    # context exit closes without error; explicit close is idempotent
    a.close()
    a.close()
