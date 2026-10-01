"""Amazon search client: request, search orchestration, result parsing."""

from __future__ import annotations

import concurrent.futures
import logging

import requests
from urllib.parse import ParseResult, urlencode, urlparse, urlunparse

from .config import MAX_WORKERS, __version__
from .extractors import extract_data
from .models import AmazonProduct, AmazonResult, PriceResult, ReviewResult
from .parsers import parse_html, parse_pagination

__all__ = [
    "Amazon",
    "AmazonProduct",
    "AmazonResult",
    "PriceResult",
    "ReviewResult",
    "__version__",
]


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
        current_page, total_pages = parse_pagination(
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




    def __process_html(self, html: str) -> list[AmazonProduct]:
        """
        Processes the HTML content to extract product information.  Uses multithreading.

        Args:
            html (str): The HTML content to process.

        Returns:
            list[AmazonProduct]: A list of AmazonProduct objects.
        """
        divs = parse_html(html)
        if not divs:
            return []

        products: list[AmazonProduct] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = [executor.submit(extract_data, div) for div in divs]
            for future in concurrent.futures.as_completed(futures):
                product = future.result()
                if product:
                    products.append(product)

        return products



if __name__ == "__main__":
    import json

    amazon = Amazon(False)
    result = amazon.search("thinkpad", productType="electronics")

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

    if result.products:
        print(result.products[0].scrape())
