from requests import get as get_request
from bs4 import BeautifulSoup, element
from dataclasses import dataclass
import concurrent.futures


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
    price: str | None = None
    image: str | None = None

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
            "price": self.price,
            "image": self.image,
        }


class Amazon:
    """
    Provides methods to search for products on Amazon and extract product information.
    """

    def __init__(self, is_debuging: bool = False) -> None:
        """
        Initializes an Amazon object.

        Args:
            is_debuging (bool): If True, enables debugging output (e.g., prints the URL and response content).
                Defaults to False.
        """

        self.base_url: str = "https://www.amazon.com/s?"
        self._HEADER: dict = {
            "User-Agent": "Mozilla/5.0 (X11; Linuin zipx x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": "en-US, en;q=0.5",
        }
        self.is_debuging = is_debuging

    def search(
        self,
        productName: str,
        productType: str | None = None,
        brand: str | None = None,
        priceRange: str | None = None,
    ) -> list[dict]:
        """
        Searches for products on Amazon based on the provided criteria.

        Args:
            productName (str): The name of the product to search for (required).
            productType (str | None): The type of product (e.g., "electronics").  Optional.
            brand (str | None): The brand of the product. Optional.
            priceRange (str | None): The price range of the product.  Optional.

        Returns:
            list[dict]: A list of dictionaries, where each dictionary represents a product
                and contains its title, link, review, price, and image URL.

        Raises:
            ValueError: If productName is empty.
            Exception: If there is an error fetching data from Amazon.
        """
        if productName.strip() == "":
            raise ValueError("Error product Name is required")

        url = self.base_url
        url += "&k=" + productName

        if productType is not None and productType.strip() != "":
            url += "&i=" + productType
        if brand is not None and brand.strip() != "":
            url += "&brand=" + brand
        if priceRange is not None and priceRange.strip() != "":
            url += "&price=" + priceRange
        if self.is_debuging:
            print("url: ", url)

        responseHtml = self.__amazon_request(url)
        if responseHtml is None:
            raise Exception("Error while geting data from Amazon")

        processed_html = self.__process_html(responseHtml)
        return [data.get() for data in processed_html]

    def __amazon_request(self, url: str) -> bytes | None:
        """
        Sends an HTTP GET request to the specified Amazon URL.

        Args:
            url (str): The URL to request.

        Returns:
            bytes | None: The response content as bytes if the request is successful,
                None otherwise.
        """
        try:
            response = get_request(
                url, headers=self._HEADER, timeout=10
            )  # Added timeout
            if response.status_code != 200:
                print(
                    "Error while geting {url}:\n{error} ".format(
                        url=url, error=response.content
                    )
                )
                return None
            data = response.content
            if self.is_debuging:
                print("Content: ", data)
            return data
        except Exception as error:
            if self.is_debuging:
                print(
                    "Error while fetching amazon url[{url}]\nError:{error}".format(
                        url=url, error=error
                    )
                )
            return None

    def __parse_html(self, html: str) -> list[element.Tag]:
        """
        Parses the HTML content and extracts the relevant product divs.

        Args:
            html (str): The HTML content to parse.

        Returns:
            list[element.Tag]: A list of BeautifulSoup Tag objects, each representing a product search result.
        """
        soup = BeautifulSoup(html, "lxml")  # Use lxml parser
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
        datas: list[AmazonProduct] = []
        divs = self.__parse_html(html)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=10
        ) as executor:  # Use ThreadPoolExecutor
            futures = [executor.submit(self.__extract_data, div) for div in divs]
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data:
                    datas.append(data)
        return datas

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
        data.review = self.__get_reviews(div)
        data.price = self.__get_price(div)
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
                    return "https://www.amazon.com" + href
        return None

    def __get_reviews(self, div: element.Tag) -> str | None:
        """
        Extracts the product review string from a product div.

        Args:
            div (element.Tag): A BeautifulSoup Tag representing a product.

        Returns:
            str | None: The product review string, or None if not found.
        """
        review_div = div.find("div", attrs={"data-cy": "reviews-block"})
        if review_div:
            review_span = review_div.find("span", attrs={"class": "a-icon-alt"})
            if review_span:
                return review_span.string
        return None

    def __get_price(self, div: element.Tag) -> str | None:
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
            if price_span:
                return price_span.string
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
    amazon = Amazon(False)
    results = amazon.search("iPhone", productType="electronics")
    print(results)

