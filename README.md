# 🛍️ Amazon Product Search Library 📦

## Overview

Tired of manually browsing Amazon for the best deals? 🌐 Meet **Amazon Product Search** — your trusty Python library to scrape product listings and detail pages from Amazon with just a few lines of code. Powered by **curl_cffi** browser impersonation (so Amazon's bot filter doesn't return a 503 error page) and **BeautifulSoup4 (bs4)** for parsing, with optional **async** requests for speed. 🎉

### Key Features

- **Product Search:** Search for products by name, type, brand, and price range. 📱💻
- **Detailed Data:** Scrape titles, prices (+currency), reviews (+count), images, and URLs. 🎯
- **Deep Scrape:** Fetch a product detail page for brand, rating, availability, feature bullets, specs, gallery images, and variations through a stable, generalized schema. 🕵️
- **Pagination:** Navigate Amazon pages via `page` param and get `current_page` / `total_pages` from `data-csa-c-content-id="pagination-button"`. 📄
- **Fast and Efficient:** Session reuse (keep-alive), `SoupStrainer` partial parsing, and optional `async_search()` for overlapping network I/O.
- **Anti-bot:** Ships `curl_cffi` TLS/HTTP2 browser impersonation with automatic profile rotation and retry, so Amazon's "Sorry! Something went wrong!" 503 page doesn't reach you. 🛡️
- **Easy-to-use:** Simple API + context-manager + backward-compatible iteration. ✨
- **Lightweight & Compatible:** Python 3.9–3.14, relaxed deps (`beautifulsoup4>=4.11`, `curl_cffi>=0.13`, `lxml>=4.9`). No heavy frameworks.

## Setup 🛠️

### 1. Install via PyPI (Recommended) 🧑‍💻

```bash
pip install amazon-product-search-v2
```

Installs the latest stable release. **Package name on PyPI is `amazon-product-search-v2`**.

### 2. Install via GitHub (For Developers) 🦸‍♂️

```bash
git clone --depth 1 https://github.com/ManojPanda3/amazon-product-search
cd amazon-product-search
pip install -e .
# or with venv: python -m pip install -e .
```

## Usage 📚

### Import

```python
from amazon_product_search import (
    Amazon,
    AmazonProduct,
    AmazonProductDetails,
    AmazonResult,
)
# Package is amazon-product-search-v2 on PyPI, but import stays amazon_product_search
```

### Basic Search

```python
from amazon_product_search import Amazon

# Session is reused across searches (keep-alive). Use as context manager to auto-close.
with Amazon() as amazon:
    result = amazon.search("thinkpad", productType="electronics", page=1)
    # or: amazon = Amazon(); result = amazon.search(...); amazon.close()

print(result.current_page, "/", result.total_pages)
for prod in result.products:
    print(prod.title, prod.price, prod.currency)
    print(prod.get())  # dict with title/link/review/review_numbers/currency/price/image
```

Or one-off:

```python
amazon = Amazon(is_debuging=False, workers=4)
result = amazon.search(productName="iPhone", productType="electronics", brand="Apple", priceRange="80000-100000", page=2)
# result is AmazonResult — also iterable/len-compatible
print(len(result))          # == len(result.products)
for product in result:      # iterates products directly
    print(product.get())
```

### Deep-scrape a product page 🕵️

`AmazonProduct.deep_scrape()` fetches a product detail page and returns an
`AmazonProductDetails` object. Amazon renders different widgets for different
products, so the result uses one **generalized schema**: missing scalars are
`None`, missing lists are `[]`, and missing mappings are `{}` — the keys are
always present.

```python
from amazon_product_search import AmazonProduct

product = AmazonProduct(link="https://www.amazon.com/dp/B073CWSQ51")
details = product.deep_scrape()

print(details.title, details.brand, details.rating)
print(details.price, details.price_value, details.currency)
print(details.availability)
print(details.features)
print(details.specifications)   # {"Brand Name": "COLOR WOW", ...}
print(details.product_details)  # {"Item model number": "CW527", ...}
print(details.images)
print(details.variations)       # size/colour options with ASIN + price
print(details.get())            # JSON-serialisable dict
```

Fields:

| Group | Fields |
|---|---|
| Identity | `asin`, `title`, `brand`, `link`, `breadcrumbs` |
| Offer | `price` (display string), `price_value` (float), `currency`, `availability` |
| Social proof | `rating`, `review_count`, `best_sellers_rank` |
| Content | `features`, `specifications`, `product_details` |
| Media | `main_image`, `images` |
| Variations | `variations` (`dimension`, `value`, `asin`, `selected`, `available`, `price`, `price_value`, `image`, `url`) |

Notes:

- `price` is the display string Amazon rendered (for example `"$1,299.99"`);
  use `price_value` when you need a float. A page can provide a currency symbol
  without a buy-box price, so `currency` may be set while both price fields are
  `None`.
- `specifications` and `product_details` are free-form key/value maps because
  every category uses different labels. Common keys include `Brand Name`,
  `Item model number`, `Product Dimensions`, and `Best Sellers Rank`.
- `get()` always returns the same keys, so the result can be serialized
  directly to JSON.

Saved HTML and local files are supported, which is handy for tests:

```python
details = product.deep_scrape(html=saved_html)
# or point the product at a file
details = AmazonProduct(link="/path/to/product.html").deep_scrape()
```

### Async Search (overlapping network I/O) 🐍

Searching Amazon is dominated by network wait, so `async_search()` lets you run several searches at once. It performs one search per call; batch them yourself with `asyncio.gather()` or a task group.

```python
import asyncio
from amazon_product_search import Amazon

async def main():
    async with Amazon() as amazon:
        results = await asyncio.gather(
            amazon.async_search("thinkpad", productType="electronics"),
            amazon.async_search("macbook air"),
            amazon.async_search("dell xps"),
        )
    for result in results:
        print(result.current_page, len(result.products))

asyncio.run(main())
```

Notes:
- `async_search()` takes the same parameters and returns the same `AmazonResult` as `search()`.
- Parsing runs off the event loop, so one large page won't stall your other searches.
- Non-200 responses and network failures are logged and raise `ValueError`, matching `search()`.

### Parameters for `search()`

- `productName` (str, **required**): Search term (e.g. `"thinkpad"`, `"laptop"`).
- `productType` (str, optional): `i` filter (e.g. `"electronics"`, `"books"`).
- `brand` (str, optional): Brand filter.
- `priceRange` (str, optional): `"min-max"` (e.g. `"100-200"`).
- `page` (int, optional, default `0`): **New in v0.1.2** — 1-indexed page. `0` or `1` = first page (no `page` param sent), `2` → `?page=2`.

### Returns

`AmazonResult` dataclass:

```python
@dataclass
class AmazonResult:
    products: list[AmazonProduct]
    current_page: int
    total_pages: int
    def get() -> dict: ...  # {products: [...], current_page, total_pages}
```

Each `AmazonProduct`:

```python
@dataclass
class AmazonProduct:
    title: str | None
    link: str | None          # https://www.amazon.com/dp/...
    review: str | None        # "4.5 out of 5 stars" (None when missing)
    review_numbers: int | None # 1234 (parentheses stripped; k/m/b suffixes converted)
    price: float | None        # 12.99 (commas stripped)
    currency: str | None      # "$" / "₹" etc. (split on \u00a0)
    image: str | None
    def get() -> dict: ...
```

Backward compat: `for p in result`, `len(result)`, `result[i]` all proxy to `result.products`.

`AmazonProduct.deep_scrape()` returns `AmazonProductDetails`:

```python
@dataclass
class AmazonProductDetails:
    asin: str | None
    title: str | None
    brand: str | None
    link: str | None
    breadcrumbs: list[str]
    price: str | None          # display text, e.g. "$1,299.99"
    price_value: float | None  # parsed numeric value
    currency: str | None
    availability: str | None
    rating: float | None
    review_count: int | None
    best_sellers_rank: list[str]
    features: list[str]
    specifications: dict[str, str]
    product_details: dict[str, str]
    main_image: str | None
    images: list[str]
    variations: list[dict]
    def get() -> dict: ...     # same keys for every product
```

### Examples

#### Paginated search (new syntax)

```python
from amazon_product_search import Amazon
import json

with Amazon() as amazon:
    # Page 1
    r1 = amazon.search("thinkpad", productType="electronics", page=1)
    print(f"Page {r1.current_page} of {r1.total_pages} — {len(r1)} products")
    # Page 2
    r2 = amazon.search("thinkpad", productType="electronics", page=2)
    print(json.dumps(r2.get(), indent=2))
```

#### Iterate all pages

```python
amazon = Amazon()
page = 1
all_products = []
while True:
    res = amazon.search("laptop", page=page)
    all_products.extend(res.products)
    if res.current_page >= res.total_pages:
        break
    page += 1
print(f"Collected {len(all_products)} across {res.total_pages} pages")
amazon.close()
```

#### Old-style loop (still works)

```python
res = amazon.search("iPhone")
for product in res:  # or res.products
    d = product.get()
    print(f"Title: {d['title']}")
    print(f"Price: {d['currency']}{d['price']}")
    print(f"Review: {d['review']} ({d['review_numbers']})")
    print(f"Link: {d['link']}")
    print("-" * 40)
```

## How It Works 🔍

1. **URL building:** `urllib.parse.urlencode` safely encodes `k`, `i`, `brand`, `price`, `page`.
2. **Request:** `curl_cffi` with browser impersonation (real TLS/HTTP2 fingerprint), session reuse (keep-alive), 20s timeout. A blocked attempt is retried under a different browser fingerprint with exponential backoff.
3. **Parse products:** `SoupStrainer("div", {"data-component-type":"s-search-result"})` + `lxml` — only product divs are parsed.
4. **Parse pagination:** `SoupStrainer("div", {"data-csa-c-content-id":"pagination-button"})` → reads `span.s-pagination-selected` (current) and max `a/span.s-pagination-item` numeric (total, e.g. `260`).
5. **Extract:** runs `extract_data` (title/link/review/price/image) per div. Extraction is single-threaded on purpose: parsing holds the GIL, and a thread pool measured slower than a plain loop.
6. **Return:** `AmazonResult(products, current_page, total_pages)`.

### Deep-scrape pipeline

`AmazonProduct.deep_scrape(html=None)` handles the much larger, variable
product-detail document separately:

1. **Source:** explicit `html=` wins. Otherwise `link` is read from disk when it
   is a file, or fetched once with `curl_cffi` (`chrome124`, 20s timeout,
   redirects, `Accept-Language`) and checked with `raise_for_status()`.
2. **Base URL:** an HTTP(S) `link` is kept; otherwise the canonical/OG URL is
   used, falling back to `https://www.amazon.com`, so relative image and
   variation URLs become absolute.
3. **Sections:** identity (title, ASIN, brand, breadcrumbs), offer
   (price/currency/availability), social proof (`#acrPopover`, review count),
   content (`#feature-bullets`, detail bullets, spec tables), media
   (`#landingImage` + gallery JSON), and variations
   (`desktop-twister-sort-filter-data`).
4. **Projection:** always returns `AmazonProductDetails` with every key
   present. Missing sections become `None`, `[]`, or `{}`; absent markup never
   raises. `price` keeps Amazon's display text while `price_value` is numeric.
5. **Return:** `.get()` is an `asdict()` view, ready for `json.dumps()`.

Unlike `search()`, `deep_scrape()` makes a **single direct request** and does
not go through `Transport`'s fingerprint rotation/retry loop.

## What's New in v0.1.3

- **Deep scrape:** `AmazonProduct.deep_scrape()` now returns an exported `AmazonProductDetails` with a generalized detail-page schema (identity, offer, social proof, features/specs, media, variations). Missing sections stay `None` / `[]` / `{}`; saved HTML and local files are supported through `html=` or a file path in `link`.
- **Anti-bot fix:** `requests`/`httpx` replaced by `curl_cffi` browser impersonation, which is what stops Amazon serving the `503` "Sorry! Something went wrong!" page. Adds block detection by body markers (catches the `200` interstitial challenge), fingerprint rotation with exponential backoff, and a per-loop async session. **Breaking-ish:** transport deps changed (`requests`/`httpx` → `curl_cffi`); public `Amazon` API is unchanged apart from the new optional `timeout`/`max_attempts`/`backoff` args.
- **Typed fields:** `price` is now `float | None` (commas stripped, `0.0` fallback — never raises) and `review_numbers` is `int | None` (`k`/`m`/`b` suffixes converted, e.g. `"1.2K"` → `1200`; missing count → `0`).
- **Workers:** default is now `(os.cpu_count() or 4) // 2` instead of fixed `4`.
- **Version:** 0.1.2 → 0.1.3.
- See `docs/ARCHITECTURE.md` and `docs/SELECTORS.md` for the full contract, and `docs/TESTING.md` for the test suite.

## What's New in v0.1.2

- **Pagination:** `Amazon.search(..., page=N)` + `AmazonResult.current_page / total_pages` via `data-csa-c-content-id="pagination-button"`.
- **Performance:** session keep-alive, `SoupStrainer` partial parsing, early-exit on empty results, cached `find()` in `get_title`.
- **Robustness:** Broader `RequestException` catch, NBSP-safe price split, `image.get("src")` type-safe, `review_numbers` paren-stripping.
- **Compatibility & Lightweight:** `from __future__ import annotations` for Python 3.7–3.14; deps relaxed to `beautifulsoup4>=4.11`, `requests>=2.28`, `lxml>=4.9` (was pinned `==`). *Superseded:* these were later replaced by `curl_cffi` — see v0.1.3.*
- **DX:** `AmazonResult` iterable/len/indexable, `.get()` dict, `Amazon` context manager (`with Amazon() as a:` + `close()`), version bump 0.1.1→0.1.2.

## Anti-bot transport 🛡️

Amazon blocks scrapers on the **TLS/HTTP2 fingerprint**, not just headers. A
plain `requests`/`httpx` call gets a `503` "Sorry! Something went wrong!" page
(or a `200` interstitial containing `bm-verify`) that parses to zero products.
This library uses `curl_cffi` to impersonate a real browser, which is the fix.

On top of impersonation it:

- detects challenge pages by **body markers, not just status code** — the
  `bm-verify` interstitial arrives as `200`;
- **rotates browser fingerprints** across attempts (blocks follow the
  fingerprint, not the URL) with exponential backoff;
- sends **no hand-written `User-Agent`**, since one that disagrees with the
  TLS fingerprint is itself a detection signal.

Tunable via the constructor:

```python
Amazon(timeout=20, max_attempts=4, backoff=0.4)
```

`max_attempts` is capped at the number of profiles (6). When all attempts fail
you get `ValueError: Error while geting data from Amazon`; `TransportError` is
exported if you want to catch the underlying cause.

## Important Notes ⚠️

- **Rate Limiting:** heavy concurrent scraping can still get you blocked, and no
  fingerprint trick makes that impossible. Add delays / proxies for bulk work.
- **ToS:** Scraping may violate Amazon ToS — personal/educational use only.
- **Site Changes:** Search-result selectors (`data-cy="title-recipe"`, `data-component-type="s-product-image"`, etc.) and detail-page selectors (`#productTitle`, `#feature-bullets`, `#detailBullets_feature_div`, etc.) may need updates if Amazon changes markup. See `docs/SELECTORS.md`.

## Troubleshooting 🛠️

1. `ValueError: Error product Name is required` — provide `productName`.
2. `ValueError: Error while geting data from Amazon` — every attempt was blocked or errored. Run with `Amazon(is_debuging=True)` to see which fingerprint was rejected per attempt, then try `Amazon(max_attempts=6)` for a wider rotation.
3. Empty `products` — no match or HTML changed; check pagination (`total_pages`) and try different `page`.
4. `None` fields — normal (Amazon varies per product).
5. `ModuleNotFoundError: No module named 'amazon_product_search'` — `pip install amazon-product-search-v2` in correct venv.
6. `ValueError: link is not valid` from `deep_scrape()` — pass a product URL, a readable local HTML file path, or `html=...`.
7. `deep_scrape()` returns mostly `None` / empty fields — the page may be a bot challenge, an unavailable product, or saved HTML without detail markup. Compare against `docs/SELECTORS.md`.
8. `price` is `None` but `currency` is set — Amazon rendered a currency symbol but no buy-box price for that location/session; `price_value` is also `None`.

## Contributing 🤝

PRs welcome! Open an issue or submit a pull request.

## License 📜

MIT — see [LICENSE](LICENSE).
