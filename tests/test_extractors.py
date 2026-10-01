"""Field extractors + __extract_data + __parse_html/__process_html."""

from __future__ import annotations

from bs4 import BeautifulSoup

from amazon_product_search.extractors import (
    convert_review_to_number,
    extract_data,
    get_image,
    get_link,
    get_price,
    get_reviews,
    get_title,
    split_currency_amount,
)
from amazon_product_search.parsers import parse_html
from tests.conftest import NBSP, full_product_div, make_tag


def test_get_title_ok_and_missing(amazon):
    assert get_title(full_product_div(title="Hello")) == "Hello"
    empty = make_tag('<div data-component-type="s-search-result"></div>')
    assert get_title(empty) is None
    no_h2 = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="title-recipe"><p>no h2</p></div></div>'
    )
    assert get_title(no_h2) is None


def test_get_link_ok_and_missing(amazon):
    assert (
        get_link(full_product_div(href="/dp/X1"))
        == "https://www.amazon.com/dp/X1"
    )
    assert get_link(full_product_div(href=None)) is None
    assert extract_data(None) is None


def test_get_reviews_full_and_variants(amazon):
    # __get_reviews converts counts to int itself (k/m/b via converter).
    r = get_reviews(full_product_div())
    assert r["review"] == "4.5 out of 5 stars"
    assert r["reviews_number"] == 1234  # parens stripped, comma removed, int

    r2 = get_reviews(full_product_div(review=None, count="(5)"))
    assert "review" not in r2
    assert r2["reviews_number"] == 5

    r3 = get_reviews(full_product_div(review=None, count=None))
    assert r3 is None  # no reviews-block at all

    no_block = make_tag('<div data-component-type="s-search-result"></div>')
    assert get_reviews(no_block) is None


def test_get_reviews_number_missing_inner(amazon):
    # analytics span present but no inner aria-hidden span -> 0
    div = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="reviews-block">'
        '<span class="a-size-small a-color-base" aria-hidden="true">5 stars</span>'
        '<span data-component-type="s-client-side-analytics"></span>'
        "</div></div>"
    )
    r = get_reviews(div)
    assert r["review"] == "5 stars"
    assert r["reviews_number"] == 0

    # analytics span missing entirely -> 0
    div2 = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="reviews-block">'
        '<span class="a-size-small a-color-base" aria-hidden="true">5 stars</span>'
        "</div></div>"
    )
    assert get_reviews(div2)["reviews_number"] == 0


def test_get_price_primary_nbsp_and_fallback(amazon):
    # __get_price returns float amounts; decimals must parse as amounts
    # (regression: str.isnumeric() rejects "999.00" — must use float()).
    p = get_price(full_product_div())
    assert p == {"currency": "$", "price": 999.0}

    no_nbsp = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="price-recipe"><span class="a-offscreen">$19.99</span></div></div>'
    )
    # No NBSP separator: "$19.99" can't split currency/amount -> 0.0, no crash.
    assert get_price(no_nbsp) == {"currency": "", "price": 0.0}

    bare_numeric = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="price-recipe"><span class="a-offscreen">19.99</span></div></div>'
    )
    assert get_price(bare_numeric) == {"currency": "", "price": 19.99}

    secondary = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="secondary-offer-recipe">'
        '<span class="a-color-base">'
        + ("Rs" + NBSP + "499")
        + "</span></div></div>"
    )
    assert get_price(secondary) == {"currency": "Rs", "price": 499.0}

    garbage = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="price-recipe"><span class="a-offscreen">Free</span></div></div>'
    )
    assert get_price(garbage) == {"currency": "", "price": 0.0}

    empty = make_tag('<div data-component-type="s-search-result"></div>')
    assert get_price(empty) is None


def test_split_currency_amount(amazon):
    split = split_currency_amount
    assert split("$", "19.99") == ("$", 19.99)
    assert split("19.99", "$") == ("$", 19.99)
    assert split("10", "20") == ("", 20.0)
    assert split("abc", "def") == ("def", 0.0)


def test_get_price_secondary_nested_text(amazon):
    # secondary-offer span with nested children: .string is None -> get_text path.
    # Non-numeric text must yield 0.0, never raise (regression: unguarded float()).
    div = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="secondary-offer-recipe">'
        '<span class="a-color-base"><b>Rs</b><i>499</i></span></div></div>'
    )
    assert get_price(div) == {"currency": "", "price": 0.0}

    div2 = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="secondary-offer-recipe">'
        '<span class="a-color-base"><b>Rs' + NBSP + "499</b><i></i></span></div></div>"
    )
    assert get_price(div2) == {"currency": "Rs", "price": 499.0}


def test_get_image_ok_and_missing(amazon):
    assert (
        get_image(full_product_div(img="https://i.test/a.jpg"))
        == "https://i.test/a.jpg"
    )
    assert get_image(full_product_div(img=None, href="/dp/A")) is None


def test_extract_data_combines_fields(amazon):
    prod = extract_data(full_product_div())
    assert prod.title == "ThinkPad X1"
    assert prod.link == "https://www.amazon.com/dp/B0TEST123"
    assert prod.review == "4.5 out of 5 stars"
    assert prod.review_numbers == 1234
    assert isinstance(prod.review_numbers, int)
    assert prod.currency == "$"
    assert prod.price == 999.00
    assert isinstance(prod.price, float)
    assert prod.image == "https://img.test/x1.jpg"
    d = prod.get()
    assert set(d) == {
        "title",
        "link",
        "review",
        "review_numbers",
        "currency",
        "price",
        "image",
    }


def test_extract_data_missing_review_defaults(amazon):
    # No reviews-block at all -> review dict None -> fields untouched (None).
    prod = extract_data(full_product_div(review=None, count=None))
    assert prod.review is None
    assert prod.review_numbers is None

    # Block present but review text missing -> review None (.get default),
    # count converted to int by __get_reviews.
    div = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="reviews-block">'
        '<span data-component-type="s-client-side-analytics">'
        '<span aria-hidden="true">(10)</span></span>'
        "</div></div>"
    )
    prod2 = extract_data(div)
    assert prod2.review is None
    assert prod2.review_numbers == 10


def test_extract_data_review_suffix_and_comma_price(amazon):
    prod = extract_data(
        full_product_div(count="(1.2K)", price="$" + NBSP + "1,999.00")
    )
    assert prod.review_numbers == 1200
    assert prod.price == 1999.00


def test_extract_data_garbage_price_never_crashes(amazon):
    # Non-numeric price anywhere must degrade to 0.0, not raise out of the worker.
    div = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="title-recipe"><h2><span>G</span></h2></div>'
        '<div data-cy="price-recipe"><span class="a-offscreen">$19.99</span></div></div>'
    )
    prod = extract_data(div)
    assert prod.price == 0.0
    assert prod.currency == ""

    nested = make_tag(
        '<div data-component-type="s-search-result">'
        '<div data-cy="title-recipe"><h2><span>G</span></h2></div>'
        '<div data-cy="secondary-offer-recipe">'
        '<span class="a-color-base"><b>Rs</b><i>499</i></span></div></div>'
    )
    prod2 = extract_data(nested)
    assert prod2.price == 0.0


def test_convert_review_to_number(amazon):
    conv = convert_review_to_number
    assert conv("1234") == 1234
    assert conv("0") == 0
    assert conv("") == 0
    assert conv("10") == 10
    assert conv("1.2K") == 1200
    assert conv("2.5k") == 2500
    assert conv("3M") == 3_000_000
    assert conv("1B") == 1_000_000_000
    assert conv("n/a") == 0


def test_parse_html_finds_only_product_divs(amazon):
    html = (
        "<html><body>"
        '<div data-component-type="s-search-result"><span>A</span></div>'
        '<div data-component-type="s-search-result"><span>B</span></div>'
        '<div class="noise"><span>C</span></div>'
        "</body></html>"
    )
    divs = parse_html(html)
    assert len(divs) == 2


def test_process_html_empty_and_threaded(amazon):
    assert amazon._Amazon__process_html("<html></html>") == []
    html = "<html><body>"
    for i in range(6):
        html += (
            '<div data-component-type="s-search-result">'
            '<div data-cy="title-recipe"><h2><span>Item%d</span></h2></div>'
            "</div>" % i
        )
    html += "</body></html>"
    products = amazon._Amazon__process_html(html)
    assert len(products) == 6
    assert {p.title for p in products} == {"Item%d" % i for i in range(6)}


def test_beautifulsoup_import_sanity():
    soup = BeautifulSoup("<p>x</p>", "lxml")
    assert soup.p is not None and soup.p.get_text() == "x"
