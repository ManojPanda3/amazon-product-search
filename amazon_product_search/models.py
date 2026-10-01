"""Data models and result containers."""

from __future__ import annotations

from bs4 import BeautifulSoup
from dataclasses import dataclass, field

from curl_cffi import requests as curl_requests

try:
    from typing import TypedDict
except ImportError:  # pragma: cover - Python 3.7 fallback only
    from typing_extensions import TypedDict

__all__ = [
    "AmazonProduct",
    "AmazonResult",
    "PriceResult",
    "ReviewResult",
]



class PriceResult(TypedDict):
    price: float
    currency: str


class ReviewResult(TypedDict, total=False):
    review: str
    reviews_number: int




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

    def __init__(
        self,
        title: str | None = None,
        link: str | None = None,
        review: str | None = None,
        review_numbers: int | None = None,
        price: float | None = None,
        image: str | None = None,
        currency: str | None = None,
    ):
        self.title = title
        self.link = link
        self.review = review
        self.review_numbers = review_numbers
        self.price = price
        self.image = image
        self.currency = currency

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

    def scrape(self) -> None:
        link: str = self.link or ""
        if link == None:
            raise ValueError("link is not valid")

        req = curl_requests.get(link, impersonate="chrome124", timeout=10)
        if req.status_code != 200:
            raise ValueError("request is unsuccessful")

        soup = BeautifulSoup(req.text, "lxml")
        title_span = soup.find("span", attrs={"id": "productTitle"})
        if title_span:
            title = title_span.string
            print(title)
        price_span = soup.find(
            "span", attrs={"id": "apex-pricetopay-accessibility-label"}
        )
        if price_span:
            symbl = price_span.find("span", attrs={"class": "a-price-symbol"})
            whole_price = price_span.find("span", attrs={"class": "a-price-whole"})
            fraction_price = price_span.find(
                "span", attrs={"class": "a-price-fraction"}
            )
            print(symbl, whole_price, fraction_price)

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
