# 🛍️ Amazon Product Search Library 📦

## Overview

Tired of manually browsing Amazon for the best deals? 🌐 Meet **Amazon Product Search** — your trusty Python library to scrape product details from Amazon's search results with just a few lines of code. Powered by **BeautifulSoup4 (bs4)**, **Requests**, and **multithreading** for speed, this library helps you efficiently gather product titles, prices, reviews, images, and direct links. 🎉

### Key Features

- **Product Search:** Search for products by name, type, brand, and price range. 📱💻
- **Detailed Data:** Scrape titles, prices, reviews, images, and URLs. 🎯
- **Fast and Efficient:** Uses multithreading to speed up data extraction.
- **Easy-to-use:** Simple API for quick integration. ✨

## Setup 🛠️

Get started with Amazon Product Search by installing it via PyPI or GitHub.

### 1. Install via PyPI (Recommended) 🧑‍💻

The easiest way to install the library is using `pip` from PyPI:

```bash
pip install amazon-product-search-v2
```

This installs the latest stable release. **Note the package name is now `amazon-product-search-v2`**.

### 2. Install via GitHub (For Developers) 🦸‍♂️

If you want the very latest development version (which may have new features or bug fixes, but could also be less stable), clone the repository and install it in editable mode:

```bash
git clone --depth 1 https://github.com/ManojPanda3/amazon-product-search
cd amazon-product-search
pip install -e .
```

This allows you to modify the code and have the changes immediately reflected without reinstalling.

## Usage 📚

### Import the Library

First, import the `Amazon` class from the `amazon_product_search` module:

```python
from amazon_product_search import Amazon
```

**Important:** Even though the _package_ name on PyPI is `amazon-product-search-v2`, you still import the module as `amazon_product_search`. The code inside the package hasn't changed its import paths.

### Searching for Products

The core functionality is provided by the `Amazon` class.

#### Instantiate the `Amazon` Class

```python
amazon = Amazon(is_debuging=False)  # Set is_debuging to True for verbose output
```

#### Use the `search()` Method

```python
results = amazon.search(productName="iPhone", productType="electronics", brand="Apple", priceRange="80000-100000")
```

**Parameters:**

- `productName` (str, required): The search term (e.g., "iPhone", "laptop").
- `productType` (str, optional): Filters by product type (e.g., "electronics", "books").
- `brand` (str, optional): Filters by brand (e.g., "Apple", "Samsung").
- `priceRange` (str, optional): Filters by price range using the format "min_price-max_price" (e.g., "100-200").

**Returns:**

- `list[dict]`: A list of dictionaries, where each dictionary represents a product and contains the following keys:
  - `"title"` (str | None): The product title.
  - `"link"` (str | None): The URL to the product page.
  - `"review"` (str | None): A string representing the product review (e.g., "4.5 out of 5 stars").
  - `"price"` (str | None): The product price.
  - `"image"` (str | None): The URL of the product image.

#### Example

```python
from amazon_product_search import Amazon

amazon = Amazon()
products = amazon.search("iPhone", productType="electronics", brand="Apple", priceRange="80000-100000")

for product in products:
    print(f"Title: {product['title']}")
    print(f"Price: {product['price']}")
    print(f"Review: {product['review']}")
    print(f"Image: {product['image']}")
    print(f"Link: {product['link']}")
    print("-" * 40)
```

## How It Works 🔍

This library works by:

1. **Constructing a Search URL:** It builds a URL for Amazon's search results page based on the provided search parameters.
2. **Making an HTTP Request:** It sends an HTTP GET request to the Amazon search URL using the `requests` library. It includes headers to mimic a web browser.
3. **Parsing the HTML:** It uses `BeautifulSoup4` to parse the HTML response and extract the relevant product information from the search result elements.
4. **Multithreading:** It uses `concurrent.futures.ThreadPoolExecutor` to process multiple search result elements concurrently, significantly speeding up the data extraction.
5. **Returning Data:** It returns the extracted data as a list of dictionaries.

## Important Notes ⚠️

- **Rate Limiting:** Amazon may rate-limit or block your IP address if you make too many requests in a short period. Use this library responsibly. Consider adding delays or using proxies if you need to scrape a large amount of data. The library includes a `timeout` in the request to help prevent hanging.
- **Terms of Service:** Scraping may be against Amazon's Terms of Service. Use this tool for **personal and educational purposes only**, and be aware of the potential legal and ethical implications.
- **Website Changes:** Amazon frequently updates its website structure. If the scraping stops working, the HTML parsing logic may need to be adjusted.
- **Error Handling:** The library includes basic error handling (e.g., for network errors), but you may need to add more robust error handling for production use.

## Troubleshooting 🛠️

1. **`ValueError: Error product Name is required`:** You must provide a `productName` when calling the `search()` method.
2. **`Exception: Error while geting data from Amazon`:** This indicates a problem fetching data from Amazon. It could be a network issue, a problem with your request, or Amazon blocking your request. Enable debugging (`is_debuging=True`) for more details.
3. **Empty Results:** If you get an empty list, it could be that no products matched your search criteria, or that Amazon's HTML structure has changed, and the parsing logic needs to be updated.
4. **Missing Data (None Values):** If some fields (like `review` or `price`) are `None`, it means the library couldn't find that specific data for that product on the page. This is normal, as Amazon's page structure can vary.
5. **`ModuleNotFoundError: No module named 'amazon_product_search'`:** Make sure you've installed the package correctly using `pip install amazon-product-search-v2`. If you installed from GitHub, make sure you're in the correct virtual environment and that you installed with `pip install -e .`.

## Contributing 🤝

Contributions are welcome! If you find a bug, have a feature request, or want to improve the code, please open an issue or submit a pull request on GitHub.

## License 📜

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
