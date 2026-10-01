"""async_search(): parity with search(), real I/O overlap, and error handling."""

import asyncio
import time

from amazon_product_search import Amazon

from .conftest import SEARCH_PAGE_HTML


def _patch_async_get(amazon, text=SEARCH_PAGE_HTML, delay=0.0):
    """Patch the async transport with a canned response."""
    calls = []

    async def fake_aget(url):
        calls.append(url)
        if delay:
            await asyncio.sleep(delay)
        return text

    amazon.transport.aget = fake_aget
    return calls


def test_async_search_matches_sync(amazon):
    """Same criteria must yield the same products as the sync path."""
    amazon._Amazon__amazon_request = lambda url: SEARCH_PAGE_HTML
    calls = _patch_async_get(amazon)

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


def test_async_search_blank_name_raises(amazon):
    """Blank productName keeps the sync path's validation error."""
    _patch_async_get(amazon)
    try:
        asyncio.run(amazon.async_search("   "))
    except ValueError as error:
        assert "product Name is required" in str(error)
    else:
        raise AssertionError("expected ValueError for blank productName")


def test_async_search_transport_failure_raises(amazon):
    """A transport failure is surfaced as ValueError, not leaked."""
    from amazon_product_search import TransportError

    async def boom(url):
        raise TransportError("blocked after 3 attempts")

    amazon.transport.aget = boom
    try:
        asyncio.run(amazon.async_search("thinkpad"))
    except ValueError as error:
        assert "while geting data" in str(error)
    else:
        raise AssertionError("expected ValueError when the transport gives up")


def test_concurrent_searches_overlap(amazon):
    """5 gathered searches must take ~1 delay, not 5."""
    _patch_async_get(amazon, delay=0.1)

    async def run():
        return await asyncio.gather(*(amazon.async_search(f"item{i}") for i in range(5)))

    start = time.perf_counter()
    results = asyncio.run(run())
    elapsed = time.perf_counter() - start

    assert len(results) == 5
    assert all(len(r.products) == 2 for r in results)
    # Serial would be >=0.5s; overlapped should be well under that.
    assert elapsed < 0.35, f"searches did not overlap: {elapsed:.3f}s"


def test_event_loop_not_blocked_during_parse(amazon):
    """A large parse must not stall other coroutines, proving parsing is off-loop."""
    big = SEARCH_PAGE_HTML.replace(
        "</body></html>", SEARCH_PAGE_HTML.split("<body>")[1].split("</body>")[0] * 40
    )
    _patch_async_get(amazon, text=big)

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


def test_repeated_asyncio_run_calls_are_safe(amazon):
    """The async session is per-loop; a second asyncio.run must still work."""
    _patch_async_get(amazon)

    first = asyncio.run(amazon.async_search("item1"))
    second = asyncio.run(amazon.async_search("item2"))
    assert len(first.products) == 2
    assert len(second.products) == 2


def test_async_context_manager_closes(amazon):
    _patch_async_get(amazon)

    async def run():
        async with amazon as client:
            await client.async_search("thinkpad")
        assert amazon.transport._async_sessions == {}

    asyncio.run(run())