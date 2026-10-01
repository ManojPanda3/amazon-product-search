"""async_search(): parity with search(), real I/O overlap, and error handling."""

import asyncio
import time

import httpx
import pytest

from amazon_product_search import Amazon

from .conftest import SEARCH_PAGE_HTML


def _patch_async_get(monkeypatch, status_code=200, text=SEARCH_PAGE_HTML, delay=0.0):
    """Patch the async request path with a stub httpx client."""
    calls = []

    async def fake_get(self, url, **kwargs):
        calls.append(url)
        if delay:
            await asyncio.sleep(delay)
        return httpx.Response(status_code, text=text, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return calls


def test_async_search_matches_sync(amazon, monkeypatch):
    """Same criteria must yield the same products as the sync path."""
    monkeypatch.setattr(
        "amazon_product_search.amazon_product_search.Amazon._Amazon__amazon_request",
        lambda self, url: SEARCH_PAGE_HTML,
    )
    calls = _patch_async_get(monkeypatch)

    sync_result = amazon.search("thinkpad", productType="electronics", page=2)
    async_result = asyncio.run(
        amazon.async_search("thinkpad", productType="electronics", page=2)
    )

    assert calls, "async path did not perform a request"
    assert sync_result.current_page == async_result.current_page
    assert sync_result.total_pages == async_result.total_pages
    assert [p.title for p in sync_result.products] == [
        p.title for p in async_result.products
    ]
    assert [p.price for p in async_result.products] == [19.99, 29.99]


def test_async_search_blank_name_raises(amazon, monkeypatch):
    """Blank productName keeps the sync path's validation error."""
    _patch_async_get(monkeypatch)
    with pytest.raises(ValueError, match="product Name is required"):
        asyncio.run(amazon.async_search("   "))


def test_async_search_non_200_raises(amazon, monkeypatch):
    """A non-200 response raises rather than returning empty results."""
    _patch_async_get(monkeypatch, status_code=503, text="nope")
    with pytest.raises(ValueError, match="while geting data"):
        asyncio.run(amazon.async_search("thinkpad"))


def test_async_search_network_error_raises(amazon, monkeypatch):
    """A transport failure is logged and surfaced as ValueError, not an httpx error."""

    async def boom(self, url, **kwargs):
        raise httpx.ConnectError("no route to host", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    with pytest.raises(ValueError, match="while geting data"):
        asyncio.run(amazon.async_search("thinkpad"))


def test_concurrent_searches_overlap(amazon, monkeypatch):
    """5 gathered searches must take ~1 delay, not 5."""
    _patch_async_get(monkeypatch, delay=0.1)

    async def run():
        return await asyncio.gather(*(amazon.async_search(f"item{i}") for i in range(5)))

    start = time.perf_counter()
    results = asyncio.run(run())
    elapsed = time.perf_counter() - start

    assert len(results) == 5
    assert all(len(r.products) == 2 for r in results)
    # Serial would be >=0.5s; overlapped should be well under that.
    assert elapsed < 0.35, f"searches did not overlap: {elapsed:.3f}s"


def test_event_loop_not_blocked_during_parse(amazon, monkeypatch):
    """A large parse must not stall other coroutines, proving parsing is off-loop."""
    big = SEARCH_PAGE_HTML.replace(
        "</body></html>", SEARCH_PAGE_HTML.split("<body>")[1].split("</body>")[0] * 40
    )
    _patch_async_get(monkeypatch, text=big)

    ticks = 0
    running = True

    async def ticker():
        nonlocal ticks
        while running:
            ticks += 1
            await asyncio.sleep(0.001)

    async def run():
        nonlocal running
        t = asyncio.create_task(ticker())
        results = await asyncio.gather(*(amazon.async_search(f"item{i}") for i in range(4)))
        running = False
        await t
        return results

    results = asyncio.run(run())
    assert len(results) == 4
    assert ticks > 0, "event loop was blocked during parsing"