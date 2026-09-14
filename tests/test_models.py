"""Dataclass contracts: AmazonProduct / AmazonResult."""

from __future__ import annotations

from amazon_product_search import AmazonProduct, AmazonResult


def test_product_get_and_str():
    # Types mirror the dataclass: review_numbers int, price float
    # (parser coerces via __convert_review_to_number / float()).
    p = AmazonProduct(title="T", link="L", review="4 stars", review_numbers=12,
                      price=9.99, currency="$", image="I")
    d = p.get()
    assert d == {"title": "T", "link": "L", "review": "4 stars",
                 "review_numbers": 12, "currency": "$",
                 "price": 9.99, "image": "I"}
    assert "T" in str(p)


def test_product_defaults_none():
    p = AmazonProduct()
    assert p.get() == {"title": None, "link": None, "review": None,
                       "review_numbers": None, "currency": None,
                       "price": None, "image": None}


def test_result_iter_len_getitem_get():
    ps = [AmazonProduct(title="A"), AmazonProduct(title="B")]
    r = AmazonResult(products=ps, current_page=2, total_pages=5)
    assert len(r) == 2
    assert [x.title for x in r] == ["A", "B"]
    assert r[0].title == "A" and r[1].title == "B"
    d = r.get()
    assert d["current_page"] == 2 and d["total_pages"] == 5
    assert [x["title"] for x in d["products"]] == ["A", "B"]


def test_result_defaults():
    r = AmazonResult()
    assert len(r) == 0 and list(r) == []
    assert (r.current_page, r.total_pages) == (1, 1)
