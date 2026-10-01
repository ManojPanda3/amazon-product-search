"""Live smoke tests — SKIPPED by default (needs network + Amazon reachability).

Run explicitly with: AMZN_LIVE=1 pytest tests/test_live.py -q -m live
"""

from __future__ import annotations

import asyncio
import os

import pytest

from amazon_product_search import Amazon, AmazonResult

pytestmark = pytest.mark.live


def _live_enabled() -> bool:
    return os.getenv("AMZN_LIVE") == "1" or os.getenv("PYTEST_RUN_LIVE") == "1"


def _require_live() -> None:
    if not _live_enabled():
        pytest.skip("live test opt-in only (AMZN_LIVE=1)")


def test_live_search_smoke():
    """Sync search must return real products, not a bot-challenge page."""
    _require_live()
    with Amazon(workers=2) as amazon:
        result = amazon.search("thinkpad", productType="electronics", page=1)
    assert isinstance(result, AmazonResult)
    assert len(result.products) > 0, "no products parsed — likely a block page"
    assert result.current_page >= 1
    assert result.total_pages >= result.current_page
    assert any(p.title for p in result.products)


def test_live_async_search_smoke():
    """Async path must behave like sync against real Amazon."""
    _require_live()

    async def run():
        async with Amazon() as amazon:
            return await asyncio.gather(
                amazon.async_search("thinkpad", productType="electronics", page=1),
                amazon.async_search("thinkpad", productType="electronics", page=2),
            )

    first, second = asyncio.run(run())
    assert len(first.products) > 0, "page 1 blocked"
    assert len(second.products) > 0, "page 2 blocked"
    assert second.current_page == 2


def test_live_repeated_searches_stay_unblocked():
    """Several sequential searches must not trip the bot filter.

    This is the regression guard for the original bug: plain requests/httpx got
    Amazon's 503 "Sorry! Something went wrong!" page on the very first call.
    """
    _require_live()
    with Amazon(workers=2) as amazon:
        for query in ("thinkpad", "macbook", "logitech mouse"):
            result = amazon.search(query)
            assert len(result.products) > 0, f"blocked on query {query!r}"


def test_live_blocked_response_is_never_returned_as_html():
    """A bot challenge must never reach the parser as if it were results.

    The invariant is a property of the *code*, not of Amazon's mood: a call must
    either return clean result HTML or raise ``TransportError``. It must never
    hand back a challenge page.

    Deliberately does not assert that the request succeeded. Amazon blocks real
    IPs intermittently, and a test that fails when the network misbehaves tests
    Amazon rather than this library.
    """
    _require_live()
    from amazon_product_search import TransportError
    from amazon_product_search.transport import is_blocked

    outcomes = {"clean": 0, "blocked": 0}
    with Amazon(workers=2) as amazon:
        for query in ("thinkpad", "macbook pro", "usb-c hub"):
            url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
            try:
                html = amazon.transport.get(url)
            except TransportError:
                # The correct outcome: retries exhausted, caller told it failed.
                outcomes["blocked"] += 1
                continue
            assert not is_blocked(html), f"challenge page leaked through for {query!r}"
            assert "s-search-result" in html, f"unexpected body shape for {query!r}"
            outcomes["clean"] += 1

    assert outcomes["clean"] or outcomes["blocked"], "no live requests were made"