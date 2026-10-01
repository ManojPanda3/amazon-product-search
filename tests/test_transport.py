"""Transport: impersonation, block detection, retry/backoff, lifecycle.

No live calls: the curl_cffi session is faked, so these assert the retry and
classification logic that the Amazon 503 fix depends on.
"""

from __future__ import annotations

import asyncio

import pytest
from curl_cffi.requests.errors import RequestsError

from amazon_product_search.transport import (
    BLOCK_MARKERS,
    IMPERSONATE_PROFILES,
    Transport,
    TransportError,
    is_blocked,
)

URL = "https://www.amazon.com/s?k=thinkpad"


class FakeResponse:
    def __init__(self, status_code=200, text="<html>ok</html>"):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Records calls and replays a scripted sequence of outcomes."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else FakeResponse()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        self.closed = True


def make_transport(outcomes, **kwargs):
    session = FakeSession(outcomes)
    kwargs.setdefault("backoff", 0.0)
    return Transport(session=session, **kwargs), session


# ------------------------------------------------------------ block detection


@pytest.mark.parametrize("marker", BLOCK_MARKERS)
def test_each_block_marker_is_detected(marker):
    assert is_blocked(f"<html><body>{marker} some page</body></html>") is True


def test_product_html_is_not_blocked():
    assert is_blocked('<div data-component-type="s-search-result">ok</div>') is False


def test_empty_body_is_not_blocked():
    assert is_blocked("") is False


# -------------------------------------------------------------------- retries


def test_first_clean_attempt_returns_immediately():
    transport, session = make_transport([FakeResponse(200, "<html>ok</html>")])
    assert transport.get(URL) == "<html>ok</html>"
    assert len(session.calls) == 1, "must not retry on success"


def test_blocked_attempt_is_retried_under_a_different_profile():
    transport, session = make_transport(
        [FakeResponse(503, "Sorry! Something went wrong!"), FakeResponse(200, "clean")]
    )
    assert transport.get(URL) == "clean"
    profiles = [kwargs["impersonate"] for _, kwargs in session.calls]
    assert len(profiles) == 2
    assert profiles[0] != profiles[1], "a stuck fingerprint must be rotated away from"


def test_interstitial_with_status_200_is_still_treated_as_blocked():
    """The bm-verify challenge returns 200; status alone is not success."""
    transport, session = make_transport(
        [FakeResponse(200, '<meta http-equiv="refresh" content="bm-verify=AAQ">'),
         FakeResponse(200, "clean")]
    )
    assert transport.get(URL) == "clean"
    assert len(session.calls) == 2


def test_non_200_without_marker_is_retried():
    transport, session = make_transport([FakeResponse(404, "missing"), FakeResponse(200, "clean")])
    assert transport.get(URL) == "clean"
    assert len(session.calls) == 2


def test_network_error_is_retried_then_recovers():
    transport, session = make_transport(
        [RequestsError("timeout"), FakeResponse(200, "clean")]
    )
    assert transport.get(URL) == "clean"
    assert len(session.calls) == 2


def test_all_attempts_blocked_raises_transport_error():
    blocked = [FakeResponse(503, "Sorry! Something went wrong!") for _ in range(3)]
    transport, session = make_transport(blocked, max_attempts=3)
    with pytest.raises(TransportError, match="after 3 attempts"):
        transport.get(URL)
    assert len(session.calls) == 3


def test_defaults_leave_headroom_for_slow_links():
    """A search page is ~1 MB; a tight budget aborts mid-body."""
    transport = Transport()
    assert transport.timeout >= 20
    assert transport.max_attempts >= 4


def test_max_attempts_capped_by_profile_count():
    transport, _ = make_transport([], max_attempts=99)
    assert transport.max_attempts == len(IMPERSONATE_PROFILES)


def test_attempts_stop_at_max_attempts():
    transport, session = make_transport(
        [FakeResponse(503, "blocked")] * 10, max_attempts=2
    )
    with pytest.raises(TransportError):
        transport.get(URL)
    assert len(session.calls) == 2


def test_profiles_rotate_across_successful_requests():
    """Consecutive calls must not all present the same fingerprint."""
    transport, session = make_transport([FakeResponse(200, "a") for _ in range(3)])
    transport.get(URL)
    transport.get(URL)
    transport.get(URL)
    profiles = [kwargs["impersonate"] for _, kwargs in session.calls]
    assert len(set(profiles)) > 1, f"expected rotation, got {profiles}"


def test_backoff_grows_between_attempts(monkeypatch):
    slept = []
    monkeypatch.setattr("amazon_product_search.transport.time.sleep", slept.append)
    transport, _ = make_transport(
        [FakeResponse(503, "blocked")] * 3, backoff=0.5, max_attempts=3
    )
    with pytest.raises(TransportError):
        transport.get(URL)
    # No sleep after the final attempt: 3 attempts -> 2 gaps.
    assert slept == [0.5, 1.0]


def test_empty_profile_list_rejected():
    with pytest.raises(ValueError, match="profile"):
        Transport(profiles=[])


# ------------------------------------------------------------------- requests


def test_timeout_forwarded_to_every_attempt():
    transport, session = make_transport(
        [FakeResponse(503, "blocked"), FakeResponse(200, "clean")], timeout=7
    )
    transport.get(URL)
    assert all(kwargs["timeout"] == 7 for _, kwargs in session.calls)


def test_no_user_agent_header_is_sent():
    """A hand-written UA conflicting with the TLS fingerprint is a signal."""
    transport, _ = make_transport([FakeResponse()])
    assert "User-Agent" not in transport._headers
    assert "Accept-Language" in transport._headers


# ------------------------------------------------------------------ lifecycle


def test_close_is_idempotent_and_closes_session():
    transport = Transport()
    transport._session = FakeSession([])
    transport.close()
    assert transport._session is None
    transport.close()


def test_session_created_lazily_and_reused():
    transport = Transport()
    assert transport._session is None
    first = transport._get_session()
    assert transport._get_session() is first
    transport.close()


def test_default_construction_leaves_no_session_eagerly():
    """A Transport must not open a socket until the first request."""
    transport = Transport()
    assert transport._session is None
    assert transport._injected_session is None
    assert transport._async_sessions == {}


def test_injected_session_is_used_instead_of_a_real_one():
    session = FakeSession([FakeResponse(200, "clean")])
    transport = Transport(session=session)
    assert transport._get_session() is session
    assert transport.get(URL) == "clean"


# ---------------------------------------------------------------------- async


class FakeAsyncSession:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []
        self.closed = False

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else FakeResponse()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def close(self):
        self.closed = True


def make_async_transport(outcomes, **kwargs):
    session = FakeAsyncSession(outcomes)
    kwargs.setdefault("backoff", 0.0)
    return (
        Transport(async_session_factory=lambda: session, **kwargs),
        session,
    )


def test_async_get_returns_body():
    transport, session = make_async_transport([FakeResponse(200, "clean")])
    assert asyncio.run(transport.aget(URL)) == "clean"
    assert session.calls[0][1]["impersonate"] in IMPERSONATE_PROFILES


def test_async_retries_block_with_profile_rotation():
    transport, session = make_async_transport(
        [FakeResponse(503, "Sorry! Something went wrong!"), FakeResponse(200, "clean")]
    )
    assert asyncio.run(transport.aget(URL)) == "clean"
    profiles = [kwargs["impersonate"] for _, kwargs in session.calls]
    assert profiles[0] != profiles[1]


def test_async_network_error_is_retried_then_recovers():
    transport, session = make_async_transport(
        [RequestsError("timeout"), FakeResponse(200, "clean")]
    )
    assert asyncio.run(transport.aget(URL)) == "clean"
    assert len(session.calls) == 2


def test_async_non_200_without_marker_is_retried():
    transport, session = make_async_transport(
        [FakeResponse(404, "missing"), FakeResponse(200, "clean")]
    )
    assert asyncio.run(transport.aget(URL)) == "clean"
    assert len(session.calls) == 2


def test_async_exhausted_attempts_raise():
    transport, _ = make_async_transport(
        [FakeResponse(503, "blocked")] * 3, max_attempts=2
    )
    with pytest.raises(TransportError):
        asyncio.run(transport.aget(URL))


def test_async_backoff_is_awaited(monkeypatch):
    slept = []

    async def fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr("amazon_product_search.transport.asyncio.sleep", fake_sleep)
    session = FakeAsyncSession([FakeResponse(503, "blocked")] * 3)
    transport = Transport(
        backoff=0.25, max_attempts=3, async_session_factory=lambda: session
    )
    with pytest.raises(TransportError):
        asyncio.run(transport.aget(URL))
    assert slept == [0.25, 0.5]


def test_async_session_is_not_shared_across_event_loops():
    """A second asyncio.run() must not reuse sockets bound to the dead loop."""
    built = []

    def factory():
        session = FakeAsyncSession([FakeResponse(200, "clean")] * 4)
        built.append(session)
        return session

    transport = Transport(backoff=0.0, async_session_factory=factory)
    asyncio.run(transport.aget(URL))
    asyncio.run(transport.aget(URL))
    assert len(built) == 2, "a fresh loop must get a fresh session"
    assert built[0] is not built[1]

    # A second call inside the same loop reuses that loop's session.
    built.clear()

    async def twice():
        await transport.aget(URL)
        await transport.aget(URL)

    asyncio.run(twice())
    assert len(built) == 1, "sessions must be reused within one loop"


def test_aclose_closes_and_clears_sessions():
    transport = Transport()
    loop = asyncio.new_event_loop()
    try:
        fake = FakeAsyncSession([])
        transport._async_sessions[loop] = fake
        asyncio.run(transport.aclose())
        assert fake.closed is True
        assert transport._async_sessions == {}
    finally:
        loop.close()


def test_aclose_survives_a_failing_session():
    class Boom:
        async def close(self):
            raise RuntimeError("nope")

    transport = Transport()
    loop = asyncio.new_event_loop()
    try:
        transport._async_sessions[loop] = Boom()
        asyncio.run(transport.aclose())
        assert transport._async_sessions == {}
    finally:
        loop.close()