"""HTML structure parsing: result div discovery and pagination state."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, element
from bs4.filter import SoupStrainer

__all__ = ["parse_html", "parse_pagination"]

logger = logging.getLogger(__name__)


def parse_html(html: str) -> list[element.Tag]:
    """
    Parses the HTML content and extracts the relevant product divs.
    Args:
        html (str): The HTML content to parse.
    Returns:
        list[element.Tag]: A list of BeautifulSoup Tag objects, each representing a product search result.
    """
    strainer = SoupStrainer("div", attrs={"data-component-type": "s-search-result"})
    soup = BeautifulSoup(html, "lxml", parse_only=strainer)
    searchDivs = soup.find_all(
        "div", attrs={"data-component-type": "s-search-result"}
    )
    return searchDivs



def parse_pagination(html: str, requested_page: int = 0) -> tuple[int, int]:
    """
    Extract pagination state from the container tagged
    data-csa-c-content-id="pagination-button".

    Args:
    html: Full response HTML.
    requested_page: Page requested `search()` (fallback when markup is missing).
    Returns:
    (current_page, total_pages)
    """
    fallback = requested_page if requested_page and requested_page > 0 else 1
    try:
        strainer = SoupStrainer(
            "div", attrs={"data-csa-c-content-id": "pagination-button"}
        )
        soup = BeautifulSoup(html, "lxml", parse_only=strainer)
        pagination_div = soup.find(
            "div", attrs={"data-csa-c-content-id": "pagination-button"}
        )
        if pagination_div is None:
            soup = BeautifulSoup(html, "lxml")
            pagination_div = soup.find(
                "div", attrs={"data-csa-c-content-id": "pagination-button"}
            )
        if pagination_div is None:
            return (fallback, fallback if fallback == 1 else fallback)
        current = fallback
        selected = pagination_div.find("span", class_="s-pagination-selected")
        if selected:
            txt = selected.get_text(strip=True)
            if txt.isdigit():
                current = int(txt)
            else:
                m = re.search(r"\d+", txt)
                if m:
                    current = int(m.group())
        elif requested_page:
            current = requested_page
        total = current
        items = pagination_div.find_all(
            ["a", "span"],
            class_=re.compile(r"s-pagination-item"),
        )
        nums: list[int] = []
        for el in items:
            txt = el.get_text(strip=True)
            if txt.isdigit():
                nums.append(int(txt))
            else:
                m = re.search(r"\d+", txt)
                if m and txt.strip("() ").isdigit() is False:
                    pass
        if nums:
            total = max(nums)
        if total < current:
            total = current
        if total < 1:
            total = 1
        return (current, total)
    except Exception as e:
        logger.debug(f"Pagination parse failed: {e}")
        return (fallback, fallback)
