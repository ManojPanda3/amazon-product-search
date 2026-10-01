"""Network boundary: the transport is stubbed (no live calls)."""

from __future__ import annotations

import pytest

from amazon_product_search import Amazon, TransportError

URL = "https://www.amazon.com/s?k=x"


def stub_transport(amazon, body="<html>ok</html>"):
    """Replace the transport with a canned response; returns captured URLs."""
    urls = []

    def fake_get(url):
        urls.append(url)
        return body

    amazon.transport.get = fake_get
    return urls


def test_success_returns_text(amazon):
    urls = stub_transport(amazon, "<html>ok</html>")
    assert amazon._Amazon__amazon_request(URL) == "<html>ok</html>"
    assert urls == [URL]


def test_transport_failure_returns_empty(amazon):
    def boom(url):
        raise TransportError("blocked after 3 attempts")

    amazon.transport.get = boom
    assert amazon._Amazon__amazon_request(URL) == ""


def test_transport_failure_is_logged(amazon, caplog):
    def boom(url):
        raise TransportError("blocked")

    amazon.transport.get = boom
    with caplog.at_level("ERROR", logger="amazon_product_search.amazon_product_search"):
        amazon._Amazon__amazon_request(URL)
    assert "blocked" in caplog.text


def test_search_raises_on_transport_failure(amazon):
    def boom(url):
        raise TransportError("blocked")

    amazon.transport.get = boom
    with pytest.raises(ValueError, match="while geting data"):
        amazon.search("thinkpad")


def test_session_property_and_lifecycle():
    a = Amazon(workers=1)
    session = a.session
    assert session is a.session, "session must be reused across calls"
    assert "Accept-Language" in session.headers
    with Amazon(workers=1) as b:
        assert b.session is not None
    # context exit closes without error; explicit close is idempotent
    a.close()
    a.close()


def test_client_passes_settings_to_transport():
    a = Amazon(timeout=7, max_attempts=2, backoff=0.0)
    try:
        assert a.transport.timeout == 7
        assert a.transport.max_attempts == 2
        assert a.transport.backoff == 0.0
        assert a.transport.debug is False
    finally:
        a.close()


def test_debug_flag_reaches_transport():
    a = Amazon(is_debuging=True)
    try:
        assert a.transport.debug is True
    finally:
        a.close()