# 🛍️ Amazon Product Search Library 📦

## Overview

Looking for the best deals on Amazon but tired of manually browsing? 🌐 Meet **Amazon Product Search** — your trusty Python library to scrape product details from Amazon with just a few lines of code. Powered by **BeautifulSoup4 (bs4)** and **Requests**, this library helps you gather all the juicy details about products including their titles, prices, reviews, images, and direct links, straight from Amazon's search results. 🎉

### Key Features:
- **Product Search**: Search for products by name, brand, type, and price range. 📱💻
- **Detailed Data**: Scrape titles, prices, reviews, images, and URLs in one go! 🎯
- **Easy-to-use**: Just import and go, it's like magic! ✨

## Setup 🛠️

To get started with Amazon Product Search, follow these simple steps:

### 1. Install via GitHub (Recommended for Devs) 🦸‍♂️

Clone the repo and install the library directly:

```bash
git clone --depth 1 https://github.com/ManojPanda3/amazon-product-search && pip install -e .
```

You’ll have access to the latest updates and developments! 🚀

### 2. Install via PyPI (For Simplicity) 🧑‍💻

If you just want to get it up and running without any hassle, install the library using `pip` from PyPI:

```bash
pip install amazon-product-search
```

And boom! 🎉 You’re all set!

## Usage 📚

### Import the Library 🧑‍💻

First, import the **`amazon_product_search`** module:

```python
import amazon_product_search as ams
```

### Function: `amazon_product_search()`

The core function of the library is **`amazon_product_search()`**. It allows you to search for products and get detailed info all at once. ✨

#### Function Syntax:

```python
ams.amazon_product_search(query, productType=None, brand=None, priceRange=None)
```

#### Parameters:
- `productName` (str): The search term (e.g., `"iPhone"`, `"laptop"`).
- `productType` (str, optional): The type of product (e.g., `"electronic"`).
- `brand` (str, optional): The brand of the product (e.g., `"Apple"`).
- `priceRange` (str, optional): The price range in the format `"min_price-max_price"`, e.g., `"80000-100000"`.

#### Example Usage:

```python
import amazon_product_search as ams

# Search for iPhones by Apple in the 'electronic' category, with a price range of 80,000 to 100,000
products = ams.amazon_product_search("iPhone", productType="electronic", brand="Apple", priceRange="80000-100000")

# Display the product details
for product in products:
    print(f"Title: {product['title']}")
    print(f"Price: {product['price']}")
    print(f"Reviews: {product['reviews']}")
    print(f"Image URL: {product['image_url']}")
    print(f"Product Link: {product['url']}")
    print("-" * 40)
```

## How It Works 🔍

This library works by making HTTP requests to Amazon's search results pages and scraping the HTML content using **BeautifulSoup4**. 🕵️‍♂️

It extracts the following information:
- **Title**: The product’s name (or title) is grabbed from the search card.
- **Price**: Extracted from the product’s price section 💸.
- **Reviews**: Number of reviews scraped from the product's rating section.
- **Image URL**: The source of the product image for your viewing pleasure 📸.
- **Product Link**: The direct Amazon link to the product page, so you can buy it (or just admire it) 🛒.

## Example:

Here’s a real-world example:

```python
import amazon_product_search as ams

# Search for Apple iPhones in the 'electronic' category, in the price range of 80,000 to 100,000
products = ams.amazon_product_search("iPhone", productType="electronic", brand="Apple", priceRange="80000-100000")

# Loop through the results and print the details
for product in products:
    print(f"Title: {product['title'][0]}")
    print(f"Price: {product['price'][0]}")
    print(f"Reviews: {product['reviews'][0]}")
    print(f"Image URL: {product['image_url'][0]}")
    print(f"Product Link: {product['url'][0]}")
    print("-" * 40)
```

### Sample Output 🎯:

```plaintext
Title: Apple iPhone 13 (128GB) - Blue
Price: ₹89,999
Reviews: 10,000+ ratings
Image URL: https://example.com/image.jpg
Product Link: https://www.amazon.in/dp/B09V4G5SP1
----------------------------------------
Title: Apple iPhone 12 (64GB) - Black
Price: ₹74,999
Reviews: 5,000+ ratings
Image URL: https://example.com/image2.jpg
Product Link: https://www.amazon.in/dp/B08L6LQ5G9
----------------------------------------
```

## Notes ⚠️

- **Be Nice to Amazon!** 🌱 Scraping can be heavy on resources, so use it responsibly. Amazon might block your IP if you’re scraping too frequently. 🛑
- **Legal Stuff**: Scraping Amazon might go against their [Terms of Service](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088). Use this tool for **personal and educational purposes only**. 🔒
- **Amazon Changes**: If Amazon updates its website structure, scraping may break. Let’s hope they don’t change things too much! 🤞

## Troubleshooting 🛠️

1. **Missing Data?** 🧐 If the data isn’t coming through, check if Amazon has changed their page structure or if you’ve missed a parameter in the function.
2. **Blocked by Amazon?** 🕵️‍♂️ Try adding a delay between requests or use a proxy to avoid rate-limiting.

## Contributing 🤝

Got ideas or improvements? 🎨 Open a pull request or create an issue on GitHub. Let’s make this even better! 🚀

## License 📜

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

**Happy Scraping!** 🕸️✨


