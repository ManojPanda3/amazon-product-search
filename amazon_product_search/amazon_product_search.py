"""Amazon search client: request, search orchestration, result parsing."""
from __future__ import annotations

import asyncio
import logging

from urllib.parse import ParseResult, urlencode, urlparse, urlunparse

from .config import MAX_WORKERS, __version__
from .extractors import extract_data
from .models import AmazonProduct, AmazonResult, PriceResult, ReviewResult
from .parsers import parse_html, parse_pagination
from .transport import Transport, TransportError

__all__ = [
    "Amazon",
    "AmazonProduct",
    "AmazonResult",
    "PriceResult",
    "ReviewResult",
    "TransportError",
    "__version__",
]


class Amazon:
    def __init__(
        self,
        is_debuging: bool = False,
        workers: int | None = None,
        timeout: int = 20,
        max_attempts: int = 4,
        backoff: float = 0.4,
    ):
        self.base_url: ParseResult = urlparse("https://www.amazon.com/s")
        self.workers = workers if workers is not None else MAX_WORKERS
        self.is_debuging = is_debuging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if is_debuging else logging.ERROR)
        self.transport = Transport(
            timeout=timeout,
            max_attempts=max_attempts,
            backoff=backoff,
            debug=is_debuging,
        )

    @property
    def session(self):
        """The underlying curl_cffi Session (created on first use)."""
        return self.transport._get_session()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.transport.close()

    def __enter__(self) -> "Amazon":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    async def __aenter__(self) -> "Amazon":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.transport.aclose()

    def __build_url(
        self,
        productName: str,
        productType: str = "",
        brand: str = "",
        priceRange: str = "",
        page: int = 0,
    ) -> str:
        """Build the Amazon search URL for the given criteria."""
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
        return urlunparse(self.base_url._replace(query=query_params))

    def search(
        self,
        productName: str,
        productType: str = "",
        brand: str = "",
        priceRange: str = "",
        page: int = 0,
    ) -> AmazonResult:
        """
        Searches products on Amazon based on provided criteria.

        Args:
            productName (str): The name of the product to search for (required).
            productType (str): The type of product (e.g., "electronics"). Optional.
            brand (str): The brand of the product. Optional.
            priceRange (str): The price range of the product. Optional.
            page (int): The page number to fetch. Optional.

        Returns:
            AmazonResult: Products found plus pagination info (current_page, total_pages).

        Raises:
            ValueError: If productName is empty.

        Exception:
            If there is an error fetching data from Amazon.
        """
        if productName.strip() == "":
            raise ValueError("Error product Name is required")

        url = self.__build_url(productName, productType, brand, priceRange, page)

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

    async def async_search(
        self,
        productName: str,
        productType: str = "",
        brand: str = "",
        priceRange: str = "",
        page: int = 0,
    ) -> AmazonResult:
        """
        Searches products on Amazon asynchronously.

        A single search is performed per call. To overlap the network waits of
        several searches, await them together, for example::

            results = await asyncio.gather(
                amazon.async_search("thinkpad"),
                amazon.async_search("macbook"),
            )

        Args:
            productName (str): The name of the product to search for (required).
            productType (str): The type of product (e.g., "electronics"). Optional.
            brand (str): The brand of the product. Optional.
            priceRange (str): The price range of the product. Optional.
            page (int): The page number to fetch. Optional.

        Returns:
            AmazonResult: Products found plus pagination info (current_page, total_pages).

        Raises:
            ValueError: If productName is empty or the data could not be fetched.

        Exception:
            If there is an error fetching data from Amazon.
        """
        if productName.strip() == "":
            raise ValueError("Error product Name is required")

        url = self.__build_url(productName, productType, brand, priceRange, page)

        responseHtml = await self.__async_request(url)
        if not responseHtml:
            raise ValueError("Error while geting data from Amazon")

        # Parsing is CPU-bound and holds the GIL, so keep it off the event loop
        # to leave other in-flight searches free to make progress.
        products, (current_page, total_pages) = await asyncio.gather(
            asyncio.to_thread(self.__process_html, responseHtml),
            asyncio.to_thread(parse_pagination, responseHtml, requested_page=page),
        )

        return AmazonResult(
            products=products, current_page=current_page, total_pages=total_pages
        )

    def __amazon_request(self, url: str) -> str:
        """
        Fetches an Amazon URL through the impersonating transport.

        Retries with a rotated browser fingerprint when Amazon serves a bot
        challenge instead of results.

        Args:
            url (str): The URL to request.

        Returns:
            str: The response content text if successful, empty string otherwise.
        """
        try:
            return self.transport.get(url)
        except TransportError as error:
            self.logger.error(f"Error while fetching amazon url[{url}]\nError:{error}")
            return ""

    async def __async_request(self, url: str) -> str:
        """
        Asynchronous twin of :meth:`__amazon_request`.

        Args:
            url (str): The URL to request.

        Returns:
            str: The response content text if successful, empty string otherwise.
        """
        try:
            return await self.transport.aget(url)
        except TransportError as error:
            self.logger.error(f"Error while fetching amazon url[{url}]\nError:{error}")
            return ""

    def __process_html(self, html: str) -> list[AmazonProduct]:
        """
        Processes the HTML content to extract product information.

        Args:
            html (str): The HTML content to process.

        Returns:
            list[AmazonProduct]: A list of AmazonProduct objects.
        """
        divs = parse_html(html)
        if not divs:
            return []

        products: list[AmazonProduct] = []
        for div in divs:
            product = extract_data(div)
            if product:
                products.append(product)

        return products


if __name__ == "__main__":
    import json

    with Amazon(is_debuging=True) as amazon:
        result = amazon.search("thinkpad", productType="electronics", page=1)
    print(json.dumps(result.get(), indent=2))