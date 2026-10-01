# Selector contract

Amazon markup changes without notice — this table is the contract between
the library and Amazon's search-results HTML. When scraping breaks, start
here. Each row: logical field → anchor → missing-markup behaviour.

## Product fields (`div[data-component-type="s-search-result"]` scope)

| Field | Anchor | Missing behaviour |
|---|---|---|
| `title` | `div[data-cy="title-recipe"] > h2 > span` (`.string`) | `None` |
| `link` | `span[data-component-type="s-product-image"] > a[href]` → `https://www.amazon.com{href}` | `None` |
| `review` | `div[data-cy="reviews-block"] span.a-size-small.a-color-base[aria-hidden="true"]` (`.string`) | key absent → `None` (`.get("review")` default); no block → `None` (untouched) |
| `review_numbers` | `div[data-cy="reviews-block"] span[data-component-type="s-client-side-analytics"] > span[aria-hidden="true"]`; strip commas, strip one surrounding paren pair (`"(1,234)"` → `"1234"`), then `convert_review_to_number` → `int` (`"1.2K"` → `1200`, `k`/`m`/`b`, case-insensitive) | missing/empty (block present) → `0`; no block → `None` (untouched) |
| `price` / `currency` | tried in order: `div[data-cy="price-recipe"] span.a-offscreen`, then `div[data-cy="secondary-offer-recipe"] span.a-color-base`; commas stripped; NBSP split classified per-side by `float()` (`"$"` + `"19.99"` → `currency="$"`, `price=19.99`); no-NBSP text → `float()` with `currency=""`; anything non-numeric → `price=0.0` (never raises) | `None` (whole dict) when no price node |
| `image` | `img.s-image[src]` | `None` |

Notes:

- `.string` is `None` when a span has nested markup; `get_price` falls
  back to `get_text(strip=True)` in that case (see `ARCHITECTURE.md`).
- `review_numbers` paren-stripping assumes at most one surrounding pair;
  a bare `"5"` converts to int `5` via `convert_review_to_number`.

## Pagination (`div[data-csa-c-content-id="pagination-button"]` scope)

```html
<div data-csa-c-content-id="pagination-button">
  <span class="s-pagination-item s-pagination-selected" aria-current="page">1</span>
  <a class="s-pagination-item s-pagination-button" href="#">2</a>
  <a class="s-pagination-item s-pagination-button" href="#">3</a>
  <span class="s-pagination-item s-pagination-disabled">20</span>
</div>
```

- **Current:** `span.s-pagination-selected` text; pure digits → `int`,
  else first `\d+` regex match; absent → requested `page` (fallback `1`).
- **Total:** max numeric text over all `a/span.s-pagination-item`;
  non-numeric items (`Next`/`Previous`) ignored; no numbers → `current`.
- **No widget at all:** `(fallback, fallback)` where fallback is the
  requested page (`1` when `page` is `0`/unset).
- Guards: `total` is clamped up to `current`; minimum `1`.

## How to update selectors when Amazon changes markup

1. Save a failing sample (synthetic, minimal — do **not** commit full
   scraped pages).
2. Add it as a fixture in `tests/conftest.py` and a regression test in
   `tests/test_extractors.py` (or `test_pagination.py`) asserting the
   expected field values.
3. Update the extractor + this table in the same PR.
4. Run `pytest -m "not live"` + `coverage report --include="amazon_product_search/*"`.
