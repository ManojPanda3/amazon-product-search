import requests
from bs4 import BeautifulSoup, element
from dataclasses import dataclass
from urllib.parse import ParseResult, urlparse, urlunparse, urlencode
import concurrent.futures
import logging

MAX_WORKERS = 4


@dataclass
class AmazonProduct:
    """
    Represents a product found on Amazon.

    Attributes:
        title (str | None): The title of the product.
        link (str | None): The URL link to the product page.
        review (str | None):  A string representing the product's review (e.g., "4.5 out of 5 stars").
        price (str | None): The price of the product as a string.
        image (str | None): The URL of the product image.
    """

    title: str | None = None
    link: str | None = None
    review: str | None = None
    review_numbers: int | None = None
    price: str | None = None
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

    def search(
        self,
        productName: str,
        productType: str = "",
        brand: str = "",
        priceRange: str = "",
    ) -> list[AmazonProduct]:
        """
        Searches for products on Amazon based on the provided criteria.

        Args:
            productName (str): The name of the product to search for (required).
            productType (str ): The type of product (e.g., "electronics").  Optional.
            brand (str ): The brand of the product. Optional.
            priceRange (str ): The price range of the product.  Optional.

        Returns:
            list[dict]: A list of dictionaries, where each dictionary represents a product
                and contains its title, link, review, price, and image URL.

        Raises:
            ValueError: If productName is empty.
            Exception: If there is an error fetching data from Amazon.
        """
        if productName.strip() == "":
            raise ValueError("Error product Name is required")

        clean_params = {
            "k": productName,
            "i": productType.strip() if productType.strip() != "" else None,
            "brand": brand.strip() if brand.strip() != "" else None,
            "price": priceRange.strip() if priceRange.strip() != "" else None,
        }
        query_params: str = urlencode(
            {k: v for k, v in clean_params.items() if v is not None}
        )
        url = urlunparse(self.base_url._replace(query=query_params))

        responseHtml = self.__amazon_request(url)
        if responseHtml is None:
            raise ValueError("Error while geting data from Amazon")

        products = self.__process_html(responseHtml)
        return products

    def __amazon_request(self, url: str) -> str:
        """
        Sends an HTTP GET request to the specified Amazon URL.

        Args:
            url (str): The URL to request.

        Returns:
            str | None: The response content as bytes if the request is successful,
                None otherwise.
        """
        data = ""
        try:
            response = requests.get(url, headers=self._HEADER, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Error while geting {url}:\t{response.content}")
                return data

            data = response.text
        except requests.HTTPError as error:
            self.logger.error(f"Error while fetching amazon url[{url}]\nError:{error}")

        return data

    def __parse_html(self, html: str) -> list[element.Tag]:
        """
        Parses the HTML content and extracts the relevant product divs.

        Args:
            html (str): The HTML content to parse.

        Returns:
            list[element.Tag]: A list of BeautifulSoup Tag objects, each representing a product search result.
        """
        soup = BeautifulSoup(html, "lxml")
        searchDivs = soup.find_all(
            "div", attrs={"data-component-type": "s-search-result"}
        )
        return searchDivs

    def __process_html(self, html: str) -> list[AmazonProduct]:
        """
        Processes the HTML content to extract product information.  Uses multithreading.

        Args:
            html (str): The HTML content to process.

        Returns:
            list[AmazonProduct]: A list of AmazonProduct objects.
        """
        products: list[AmazonProduct] = []
        divs = self.__parse_html(html)

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
            data.price = price.get("price")
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
        title = div.find(
            "div",
            attrs={
                "data-cy": "title-recipe",
            },
        )
        title = title.find("h2") if title else None
        return (
            title.find("span").string if title and title.find("span") else None
        )  # More robust check

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

    def __get_reviews(self, div: element.Tag) -> dict | None:
        review_div = div.find("div", attrs={"data-cy": "reviews-block"})
        if review_div:
            reviews = {}
            review_span = review_div.find(
                "span",
                attrs={"class": "a-size-small a-color-base", "aria-hidden": "true"},
            )
            reviews_number_span = review_div.find(
                "span", attrs={"data-component-type": "s-client-side-analytics"}
            )
            if reviews_number_span:
                # The inner span with aria-hidden="true" contains the count text
                inner_span = reviews_number_span.find(
                    "span", attrs={"aria-hidden": "true"}
                )
                if inner_span and inner_span.string:
                    count_text = inner_span.string.strip().replace(",", "")
                    reviews["reviews_number"] = count_text[1:-1]
                else:
                    reviews["reviews_number"] = None
            else:
                reviews["reviews_number"] = None

            if review_span:
                reviews["review"] = review_span.string

            return reviews
        return None

    def __get_price(self, div: element.Tag) -> dict | None:
        """
        Extracts the product price from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product price, or None if not found.
        """
        price_div = div.find("div", attrs={"data-cy": "price-recipe"})

        if price_div:
            price_span = price_div.find("span", attrs={"class": "a-offscreen"})
            if price_span and price_span.string:
                price = price_span.string.strip()
                p = price.split("\u00a0")
                return {"currency": p[0], "price": p[1]}

        price_div = div.find("div", attrs={"data-cy": "secondary-offer-recipe"})
        if price_div:
            price_span = price_div.find(
                "span",
                attrs={"class": "a-color-base"},
            )
            if price_span:
                price = price_span.string.strip()
                p = price.split("\u00a0")
                return {"currency": p[0], "price": p[1]}

        return None

    def __get_image(self, div: element.Tag) -> str | None:
        """
        Extracts the product image URL from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product image URL, or None if not found.
        """
        image = div.find("img", attrs={"class": "s-image"})
        return image.get("src") if image else None


if __name__ == "__main__":
    import json

    amazon = Amazon(False)
    results = amazon.search("mac", productType="electronics")
    print(json.dumps([i.get() for i in results], indent=2))
