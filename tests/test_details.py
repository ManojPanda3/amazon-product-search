"""Detail-page scraping: generalized schema and defensive parsing."""

from __future__ import annotations

import pytest

from amazon_product_search import AmazonProduct

DETAIL_HTML = """
<html>
<head>
  <link rel="canonical" href="https://www.amazon.com/dp/B0TEST1234"/>
</head>
<body>
  <input type="hidden" name="ASIN" value="B0TEST1234"/>
  <span id="productTitle">Test Product</span>
  <div id="bylineInfo">Visit the Acme Store</div>

  <div id="wayfinding-breadcrumbs_feature_div">
    <ul>
      <li><a>Electronics</a></li>
      <li><a>Computers</a></li>
    </ul>
  </div>

  <div id="corePriceDisplay_desktop_feature_div">
    <span class="a-price"><span class="a-offscreen">$1,299.99</span></span>
  </div>
  <div id="availability">In Stock</div>

  <div id="acrPopover" title="4.6 out of 5 stars"></div>
  <span id="acrCustomerReviewText">(1,234)</span>

  <div id="feature-bullets">
    <ul>
      <li><span class="a-list-item">Feature one</span></li>
      <li>Feature two</li>
    </ul>
  </div>

  <div id="detailBullets_feature_div">
    <ul class="detail-bullet-list">
      <li>
        <span class="a-text-bold">Language \u200f:\u200e</span>
        <span>English</span>
      </li>
      <li>
        <span class="a-text-bold">Item model number \u200f:\u200e</span>
        <span>X1</span>
      </li>
    </ul>
  </div>

  <div id="productDetails_techSpec_section_1">
    <table>
      <tr><th>Color</th><td>Black</td></tr>
      <tr><th>Best Sellers Rank</th><td>#1 in Electronics #2 in TVs</td></tr>
    </table>
  </div>

  <div id="landingImage" data-old-hires="https://m.media-amazon.com/images/I/landing.jpg"></div>

  <script>
    var gallery = {'colorImages': {'initial': A.$.parseJSON('[{"hiRes":"https://m.media-amazon.com/images/I/one.jpg"},{"large":"https://m.media-amazon.com/images/I/two.jpg"}]')}};
  </script>

  <script data-a-state='{"key":"desktop-twister-sort-filter-data"}' type="a-state">
    {"sortedDimValuesForAllDims":{"size_name":[
      {"dimensionValueDisplayText":"Large","defaultAsin":"B0TEST1234",
       "dimensionValueState":"SELECTED",
       "imageAttribute":{"url":"https://m.media-amazon.com/images/I/large.jpg"},
       "pageLoadURL":"/dp/B0TEST1234"},
      {"dimensionValueDisplayText":"Small","defaultAsin":"B0TEST1245",
       "dimensionValueState":"AVAILABLE",
       "slots":[{"metaData":{"key":"apexPrice"},"displayData":{
         "apexPriceViewModel":{"priceToPay":{"displayString":"$9.99","price":9.99}}}}],
       "pageLoadURL":"/dp/B0TEST1245"}
    ]}}
  </script>
</body>
</html>
"""

DETAIL_KEYS = {
    "asin",
    "title",
    "brand",
    "link",
    "breadcrumbs",
    "price",
    "price_value",
    "currency",
    "availability",
    "rating",
    "review_count",
    "best_sellers_rank",
    "features",
    "specifications",
    "product_details",
    "main_image",
    "images",
    "variations",
}


def test_deep_scrape_full_detail_page():
    product = AmazonProduct(link="https://www.amazon.com/dp/B0TEST1234")
    details = product.deep_scrape(html=DETAIL_HTML)

    assert details.asin == "B0TEST1234"
    assert details.title == "Test Product"
    assert details.brand == "Acme"
    assert details.link == "https://www.amazon.com/dp/B0TEST1234"
    assert details.breadcrumbs == ["Electronics", "Computers"]

    assert details.price == "$1,299.99"
    assert details.price_value == 1299.99
    assert details.currency == "$"
    assert details.availability == "In Stock"

    assert details.rating == 4.6
    assert details.review_count == 1234
    assert details.best_sellers_rank == ["#1 in Electronics", "#2 in TVs"]

    assert details.features == ["Feature one", "Feature two"]
    assert details.product_details["Language"] == "English"
    assert details.product_details["Item model number"] == "X1"
    assert details.specifications["Color"] == "Black"

    assert details.main_image == "https://m.media-amazon.com/images/I/landing.jpg"
    assert details.images == [
        "https://m.media-amazon.com/images/I/landing.jpg",
        "https://m.media-amazon.com/images/I/one.jpg",
        "https://m.media-amazon.com/images/I/two.jpg",
    ]

    assert len(details.variations) == 2
    selected = details.variations[0]
    assert selected["dimension"] == "Size"
    assert selected["value"] == "Large"
    assert selected["selected"] is True
    assert selected["available"] is True
    assert selected["url"] == "https://www.amazon.com/dp/B0TEST1234"

    other = details.variations[1]
    assert other["price"] == "$9.99"
    assert other["price_value"] == 9.99
    assert other["selected"] is False
    assert other["available"] is True

    assert set(details.get()) == DETAIL_KEYS


def test_deep_scrape_missing_markup_keeps_generalized_schema():
    product = AmazonProduct(link="https://www.amazon.com/dp/B0TEST1234")
    details = product.deep_scrape(html="<html><body></body></html>")

    # ASIN still comes from the link when the page has no ASIN input.
    assert details.asin == "B0TEST1234"
    assert details.title is None
    assert details.brand is None
    assert details.price is None
    assert details.price_value is None
    assert details.currency is None
    assert details.availability is None
    assert details.rating is None
    assert details.review_count is None
    assert details.main_image is None
    assert details.breadcrumbs == []
    assert details.best_sellers_rank == []
    assert details.features == []
    assert details.specifications == {}
    assert details.product_details == {}
    assert details.images == []
    assert details.variations == []
    assert set(details.get()) == DETAIL_KEYS


def test_deep_scrape_reads_local_file(tmp_path):
    path = tmp_path / "product.html"
    path.write_text(
        '<html><body><span id="productTitle">From Disk</span></body></html>',
        encoding="utf-8",
    )

    details = AmazonProduct(link=str(path)).deep_scrape()

    assert details.title == "From Disk"
    assert details.link is None


def test_deep_scrape_requires_link_without_html():
    with pytest.raises(ValueError, match="link is not valid"):
        AmazonProduct().deep_scrape()
