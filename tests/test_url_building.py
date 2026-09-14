"""URL building, validation, and search() orchestration (network mocked)."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from amazon_product_search import Amazon
from tests.conftest import SEARCH_PAGE_HTML


def _captured_url(amazon, **kwargs):
    captured = {}

    def fake(url):
        captured["url"] = url
        return SEARCH_PAGE_HTML

    with patch.object(Amazon, "_Amazon__amazon_request", side_effect=fake):
        amazon.search(**kwargs)
    return captured["url"]


def test_search_rejects_empty_name(amazon):
    with pytest.raises(ValueError, match="product Name is required"):
        amazon.search("")
    with pytest.raises(ValueError, match="product Name is required"):
        amazon.search("   ")


def test_search_raises_when_no_html(amazon):
    with patch.object(Amazon, "_Amazon__amazon_request", return_value=""):
        with pytest.raises(ValueError, match="geting data from Amazon"):
            amazon.search("thinkpad")


def test_page_0_and_1_omit_page_param(amazon):
    for page in (0, 1):
        url = _captured_url(amazon, productName="thinkpad", page=page)
        qs = parse_qs(urlparse(url).query)
        assert qs["k"] == ["thinkpad"]
        assert "page" not in qs


def test_page_gt1_included(amazon):
    url = _captured_url(amazon, productName="thinkpad", page=2)
    qs = parse_qs(urlparse(url).query)
    assert qs["page"] == ["2"]


def test_optional_filters_encoded_and_blank_omitted(amazon):
    url = _captured_url(
        amazon,
        productName="iPhone",
        productType="electronics",
        brand="Apple",
        priceRange="80000-100000",
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["k"] == ["iPhone"]
    assert qs["i"] == ["electronics"]
    assert qs["brand"] == ["Apple"]
    assert qs["price"] == ["80000-100000"]

    url2 = _captured_url(
        amazon, productName="laptop", productType="  ", brand="", priceRange=""
    )
    qs2 = parse_qs(urlparse(url2).query)
    assert "i" not in qs2 and "brand" not in qs2 and "price" not in qs2


def test_special_chars_encoded(amazon):
    url = _captured_url(amazon, productName="think pad & co")
    assert "think+pad" in url or "think%20pad" in url


def test_search_returns_pagination_from_fixture(amazon):
    with patch.object(
        Amazon, "_Amazon__amazon_request", return_value=SEARCH_PAGE_HTML
    ):
        result = amazon.search("laptop", page=2)
    assert result.current_page == 2
    assert result.total_pages == 5
    assert len(result) == 2
    titles = {p.title for p in result.products}
    assert titles == {"Alpha", "Beta"}
