# Testing guide

## Tooling

- Framework: **pytest** (+ **coverage** for gates). Install: `pip install -e ".[test]"`.
- Private helpers are tested via name mangling: `amazon._Amazon__parse_pagination(...)`.
- The `amazon` fixture in `tests/conftest.py` yields `Amazon(workers=2)` and closes it.

## Commands

```bash
pytest tests/ -q -m "not live"          # default: offline suite (43 tests)
pytest tests/ -q                        # same — live test self-skips without AMZN_LIVE=1
AMZN_LIVE=1 pytest tests/test_live.py -q -m live   # opt-in live smoke (hits amazon.com)
coverage run -m pytest tests/ -q -m "not live"
coverage report --include="amazon_product_search/*"   # gate: --fail-under=85 (currently ~97%)
```

CI (`.github/workflows/test.yml`) runs the offline suite + coverage gate on
Python 3.9 and 3.12 for every push/PR.

## Layout

| File | Covers |
|---|---|
| `test_url_building.py` | `search()` validation, `page` normalisation, filter encoding, mocked end-to-end pagination |
| `test_request.py` | `__amazon_request` (200 / non-200 / exception), session headers, `close()` + context manager |
| `test_parse_html.py` — folded into `test_extractors.py` | `SoupStrainer` scoping |
| `test_pagination.py` | selected/total/ellipsis/missing-widget/regex/exception paths |
| `test_extractors.py` | all six field extractors, `__extract_data` (incl. `None`/`0` defaults, `K`-suffix counts, comma prices, garbage-price no-crash), `__convert_review_to_number` (`K`/`M`/`B`/empty/garbage), `__split_currency_amount`, `__process_html` threading |
| `test_models.py` | `AmazonProduct`/`AmazonResult` contracts |
| `test_config.py` | `MAX_WORKERS` int, `workers=` override, debug log level |
| `test_live.py` (`@pytest.mark.live`) | opt-in real-Amazon smoke; caution: rate-limit/ToS risk — never run in CI |

## Fixture policy

- **Synthetic minimal HTML only** (`tests/conftest.py`: `full_product_div()`,
  `make_tag()`, `PAGINATION_HTML`, `SEARCH_PAGE_HTML`). No committed scraped
  pages (ToS + brittleness). Mirror the anchors in `SELECTORS.md`.
- NBSP (`\u00a0`) price splitting is built via the `NBSP` constant — never a
  literal invisible character.

## Known coverage gaps (accepted)

- `__parse_pagination`: `if total < 1: total = 1` — unreachable when
  `current >= 1` (total is clamped to `current` first). Defensive only.
- `if __name__ == "__main__":` demo block — excluded via
  `[tool.coverage.report] exclude_lines` in `pyproject.toml`.

## Adding a regression test (markup change)

1. Add minimal snippet to `tests/conftest.py`.
2. Add failing test in `test_extractors.py` / `test_pagination.py`.
3. Fix extractor + update `docs/SELECTORS.md` in the same change.
4. Re-run suite + coverage before pushing.
