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


def test_live_blocked_response_is_retried_not_returned_as_empty():
    """A bot challenge must never reach the parser as empty products.

    Checks the classification itself: whatever the network does, the transport
    must never hand back a body containing a challenge marker as if it were a
    result page. Runs several queries so a live block is actually exercised.
    """
    _require_live()
    from amazon_product_search.transport import is_blocked

    with Amazon(workers=2) as amazon:
        for query in ("thinkpad", "macbook pro", "usb-c hub"):
            html = amazon.transport.get(f"https://www.amazon.com/s?k={query.replace(' ', '+')}")
            assert not is_blocked(html), f"challenge page leaked through for {query!r}"
            assert "s-search-result" in html