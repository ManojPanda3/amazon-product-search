"""Per-product field extractors operating on a single result div."""

from __future__ import annotations

from bs4 import element

from .models import AmazonProduct, PriceResult, ReviewResult

__all__ = [
    "convert_review_to_number",
    "extract_data",
    "get_image",
    "get_link",
    "get_price",
    "get_reviews",
    "get_title",
    "split_currency_amount",
]


def get_title(div: element.Tag) -> str | None:
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



def get_link(div: element.Tag) -> str | None:
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



def convert_review_to_number(s: str) -> int:
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



def get_reviews(div: element.Tag) -> ReviewResult | None:
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
            reviews["reviews_number"] = convert_review_to_number(
                count_text[1:-1] if len(count_text) >= 2 else count_text
            )
        else:
            reviews["reviews_number"] = 0
    else:
        reviews["reviews_number"] = 0
    return reviews



def get_price(div: element.Tag) -> PriceResult | None:
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
                currency, amount = split_currency_amount(f, s)
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
                    currency, amount = split_currency_amount(f, s)
                    return {"currency": currency, "price": amount}
                try:
                    price = float(text)
                except ValueError:
                    price = 0.0
                return {"currency": "", "price": price}
    return None



def split_currency_amount(f: str, s: str) -> tuple[str, float]:
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



def get_image(div: element.Tag) -> str | None:
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



def extract_data(div: element.Tag) -> AmazonProduct | None:
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
    data.title = get_title(div)
    data.link = get_link(div)
    review = get_reviews(div)
    if review:
        data.review = review.get("review")
        data.review_numbers = review.get("reviews_number")
    price = get_price(div)
    if price is not None:
        data.price = price.get("price", 0.0)
        data.currency = price.get("currency")
    data.image = get_image(div)
    return data
