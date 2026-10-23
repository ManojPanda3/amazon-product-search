"""Data models and result containers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, element
from curl_cffi import requests as curl_requests

try:
    from typing import TypedDict
except ImportError:  # pragma: cover - Python 3.7 fallback only
    from typing_extensions import TypedDict

__all__ = [
    "AmazonProduct",
    "AmazonProductDetails",
    "AmazonResult",
    "PriceResult",
    "ReviewResult",
]

logger = logging.getLogger(__name__)

# Amazon rotates price widgets between pages/experiments. Try specific layouts
# first so installments/coupons are not mistaken for the product price.
_PRICE_SELECTORS = (
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#corePrice_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    "#buybox .a-price .a-offscreen",
    "#price_inside_buybox",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "#priceblock_saleprice",
    "#newBuyBoxPrice",
    "#tp_price_block_total_price_ww .a-offscreen",
    "#booksHeaderSection .a-color-price",
)

_SPEC_ROOTS = (
    "#productOverview_feature_div",
    "#features_and_specs",
    "#measurements",
    "#productDetails_techSpec_section_1",
    "#productDetails_detailBullets_sections1",
    "#productDetails_db_sections",
    "#technicalSpecifications_section_1",
    "#prodDetails",
    "#productDetails_feature_div",
)


# ---------------------------------------------------------------------------
# small HTML helpers
# ---------------------------------------------------------------------------


def _clean_text(value: object) -> str:
    """Collapse whitespace and remove Amazon's invisible direction marks."""
    if value is None:
        return ""
    text = str(value)
    for char in ("\u200b", "\u200e", "\u200f", "\u202a", "\u202c", "\u2066", "\u2069"):
        text = text.replace(char, "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _first_text(source: BeautifulSoup | element.Tag, selectors: tuple[str, ...]) -> str | None:
    """Return the first non-empty text matching one of ``selectors``."""
    for selector in selectors:
        node = source.select_one(selector)
        if node is None:
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if text:
            return text
    return None


def _first_attr(
    source: BeautifulSoup | element.Tag,
    selectors: tuple[str, ...],
    attribute: str,
) -> str | None:
    """Return the first non-empty attribute matching one of ``selectors``."""
    for selector in selectors:
        node = source.select_one(selector)
        if node is None:
            continue
        text = _clean_text(node.get(attribute))
        if text:
            return text
    return None


def _absolute_url(value: object, base_url: str) -> str | None:
    """Turn a possibly relative URL into an absolute one."""
    url = _clean_text(value)
    if not url or url.startswith(("data:", "javascript:")):
        return None
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base_url, url)


def _parse_float(value: object) -> float | None:
    """Parse the first number out of a display string, locale-tolerantly."""
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None

    number = match.group(0).rstrip(".,")
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            # 1.234,56 -> 1234.56
            number = number.replace(".", "").replace(",", ".")
        else:
            # 1,234.56 -> 1234.56
            number = number.replace(",", "")
    elif "," in number:
        # "1,234" (thousands) vs "19,99" (decimal comma)
        if re.search(r",\d{1,2}$", number):
            number = number.replace(",", ".")
        else:
            number = number.replace(",", "")

    try:
        return float(number)
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    """Parse counts like ``(112,193)`` or ``1.2K`` into an int."""
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([kKmMbB])?", text)
    if not match:
        return None
    number = _parse_float(match.group(1))
    if number is None:
        return None
    suffix = (match.group(2) or "").lower()
    if suffix:
        number *= {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
    return int(number)


def _canonical_link(soup: BeautifulSoup) -> str | None:
    value = _first_attr(soup, ('link[rel="canonical"]',), "href")
    if not value:
        value = _first_attr(soup, ('meta[property="og:url"]',), "content")
    return _absolute_url(value, "https://www.amazon.com")


# ---------------------------------------------------------------------------
# detail-page section parsers
# ---------------------------------------------------------------------------


def _find_asin(soup: BeautifulSoup, link: str | None) -> str | None:
    selectors = (
        'input[name="ASIN"]',
        "input#ASIN",
        "#averageCustomerReviews[data-asin]",
        "#dp[data-asin]",
        "#dp-container[data-asin]",
        "#prodDetails[data-asin]",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if node is None:
            continue
        value = _clean_text(node.get("value") or node.get("data-asin")).upper()
        if re.fullmatch(r"[A-Z0-9]{10}", value):
            return value

    for candidate in (link, _canonical_link(soup)):
        match = re.search(
            r"/(?:dp|gp/product|gp/aw/d)/([A-Za-z0-9]{10})(?:[/?]|$)",
            candidate or "",
        )
        if match:
            return match.group(1).upper()
    return None


def _parse_breadcrumbs(soup: BeautifulSoup) -> list[str]:
    breadcrumbs: list[str] = []
    for anchor in soup.select("#wayfinding-breadcrumbs_feature_div a"):
        text = _clean_text(anchor.get_text(" ", strip=True))
        if text and text not in {"›", ">"} and text not in breadcrumbs:
            breadcrumbs.append(text)
    return breadcrumbs


def _parse_features(soup: BeautifulSoup) -> list[str]:
    root = soup.find("div", attrs={"id": "feature-bullets"})
    if root is None:
        return []

    features: list[str] = []
    for item in root.find_all("li"):
        text = _clean_text(item.get_text(" ", strip=True))
        if not text or text.lower() in {"see more product details", "show more"}:
            continue
        if text not in features:
            features.append(text)
    return features


def _parse_detail_bullets(soup: BeautifulSoup) -> dict[str, str]:
    """Parse the ``detailBullets_feature_div`` key/value list."""
    root = soup.find("div", attrs={"id": "detailBullets_feature_div"})
    if root is None:
        return {}

    details: dict[str, str] = {}
    for item in root.select("ul.detail-bullet-list > li"):
        label_node = item.select_one("span.a-text-bold")
        if label_node is None:
            continue

        label = _clean_text(label_node.get_text(" ", strip=True)).rstrip(":").strip()
        if not label or label.lower() == "customer reviews":
            continue

        full = _clean_text(item.get_text(" ", strip=True))
        if full.startswith(label):
            value = full[len(label) :].lstrip(" :")
        else:
            value = full
        value = _clean_text(value)
        if value:
            details.setdefault(label, value)
    return details


def _collect_spec_row(row: element.Tag, specs: dict[str, str]) -> None:
    if row.find_parent(id="productDetails_feedback_sections") is not None:
        return

    cells = row.find_all(["th", "td"], recursive=False)
    if len(cells) < 2:
        return

    key = _clean_text(cells[0].get_text(" ", strip=True)).rstrip(":").strip()
    value = _clean_text(cells[1].get_text(" ", strip=True))
    if not key or not value or key.lower() == "customer reviews":
        return
    specs.setdefault(key, value)


def _parse_specifications(soup: BeautifulSoup) -> dict[str, str]:
    """Parse Amazon's various specification/overview tables."""
    specs: dict[str, str] = {}
    seen_rows: set[int] = set()

    for root in soup.select(", ".join(_SPEC_ROOTS)):
        for row in root.select("tr"):
            if id(row) in seen_rows:
                continue
            seen_rows.add(id(row))
            _collect_spec_row(row, specs)

    # Fallback for table layouts outside the known feature-div IDs.
    for row in soup.select("table.a-keyvalue tr"):
        if id(row) in seen_rows:
            continue
        seen_rows.add(id(row))
        _collect_spec_row(row, specs)
    return specs


def _parse_brand(
    soup: BeautifulSoup,
    specifications: dict[str, str],
    product_details: dict[str, str],
) -> str | None:
    for selector in ("#bylineInfo", "#visitStoreLink", "#pqv-byline", "#brand"):
        node = soup.select_one(selector)
        if node is None:
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        match = re.search(r"(?:Visit the|Brand:|From)\s+(.+?)(?:\s+Store)?$", text, re.I)
        brand = match.group(1) if match else text
        brand = re.sub(r"\s+Store$", "", brand, flags=re.I).strip(" :")
        if brand:
            return brand

    logo = soup.select_one("#logoByLine[alt], #bylineInfo img[alt]")
    if logo is not None:
        brand = _clean_text(logo.get("alt"))
        if brand:
            return brand

    for mapping in (specifications, product_details):
        for key in ("Brand Name", "Brand"):
            value = _clean_text(mapping.get(key))
            if value:
                return value
    return None


def _parse_best_sellers_rank(
    product_details: dict[str, str],
    specifications: dict[str, str],
) -> list[str]:
    rank_text = product_details.get("Best Sellers Rank") or specifications.get(
        "Best Sellers Rank"
    )
    if not rank_text:
        return []

    ranks: list[str] = []
    for part in re.split(r"(?=#[\d,]+\s+in\s+)", rank_text):
        text = _clean_text(part)
        if text and text not in ranks:
            ranks.append(text)
    return ranks


def _parse_price(soup: BeautifulSoup) -> tuple[str | None, float | None, str | None]:
    price_text = _first_text(soup, _PRICE_SELECTORS)
    price_value = _parse_float(price_text)

    currency = None
    if price_text:
        match = re.match(r"^\s*([^\d\s.,-]+)", price_text)
        if match:
            currency = match.group(1).strip() or None
    if not currency:
        currency = _first_attr(soup, ("#priceSymbol",), "value")
    if not currency:
        node = soup.select_one(
            "#corePriceDisplay_desktop_feature_div .a-price-symbol, "
            "#corePrice_feature_div .a-price-symbol, #buybox .a-price-symbol"
        )
        if node is not None:
            currency = _clean_text(node.get_text(" ", strip=True)) or None
    return price_text, price_value, currency


def _parse_availability(soup: BeautifulSoup) -> str | None:
    return _first_text(
        soup,
        (
            "#availability",
            "#outOfStockBuyBox_feature_div",
            "#availability_feature_div",
        ),
    )


def _parse_rating(soup: BeautifulSoup) -> float | None:
    text = _first_attr(soup, ("#acrPopover",), "title")
    if not text:
        text = _first_text(
            soup,
            (
                "#acrPopover .a-icon-alt",
                "span[data-hook='rating-out-of-text']",
                "#averageCustomerReviews .a-icon-alt",
            ),
        )
    if not text:
        return None
    match = re.search(r"([\d.]+)\s+out of\s+5", text, re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_review_count(soup: BeautifulSoup) -> int | None:
    text = _first_text(
        soup,
        (
            "#acrCustomerReviewText",
            "#acrCustomerReviewLink",
            "span[data-hook='total-review-count']",
        ),
    )
    return _parse_int(text)


def _parse_media(
    soup: BeautifulSoup, base_url: str
) -> tuple[str | None, list[str]]:
    landing = soup.find(id="landingImage")
    main_image = None
    if landing is not None:
        main_image = landing.get("data-old-hires") or landing.get("src")
    if not main_image:
        main_image = _first_attr(soup, ('meta[property="og:image"]',), "content")
    main_image = _absolute_url(main_image, base_url)

    images: list[str] = []

    def add(url: object) -> None:
        absolute = _absolute_url(url, base_url)
        if absolute and absolute not in images:
            images.append(absolute)

    # Highest-quality source: the gallery JSON in an inline script.
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if "colorImages" not in text:
            continue
        match = re.search(
            r"colorImages['\"]?\s*:\s*\{\s*['\"]initial['\"]\s*:\s*"
            r"A\.\$\.parseJSON\(\s*['\"](\[.*?\])['\"]\s*\)",
            text,
            re.S,
        )
        if not match:
            match = re.search(
                r"colorImages['\"]?\s*:\s*\{\s*['\"]initial['\"]\s*:\s*(\[.*?\])\s*[,}]",
                text,
                re.S,
            )
        if not match:
            continue
        try:
            gallery = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for item in gallery:
            if not isinstance(item, dict):
                continue
            add(item.get("hiRes") or item.get("large") or item.get("mainUrl"))
        if images:
            break

    # Fallback 1: the dynamic image map on the landing image.
    if not images and landing is not None:
        dynamic = landing.get("data-a-dynamic-image")
        if dynamic:
            try:
                for url in json.loads(dynamic):
                    add(url)
            except json.JSONDecodeError:
                pass

    # Fallback 2: gallery thumbnails.
    if not images:
        for image in soup.select("#altImages img"):
            add(image.get("data-old-hires") or image.get("src"))

    if main_image and main_image not in images:
        images.insert(0, main_image)
    return main_image, images


def _parse_variations(
    soup: BeautifulSoup,
    base_url: str,
    asin: str | None,
) -> list[dict[str, Any]]:
    state: dict[str, Any] | None = None
    for script in soup.find_all("script", attrs={"data-a-state": True}):
        try:
            meta = json.loads(script.get("data-a-state") or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if meta.get("key") != "desktop-twister-sort-filter-data":
            continue
        try:
            state = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            state = None
        break

    if not isinstance(state, dict):
        return []

    variations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    dimensions = state.get("sortedDimValuesForAllDims") or {}
    if not isinstance(dimensions, dict):
        return []
    for dimension, values in dimensions.items():
        label = dimension.replace("_name", "").replace("_", " ").title()
        for value in values or []:
            if not isinstance(value, dict):
                continue

            value_asin = _clean_text(value.get("defaultAsin")) or None
            value_text = _clean_text(value.get("dimensionValueDisplayText"))
            key = (dimension, value_asin or value_text)
            if key in seen:
                continue
            seen.add(key)

            price_text: str | None = None
            price_value: float | None = None
            for slot in value.get("slots") or []:
                if not isinstance(slot, dict):
                    continue
                meta_data = slot.get("metaData") or {}
                if not isinstance(meta_data, dict):
                    continue
                slot_key = meta_data.get("key")
                display = slot.get("displayData") or {}
                if not isinstance(display, dict):
                    continue
                if slot_key == "olp":
                    price_text = _clean_text(display.get("olpMessage")) or price_text
                    price_value = (
                        _parse_float(display.get("priceWithoutCurrencySymbol"))
                        or price_value
                    )
                elif slot_key == "apexPrice":
                    view_model = display.get("apexPriceViewModel") or {}
                    if not isinstance(view_model, dict):
                        continue
                    price_to_pay = view_model.get("priceToPay") or {}
                    if not isinstance(price_to_pay, dict):
                        continue
                    price_text = (
                        _clean_text(price_to_pay.get("displayString")) or price_text
                    )
                    raw_price = price_to_pay.get("price") or price_to_pay.get("amount")
                    if isinstance(raw_price, (int, float)):
                        price_value = float(raw_price)
                    else:
                        price_value = _parse_float(raw_price) or price_value

            page_url = value.get("pageLoadURL") or (
                f"/dp/{value_asin}" if value_asin else None
            )
            image_attribute = value.get("imageAttribute") or {}
            if not isinstance(image_attribute, dict):
                image_attribute = {}
            state_name = _clean_text(value.get("dimensionValueState")) or None
            normalized_state = state_name.upper() if state_name else None
            variations.append(
                {
                    "dimension": label,
                    "value": value_text or None,
                    "asin": value_asin,
                    "selected": normalized_state == "SELECTED"
                    or bool(asin and value_asin == asin),
                    "state": state_name,
                    "available": normalized_state in {"AVAILABLE", "SELECTED"},
                    "price": price_text or None,
                    "price_value": price_value,
                    "image": _absolute_url(image_attribute.get("url"), base_url),
                    "url": _absolute_url(page_url, base_url),
                }
            )
    return variations


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

    def deep_scrape(self, html: str | None = None) -> AmazonProductDetails:
        """Scrape commonly available details from this product's detail page.

        The returned :class:`AmazonProductDetails` always has the same shape:
        missing scalars are ``None`` and missing collections are empty. That
        makes it safe to consume pages that only render a subset of Amazon's
        widgets.

        Args:
            html: Optional raw HTML (for saved pages/tests). When omitted, the
                product ``link`` is read from disk if it is a file, otherwise
                fetched over HTTP.

        Raises:
            ValueError: If no link is set and no HTML is supplied.
        """
        target = (self.link or "").strip()
        source = html

        if source is None:
            if not target:
                raise ValueError("link is not valid")
            if not target.startswith(("http://", "https://")):
                path = Path(target).expanduser()
                if path.is_file():
                    source = path.read_text(encoding="utf-8", errors="replace")
            if source is None:
                response = curl_requests.get(
                    target,
                    impersonate="chrome124",
                    timeout=20,
                    allow_redirects=True,
                    headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                response.raise_for_status()
                source = response.text

        soup = BeautifulSoup(source, "lxml")
        product = AmazonProductDetails()

        if target.startswith(("http://", "https://")):
            product.link = target
            base_url = target
        else:
            product.link = _canonical_link(soup)
            base_url = product.link or "https://www.amazon.com"

        product.title = _first_text(soup, ("#productTitle", "#title"))
        if not product.title:
            product.title = _first_attr(
                soup, ('meta[property="og:title"]',), "content"
            )
        product.asin = _find_asin(soup, product.link or target)
        product.breadcrumbs = _parse_breadcrumbs(soup)
        product.features = _parse_features(soup)
        product.product_details = _parse_detail_bullets(soup)
        product.specifications = _parse_specifications(soup)
        product.brand = _parse_brand(
            soup, product.specifications, product.product_details
        )
        product.best_sellers_rank = _parse_best_sellers_rank(
            product.product_details, product.specifications
        )
        product.price, product.price_value, product.currency = _parse_price(soup)
        product.availability = _parse_availability(soup)
        product.rating = _parse_rating(soup)
        product.review_count = _parse_review_count(soup)
        product.main_image, product.images = _parse_media(soup, base_url)
        product.variations = _parse_variations(soup, base_url, product.asin)
        return product

    def __str__(self) -> str:
        return str(self.get())


@dataclass
class AmazonProductDetails:
    """Generalized snapshot of a product detail page.

    Amazon renders different sections for different products, so every field
    is optional: scalars default to ``None``, lists to ``[]`` and mappings to
    ``{}``. Consumers can rely on the same keys existing for every product.
    """

    # Identity
    asin: str | None = None
    title: str | None = None
    brand: str | None = None
    link: str | None = None
    breadcrumbs: list[str] = field(default_factory=list)

    # Offer
    price: str | None = None
    price_value: float | None = None
    currency: str | None = None
    availability: str | None = None

    # Social proof
    rating: float | None = None
    review_count: int | None = None
    best_sellers_rank: list[str] = field(default_factory=list)

    # Content
    features: list[str] = field(default_factory=list)
    specifications: dict[str, str] = field(default_factory=dict)
    product_details: dict[str, str] = field(default_factory=dict)

    # Media
    main_image: str | None = None
    images: list[str] = field(default_factory=list)

    # Variations (size, colour, style, ...)
    variations: list[dict[str, Any]] = field(default_factory=list)

    def get(self) -> dict[str, Any]:
        """Dict representation with the same keys for every product."""
        return asdict(self)

    def __str__(self) -> str:
        return json.dumps(self.get(), ensure_ascii=False, indent=2)


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
