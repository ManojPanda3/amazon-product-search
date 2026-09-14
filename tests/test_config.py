"""Config: MAX_WORKERS integer, workers override, debug flag."""

from __future__ import annotations

import logging

from amazon_product_search import amazon_product_search as mod
from amazon_product_search import Amazon


def test_max_workers_is_positive_int():
    assert isinstance(mod.MAX_WORKERS, int)
    assert mod.MAX_WORKERS >= 1


def test_default_workers_and_override():
    default = Amazon()
    try:
        assert default.workers == mod.MAX_WORKERS
    finally:
        default.close()
    a = Amazon(workers=8)
    try:
        assert a.workers == 8
    finally:
        a.close()


def test_debug_flag_sets_log_level():
    a = Amazon(is_debuging=True)
    try:
        assert a.logger.level == logging.DEBUG
    finally:
        a.close()
    b = Amazon(is_debuging=False)
    try:
        assert b.logger.level == logging.ERROR
    finally:
        b.close()
