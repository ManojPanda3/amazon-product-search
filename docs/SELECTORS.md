# Selector contract

Amazon markup changes without notice — these tables are the contract between
the library and Amazon's search-results/detail-page HTML. When scraping breaks,
start here. Each row: logical field → anchor → missing-markup behaviour.

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

## Detail-page fields (`AmazonProduct.deep_scrape`)

The detail page is parsed by `models.py` into a fixed schema. Every field is
optional; missing markup yields `None` / `[]` / `{}` rather than a missing key.
The page source can be a real URL, a local file path in `link`, or explicit
HTML passed as `deep_scrape(html=...)`.

| Field | Anchor(s) | Notes |
|---|---|---|
| `title` | `#productTitle`, `#title`, `meta[property="og:title"]` | first non-empty |
| `asin` | `input[name="ASIN"]`, `[data-asin]`, `/dp/<ASIN>` in link/canonical | 10-char alphanumeric |
| `brand` | `#bylineInfo`, `#visitStoreLink`, `#pqv-byline`, logo `alt`, spec tables | strips "Visit the … Store"/"Brand:" |
| `link` | HTTP(S) `link`, else canonical/`og:url` | `None` for local HTML without canonical |
| `breadcrumbs` | `#wayfinding-breadcrumbs_feature_div a` | deduplicated, `›` dropped |
| `price` / `price_value` / `currency` | `_PRICE_SELECTORS`: `#corePriceDisplay_desktop_feature_div .a-price .a-offscreen`, `#corePrice_feature_div …`, `#apex_desktop …`, `#buybox …`, `#price_inside_buybox`, legacy `#priceblock_*`, `#newBuyBoxPrice`, `#tp_price_block_total_price_ww .a-offscreen`, `#booksHeaderSection .a-color-price`, then `#priceSymbol` for currency | `price` keeps display text, `price_value` is a float; `currency` can exist without a price |
| `availability` | `#availability`, `#outOfStockBuyBox_feature_div`, `#availability_feature_div` | first non-empty |
| `rating` | `#acrPopover[title]`, `.a-icon-alt`, `[data-hook="rating-out-of-text"]` | parsed from "N out of 5" |
| `review_count` | `#acrCustomerReviewText`, `#acrCustomerReviewLink`, `[data-hook="total-review-count"]` | `(1,234)` / `1.2K` → int |
| `features` | `#feature-bullets li` | deduplicated |
| `product_details` | `#detailBullets_feature_div ul.detail-bullet-list > li` | bold label + value pairs |
| `specifications` | `#productOverview_feature_div`, `#productDetails_*`, `#technicalSpecifications_section_1`, `table.a-keyvalue tr` | key/value tables; feedback table excluded |
| `best_sellers_rank` | "Best Sellers Rank" from either mapping | split on `#N in …` |
| `main_image` / `images` | `#landingImage`, `og:image`, `colorImages` script JSON, dynamic image map, `#altImages img` | absolute URLs, deduplicated; main image first |
| `variations` | `script[data-a-state]` key `desktop-twister-sort-filter-data` | one dict per value: `dimension`, `value`, `asin`, `selected`, `state`, `available`, `price`, `price_value`, `image`, `url` |

Notes:

- `_clean_text` removes Amazon's invisible direction marks (U+200E/U+200F)
  and normalises NBSPs (U+00A0) before labels/values are compared.
- Detail bullets are label/value pairs from the `a-text-bold` span; the value
  is the remaining text of the `<li>`. "Customer Reviews" is skipped there
  because rating/count are parsed separately.
- Specification keys are category-specific (`Brand Name`, `Item model number`,
  `Product Dimensions`, `Best Sellers Rank`, …), so they stay in a dictionary
  instead of becoming top-level fields.
- `price` and `price_value` are separate on purpose: prices can be missing,
  non-numeric, or formatted for a locale. `price_value` is `None` when no
  numeric amount is present.
- `variations` comes from the twister state JSON, not from the rendered swatch
  markup, so it survives lazy-loaded widgets.
- `AmazonProductDetails.get()` always returns the same 18 keys.

## How to update selectors when Amazon changes markup

1. Save a failing sample (synthetic, minimal — do **not** commit full
   scraped pages).
2. Add it as a fixture in `tests/conftest.py` (search) or
   `tests/test_details.py` (detail page) and a regression test in the
   corresponding test module.
3. Update the extractor/parser + this table in the same PR.
4. Run `pytest -m "not live"` + `coverage report --include="amazon_product_search/*"`.
