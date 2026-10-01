# 🛍️ Amazon Product Search Library 📦

## Overview

Tired of manually browsing Amazon for the best deals? 🌐 Meet **Amazon Product Search** — your trusty Python library to scrape product details from Amazon's search results with just a few lines of code. Powered by **BeautifulSoup4 (bs4)**, **Requests**, and optional **async** requests for speed, this library helps you efficiently gather product titles, prices, reviews, images, and direct links. 🎉

### Key Features

- **Product Search:** Search for products by name, type, brand, and price range. 📱💻
- **Detailed Data:** Scrape titles, prices (+currency), reviews (+count), images, and URLs. 🎯
- **Pagination:** Navigate Amazon pages via `page` param and get `current_page` / `total_pages` from `data-csa-c-content-id="pagination-button"`. 📄
- **Fast and Efficient:** Session reuse (keep-alive), `SoupStrainer` partial parsing, and optional `async_search()` for overlapping network I/O.
- **Easy-to-use:** Simple API + context-manager + backward-compatible iteration. ✨
- **Lightweight & Compatible:** Python 3.9–3.14, relaxed deps (`beautifulsoup4>=4.11`, `requests>=2.28`, `lxml>=4.9`, `httpx>=0.27`). No heavy frameworks.

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
from amazon_product_search import Amazon, AmazonProduct, AmazonResult
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
2. **Request:** `requests.Session` reuse (keep-alive, header persistence), 10s timeout, `RequestException` handling, `networkidle` not needed.
3. **Parse products:** `SoupStrainer("div", {"data-component-type":"s-search-result"})` + `lxml` — only product divs are parsed.
4. **Parse pagination:** `SoupStrainer("div", {"data-csa-c-content-id":"pagination-button"})` → reads `span.s-pagination-selected` (current) and max `a/span.s-pagination-item` numeric (total, e.g. `260`).
5. **Extract:** runs `extract_data` (title/link/review/price/image) per div. Extraction is single-threaded on purpose: parsing holds the GIL, and a thread pool measured slower than a plain loop.
6. **Return:** `AmazonResult(products, current_page, total_pages)`.

## Unreleased (unversioned, in working tree)

- **Typed fields:** `price` is now `float | None` (commas stripped, `0.0` fallback — never raises) and `review_numbers` is `int | None` (`k`/`m`/`b` suffixes converted, e.g. `"1.2K"` → `1200`; missing count → `0`).
- **Workers:** default is now `(os.cpu_count() or 4) // 2` instead of fixed `4`.
- See `docs/ARCHITECTURE.md` and `docs/SELECTORS.md` for the full contract, and `docs/TESTING.md` for the test suite.

## What's New in v0.1.2

- **Pagination:** `Amazon.search(..., page=N)` + `AmazonResult.current_page / total_pages` via `data-csa-c-content-id="pagination-button"`.
- **Performance:** `requests.Session` keep-alive, `SoupStrainer` partial parsing, early-exit on empty results, cached `find()` in `get_title`.
- **Robustness:** Broader `RequestException` catch, NBSP-safe price split, `image.get("src")` type-safe, `review_numbers` paren-stripping.
- **Compatibility & Lightweight:** `from __future__ import annotations` for Python 3.7–3.14; deps relaxed to `beautifulsoup4>=4.11`, `requests>=2.28`, `lxml>=4.9` (was pinned `==`).
- **DX:** `AmazonResult` iterable/len/indexable, `.get()` dict, `Amazon` context manager (`with Amazon() as a:` + `close()`), version bump 0.1.1→0.1.2.

## Important Notes ⚠️

- **Rate Limiting:** Amazon may block frequent requests. Add delays / proxies for bulk scraping.
- **ToS:** Scraping may violate Amazon ToS — personal/educational use only.
- **Site Changes:** Selectors (`data-cy="title-recipe"`, `data-component-type="s-product-image"`, etc.) may need updates if Amazon changes markup.

## Troubleshooting 🛠️

1. `ValueError: Error product Name is required` — provide `productName`.
2. `ValueError: Error while geting data from Amazon` — network/blocked; try `Amazon(is_debuging=True)` for logs.
3. Empty `products` — no match or HTML changed; check pagination (`total_pages`) and try different `page`.
4. `None` fields — normal (Amazon varies per product).
5. `ModuleNotFoundError: No module named 'amazon_product_search'` — `pip install amazon-product-search-v2` in correct venv.

## Contributing 🤝

PRs welcome! Open an issue or submit a pull request.

## License 📜

MIT — see [LICENSE](LICENSE).
