"""Live smoke test — SKIPPED by default (needs network + Amazon reachability).

Run explicitly with: pytest -m live --run-live  (or AMZN_LIVE=1)
"""

from __future__ import annotations

import os

import pytest

from amazon_product_search import Amazon, AmazonResult

pytestmark = pytest.mark.live


def test_live_search_smoke():
    if not (os.getenv("AMZN_LIVE") == "1" or os.getenv("PYTEST_RUN_LIVE") == "1"):
        pytest.skip("live test opt-in only (AMZN_LIVE=1)")
    with Amazon(workers=2) as amazon:
        result = amazon.search("thinkpad", productType="electronics", page=1)
    assert isinstance(result, AmazonResult)
    assert result.current_page >= 1
    assert result.total_pages >= result.current_page
