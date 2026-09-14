# Architecture

Single-module library: everything lives in
`amazon_product_search/amazon_product_search.py` (~530 lines).
Public API is re-exported from `amazon_product_search/__init__.py`
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
6. **Extract concurrently** — `ThreadPoolExecutor(max_workers=self.workers)`
   runs `__extract_data` per div (`workers` defaults to `MAX_WORKERS =
   (os.cpu_count() or 4) // 2`, override via `Amazon(workers=N)`).
   `None` results are filtered out; result order is completion order
   (not document order).
7. **Return** — `AmazonResult(products, current_page, total_pages)`.

## Module map

| Symbol | Role |
|---|---|
| `AmazonProduct` | Dataclass for one product; `.get()` → JSON-serialisable dict. `review_numbers: int \| None` (converted inside `__get_reviews` by `__convert_review_to_number`, incl. `k`/`m`/`b` suffixes: `"1.2K"` → `1200`); `price: float \| None` (converted inside `__get_price`, commas stripped). Missing review text → `review is None`; missing count (block present) → `0`; no reviews-block → both stay `None`. |
| `AmazonResult` | `products` + `current_page` + `total_pages`; iterable/`len()`/indexable proxying `products`; `.get()` for JSON. |
| `PriceResult` / `ReviewResult` | `TypedDict`s for the `__get_price` / `__get_reviews` return shapes (`ReviewResult` is `total=False`: `review` may be absent). |
| `Amazon` | Session owner (`close()` + context-manager support), URL builder, orchestrator. All parsing helpers are private (`_Amazon__*`). |
| `__amazon_request` | Sole network boundary — the seam all offline tests mock. |
| `__parse_html` / `__parse_pagination` | HTML → divs / (current, total). Pagination holds most branching logic. |
| `__convert_review_to_number` | `@staticmethod`: `"1234"` → `1234`, `"1.2K"` → `1200`, `"3M"` → `3000000`, `"1B"` → `1000000000` (case-insensitive suffix); garbage/empty → `0`. Unit-tested in `test_convert_review_to_number`. |
| `__split_currency_amount` | `@staticmethod`: classifies each NBSP side via `float()` (parseable → amount, else currency). |
| `__process_html` / `__extract_data` | Thread fan-out + per-div field aggregation. |
| `__get_title/link/reviews/price/image` | One selector-anchored extractor each; all return `None` on missing markup (never raise on absent fields). |

## Design notes for contributors

- **Session reuse** is load-bearing for perf (avoids a TLS handshake per
  search). Always go through `self.session`; tests assert the default headers.
- **`__process_html` has no per-future error handling, so a raising extractor
  would fail the whole search. Guard with `if not div / if not node: return None`.
- **`__get_price` never raises:** amounts parse via `float()` with `0.0`
  fallback; NBSP sides are classified by `__split_currency_amount`
  (float-parseable → amount, else currency). Lesson learned: do **not**
  use `str.isnumeric()` for numeric detection — it rejects decimals
  (`"19.99".isnumeric()` is `False`), which once turned every normal price
  into `0.0`. Covered by `test_get_price_*` and `test_split_currency_amount`.
- **`__get_price` NBSP subtlety:** `get_text(strip=True)` strips each text
  node, so the `currency\u00a0amount` split only survives when the NBSP is
  *interior* to the joined text. Multi-child markup with no parseable amount
  (e.g. `<b>Rs</b><i>499</i>` → `"Rs499"`) degrades to `price=0.0` instead of
  raising. Covered by `test_get_price_secondary_nested_text`.
- **`__parse_pagination` defensive guards** (`total < current`, `total < 1`)
  are near-unreachable with well-formed markup; `total < 1` is currently
  uncovered by tests (see `TESTING.md`).
