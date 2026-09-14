"""Pagination parsing: selected/total/ellipsis/missing/exception paths."""

from __future__ import annotations

from tests.conftest import PAGINATION_HTML


def test_standard_widget(amazon):
    cur, total = amazon._Amazon__parse_pagination(PAGINATION_HTML, requested_page=1)
    assert (cur, total) == (1, 20)


def test_requested_page_fallback_when_no_widget(amazon):
    html = "<html><body><p>no pagination here</p></body></html>"
    assert amazon._Amazon__parse_pagination(html, requested_page=3) == (3, 3)
    assert amazon._Amazon__parse_pagination(html, requested_page=0) == (1, 1)


def test_missing_selected_uses_requested_page(amazon):
    html = """
    <html><body><div data-csa-c-content-id="pagination-button">
      <a class="s-pagination-item s-pagination-button" href="#">1</a>
      <a class="s-pagination-item s-pagination-button" href="#">2</a>
    </div></body></html>
    """
    cur, total = amazon._Amazon__parse_pagination(html, requested_page=2)
    assert cur == 2
    assert total == 2


def test_total_never_below_current(amazon):
    html = """
    <html><body><div data-csa-c-content-id="pagination-button">
      <span class="s-pagination-item s-pagination-selected">7</span>
      <a class="s-pagination-item s-pagination-button" href="#">2</a>
    </div></body></html>
    """
    cur, total = amazon._Amazon__parse_pagination(html, requested_page=7)
    assert cur == 7
    assert total >= 7


def test_total_clamped_when_items_below_selected(amazon):
    # selected span WITHOUT s-pagination-item class: nums=[2] < current=7
    # exercises the `total < current -> total = current` guard.
    html = """
    <html><body><div data-csa-c-content-id="pagination-button">
      <span class="s-pagination-selected">7</span>
      <a class="s-pagination-item s-pagination-button" href="#">2</a>
    </div></body></html>
    """
    cur, total = amazon._Amazon__parse_pagination(html, requested_page=1)
    assert (cur, total) == (7, 7)


def test_non_numeric_items_ignored(amazon):
    html = """
    <html><body><div data-csa-c-content-id="pagination-button">
      <span class="s-pagination-item s-pagination-selected">1</span>
      <a class="s-pagination-item s-pagination-button" href="#">Next</a>
      <a class="s-pagination-item s-pagination-button" href="#">Previous</a>
      <span class="s-pagination-item s-pagination-disabled">8</span>
    </div></body></html>
    """
    assert amazon._Amazon__parse_pagination(html) == (1, 8)


def test_garbage_html_returns_fallback(amazon):
    cur, total = amazon._Amazon__parse_pagination("", requested_page=0)
    assert (cur, total) == (1, 1)


def test_selected_regex_fallback(amazon):
    html = """
    <html><body><div data-csa-c-content-id="pagination-button">
      <span class="s-pagination-item s-pagination-selected">Page 3</span>
      <a class="s-pagination-item s-pagination-button" href="#">3</a>
    </div></body></html>
    """
    cur, total = amazon._Amazon__parse_pagination(html, requested_page=1)
    assert cur == 3
    assert total == 3


def test_exception_path_returns_fallback(amazon):
    cur, total = amazon._Amazon__parse_pagination(None, requested_page=4)
    assert (cur, total) == (4, 4)
