"""Shared synthetic fixtures mirroring Amazon markup (no live scraping)."""

from __future__ import annotations

from typing import Optional

import pytest
from bs4 import BeautifulSoup

from amazon_product_search import Amazon

NBSP = "\u00a0"


def make_tag(html: str):
    """Parse a single product-div snippet into a bs4 Tag."""
    soup = BeautifulSoup(html, "lxml")
    return soup.find("div", attrs={"data-component-type": "s-search-result"})


def full_product_div(
    title: Optional[str] = "ThinkPad X1",
    href: Optional[str] = "/dp/B0TEST123",
    img: Optional[str] = "https://img.test/x1.jpg",
    review: Optional[str] = "4.5 out of 5 stars",
    count: Optional[str] = "(1,234)",
    price: Optional[str] = None,
):
    if price is None:
        price = "$" + NBSP + "999.00"
    review_html = ""
    if review is not None or count is not None:
        parts = ""
        if review is not None:
            parts += (
                '<span class="a-size-small a-color-base" aria-hidden="true">'
                + review
                + "</span>"
            )
        if count is not None:
            parts += (
                '<span data-component-type="s-client-side-analytics">'
                '<span aria-hidden="true">' + count + "</span></span>"
            )
        review_html = '<div data-cy="reviews-block">' + parts + "</div>"
    if price is not None:
        price_html = (
            '<div data-cy="price-recipe"><span class="a-offscreen">'
            + price
            + "</span></div>"
        )
    else:
        price_html = ""
    if title is not None:
        title_html = (
            '<div data-cy="title-recipe"><h2><span>' + title + "</span></h2></div>"
        )
    else:
        title_html = ""
    if img is not None:
        img_html = '<img class="s-image" src="' + img + '"/>'
    else:
        img_html = ""
    if href is not None:
        link_html = (
            '<span data-component-type="s-product-image"><a href="'
            + href
            + '">'
            + img_html
            + "</a></span>"
        )
    else:
        link_html = ""
    return make_tag(
        '<div data-component-type="s-search-result">'
        + title_html
        + link_html
        + review_html
        + price_html
        + "</div>"
    )


PAGINATION_HTML = """
<html><body>
<div data-csa-c-content-id="pagination-button">
  <span class="s-pagination-item s-pagination-selected" aria-current="page">1</span>
  <a class="s-pagination-item s-pagination-button" href="#">2</a>
  <a class="s-pagination-item s-pagination-button" href="#">3</a>
  <span class="s-pagination-item s-pagination-disabled">20</span>
</div>
<div data-component-type="s-search-result">
  <div data-cy="title-recipe"><h2><span>Item</span></h2></div>
</div>
</body></html>
"""


def _search_page_html() -> str:
    p1 = "$" + NBSP + "19.99"
    p2 = "$" + NBSP + "29.99"
    return (
        "<html><body>"
        '<div data-component-type="s-search-result">'
        '<div data-cy="title-recipe"><h2><span>Alpha</span></h2></div>'
        '<span data-component-type="s-product-image">'
        '<a href="/dp/A1"><img class="s-image" src="https://img.test/a.jpg"/></a></span>'
        '<div data-cy="reviews-block">'
        '<span class="a-size-small a-color-base" aria-hidden="true">4.0 out of 5 stars</span>'
        '<span data-component-type="s-client-side-analytics">'
        '<span aria-hidden="true">(10)</span></span></div>'
        '<div data-cy="price-recipe"><span class="a-offscreen">' + p1 + "</span></div>"
        "</div>"
        '<div data-component-type="s-search-result">'
        '<div data-cy="title-recipe"><h2><span>Beta</span></h2></div>'
        '<span data-component-type="s-product-image">'
        '<a href="/dp/B2"><img class="s-image" src="https://img.test/b.jpg"/></a></span>'
        '<div data-cy="price-recipe"><span class="a-offscreen">' + p2 + "</span></div>"
        "</div>"
        '<div data-csa-c-content-id="pagination-button">'
        '<span class="s-pagination-item s-pagination-selected">2</span>'
        '<a class="s-pagination-item s-pagination-button" href="#">1</a>'
        '<a class="s-pagination-item s-pagination-button" href="#">2</a>'
        '<span class="s-pagination-item s-pagination-disabled">5</span>'
        "</div></body></html>"
    )


SEARCH_PAGE_HTML = _search_page_html()


@pytest.fixture
def amazon():
    a = Amazon(workers=2)
    yield a
    a.close()
