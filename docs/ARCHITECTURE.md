# Architecture

Single-package library split across focused modules:

| Module | Responsibility |
| --- | --- |
| `config.py` | `__version__`, `MAX_WORKERS` |
| `models.py` | `AmazonProduct`, `AmazonResult`, `PriceResult`, `ReviewResult` |
| `transport.py` | `Transport`: curl_cffi impersonation, block detection, retry/backoff; `is_blocked`, `IMPERSONATE_PROFILES`, `BLOCK_MARKERS` |
| `parsers.py` | `parse_html` (result divs), `parse_pagination` |
| `extractors.py` | `get_title`/`get_link`/`get_reviews`/`get_price`/`get_image`, `extract_data`, plus the `convert_review_to_number` and `split_currency_amount` helpers |
| `amazon_product_search.py` | `Amazon` client: request, `search()` orchestration, `__process_html` thread pool |

Parsers and extractors are pure module-level functions holding no client state, so they import and test directly.

(`Amazon`, `AmazonProduct`, `AmazonResult`, `__version__`).

## Request → parse → extract → return pipeline

`Amazon.search(productName, productType, brand, priceRange, page)`:

1. **Validate** — blank `productName` raises
   `ValueError("Error product Name is required")`.
2. **Build URL** — `urllib.parse.urlencode` over `{k, i, brand, price, page}`,
   dropping blank/`None` values. `page` is 1-indexed: `0`/`1` send **no**
   `page` param (first page); `>1` sends `?page=N`. Base is
   `https://www.amazon.com/s`.
3. **Request** — `Transport.get(url)`, which sends the request through
   `curl_cffi` while impersonating a real browser's TLS/HTTP2 fingerprint. A
   blocked attempt is retried under a different fingerprint; exhausting
   `max_attempts` raises `TransportError`, which the client turns into `""` and
   then `ValueError("Error while geting data from Amazon")`. See
   "Anti-bot transport" below.
4. **Parse products** — `BeautifulSoup(html, "lxml",
   parse_only=SoupStrainer("div", {"data-component-type": "s-search-result"}))`;
   only product divs are parsed (perf). Empty result → `[]` early exit.
5. **Parse pagination** — second `SoupStrainer` on
   `div[data-csa-c-content-id="pagination-button"]` with a full-parse
   fallback; reads `span.s-pagination-selected` (current) and max numeric
   `s-pagination-item` (total). See `SELECTORS.md`.
6. **Extract** — runs `extract_data` per div in a plain loop. Single-threaded on
   purpose: BeautifulSoup parsing holds the GIL, and a thread pool measured ~25%
   slower than the loop, so `workers` is accepted for backward compatibility but
   no longer drives extraction.
7. **Filter** — `None` results filtered out; products are returned in document order.
8. **Return** — `AmazonResult(products, current_page, total_pages)`.

## Module map

| Symbol | Role |
|---|---|
| `AmazonProduct` | Dataclass for one product; `.get()` → JSON-serialisable dict. `review_numbers: int \| None` (converted inside `get_reviews` by `convert_review_to_number`, incl. `k`/`m`/`b` suffixes: `"1.2K"` → `1200`); `price: float \| None` (converted inside `get_price`, commas stripped). Missing review text → `review is None`; missing count (block present) → `0`; no reviews-block → both stay `None`. |
| `AmazonResult` | `products` + `current_page` + `total_pages`; iterable/`len()`/indexable proxying `products`; `.get()` for JSON. |
| `PriceResult` / `ReviewResult` | `TypedDict`s for the `get_price` / `get_reviews` return shapes (`ReviewResult` is `total=False`: `review` may be absent). |
| `Amazon` | Transport owner (`close()`/`aclose()` + sync/async context managers), URL builder, orchestrator. Network and thread-pool helpers stay private (`_Amazon__amazon_request`, `_Amazon__process_html`). |
| `Transport` | Sole network boundary — the seam all offline tests stub. Owns curl_cffi sessions (sync + per-loop async), profile rotation, block detection, backoff. Raises `TransportError` when a URL is unrecoverable. |
| `is_blocked` | `module function`: body → "is this a bot challenge?". Status is checked by the caller, not here. |
| `__amazon_request` / `__async_request` | Thin adapters: `Transport.get`/`aget` → HTML or `""` (logging `TransportError`). |
| `parse_html` / `parse_pagination` | HTML → divs / (current, total). Pagination holds most branching logic. |
| `convert_review_to_number` | `module function`: `"1234"` → `1234`, `"1.2K"` → `1200`, `"3M"` → `3000000`, `"1B"` → `1000000000` (case-insensitive suffix); garbage/empty → `0`. Unit-tested in `test_convert_review_to_number`. |
| `split_currency_amount` | `module function`: classifies each NBSP side via `float()` (parseable → amount, else currency). |
| `__process_html` / `extract_data` | Thread fan-out + per-div field aggregation. |
| `get_title/link/reviews/price/image` | One selector-anchored extractor each; all return `None` on missing markup (never raise on absent fields). |

## Anti-bot transport

Amazon's bot filter keys on the **TLS ClientHello and HTTP/2 SETTINGS frame**,
not just headers. `requests`/`httpx` present Python's fingerprint, so
`/s` returns a `503` "Sorry! Something went wrong!" page (or a `200`
interstitial carrying `bm-verify`) that parses to zero products. `curl_cffi`
spoofs a genuine browser fingerprint, which is what actually fixes it.

`transport.py` adds two things on top of impersonation:

- **Block detection.** `is_blocked()` checks status *and* body markers
  (`BLOCK_MARKERS`). Status alone is not enough: the `bm-verify` interstitial
  arrives as `200`.
- **Profile rotation with backoff.** Attempts rotate through
  `IMPERSONATE_PROFILES` (Chrome + Safari generations). Blocks follow the
  fingerprint rather than the URL, so rotating is what recovers. Backoff is
  exponential: `backoff * 2**index`, no sleep after the final attempt.

Choices worth knowing before you change them:

- **No `User-Agent` header is sent.** With impersonation active, a hand-written
  UA that disagrees with the TLS fingerprint is itself a detection signal;
  curl_cffi supplies a matching one. Only `Accept-Language` is set.
- **Do not add a homepage warm-up.** Fetching `/` first seeds a session cookie
  and measurably *raises* the interstitial rate on subsequent `/s` requests.
- **Async sessions are cached per event loop.** curl_cffi's `AsyncSession`
  registers sockets with the loop that created it, so reusing one across a
  second `asyncio.run()` raises `RuntimeError: Event loop is closed`. Keying the
  cache on the running loop is what makes repeated `asyncio.run(...)` calls and
  the existing test suite work. `aclose()` must be awaited from a live loop,
  which is why `__aexit__` is async; `close()` remains the sync path.
- **`timeout` defaults to 20, not 10.** A search page is ~1 MB; a tighter budget
  aborts mid-body ("timed out with N bytes received") on slow links and turns a
  good response into a retry. `max_attempts` defaults to 4 because DNS/connect
  blips are transient and need more than one shot to clear.
- **Fingerprints are version-sensitive.** Some profiles work and others do not
  depending on Amazon's current filter state — measured on the same IP, the
  same URL: `chrome124`/`safari184` return results while `chrome136` and
  `firefox144` were blocked. Keep several in the list so one going stale is
  survivable, and re-measure with `AMZN_LIVE=1 pytest -m live` rather than
  assuming.

## Design notes for contributors

- **Session reuse** is load-bearing for perf (avoids a TLS handshake per
  search). Always go through `Transport`; `Amazon.session` proxies it.
- **`__process_html` has no per-future error handling, so a raising extractor
  would fail the whole search. Guard with `if not div / if not node: return None`.
- **`get_price` never raises:** amounts parse via `float()` with `0.0`
  fallback; NBSP sides are classified by `split_currency_amount`
  (float-parseable → amount, else currency). Lesson learned: do **not**
  use `str.isnumeric()` for numeric detection — it rejects decimals
  (`"19.99".isnumeric()` is `False`), which once turned every normal price
  into `0.0`. Covered by `test_get_price_*` and `test_split_currency_amount`.
- **`get_price` NBSP subtlety:** `get_text(strip=True)` strips each text
  node, so the `currency\u00a0amount` split only survives when the NBSP is
  *interior* to the joined text. Multi-child markup with no parseable amount
  (e.g. `<b>Rs</b><i>499</i>` → `"Rs499"`) degrades to `price=0.0` instead of
  raising. Covered by `test_get_price_secondary_nested_text`.
- **`parse_pagination` defensive guards** (`total < current`, `total < 1`)
  are near-unreachable with well-formed markup; `total < 1` is currently
  uncovered by tests (see `TESTING.md`).
