from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup, element
from bs4.filter import SoupStrainer
from dataclasses import dataclass, field
from urllib.parse import ParseResult, urlparse, urlunparse, urlencode
import concurrent.futures
import os, logging

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - Python 3.7 fallback only
    from typing_extensions import TypedDict

__version__ = "0.1.2"

MAX_WORKERS = (os.cpu_count() or 4) // 2


class PriceResult(TypedDict):
    price: float
    currency: str


class ReviewResult(TypedDict, total=False):
    review: str
    reviews_number: int


@dataclass
class AmazonProduct:
    """
    Represents a product found on Amazon.

    Attributes:
        title (str | None): The title of the product.
        link (str | None): The URL link to the product page.
        review (str | None):  A string representing the product's review (e.g., "4.5 out of 5 stars").
        review_numbers (int | None): The review count as an int (k/m/b suffixes converted).
        price (float | None): The price of the product as a float.
        currency (str | None): The currency symbol (e.g., "$").
        image (str | None): The URL of the product image.
    """

    title: str | None = None
    link: str | None = None
    review: str | None = None
    review_numbers: int | None = None
    price: float | None = None
    image: str | None = None
    currency: str | None = None

    def get(self) -> dict:
        """
        Returns the product information as a dictionary.

        Returns:
            dict: A dictionary containing the product's title, link, review, price, and image.
        """
        return {
            "title": self.title,
            "link": self.link,
            "review": self.review,
            "review_numbers": self.review_numbers,
            "currency": self.currency,
            "price": self.price,
            "image": self.image,
        }

    def __str__(self) -> str:
        return str(self.get())


@dataclass
class AmazonResult:
    products: list[AmazonProduct] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1

    def __iter__(self):
        return iter(self.products)

    def __len__(self):
        return len(self.products)

    def __getitem__(self, idx):
        return self.products[idx]

    def get(self) -> dict:
        """Dict representation for JSON serialization."""
        return {
            "products": [p.get() for p in self.products],
            "current_page": self.current_page,
            "total_pages": self.total_pages,
        }


class Amazon:
    def __init__(self, is_debuging: bool = False, workers: int = MAX_WORKERS) -> None:
        self.base_url: ParseResult = urlparse("https://www.amazon.com/s")
        self.workers = workers
        self._HEADER: dict = {
            "User-Agent": "Mozilla/5.0 (X11; Linuin zipx x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": "en-US, en;q=0.5",
        }
        self.is_debuging = is_debuging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if is_debuging else logging.ERROR)
        self.session = requests.Session()
        self.session.headers.update(self._HEADER)

    def close(self) -> None:
        """Close the underlying requests Session."""
        self.session.close()

    def __enter__(self) -> Amazon:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def search(
        self,
        productName: str,
        productType: str = "",
        brand: str = "",
        priceRange: str = "",
        page: int = 0,
    ) -> AmazonResult:
        """
        Searches for products on Amazon based on the provided criteria.

        Args:
            productName (str): The name of the product to search for (required).
            productType (str ): The type of product (e.g., "electronics").  Optional.
            brand (str ): The brand of the product. Optional.
            priceRange (str ): The price range of the product.  Optional.
            page (int): Page number (1-indexed). 0 / 1 both mean first page. Optional.

        Returns:
            AmazonResult: Products plus pagination info (current_page, total_pages).

        Raises:
            ValueError: If productName is empty.
            Exception: If there is an error fetching data from Amazon.
        """
        if productName.strip() == "":
            raise ValueError("Error product Name is required")

        page_param = str(page) if page and page > 1 else None
        clean_params = {
            "k": productName,
            "i": productType.strip() if productType.strip() != "" else None,
            "brand": brand.strip() if brand.strip() != "" else None,
            "price": priceRange.strip() if priceRange.strip() != "" else None,
            "page": page_param,
        }
        query_params: str = urlencode(
            {k: v for k, v in clean_params.items() if v is not None}
        )
        url = urlunparse(self.base_url._replace(query=query_params))

        responseHtml = self.__amazon_request(url)
        if not responseHtml:
            raise ValueError("Error while geting data from Amazon")

        products = self.__process_html(responseHtml)
        current_page, total_pages = self.__parse_pagination(
            responseHtml, requested_page=page
        )

        return AmazonResult(
            products=products, current_page=current_page, total_pages=total_pages
        )

    def __amazon_request(self, url: str) -> str:
        """
        Sends an HTTP GET request to the specified Amazon URL.

        Args:
            url (str): The URL to request.

        Returns:
            str: The response content as text if successful, empty string otherwise.
        """
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Error while geting {url}:\t{response.content}")
                return ""
            return response.text
        except requests.RequestException as error:
            self.logger.error(f"Error while fetching amazon url[{url}]\nError:{error}")
            return ""

    def __parse_html(self, html: str) -> list[element.Tag]:
        """
        Parses the HTML content and extracts the relevant product divs.

        Args:
            html (str): The HTML content to parse.

        Returns:
            list[element.Tag]: A list of BeautifulSoup Tag objects, each representing a product search result.
        """
        strainer = SoupStrainer("div", attrs={"data-component-type": "s-search-result"})
        soup = BeautifulSoup(html, "lxml", parse_only=strainer)
        searchDivs = soup.find_all(
            "div", attrs={"data-component-type": "s-search-result"}
        )
        return searchDivs

    def __parse_pagination(self, html: str, requested_page: int = 0) -> tuple[int, int]:
        """
        Extract pagination info anchored on data-csa-c-content-id="pagination-button".

        Amazon renders pagination inside:
          <div data-csa-c-content-id="pagination-button" ...>
            <span class="s-pagination-selected">1</span>
            <a class="s-pagination-button">2</a>
            ...
            <span class="s-pagination-disabled">260</span>
          </div>

        Args:
            html: Full response HTML.
            requested_page: Page requested in `search()` (fallback if markup missing).

        Returns:
            (current_page, total_pages)
        """
        fallback = requested_page if requested_page and requested_page > 0 else 1
        try:
            strainer = SoupStrainer(
                "div", attrs={"data-csa-c-content-id": "pagination-button"}
            )
            soup = BeautifulSoup(html, "lxml", parse_only=strainer)
            pagination_div = soup.find(
                "div", attrs={"data-csa-c-content-id": "pagination-button"}
            )
            if pagination_div is None:
                soup = BeautifulSoup(html, "lxml")
                pagination_div = soup.find(
                    "div", attrs={"data-csa-c-content-id": "pagination-button"}
                )
            if pagination_div is None:
                return (fallback, fallback if fallback == 1 else fallback)

            current = fallback
            selected = pagination_div.find("span", class_="s-pagination-selected")
            if selected:
                txt = selected.get_text(strip=True)
                if txt.isdigit():
                    current = int(txt)
                else:
                    m = re.search(r"\d+", txt)
                    if m:
                        current = int(m.group())
            elif requested_page:
                current = requested_page

            total = current
            items = pagination_div.find_all(
                ["a", "span"],
                class_=re.compile(r"s-pagination-item"),
            )
            nums: list[int] = []
            for el in items:
                txt = el.get_text(strip=True)
                if txt.isdigit():
                    nums.append(int(txt))
                else:
                    m = re.search(r"\d+", txt)
                    if m and txt.strip("() ").isdigit() is False:
                        pass
            if nums:
                total = max(nums)
            if total < current:
                total = current
            if total < 1:
                total = 1
            return (current, total)
        except Exception as e:
            self.logger.debug(f"Pagination parse failed: {e}")
            return (fallback, fallback)

    def __process_html(self, html: str) -> list[AmazonProduct]:
        """
        Processes the HTML content to extract product information.  Uses multithreading.

        Args:
            html (str): The HTML content to process.

        Returns:
            list[AmazonProduct]: A list of AmazonProduct objects.
        """
        divs = self.__parse_html(html)
        if not divs:
            return []

        products: list[AmazonProduct] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = [executor.submit(self.__extract_data, div) for div in divs]
            for future in concurrent.futures.as_completed(futures):
                product = future.result()
                if product:
                    products.append(product)

        return products

    def __extract_data(self, div: element.Tag) -> AmazonProduct | None:
        """
        Extracts data for a single product from a BeautifulSoup Tag.

        Args:
            div (element.Tag):  A BeautifulSoup Tag representing a single product search result.

        Returns:
            AmazonProduct | None: An AmazonProduct object containing the extracted data, or None if
                the input div is invalid.
        """
        if not div:
            return None

        data = AmazonProduct()
        data.title = self.__get_title(div)
        data.link = self.__get_link(div)
        review = self.__get_reviews(div)
        if review:
            data.review = review.get("review")
            data.review_numbers = review.get("reviews_number")

        price = self.__get_price(div)
        if price is not None:
            data.price = price.get("price", 0.0)
            data.currency = price.get("currency")
        data.image = self.__get_image(div)
        return data

    def __get_title(self, div: element.Tag) -> str | None:
        """
        Extracts the product title from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product title, or None if not found.
        """
        title = div.find("div", attrs={"data-cy": "title-recipe"})
        if not title:
            return None
        h2 = title.find("h2")
        if not h2:
            return None
        span = h2.find("span")
        return span.string if span else None

    def __get_link(self, div: element.Tag) -> str | None:
        """
        Extracts the product link from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product link, or None if not found.
        """
        link_span = div.find(
            "span",
            attrs={
                "data-component-type": "s-product-image",
            },
        )

        if link_span:
            link_a = link_span.find("a")
            if link_a:
                href = link_a.get("href")
                if href:
                    return f"https://www.amazon.com{href}"
        return None

    @staticmethod
    def __convert_review_to_number(s: str) -> int:
        s = s.lower()
        if not s:
            return 0
        symb = {"k": int(1e3), "m": int(1e6), "b": int(1e9)}
        review_num: float = 0.0
        try:
            review_num = float(s[0:-1]) * symb[s[-1]] if s[-1] in symb else float(s)
        except ValueError:
            review_num = 0.0

        return int(review_num)

    def __get_reviews(self, div: element.Tag) -> ReviewResult | None:
        review_div = div.find("div", attrs={"data-cy": "reviews-block"})

        if not review_div:
            return None

        reviews: ReviewResult = {}
        review_span = review_div.find(
            "span",
            attrs={"class": "a-size-small a-color-base", "aria-hidden": "true"},
        )

        if review_span and review_span.string:
            reviews["review"] = review_span.string

        reviews_number_span = review_div.find(
            "span", attrs={"data-component-type": "s-client-side-analytics"}
        )

        if reviews_number_span:
            inner_span = reviews_number_span.find("span", attrs={"aria-hidden": "true"})

            if inner_span and inner_span.string:
                count_text = inner_span.string.strip().replace(",", "")
                reviews["reviews_number"] = self.__convert_review_to_number(
                    count_text[1:-1] if len(count_text) >= 2 else count_text
                )
            else:
                reviews["reviews_number"] = 0
        else:
            reviews["reviews_number"] = 0

        return reviews

    def __get_price(self, div: element.Tag) -> PriceResult | None:
        """
        Extracts the product price from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            dict | None: {"currency": str, "price": float} or None if not found.
                Non-numeric amounts fall back to 0.0 (never raises).
        """
        for attr in ("price-recipe", "secondary-offer-recipe"):
            price_div = div.find("div", attrs={"data-cy": attr})

            if not price_div:
                continue

            cls = "a-offscreen" if attr == "price-recipe" else "a-color-base"
            price_span = price_div.find("span", attrs={"class": cls})

            if price_span and price_span.string:
                price = price_span.string.strip()
                price = price.replace(",", "")

                if "\u00a0" in price:
                    f, s = price.split("\u00a0", 1)
                    currency, amount = self.__split_currency_amount(f, s)
                    return {"currency": currency, "price": amount}

                try:
                    price = float(price)
                except ValueError:
                    price = 0.0

                return {"currency": "", "price": price}

            if price_span:
                text = price_span.get_text(strip=True).replace(",", "")
                if text:
                    if "\u00a0" in text:
                        f, s = text.split("\u00a0", 1)
                        currency, amount = self.__split_currency_amount(f, s)
                        return {"currency": currency, "price": amount}

                    try:
                        price = float(text)
                    except ValueError:
                        price = 0.0

                    return {"currency": "", "price": price}

        return None

    @staticmethod
    def __split_currency_amount(f: str, s: str) -> tuple[str, float]:
        """Split an NBSP-separated price into (currency, amount).

        Each side that parses as float becomes the amount; non-numeric
        sides become the currency (last one wins). Both numeric →
        amount is the second part; neither numeric → amount 0.0.
        Uses float() — not str.isnumeric() — so decimals like "19.99"
        are recognised as amounts.
        """
        currency, amount = "", 0.0
        for part in (f, s):
            try:
                amount = float(part)
            except ValueError:
                currency = part
        return currency, amount

    def __get_image(self, div: element.Tag) -> str | None:
        """
        Extracts the product image URL from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product image URL, or None if not found.
        """
        image = div.find("img", attrs={"class": "s-image"})
        if not image:
            return None
        src = image.get("src")
        return str(src) if src else None


if __name__ == "__main__":
    import json

    amazon = Amazon(False)
    result = amazon.search("mac", productType="electronics")

    print(
        json.dumps(
            {
                "products": [p.get() for p in result.products],
                "current_page": result.current_page,
                "total_pages": result.total_pages,
            },
            indent=2,
        )
    )
