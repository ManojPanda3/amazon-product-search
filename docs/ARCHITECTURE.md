# Architecture

Single-package library split across focused modules:

| Module | Responsibility |
| --- | --- |
| `config.py` | `__version__`, `MAX_WORKERS` |
| `models.py` | `AmazonProduct`, `AmazonResult`, `PriceResult`, `ReviewResult` |
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
3. **Request** — `requests.Session.get(url, timeout=10)` on a persistent
   session (keep-alive, shared `User-Agent`/`Accept-Language` headers).
   Non-200 status or `requests.RequestException` → `""`, which `search()`
   converts to `ValueError("Error while geting data from Amazon")`.
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
| `Amazon` | Session owner (`close()` + context-manager support), URL builder, orchestrator. Network and thread-pool helpers stay private (`_Amazon__amazon_request`, `_Amazon__process_html`). |
| `__amazon_request` | Sole network boundary — the seam all offline tests mock. |
| `parse_html` / `parse_pagination` | HTML → divs / (current, total). Pagination holds most branching logic. |
| `convert_review_to_number` | `module function`: `"1234"` → `1234`, `"1.2K"` → `1200`, `"3M"` → `3000000`, `"1B"` → `1000000000` (case-insensitive suffix); garbage/empty → `0`. Unit-tested in `test_convert_review_to_number`. |
| `split_currency_amount` | `module function`: classifies each NBSP side via `float()` (parseable → amount, else currency). |
| `__process_html` / `extract_data` | Thread fan-out + per-div field aggregation. |
| `get_title/link/reviews/price/image` | One selector-anchored extractor each; all return `None` on missing markup (never raise on absent fields). |

## Design notes for contributors

- **Session reuse** is load-bearing for perf (avoids a TLS handshake per
  search). Always go through `self.session`; tests assert the default headers.
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
